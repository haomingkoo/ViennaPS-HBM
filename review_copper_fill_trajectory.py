"""Review the coarse full-2D Cu-fill trajectory mechanism screen.

The reviewer deliberately separates a simulator-reported screen pass from an
accepted mechanism result.  A trajectory that changes topology faster than
its configured front can move remains visible, but cannot support a pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json"
)
DEFAULT_ROWS = Path(
    "autoresearch-results/restart_audit/copper_fill_trajectory_rows.jsonl"
)
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/copper_fill_trajectory_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/copper_fill_trajectory_review.md"
)

CASE_FIELDS = (
    "manifest_version",
    "design",
    "geometry",
    "layers",
    "model",
    "numerics",
    "target",
    "provenance",
    "runtime_fingerprint",
    "rng_seed",
)


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def case_id(case):
    payload = json.dumps(case, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def expected_runtime_fingerprint(manifest, project_root):
    """Build the fingerprint expected by the runner without importing it."""
    root = Path(project_root)
    return {
        "runner_sha256": _sha256_file(
            root / "foundation_copper_fill_trajectory.py"
        ),
        "traveler_metrics_sha256": _sha256_file(root / "traveler_metrics.py"),
        "tsv_process_sha256": _sha256_file(root / "tsv_process.py"),
        "viennaps_binary_sha256": manifest["provenance"].get(
            "viennaps_binary_sha256"
        ),
    }


def expand_expected_cases(manifest, runtime_fingerprint):
    cases = []
    for design in manifest["designs"]:
        for seed in design["rng_seeds"]:
            case = {
                "manifest_version": manifest["manifest_version"],
                "design": design["name"],
                "geometry": manifest["geometry"],
                "layers": manifest["layers"],
                "model": {**manifest["model"], **design["model"]},
                "numerics": {
                    **manifest["numerics"],
                    **design.get("numerics", {}),
                },
                "target": manifest["target"],
                "provenance": manifest["provenance"],
                "runtime_fingerprint": dict(runtime_fingerprint),
                "rng_seed": seed,
            }
            case["case_id"] = case_id(case)
            cases.append(case)
    return cases


def load_jsonl(path):
    path = Path(path)
    if not path.exists():
        return [], [], True
    rows = []
    parse_errors = []
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
            if not isinstance(row, dict):
                raise TypeError("JSONL row is not an object")
            rows.append(row)
        except Exception as error:
            parse_errors.append({
                "line_number": line_number,
                "error": repr(error),
                "raw_line": raw_line,
            })
    return rows, parse_errors, False


def _case_payload(row):
    return {key: row.get(key) for key in CASE_FIELDS}


def _logical_key(row):
    return row.get("design"), row.get("rng_seed")


def _attempt_validation_errors(row, expected, runtime_fingerprint):
    errors = []
    if row.get("case_id") != expected["case_id"]:
        errors.append("case_id does not match the manifest/runtime fingerprint")
    if row.get("runtime_fingerprint") != runtime_fingerprint:
        errors.append("runtime fingerprint does not match the reviewed files")
    if row.get("case_id") != case_id(_case_payload(row)):
        errors.append("case_id does not match the row's own case payload")
    for key in CASE_FIELDS:
        if row.get(key) != expected.get(key):
            errors.append(f"case field differs from manifest: {key}")
    if row.get("production_doe_eligible") is not False:
        errors.append("row is not explicitly marked production_doe_eligible=false")
    return errors


def _is_superseded_fingerprint_attempt(row, expected, runtime_fingerprint):
    """Recognize a self-consistent result from an older reviewed runner."""
    if row.get("runtime_fingerprint") == runtime_fingerprint:
        return False
    if row.get("case_id") != case_id(_case_payload(row)):
        return False
    if row.get("production_doe_eligible") is not False:
        return False
    return all(
        row.get(key) == expected.get(key)
        for key in CASE_FIELDS
        if key != "runtime_fingerprint"
    )


def _checkpoint_failure(checkpoint):
    topology = checkpoint.get("topology", {})
    protected = checkpoint.get("protected_stack", {})
    diagnostics = checkpoint.get("model_diagnostics", {})
    return {
        "pinch_off": bool(
            checkpoint.get("pinch_off_seen")
            or topology.get("pinch_off_failure")
        ),
        "invalid_topology": bool(
            checkpoint.get("invalid_topology_seen")
            or topology.get("topology_valid") is False
        ),
        "topology_transition": bool(
            checkpoint.get("topology_transition_failure_seen")
            or checkpoint.get("topology_transition", {}).get("valid") is False
        ),
        "protected_stack": bool(
            checkpoint.get("protected_failure_seen")
            or protected.get("survives") is False
        ),
        "model_diagnostic": bool(
            checkpoint.get("model_failure_seen")
            or diagnostics.get("valid") is False
        ),
    }


def _persistent_failures(row):
    keys = (
        ("pinch_off", "pinch_off_seen"),
        ("invalid_topology", "invalid_topology_seen"),
        (
            "topology_transition",
            "topology_transition_failure_seen",
        ),
        ("protected_stack", "protected_failure_seen"),
        ("model_diagnostic", "model_failure_seen"),
    )
    result = {}
    trajectory = row.get("trajectory", [])
    for name, row_key in keys:
        first = next(
            (
                checkpoint
                for checkpoint in trajectory
                if _checkpoint_failure(checkpoint)[name]
            ),
            None,
        )
        result[name] = {
            "seen": bool(row.get(row_key) or first is not None),
            "first_checkpoint": first.get("checkpoint") if first else None,
            "first_elapsed": first.get("elapsed") if first else None,
        }
    return result


def topology_transition_failures(row):
    """Return recorded hard transition classifications, preserving tail data.

    Current rows use the width-aware runner classification.  The depth-only
    fallback exists solely so older rows remain auditable.
    """
    trajectory = row.get("trajectory", [])
    if not trajectory:
        return []
    recorded = []
    for checkpoint in trajectory:
        transition = checkpoint.get("topology_transition", {})
        if transition.get("valid") is False:
            recorded.append({
                "type": transition.get(
                    "classification", "topology_transition_failure"
                ),
                "checkpoint": checkpoint.get("checkpoint"),
                "elapsed": checkpoint.get("elapsed"),
                "unresolved_seam_risk": bool(
                    transition.get("unresolved_seam_risk")
                ),
                "tail_height": transition.get("disappearing_tail_height"),
                "tail_maximum_width": transition.get(
                    "disappearing_tail_max_width"
                ),
                "tail_aspect_ratio": transition.get(
                    "disappearing_tail_aspect_ratio"
                ),
                "closure_width_bound": transition.get("closure_width_bound"),
                "open_void_depth_before": transition.get(
                    "previous_open_void_depth"
                ),
                "open_void_depth_after": transition.get(
                    "current_open_void_depth"
                ),
                "depth_drop": transition.get(
                    "observed_open_void_depth_drop"
                ),
                "message": transition.get("reason"),
            })
    if recorded:
        return recorded

    invariants = row.get("numerical_invariants", {})
    max_displacement = invariants.get("max_front_displacement")
    if not isinstance(max_displacement, (int, float)) or max_displacement <= 0:
        return [{
            "type": "missing_front_motion_bound",
            "checkpoint": trajectory[0].get("checkpoint"),
            "message": "max_front_displacement is absent or non-positive",
        }]

    initial = row.get("reference", {}).get("initial_topology")
    states = []
    if isinstance(initial, dict):
        states.append({"checkpoint": 0, "elapsed": 0.0, "topology": initial})
    states.extend(trajectory)
    failures = []
    grid_delta = float(row.get("numerics", {}).get("grid_delta", 0.0) or 0.0)
    # Two cells cover the metric's discrete interface-location uncertainty.
    # Drops beyond that plus the physical front bound are not accepted.
    depth_tolerance = max(1e-10, 2.0 * grid_delta)

    for previous, current in zip(states, states[1:]):
        before = previous.get("topology", {})
        after = current.get("topology", {})
        if not before or not after:
            continue
        checkpoint_delta = max(
            1,
            int(current.get("checkpoint", 0))
            - int(previous.get("checkpoint", 0)),
        )
        motion_bound = float(max_displacement) * checkpoint_delta
        before_depth = float(before.get("open_void_depth", 0.0) or 0.0)
        after_depth = float(after.get("open_void_depth", 0.0) or 0.0)
        before_area = float(before.get("remaining_void_area", 0.0) or 0.0)
        after_area = float(after.get("remaining_void_area", 0.0) or 0.0)
        depth_drop = before_depth - after_depth
        area_drop = before_area - after_area
        closed_void_created = int(after.get("closed_void_count", 0) or 0) > int(
            before.get("closed_void_count", 0) or 0
        )
        detection_area = float(
            after.get(
                "void_area_detection_limit",
                before.get("void_area_detection_limit", grid_delta * grid_delta),
            )
            or 0.0
        )

        if (
            before.get("open_void")
            and not closed_void_created
            and depth_drop > motion_bound + depth_tolerance
        ):
            failures.append({
                "type": "open_void_depth_drop_exceeds_front_motion",
                "legacy_depth_only_fallback": True,
                "from_checkpoint": previous.get("checkpoint"),
                "checkpoint": current.get("checkpoint"),
                "from_elapsed": previous.get("elapsed"),
                "elapsed": current.get("elapsed"),
                "open_void_depth_before": before_depth,
                "open_void_depth_after": after_depth,
                "depth_drop": depth_drop,
                "maximum_allowed_depth_drop": motion_bound + depth_tolerance,
                "remaining_void_area_before": before_area,
                "remaining_void_area_after": after_area,
                "remaining_void_area_drop": area_drop,
                "closed_void_created": closed_void_created,
                "message": (
                    "legacy row lacks the width-aware transition fields"
                ),
            })

        if after_area - before_area > detection_area + 1e-12:
            failures.append({
                "type": "remaining_void_area_increased_during_deposition",
                "from_checkpoint": previous.get("checkpoint"),
                "checkpoint": current.get("checkpoint"),
                "remaining_void_area_before": before_area,
                "remaining_void_area_after": after_area,
                "increase": after_area - before_area,
                "allowed_detection_area": detection_area,
            })

        bounds = row.get("reference", {}).get("via_x_bounds", [])
        if len(bounds) == 2 and area_drop > 0:
            via_width = float(bounds[1]) - float(bounds[0])
            swept_area_bound = (
                2.0 * (max(via_width, 0.0) + before_depth) * motion_bound
                + math.pi * motion_bound * motion_bound
                + detection_area
            )
            if area_drop > swept_area_bound + 1e-12:
                failures.append({
                    "type": "remaining_void_area_drop_exceeds_swept_bound",
                    "from_checkpoint": previous.get("checkpoint"),
                    "checkpoint": current.get("checkpoint"),
                    "remaining_void_area_before": before_area,
                    "remaining_void_area_after": after_area,
                    "area_drop": area_drop,
                    "conservative_swept_area_bound": swept_area_bound,
                })
    return failures


def _trajectory_validation_errors(row):
    errors = []
    trajectory = row.get("trajectory")
    if not isinstance(trajectory, list) or not trajectory:
        return ["successful row has no trajectory checkpoints"]
    checkpoints = [checkpoint.get("checkpoint") for checkpoint in trajectory]
    elapsed = [checkpoint.get("elapsed") for checkpoint in trajectory]
    if any(not isinstance(value, int) for value in checkpoints):
        errors.append("checkpoint identifiers are not integers")
    elif any(b <= a for a, b in zip(checkpoints, checkpoints[1:])):
        errors.append("checkpoint identifiers are not strictly increasing")
    if any(not isinstance(value, (int, float)) for value in elapsed):
        errors.append("checkpoint elapsed values are not numeric")
    elif any(b <= a for a, b in zip(elapsed, elapsed[1:])):
        errors.append("checkpoint elapsed values are not strictly increasing")
    if row.get("last_checkpoint") != checkpoints[-1]:
        errors.append("last_checkpoint does not match the terminal trajectory row")

    persistent = _persistent_failures(row)
    row_keys = {
        "pinch_off": "pinch_off_seen",
        "invalid_topology": "invalid_topology_seen",
        "topology_transition": "topology_transition_failure_seen",
        "protected_stack": "protected_failure_seen",
        "model_diagnostic": "model_failure_seen",
    }
    for name, row_key in row_keys.items():
        if bool(row.get(row_key)) != persistent[name]["seen"]:
            errors.append(f"top-level {row_key} disagrees with trajectory")

    any_target = False
    threshold = float(row.get("target", {}).get("min_overburden", math.inf))
    for checkpoint in trajectory:
        topology = checkpoint.get("topology", {})
        if checkpoint.get("target_pass"):
            any_target = True
            failures = _checkpoint_failure(checkpoint)
            if not (
                topology.get("topology_valid")
                and topology.get("void_free")
                and topology.get("overburden_min", -math.inf) >= threshold
                and not any(failures.values())
            ):
                errors.append(
                    f"checkpoint {checkpoint.get('checkpoint')} target_pass "
                    "does not satisfy its recorded gates"
                )
    if bool(row.get("target_pass")) != any_target:
        errors.append("top-level target_pass disagrees with trajectory")
    if bool(row.get("screen_pass")) != any_target:
        errors.append("top-level screen_pass disagrees with trajectory")
    return errors


def _first_checkpoint(trajectory, predicate):
    checkpoint = next((item for item in trajectory if predicate(item)), None)
    if checkpoint is None:
        return None
    return {
        "checkpoint": checkpoint.get("checkpoint"),
        "elapsed": checkpoint.get("elapsed"),
    }


def _terminal_topology(checkpoint):
    if not checkpoint:
        return None
    topology = checkpoint.get("topology", {})
    if topology.get("topology_valid") is False:
        classification = "invalid_topology"
    elif topology.get("closed_void_count", 0):
        classification = "closed_void"
    elif topology.get("open_void"):
        classification = "open_void"
    elif topology.get("void_free"):
        classification = "void_free"
    else:
        classification = "unclassified"
    keys = (
        "topology_valid",
        "open_void",
        "closed_void_count",
        "void_free",
        "remaining_void_area",
        "fill_fraction",
        "mouth_aperture",
        "overburden_min",
        "overburden_mean",
        "overburden_nonuniformity",
    )
    return {
        "classification": classification,
        "checkpoint": checkpoint.get("checkpoint"),
        "elapsed": checkpoint.get("elapsed"),
        **{key: topology.get(key) for key in keys},
    }


def _censoring(row, persistent, transition_failures):
    trajectory = row.get("trajectory", [])
    if not trajectory:
        return ["no completed trajectory is available"]
    terminal = trajectory[-1]
    reasons = []
    if terminal.get("target_pass"):
        reasons.append(
            "stopped at first reported target crossing; later morphology is unobserved"
        )
    if any(item["seen"] for item in persistent.values()):
        reasons.append(
            "stopped at first persistent hard failure; later trajectory is unobserved"
        )
    if transition_failures:
        reasons.append(
            "topology after the first hard seam transition is rejected"
        )
    max_duration = float(row.get("numerics", {}).get("max_duration", math.inf))
    if (
        float(terminal.get("elapsed", 0.0)) >= max_duration - 1e-10
        and not terminal.get("target_pass")
        and not any(item["seen"] for item in persistent.values())
    ):
        reasons.append("right-censored at the configured maximum duration")
    return reasons


def _case_summary(expected, attempts, selected):
    error_attempts = [row for row in attempts if not row.get("ok")]
    if selected is None:
        return {
            "design": expected["design"],
            "rng_seed": expected["rng_seed"],
            "case_id": expected["case_id"],
            "status": "error_only" if error_attempts else "missing",
            "attempt_count": len(attempts),
            "error_attempt_count": len(error_attempts),
            "terminal_topology": None,
            "persistent_failures": None,
            "transition_plausibility_failures": [],
            "trajectory_validation_errors": [],
            "reported_screen_pass": False,
            "review_valid_screen_pass": False,
            "events": {},
            "censoring": ["no successful row is available"],
        }

    trajectory = selected.get("trajectory", [])
    validation_errors = _trajectory_validation_errors(selected)
    transitions = topology_transition_failures(selected)
    persistent = _persistent_failures(selected)
    target_threshold = float(selected["target"]["min_overburden"])
    first_target = _first_checkpoint(
        trajectory, lambda checkpoint: bool(checkpoint.get("target_pass"))
    )
    first_transition_checkpoint = min(
        (
            item.get("checkpoint", math.inf)
            for item in transitions
            if item.get("checkpoint") is not None
        ),
        default=None,
    )
    review_valid_screen_pass = bool(
        selected.get("screen_pass")
        and not validation_errors
        and not transitions
        and not any(item["seen"] for item in persistent.values())
    )
    status = "complete"
    if validation_errors:
        status = "invalid_output"
    elif transitions:
        status = "complete_transition_rejected"
    return {
        "design": expected["design"],
        "rng_seed": expected["rng_seed"],
        "case_id": expected["case_id"],
        "status": status,
        "attempt_count": len(attempts),
        "error_attempt_count": len(error_attempts),
        "trajectory_checkpoint_count": len(trajectory),
        "terminal_topology": _terminal_topology(
            trajectory[-1] if trajectory else None
        ),
        "persistent_failures": persistent,
        "transition_plausibility_failures": transitions,
        "first_transition_failure": transitions[0] if transitions else None,
        "trajectory_validation_errors": validation_errors,
        "reported_screen_pass": bool(selected.get("screen_pass")),
        "review_valid_screen_pass": review_valid_screen_pass,
        "events": {
            "first_void_free": _first_checkpoint(
                trajectory,
                lambda checkpoint: bool(
                    checkpoint.get("topology", {}).get("topology_valid")
                    and checkpoint.get("topology", {}).get("void_free")
                ),
            ),
            "first_overburden_crossing": _first_checkpoint(
                trajectory,
                lambda checkpoint: checkpoint.get("topology", {}).get(
                    "overburden_min", -math.inf
                ) >= target_threshold,
            ),
            "first_reported_target_pass": first_target,
            "first_review_valid_target_pass": (
                first_target if review_valid_screen_pass else None
            ),
            "first_hard_transition_checkpoint": first_transition_checkpoint,
            "first_implausible_transition_checkpoint": first_transition_checkpoint,
        },
        "censoring": _censoring(selected, persistent, transitions),
    }


def _best_valid_miss(case_pairs):
    candidates = []
    for case_summary, row in case_pairs:
        if row is None or case_summary["trajectory_validation_errors"]:
            continue
        rejected_from = case_summary["events"].get(
            "first_implausible_transition_checkpoint"
        )
        initial_area = float(
            row.get("reference", {}).get("initial_cavity_area", 0.0) or 0.0
        )
        threshold = float(row["target"]["min_overburden"])
        hard_failure_seen = False
        for checkpoint in row.get("trajectory", []):
            hard_failure_seen = hard_failure_seen or any(
                _checkpoint_failure(checkpoint).values()
            )
            if hard_failure_seen:
                continue
            if (
                rejected_from is not None
                and checkpoint.get("checkpoint", math.inf) >= rejected_from
            ):
                continue
            topology = checkpoint.get("topology", {})
            if (
                not topology.get("topology_valid")
                or checkpoint.get("protected_stack", {}).get("survives") is False
                or checkpoint.get("model_diagnostics", {}).get("valid") is False
                or checkpoint.get("target_pass")
            ):
                continue
            remaining = float(topology.get("remaining_void_area", math.inf))
            fill_fraction = topology.get("fill_fraction")
            if fill_fraction is None:
                fill_fraction = (
                    max(0.0, 1.0 - remaining / initial_area)
                    if initial_area > 0
                    else -math.inf
                )
            overburden = float(topology.get("overburden_min", -math.inf))
            gates_met = int(bool(topology.get("void_free"))) + int(
                overburden >= threshold
            )
            normalized_deficit = (
                max(0.0, threshold - overburden) / threshold
                if threshold > 0 and math.isfinite(overburden)
                else math.inf
            )
            rank = (
                gates_met,
                float(fill_fraction),
                -normalized_deficit,
                float(checkpoint.get("elapsed", 0.0)),
            )
            candidates.append((rank, case_summary, checkpoint, remaining))
    if not candidates:
        return None
    _, case_summary, checkpoint, remaining = max(candidates, key=lambda item: item[0])
    topology = checkpoint["topology"]
    threshold = float(
        next(
            row["target"]["min_overburden"]
            for summary, row in case_pairs
            if summary["case_id"] == case_summary["case_id"] and row is not None
        )
    )
    return {
        "selection_rule": (
            "among pre-failure, pre-seam, non-passing checkpoints: "
            "maximize target conditions met, then fill fraction, then minimize "
            "normalized overburden deficit"
        ),
        "design": case_summary["design"],
        "rng_seed": case_summary["rng_seed"],
        "case_id": case_summary["case_id"],
        "checkpoint": checkpoint.get("checkpoint"),
        "elapsed": checkpoint.get("elapsed"),
        "void_free": topology.get("void_free"),
        "remaining_void_area": remaining,
        "fill_fraction": topology.get("fill_fraction"),
        "mouth_aperture": topology.get("mouth_aperture"),
        "overburden_min": topology.get("overburden_min"),
        "overburden_deficit": max(
            0.0, threshold - float(topology.get("overburden_min", -math.inf))
        ),
    }


def _variable_design_factors(manifest):
    values = defaultdict(set)
    for design in manifest["designs"]:
        merged = {**manifest["model"], **design["model"]}
        for key, value in merged.items():
            if isinstance(value, (int, float)):
                values[key].add(float(value))
    return {
        key: sorted(observed)
        for key, observed in values.items()
        if len(observed) > 1
    }


def build_summary(manifest, rows, parse_errors, rows_missing, runtime_fingerprint):
    expected = expand_expected_cases(manifest, runtime_fingerprint)
    expected_keys = [_logical_key(case) for case in expected]
    expected_ids = [case["case_id"] for case in expected]
    manifest_errors = []
    if len(set(expected_keys)) != len(expected_keys):
        manifest_errors.append("manifest has duplicate design/seed cases")
    if len(set(expected_ids)) != len(expected_ids):
        manifest_errors.append("manifest expands to duplicate case IDs")
    if not runtime_fingerprint.get("viennaps_binary_sha256"):
        manifest_errors.append("manifest has no expected ViennaPS binary SHA-256")

    expected_by_key = {_logical_key(case): case for case in expected}
    attempts_by_key = defaultdict(list)
    unexpected_attempts = []
    superseded_attempts = []
    invalid_attempts = []
    error_attempts = []
    for row in rows:
        expected_case = expected_by_key.get(_logical_key(row))
        if expected_case is None:
            unexpected_attempts.append(row)
            continue
        attempts_by_key[_logical_key(row)].append(row)
        errors = _attempt_validation_errors(
            row, expected_case, runtime_fingerprint
        )
        if _is_superseded_fingerprint_attempt(
            row, expected_case, runtime_fingerprint
        ):
            superseded_attempts.append(row)
        elif errors:
            invalid_attempts.append({"reasons": errors, "row": row})
        if not row.get("ok"):
            error_attempts.append(row)

    case_summaries = []
    case_pairs = []
    duplicate_success_ids = []
    for expected_case in expected:
        attempts = attempts_by_key[_logical_key(expected_case)]
        eligible_successes = [
            row
            for row in attempts
            if row.get("ok")
            and not _attempt_validation_errors(
                row, expected_case, runtime_fingerprint
            )
        ]
        if len(eligible_successes) > 1:
            duplicate_success_ids.append(expected_case["case_id"])
        selected = eligible_successes[-1] if eligible_successes else None
        case_summary = _case_summary(expected_case, attempts, selected)
        case_summaries.append(case_summary)
        case_pairs.append((case_summary, selected))

    groups = []
    for design in [item["name"] for item in manifest["designs"]]:
        cases = [item for item in case_summaries if item["design"] == design]
        groups.append({
            "design": design,
            "expected_cases": len(cases),
            "completed_cases": sum(
                item["status"].startswith("complete") for item in cases
            ),
            "reported_screen_passes": sum(
                item["reported_screen_pass"] for item in cases
            ),
            "review_valid_screen_passes": sum(
                item["review_valid_screen_pass"] for item in cases
            ),
            "transition_rejected_reported_passes": sum(
                item["reported_screen_pass"]
                and bool(item["transition_plausibility_failures"])
                for item in cases
            ),
            "cases": cases,
        })

    output_invalid = bool(
        manifest_errors
        or parse_errors
        or unexpected_attempts
        or invalid_attempts
        or duplicate_success_ids
        or any(
            item["status"] in {"missing", "error_only", "invalid_output"}
            for item in case_summaries
        )
    )
    transitions = sum(
        len(item["transition_plausibility_failures"])
        for item in case_summaries
    )
    seam_transitions = sum(
        failure.get("type") == "unresolved_narrow_tail_merger"
        for item in case_summaries
        for failure in item["transition_plausibility_failures"]
    )
    if rows_missing:
        status = "missing_rows"
    elif output_invalid:
        status = "incomplete_or_invalid_output"
    elif transitions:
        status = (
            "complete_with_unresolved_seam_failures"
            if seam_transitions == transitions
            else "complete_with_rejected_topology_transitions"
        )
    elif error_attempts:
        status = "complete_with_recovered_attempts"
    else:
        status = "complete_coarse_screen"

    best_miss = _best_valid_miss(case_pairs)
    variable_factors = _variable_design_factors(manifest)
    warnings = [
        "This is a coarse one-seed mechanism screen, not recipe or model acceptance.",
        "Checkpoint and grid follow-up localized the failure as an unresolved narrow-tail seam; broader model qualification remains outstanding.",
    ]
    if transitions:
        warnings.append(
            "Width-aware review identifies unresolved narrow-tail seam mergers; later void-free metrics cannot overrule this hard gate."
        )
    hard_stopped = sum(
        bool(case["censoring"])
        and any("hard failure" in reason for reason in case["censoring"])
        for group in groups
        for case in group["cases"]
    )
    if hard_stopped:
        warnings.append(
            f"{hard_stopped} current trajectories stop at their first hard "
            "failure; later morphology is censored."
        )
    if any(item["reported_screen_pass"] for item in case_summaries):
        warnings.append(
            "Passing trajectories stop at their first target crossing, so later overburden and topology are censored."
        )
    superseded_passes = sum(
        bool(row.get("screen_pass")) for row in superseded_attempts
    )
    if superseded_attempts:
        warnings.append(
            f"{len(superseded_attempts)} older-fingerprint attempts are "
            f"preserved but superseded; {superseded_passes} reported passes "
            "from those attempts are not current evidence."
        )
    if best_miss:
        source = next(
            case
            for case in expected
            if case["case_id"] == best_miss["case_id"]
        )
        for factor, values in variable_factors.items():
            value = float(source["model"][factor])
            if value in {values[0], values[-1]}:
                side = "lower" if value == values[0] else "upper"
                warnings.append(
                    f"The best valid miss is on the {side} tested {factor} "
                    "boundary; it is not an optimum."
                )

    unique_fingerprints = []
    seen_fingerprints = set()
    for row in rows:
        encoded = json.dumps(
            row.get("runtime_fingerprint"), sort_keys=True, default=str
        )
        if encoded not in seen_fingerprints:
            seen_fingerprints.add(encoded)
            unique_fingerprints.append(row.get("runtime_fingerprint"))
    one_seed_per_design = all(
        len(design["rng_seeds"]) == 1 for design in manifest["designs"]
    )
    return {
        "status": status,
        "campaign": manifest.get("campaign"),
        "evidence_class": "coarse one-seed full-2D mechanism screen",
        "model_acceptance_eligible": False,
        "recipe_acceptance_eligible": False,
        "production_doe_eligible": False,
        "one_seed_per_design": one_seed_per_design,
        "expected_case_count": len(expected),
        "attempt_count": len(rows),
        "successful_attempt_count": sum(bool(row.get("ok")) for row in rows),
        "error_attempt_count": len(error_attempts),
        "superseded_fingerprint_attempt_count": len(superseded_attempts),
        "superseded_reported_screen_pass_count": superseded_passes,
        "selected_case_count": sum(pair[1] is not None for pair in case_pairs),
        "reported_screen_pass_count": sum(
            item["reported_screen_pass"] for item in case_summaries
        ),
        "review_valid_screen_pass_count": sum(
            item["review_valid_screen_pass"] for item in case_summaries
        ),
        "transition_plausibility_failure_count": transitions,
        "unresolved_seam_transition_count": seam_transitions,
        "expected_runtime_fingerprint": runtime_fingerprint,
        "observed_runtime_fingerprints": unique_fingerprints,
        "manifest_validation_errors": manifest_errors,
        "duplicate_success_case_ids": sorted(duplicate_success_ids),
        "parse_errors": parse_errors,
        "error_attempt_rows": error_attempts,
        "superseded_fingerprint_attempt_rows": superseded_attempts,
        "invalid_attempts": invalid_attempts,
        "unexpected_attempt_rows": unexpected_attempts,
        "designs": groups,
        "best_valid_miss": best_miss,
        "boundary_and_censoring_warnings": warnings,
        "decision": (
            "No model or recipe is accepted by this block. "
            "The unresolved seam is now followed by the identifiable "
            "lambda-by-sticking access/coverage surface, not another blind "
            "recipe search."
        ),
    }


def _fmt(value, digits=5):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return f"{value:.{digits}g}" if isinstance(value, (int, float)) else str(value)


def markdown(summary):
    lines = [
        "# Coarse Cu-fill trajectory review",
        "",
        f"Status: **{summary['status']}**. Expected cases: "
        f"{summary['expected_case_count']}; selected results: "
        f"{summary['selected_case_count']}; attempts: {summary['attempt_count']}; "
        f"error attempts retained: {summary['error_attempt_count']}.",
        "",
        "**Decision:** This one-seed pilot does not accept a fill model or "
        "process setting. Width-aware review treats unresolved narrow-tail "
        "mergers as hard seam failures.",
        "",
        f"Reported screen passes: **{summary['reported_screen_pass_count']}**. "
        f"Review-valid screen passes: **{summary['review_valid_screen_pass_count']}**. "
        f"Unresolved seam transitions: **{summary['unresolved_seam_transition_count']}**.",
        "",
        "| Design / seed | Status | Terminal topology | Remaining void | Fill fraction | Mouth | Seam tail h / w / aspect / bound | Persistent failures |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for design in summary["designs"]:
        for case in design["cases"]:
            terminal = case["terminal_topology"] or {}
            persistent = case.get("persistent_failures") or {}
            failures = [
                name
                for name, value in persistent.items()
                if value.get("seen")
            ]
            if (
                case["transition_plausibility_failures"]
                and "topology_transition" not in failures
            ):
                failures.append("implausible transition")
            transition = case.get("first_transition_failure") or {}
            lines.append(
                f"| {case['design']} / {case['rng_seed']} | {case['status']} | "
                f"{terminal.get('classification', '—')} | "
                f"{_fmt(terminal.get('remaining_void_area'))} | "
                f"{_fmt(terminal.get('fill_fraction'))} | "
                f"{_fmt(terminal.get('mouth_aperture'))} | "
                f"{_fmt(transition.get('tail_height'))} / "
                f"{_fmt(transition.get('tail_maximum_width'))} / "
                f"{_fmt(transition.get('tail_aspect_ratio'))} / "
                f"{_fmt(transition.get('closure_width_bound'))} | "
                f"{', '.join(failures) if failures else 'none'} |"
            )

    lines += ["", "## Best valid miss", ""]
    miss = summary["best_valid_miss"]
    if miss:
        lines += [
            f"Before any hard seam failure: **{miss['design']}**, "
            f"checkpoint {miss['checkpoint']} (t={_fmt(miss['elapsed'])}). "
            f"Fill fraction {_fmt(miss['fill_fraction'])}; remaining void "
            f"{_fmt(miss['remaining_void_area'])}; minimum overburden "
            f"{_fmt(miss['overburden_min'])}. This is a miss, not a recipe.",
            "",
            f"Selection rule: {miss['selection_rule']}.",
        ]
    else:
        lines.append("No structurally valid, pre-failure miss is available.")

    lines += ["", "## Validity and censoring", ""]
    for warning in summary["boundary_and_censoring_warnings"]:
        lines.append(f"- {warning}")
    if summary["error_attempt_rows"]:
        lines += [
            "",
            f"All {len(summary['error_attempt_rows'])} simulator error attempts "
            "remain in the machine-readable summary.",
        ]
    lines += [
        "",
        "Next: run the queued identifiable access/coverage surface over "
        "lambda × sticking. Keep the unresolved-seam gate, and use the result "
        "only to select the next model experiment.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    rows, parse_errors, rows_missing = load_jsonl(args.rows)
    runtime_fingerprint = expected_runtime_fingerprint(
        manifest, args.project_root
    )
    summary = build_summary(
        manifest, rows, parse_errors, rows_missing, runtime_fingerprint
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    args.markdown.write_text(markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "attempts": summary["attempt_count"],
        "selected": summary["selected_case_count"],
        "reported_passes": summary["reported_screen_pass_count"],
        "review_valid_passes": summary["review_valid_screen_pass_count"],
        "transition_failures": summary["transition_plausibility_failure_count"],
    }))


if __name__ == "__main__":
    main()

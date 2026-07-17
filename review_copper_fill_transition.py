"""Review replicated Cu-fill checkpoint and grid transition studies."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import traveler_metrics as tm


DEFAULT_CHECKPOINT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_copper_fill_transition_manifest.json"
)
DEFAULT_CHECKPOINT_ROWS = Path(
    "autoresearch-results/restart_audit/copper_fill_transition_rows.jsonl"
)
DEFAULT_FINE_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_copper_fill_transition_grid_fine_manifest.json"
)
DEFAULT_FINE_ROWS = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transition_grid_fine_rows.jsonl"
)
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/copper_fill_transition_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/copper_fill_transition_review.md"
)

SEEDS = (91000, 91001, 91002, 91003)
REGIMES = {
    0.0: "no_suppression",
    0.25: "suppression_transition",
}
CHECKPOINT_INTERVALS = (0.05, 0.025, 0.0125)
COARSE_GRID = 0.01
FINE_GRID = 0.005
SELECTED_INTERVAL = 0.0125

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


def runtime_fingerprint(manifest, project_root):
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


def expand_cases(manifest, fingerprint):
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
                "runtime_fingerprint": dict(fingerprint),
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


def _close(first, second, tolerance=1e-12):
    return math.isclose(float(first), float(second), rel_tol=0.0, abs_tol=tolerance)


def regime_for(case):
    adsorption = float(case["model"]["adsorption_strength"])
    return next(
        (name for value, name in REGIMES.items() if _close(adsorption, value)),
        f"unknown_adsorption_{adsorption:g}",
    )


def matrix_key(case):
    return (
        regime_for(case),
        float(case["numerics"]["grid_delta"]),
        float(case["numerics"]["checkpoint_interval"]),
        int(case["rng_seed"]),
    )


def required_matrix(study):
    if study == "checkpoint":
        return {
            (regime, COARSE_GRID, interval, seed)
            for regime in REGIMES.values()
            for interval in CHECKPOINT_INTERVALS
            for seed in SEEDS
        }
    if study == "fine_grid":
        return {
            (regime, FINE_GRID, SELECTED_INTERVAL, seed)
            for regime in REGIMES.values()
            for seed in SEEDS
        }
    raise ValueError(f"unknown study: {study}")


def validate_manifest_matrix(manifest, cases, study):
    errors = []
    expected_campaign = {
        "checkpoint": "foundation-copper-fill-topology-transition-step-study",
        "fine_grid": "foundation-copper-fill-topology-transition-grid-study",
    }[study]
    expected_version = {"checkpoint": 2, "fine_grid": 3}[study]
    if manifest.get("campaign") != expected_campaign:
        errors.append(f"unexpected campaign: {manifest.get('campaign')}")
    if manifest.get("manifest_version") != expected_version:
        errors.append(
            f"unexpected manifest_version: {manifest.get('manifest_version')}"
        )
    observed = [matrix_key(case) for case in cases]
    duplicates = sorted(
        key for key, count in Counter(observed).items() if count > 1
    )
    required = required_matrix(study)
    missing = sorted(required - set(observed))
    extra = sorted(set(observed) - required)
    if duplicates:
        errors.append(f"duplicate matrix cells: {duplicates}")
    if missing:
        errors.append(f"missing matrix cells: {missing}")
    if extra:
        errors.append(f"unexpected matrix cells: {extra}")
    if len({case["case_id"] for case in cases}) != len(cases):
        errors.append("duplicate expected case IDs")
    return errors


def _case_payload(row):
    return {key: row.get(key) for key in CASE_FIELDS}


def _logical_key(row):
    return row.get("design"), row.get("rng_seed")


def validate_attempt(row, expected, fingerprint):
    errors = []
    if row.get("case_id") != expected["case_id"]:
        errors.append("case_id differs from current manifest/fingerprint")
    if row.get("runtime_fingerprint") != fingerprint:
        errors.append("runtime fingerprint differs from current reviewed files")
    if row.get("case_id") != case_id(_case_payload(row)):
        errors.append("case_id differs from the row's own payload")
    for field in CASE_FIELDS:
        if row.get(field) != expected.get(field):
            errors.append(f"case field differs from manifest: {field}")
    if row.get("production_doe_eligible") is not False:
        errors.append("production_doe_eligible is not explicitly false")
    return errors


def _offline_reauditable_attempt(row, expected, fingerprint):
    """Accept old-runner geometry only for an explicit offline mesh reaudit."""
    observed = row.get("runtime_fingerprint")
    if not isinstance(observed, dict) or observed == fingerprint:
        return False
    if row.get("case_id") != case_id(_case_payload(row)):
        return False
    if row.get("production_doe_eligible") is not False:
        return False
    if not all(
        row.get(field) == expected.get(field)
        for field in CASE_FIELDS
        if field != "runtime_fingerprint"
    ):
        return False
    return all(
        observed.get(key) == fingerprint.get(key)
        for key in (
            "traveler_metrics_sha256",
            "tsv_process_sha256",
            "viennaps_binary_sha256",
        )
    )


def _is_number(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _hard_failures(row):
    trajectory = row.get("trajectory", [])
    definitions = {
        "topology_transition": (
            "topology_transition_failure_seen",
            lambda checkpoint: checkpoint.get(
                "topology_transition_failure_seen"
            )
            or checkpoint.get("topology_transition", {}).get("valid") is False,
        ),
        "invalid_topology": (
            "invalid_topology_seen",
            lambda checkpoint: checkpoint.get("invalid_topology_seen")
            or checkpoint.get("topology", {}).get("topology_valid") is False,
        ),
        "pinch_off": (
            "pinch_off_seen",
            lambda checkpoint: checkpoint.get("pinch_off_seen")
            or checkpoint.get("topology", {}).get("pinch_off_failure"),
        ),
        "protected_stack": (
            "protected_failure_seen",
            lambda checkpoint: checkpoint.get("protected_failure_seen")
            or checkpoint.get("protected_stack", {}).get("survives") is False,
        ),
        "model_diagnostic": (
            "model_failure_seen",
            lambda checkpoint: checkpoint.get("model_failure_seen")
            or checkpoint.get("model_diagnostics", {}).get("valid") is False,
        ),
    }
    result = {}
    for name, (row_key, predicate) in definitions.items():
        first = next((item for item in trajectory if predicate(item)), None)
        result[name] = {
            "seen": bool(row.get(row_key) or first is not None),
            "first_checkpoint": first.get("checkpoint") if first else None,
            "first_elapsed": first.get("elapsed") if first else None,
        }
    return result


def _recorded_or_offline_width_audit(
    row,
    trajectory,
    observation_index,
    transition,
    project_root,
):
    """Classify the disappearing tail using the saved pre-event mesh."""
    front = float(row["numerical_invariants"]["max_front_displacement"])
    grid = float(row["numerics"]["grid_delta"])
    closure_bound = 2.0 * front + grid
    recorded_width = transition.get("disappearing_tail_max_width")
    recorded_classification = transition.get("classification")
    if recorded_classification is not None:
        errors = []
        recorded_bound = transition.get("closure_width_bound", closure_bound)
        if not _is_number(recorded_bound) or not _close(
            recorded_bound, closure_bound, 1e-10
        ):
            errors.append("recorded closure-width bound is inconsistent")
        if recorded_classification == "unresolved_narrow_tail_merger":
            if not _is_number(recorded_width):
                errors.append("unresolved narrow tail has no measured width")
            elif float(recorded_width) > closure_bound + 1e-12:
                errors.append("narrow-tail width exceeds its closure bound")
            if not transition.get("unresolved_seam_risk"):
                errors.append("narrow-tail classification lacks seam-risk flag")
        return {
            "source": "recorded_current_runner",
            "classification": recorded_classification,
            "disappearing_tail_max_width": recorded_width,
            "closure_width_bound": (
                float(recorded_bound) if _is_number(recorded_bound) else None
            ),
            "unresolved_seam_risk": bool(
                transition.get("unresolved_seam_risk")
            ),
        }, errors

    if observation_index == 0:
        return None, ["first checkpoint cannot be width-reaudited without a pre-event mesh"]
    previous_snapshot = trajectory[observation_index - 1].get("snapshot_path")
    if not previous_snapshot:
        return None, ["pre-event snapshot path is missing"]
    snapshot_path = Path(previous_snapshot)
    if not snapshot_path.is_absolute():
        snapshot_path = Path(project_root) / snapshot_path
    if not snapshot_path.exists():
        return None, [f"pre-event snapshot is missing: {snapshot_path}"]

    try:
        with np.load(snapshot_path) as snapshot:
            nodes = np.asarray(snapshot["nodes"], dtype=float)
            lines = np.asarray(snapshot["lines"], dtype=int)
    except Exception as error:
        return None, [f"cannot read pre-event snapshot: {error!r}"]
    reference = row.get("reference", {})
    field_y = reference.get("field_y")
    bounds = reference.get("via_x_bounds")
    if not _is_number(field_y) or not isinstance(bounds, list) or len(bounds) != 2:
        return None, ["row reference lacks field_y or via_x_bounds"]

    previous_depth = float(transition["previous_open_void_depth"])
    current_depth = float(transition["current_open_void_depth"])
    observed_drop = float(transition["observed_open_void_depth_drop"])
    allowed_drop = float(transition["allowed_open_void_depth_drop"])
    lower_y = float(field_y) - previous_depth
    upper_y = float(field_y) - current_depth
    widths = []
    if upper_y > lower_y:
        sample_count = max(
            8, int(math.ceil((upper_y - lower_y) / (0.5 * grid)))
        )
        sample_edges = np.linspace(lower_y, upper_y, sample_count + 1)
        for sample_y in 0.5 * (sample_edges[:-1] + sample_edges[1:]):
            intersections = tm.line_intersections_at_y(
                nodes,
                lines,
                float(sample_y),
                x_bounds=(float(bounds[0]), float(bounds[1])),
            )
            left = intersections[intersections <= 0.0]
            right = intersections[intersections >= 0.0]
            if len(left) and len(right):
                widths.append(float(np.min(right) - np.max(left)))
    max_width = max(widths) if widths else None
    closed_created = bool(transition.get("closed_void_created"))
    depth_resolved = observed_drop <= allowed_drop + 1e-12
    narrow_tail = bool(
        not depth_resolved
        and not closed_created
        and max_width is not None
        and max_width <= closure_bound + 1e-12
    )
    if depth_resolved:
        classification = "resolved_front_motion"
    elif closed_created:
        classification = "resolved_closed_void_creation"
    elif narrow_tail:
        classification = "unresolved_narrow_tail_merger"
    else:
        classification = "nonconservative_or_unmeasurable_cavity_loss"
    return {
        "source": "offline_saved_pre_event_mesh",
        "classification": classification,
        "disappearing_tail_max_width": max_width,
        "closure_width_bound": closure_bound,
        "unresolved_seam_risk": narrow_tail,
        "sampled_tail_section_count": len(widths),
        "snapshot_path": str(snapshot_path),
    }, []


def diagnose_row(row, project_root=Path.cwd()):
    """Return the first transition failure, or the worst observed transition."""
    errors = []
    trajectory = row.get("trajectory")
    if not isinstance(trajectory, list) or not trajectory:
        return None, ["successful row has no trajectory"]
    checkpoints = [item.get("checkpoint") for item in trajectory]
    elapsed = [item.get("elapsed") for item in trajectory]
    if any(not isinstance(value, int) for value in checkpoints) or any(
        later <= earlier for earlier, later in zip(checkpoints, checkpoints[1:])
    ):
        errors.append("checkpoint identifiers are not strictly increasing integers")
    if any(not _is_number(value) for value in elapsed) or any(
        later <= earlier for earlier, later in zip(elapsed, elapsed[1:])
    ):
        errors.append("elapsed values are not strictly increasing finite numbers")
    if row.get("last_checkpoint") != checkpoints[-1]:
        errors.append("last_checkpoint differs from terminal checkpoint")

    grid = float(row["numerics"]["grid_delta"])
    front = row.get("numerical_invariants", {}).get(
        "max_front_displacement"
    )
    if not _is_number(front) or float(front) <= 0:
        errors.append("max_front_displacement is missing or non-positive")
        expected_bound = None
    else:
        expected_front = (
            float(row["model"]["active_deposition_rate"])
            * float(row["numerics"]["checkpoint_interval"])
        )
        if not _close(front, expected_front, 1e-10):
            errors.append("max_front_displacement disagrees with rate × interval")
        expected_bound = float(front) + 2.0 * grid

    observations = []
    initial_topology = row.get("reference", {}).get("initial_topology", {})
    width_audit_errors = []
    for observation_index, checkpoint in enumerate(trajectory):
        transition = checkpoint.get("topology_transition")
        topology = checkpoint.get("topology")
        if not isinstance(transition, dict) or not isinstance(topology, dict):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} lacks topology metrics"
            )
            continue
        required_transition = (
            "previous_open_void_depth",
            "current_open_void_depth",
            "observed_open_void_depth_drop",
            "allowed_open_void_depth_drop",
        )
        required_topology = (
            "mouth_aperture",
            "remaining_void_area",
        )
        missing = [
            key
            for key in required_transition
            if not _is_number(transition.get(key))
        ] + [
            key for key in required_topology if not _is_number(topology.get(key))
        ]
        if missing or not isinstance(transition.get("valid"), bool) or not isinstance(
            topology.get("topology_valid"), bool
        ):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} has invalid metrics: "
                f"{missing or ['boolean validity flag']}"
            )
            continue
        prior = float(transition["previous_open_void_depth"])
        current = float(transition["current_open_void_depth"])
        jump = float(transition["observed_open_void_depth_drop"])
        allowed = float(transition["allowed_open_void_depth_drop"])
        if not _close(jump, max(0.0, prior - current), 1e-9):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} depth jump is inconsistent"
            )
        if expected_bound is not None and not _close(allowed, expected_bound, 1e-10):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} allowed bound is inconsistent"
            )
        if allowed <= 0:
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} allowed bound is non-positive"
            )
            continue
        closed_created = bool(transition.get("closed_void_created"))
        should_be_valid = bool(jump <= allowed + 1e-12 or closed_created)
        if bool(transition["valid"]) != should_be_valid:
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} transition validity is inconsistent"
            )
        observations.append({
            "checkpoint": checkpoint["checkpoint"],
            "elapsed": float(checkpoint["elapsed"]),
            "transition_valid": bool(transition["valid"]),
            "physical_failure": not bool(transition["valid"]),
            "prior_open_void_depth": prior,
            "current_open_void_depth": current,
            "observed_depth_jump": jump,
            "allowed_bound": allowed,
            "jump_bound_ratio": jump / allowed,
            "mouth_aperture": float(topology["mouth_aperture"]),
            "remaining_void_area": float(topology["remaining_void_area"]),
            "topology_valid": bool(topology["topology_valid"]),
        })
        if not bool(transition["valid"]):
            width_audit, audit_errors = _recorded_or_offline_width_audit(
                row,
                trajectory,
                observation_index,
                transition,
                project_root,
            )
            width_audit_errors.extend(audit_errors)
            observations[-1]["width_audit"] = width_audit
        else:
            observations[-1]["width_audit"] = {
                "source": "depth_within_bound",
                "classification": "resolved_front_motion",
                "disappearing_tail_max_width": None,
                "closure_width_bound": (
                    2.0 * float(front) + grid if _is_number(front) else None
                ),
                "unresolved_seam_risk": False,
            }
        previous_topology = (
            initial_topology
            if observation_index == 0
            else trajectory[observation_index - 1].get("topology", {})
        )
        prior_area = previous_topology.get("remaining_void_area")
        prior_mouth = previous_topology.get("mouth_aperture")
        if _is_number(prior_area):
            observations[-1]["prior_remaining_void_area"] = float(prior_area)
            observations[-1]["observed_area_drop"] = float(prior_area) - float(
                topology["remaining_void_area"]
            )
        else:
            observations[-1]["prior_remaining_void_area"] = None
            observations[-1]["observed_area_drop"] = None
        if _is_number(prior_mouth):
            observations[-1]["prior_mouth_aperture"] = float(prior_mouth)
            observations[-1]["observed_mouth_change"] = float(
                topology["mouth_aperture"]
            ) - float(prior_mouth)
        else:
            observations[-1]["prior_mouth_aperture"] = None
            observations[-1]["observed_mouth_change"] = None

    if not observations:
        return None, errors or ["trajectory has no usable transition observations"]
    first_failure = next(
        (item for item in observations if item["physical_failure"]), None
    )
    diagnostic = first_failure or max(
        observations, key=lambda item: item["jump_bound_ratio"]
    )
    hard = _hard_failures(row)
    transition_seen = first_failure is not None
    if bool(row.get("topology_transition_failure_seen")) != transition_seen:
        errors.append(
            "top-level topology_transition_failure_seen disagrees with trajectory"
        )
    if bool(row.get("target_pass")) or bool(row.get("screen_pass")):
        # Keep the row, but the transition study never treats this as acceptance.
        diagnostic["reported_screen_pass"] = True
    else:
        diagnostic["reported_screen_pass"] = False
    diagnostic.update({
        "case_id": row.get("case_id"),
        "design": row.get("design"),
        "regime": regime_for(row),
        "rng_seed": int(row["rng_seed"]),
        "grid_delta": grid,
        "checkpoint_interval": float(
            row["numerics"]["checkpoint_interval"]
        ),
        "physical_failure_time": (
            first_failure["elapsed"] if first_failure else None
        ),
        "failure_censored_at": (
            float(trajectory[-1]["elapsed"]) if first_failure is None else None
        ),
        "hard_failures": hard,
    })
    width_audit = diagnostic.pop("width_audit", None)
    errors.extend(width_audit_errors)
    if width_audit is None:
        if not width_audit_errors:
            errors.append("transition width audit is unavailable")
    else:
        diagnostic.update({
            "width_audit_source": width_audit["source"],
            "transition_classification": width_audit["classification"],
            "disappearing_tail_max_width": width_audit[
                "disappearing_tail_max_width"
            ],
            "closure_width_bound": width_audit["closure_width_bound"],
            "tail_width_bound_ratio": (
                width_audit["disappearing_tail_max_width"]
                / width_audit["closure_width_bound"]
                if width_audit["disappearing_tail_max_width"] is not None
                and width_audit["closure_width_bound"]
                else None
            ),
            "unresolved_seam_risk": width_audit["unresolved_seam_risk"],
            "width_audit_details": width_audit,
        })
    return diagnostic, errors


def stats(values):
    values = [float(value) for value in values if value is not None]
    if not values:
        return {key: None for key in ("n", "mean", "sd", "min", "max", "range")}
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "sd": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
    }


def _study_attempts(
    study,
    manifest,
    rows,
    parse_errors,
    rows_missing,
    fingerprint,
    project_root,
):
    cases = expand_cases(manifest, fingerprint)
    manifest_errors = validate_manifest_matrix(manifest, cases, study)
    expected_by_key = {_logical_key(case): case for case in cases}
    attempts_by_key = defaultdict(list)
    error_rows = []
    invalid_attempts = []
    superseded_runner_attempts = []
    unexpected_rows = []
    for row in rows:
        expected = expected_by_key.get(_logical_key(row))
        if expected is None:
            unexpected_rows.append(row)
            continue
        attempts_by_key[_logical_key(row)].append(row)
        validation = validate_attempt(row, expected, fingerprint)
        if _offline_reauditable_attempt(row, expected, fingerprint):
            superseded_runner_attempts.append(row)
        elif validation:
            invalid_attempts.append({"reasons": validation, "row": row})
        if not row.get("ok"):
            error_rows.append(row)

    selected = []
    missing_cases = []
    duplicate_success_ids = []
    invalid_metric_rows = []
    diagnostics = []
    for expected in cases:
        attempts = attempts_by_key[_logical_key(expected)]
        current_successes = [
            row
            for row in attempts
            if row.get("ok") and not validate_attempt(row, expected, fingerprint)
        ]
        offline_successes = [
            row
            for row in attempts
            if row.get("ok")
            and _offline_reauditable_attempt(row, expected, fingerprint)
        ]
        if len(current_successes) > 1:
            duplicate_success_ids.append(expected["case_id"])
        if not current_successes and len(offline_successes) > 1:
            duplicate_success_ids.append(expected["case_id"])
        if not current_successes and not offline_successes:
            missing_cases.append({
                "case_id": expected["case_id"],
                "design": expected["design"],
                "rng_seed": expected["rng_seed"],
                "attempt_count": len(attempts),
            })
            continue
        row = (current_successes or offline_successes)[-1]
        selected.append(row)
        diagnostic, metric_errors = diagnose_row(row, project_root)
        if metric_errors:
            invalid_metric_rows.append({
                "reasons": metric_errors,
                "row": row,
            })
        if diagnostic is not None and not metric_errors:
            diagnostics.append(diagnostic)

    invalid = bool(
        manifest_errors
        or parse_errors
        or invalid_attempts
        or invalid_metric_rows
        or unexpected_rows
        or duplicate_success_ids
    )
    complete = bool(
        not rows_missing
        and not invalid
        and len(selected) == len(cases)
        and len(diagnostics) == len(cases)
    )
    observed_fingerprints = []
    seen_fingerprints = set()
    for row in rows:
        encoded = json.dumps(
            row.get("runtime_fingerprint"), sort_keys=True, default=str
        )
        if encoded not in seen_fingerprints:
            seen_fingerprints.add(encoded)
            observed_fingerprints.append(row.get("runtime_fingerprint"))
    return {
        "study": study,
        "status": (
            (
                "complete_with_offline_width_reaudit"
                if superseded_runner_attempts and complete
                else "complete"
            )
            if complete
            else "missing_rows"
            if rows_missing
            else "incomplete_or_invalid"
        ),
        "complete": complete,
        "expected_case_count": len(cases),
        "attempt_count": len(rows),
        "selected_case_count": len(selected),
        "metric_valid_case_count": len(diagnostics),
        "runtime_fingerprint": fingerprint,
        "observed_runtime_fingerprints": observed_fingerprints,
        "current_fingerprint_selected_case_count": sum(
            row.get("runtime_fingerprint") == fingerprint for row in selected
        ),
        "offline_reaudited_case_count": sum(
            row.get("runtime_fingerprint") != fingerprint for row in selected
        ),
        "manifest_validation_errors": manifest_errors,
        "parse_errors": parse_errors,
        "error_attempt_rows": error_rows,
        "invalid_attempts": invalid_attempts,
        "superseded_runner_fingerprint_attempt_rows": superseded_runner_attempts,
        "invalid_metric_rows": invalid_metric_rows,
        "unexpected_attempt_rows": unexpected_rows,
        "duplicate_success_case_ids": sorted(duplicate_success_ids),
        "missing_cases": missing_cases,
        "diagnostics": diagnostics,
    }


def aggregate_groups(diagnostics):
    grouped = defaultdict(list)
    for item in diagnostics:
        grouped[
            (
                item["regime"],
                item["checkpoint_interval"],
                item["grid_delta"],
            )
        ].append(item)
    result = []
    metric_names = (
        "physical_failure_time",
        "observed_depth_jump",
        "allowed_bound",
        "jump_bound_ratio",
        "prior_open_void_depth",
        "current_open_void_depth",
        "mouth_aperture",
        "remaining_void_area",
        "prior_remaining_void_area",
        "observed_area_drop",
        "prior_mouth_aperture",
        "observed_mouth_change",
        "disappearing_tail_max_width",
        "closure_width_bound",
        "tail_width_bound_ratio",
    )
    for (regime, interval, grid), rows in sorted(grouped.items()):
        hard_counts = {
            name: sum(item["hard_failures"][name]["seen"] for item in rows)
            for name in (
                "topology_transition",
                "invalid_topology",
                "pinch_off",
                "protected_stack",
                "model_diagnostic",
            )
        }
        result.append({
            "regime": regime,
            "checkpoint_interval": interval,
            "grid_delta": grid,
            "n": len(rows),
            "seed_labels": sorted(item["rng_seed"] for item in rows),
            "physical_failure_count": sum(
                item["physical_failure"] for item in rows
            ),
            "censored_without_transition_failure_count": sum(
                not item["physical_failure"] for item in rows
            ),
            "topology_valid_count_at_diagnostic": sum(
                item["topology_valid"] for item in rows
            ),
            "reported_screen_pass_count": sum(
                item["reported_screen_pass"] for item in rows
            ),
            "transition_classification_counts": dict(sorted(Counter(
                item["transition_classification"] for item in rows
            ).items())),
            "unresolved_seam_risk_count": sum(
                item["unresolved_seam_risk"] for item in rows
            ),
            "width_audit_source_counts": dict(sorted(Counter(
                item["width_audit_source"] for item in rows
            ).items())),
            "hard_failure_counts": hard_counts,
            "metrics": {
                name: stats(item.get(name) for item in rows)
                for name in metric_names
            },
            "seed_spread": {
                name: stats(item.get(name) for item in rows)["range"]
                for name in metric_names
            },
        })
    return result


def _group_index(groups):
    return {
        (
            group["regime"],
            group["grid_delta"],
            group["checkpoint_interval"],
        ): group
        for group in groups
    }


def grid_comparisons(groups):
    indexed = _group_index(groups)
    comparisons = []
    for regime in REGIMES.values():
        coarse = indexed.get((regime, COARSE_GRID, SELECTED_INTERVAL))
        fine = indexed.get((regime, FINE_GRID, SELECTED_INTERVAL))
        complete = bool(coarse and fine and coarse["n"] == 4 and fine["n"] == 4)
        comparison = {
            "regime": regime,
            "status": "complete" if complete else "incomplete",
            "coarse": coarse,
            "fine": fine,
            "shared_seed_label_count": (
                len(set(coarse["seed_labels"]) & set(fine["seed_labels"]))
                if coarse and fine
                else 0
            ),
            "comparison_policy": (
                "compare replicated distributions; identical seed labels do "
                "not imply pathwise equality after remeshing"
            ),
        }
        for metric in (
            "physical_failure_time",
            "observed_depth_jump",
            "jump_bound_ratio",
            "mouth_aperture",
            "remaining_void_area",
        ):
            coarse_mean = (
                coarse["metrics"][metric]["mean"] if coarse else None
            )
            fine_mean = fine["metrics"][metric]["mean"] if fine else None
            comparison[f"fine_minus_coarse_mean_{metric}"] = (
                fine_mean - coarse_mean
                if coarse_mean is not None and fine_mean is not None
                else None
            )
            comparison[f"fine_to_coarse_mean_{metric}_ratio"] = (
                fine_mean / coarse_mean
                if coarse_mean not in (None, 0.0) and fine_mean is not None
                else None
            )
        comparisons.append(comparison)
    return comparisons


def classify_decision(checkpoint_study, fine_study, groups):
    if not checkpoint_study["complete"] or not fine_study["complete"]:
        return {
            "classification": "incomplete",
            "provisional_depth_guard_classification": "incomplete",
            "guard_validation_status": "incomplete",
            "per_regime": {
                regime: "incomplete" for regime in REGIMES.values()
            },
            "reason": (
                "Both exact matrices must be complete and metric-valid before "
                "checkpoint, grid, or structural attribution."
            ),
        }
    indexed = _group_index(groups)
    per_regime = {}
    reasons = {}
    provisional_per_regime = {}
    for regime in REGIMES.values():
        coarse = indexed[(regime, COARSE_GRID, SELECTED_INTERVAL)]
        fine = indexed[(regime, FINE_GRID, SELECTED_INTERVAL)]
        coarse_failures = coarse["physical_failure_count"]
        fine_failures = fine["physical_failure_count"]
        provisional_per_regime[regime] = (
            "structural_morphology_limitation"
            if coarse_failures == 4 and fine_failures == 4
            else "grid_resolved"
            if coarse_failures == 4 and fine_failures == 0
            else "checkpoint_resolved"
            if coarse_failures == 0 and fine_failures == 0
            else "incomplete"
        )
        if coarse_failures == 0 and fine_failures == 0:
            classification = "checkpoint_resolved"
            reason = (
                "the selected smaller checkpoint has no transition failures "
                "at either grid"
            )
        elif coarse_failures == 4 and fine_failures == 0:
            classification = "grid_resolved"
            reason = (
                "all coarse-grid failures disappear at the finer grid"
            )
        elif coarse_failures == 4 and fine_failures == 4:
            coarse_seams = coarse["unresolved_seam_risk_count"]
            fine_seams = fine["unresolved_seam_risk_count"]
            if coarse_seams == 4 and fine_seams == 4:
                classification = "unresolved_seam_limitation"
                reason = (
                    "Saved pre-event meshes show a narrow pointed tail within "
                    "the opposing-front closure-width bound in all eight "
                    "selected-grid cases; seam-free closure is not resolved"
                )
            elif coarse_seams == 0 and fine_seams == 0:
                classification = "structural_morphology_limitation"
                reason = (
                    "all four seeds retain a width-audited, nonconservative "
                    "morphology loss at both grids"
                )
            else:
                classification = "incomplete"
                reason = (
                    "mixed width-audit classifications do not support one "
                    "robust morphology attribution"
                )
        else:
            classification = "incomplete"
            reason = (
                "mixed seed outcomes do not support a robust resolution claim"
            )
        per_regime[regime] = classification
        reasons[regime] = reason

    unique = set(per_regime.values())
    overall = next(iter(unique)) if len(unique) == 1 else "incomplete"
    provisional_unique = set(provisional_per_regime.values())
    provisional_overall = (
        next(iter(provisional_unique))
        if len(provisional_unique) == 1
        else "incomplete"
    )
    reason = (
        reasons[next(iter(REGIMES.values()))]
        if len(unique) == 1
        else "Regime-level decisions disagree; no single robust attribution is available."
    )
    return {
        "classification": overall,
        "provisional_depth_guard_classification": provisional_overall,
        "provisional_depth_guard_per_regime": provisional_per_regime,
        "guard_validation_status": "width_audited_from_saved_pre_event_meshes",
        "per_regime": per_regime,
        "per_regime_reason": reasons,
        "reason": reason,
    }


def build_summary(
    checkpoint_manifest,
    checkpoint_rows,
    checkpoint_parse_errors,
    checkpoint_missing,
    fine_manifest,
    fine_rows,
    fine_parse_errors,
    fine_missing,
    checkpoint_fingerprint,
    fine_fingerprint,
    project_root=Path.cwd(),
):
    checkpoint_study = _study_attempts(
        "checkpoint",
        checkpoint_manifest,
        checkpoint_rows,
        checkpoint_parse_errors,
        checkpoint_missing,
        checkpoint_fingerprint,
        project_root,
    )
    fine_study = _study_attempts(
        "fine_grid",
        fine_manifest,
        fine_rows,
        fine_parse_errors,
        fine_missing,
        fine_fingerprint,
        project_root,
    )
    diagnostics = checkpoint_study.pop("diagnostics") + fine_study.pop(
        "diagnostics"
    )
    groups = aggregate_groups(diagnostics)
    comparisons = grid_comparisons(groups)
    decision = classify_decision(checkpoint_study, fine_study, groups)
    offline_reaudited = (
        checkpoint_study["offline_reaudited_case_count"]
        + fine_study["offline_reaudited_case_count"]
    )
    return {
        "status": (
            (
                "complete_with_offline_width_reaudit"
                if offline_reaudited
                else "complete"
            )
            if checkpoint_study["complete"] and fine_study["complete"]
            else "incomplete_or_invalid"
        ),
        "decision": decision,
        "model_acceptance_eligible": False,
        "recipe_acceptance_eligible": False,
        "production_doe_eligible": False,
        "checkpoint_study": checkpoint_study,
        "fine_grid_study": fine_study,
        "groups": groups,
        "grid_comparisons": comparisons,
        "hard_gate": (
            "An unresolved narrow-tail merger is a hard seam-risk failure; "
            "later void-free metrics cannot overrule it."
        ),
        "physical_failure_time_interpretation": (
            "physical_failure_time is the first width-audited unresolved seam "
            "event, not proof of impossible material motion"
        ),
        "offline_reaudited_case_count": offline_reaudited,
    }


def _fmt(value, digits=5):
    if value is None:
        return "—"
    return f"{value:.{digits}g}" if isinstance(value, (int, float)) else str(value)


def _mean_range(metric):
    if metric["mean"] is None:
        return "—"
    return f"{_fmt(metric['mean'])} [{_fmt(metric['min'])}, {_fmt(metric['max'])}]"


def markdown(summary):
    checkpoint = summary["checkpoint_study"]
    fine = summary["fine_grid_study"]
    decision = summary["decision"]
    lines = [
        "# Cu-fill topology-transition resolution review",
        "",
        f"Status: **{summary['status']}**. Decision: "
        f"**{decision['classification']}**.",
        "",
        decision["reason"],
        "",
        f"Transition guard: **{decision['guard_validation_status']}**. "
        f"Withdrawn depth-only classification: "
        f"**{decision['provisional_depth_guard_classification']}**.",
        "",
        "The saved rows predate the width-aware runner fingerprint. They are "
        "not relabeled as current simulations: the exact pre-event meshes are "
        "reanalyzed offline, while the metric, process, and ViennaPS binary "
        "fingerprints must still match.",
        "",
        "This study diagnoses whether apparent cavity closure is numerically "
        "resolved. It does not accept a fill model or recipe.",
        "",
        "| Input block | Cases | Selected | Current fingerprint | Offline mesh reaudit | Metric-valid | Errors | Missing |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| Checkpoint increments | {checkpoint['expected_case_count']} | "
        f"{checkpoint['selected_case_count']} | "
        f"{checkpoint['current_fingerprint_selected_case_count']} | "
        f"{checkpoint['offline_reaudited_case_count']} | "
        f"{checkpoint['metric_valid_case_count']} | "
        f"{len(checkpoint['error_attempt_rows']) + len(checkpoint['invalid_attempts']) + len(checkpoint['invalid_metric_rows'])} | "
        f"{len(checkpoint['missing_cases'])} |",
        f"| Fine grid | {fine['expected_case_count']} | "
        f"{fine['selected_case_count']} | "
        f"{fine['current_fingerprint_selected_case_count']} | "
        f"{fine['offline_reaudited_case_count']} | "
        f"{fine['metric_valid_case_count']} | "
        f"{len(fine['error_attempt_rows']) + len(fine['invalid_attempts']) + len(fine['invalid_metric_rows'])} | "
        f"{len(fine['missing_cases'])} |",
        "",
        "## Replicated transition measurements",
        "",
        "Values are mean [minimum, maximum] across seed labels.",
        "The listed failure time is the first width-audited unresolved seam "
        "event, not evidence of impossible area motion.",
        "",
        "| Regime | Grid | Checkpoint | n | Seam risks | Failure time | Depth jump | Tail width | Width bound | Width/bound | Mouth | Void area | Area drop | Topology valid |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group in summary["groups"]:
        metrics = group["metrics"]
        lines.append(
            f"| {group['regime']} | {_fmt(group['grid_delta'])} | "
            f"{_fmt(group['checkpoint_interval'])} | {group['n']} | "
            f"{group['physical_failure_count']} | "
            f"{_mean_range(metrics['physical_failure_time'])} | "
            f"{_mean_range(metrics['observed_depth_jump'])} | "
            f"{_mean_range(metrics['disappearing_tail_max_width'])} | "
            f"{_mean_range(metrics['closure_width_bound'])} | "
            f"{_mean_range(metrics['tail_width_bound_ratio'])} | "
            f"{_mean_range(metrics['mouth_aperture'])} | "
            f"{_mean_range(metrics['remaining_void_area'])} | "
            f"{_mean_range(metrics['observed_area_drop'])} | "
            f"{group['topology_valid_count_at_diagnostic']}/{group['n']} |"
        )

    lines += ["", "## Grid comparison at checkpoint 0.0125", ""]
    lines += [
        "| Regime | Status | Coarse seam risks | Fine seam risks | Δ mean failure time | Fine/coarse depth jump | Fine/coarse depth jump/bound |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for comparison in summary["grid_comparisons"]:
        coarse = comparison["coarse"] or {}
        fine_group = comparison["fine"] or {}
        lines.append(
            f"| {comparison['regime']} | {comparison['status']} | "
            f"{coarse.get('physical_failure_count', '—')} | "
            f"{fine_group.get('physical_failure_count', '—')} | "
            f"{_fmt(comparison['fine_minus_coarse_mean_physical_failure_time'])} | "
            f"{_fmt(comparison['fine_to_coarse_mean_observed_depth_jump_ratio'])} | "
            f"{_fmt(comparison['fine_to_coarse_mean_jump_bound_ratio_ratio'])} |"
        )

    lines += ["", "## Hard-failure interpretation", ""]
    for regime, classification in decision["per_regime"].items():
        reason = decision.get("per_regime_reason", {}).get(
            regime, "required matrix is incomplete"
        )
        lines.append(f"- **{regime}: {classification}.** {reason}")
    lines += [
        "",
        f"Hard gate: {summary['hard_gate']}",
        "",
    ]
    if decision["classification"] == "incomplete":
        if summary["status"] == "complete":
            lines.append(
                "Both matrices are complete. No structural conclusion is "
                "accepted until the pointed-tail width/area transition is "
                "checked against a mesh-derived conservation bound."
            )
        else:
            lines.append(
                "No checkpoint, grid, or structural conclusion is accepted "
                "until both exact matrices and all metrics pass audit."
            )
    elif decision["classification"] == "structural_morphology_limitation":
        lines.append(
            "Stop tuning this morphology path. Test an explicit multi-region "
            "or field-based representation before any production fill DOE."
        )
    elif decision["classification"] == "unresolved_seam_limitation":
        lines.append(
            "The depth-only interpretation is withdrawn. The hard failure is "
            "an unresolved seam: opposing fronts remove a narrow pointed tail, "
            "so these meshes cannot certify continuous void-free Cu. Use a "
            "multi-region or field-based fill representation before a recipe DOE."
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint-manifest", type=Path, default=DEFAULT_CHECKPOINT_MANIFEST
    )
    parser.add_argument(
        "--checkpoint-rows", type=Path, default=DEFAULT_CHECKPOINT_ROWS
    )
    parser.add_argument("--fine-manifest", type=Path, default=DEFAULT_FINE_MANIFEST)
    parser.add_argument("--fine-rows", type=Path, default=DEFAULT_FINE_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()

    checkpoint_manifest = json.loads(args.checkpoint_manifest.read_text())
    fine_manifest = json.loads(args.fine_manifest.read_text())
    checkpoint_rows, checkpoint_parse, checkpoint_missing = load_jsonl(
        args.checkpoint_rows
    )
    fine_rows, fine_parse, fine_missing = load_jsonl(args.fine_rows)
    summary = build_summary(
        checkpoint_manifest,
        checkpoint_rows,
        checkpoint_parse,
        checkpoint_missing,
        fine_manifest,
        fine_rows,
        fine_parse,
        fine_missing,
        runtime_fingerprint(checkpoint_manifest, args.project_root),
        runtime_fingerprint(fine_manifest, args.project_root),
        args.project_root,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    args.markdown.write_text(markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "decision": summary["decision"]["classification"],
        "checkpoint_cases": summary["checkpoint_study"]["selected_case_count"],
        "fine_cases": summary["fine_grid_study"]["selected_case_count"],
    }))


if __name__ == "__main__":
    main()

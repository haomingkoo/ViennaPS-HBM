"""Review the Cu-fill suppressor-access mechanism surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_copper_fill_access_surface_manifest.json"
)
DEFAULT_ROWS = Path(
    "autoresearch-results/restart_audit/copper_fill_access_surface_rows.jsonl"
)
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/copper_fill_access_surface_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/copper_fill_access_surface_review.md"
)

LAMBDA_LEVELS = (0.2, 0.5, 1.0, 2.0)
STICKING_LEVELS = (0.05, 0.2, 0.5, 0.8)
SEEDS = (93000, 93001)
DESIGN_PATTERN = re.compile(
    r"^lambda_(?P<lambda>\d+p\d+)_stick_(?P<sticking>\d+p\d+)$"
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


def case_id(case):
    payload = json.dumps(case, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


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


def _canonical(value, levels):
    return next(
        (level for level in levels if _close(value, level)),
        float(value),
    )


def recompute_lambda(model):
    deactivation = float(model["deactivation_rate"])
    if deactivation <= 0:
        raise ValueError("deactivation_rate must be positive")
    return (
        float(model["adsorption_strength"])
        * float(model["suppressor_sticking_probability"])
        / deactivation
    )


def parse_design_name(name):
    match = DESIGN_PATTERN.fullmatch(name)
    if match is None:
        raise ValueError(f"invalid design name: {name}")
    return (
        float(match.group("lambda").replace("p", ".")),
        float(match.group("sticking").replace("p", ".")),
    )


def _token(value):
    text = f"{value:.2f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text.replace(".", "p")


def expected_design_name(coverage_lambda, sticking):
    return f"lambda_{_token(coverage_lambda)}_stick_{_token(sticking)}"


def validate_manifest(manifest, cases):
    errors = []
    if manifest.get("manifest_version") != 4:
        errors.append(f"unexpected manifest_version: {manifest.get('manifest_version')}")
    if manifest.get("campaign") != "foundation-copper-fill-access-coverage-surface":
        errors.append(f"unexpected campaign: {manifest.get('campaign')}")
    expected = {
        (coverage_lambda, sticking, seed)
        for coverage_lambda in LAMBDA_LEVELS
        for sticking in STICKING_LEVELS
        for seed in SEEDS
    }
    observed = []
    for case in cases:
        try:
            named_lambda, named_sticking = parse_design_name(case["design"])
            actual_lambda = recompute_lambda(case["model"])
            actual_sticking = float(
                case["model"]["suppressor_sticking_probability"]
            )
            if not _close(named_lambda, actual_lambda):
                errors.append(
                    f"{case['design']} names lambda={named_lambda:g} but "
                    f"parameters give {actual_lambda:g}"
                )
            if not _close(named_sticking, actual_sticking):
                errors.append(
                    f"{case['design']} names sticking={named_sticking:g} but "
                    f"parameters give {actual_sticking:g}"
                )
            observed.append((
                _canonical(actual_lambda, LAMBDA_LEVELS),
                _canonical(actual_sticking, STICKING_LEVELS),
                int(case["rng_seed"]),
            ))
        except Exception as error:
            errors.append(str(error))
    counts = Counter(observed)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    missing = sorted(expected - set(observed))
    extra = sorted(set(observed) - expected)
    if duplicates:
        errors.append(f"duplicate design/seed cells: {duplicates}")
    if missing:
        errors.append(f"missing design/seed cells: {missing}")
    if extra:
        errors.append(f"unexpected design/seed cells: {extra}")
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
        errors.append("case_id differs from manifest/current fingerprint")
    if row.get("runtime_fingerprint") != fingerprint:
        errors.append("runtime fingerprint differs from current reviewed files")
    if row.get("case_id") != case_id(_case_payload(row)):
        errors.append("case_id differs from the row's own case payload")
    for field in CASE_FIELDS:
        if row.get(field) != expected.get(field):
            errors.append(f"case field differs from manifest: {field}")
    if row.get("production_doe_eligible") is not False:
        errors.append("production_doe_eligible is not explicitly false")
    return errors


def _is_superseded_fingerprint_attempt(row, expected, fingerprint):
    """Recognize a self-consistent attempt from an older runner fingerprint."""
    if row.get("runtime_fingerprint") == fingerprint:
        return False
    if row.get("case_id") != case_id(_case_payload(row)):
        return False
    if row.get("production_doe_eligible") is not False:
        return False
    return all(
        row.get(field) == expected.get(field)
        for field in CASE_FIELDS
        if field != "runtime_fingerprint"
    )


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _contrast(diagnostics):
    required = (
        "field_coverage_mean",
        "center_coverage_mean",
        "field_velocity_mean",
        "center_velocity_mean",
    )
    if any(not _number(diagnostics.get(key)) for key in required):
        return None
    field_coverage = float(diagnostics["field_coverage_mean"])
    center_coverage = float(diagnostics["center_coverage_mean"])
    field_velocity = float(diagnostics["field_velocity_mean"])
    center_velocity = float(diagnostics["center_velocity_mean"])
    return {
        "field_coverage_mean": field_coverage,
        "center_coverage_mean": center_coverage,
        "coverage_field_minus_center": field_coverage - center_coverage,
        "field_velocity_mean": field_velocity,
        "center_velocity_mean": center_velocity,
        "velocity_center_minus_field": center_velocity - field_velocity,
        "velocity_center_to_field_ratio": (
            center_velocity / field_velocity if field_velocity != 0 else None
        ),
    }


def _checkpoint_failures(checkpoint):
    topology = checkpoint.get("topology", {})
    transition = checkpoint.get("topology_transition", {})
    failures = []
    if checkpoint.get("topology_transition_failure_seen") or transition.get(
        "valid"
    ) is False:
        failures.append(
            transition.get("classification", "topology_transition_failure")
        )
    if checkpoint.get("invalid_topology_seen") or topology.get(
        "topology_valid"
    ) is False:
        failures.append("invalid_topology")
    if checkpoint.get("pinch_off_seen") or topology.get("pinch_off_failure"):
        failures.append("pinch_off_or_closed_void")
    if checkpoint.get("protected_failure_seen") or checkpoint.get(
        "protected_stack", {}
    ).get("survives") is False:
        failures.append("protected_stack_changed")
    if checkpoint.get("model_failure_seen") or checkpoint.get(
        "model_diagnostics", {}
    ).get("valid") is False:
        failures.append("invalid_model_diagnostic")
    return sorted(set(failures))


def diagnose_row(row):
    errors = []
    trajectory = row.get("trajectory")
    if not isinstance(trajectory, list) or not trajectory:
        return None, ["successful row has no trajectory"]
    checkpoints = [item.get("checkpoint") for item in trajectory]
    elapsed = [item.get("elapsed") for item in trajectory]
    if any(not isinstance(value, int) for value in checkpoints) or any(
        later <= earlier for earlier, later in zip(checkpoints, checkpoints[1:])
    ):
        errors.append("checkpoint IDs are not strictly increasing integers")
    if any(not _number(value) for value in elapsed) or any(
        later <= earlier for earlier, later in zip(elapsed, elapsed[1:])
    ):
        errors.append("elapsed times are not strictly increasing finite values")
    if row.get("last_checkpoint") != checkpoints[-1]:
        errors.append("last_checkpoint differs from terminal checkpoint")

    required_topology = (
        "fill_fraction",
        "remaining_void_area",
        "mouth_aperture",
        "overburden_min",
    )
    hard_event = None
    valid_progress = []
    contrasts = []
    for checkpoint in trajectory:
        topology = checkpoint.get("topology", {})
        transition = checkpoint.get("topology_transition", {})
        diagnostics = checkpoint.get("model_diagnostics", {})
        missing = [
            key for key in required_topology if not _number(topology.get(key))
        ]
        if missing or not isinstance(topology.get("topology_valid"), bool):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} has invalid "
                f"topology metrics: {missing or ['topology_valid']}"
            )
        if not isinstance(transition, dict) or not isinstance(
            transition.get("valid"), bool
        ):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} lacks transition validity"
            )
        contrast = _contrast(diagnostics)
        if contrast is None or not isinstance(diagnostics.get("valid"), bool):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} has invalid "
                "coverage/velocity diagnostics"
            )
        else:
            contrasts.append((checkpoint, contrast))

        failures = _checkpoint_failures(checkpoint)
        if failures and hard_event is None:
            hard_event = (checkpoint, failures)
        if hard_event is None and not missing and contrast is not None and topology.get(
            "topology_valid"
        ):
            valid_progress.append(checkpoint)

    if not contrasts:
        return None, errors or ["no valid coverage/velocity diagnostics"]

    terminal = trajectory[-1]
    target_event = next(
        (item for item in trajectory if item.get("target_pass")), None
    )
    max_duration = float(row["numerics"]["max_duration"])
    if hard_event:
        event_status = "hard_failure"
        event_checkpoint, hard_types = hard_event
        event_time = float(event_checkpoint["elapsed"])
        censor_time = None
    elif target_event:
        event_status = "reported_target_event"
        event_checkpoint = target_event
        hard_types = []
        event_time = float(target_event["elapsed"])
        censor_time = None
    elif float(terminal["elapsed"]) >= max_duration - 1e-10:
        event_status = "censored_at_max_duration"
        event_checkpoint = terminal
        hard_types = []
        event_time = None
        censor_time = float(terminal["elapsed"])
    else:
        event_status = "invalid_early_termination"
        event_checkpoint = terminal
        hard_types = []
        event_time = None
        censor_time = float(terminal["elapsed"])
        errors.append("trajectory ended before an event or max-duration censor")

    top_flags = {
        "invalid_topology_seen": "invalid_topology",
        "pinch_off_seen": "pinch_off_or_closed_void",
        "protected_failure_seen": "protected_stack_changed",
        "model_failure_seen": "invalid_model_diagnostic",
    }
    all_failure_types = sorted({
        failure
        for checkpoint in trajectory
        for failure in _checkpoint_failures(checkpoint)
    })
    for row_key, failure in top_flags.items():
        if bool(row.get(row_key)) != (failure in all_failure_types):
            errors.append(f"top-level {row_key} disagrees with trajectory")
    transition_seen = any(
        failure
        not in {
            "invalid_topology",
            "pinch_off_or_closed_void",
            "protected_stack_changed",
            "invalid_model_diagnostic",
        }
        for failure in all_failure_types
    )
    if bool(row.get("topology_transition_failure_seen")) != transition_seen:
        errors.append(
            "top-level topology_transition_failure_seen disagrees with trajectory"
        )
    if bool(row.get("target_pass")) != bool(target_event):
        errors.append("top-level target_pass disagrees with trajectory")
    if bool(row.get("screen_pass")) != bool(target_event):
        errors.append("top-level screen_pass disagrees with trajectory")

    best_progress = None
    if valid_progress:
        best = max(
            valid_progress,
            key=lambda checkpoint: (
                float(checkpoint["topology"]["fill_fraction"]),
                -float(checkpoint["topology"]["remaining_void_area"]),
                float(checkpoint["topology"]["mouth_aperture"]),
            ),
        )
        topology = best["topology"]
        best_progress = {
            "checkpoint": best["checkpoint"],
            "elapsed": float(best["elapsed"]),
            "fill_fraction": float(topology["fill_fraction"]),
            "remaining_void_area": float(topology["remaining_void_area"]),
            "mouth_aperture": float(topology["mouth_aperture"]),
            "overburden_min": float(topology["overburden_min"]),
        }

    transition = event_checkpoint.get("topology_transition", {})
    transition_failure = bool(
        event_status == "hard_failure"
        and transition.get("valid") is False
    )
    tail = {
        "classification": transition.get("classification"),
        "height": (
            transition.get("disappearing_tail_height")
            if transition_failure
            else None
        ),
        "maximum_width": (
            transition.get("disappearing_tail_max_width")
            if transition_failure
            else None
        ),
        "aspect_ratio": (
            transition.get("disappearing_tail_aspect_ratio")
            if transition_failure
            else None
        ),
        "closure_width_bound": (
            transition.get("closure_width_bound")
            if transition_failure
            else None
        ),
        "unresolved_seam_risk": bool(
            transition_failure and transition.get("unresolved_seam_risk")
        ),
    }
    if tail["classification"] == "unresolved_narrow_tail_merger":
        for key in ("height", "maximum_width", "aspect_ratio", "closure_width_bound"):
            if not _number(tail[key]):
                errors.append(f"unresolved seam has invalid tail metric: {key}")

    coverage_lambda = _canonical(
        recompute_lambda(row["model"]), LAMBDA_LEVELS
    )
    sticking = _canonical(
        float(row["model"]["suppressor_sticking_probability"]),
        STICKING_LEVELS,
    )
    return {
        "case_id": row.get("case_id"),
        "design": row.get("design"),
        "rng_seed": int(row["rng_seed"]),
        "coverage_lambda": coverage_lambda,
        "sticking_probability": sticking,
        "event_status": event_status,
        "event_checkpoint": event_checkpoint.get("checkpoint"),
        "event_time": event_time,
        "censor_time": censor_time,
        "hard_failure_types": hard_types,
        "all_hard_failure_types": all_failure_types,
        "accepted_pass": False,
        "reported_target_event": target_event is not None,
        "best_pre_failure_progress": best_progress,
        "tail": tail,
        "initial_contrast": contrasts[0][1],
        "terminal_contrast": contrasts[-1][1],
    }, errors


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


def _nested(diagnostic, *keys):
    value = diagnostic
    for key in keys:
        if value is None:
            return None
        value = value.get(key)
    return value


METRIC_PATHS = {
    "event_time": ("event_time",),
    "censor_time": ("censor_time",),
    "best_fill_fraction": ("best_pre_failure_progress", "fill_fraction"),
    "best_remaining_void_area": (
        "best_pre_failure_progress",
        "remaining_void_area",
    ),
    "best_mouth_aperture": ("best_pre_failure_progress", "mouth_aperture"),
    "best_overburden_min": ("best_pre_failure_progress", "overburden_min"),
    "tail_height": ("tail", "height"),
    "tail_maximum_width": ("tail", "maximum_width"),
    "tail_aspect_ratio": ("tail", "aspect_ratio"),
    "initial_coverage_contrast": (
        "initial_contrast",
        "coverage_field_minus_center",
    ),
    "terminal_coverage_contrast": (
        "terminal_contrast",
        "coverage_field_minus_center",
    ),
    "initial_velocity_contrast": (
        "initial_contrast",
        "velocity_center_minus_field",
    ),
    "terminal_velocity_contrast": (
        "terminal_contrast",
        "velocity_center_minus_field",
    ),
    "initial_velocity_ratio": (
        "initial_contrast",
        "velocity_center_to_field_ratio",
    ),
    "terminal_velocity_ratio": (
        "terminal_contrast",
        "velocity_center_to_field_ratio",
    ),
}


def aggregate(label, value, rows, expected_n):
    hard_types = Counter(
        failure for row in rows for failure in row["all_hard_failure_types"]
    )
    events = Counter(row["event_status"] for row in rows)
    metrics = {
        name: stats(_nested(row, *path) for row in rows)
        for name, path in METRIC_PATHS.items()
    }
    return {
        "factor": label,
        "value": value,
        "expected_n": expected_n,
        "n": len(rows),
        "complete": len(rows) == expected_n,
        "seed_labels": sorted({row["rng_seed"] for row in rows}),
        "hard_failure_case_count": sum(bool(row["hard_failure_types"]) for row in rows),
        "hard_failure_type_counts": dict(sorted(hard_types.items())),
        "event_status_counts": dict(sorted(events.items())),
        "censored_case_count": events["censored_at_max_duration"],
        "reported_target_event_count": events["reported_target_event"],
        "accepted_pass_count": 0,
        "metrics": metrics,
        "seed_spread": {
            name: metric["range"] for name, metric in metrics.items()
        },
    }


def point_summaries(diagnostics):
    grouped = defaultdict(list)
    for row in diagnostics:
        grouped[(row["coverage_lambda"], row["sticking_probability"])].append(row)
    points = []
    for coverage_lambda in LAMBDA_LEVELS:
        for sticking in STICKING_LEVELS:
            rows = grouped[(coverage_lambda, sticking)]
            summary = aggregate(
                "point",
                {
                    "coverage_lambda": coverage_lambda,
                    "sticking_probability": sticking,
                },
                rows,
                2,
            )
            summary.update({
                "coverage_lambda": coverage_lambda,
                "sticking_probability": sticking,
                "design": expected_design_name(coverage_lambda, sticking),
            })
            points.append(summary)
    return points


def main_surfaces(diagnostics, factor):
    grouped = defaultdict(list)
    key = "coverage_lambda" if factor == "lambda" else "sticking_probability"
    for row in diagnostics:
        grouped[row[key]].append(row)
    levels = LAMBDA_LEVELS if factor == "lambda" else STICKING_LEVELS
    return [aggregate(factor, value, grouped[value], 8) for value in levels]


def rank_points(points):
    eligible = [point for point in points if point["complete"]]

    def metric(point, name, stat_name, fallback):
        value = point["metrics"][name][stat_name]
        return fallback if value is None else value

    def rank_key(point):
        return (
            -point["hard_failure_case_count"],
            point["reported_target_event_count"],
            metric(point, "best_fill_fraction", "min", -math.inf),
            -metric(point, "best_remaining_void_area", "max", math.inf),
            -metric(point, "tail_height", "max", 0.0),
            metric(point, "best_mouth_aperture", "min", -math.inf),
            -point["coverage_lambda"],
            -point["sticking_probability"],
        )

    ranked = sorted(eligible, key=rank_key, reverse=True)
    return [
        {
            "rank": index,
            "design": point["design"],
            "coverage_lambda": point["coverage_lambda"],
            "sticking_probability": point["sticking_probability"],
            "next_model_experiment_only": True,
            "accepted_pass": False,
            "rank_basis": {
                "hard_failure_case_count": point["hard_failure_case_count"],
                "reported_target_event_count": point["reported_target_event_count"],
                "worst_seed_best_fill_fraction": point["metrics"]["best_fill_fraction"]["min"],
                "worst_seed_remaining_void_area": point["metrics"]["best_remaining_void_area"]["max"],
                "worst_seed_tail_height": point["metrics"]["tail_height"]["max"],
                "worst_seed_mouth_aperture": point["metrics"]["best_mouth_aperture"]["min"],
                "censored_case_count": point["censored_case_count"],
            },
        }
        for index, point in enumerate(ranked, 1)
    ]


def build_summary(manifest, rows, parse_errors, rows_missing, fingerprint):
    cases = expand_cases(manifest, fingerprint)
    manifest_errors = validate_manifest(manifest, cases)
    expected_by_key = {_logical_key(case): case for case in cases}
    attempts_by_key = defaultdict(list)
    error_rows = []
    current_fingerprint_error_rows = []
    superseded_attempts = []
    superseded_error_rows = []
    invalid_attempts = []
    unexpected_rows = []
    for row in rows:
        expected = expected_by_key.get(_logical_key(row))
        if expected is None:
            unexpected_rows.append(row)
            continue
        attempts_by_key[_logical_key(row)].append(row)
        attempt_errors = validate_attempt(row, expected, fingerprint)
        superseded = _is_superseded_fingerprint_attempt(
            row, expected, fingerprint
        )
        if superseded:
            superseded_attempts.append(row)
        elif attempt_errors:
            invalid_attempts.append({"reasons": attempt_errors, "row": row})
        if not row.get("ok"):
            error_rows.append(row)
            if superseded:
                superseded_error_rows.append(row)
            else:
                current_fingerprint_error_rows.append(row)

    diagnostics = []
    invalid_metric_rows = []
    missing_cases = []
    duplicate_success_ids = []
    selected = []
    for expected in cases:
        attempts = attempts_by_key[_logical_key(expected)]
        successes = [
            row
            for row in attempts
            if row.get("ok") and not validate_attempt(row, expected, fingerprint)
        ]
        if len(successes) > 1:
            duplicate_success_ids.append(expected["case_id"])
        if not successes:
            missing_cases.append({
                "case_id": expected["case_id"],
                "design": expected["design"],
                "rng_seed": expected["rng_seed"],
                "attempt_count": len(attempts),
            })
            continue
        row = successes[-1]
        selected.append(row)
        diagnostic, metric_errors = diagnose_row(row)
        if metric_errors:
            invalid_metric_rows.append({"reasons": metric_errors, "row": row})
        elif diagnostic is not None:
            diagnostics.append(diagnostic)

    invalid = bool(
        manifest_errors
        or parse_errors
        or invalid_attempts
        or invalid_metric_rows
        or unexpected_rows
        or duplicate_success_ids
        or current_fingerprint_error_rows
    )
    complete = bool(
        not rows_missing
        and not invalid
        and len(selected) == 32
        and len(diagnostics) == 32
    )
    points = point_summaries(diagnostics)
    ranking = rank_points(points) if complete else []
    warnings = [
        "This surface selects the next model experiment; it does not select a process setting.",
        "A max-duration censor is unresolved evidence, never a pass.",
        "Two seeds per point are screen-level evidence; promoted points require independent replication and numerical confirmation.",
        "Any promoted lambda or sticking boundary must be expanded before interpreting a best region.",
    ]
    if ranking:
        top = ranking[0]
        boundary = []
        if top["coverage_lambda"] in {min(LAMBDA_LEVELS), max(LAMBDA_LEVELS)}:
            boundary.append("lambda")
        if top["sticking_probability"] in {
            min(STICKING_LEVELS),
            max(STICKING_LEVELS),
        }:
            boundary.append("sticking")
        if boundary:
            warnings.append(
                "The first-ranked next experiment is on the tested "
                f"{' and '.join(boundary)} boundary; expand that boundary before interpreting a best region."
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
        "status": (
            "complete"
            if complete
            else "missing_rows"
            if rows_missing
            else "incomplete_or_invalid"
        ),
        "campaign": manifest.get("campaign"),
        "expected_case_count": 32,
        "attempt_count": len(rows),
        "selected_case_count": len(selected),
        "metric_valid_case_count": len(diagnostics),
        "model_acceptance_eligible": False,
        "recipe_acceptance_eligible": False,
        "production_doe_eligible": False,
        "accepted_pass_count": 0,
        "expected_runtime_fingerprint": fingerprint,
        "observed_runtime_fingerprints": observed_fingerprints,
        "manifest_validation_errors": manifest_errors,
        "parse_errors": parse_errors,
        "error_attempt_rows": error_rows,
        "current_fingerprint_error_attempt_rows": current_fingerprint_error_rows,
        "superseded_fingerprint_attempt_rows": superseded_attempts,
        "superseded_fingerprint_error_attempt_rows": superseded_error_rows,
        "superseded_fingerprint_attempt_count": len(superseded_attempts),
        "superseded_fingerprint_error_attempt_count": len(
            superseded_error_rows
        ),
        "invalid_attempts": invalid_attempts,
        "invalid_metric_rows": invalid_metric_rows,
        "unexpected_attempt_rows": unexpected_rows,
        "duplicate_success_case_ids": sorted(duplicate_success_ids),
        "missing_cases": missing_cases,
        "points": points,
        "lambda_main_surface": main_surfaces(diagnostics, "lambda"),
        "sticking_main_surface": main_surfaces(diagnostics, "sticking"),
        "next_model_experiment_ranking": ranking,
        "ranking_policy": (
            "lexicographic only: complete valid evidence; fewer hard failures; "
            "reported resolved target events; worst-seed bottom-up fill progress; "
            "worst-seed remaining void; seam-height reduction; mouth margin"
        ),
        "boundary_warnings": warnings,
        "decision": (
            "Use the ordering only to choose follow-up model experiments. "
            "Do not infer a recipe, optimum, calibrated mechanism, or scalar-loss winner."
        ),
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
    lines = [
        "# Cu-fill access/coverage surface review",
        "",
        f"Status: **{summary['status']}**. Cases selected: "
        f"{summary['selected_case_count']}/{summary['expected_case_count']}; "
        f"metric-valid: {summary['metric_valid_case_count']}; error attempts "
        f"retained: {len(summary['error_attempt_rows'])} "
        f"(current fingerprint: "
        f"{len(summary['current_fingerprint_error_attempt_rows'])}; "
        f"superseded: "
        f"{summary['superseded_fingerprint_error_attempt_count']}).",
        "",
        f"Superseded attempts retained for audit: "
        f"{summary['superseded_fingerprint_attempt_count']}. They do not "
        "replace or invalidate the clean current matrix.",
        "",
        "This is a model-behavior screen. It ranks follow-up model experiments, "
        "not process settings. Censored trajectories are not passes.",
        "",
    ]
    if summary["status"] != "complete":
        lines += [
            "The exact 16-point × 2-seed matrix is incomplete or invalid. "
            "No ordering is accepted yet.",
            "",
        ]
    lines += [
        "## Surface points",
        "",
        "Values are mean [minimum, maximum] across the two seed labels.",
        "",
        "| λ | Sticking | n | Hard failures | Event / censor time | Best fill | Remaining void | Mouth | Tail height | Tail width | Tail aspect | Coverage contrast initial→terminal | Velocity contrast initial→terminal |",
        "|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for point in summary["points"]:
        metrics = point["metrics"]
        failure_text = (
            ", ".join(
                f"{name}:{count}"
                for name, count in point["hard_failure_type_counts"].items()
            )
            or "none"
        )
        time_metric = (
            metrics["event_time"]
            if metrics["event_time"]["n"]
            else metrics["censor_time"]
        )
        lines.append(
            f"| {_fmt(point['coverage_lambda'])} | "
            f"{_fmt(point['sticking_probability'])} | {point['n']} | "
            f"{failure_text} | {_mean_range(time_metric)} | "
            f"{_mean_range(metrics['best_fill_fraction'])} | "
            f"{_mean_range(metrics['best_remaining_void_area'])} | "
            f"{_mean_range(metrics['best_mouth_aperture'])} | "
            f"{_mean_range(metrics['tail_height'])} | "
            f"{_mean_range(metrics['tail_maximum_width'])} | "
            f"{_mean_range(metrics['tail_aspect_ratio'])} | "
            f"{_fmt(metrics['initial_coverage_contrast']['mean'])}→"
            f"{_fmt(metrics['terminal_coverage_contrast']['mean'])} | "
            f"{_fmt(metrics['initial_velocity_contrast']['mean'])}→"
            f"{_fmt(metrics['terminal_velocity_contrast']['mean'])} |"
        )

    lines += ["", "## Main surfaces", ""]
    lines += [
        "| Factor | Value | n | Hard-failure cases | Censored | Best fill | Tail height | Mouth | Terminal coverage contrast | Terminal velocity contrast |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for surface in (
        summary["lambda_main_surface"] + summary["sticking_main_surface"]
    ):
        metrics = surface["metrics"]
        lines.append(
            f"| {surface['factor']} | {_fmt(surface['value'])} | "
            f"{surface['n']} | {surface['hard_failure_case_count']} | "
            f"{surface['censored_case_count']} | "
            f"{_mean_range(metrics['best_fill_fraction'])} | "
            f"{_mean_range(metrics['tail_height'])} | "
            f"{_mean_range(metrics['best_mouth_aperture'])} | "
            f"{_mean_range(metrics['terminal_coverage_contrast'])} | "
            f"{_mean_range(metrics['terminal_velocity_contrast'])} |"
        )

    lines += ["", "## Next model experiments", ""]
    if summary["status"] == "complete":
        lines += [
            "Ordering is lexicographic—validity and hard gates first, then "
            "replicated bottom-up progress, seam reduction, and mouth margin.",
            "",
            "| Rank | λ | Sticking | Hard failures | Worst-seed fill | Worst-seed void | Worst seam height | Worst mouth | Censored |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for item in summary["next_model_experiment_ranking"][:8]:
            basis = item["rank_basis"]
            lines.append(
                f"| {item['rank']} | {_fmt(item['coverage_lambda'])} | "
                f"{_fmt(item['sticking_probability'])} | "
                f"{basis['hard_failure_case_count']} | "
                f"{_fmt(basis['worst_seed_best_fill_fraction'])} | "
                f"{_fmt(basis['worst_seed_remaining_void_area'])} | "
                f"{_fmt(basis['worst_seed_tail_height'])} | "
                f"{_fmt(basis['worst_seed_mouth_aperture'])} | "
                f"{basis['censored_case_count']} |"
            )
    else:
        lines.append("No ranking is accepted from partial or invalid rows.")

    lines += ["", "## Limits", ""]
    for warning in summary["boundary_warnings"]:
        lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


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
    summary = build_summary(
        manifest,
        rows,
        parse_errors,
        rows_missing,
        runtime_fingerprint(manifest, args.project_root),
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    args.markdown.write_text(markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "attempts": summary["attempt_count"],
        "selected": summary["selected_case_count"],
        "metric_valid": summary["metric_valid_case_count"],
    }))


if __name__ == "__main__":
    main()

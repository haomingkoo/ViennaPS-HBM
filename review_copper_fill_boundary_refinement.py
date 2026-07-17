"""Review the replicated low-sticking Cu-fill boundary refinement."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import review_copper_fill_access_surface as access


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_copper_fill_boundary_refinement_v2_manifest.json"
)
DEFAULT_ROWS = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_boundary_refinement_v2_rows.jsonl"
)
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_boundary_refinement_v2_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_boundary_refinement_v2_review.md"
)

LAMBDA_LEVELS = (0.5, 0.625, 0.75, 0.875, 1.0, 1.25)
STICKING_LEVELS = (0.025, 0.05, 0.1)
SEEDS = (94000, 95000, 96000, 97000)


def _close(first, second, tolerance=1e-12):
    return math.isclose(float(first), float(second), rel_tol=0.0, abs_tol=tolerance)


def _canonical(value, levels):
    return next((level for level in levels if _close(value, level)), float(value))


def _token(value):
    text = f"{value:.3f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text.replace(".", "p")


def expected_design_name(coverage_lambda, sticking):
    return f"lambda_{_token(coverage_lambda)}_stick_{_token(sticking)}"


def validate_manifest(manifest, cases):
    errors = []
    if manifest.get("manifest_version") != 6:
        errors.append(f"unexpected manifest_version: {manifest.get('manifest_version')}")
    if manifest.get("campaign") != (
        "foundation-copper-fill-low-sticking-boundary-refinement-v2"
    ):
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
            named_lambda, named_sticking = access.parse_design_name(
                case["design"]
            )
            actual_lambda = access.recompute_lambda(case["model"])
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
    numerics = manifest.get("numerics", {})
    checkpoint_count = int(math.ceil(
        float(numerics.get("max_duration", 0.0))
        / float(numerics.get("checkpoint_interval", 1.0))
    ))
    if not numerics.get("require_disjoint_replicate_rng_streams"):
        errors.append("disjoint replicate RNG streams are not required")
    for index, first in enumerate(SEEDS):
        for second in SEEDS[index + 1:]:
            if abs(second - first) <= checkpoint_count:
                errors.append(
                    "replicate RNG base seeds overlap across checkpoint streams"
                )
    return errors


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _hard_failures(checkpoint):
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
    if int(topology.get("degenerate_closed_component_count", 0) or 0) > 0:
        failures.append("degenerate_closed_fragment")
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


def _velocity(diagnostics):
    center = diagnostics.get("center_velocity_mean")
    field = diagnostics.get("field_velocity_mean")
    if center is None and field is None:
        return None, []
    if not _number(center) or not _number(field):
        return None, ["center/field velocity is partially missing or non-finite"]
    center = float(center)
    field = float(field)
    return {
        "center_velocity": center,
        "field_velocity": field,
        "center_minus_field_velocity": center - field,
        "center_to_field_velocity_ratio": center / field if field != 0 else None,
    }, []


def diagnose_row(row):
    errors = []
    trajectory = row.get("trajectory")
    if not isinstance(trajectory, list) or not trajectory:
        return None, ["successful row has no trajectory"]
    checkpoint_ids = [item.get("checkpoint") for item in trajectory]
    elapsed = [item.get("elapsed") for item in trajectory]
    if any(not isinstance(value, int) for value in checkpoint_ids) or any(
        later <= earlier
        for earlier, later in zip(checkpoint_ids, checkpoint_ids[1:])
    ):
        errors.append("checkpoint IDs are not strictly increasing integers")
    if any(not _number(value) for value in elapsed) or any(
        later <= earlier for earlier, later in zip(elapsed, elapsed[1:])
    ):
        errors.append("elapsed times are not strictly increasing finite values")
    if row.get("last_checkpoint") != checkpoint_ids[-1]:
        errors.append("last_checkpoint differs from terminal checkpoint")

    reference_topology = row.get("reference", {}).get("initial_topology", {})
    initial_depth = reference_topology.get("open_void_depth")
    initial_area = row.get("reference", {}).get(
        "initial_cavity_area", reference_topology.get("remaining_void_area")
    )
    initial_mouth = reference_topology.get("mouth_aperture")
    if not all(_number(value) for value in (initial_depth, initial_area, initial_mouth)):
        errors.append("reference topology lacks initial depth, area, or mouth")
        initial_depth = initial_depth if _number(initial_depth) else None

    first_hard = None
    valid_progress = []
    all_failure_types = set()
    required_topology = (
        "open_void_depth",
        "remaining_void_area",
        "mouth_aperture",
        "fill_fraction",
        "overburden_min",
        "overburden_nonuniformity",
    )
    for checkpoint in trajectory:
        topology = checkpoint.get("topology", {})
        diagnostics = checkpoint.get("model_diagnostics", {})
        missing = [
            key for key in required_topology if not _number(topology.get(key))
        ]
        if missing or not isinstance(topology.get("topology_valid"), bool):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} has invalid "
                f"topology metrics: {missing or ['topology_valid']}"
            )
        transition = checkpoint.get("topology_transition")
        if not isinstance(transition, dict) or not isinstance(
            transition.get("valid"), bool
        ):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} lacks transition validity"
            )
        if not isinstance(diagnostics.get("valid"), bool):
            errors.append(
                f"checkpoint {checkpoint.get('checkpoint')} lacks diagnostic validity"
            )
        velocity, velocity_errors = _velocity(diagnostics)
        errors.extend(
            f"checkpoint {checkpoint.get('checkpoint')}: {message}"
            for message in velocity_errors
        )
        failures = _hard_failures(checkpoint)
        all_failure_types.update(failures)
        if failures and first_hard is None:
            first_hard = (checkpoint, failures)
        if (
            first_hard is None
            and not missing
            and topology.get("topology_valid")
            and diagnostics.get("valid")
        ):
            depth_advance = (
                float(initial_depth) - float(topology["open_void_depth"])
                if initial_depth is not None
                else None
            )
            area_reduction = (
                float(initial_area) - float(topology["remaining_void_area"])
                if _number(initial_area)
                else None
            )
            mouth_open = bool(
                topology.get("mouth_open", topology["mouth_aperture"] > 0.0)
            )
            if (
                depth_advance is not None
                and depth_advance > 1e-12
                and area_reduction is not None
                and area_reduction > 1e-12
                and mouth_open
                and float(topology["mouth_aperture"]) > 0.0
            ):
                valid_progress.append({
                    "checkpoint": checkpoint,
                    "depth_advance": depth_advance,
                    "area_reduction": area_reduction,
                    "velocity": velocity,
                })

    target_event = next(
        (item for item in trajectory if item.get("target_pass")), None
    )
    terminal = trajectory[-1]
    max_duration = float(row["numerics"]["max_duration"])
    if first_hard:
        event_status = "hard_failure"
        event_checkpoint, first_failure_types = first_hard
        event_time = float(event_checkpoint["elapsed"])
        censor_time = None
    elif target_event:
        event_status = "resolved_target_event"
        event_checkpoint = target_event
        first_failure_types = []
        event_time = float(target_event["elapsed"])
        censor_time = None
    elif float(terminal["elapsed"]) >= max_duration - 1e-10:
        event_status = "censored_at_max_duration"
        event_checkpoint = terminal
        first_failure_types = []
        event_time = None
        censor_time = float(terminal["elapsed"])
    else:
        event_status = "invalid_early_termination"
        event_checkpoint = terminal
        first_failure_types = []
        event_time = None
        censor_time = float(terminal["elapsed"])
        errors.append("trajectory ended before a hard/target event or censor")

    top_flags = {
        "invalid_topology_seen": "invalid_topology",
        "pinch_off_seen": "pinch_off_or_closed_void",
        "protected_failure_seen": "protected_stack_changed",
        "model_failure_seen": "invalid_model_diagnostic",
    }
    for row_key, failure_type in top_flags.items():
        if bool(row.get(row_key)) != (failure_type in all_failure_types):
            errors.append(f"top-level {row_key} disagrees with trajectory")
    transition_types = all_failure_types - {
        "invalid_topology",
        "degenerate_closed_fragment",
        "pinch_off_or_closed_void",
        "protected_stack_changed",
        "invalid_model_diagnostic",
    }
    if bool(row.get("topology_transition_failure_seen")) != bool(
        transition_types
    ):
        errors.append(
            "top-level topology_transition_failure_seen disagrees with trajectory"
        )
    if bool(row.get("target_pass")) != bool(target_event):
        errors.append("top-level target_pass disagrees with trajectory")
    if bool(row.get("screen_pass")) != bool(target_event):
        errors.append("top-level screen_pass disagrees with trajectory")

    if valid_progress:
        best = max(
            valid_progress,
            key=lambda item: (
                item["depth_advance"]
                if item["depth_advance"] is not None
                else -math.inf,
                float(item["checkpoint"]["topology"]["fill_fraction"]),
                item["area_reduction"],
                -float(item["checkpoint"]["topology"]["remaining_void_area"]),
                float(item["checkpoint"]["topology"]["mouth_aperture"]),
            ),
        )
        checkpoint = best["checkpoint"]
        topology = checkpoint["topology"]
        best_progress = {
            "checkpoint": checkpoint["checkpoint"],
            "elapsed": float(checkpoint["elapsed"]),
            "open_void_depth": float(topology["open_void_depth"]),
            "open_void_depth_advance": best["depth_advance"],
            "remaining_void_area_reduction": best["area_reduction"],
            "remaining_void_area": float(topology["remaining_void_area"]),
            "mouth_aperture": float(topology["mouth_aperture"]),
            "fill_fraction": float(topology["fill_fraction"]),
            "topology_valid": bool(topology["topology_valid"]),
            "overburden_margin": (
                float(topology["overburden_min"])
                - float(row["target"]["min_overburden"])
            ),
            "overburden_nonuniformity": float(
                topology["overburden_nonuniformity"]
            ),
            "velocity": best["velocity"],
        }
    elif initial_depth is not None and _number(initial_area) and _number(initial_mouth):
        best_progress = {
            "checkpoint": 0,
            "elapsed": 0.0,
            "open_void_depth": float(initial_depth),
            "open_void_depth_advance": 0.0,
            "remaining_void_area_reduction": 0.0,
            "remaining_void_area": float(initial_area),
            "mouth_aperture": float(initial_mouth),
            "fill_fraction": 0.0,
            "topology_valid": bool(reference_topology.get("topology_valid", True)),
            "overburden_margin": None,
            "overburden_nonuniformity": None,
            "velocity": None,
        }
    else:
        best_progress = None

    terminal_topology = terminal.get("topology", {})
    terminal_velocity, terminal_velocity_errors = _velocity(
        terminal.get("model_diagnostics", {})
    )
    errors.extend(f"terminal: {message}" for message in terminal_velocity_errors)
    return {
        "case_id": row.get("case_id"),
        "design": row.get("design"),
        "rng_seed": int(row["rng_seed"]),
        "coverage_lambda": _canonical(
            access.recompute_lambda(row["model"]), LAMBDA_LEVELS
        ),
        "sticking_probability": _canonical(
            row["model"]["suppressor_sticking_probability"],
            STICKING_LEVELS,
        ),
        "event_status": event_status,
        "event_time": event_time,
        "censor_time": censor_time,
        "first_hard_failure_types": first_failure_types,
        "all_hard_failure_types": sorted(all_failure_types),
        "reported_target_event": target_event is not None,
        "accepted_pass": False,
        "best_progress": best_progress,
        "terminal_topology_valid": bool(
            terminal_topology.get("topology_valid", False)
        ),
        "terminal_open_void_depth": terminal_topology.get("open_void_depth"),
        "terminal_remaining_void_area": terminal_topology.get(
            "remaining_void_area"
        ),
        "terminal_mouth_aperture": terminal_topology.get("mouth_aperture"),
        "terminal_fill_fraction": terminal_topology.get("fill_fraction"),
        "terminal_velocity": terminal_velocity,
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


def _nested(row, *path):
    value = row
    for key in path:
        if value is None:
            return None
        value = value.get(key)
    return value


METRICS = {
    "hard_failure_time": ("event_time",),
    "censor_time": ("censor_time",),
    "depth_advance": ("best_progress", "open_void_depth_advance"),
    "area_reduction": (
        "best_progress",
        "remaining_void_area_reduction",
    ),
    "open_void_depth": ("best_progress", "open_void_depth"),
    "remaining_void_area": ("best_progress", "remaining_void_area"),
    "mouth_aperture": ("best_progress", "mouth_aperture"),
    "fill_fraction": ("best_progress", "fill_fraction"),
    "overburden_margin": ("best_progress", "overburden_margin"),
    "overburden_nonuniformity": (
        "best_progress",
        "overburden_nonuniformity",
    ),
    "center_velocity": ("best_progress", "velocity", "center_velocity"),
    "field_velocity": ("best_progress", "velocity", "field_velocity"),
    "velocity_contrast": (
        "best_progress",
        "velocity",
        "center_minus_field_velocity",
    ),
}


def recipe_summaries(diagnostics):
    grouped = defaultdict(list)
    for row in diagnostics:
        grouped[(row["coverage_lambda"], row["sticking_probability"])].append(row)
    recipes = []
    for coverage_lambda in LAMBDA_LEVELS:
        for sticking in STICKING_LEVELS:
            rows = grouped[(coverage_lambda, sticking)]
            metrics = {
                name: stats(_nested(row, *path) for row in rows)
                for name, path in METRICS.items()
            }
            failures = Counter(
                failure
                for row in rows
                for failure in row["all_hard_failure_types"]
            )
            events = Counter(row["event_status"] for row in rows)
            recipes.append({
                "design": expected_design_name(coverage_lambda, sticking),
                "coverage_lambda": coverage_lambda,
                "sticking_probability": sticking,
                "expected_n": 4,
                "n": len(rows),
                "complete": len(rows) == 4,
                "seed_labels": sorted(row["rng_seed"] for row in rows),
                "hard_failure_case_count": sum(
                    bool(row["first_hard_failure_types"]) for row in rows
                ),
                "hard_failure_type_counts": dict(sorted(failures.items())),
                "topology_valid_case_count": sum(
                    row["terminal_topology_valid"] for row in rows
                ),
                "censored_case_count": events["censored_at_max_duration"],
                "resolved_target_event_count": events["resolved_target_event"],
                "accepted_pass_count": 0,
                "event_status_counts": dict(sorted(events.items())),
                "metrics": metrics,
                "means": {
                    name: metric["mean"] for name, metric in metrics.items()
                },
                "worst_seed": {
                    "earliest_hard_failure_time": metrics["hard_failure_time"]["min"],
                    "minimum_depth_advance": metrics["depth_advance"]["min"],
                    "minimum_area_reduction": metrics["area_reduction"]["min"],
                    "maximum_remaining_void_area": metrics[
                        "remaining_void_area"
                    ]["max"],
                    "minimum_mouth_aperture": metrics["mouth_aperture"]["min"],
                    "minimum_fill_fraction": metrics["fill_fraction"]["min"],
                    "minimum_velocity_contrast": metrics["velocity_contrast"]["min"],
                    "all_terminal_topologies_valid": bool(
                        rows and all(row["terminal_topology_valid"] for row in rows)
                    ),
                },
                "seed_spread": {
                    name: metric["range"] for name, metric in metrics.items()
                },
            })
    return recipes


def rank_recipes(recipes):
    eligible = [recipe for recipe in recipes if recipe["complete"]]

    def value(recipe, path, fallback):
        item = recipe
        for key in path:
            item = item[key]
        return fallback if item is None else item

    def key(recipe):
        return (
            -recipe["hard_failure_case_count"],
            recipe["topology_valid_case_count"],
            recipe["resolved_target_event_count"],
            value(recipe, ("worst_seed", "minimum_depth_advance"), -math.inf),
            value(recipe, ("worst_seed", "minimum_area_reduction"), -math.inf),
            -value(
                recipe,
                ("worst_seed", "maximum_remaining_void_area"),
                math.inf,
            ),
            value(recipe, ("worst_seed", "minimum_mouth_aperture"), -math.inf),
            value(recipe, ("worst_seed", "minimum_fill_fraction"), -math.inf),
            -value(recipe, ("metrics", "hard_failure_time", "max"), math.inf),
            -recipe["coverage_lambda"],
            -recipe["sticking_probability"],
        )

    ordered = sorted(eligible, key=key, reverse=True)
    return [
        {
            "rank": index,
            "design": recipe["design"],
            "coverage_lambda": recipe["coverage_lambda"],
            "sticking_probability": recipe["sticking_probability"],
            "next_model_experiment_only": True,
            "accepted_pass": False,
            "hard_failure_case_count": recipe["hard_failure_case_count"],
            "censored_case_count": recipe["censored_case_count"],
            "resolved_target_event_count": recipe[
                "resolved_target_event_count"
            ],
            "worst_seed": recipe["worst_seed"],
        }
        for index, recipe in enumerate(ordered, 1)
    ]


def _next_decision(status, ranking):
    if status != "complete" or not ranking:
        return {
            "classification": "complete_current_matrix_before_decision",
            "reason": "No boundary decision is accepted from partial or invalid rows.",
        }
    winner = ranking[0]
    boundary_axes = []
    if winner["coverage_lambda"] in {min(LAMBDA_LEVELS), max(LAMBDA_LEVELS)}:
        boundary_axes.append("lambda")
    if winner["sticking_probability"] in {
        min(STICKING_LEVELS),
        max(STICKING_LEVELS),
    }:
        boundary_axes.append("sticking")
    if winner["hard_failure_case_count"]:
        return {
            "classification": "revise_or_refine_model_failure_region",
            "boundary_axes": boundary_axes,
            "reason": (
                "Every leading region still contains a replicated hard failure; "
                "a boundary location does not override that gate."
            ),
        }
    if boundary_axes:
        return {
            "classification": "expand_boundary_before_promotion",
            "boundary_axes": boundary_axes,
            "reason": (
                "The first-ranked robust region is on the tested "
                f"{' and '.join(boundary_axes)} boundary; expand it before "
                "promotion or best-region language."
            ),
        }
    if winner["censored_case_count"]:
        return {
            "classification": "resolve_kinetic_censoring",
            "boundary_axes": [],
            "reason": (
                "The leading hard-gate-clear region is unfinished at duration "
                "8; extend or alter the model experiment without calling it a pass."
            ),
        }
    if winner["resolved_target_event_count"] == 4:
        return {
            "classification": "numerical_confirmation",
            "boundary_axes": [],
            "reason": (
                "All four seeds reach the resolved target; next require half-grid "
                "and half-checkpoint confirmation."
            ),
        }
    return {
        "classification": "diagnose_unfinished_nonboundary_region",
        "boundary_axes": [],
        "reason": "The leading region is hard-gate clear but has not reached the target.",
    }


def build_summary(manifest, rows, parse_errors, rows_missing, fingerprint):
    cases = access.expand_cases(manifest, fingerprint)
    manifest_errors = validate_manifest(manifest, cases)
    expected_by_key = {
        (case["design"], case["rng_seed"]): case for case in cases
    }
    attempts_by_key = defaultdict(list)
    invalid_attempts = []
    unexpected_rows = []
    all_error_rows = []
    current_error_rows = []
    superseded_rows = []
    superseded_error_rows = []
    for row in rows:
        logical = (row.get("design"), row.get("rng_seed"))
        expected = expected_by_key.get(logical)
        if expected is None:
            unexpected_rows.append(row)
            continue
        attempts_by_key[logical].append(row)
        superseded = access._is_superseded_fingerprint_attempt(
            row, expected, fingerprint
        )
        attempt_errors = access.validate_attempt(row, expected, fingerprint)
        if superseded:
            superseded_rows.append(row)
        elif attempt_errors:
            invalid_attempts.append({"reasons": attempt_errors, "row": row})
        if not row.get("ok"):
            all_error_rows.append(row)
            if superseded:
                superseded_error_rows.append(row)
            else:
                current_error_rows.append(row)

    selected = []
    diagnostics = []
    invalid_metric_rows = []
    missing_cases = []
    duplicate_success_ids = []
    for expected in cases:
        attempts = attempts_by_key[(expected["design"], expected["rng_seed"])]
        current_successes = [
            row
            for row in attempts
            if row.get("ok")
            and not access.validate_attempt(row, expected, fingerprint)
        ]
        if len(current_successes) > 1:
            duplicate_success_ids.append(expected["case_id"])
        if not current_successes:
            missing_cases.append({
                "case_id": expected["case_id"],
                "design": expected["design"],
                "rng_seed": expected["rng_seed"],
                "attempt_count": len(attempts),
            })
            continue
        row = current_successes[-1]
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
        or unexpected_rows
        or current_error_rows
        or invalid_metric_rows
        or duplicate_success_ids
    )
    complete = bool(
        not rows_missing
        and not invalid
        and len(selected) == 72
        and len(diagnostics) == 72
    )
    status = (
        "complete"
        if complete
        else "missing_rows"
        if rows_missing
        else "incomplete_or_invalid"
    )
    recipes = recipe_summaries(diagnostics)
    ranking = rank_recipes(recipes) if complete else []
    decision = _next_decision(status, ranking)
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
        "status": status,
        "campaign": manifest.get("campaign"),
        "expected_case_count": 72,
        "attempt_count": len(rows),
        "selected_current_case_count": len(selected),
        "metric_valid_case_count": len(diagnostics),
        "model_acceptance_eligible": False,
        "recipe_acceptance_eligible": False,
        "production_doe_eligible": False,
        "accepted_pass_count": 0,
        "expected_runtime_fingerprint": fingerprint,
        "observed_runtime_fingerprints": observed_fingerprints,
        "manifest_validation_errors": manifest_errors,
        "parse_errors": parse_errors,
        "error_attempt_rows": all_error_rows,
        "current_fingerprint_error_attempt_rows": current_error_rows,
        "superseded_fingerprint_attempt_rows": superseded_rows,
        "superseded_fingerprint_error_attempt_rows": superseded_error_rows,
        "invalid_attempts": invalid_attempts,
        "invalid_metric_rows": invalid_metric_rows,
        "unexpected_attempt_rows": unexpected_rows,
        "duplicate_success_case_ids": sorted(duplicate_success_ids),
        "missing_cases": missing_cases,
        "recipes": recipes,
        "next_model_experiment_ranking": ranking,
        "ranking_policy": (
            "lexicographic: complete current evidence; zero hard failures; all "
            "terminal topologies valid; resolved target events; worst-seed depth "
            "advance; worst-seed remaining void; mouth margin; fill fraction; time"
        ),
        "next_decision": decision,
        "censoring_rule": (
            "A duration-8 unfinished trajectory is censored unresolved evidence, "
            "never a pass."
        ),
    }


def _fmt(value, digits=5):
    if value is None:
        return "—"
    return f"{value:.{digits}g}" if isinstance(value, (int, float)) else str(value)


def _mean_worst(recipe, metric, worst_key):
    return (
        f"{_fmt(recipe['means'][metric])} / "
        f"{_fmt(recipe['worst_seed'][worst_key])}"
    )


def markdown(summary):
    lines = [
        "# Cu-fill low-sticking boundary refinement",
        "",
        f"Status: **{summary['status']}**. Current cases: "
        f"{summary['selected_current_case_count']}/{summary['expected_case_count']}; "
        f"metric-valid: {summary['metric_valid_case_count']}; current errors: "
        f"{len(summary['current_fingerprint_error_attempt_rows'])}; "
        f"superseded attempts retained: "
        f"{len(summary['superseded_fingerprint_attempt_rows'])}.",
        "",
        "This ranks the next model experiment, not a process setting. A "
        "duration-8 censor is unfinished evidence and never a pass.",
        "",
    ]
    if summary["status"] != "complete":
        lines += [
            "The exact 18-point × 4-seed current matrix is incomplete or "
            "invalid, so no ranking or boundary decision is accepted.",
            "",
        ]
    lines += [
        "## Replicated regions",
        "",
        "Metric cells show mean / worst seed. For depth advance, mouth, fill, "
        "and velocity contrast, lower is the worse seed; for remaining void, "
        "higher is worse.",
        "",
        "| λ | Sticking | n | Hard failures | Event / censor | Topology valid | Depth advance | Remaining void | Mouth | Fill | Center−field velocity |",
        "|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for recipe in summary["recipes"]:
        failures = (
            ", ".join(
                f"{name}:{count}"
                for name, count in recipe["hard_failure_type_counts"].items()
            )
            or "none"
        )
        event_metric = (
            recipe["metrics"]["hard_failure_time"]
            if recipe["metrics"]["hard_failure_time"]["n"]
            else recipe["metrics"]["censor_time"]
        )
        event_worst = (
            event_metric["min"]
            if recipe["metrics"]["hard_failure_time"]["n"]
            else event_metric["max"]
        )
        lines.append(
            f"| {_fmt(recipe['coverage_lambda'])} | "
            f"{_fmt(recipe['sticking_probability'])} | {recipe['n']} | "
            f"{failures} | {_fmt(event_metric['mean'])} / "
            f"{_fmt(event_worst)} | "
            f"{recipe['topology_valid_case_count']}/{recipe['n']} | "
            f"{_mean_worst(recipe, 'depth_advance', 'minimum_depth_advance')} | "
            f"{_mean_worst(recipe, 'remaining_void_area', 'maximum_remaining_void_area')} | "
            f"{_mean_worst(recipe, 'mouth_aperture', 'minimum_mouth_aperture')} | "
            f"{_mean_worst(recipe, 'fill_fraction', 'minimum_fill_fraction')} | "
            f"{_mean_worst(recipe, 'velocity_contrast', 'minimum_velocity_contrast')} |"
        )

    lines += ["", "## Next model experiment", ""]
    if summary["status"] == "complete":
        lines += [
            "Ordering uses hard gates first and worst-seed progress—not a scalar "
            "average or one lucky run.",
            "",
            "| Rank | λ | Sticking | Hard failures | Censored | Worst depth advance | Worst void | Worst mouth | Worst fill |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for item in summary["next_model_experiment_ranking"][:10]:
            worst = item["worst_seed"]
            lines.append(
                f"| {item['rank']} | {_fmt(item['coverage_lambda'])} | "
                f"{_fmt(item['sticking_probability'])} | "
                f"{item['hard_failure_case_count']} | "
                f"{item['censored_case_count']} | "
                f"{_fmt(worst['minimum_depth_advance'])} | "
                f"{_fmt(worst['maximum_remaining_void_area'])} | "
                f"{_fmt(worst['minimum_mouth_aperture'])} | "
                f"{_fmt(worst['minimum_fill_fraction'])} |"
            )
    else:
        lines.append("No ranking is accepted from partial or invalid rows.")

    decision = summary["next_decision"]
    lines += [
        "",
        f"Predeclared next decision: **{decision['classification']}** — "
        f"{decision['reason']}",
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
    rows, parse_errors, rows_missing = access.load_jsonl(args.rows)
    fingerprint = access.runtime_fingerprint(manifest, args.project_root)
    summary = build_summary(
        manifest, rows, parse_errors, rows_missing, fingerprint
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    args.markdown.write_text(markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "attempts": summary["attempt_count"],
        "selected": summary["selected_current_case_count"],
        "metric_valid": summary["metric_valid_case_count"],
        "next_decision": summary["next_decision"]["classification"],
    }))


if __name__ == "__main__":
    main()

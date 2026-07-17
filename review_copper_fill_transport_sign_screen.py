"""Independent audit of the one-checkpoint Cu-fill transport-sign screen."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

import foundation_copper_fill_transport_sign_screen as screen
import foundation_metric_audit as foundation
import review_copper_fill_access_surface as access
import review_copper_fill_regional_kinematics as regional


DEFAULT_MANIFEST = screen.DEFAULT_MANIFEST
DEFAULT_ROWS = screen.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_sign_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_sign_review.md"
)

CASE_FIELDS = (
    "manifest_version",
    "labels",
    "geometry_tier",
    "design",
    "geometry",
    "layers",
    "model",
    "numerics",
    "target",
    "analysis",
    "provenance",
    "runtime_fingerprint",
    "rng_seed",
)
LOWER_REGIONS = ("left_lower_wall", "right_lower_wall")
MIDDLE_UPPER_REGIONS = (
    "left_middle_wall",
    "right_middle_wall",
    "left_upper_wall",
    "right_upper_wall",
)


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_fingerprint(manifest, project_root):
    root = Path(project_root)
    return {
        "runner_sha256": _file_sha256(
            root / "foundation_copper_fill_transport_sign_screen.py"
        ),
        "trajectory_runner_sha256": _file_sha256(
            root / "foundation_copper_fill_trajectory.py"
        ),
        "regional_kinematics_sha256": _file_sha256(
            root / "review_copper_fill_regional_kinematics.py"
        ),
        "traveler_metrics_sha256": _file_sha256(root / "traveler_metrics.py"),
        "tsv_process_sha256": _file_sha256(root / "tsv_process.py"),
        "viennaps_binary_sha256": manifest["provenance"][
            "viennaps_binary_sha256"
        ],
    }


def _case_payload(row):
    return {key: row.get(key) for key in CASE_FIELDS}


def _logical_key(row):
    return row.get("geometry_tier"), row.get("design"), row.get("rng_seed")


def validate_attempt(row, expected, fingerprint):
    errors = []
    if row.get("case_id") != expected["case_id"]:
        errors.append("case_id differs from manifest/current fingerprint")
    if row.get("runtime_fingerprint") != fingerprint:
        errors.append("runtime fingerprint differs from current reviewed files")
    if row.get("case_id") != foundation.case_id(_case_payload(row)):
        errors.append("case_id differs from the row's own case payload")
    for field in CASE_FIELDS:
        if row.get(field) != expected.get(field):
            errors.append(f"case field differs from manifest: {field}")
    if row.get("production_doe_eligible") is not False:
        errors.append("production_doe_eligible is not explicitly false")
    if row.get("morphology_ranking_eligible") is not False:
        errors.append("morphology_ranking_eligible is not explicitly false")
    return errors


def _is_superseded_attempt(row, expected, fingerprint):
    if row.get("runtime_fingerprint") == fingerprint:
        return False
    if row.get("case_id") != foundation.case_id(_case_payload(row)):
        return False
    if row.get("production_doe_eligible") is not False:
        return False
    if row.get("morphology_ranking_eligible") is not False:
        return False
    return all(
        row.get(field) == expected.get(field)
        for field in CASE_FIELDS
        if field != "runtime_fingerprint"
    )


def audit_attempts(manifest, rows, parse_errors, rows_missing, fingerprint):
    """Select exactly one current success per frozen matrix cell."""
    cases = screen.expand_cases(manifest, fingerprint)
    manifest_errors = screen.validate_manifest(manifest, cases)
    expected_by_key = {_logical_key(case): case for case in cases}
    attempts = defaultdict(list)
    invalid_attempts = []
    unexpected_rows = []
    current_errors_by_key = defaultdict(list)
    superseded_rows = []
    superseded_error_rows = []
    row_positions = {id(row): index for index, row in enumerate(rows)}
    for row in rows:
        expected = expected_by_key.get(_logical_key(row))
        if expected is None:
            unexpected_rows.append(row)
            continue
        attempts[_logical_key(row)].append(row)
        attempt_errors = validate_attempt(row, expected, fingerprint)
        superseded = _is_superseded_attempt(row, expected, fingerprint)
        if superseded:
            superseded_rows.append(row)
            if not row.get("ok"):
                superseded_error_rows.append(row)
        elif attempt_errors:
            invalid_attempts.append({"reasons": attempt_errors, "row": row})
        elif not row.get("ok"):
            current_errors_by_key[_logical_key(row)].append(row)

    selected = []
    missing = []
    duplicate_successes = []
    resolved_current_error_rows = []
    unresolved_current_error_rows = []
    for expected in cases:
        successes = [
            row
            for row in attempts[_logical_key(expected)]
            if row.get("ok")
            and not validate_attempt(row, expected, fingerprint)
        ]
        if len(successes) > 1:
            duplicate_successes.append(expected["case_id"])
        if not successes:
            missing.append({
                "case_id": expected["case_id"],
                "geometry_tier": expected["geometry_tier"],
                "design": expected["design"],
                "rng_seed": expected["rng_seed"],
            })
        else:
            selected.append(successes[-1])
        errors_for_case = current_errors_by_key[_logical_key(expected)]
        if errors_for_case and successes:
            latest_success_position = max(
                row_positions[id(row)] for row in successes
            )
            resolved_current_error_rows.extend(
                row
                for row in errors_for_case
                if row_positions[id(row)] < latest_success_position
            )
            unresolved_current_error_rows.extend(
                row
                for row in errors_for_case
                if row_positions[id(row)] > latest_success_position
            )
        elif errors_for_case:
            unresolved_current_error_rows.extend(errors_for_case)

    invalid = bool(
        manifest_errors
        or parse_errors
        or invalid_attempts
        or unexpected_rows
        or unresolved_current_error_rows
        or duplicate_successes
    )
    complete = bool(
        not rows_missing
        and not invalid
        and len(selected) == 168
        and not missing
    )
    return {
        "status": (
            "complete"
            if complete
            else "missing_rows"
            if rows_missing
            else "incomplete_or_invalid"
        ),
        "expected_case_count": 168,
        "attempt_count": len(rows),
        "selected_current_case_count": len(selected),
        "manifest_validation_errors": manifest_errors,
        "parse_errors": parse_errors,
        "rows_missing": rows_missing,
        "invalid_attempts": invalid_attempts,
        "unexpected_attempt_rows": unexpected_rows,
        "current_fingerprint_error_attempt_rows": unresolved_current_error_rows,
        "resolved_current_fingerprint_error_attempt_rows": resolved_current_error_rows,
        "superseded_fingerprint_attempt_count": len(superseded_rows),
        "superseded_fingerprint_error_attempt_count": len(
            superseded_error_rows
        ),
        "duplicate_success_case_ids": sorted(duplicate_successes),
        "missing_cases": missing,
        "selected_rows": selected,
    }


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _mean(regions, region, quantity):
    try:
        return regions[region][quantity]["mean"]
    except (KeyError, TypeError):
        return None


def transport_case_decision(
    regions,
    *,
    balance_valid,
    diagnostics_valid,
    topology_valid,
    transition_valid,
    protected_stack_survives,
):
    """Apply the strict predeclared transport-sign inequalities."""
    required_statistics_valid = True
    for name in screen.REGION_NAMES:
        item = regions.get(name, {})
        if not isinstance(item.get("point_count"), int) or item["point_count"] <= 0:
            required_statistics_valid = False
            continue
        for quantity in screen.QUANTITIES:
            statistic = item.get(quantity, {})
            if any(
                not _number(statistic.get(key))
                for key in ("mean", "q10", "q50", "q90")
            ):
                required_statistics_valid = False

    floor_flux = _mean(regions, "floor", "suppressor_flux")
    floor_coverage = _mean(regions, "floor", "coverage")
    floor_velocity = _mean(regions, "floor", "normal_velocity")
    lower_flux_ratios = []
    lower_coverage_margins = []
    lower_velocity_ratios = []
    middle_upper_velocity_margins = []
    if required_statistics_valid:
        for name in LOWER_REGIONS:
            lower_flux = _mean(regions, name, "suppressor_flux")
            lower_coverage = _mean(regions, name, "coverage")
            lower_velocity = _mean(regions, name, "normal_velocity")
            lower_flux_ratios.append(
                floor_flux / lower_flux if lower_flux > 0.0 else None
            )
            lower_coverage_margins.append(lower_coverage - floor_coverage)
            lower_velocity_ratios.append(
                floor_velocity / lower_velocity if lower_velocity > 0.0 else None
            )
        middle_upper_velocity_margins = [
            floor_velocity - _mean(regions, name, "normal_velocity")
            for name in MIDDLE_UPPER_REGIONS
        ]

    flux_condition = bool(
        lower_flux_ratios
        and all(_number(value) and value < 0.95 for value in lower_flux_ratios)
    )
    coverage_condition = bool(
        lower_coverage_margins
        and all(value > 0.0 for value in lower_coverage_margins)
    )
    lower_velocity_condition = bool(
        lower_velocity_ratios
        and all(
            _number(value) and value > 1.05 for value in lower_velocity_ratios
        )
    )
    upper_velocity_condition = bool(
        middle_upper_velocity_margins
        and all(value > 0.0 for value in middle_upper_velocity_margins)
    )
    structural_guard = bool(
        diagnostics_valid
        and topology_valid
        and transition_valid
        and protected_stack_survives
    )
    conditions = {
        "all_required_regions_nonempty_and_finite": required_statistics_valid,
        "diagnostic_balance_valid": bool(balance_valid),
        "diagnostic_and_structure_guards_valid": structural_guard,
        "floor_to_each_lower_flux_ratio_strictly_below_0p95": flux_condition,
        "floor_coverage_strictly_below_each_lower_wall": coverage_condition,
        "floor_to_each_lower_velocity_ratio_strictly_above_1p05": lower_velocity_condition,
        "floor_velocity_strictly_above_each_middle_and_upper_side": upper_velocity_condition,
    }
    return {
        "pass": all(conditions.values()),
        "conditions": conditions,
        "floor_to_lower_flux_ratios": lower_flux_ratios,
        "lower_minus_floor_coverage": lower_coverage_margins,
        "floor_to_lower_velocity_ratios": lower_velocity_ratios,
        "floor_minus_middle_upper_velocity": middle_upper_velocity_margins,
    }


def _structures_close(first, second, tolerance=1e-12):
    if isinstance(first, dict) and isinstance(second, dict):
        return set(first) == set(second) and all(
            _structures_close(first[key], second[key], tolerance)
            for key in first
        )
    if isinstance(first, list) and isinstance(second, list):
        return len(first) == len(second) and all(
            _structures_close(a, b, tolerance) for a, b in zip(first, second)
        )
    if _number(first) and _number(second):
        return math.isclose(
            float(first), float(second), rel_tol=0.0, abs_tol=tolerance
        )
    return first == second


def _load_snapshot(row, project_root):
    errors = []
    trajectory_rows = row.get("trajectory")
    if not isinstance(trajectory_rows, list) or len(trajectory_rows) != 1:
        return None, ["successful row must contain exactly one checkpoint"]
    checkpoint = trajectory_rows[0]
    interval = float(row["numerics"]["checkpoint_interval"])
    if checkpoint.get("checkpoint") != 1 or not math.isclose(
        float(checkpoint.get("elapsed", math.nan)), interval, rel_tol=0.0, abs_tol=1e-12
    ):
        errors.append("checkpoint identity or elapsed time differs from manifest")
    declared = checkpoint.get("snapshot_path")
    if declared != row.get("diagnostic_snapshot_path"):
        errors.append("top-level and checkpoint snapshot paths differ")
    path = Path(declared or "")
    if not path.is_absolute():
        path = Path(project_root) / path
    profile, profile_errors = regional.snapshot_profile(
        path,
        checkpoint,
        row["reference"],
        float(row["numerics"]["grid_delta"]),
    )
    errors.extend(profile_errors)
    if not path.is_file():
        return None, errors
    if row.get("diagnostic_snapshot_sha256") != _file_sha256(path):
        errors.append("diagnostic snapshot hash differs from row")
    try:
        with np.load(path, allow_pickle=False) as snapshot:
            raw = {
                "coordinates": np.asarray(
                    snapshot["diagnostic_coordinates"], dtype=float
                ),
                "material_ids": np.asarray(
                    snapshot["diagnostic_material_ids"], dtype=float
                ),
                "suppressor_flux": np.asarray(
                    snapshot["diagnostic_suppressor_flux"], dtype=float
                ),
                "coverage": np.asarray(
                    snapshot["diagnostic_coverage"], dtype=float
                ),
                "velocity": np.asarray(
                    snapshot["diagnostic_velocity"], dtype=float
                ),
                "adsorption_term": np.asarray(
                    snapshot["diagnostic_adsorption_term"], dtype=float
                ),
                "deactivation_term": np.asarray(
                    snapshot["diagnostic_deactivation_term"], dtype=float
                ),
            }
            saved_balance = np.asarray(
                snapshot["diagnostic_relative_balance_error"], dtype=float
            ).reshape(-1)
    except Exception as error:
        return None, [*errors, f"cannot load raw diagnostic arrays: {error!r}"]
    if len(saved_balance) != 1 or not np.isfinite(saved_balance[0]):
        errors.append("snapshot balance error is not one finite scalar")
    return {
        "path": str(path),
        "profile": profile,
        "raw": raw,
        "saved_balance_error": (
            float(saved_balance[0]) if len(saved_balance) == 1 else None
        ),
    }, errors


def _review_case(row, project_root):
    errors = []
    loaded, snapshot_errors = _load_snapshot(row, project_root)
    errors.extend(snapshot_errors)
    if loaded is None:
        return None, errors
    checkpoint = row["trajectory"][0]
    if row.get("last_checkpoint") != 1:
        errors.append("last_checkpoint is not one")
    if row.get("target_pass") is not False:
        errors.append("one-checkpoint transport row reports a morphology target pass")
    if row.get("transport_screen_pass") is not None:
        errors.append("runner preempted the four-stream reviewer decision")
    stream = row.get("rng_stream", {})
    if not stream or (
        stream.get("base_seed") != row.get("rng_seed")
        or stream.get("checkpoint_seed") != int(row["rng_seed"]) + 1
        or stream.get("paired_across_designs") is not True
    ):
        errors.append("declared RNG stream differs from base+checkpoint policy")
    diagnostics = checkpoint.get("model_diagnostics", {})
    topology = checkpoint.get("topology", {})
    transition = checkpoint.get("topology_transition", {})
    protected = checkpoint.get("protected_stack", {})
    balance = diagnostics.get("relative_balance_error")
    balance_valid = bool(
        _number(balance) and float(balance) <= float(row["target"]["max_balance_error"])
    )
    raw = loaded["raw"]
    plating_material_ids = row.get("plating_material_legacy_ids")
    if not isinstance(plating_material_ids, list) or not plating_material_ids:
        errors.append("plating material IDs are missing")
    point_count = len(raw["coordinates"])
    if point_count <= 0 or raw["coordinates"].ndim != 2:
        errors.append("raw diagnostic coordinates are empty or malformed")
    for name, values in raw.items():
        if name == "coordinates":
            continue
        if values.shape != (point_count,):
            errors.append(f"raw diagnostic array does not align: {name}")
        elif not np.all(np.isfinite(values)):
            errors.append(f"raw diagnostic array contains nonfinite values: {name}")
    if (
        _number(loaded.get("saved_balance_error"))
        and _number(balance)
        and not math.isclose(
            float(loaded["saved_balance_error"]),
            float(balance),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ):
        errors.append("snapshot and row equilibrium-balance errors differ")
    if errors:
        return None, errors
    masks = screen._authoritative_region_masks(
        raw["coordinates"], row["reference"]
    )
    try:
        regions = screen.detailed_region_statistics(
            raw["coordinates"],
            raw["suppressor_flux"],
            raw["coverage"],
            raw["velocity"],
            row["reference"],
            diagnostic_summary=diagnostics,
            masks=masks,
        )
    except Exception as error:
        return None, [*errors, f"invalid regional diagnostics: {error}"]
    if not _structures_close(regions, checkpoint.get("analysis_regions")):
        errors.append("saved regional statistics differ from raw snapshot")

    model = row["model"]
    pi_a = (
        float(model["adsorption_strength"])
        * float(model["suppressor_sticking_probability"])
        / (
            float(model["deactivation_rate"])
            * float(model["active_deposition_rate"])
        )
    )
    analytic = screen.analytic_diagnostics(
        raw["suppressor_flux"],
        raw["material_ids"],
        row["plating_material_legacy_ids"],
        pi_a=pi_a,
        deactivation_rate=model["deactivation_rate"],
        active_rate=model["active_deposition_rate"],
        suppressed_rate=model["suppressed_deposition_rate"],
    )
    parity = {
        "coverage_max_abs_error": float(
            np.max(np.abs(analytic["coverage"] - raw["coverage"]))
        ),
        "velocity_max_abs_error": float(
            np.max(np.abs(analytic["velocity"] - raw["velocity"]))
        ),
        "adsorption_term_max_abs_error": float(
            np.max(np.abs(analytic["adsorption_term"] - raw["adsorption_term"]))
        ),
        "deactivation_term_max_abs_error": float(
            np.max(np.abs(analytic["deactivation_term"] - raw["deactivation_term"]))
        ),
        "analytic_relative_balance_error": analytic["relative_balance_error"],
    }
    parity_tolerance = float(row["analysis"]["analytic_parity_abs_tolerance"])
    if any(
        parity[key] > parity_tolerance
        for key in (
            "coverage_max_abs_error",
            "velocity_max_abs_error",
            "adsorption_term_max_abs_error",
            "deactivation_term_max_abs_error",
        )
    ):
        errors.append("exact equilibrium law does not match saved C++ diagnostics")

    decision = transport_case_decision(
        regions,
        balance_valid=balance_valid,
        diagnostics_valid=diagnostics.get("valid") is True,
        topology_valid=topology.get("topology_valid") is True,
        transition_valid=transition.get("valid") is True,
        protected_stack_survives=protected.get("survives") is True,
    )
    geometry = regional._reference_geometry(row["reference"])
    declared_depth = float(row["geometry"]["depth"])
    if not math.isclose(
        geometry["H"], declared_depth, rel_tol=0.0, abs_tol=0.1
    ):
        errors.append("measured post-seed cavity height is inconsistent with its geometry tier")
    expected_tier = (
        "continuity" if math.isclose(declared_depth, 1.25) else
        "nominal_hbm" if math.isclose(declared_depth, 3.0) else None
    )
    if row.get("geometry_tier") != expected_tier:
        errors.append("geometry_tier label differs from the declared depth")
    public = {
        "case_id": row["case_id"],
        "geometry_tier": row["geometry_tier"],
        "design": row["design"],
        "rng_seed": row["rng_seed"],
        "sticking_probability": float(
            model["suppressor_sticking_probability"]
        ),
        "source_power": float(model["suppressor_source_power"]),
        "transport_sign": decision,
        "kinematic_threshold_H_over_a": geometry[
            "nominal_threshold_H_over_a"
        ],
        "analytic_law_parity": parity,
        "topology_valid": topology.get("topology_valid") is True,
        "topology_transition_valid": transition.get("valid") is True,
        "protected_stack_survives": protected.get("survives") is True,
        "diagnostic_balance_valid": balance_valid,
        "diagnostic_snapshot_path": loaded["path"],
    }
    internal = {
        "raw": raw,
        "masks": masks,
        "reference": row["reference"],
        "model": model,
        "plating_material_ids": row["plating_material_legacy_ids"],
    }
    return {"public": public, "internal": internal}, errors


def _analytic_ratio(record, pi_a, suppressed_rate):
    internal = record["internal"]
    model = internal["model"]
    predicted = screen.analytic_diagnostics(
        internal["raw"]["suppressor_flux"],
        internal["raw"]["material_ids"],
        internal["plating_material_ids"],
        pi_a=pi_a,
        deactivation_rate=model["deactivation_rate"],
        active_rate=model["active_deposition_rate"],
        suppressed_rate=suppressed_rate,
    )
    return _velocity_ratio(record, predicted["velocity"])


def _velocity_ratio(record, velocity):
    internal = record["internal"]
    velocity = np.asarray(velocity, dtype=float)
    masks = internal["masks"]
    floor = float(np.mean(velocity[masks["floor"]]))
    walls = [
        float(np.mean(velocity[masks[name]]))
        for name in screen.WALL_REGION_NAMES
    ]
    fastest_wall = max(walls)
    if fastest_wall > 0.0:
        return floor / fastest_wall
    return math.inf if floor > 0.0 else None


def _json_ratio(value):
    if value is None:
        return None
    if value == math.inf:
        return "infinite"
    if value == -math.inf:
        return "negative_infinite"
    if not _number(value):
        return "invalid_nonfinite"
    return float(value)


def _ratio_vector_summary(ratios, expected_count):
    """Summarize ratios without minimizing undefined zero/zero streams."""
    eligible_flags = [
        _number(value) or value == math.inf for value in ratios
    ]
    eligible = bool(
        len(ratios) == expected_count and all(eligible_flags)
    )
    return {
        "eligible": eligible,
        "status": (
            "eligible"
            if eligible
            else "ineligible_undefined_or_nonfinite_stream_ratio"
        ),
        "stream_count": len(ratios),
        "invalid_stream_indices": [
            index for index, valid in enumerate(eligible_flags) if not valid
        ],
        "stream_ratios": [_json_ratio(value) for value in ratios],
        "worst_ratio": (
            _json_ratio(min(ratios)) if eligible else None
        ),
    }


def analytic_pi_limits(records, manifest):
    """Evaluate exact Pi_A endpoints, including saved zero-flux points."""
    grouped = defaultdict(list)
    for record in records:
        grouped[record["public"]["design"]].append(record)
    r_fractions = manifest["analysis"]["analytic_envelope_R_over_Va"]
    designs = []
    qualified = []
    total_zero_flux_points = 0
    for sticking in screen.STICKING_LEVELS:
        for power in screen.SOURCE_POWER_LEVELS:
            design = screen.expected_design_name(sticking, power)
            design_records = grouped[design]
            thresholds = [
                record["public"]["kinematic_threshold_H_over_a"]
                for record in design_records
            ]
            pi_zero_ratios = [
                _analytic_ratio(
                    record,
                    0.0,
                    record["internal"]["model"]["suppressed_deposition_rate"],
                )
                for record in design_records
            ]
            pi_zero_valid = all(
                _number(ratio) or ratio == math.inf
                for ratio in pi_zero_ratios
            )
            pi_zero_margin = (
                min(
                    ratio / threshold
                    for ratio, threshold in zip(pi_zero_ratios, thresholds)
                )
                if pi_zero_valid and len(pi_zero_ratios) == 8
                else None
            )

            infinity_candidates = []
            zero_flux_points = 0
            for r_fraction in r_fractions:
                ratios = []
                for record in design_records:
                    internal = record["internal"]
                    raw = internal["raw"]
                    model = internal["model"]
                    plating = np.isin(
                        raw["material_ids"],
                        np.asarray(internal["plating_material_ids"], dtype=float),
                    )
                    required = np.logical_or.reduce([
                        internal["masks"][name] for name in screen.REGION_NAMES
                    ])
                    if r_fraction == r_fractions[0]:
                        zero_flux_points += int(np.count_nonzero(
                            required & plating & (raw["suppressor_flux"] <= 0.0)
                        ))
                    velocity = np.zeros_like(raw["suppressor_flux"], dtype=float)
                    positive_flux = raw["suppressor_flux"] > 0.0
                    active_rate = float(model["active_deposition_rate"])
                    suppressed_rate = float(r_fraction) * active_rate
                    velocity[plating & positive_flux] = suppressed_rate
                    velocity[plating & ~positive_flux] = active_rate
                    ratios.append(_velocity_ratio(record, velocity))
                valid = bool(
                    len(ratios) == 8
                    and all(
                        _number(ratio) or ratio == math.inf for ratio in ratios
                    )
                )
                if valid:
                    infinity_candidates.append({
                        "R_over_Va": float(r_fraction),
                        "worst_normalized_margin": min(
                            ratio / threshold
                            for ratio, threshold in zip(ratios, thresholds)
                        ),
                    })
            best_infinity = (
                max(
                    infinity_candidates,
                    key=lambda item: item["worst_normalized_margin"],
                )
                if infinity_candidates
                else None
            )
            pi_zero_pass = bool(
                pi_zero_margin is not None and pi_zero_margin > 1.0
            )
            infinity_pass = bool(
                best_infinity is not None
                and best_infinity["worst_normalized_margin"] > 1.0
            )
            item = {
                "design": design,
                "sticking_probability": sticking,
                "source_power": power,
                "stream_count": len(design_records),
                "required_region_zero_flux_point_count": zero_flux_points,
                "pi_a_zero": {
                    "worst_normalized_margin": _json_ratio(pi_zero_margin),
                    "all_eight_streams_exceed_tier_threshold": pi_zero_pass,
                },
                "pi_a_infinity": {
                    "best_R_over_Va": (
                        best_infinity["R_over_Va"] if best_infinity else None
                    ),
                    "best_worst_normalized_margin": (
                        _json_ratio(best_infinity["worst_normalized_margin"])
                        if best_infinity
                        else None
                    ),
                    "all_eight_streams_exceed_tier_threshold": infinity_pass,
                },
            }
            designs.append(item)
            total_zero_flux_points += zero_flux_points
            if pi_zero_pass:
                qualified.append({
                    "design": design,
                    "coefficient_boundary_details": [{
                        "factor": "pi_a",
                        "boundary": "physical_lower",
                        "action": "confirm inward sensitivity above Pi_A=0",
                    }],
                })
            if infinity_pass:
                qualified.append({
                    "design": design,
                    "coefficient_boundary_details": [{
                        "factor": "pi_a",
                        "boundary": "asymptotic_upper",
                        "action": "confirm large finite Pi_A convergence and inward sensitivity",
                    }],
                })
    return {
        "method": "Pi_A=0 is evaluated with the exact law; Pi_A to infinity uses R on every positive-flux plating point and Va on saved zero-flux plating points",
        "required_region_zero_flux_point_count": total_zero_flux_points,
        "designs": designs,
        "cross_tier_kinematic_passes": qualified,
    }


def analytic_counterfactuals(records, manifest):
    """Evaluate the frozen Pi_A/R grid on each saved C++ transport field."""
    grouped = defaultdict(list)
    for record in records:
        grouped[(
            record["public"]["geometry_tier"],
            record["public"]["design"],
        )].append(record)
    results = []
    qualified = []
    for geometry_tier in screen.GEOMETRY_TIERS:
        for sticking in screen.STICKING_LEVELS:
            for power in screen.SOURCE_POWER_LEVELS:
                design = screen.expected_design_name(sticking, power)
                design_records = grouped[(geometry_tier, design)]
                for pi_a in manifest["analysis"]["analytic_pi_a"]:
                    for suppressed_rate in manifest["analysis"][
                        "analytic_suppressed_rate_R"
                    ]:
                        ratios = []
                        thresholds = []
                        for record in design_records:
                            internal = record["internal"]
                            ratios.append(
                                _analytic_ratio(record, pi_a, suppressed_rate)
                            )
                            thresholds.append(
                                regional._reference_geometry(
                                    internal["reference"]
                                )["nominal_threshold_H_over_a"]
                            )
                        ratio_summary = _ratio_vector_summary(ratios, 4)
                        valid = bool(
                            ratio_summary["eligible"]
                            and len(thresholds) == 4
                        )
                        kinematic_pass = bool(
                            valid
                            and all(
                                ratio > threshold
                                for ratio, threshold in zip(ratios, thresholds)
                            )
                        )
                        item = {
                            "geometry_tier": geometry_tier,
                            "design": design,
                            "sticking_probability": sticking,
                            "source_power": power,
                            "pi_a": float(pi_a),
                            "suppressed_rate_R": float(suppressed_rate),
                            "R_over_Va": float(suppressed_rate)
                            / float(design_records[0]["internal"]["model"][
                                "active_deposition_rate"
                            ]),
                            "stream_count": len(ratios),
                            "ratio_status": ratio_summary["status"],
                            "invalid_stream_indices": ratio_summary[
                                "invalid_stream_indices"
                            ],
                            "stream_velocity_ratios": ratio_summary[
                                "stream_ratios"
                            ],
                            "worst_stream_floor_to_fastest_wall_velocity_ratio": (
                                ratio_summary["worst_ratio"]
                            ),
                            "kinematic_threshold_H_over_a": (
                                max(thresholds) if thresholds else None
                            ),
                            "all_four_streams_exceed_kinematic_threshold": kinematic_pass,
                        }
                        item["coefficient_boundary_details"] = (
                            [{
                                "factor": "R_over_Va",
                                "boundary": "physical_lower",
                                "action": "confirm inward sensitivity at small positive R",
                            }]
                            if item["R_over_Va"] == 0.0
                            else [{
                                "factor": "R_over_Va",
                                "boundary": "physical_upper",
                                "action": "confirm inward sensitivity below uniform-rate R/Va=1",
                            }]
                            if item["R_over_Va"] == 1.0
                            else []
                        )
                        results.append(item)
                        if kinematic_pass:
                            qualified.append(item)
    grouped_results = defaultdict(dict)
    for item in results:
        key = (
            item["design"],
            item["pi_a"],
            item["suppressed_rate_R"],
        )
        grouped_results[key][item["geometry_tier"]] = item
    cross_tier_qualified = []
    for (design, pi_a, suppressed_rate), tiers in grouped_results.items():
        if set(tiers) != set(screen.GEOMETRY_TIERS):
            continue
        if all(
            tiers[tier]["all_four_streams_exceed_kinematic_threshold"]
            for tier in screen.GEOMETRY_TIERS
        ):
            cross_tier_qualified.append({
                "design": design,
                "sticking_probability": tiers["continuity"][
                    "sticking_probability"
                ],
                "source_power": tiers["continuity"]["source_power"],
                "pi_a": pi_a,
                "suppressed_rate_R": suppressed_rate,
                "R_over_Va": tiers["continuity"]["R_over_Va"],
                "tier_results": {
                    tier: {
                        "worst_stream_floor_to_fastest_wall_velocity_ratio": tiers[
                            tier
                        ]["worst_stream_floor_to_fastest_wall_velocity_ratio"],
                        "kinematic_threshold_H_over_a": tiers[tier][
                            "kinematic_threshold_H_over_a"
                        ],
                    }
                    for tier in screen.GEOMETRY_TIERS
                },
                "all_eight_streams_exceed_tier_kinematic_threshold": True,
                "coefficient_boundary_details": tiers["continuity"][
                    "coefficient_boundary_details"
                ],
            })
    return results, qualified, cross_tier_qualified


def analytic_envelope(records, manifest):
    """Search the declared coefficient envelope after flux gating."""
    grouped = defaultdict(list)
    for record in records:
        grouped[(
            record["public"]["geometry_tier"],
            record["public"]["design"],
        )].append(record)
    envelope_spec = manifest["analysis"]["analytic_envelope_log10_pi_a"]
    pi_values = np.logspace(
        float(envelope_spec["minimum"]),
        float(envelope_spec["maximum"]),
        int(envelope_spec["count"]),
    )
    r_fractions = manifest["analysis"]["analytic_envelope_R_over_Va"]
    near_fraction = float(
        manifest["analysis"]["analytic_envelope_near_threshold_fraction"]
    )
    summaries = []
    qualified = []
    inconclusive = []
    cross_tier_evaluations = defaultdict(dict)
    for geometry_tier in screen.GEOMETRY_TIERS:
        for sticking in screen.STICKING_LEVELS:
            for power in screen.SOURCE_POWER_LEVELS:
                design = screen.expected_design_name(sticking, power)
                records_at_design = grouped[(geometry_tier, design)]
                flux_sign_pass = bool(
                    len(records_at_design) == 4
                    and all(
                        record["public"]["transport_sign"]["conditions"][
                            "floor_to_each_lower_flux_ratio_strictly_below_0p95"
                        ]
                        for record in records_at_design
                    )
                )
                threshold = max(
                    record["public"]["kinematic_threshold_H_over_a"]
                    for record in records_at_design
                )
                best = None
                best_interior_pass = None
                if flux_sign_pass:
                    active_rate = float(
                        records_at_design[0]["internal"]["model"][
                            "active_deposition_rate"
                        ]
                    )
                    for pi_a in pi_values:
                        for r_fraction in r_fractions:
                            suppressed_rate = float(r_fraction) * active_rate
                            ratios = [
                                _analytic_ratio(record, pi_a, suppressed_rate)
                                for record in records_at_design
                            ]
                            if not all(
                                _number(value) or value == math.inf
                                for value in ratios
                            ):
                                continue
                            worst = min(ratios)
                            cross_tier_evaluations[(
                                design,
                                float(pi_a),
                                float(r_fraction),
                            )][geometry_tier] = {
                                "worst_ratio": worst,
                                "threshold": threshold,
                                "normalized_margin": worst / threshold,
                                "suppressed_rate_R": suppressed_rate,
                            }
                            if best is None or worst > best["_ratio"]:
                                best = {
                                    "_ratio": worst,
                                    "pi_a": float(pi_a),
                                    "suppressed_rate_R": suppressed_rate,
                                    "R_over_Va": float(r_fraction),
                                }
                            log_pi = math.log10(float(pi_a))
                            interior = bool(
                                float(r_fraction) not in {0.0, 1.0}
                                and not math.isclose(
                                    log_pi,
                                    float(envelope_spec["minimum"]),
                                    rel_tol=0.0,
                                    abs_tol=1e-12,
                                )
                                and not math.isclose(
                                    log_pi,
                                    float(envelope_spec["maximum"]),
                                    rel_tol=0.0,
                                    abs_tol=1e-12,
                                )
                            )
                            if (
                                interior
                                and worst > threshold
                                and (
                                    best_interior_pass is None
                                    or worst > best_interior_pass["_ratio"]
                                )
                            ):
                                best_interior_pass = {
                                    "_ratio": worst,
                                    "pi_a": float(pi_a),
                                    "suppressed_rate_R": suppressed_rate,
                                    "R_over_Va": float(r_fraction),
                                }
                    if best_interior_pass is not None:
                        best = best_interior_pass
                if best is None:
                    item = {
                        "geometry_tier": geometry_tier,
                        "design": design,
                        "sticking_probability": sticking,
                        "source_power": power,
                        "all_four_streams_pass_fixed_flux_gate": flux_sign_pass,
                        "best_worst_stream_ratio": None,
                        "kinematic_threshold_H_over_a": threshold,
                        "all_four_streams_exceed_kinematic_threshold": False,
                        "coefficient_boundary_limited": False,
                        "near_threshold": False,
                    }
                else:
                    ratio = best.pop("_ratio")
                    log_pi = math.log10(best["pi_a"])
                    pi_boundary = bool(
                        math.isclose(
                            log_pi,
                            float(envelope_spec["minimum"]),
                            rel_tol=0.0,
                            abs_tol=1e-12,
                        )
                        or math.isclose(
                            log_pi,
                            float(envelope_spec["maximum"]),
                            rel_tol=0.0,
                            abs_tol=1e-12,
                        )
                    )
                    coefficient_boundary_details = []
                    if pi_boundary:
                        coefficient_boundary_details.append({
                            "factor": "pi_a",
                            "boundary": "finite_envelope_limit",
                            "action": "expand or analytically bound the Pi_A envelope",
                        })
                    if best["R_over_Va"] == 0.0:
                        coefficient_boundary_details.append({
                            "factor": "R_over_Va",
                            "boundary": "physical_lower",
                            "action": "confirm inward sensitivity at small positive R",
                        })
                    elif best["R_over_Va"] == 1.0:
                        coefficient_boundary_details.append({
                            "factor": "R_over_Va",
                            "boundary": "physical_upper",
                            "action": "confirm inward sensitivity below uniform-rate R/Va=1",
                        })
                    item = {
                        "geometry_tier": geometry_tier,
                        "design": design,
                        "sticking_probability": sticking,
                        "source_power": power,
                        "all_four_streams_pass_fixed_flux_gate": True,
                        **best,
                        "best_worst_stream_ratio": _json_ratio(ratio),
                        "kinematic_threshold_H_over_a": threshold,
                        "all_four_streams_exceed_kinematic_threshold": bool(
                            ratio > threshold
                        ),
                        "coefficient_boundary_limited": bool(
                            coefficient_boundary_details and ratio > 1.01
                        ),
                        "coefficient_boundary_details": coefficient_boundary_details,
                        "near_threshold": bool(
                            ratio <= threshold
                            and ratio >= near_fraction * threshold
                        ),
                    }
                summaries.append(item)
                if item["all_four_streams_exceed_kinematic_threshold"]:
                    qualified.append(item)
                if item["coefficient_boundary_limited"] or item["near_threshold"]:
                    inconclusive.append(item)
    cross_summaries = []
    cross_qualified = []
    cross_inconclusive = []
    grouped_cross = defaultdict(list)
    for (design, pi_a, r_fraction), tiers in cross_tier_evaluations.items():
        if set(tiers) != set(screen.GEOMETRY_TIERS):
            continue
        grouped_cross[design].append({
            "pi_a": pi_a,
            "R_over_Va": r_fraction,
            "suppressed_rate_R": tiers["continuity"]["suppressed_rate_R"],
            "_worst_normalized_margin": min(
                tiers[tier]["normalized_margin"]
                for tier in screen.GEOMETRY_TIERS
            ),
            "tier_results": {
                tier: {
                    "worst_stream_ratio": _json_ratio(
                        tiers[tier]["worst_ratio"]
                    ),
                    "threshold_H_over_a": tiers[tier]["threshold"],
                    "normalized_margin": _json_ratio(
                        tiers[tier]["normalized_margin"]
                    ),
                }
                for tier in screen.GEOMETRY_TIERS
            },
        })
    for sticking in screen.STICKING_LEVELS:
        for power in screen.SOURCE_POWER_LEVELS:
            design = screen.expected_design_name(sticking, power)
            candidates = grouped_cross[design]
            if not candidates:
                item = {
                    "design": design,
                    "sticking_probability": sticking,
                    "source_power": power,
                    "both_tiers_pass_fixed_flux_gate": False,
                    "best_worst_normalized_margin": None,
                    "all_eight_streams_exceed_tier_kinematic_threshold": False,
                    "coefficient_boundary_limited": False,
                    "near_threshold": False,
                }
            else:
                overall_best = max(
                    candidates,
                    key=lambda candidate: candidate[
                        "_worst_normalized_margin"
                    ],
                )
                passing_candidates = [
                    candidate
                    for candidate in candidates
                    if candidate["_worst_normalized_margin"] > 1.0
                ]
                interior_passing_candidates = [
                    candidate
                    for candidate in passing_candidates
                    if candidate["R_over_Va"] not in {0.0, 1.0}
                    and not math.isclose(
                        math.log10(candidate["pi_a"]),
                        float(envelope_spec["minimum"]),
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    )
                    and not math.isclose(
                        math.log10(candidate["pi_a"]),
                        float(envelope_spec["maximum"]),
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    )
                ]
                best = (
                    max(
                        interior_passing_candidates,
                        key=lambda candidate: candidate[
                            "_worst_normalized_margin"
                        ],
                    )
                    if interior_passing_candidates
                    else overall_best
                )
                log_pi = math.log10(best["pi_a"])
                pi_boundary = bool(
                    math.isclose(
                        log_pi,
                        float(envelope_spec["minimum"]),
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    )
                    or math.isclose(
                        log_pi,
                        float(envelope_spec["maximum"]),
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    )
                )
                coefficient_boundary_details = []
                if pi_boundary:
                    coefficient_boundary_details.append({
                        "factor": "pi_a",
                        "boundary": "finite_envelope_limit",
                        "action": "expand or analytically bound the Pi_A envelope",
                    })
                if best["R_over_Va"] == 0.0:
                    coefficient_boundary_details.append({
                        "factor": "R_over_Va",
                        "boundary": "physical_lower",
                        "action": "confirm inward sensitivity at small positive R",
                    })
                elif best["R_over_Va"] == 1.0:
                    coefficient_boundary_details.append({
                        "factor": "R_over_Va",
                        "boundary": "physical_upper",
                        "action": "confirm inward sensitivity below uniform-rate R/Va=1",
                    })
                margin = best["_worst_normalized_margin"]
                item = {
                    "design": design,
                    "sticking_probability": sticking,
                    "source_power": power,
                    "both_tiers_pass_fixed_flux_gate": True,
                    "passing_coefficient_case_count": len(passing_candidates),
                    "interior_passing_coefficient_case_count": len(
                        interior_passing_candidates
                    ),
                    "selection_policy": "prefer a passing interior coefficient case; otherwise report the overall maximum",
                    "pi_a": best["pi_a"],
                    "R_over_Va": best["R_over_Va"],
                    "suppressed_rate_R": best["suppressed_rate_R"],
                    "tier_results": best["tier_results"],
                    "best_worst_normalized_margin": _json_ratio(margin),
                    "all_eight_streams_exceed_tier_kinematic_threshold": (
                        margin > 1.0
                    ),
                    "coefficient_boundary_limited": bool(
                        coefficient_boundary_details and margin > 0.1
                    ),
                    "coefficient_boundary_details": coefficient_boundary_details,
                    "near_threshold": bool(
                        margin <= 1.0 and margin >= near_fraction
                    ),
                }
            cross_summaries.append(item)
            if item["all_eight_streams_exceed_tier_kinematic_threshold"]:
                cross_qualified.append(item)
            if item["coefficient_boundary_limited"] or item["near_threshold"]:
                cross_inconclusive.append(item)
    return (
        summaries,
        qualified,
        inconclusive,
        cross_summaries,
        cross_qualified,
        cross_inconclusive,
    )


def _tier_design_summaries(records):
    grouped = defaultdict(list)
    for record in records:
        grouped[(
            record["public"]["geometry_tier"],
            record["public"]["design"],
        )].append(record["public"])
    summaries = []
    for geometry_tier in screen.GEOMETRY_TIERS:
        for sticking in screen.STICKING_LEVELS:
            for power in screen.SOURCE_POWER_LEVELS:
                design = screen.expected_design_name(sticking, power)
                rows = grouped[(geometry_tier, design)]
                decisions = [row["transport_sign"] for row in rows]
                flux_ratios = [
                    value
                    for decision in decisions
                    for value in decision["floor_to_lower_flux_ratios"]
                    if _number(value)
                ]
                coverage_margins = [
                    value
                    for decision in decisions
                    for value in decision["lower_minus_floor_coverage"]
                    if _number(value)
                ]
                velocity_ratios = [
                    value
                    for decision in decisions
                    for value in decision["floor_to_lower_velocity_ratios"]
                    if _number(value)
                ]
                upper_margins = [
                    value
                    for decision in decisions
                    for value in decision["floor_minus_middle_upper_velocity"]
                    if _number(value)
                ]
                summaries.append({
                    "geometry_tier": geometry_tier,
                    "design": design,
                    "sticking_probability": sticking,
                    "source_power": power,
                    "stream_count": len(rows),
                    "stream_pass_count": sum(
                        decision["pass"] for decision in decisions
                    ),
                    "all_four_streams_pass": bool(
                        len(rows) == 4
                        and all(decision["pass"] for decision in decisions)
                    ),
                    "worst_floor_to_lower_flux_ratio": (
                        max(flux_ratios) if flux_ratios else None
                    ),
                    "worst_lower_minus_floor_coverage": (
                        min(coverage_margins) if coverage_margins else None
                    ),
                    "worst_floor_to_lower_velocity_ratio": (
                        min(velocity_ratios) if velocity_ratios else None
                    ),
                    "worst_floor_minus_middle_upper_velocity": (
                        min(upper_margins) if upper_margins else None
                    ),
                })
    return summaries


def _cross_tier_design_summaries(tier_summaries):
    grouped = defaultdict(dict)
    for item in tier_summaries:
        grouped[item["design"]][item["geometry_tier"]] = item
    summaries = []
    for sticking in screen.STICKING_LEVELS:
        for power in screen.SOURCE_POWER_LEVELS:
            design = screen.expected_design_name(sticking, power)
            tiers = grouped[design]
            complete = set(tiers) == set(screen.GEOMETRY_TIERS)
            summaries.append({
                "design": design,
                "sticking_probability": sticking,
                "source_power": power,
                "tier_results": {
                    tier: {
                        "stream_count": tiers[tier]["stream_count"],
                        "stream_pass_count": tiers[tier]["stream_pass_count"],
                        "all_four_streams_pass": tiers[tier][
                            "all_four_streams_pass"
                        ],
                    }
                    for tier in screen.GEOMETRY_TIERS
                    if tier in tiers
                },
                "stream_count": sum(
                    item["stream_count"] for item in tiers.values()
                ),
                "stream_pass_count": sum(
                    item["stream_pass_count"] for item in tiers.values()
                ),
                "both_tiers_complete": complete,
                "all_eight_streams_pass": bool(
                    complete
                    and all(
                        tiers[tier]["all_four_streams_pass"]
                        for tier in screen.GEOMETRY_TIERS
                    )
                ),
            })
    return summaries


def _factor_boundary(item):
    boundaries = []
    if item["sticking_probability"] == min(screen.STICKING_LEVELS):
        boundaries.append({
            "factor": "sticking_probability",
            "boundary": "tested_lower",
            "action": "expand lower if the model accepts a smaller positive value",
        })
    if item["sticking_probability"] == max(screen.STICKING_LEVELS):
        boundaries.append({
            "factor": "sticking_probability",
            "boundary": "physical_upper",
            "action": "densify immediately below one and test perturbation robustness",
        })
    if item["source_power"] == min(screen.SOURCE_POWER_LEVELS):
        boundaries.append({
            "factor": "source_power",
            "boundary": "physical_lower",
            "action": "densify immediately above zero and test perturbation robustness",
        })
    if item["source_power"] == max(screen.SOURCE_POWER_LEVELS):
        boundaries.append({
            "factor": "source_power",
            "boundary": "tested_upper",
            "action": "expand the tested upper range",
        })
    return boundaries


def decision_from_evidence(
    designs,
    analytic_qualified,
    envelope_qualified=(),
    envelope_inconclusive=(),
    numerically_confirmed=False,
    matched_3d_confirmed=False,
):
    transport_passes = {
        item["design"]: item
        for item in designs
        if item["all_eight_streams_pass"]
    }
    coefficient_passes = [*analytic_qualified, *envelope_qualified]
    interior_coefficient_passes = [
        item
        for item in coefficient_passes
        if not item.get("coefficient_boundary_details")
    ]
    boundary_coefficient_passes = [
        item
        for item in coefficient_passes
        if item.get("coefficient_boundary_details")
    ]
    coefficient_pass_designs = {
        item["design"] for item in interior_coefficient_passes
    }
    coherent_designs = sorted(set(transport_passes) & coefficient_pass_designs)
    if not coefficient_pass_designs and boundary_coefficient_passes:
        boundary_designs = sorted({
            item["design"] for item in boundary_coefficient_passes
        })
        coherent_boundary_designs = sorted(
            set(transport_passes) & set(boundary_designs)
        )
        return {
            "classification": "coefficient_physical_boundary_refinement_required",
            "coherent_designs": coherent_boundary_designs,
            "boundary_warnings": [
                {
                    "design": item["design"],
                    "factors": item["coefficient_boundary_details"],
                }
                for item in boundary_coefficient_passes
            ],
            "reason": (
                "Kinematic clearance occurs only at a Pi_A or R/Va limiting "
                "control. Confirm inward coefficient sensitivity and both-tier "
                "robustness before treating it as qualified."
            ),
        }
    if not coefficient_pass_designs and envelope_inconclusive:
        return {
            "classification": "analytic_envelope_refinement_required",
            "coherent_designs": [],
            "boundary_warnings": [],
            "reason": (
                "No coefficient case clears H/a, but the broad analytic envelope "
                "is near-threshold or coefficient-boundary limited; refine it before pivoting."
            ),
        }
    if not coefficient_pass_designs:
        if not numerically_confirmed:
            return {
                "classification": "transport_no_go_requires_numerical_confirmation",
                "coherent_designs": [],
                "boundary_warnings": [],
                "post_confirmation_action": "pivot_model_family",
                "reason": (
                    "Both geometry tiers miss the required broad coefficient envelope "
                    "at grid 0.01, 1000 rays, and maxReflections 400. Confirm selected "
                    "worst misses at grid 0.005, 2000 rays, and maxReflections "
                    "400 versus 800 before pivoting the model family."
                ),
            }
        if not matched_3d_confirmed:
            return {
                "classification": "transport_no_go_requires_matched_3d_confirmation",
                "coherent_designs": [],
                "boundary_warnings": [],
                "post_confirmation_action": "pivot_model_family",
                "reason": (
                    "The two 2D tiers reproduce the no-go after numerical confirmation, "
                    "but matched 3D transport is still required before a model-family pivot."
                ),
            }
        return {
            "classification": "pivot_model_family",
            "coherent_designs": [],
            "boundary_warnings": [],
            "reason": (
                "Neither the required Pi_A/R grid nor the twelve-decade coefficient "
                "envelope makes the worst paired stream outrun the fastest wall by H/a."
            ),
        }
    if coherent_designs:
        boundary_warnings = [
            {
                "design": design,
                "factors": _factor_boundary(transport_passes[design]),
            }
            for design in coherent_designs
            if _factor_boundary(transport_passes[design])
        ]
        interior = [
            design
            for design in coherent_designs
            if not _factor_boundary(transport_passes[design])
        ]
        if not interior:
            boundary_kinds = {
                warning["boundary"]
                for item in boundary_warnings
                for warning in item["factors"]
            }
            classification = (
                "transport_sign_physical_boundary_refinement_required"
                if boundary_kinds <= {"physical_lower", "physical_upper"}
                else "transport_sign_boundary_resolution_required"
            )
            return {
                "classification": classification,
                "coherent_designs": coherent_designs,
                "boundary_warnings": boundary_warnings,
                "reason": (
                    "The same transport design clears measured sign and analytic H/a, "
                    "but every coherent design is on a tested sticking or source-power "
                    "boundary. Follow each boundary-specific expansion or inward "
                    "refinement action before morphology work; this is not an optimum."
                ),
            }
        if not numerically_confirmed:
            return {
                "classification": "transport_candidate_requires_numerical_confirmation",
                "coherent_designs": coherent_designs,
                "boundary_warnings": boundary_warnings,
                "reason": (
                    "An identical interior design clears both tiers on the coarse "
                    "screen. Recheck it at grid 0.005, 2000 rays, and maxReflections "
                    "400 versus 800 before morphology work."
                ),
            }
        if not matched_3d_confirmed:
            return {
                "classification": "transport_candidate_requires_matched_3d_confirmation",
                "coherent_designs": coherent_designs,
                "boundary_warnings": boundary_warnings,
                "reason": (
                    "The same interior design clears both numerically confirmed 2D tiers; "
                    "matched 3D transport must reproduce the sign and H/a result before "
                    "morphology work."
                ),
            }
        return {
            "classification": "transport_sign_and_kinematics_qualified",
            "coherent_designs": coherent_designs,
            "boundary_warnings": boundary_warnings,
            "reason": (
                "At least one identical interior transport design passes every measured "
                "sign guard and clears analytic H/a on all eight paired tier/stream cases."
            ),
        }
    return {
        "classification": "targeted_kinetic_confirmation_required",
        "coherent_designs": [],
        "boundary_warnings": [],
        "reason": (
            "A coefficient case is kinematically capable, but it does not belong to "
            "the same transport design as any four-stream measured sign pass."
        ),
    }


def build_summary(
    manifest,
    rows,
    parse_errors,
    rows_missing,
    fingerprint,
    project_root,
):
    audit = audit_attempts(
        manifest, rows, parse_errors, rows_missing, fingerprint
    )
    selected = audit.pop("selected_rows")
    summary = {
        **audit,
        "campaign": manifest.get("campaign"),
        "expected_runtime_fingerprint": fingerprint,
        "reviewer_sha256": _file_sha256(Path(__file__).resolve()),
        "metric_valid_case_count": 0,
        "snapshot_errors": [],
        "case_records": [],
        "tier_designs": [],
        "cross_tier_designs": [],
        "analytic_counterfactuals": [],
        "analytic_tier_kinematic_passes": [],
        "analytic_cross_tier_kinematic_passes": [],
        "analytic_envelope_tiers": [],
        "analytic_envelope_cross_tier": [],
        "analytic_envelope_cross_tier_kinematic_passes": [],
        "analytic_envelope_cross_tier_inconclusive": [],
        "analytic_envelope_exact_limits": None,
        "morphology_ranking": [],
        "ranking_policy": "none; this screen tests transport direction and kinematic capability only",
        "decision": {
            "classification": "insufficient_audited_evidence",
            "reason": "The exact current 168-case paired-tier audit gate has not cleared.",
        },
    }
    if audit["status"] != "complete":
        return summary

    reviewed = []
    errors = []
    for row in selected:
        record, case_errors = _review_case(row, project_root)
        if case_errors:
            errors.append({"case_id": row.get("case_id"), "reasons": case_errors})
        if record is not None:
            reviewed.append(record)
    summary["metric_valid_case_count"] = len(reviewed) - sum(
        bool(item["reasons"]) for item in errors
    )
    summary["snapshot_errors"] = errors
    if errors or len(reviewed) != 168:
        summary["status"] = "incomplete_or_invalid"
        summary["decision"] = {
            "classification": "insufficient_audited_evidence",
            "reason": "Snapshot, regional, structural, or analytic-parity errors block inference.",
        }
        return summary

    tier_designs = _tier_design_summaries(reviewed)
    cross_tier_designs = _cross_tier_design_summaries(tier_designs)
    analytic, tier_qualified, cross_tier_qualified = analytic_counterfactuals(
        reviewed, manifest
    )
    (
        envelope_tiers,
        envelope_tier_qualified,
        envelope_tier_inconclusive,
        envelope_cross_tier,
        envelope_cross_tier_qualified,
        envelope_cross_tier_inconclusive,
    ) = analytic_envelope(reviewed, manifest)
    exact_limits = analytic_pi_limits(reviewed, manifest)
    summary.update({
        "status": "complete",
        "metric_valid_case_count": 168,
        "case_records": [record["public"] for record in reviewed],
        "tier_designs": tier_designs,
        "cross_tier_designs": cross_tier_designs,
        "transport_pass_design_count": sum(
            item["all_eight_streams_pass"] for item in cross_tier_designs
        ),
        "analytic_counterfactuals": analytic,
        "analytic_tier_kinematic_passes": tier_qualified,
        "analytic_cross_tier_kinematic_passes": cross_tier_qualified,
        "analytic_envelope_tiers": envelope_tiers,
        "analytic_envelope_tier_kinematic_passes": envelope_tier_qualified,
        "analytic_envelope_tier_inconclusive": envelope_tier_inconclusive,
        "analytic_envelope_cross_tier": envelope_cross_tier,
        "analytic_envelope_cross_tier_kinematic_passes": envelope_cross_tier_qualified,
        "analytic_envelope_cross_tier_inconclusive": envelope_cross_tier_inconclusive,
        "analytic_envelope_exact_limits": exact_limits,
        "analytic_law_parity": {
            key: max(
                record["public"]["analytic_law_parity"][key]
                for record in reviewed
            )
            for key in (
                "coverage_max_abs_error",
                "velocity_max_abs_error",
                "adsorption_term_max_abs_error",
                "deactivation_term_max_abs_error",
                "analytic_relative_balance_error",
            )
        },
        "region_definitions": {
            "frozen_source": "review_copper_fill_regional_kinematics.region_statistics",
            "floor_and_walls": "unchanged frozen floor/lower/middle/upper cuts, with walls split at the via centerline",
            "mouth_shoulder": "the frozen near-via field cut, relabeled by its actual shoulder location",
            "field": "the far-field cut used by foundation_copper_fill_trajectory._model_diagnostics",
        },
        "decision": decision_from_evidence(
            cross_tier_designs,
            cross_tier_qualified,
            [
                *envelope_cross_tier_qualified,
                *exact_limits["cross_tier_kinematic_passes"],
            ],
            envelope_cross_tier_inconclusive,
            numerically_confirmed=False,
            matched_3d_confirmed=False,
        ),
    })
    return summary


def _fmt(value, digits=5):
    if value is None:
        return "—"
    return f"{value:.{digits}g}" if isinstance(value, (int, float)) else str(value)


def markdown(summary):
    lines = [
        "# Cu-fill transport-sign screen",
        "",
        f"Status: **{summary['status']}**. Current cases: "
        f"{summary['selected_current_case_count']}/{summary['expected_case_count']}; "
        f"metric-valid: {summary['metric_valid_case_count']}; current errors: "
        f"{len(summary['current_fingerprint_error_attempt_rows'])}.",
        "",
        "This is a one-checkpoint model-direction test. It does not rank morphology or process settings.",
        "",
    ]
    if summary["status"] != "complete":
        lines += [
            f"Decision: **{summary['decision']['classification']}** — "
            f"{summary['decision']['reason']}",
            "",
        ]
        return "\n".join(lines)
    lines += [
        "| Tier / sticking | Source power | Streams passed | Worst floor/lower flux | Coverage margin | Floor/lower velocity | Floor-minus-upper velocity |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary["tier_designs"]:
        lines.append(
            f"| {item['geometry_tier']} / {_fmt(item['sticking_probability'])} | "
            f"{_fmt(item['source_power'])} | "
            f"{item['stream_pass_count']}/4 | "
            f"{_fmt(item['worst_floor_to_lower_flux_ratio'])} | "
            f"{_fmt(item['worst_lower_minus_floor_coverage'])} | "
            f"{_fmt(item['worst_floor_to_lower_velocity_ratio'])} | "
            f"{_fmt(item['worst_floor_minus_middle_upper_velocity'])} |"
        )
    lines += [
        "",
        f"Required Pi_A/R cases clearing both tiers on all eight streams: "
        f"{len(summary['analytic_cross_tier_kinematic_passes'])}. Broad-envelope "
        f"cross-tier passes: "
        f"{len(summary['analytic_envelope_cross_tier_kinematic_passes'])}.",
        "",
        f"Decision: **{summary['decision']['classification']}** — "
        f"{summary['decision']['reason']}",
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
    fingerprint = runtime_fingerprint(manifest, args.project_root)
    summary = build_summary(
        manifest,
        rows,
        parse_errors,
        rows_missing,
        fingerprint,
        args.project_root,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    args.markdown.write_text(markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "selected": summary["selected_current_case_count"],
        "metric_valid": summary["metric_valid_case_count"],
        "decision": summary["decision"]["classification"],
    }))


if __name__ == "__main__":
    main()

"""Independent audit of the Cu transport numerical/boundary confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

import foundation_copper_fill_transport_confirmation as campaign
import foundation_metric_audit as foundation
import foundation_copper_fill_transport_sign_screen as coarse_screen
import review_copper_fill_access_surface as access
import review_copper_fill_transport_sign_screen as coarse_review
import foundation_copper_fill_trajectory as trajectory


DEFAULT_MANIFEST = campaign.DEFAULT_MANIFEST
DEFAULT_ROWS = campaign.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_confirmation_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_confirmation_review.md"
)

TERMS = (
    ("grid_refinement",),
    ("ray_refinement",),
    ("reflection_refinement",),
    ("grid_refinement", "ray_refinement"),
    ("grid_refinement", "reflection_refinement"),
    ("ray_refinement", "reflection_refinement"),
    ("grid_refinement", "ray_refinement", "reflection_refinement"),
)
INTERACTION_TERMS = TERMS[3:]
RESPONSES = {
    "worst_floor_to_each_lower_flux_ratio": False,
    "minimum_lower_minus_floor_coverage": True,
    "worst_floor_to_each_lower_velocity_ratio": True,
    "minimum_floor_minus_middle_upper_velocity": True,
}
CLASS_SCORE = {"invalid": -1.0, "no_go": 0.0, "near_threshold": 1.0, "pass": 2.0}


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
            root / "foundation_copper_fill_transport_confirmation.py"
        ),
        "coarse_runner_sha256": _file_sha256(
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


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _json_number(value):
    if value is None:
        return None
    if value == math.inf:
        return "infinite"
    if value == -math.inf:
        return "negative_infinite"
    return float(value) if _number(value) else "invalid_nonfinite"


def _logical_key(row):
    return campaign._cell_key(row)


def _case_payload(row):
    return {field: row.get(field) for field in campaign.CASE_FIELDS}


def validate_attempt(row, expected, manifest, fingerprint):
    errors = []
    if row.get("case_id") != expected["case_id"]:
        errors.append("case_id differs from the frozen logical cell")
    if row.get("case_id") != foundation.case_id(_case_payload(row)):
        errors.append("case_id differs from the row's own case payload")
    for field in campaign.CASE_FIELDS:
        if row.get(field) != expected.get(field):
            errors.append(f"case field differs from manifest: {field}")
    if row.get("runtime_fingerprint") != fingerprint:
        errors.append("runtime fingerprint differs from the reviewed files")
    if row.get("production_doe_eligible") is not False:
        errors.append("production_doe_eligible is not explicitly false")
    if row.get("morphology_ranking_eligible") is not False:
        errors.append("morphology_ranking_eligible is not explicitly false")
    origin = row.get("evidence_origin", {})
    expected_mode = (
        "verified_parent_reuse"
        if campaign.is_parent_reuse_case(expected, manifest)
        else "executed_confirmation"
    )
    if origin.get("mode") != expected_mode:
        errors.append(f"evidence origin must be {expected_mode}")
    if expected_mode == "verified_parent_reuse":
        reuse_item = next(
            item
            for item in manifest["parent_reuse"]["rows"]
            if (item["geometry_tier"], item["rng_seed"])
            == campaign._reuse_key(expected)
        )
        if origin != {
            "mode": "verified_parent_reuse",
            "parent_case_id": reuse_item["parent_case_id"],
            "parent_row_canonical_sha256": reuse_item[
                "parent_row_canonical_sha256"
            ],
            "parent_rows_sha256": manifest["parent_reuse"][
                "source_rows_sha256"
            ],
            "parent_snapshot_sha256": reuse_item["snapshot_sha256"],
        }:
            errors.append("parent reuse pointer differs from the frozen reuse map")
    else:
        residual = origin.get("reflection_residual_upper_bound")
        if not _number(residual) or not math.isclose(
            float(residual),
            float(expected["reflection_residual_upper_bound"]),
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            errors.append("executed row reflection residual differs from its cell")
    return errors


def audit_attempts(manifest, rows, parse_errors, rows_missing, fingerprint):
    """Select one current success per cell while preserving recoverable retries."""
    cases = campaign.expand_cases(manifest, fingerprint)
    manifest_errors = campaign.validate_manifest(manifest, cases)
    expected = {_logical_key(case): case for case in cases}
    attempts = defaultdict(list)
    invalid_attempts = []
    unexpected = []
    positions = {id(row): index for index, row in enumerate(rows)}
    for row in rows:
        case = expected.get(_logical_key(row))
        if case is None:
            unexpected.append(row)
            continue
        attempts[_logical_key(row)].append(row)
        errors = validate_attempt(row, case, manifest, fingerprint)
        if errors:
            invalid_attempts.append({"reasons": errors, "row": row})

    selected = []
    missing = []
    duplicate_successes = []
    resolved_errors = []
    unresolved_errors = []
    for case in cases:
        cell_attempts = attempts[_logical_key(case)]
        valid_attempts = [
            row
            for row in cell_attempts
            if not validate_attempt(row, case, manifest, fingerprint)
        ]
        successes = [row for row in valid_attempts if row.get("ok") is True]
        errors = [row for row in valid_attempts if row.get("ok") is not True]
        if len(successes) > 1:
            duplicate_successes.append(case["case_id"])
        if not successes:
            missing.append({
                "case_id": case["case_id"],
                "design": case["design"],
                "geometry_tier": case["geometry_tier"],
                "grid_delta": case["numerics"]["grid_delta"],
                "rays_per_point": case["numerics"]["rays_per_point"],
                "max_reflections": case["numerics"]["max_reflections"],
                "rng_seed": case["rng_seed"],
            })
        else:
            latest_success = max(successes, key=lambda row: positions[id(row)])
            selected.append(latest_success)
            for row in errors:
                if positions[id(row)] < positions[id(latest_success)]:
                    resolved_errors.append(row)
                else:
                    unresolved_errors.append(row)

    invalid = bool(
        manifest_errors
        or parse_errors
        or invalid_attempts
        or unexpected
        or duplicate_successes
        or unresolved_errors
    )
    complete = bool(
        not rows_missing and not invalid and len(selected) == 128 and not missing
    )
    return {
        "status": (
            "complete"
            if complete
            else "missing_rows"
            if rows_missing
            else "incomplete_or_invalid"
        ),
        "expected_case_count": 128,
        "expected_parent_reuse_count": 8,
        "expected_new_execution_count": 120,
        "attempt_count": len(rows),
        "selected_current_case_count": len(selected),
        "manifest_validation_errors": manifest_errors,
        "parse_errors": parse_errors,
        "rows_missing": rows_missing,
        "invalid_attempts": invalid_attempts,
        "unexpected_attempt_rows": unexpected,
        "resolved_current_error_attempt_rows": resolved_errors,
        "current_error_attempt_rows": unresolved_errors,
        "duplicate_success_case_ids": sorted(duplicate_successes),
        "missing_cases": missing,
        "selected_rows": selected,
    }


def _hydrate_evidence(row, parents, manifest):
    origin = row["evidence_origin"]
    if origin["mode"] == "executed_confirmation":
        return row, []
    parent = parents.get(campaign._reuse_key(row))
    if parent is None:
        return None, ["verified parent row is unavailable"]
    reuse_item = next(
        item
        for item in manifest["parent_reuse"]["rows"]
        if (item["geometry_tier"], item["rng_seed"])
        == campaign._reuse_key(row)
    )
    errors = []
    if parent.get("case_id") != origin.get("parent_case_id"):
        errors.append("parent row case_id differs from reuse pointer")
    if campaign._canonical_row_sha256(parent) != reuse_item[
        "parent_row_canonical_sha256"
    ]:
        errors.append("parent row canonical hash differs during hydration")
    return parent, errors


def _response_values(transport_sign):
    def finite(values, operation):
        selected = [float(value) for value in values if _number(value)]
        return operation(selected) if selected else None

    return {
        "worst_floor_to_each_lower_flux_ratio": finite(
            transport_sign["floor_to_lower_flux_ratios"], max
        ),
        "minimum_lower_minus_floor_coverage": finite(
            transport_sign["lower_minus_floor_coverage"], min
        ),
        "worst_floor_to_each_lower_velocity_ratio": finite(
            transport_sign["floor_to_lower_velocity_ratios"], min
        ),
        "minimum_floor_minus_middle_upper_velocity": finite(
            transport_sign["floor_minus_middle_upper_velocity"], min
        ),
    }


def _current_code_parent_compatibility(evidence, project_root):
    """Recheck parent evidence with the current topology code."""
    errors = []
    checkpoint = evidence["trajectory"][0]
    snapshot = Path(evidence["diagnostic_snapshot_path"])
    if not snapshot.is_absolute():
        snapshot = Path(project_root) / snapshot
    try:
        with np.load(snapshot, allow_pickle=False) as saved:
            current_mesh = {
                "nodes": np.asarray(saved["nodes"], dtype=float),
                "lines": np.asarray(saved["lines"], dtype=int),
            }
    except Exception as error:
        return None, [f"cannot load parent morphology for current-code review: {error}"]

    geometry = trajectory._build_seeded_stack(evidence)
    trajectory._validate_material_stack(geometry)
    current_reference = trajectory._reference_geometry(geometry, evidence)
    previous_meshes = trajectory.tm.raw_level_set_meshes(geometry)
    previous_mesh = previous_meshes[-1]
    saved_reference = evidence["reference"]
    try:
        topology = trajectory._fill_topology_metrics_2d(
            current_mesh,
            field_y=saved_reference["field_y"],
            floor_y=saved_reference["floor_y"],
            via_x_bounds=saved_reference["via_x_bounds"],
            field_sample_xs=saved_reference["field_sample_xs"],
            center_x=0.0,
            tolerance=0.1 * evidence["numerics"]["grid_delta"],
            initial_cavity_area=saved_reference["initial_cavity_area"],
            grid_delta=evidence["numerics"]["grid_delta"],
            mouth_sample_y=saved_reference["mouth_sample_y"],
            area_sample_count=saved_reference["metric_sampling"][
                "area_sample_count"
            ],
            overburden_sample_count=saved_reference["metric_sampling"][
                "overburden_sample_count"
            ],
        )
        invariants = trajectory._validate_case_invariants(evidence)
        transition = trajectory._topology_transition_check(
            current_reference["initial_topology"],
            topology,
            invariants,
            evidence["numerics"]["grid_delta"],
            previous_mesh=previous_mesh,
            reference=current_reference,
        )
        pristine_protected = trajectory._protected_stack_delta(
            current_reference["protected_meshes"], previous_meshes[:-1]
        )
    except Exception as error:
        return None, [f"current-code parent morphology review failed: {error}"]

    topology = foundation.jsonable(topology)
    transition = foundation.jsonable(transition)
    pristine_protected = foundation.jsonable(pristine_protected)
    if not coarse_review._structures_close(
        topology, checkpoint.get("topology")
    ):
        errors.append("current topology metrics differ from saved parent evidence")
    if not coarse_review._structures_close(
        transition, checkpoint.get("topology_transition")
    ):
        errors.append("current transition classification differs from saved parent evidence")
    if not coarse_review._structures_close(
        pristine_protected, checkpoint.get("protected_stack")
    ):
        errors.append("current protected-stack semantics differ from saved parent evidence")

    diagnostics = checkpoint.get("model_diagnostics", {})
    if diagnostics.get("nonplating_velocity_max_abs") is None or float(
        diagnostics["nonplating_velocity_max_abs"]
    ) > 1e-12:
        errors.append("parent raw field does not preserve zero non-plating velocity")
    current_reference_public = {
        key: value
        for key, value in current_reference.items()
        if key != "protected_meshes"
    }
    if not coarse_review._structures_close(
        foundation.jsonable(current_reference_public), saved_reference
    ):
        errors.append("current exact-stack reference differs from the parent reference")
    return {
        "parent_traveler_metrics_sha256": evidence["runtime_fingerprint"][
            "traveler_metrics_sha256"
        ],
        "current_traveler_metrics_sha256": _file_sha256(
            Path(project_root) / "traveler_metrics.py"
        ),
        "regional_and_parity_re_review": "passed by current coarse reviewer",
        "topology_matches": coarse_review._structures_close(
            topology, checkpoint.get("topology")
        ),
        "transition_matches": coarse_review._structures_close(
            transition, checkpoint.get("topology_transition")
        ),
        "protected_stack_matches": coarse_review._structures_close(
            pristine_protected, checkpoint.get("protected_stack")
        ),
        "nonplating_velocity_max_abs": diagnostics.get(
            "nonplating_velocity_max_abs"
        ),
        "compatible": not errors,
    }, errors


def review_case(row, parents, manifest, project_root):
    evidence, errors = _hydrate_evidence(row, parents, manifest)
    if evidence is None:
        return None, errors
    record, coarse_errors = coarse_review._review_case(evidence, project_root)
    errors.extend(coarse_errors)
    if record is None:
        return None, errors
    public = record["public"]
    compatibility = None
    if row["evidence_origin"]["mode"] == "verified_parent_reuse":
        compatibility, compatibility_errors = _current_code_parent_compatibility(
            evidence, project_root
        )
        errors.extend(compatibility_errors)
    public.update({
        "case_id": row["case_id"],
        "design": row["design"],
        "geometry_tier": row["geometry_tier"],
        "rng_seed": row["rng_seed"],
        "grid_delta": row["numerics"]["grid_delta"],
        "rays_per_point": row["numerics"]["rays_per_point"],
        "max_reflections": row["numerics"]["max_reflections"],
        "reflection_residual_upper_bound": row[
            "reflection_residual_upper_bound"
        ],
        "evidence_origin": row["evidence_origin"]["mode"],
        "responses": _response_values(public["transport_sign"]),
        "parent_current_code_compatibility": compatibility,
    })
    reviewed_snapshot = Path(public["diagnostic_snapshot_path"]).resolve()
    declared_snapshot = Path(row["diagnostic_snapshot_path"])
    if not declared_snapshot.is_absolute():
        declared_snapshot = Path(project_root) / declared_snapshot
    if reviewed_snapshot != declared_snapshot.resolve():
        errors.append("reviewed snapshot path differs from confirmation row")
    return record, errors


def _adverse_summary(values, higher_is_better):
    values = np.asarray([value for value in values if _number(value)], dtype=float)
    if not len(values):
        return {
            "count": 0,
            "mean": None,
            "adverse_p90": None,
            "worst": None,
            "higher_is_better": higher_is_better,
        }
    return {
        "count": int(len(values)),
        "mean": float(np.mean(values)),
        "adverse_p90": float(np.quantile(values, 0.1 if higher_is_better else 0.9)),
        "worst": float(np.min(values) if higher_is_better else np.max(values)),
        "higher_is_better": higher_is_better,
    }


def _broad_analytic_envelope(records, analysis):
    """Audit the broad finite envelope and exact Pi_A endpoint limits."""
    thresholds = [
        float(record["public"]["kinematic_threshold_H_over_a"])
        for record in records
    ]
    fixed_flux_pass = bool(
        len(records) == 8
        and all(
            record["public"]["transport_sign"]["conditions"][
                "floor_to_each_lower_flux_ratio_strictly_below_0p95"
            ]
            for record in records
        )
    )
    result = {
        "fixed_flux_gate_all_eight": fixed_flux_pass,
        "eligible_coefficient_case_count": 0,
        "interior_passing_case_count": 0,
        "best_finite": None,
        "exact_pi_a_zero": None,
        "exact_pi_a_infinity": None,
        "best_worst_normalized_margin": None,
        "analytic_h_over_a_pass": False,
        "coefficient_boundary_limited": False,
        "near_threshold": False,
    }
    if not fixed_flux_pass:
        return result

    spec = analysis["analytic_envelope_log10_pi_a"]
    pi_values = np.logspace(
        float(spec["minimum"]), float(spec["maximum"]), int(spec["count"])
    )
    r_fractions = analysis["analytic_envelope_R_over_Va"]
    active_rate = float(records[0]["internal"]["model"]["active_deposition_rate"])
    candidates = []
    for pi_a in pi_values:
        for r_fraction in r_fractions:
            ratios = [
                coarse_review._analytic_ratio(
                    record, float(pi_a), float(r_fraction) * active_rate
                )
                for record in records
            ]
            if len(ratios) != 8 or not all(
                _number(ratio) or ratio == math.inf for ratio in ratios
            ):
                continue
            margin = min(
                ratio / threshold
                for ratio, threshold in zip(ratios, thresholds)
            )
            log_pi = math.log10(float(pi_a))
            boundary = bool(
                r_fraction in {0.0, 1.0}
                or math.isclose(log_pi, float(spec["minimum"]), abs_tol=1e-12)
                or math.isclose(log_pi, float(spec["maximum"]), abs_tol=1e-12)
            )
            candidates.append({
                "pi_a": float(pi_a),
                "R_over_Va": float(r_fraction),
                "worst_normalized_margin": float(margin),
                "coefficient_boundary": boundary,
            })
    result["eligible_coefficient_case_count"] = len(candidates)
    interior_passing = [
        item
        for item in candidates
        if item["worst_normalized_margin"] > 1.0
        and not item["coefficient_boundary"]
    ]
    result["interior_passing_case_count"] = len(interior_passing)
    best_finite = max(
        interior_passing or candidates,
        key=lambda item: item["worst_normalized_margin"],
        default=None,
    )
    result["best_finite"] = (
        {
            **best_finite,
            "worst_normalized_margin": _json_number(
                best_finite["worst_normalized_margin"]
            ),
        }
        if best_finite
        else None
    )

    zero_ratios = [
        coarse_review._analytic_ratio(record, 0.0, 0.01)
        for record in records
    ]
    zero_margin = (
        min(
            ratio / threshold
            for ratio, threshold in zip(zero_ratios, thresholds)
        )
        if len(zero_ratios) == 8
        and all(_number(ratio) or ratio == math.inf for ratio in zero_ratios)
        else None
    )
    result["exact_pi_a_zero"] = {
        "worst_normalized_margin": _json_number(zero_margin),
        "all_eight_pass": bool(zero_margin is not None and zero_margin > 1.0),
    }

    infinity_candidates = []
    zero_flux_points = 0
    for r_fraction in r_fractions:
        ratios = []
        for record in records:
            internal = record["internal"]
            raw = internal["raw"]
            plating = np.isin(
                raw["material_ids"],
                np.asarray(internal["plating_material_ids"], dtype=float),
            )
            required = np.logical_or.reduce([
                internal["masks"][name] for name in coarse_screen.REGION_NAMES
            ])
            if r_fraction == r_fractions[0]:
                zero_flux_points += int(np.count_nonzero(
                    required & plating & (raw["suppressor_flux"] <= 0.0)
                ))
            velocity = np.zeros_like(raw["suppressor_flux"], dtype=float)
            positive = raw["suppressor_flux"] > 0.0
            velocity[plating & positive] = float(r_fraction) * active_rate
            velocity[plating & ~positive] = active_rate
            ratios.append(coarse_review._velocity_ratio(record, velocity))
        if len(ratios) == 8 and all(
            _number(ratio) or ratio == math.inf for ratio in ratios
        ):
            infinity_candidates.append({
                "R_over_Va": float(r_fraction),
                "worst_normalized_margin": min(
                    ratio / threshold
                    for ratio, threshold in zip(ratios, thresholds)
                ),
            })
    best_infinity = max(
        infinity_candidates,
        key=lambda item: item["worst_normalized_margin"],
        default=None,
    )
    result["exact_pi_a_infinity"] = {
        "required_region_zero_flux_point_count": zero_flux_points,
        "best_R_over_Va": best_infinity["R_over_Va"] if best_infinity else None,
        "best_worst_normalized_margin": (
            _json_number(best_infinity["worst_normalized_margin"])
            if best_infinity
            else None
        ),
        "all_eight_pass": bool(
            best_infinity
            and best_infinity["worst_normalized_margin"] > 1.0
        ),
    }

    margins = [
        item["worst_normalized_margin"]
        for item in candidates
    ]
    if zero_margin is not None:
        margins.append(float(zero_margin))
    if best_infinity:
        margins.append(float(best_infinity["worst_normalized_margin"]))
    best_margin = max(margins) if margins else None
    result["best_worst_normalized_margin"] = _json_number(best_margin)
    result["analytic_h_over_a_pass"] = bool(interior_passing)
    result["coefficient_boundary_limited"] = bool(
        not interior_passing
        and (
            (best_finite and best_finite["worst_normalized_margin"] > 1.0)
            or (zero_margin is not None and zero_margin > 1.0)
            or (
                best_infinity
                and best_infinity["worst_normalized_margin"] > 1.0
            )
        )
    )
    near_fraction = float(analysis["analytic_envelope_near_threshold_fraction"])
    result["near_threshold"] = bool(
        best_margin is not None
        and best_margin <= 1.0
        and best_margin >= near_fraction
    )
    return result


def numerical_cell_summaries(records, manifest):
    grouped = defaultdict(list)
    for record in records:
        public = record["public"]
        grouped[(
            public["design"],
            public["grid_delta"],
            public["rays_per_point"],
            public["max_reflections"],
        )].append(record)
    summaries = []
    for design in campaign.DESIGN_NAMES:
        for grid in campaign.GRID_LEVELS:
            for rays in campaign.RAY_LEVELS:
                for reflections in campaign.REFLECTION_LEVELS:
                    cell_records = grouped[(design, grid, rays, reflections)]
                    decisions = [
                        record["public"]["transport_sign"]
                        for record in cell_records
                    ]
                    response_summaries = {
                        response: _adverse_summary(
                            [
                                record["public"]["responses"][response]
                                for record in cell_records
                            ],
                            higher_is_better,
                        )
                        for response, higher_is_better in RESPONSES.items()
                    }
                    envelope = _broad_analytic_envelope(
                        cell_records, manifest["analysis"]
                    )
                    all_eight_sign = bool(
                        len(decisions) == 8 and all(item["pass"] for item in decisions)
                    )
                    structural = {
                        name: sum(record["public"][name] for record in cell_records)
                        for name in (
                            "topology_valid",
                            "topology_transition_valid",
                            "protected_stack_survives",
                            "diagnostic_balance_valid",
                        )
                    }
                    parity_max = max(
                        (
                            max(record["public"]["analytic_law_parity"].values())
                            for record in cell_records
                        ),
                        default=None,
                    )
                    valid = bool(
                        len(cell_records) == 8
                        and all(value == 8 for value in structural.values())
                        and _number(parity_max)
                        and parity_max <= float(
                            manifest["analysis"]["analytic_parity_abs_tolerance"]
                        )
                    )
                    combined_pass = bool(
                        valid and all_eight_sign and envelope["analytic_h_over_a_pass"]
                    )
                    classification = (
                        "invalid"
                        if not valid
                        else "pass"
                        if combined_pass
                        else "near_threshold"
                        if all_eight_sign and envelope["near_threshold"]
                        else "no_go"
                    )
                    tier_flux = {}
                    for tier in campaign.GEOMETRY_TIERS:
                        values = [
                            record["public"]["responses"][
                                "worst_floor_to_each_lower_flux_ratio"
                            ]
                            for record in cell_records
                            if record["public"]["geometry_tier"] == tier
                        ]
                        tier_flux[tier] = _adverse_summary(values, False)
                    summaries.append({
                        "design": design,
                        "grid_delta": grid,
                        "rays_per_point": rays,
                        "max_reflections": reflections,
                        "stream_count": len(cell_records),
                        "transport_sign_pass_count": sum(
                            item["pass"] for item in decisions
                        ),
                        "all_eight_transport_sign_pass": all_eight_sign,
                        "response_summaries": response_summaries,
                        "tier_flux_response": tier_flux,
                        "structural_guard_pass_counts": structural,
                        "analytic_parity_max_abs_error": parity_max,
                        "broad_analytic_envelope": envelope,
                        "combined_2d_pass": combined_pass,
                        "classification": classification,
                        "high_fidelity": bool(
                            grid == campaign.HIGH_FIDELITY_CELL["grid_delta"]
                            and rays == campaign.HIGH_FIDELITY_CELL[
                                "rays_per_point"
                            ]
                            and reflections == campaign.HIGH_FIDELITY_CELL[
                                "max_reflections"
                            ]
                        ),
                    })
    return summaries


def _factor_sign(public, factor):
    if factor == "grid_refinement":
        return 1.0 if public["grid_delta"] == 0.005 else -1.0
    if factor == "ray_refinement":
        return 1.0 if public["rays_per_point"] == 2000 else -1.0
    if factor == "reflection_refinement":
        return 1.0 if public["max_reflections"] == 800 else -1.0
    raise KeyError(factor)


def paired_factorial_effects(records):
    grouped = defaultdict(list)
    for record in records:
        public = record["public"]
        grouped[(
            public["design"], public["geometry_tier"], public["rng_seed"]
        )].append(public)
    effects = []
    for design in campaign.DESIGN_NAMES:
        strata = [
            rows for (name, _, _), rows in grouped.items() if name == design
        ]
        for response, higher_is_better in RESPONSES.items():
            for term in TERMS:
                contrasts = []
                for rows in strata:
                    if len(rows) != 8:
                        continue
                    values = [row["responses"][response] for row in rows]
                    if not all(_number(value) for value in values):
                        continue
                    contrasts.append(sum(
                        float(row["responses"][response])
                        * math.prod(_factor_sign(row, factor) for factor in term)
                        for row in rows
                    ) / 4.0)
                absolute = np.abs(np.asarray(contrasts, dtype=float))
                effects.append({
                    "design": design,
                    "response": response,
                    "higher_is_better": higher_is_better,
                    "term": ":".join(term),
                    "order": len(term),
                    "paired_stratum_count": len(contrasts),
                    "mean_signed_effect": (
                        float(np.mean(contrasts)) if contrasts else None
                    ),
                    "p90_absolute_effect": (
                        float(np.quantile(absolute, 0.9)) if len(absolute) else None
                    ),
                    "worst_absolute_effect": (
                        float(np.max(absolute)) if len(absolute) else None
                    ),
                    "minimum_signed_effect": min(contrasts) if contrasts else None,
                    "maximum_signed_effect": max(contrasts) if contrasts else None,
                })
    return effects


def class_changing_interactions(cell_summaries):
    by_design = defaultdict(list)
    for item in cell_summaries:
        by_design[item["design"]].append(item)
    findings = []
    for design, cells in by_design.items():
        for term in INTERACTION_TERMS:
            contrast = sum(
                CLASS_SCORE[cell["classification"]]
                * math.prod(_factor_sign(cell, factor) for factor in term)
                for cell in cells
            ) / 4.0
            if not math.isclose(contrast, 0.0, rel_tol=0.0, abs_tol=1e-12):
                findings.append({
                    "design": design,
                    "term": ":".join(term),
                    "class_score_contrast": float(contrast),
                    "cell_classes": [
                        {
                            "grid_delta": cell["grid_delta"],
                            "rays_per_point": cell["rays_per_point"],
                            "max_reflections": cell["max_reflections"],
                            "classification": cell["classification"],
                        }
                        for cell in cells
                    ],
                })
    return findings


def _high_fidelity(cell_summaries, design):
    matches = [
        item
        for item in cell_summaries
        if item["design"] == design and item["high_fidelity"]
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one high-fidelity cell for {design}")
    return matches[0]


def numerical_artifacts(cell_summaries):
    findings = []
    for design in campaign.DESIGN_NAMES:
        high = _high_fidelity(cell_summaries, design)
        for cell in cell_summaries:
            if cell["design"] != design or cell["high_fidelity"]:
                continue
            if cell["combined_2d_pass"] and not high["combined_2d_pass"]:
                findings.append({
                    "classification": "artifact_pending_high_fidelity_reproduction",
                    "design": design,
                    "grid_delta": cell["grid_delta"],
                    "rays_per_point": cell["rays_per_point"],
                    "max_reflections": cell["max_reflections"],
                })
    design = "stick_0p0125_power_0p0"
    grouped = defaultdict(dict)
    for cell in cell_summaries:
        if cell["design"] == design:
            grouped[(cell["grid_delta"], cell["rays_per_point"])][
                cell["max_reflections"]
            ] = cell
    for (grid, rays), arms in grouped.items():
        if (
            arms[400]["combined_2d_pass"]
            and not arms[800]["combined_2d_pass"]
        ):
            findings.append({
                "classification": "reflection_truncation_artifact",
                "design": design,
                "grid_delta": grid,
                "rays_per_point": rays,
                "passing_max_reflections": 400,
                "failing_max_reflections": 800,
            })
    return findings


def boundary_expansion_evidence(cell_summaries, effects):
    design_a = _high_fidelity(cell_summaries, campaign.DESIGN_NAMES[0])
    design_b = _high_fidelity(cell_summaries, campaign.DESIGN_NAMES[1])
    response = "worst_floor_to_each_lower_flux_ratio"
    a_worst = design_a["response_summaries"][response]["worst"]
    b_worst = design_b["response_summaries"][response]["worst"]
    improvement = (
        float(a_worst) - float(b_worst)
        if _number(a_worst) and _number(b_worst)
        else None
    )
    effect_values = [
        item["worst_absolute_effect"]
        for item in effects
        if item["response"] == response
        and _number(item["worst_absolute_effect"])
    ]
    largest_numerical = max(effect_values, default=None)
    tiers_improve = bool(all(
        _number(design_a["tier_flux_response"][tier]["worst"])
        and _number(design_b["tier_flux_response"][tier]["worst"])
        and design_b["tier_flux_response"][tier]["worst"]
        < design_a["tier_flux_response"][tier]["worst"]
        for tier in campaign.GEOMETRY_TIERS
    ))
    exceeds_numerics = bool(
        improvement is not None
        and largest_numerical is not None
        and improvement > largest_numerical + 1e-12
    )
    triggered = bool(
        design_b["combined_2d_pass"] or (tiers_improve and exceeds_numerics)
    )
    return {
        "primary_response": response,
        "design_A_high_fidelity_worst": a_worst,
        "design_B_high_fidelity_worst": b_worst,
        "B_improvement_over_A": improvement,
        "largest_absolute_paired_numerical_effect_or_interaction": largest_numerical,
        "B_improves_in_both_tiers": tiers_improve,
        "B_improvement_strictly_exceeds_numerical_effect": exceeds_numerics,
        "design_B_high_fidelity_pass": design_b["combined_2d_pass"],
        "triggered": triggered,
    }


def decision_from_evidence(
    cell_summaries,
    effects,
    interactions,
    artifacts,
    conditional_design,
):
    high_a = _high_fidelity(cell_summaries, campaign.DESIGN_NAMES[0])
    high_b = _high_fidelity(cell_summaries, campaign.DESIGN_NAMES[1])
    boundary = boundary_expansion_evidence(cell_summaries, effects)
    base = {
        "morphology_authorized": False,
        "model_family_pivot_authorized": False,
        "matched_3d_required": True,
        "high_fidelity_cells": {
            campaign.DESIGN_NAMES[0]: high_a["classification"],
            campaign.DESIGN_NAMES[1]: high_b["classification"],
        },
        "boundary_expansion_evidence": boundary,
    }
    if interactions:
        return {
            **base,
            "classification": "numerical_interaction_inconclusive_refine",
            "reason": (
                "At least one grid/ray/reflection interaction changes the discrete "
                "evidence class. Resolve that interaction before a 2D model conclusion."
            ),
        }
    if high_b["combined_2d_pass"] or boundary["triggered"]:
        return {
            **base,
            "classification": "lower_sticking_boundary_expansion_required",
            "conditional_next_design": conditional_design,
            "automatic_launch_authorized": False,
            "reason": (
                "The lower-sticking design is a boundary result whose improvement "
                "exceeds the largest paired numerical effect, or it passes at the "
                "high-fidelity cell. Confirm s=0.00625 at 1600/3200 reflections; "
                "do not launch it automatically."
            ),
        }
    if high_a["combined_2d_pass"]:
        return {
            **base,
            "classification": "transport_candidate_requires_matched_3d_confirmation",
            "candidate_design": campaign.DESIGN_NAMES[0],
            "reason": (
                "Design A passes the authoritative 2D cell on all eight streams and "
                "through the interior analytic H/a envelope. Matched 3D transport "
                "must reproduce it before morphology."
            ),
        }
    if any(
        cell["classification"] == "near_threshold"
        for cell in (high_a, high_b)
    ):
        return {
            **base,
            "classification": "analytic_near_threshold_refinement_required",
            "reason": (
                "An authoritative 2D cell reaches at least 0.8 H/a but not H/a. "
                "Refine the responsible numerical/coefficient region before 3D."
            ),
        }
    boundary_limited = any(
        cell["broad_analytic_envelope"]["coefficient_boundary_limited"]
        for cell in (high_a, high_b)
    )
    if boundary_limited:
        return {
            **base,
            "classification": "analytic_coefficient_boundary_refinement_required",
            "reason": (
                "Clearance appears only at an analytic coefficient limit. Confirm "
                "inward sensitivity before interpreting the 2D result."
            ),
        }
    reflection_artifact = any(
        item["classification"] == "reflection_truncation_artifact"
        for item in artifacts
    )
    return {
        **base,
        "classification": "transport_no_go_requires_matched_3d_confirmation",
        "reflection_truncation_artifact_observed": reflection_artifact,
        "reason": (
            "Neither design passes the authoritative 0.005/2000/800 2D cell. "
            "Any coarser pass remains an artifact. Matched 3D transport is still "
            "required before pivoting the model family."
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
        "verified_parent_reuse_count": 0,
        "reviewed_new_execution_count": 0,
        "metric_valid_case_count": 0,
        "snapshot_or_metric_errors": [],
        "numerical_cells": [],
        "paired_factorial_effects": [],
        "class_changing_interactions": [],
        "numerical_artifacts": [],
        "morphology_ranking": [],
        "ranking_policy": "none; this experiment qualifies transport numerics and one lower-sticking boundary",
        "decision": {
            "classification": "insufficient_audited_evidence",
            "morphology_authorized": False,
            "model_family_pivot_authorized": False,
            "reason": "The exact 128-cell artifact and provenance audit has not cleared.",
        },
    }
    if audit["status"] != "complete":
        return summary

    parents, parent_errors = campaign.load_verified_parent_rows(
        manifest, project_root
    )
    if parent_errors:
        summary["status"] = "incomplete_or_invalid"
        summary["snapshot_or_metric_errors"] = [{
            "case_id": None,
            "reasons": parent_errors,
        }]
        return summary
    reviewed = []
    errors = []
    for row in selected:
        record, case_errors = review_case(
            row, parents, manifest, project_root
        )
        if case_errors:
            errors.append({"case_id": row.get("case_id"), "reasons": case_errors})
        if record is not None:
            reviewed.append(record)
    summary["verified_parent_reuse_count"] = sum(
        row["evidence_origin"]["mode"] == "verified_parent_reuse"
        for row in selected
    )
    summary["reviewed_new_execution_count"] = sum(
        row["evidence_origin"]["mode"] == "executed_confirmation"
        for row in selected
    )
    summary["metric_valid_case_count"] = len(reviewed) - len(errors)
    summary["snapshot_or_metric_errors"] = errors
    if errors or len(reviewed) != 128:
        summary["status"] = "incomplete_or_invalid"
        return summary

    cells = numerical_cell_summaries(reviewed, manifest)
    effects = paired_factorial_effects(reviewed)
    interactions = class_changing_interactions(cells)
    artifacts = numerical_artifacts(cells)
    decision = decision_from_evidence(
        cells,
        effects,
        interactions,
        artifacts,
        manifest["boundary_expansion"]["conditional_design"],
    )
    summary.update({
        "status": "complete",
        "metric_valid_case_count": 128,
        "numerical_cells": cells,
        "paired_factorial_effects": effects,
        "class_changing_interactions": interactions,
        "numerical_artifacts": artifacts,
        "high_fidelity_results": {
            design: _high_fidelity(cells, design)
            for design in campaign.DESIGN_NAMES
        },
        "decision": decision,
    })
    return summary


def _fmt(value, digits=5):
    if value is None:
        return "—"
    return f"{value:.{digits}g}" if isinstance(value, (int, float)) else str(value)


def markdown(summary):
    lines = [
        "# Cu-fill transport numerical confirmation",
        "",
        f"Status: **{summary['status']}**. Current cells: "
        f"{summary['selected_current_case_count']}/{summary['expected_case_count']}; "
        f"metric-valid: {summary['metric_valid_case_count']}.",
        "",
        "This is a transport/numerical confirmation, not a morphology or recipe ranking.",
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
        f"Verified parent reuse: {summary['verified_parent_reuse_count']}/8. "
        f"New executions reviewed: {summary['reviewed_new_execution_count']}/120.",
        "",
        "| Authoritative design | Sign streams | Worst flux ratio | Worst velocity ratio | Best analytic H/a margin | Class |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for design in campaign.DESIGN_NAMES:
        item = summary["high_fidelity_results"][design]
        flux = item["response_summaries"][
            "worst_floor_to_each_lower_flux_ratio"
        ]["worst"]
        velocity = item["response_summaries"][
            "worst_floor_to_each_lower_velocity_ratio"
        ]["worst"]
        margin = item["broad_analytic_envelope"][
            "best_worst_normalized_margin"
        ]
        lines.append(
            f"| {design} | {item['transport_sign_pass_count']}/8 | "
            f"{_fmt(flux)} | {_fmt(velocity)} | {_fmt(margin)} | "
            f"{item['classification']} |"
        )
    boundary = summary["decision"]["boundary_expansion_evidence"]
    lines += [
        "",
        f"Class-changing numerical interactions: {len(summary['class_changing_interactions'])}. "
        f"Coarse/reflection artifacts: {len(summary['numerical_artifacts'])}.",
        "",
        "Boundary check: B improves the high-fidelity worst flux ratio by "
        f"{_fmt(boundary['B_improvement_over_A'])}; the largest paired numerical "
        f"effect/interaction is {_fmt(boundary['largest_absolute_paired_numerical_effect_or_interaction'])}.",
        "",
        f"Decision: **{summary['decision']['classification']}** — "
        f"{summary['decision']['reason']}",
        "",
        "Morphology authorized: **no**. Model-family pivot authorized: **no**.",
        "",
    ]
    return "\n".join(lines)


def _atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


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
    encoded = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
    _atomic_write(args.json, encoded)
    _atomic_write(args.markdown, markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "selected": summary["selected_current_case_count"],
        "metric_valid": summary["metric_valid_case_count"],
        "decision": summary["decision"]["classification"],
    }, allow_nan=False))


if __name__ == "__main__":
    main()

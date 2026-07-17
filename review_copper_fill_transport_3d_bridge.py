"""Independent fail-closed review of the matched 24-case 3D bridge."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
import viennaps as ps

import copper_fill_transport_3d as metrics3d
import foundation_copper_fill_transport_3d_bridge as campaign
import review_copper_fill_transport_boundary_confirmation as parent_review


DEFAULT_MANIFEST = campaign.DEFAULT_MANIFEST
DEFAULT_ROWS = campaign.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_3d_bridge_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_3d_bridge_review.md"
)
RESPONSES = {
    "worst_floor_to_each_lower_flux_ratio": False,
    "minimum_lower_minus_floor_coverage": True,
    "worst_floor_to_each_lower_velocity_ratio": True,
    "minimum_floor_minus_middle_upper_velocity": True,
    "realized_min_floor_to_fastest_wall_velocity_ratio": True,
}
SHARED_2D_3D_RESPONSES = tuple(list(RESPONSES)[:4])


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _resolve(project_root, path):
    path = Path(path)
    return path if path.is_absolute() else Path(project_root) / path


def _strict_jsonable(value):
    if isinstance(value, dict):
        return {str(key): _strict_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _strict_jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _strict_jsonable(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return "invalid_nonfinite"
    return value


def load_jsonl(path):
    path = Path(path)
    if not path.exists():
        return [], [], True
    rows = []
    errors = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception as error:
            errors.append({"line": line_number, "error": repr(error)})
    return rows, errors, False


def _structures_close(first, second, tolerance=1e-12):
    if isinstance(first, dict) and isinstance(second, dict):
        return set(first) == set(second) and all(
            _structures_close(first[key], second[key], tolerance) for key in first
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


def validate_attempt(row, expected, fingerprint):
    errors = []
    if not isinstance(row, dict):
        return ["attempt row is not a JSON object"]
    if row.get("case_id") != expected["case_id"]:
        errors.append("case_id differs from the frozen 3D cell")
    if row.get("case_id") != campaign.case_id(campaign._case_payload(row)):
        errors.append("case_id differs from the row's own payload")
    for field in campaign.CASE_FIELDS:
        if row.get(field) != expected.get(field):
            errors.append(f"case field differs from manifest: {field}")
    if row.get("runtime_fingerprint") != fingerprint:
        errors.append("runtime fingerprint differs from reviewed files")
    if row.get("production_doe_eligible") is not False:
        errors.append("production_doe_eligible is not explicitly false")
    if row.get("morphology_ranking_eligible") is not False:
        errors.append("morphology_ranking_eligible is not explicitly false")
    if row.get("target_pass") is not False:
        errors.append("3D core row preempted a product target pass")
    if row.get("transport_screen_pass") is not None:
        errors.append("runner preempted the independent transport decision")
    if row.get("evidence_origin") != {
        "mode": "executed_matched_3d_bridge",
        "parent_simulation_reused": False,
        "matched_2d_row_reused_for_context_only": True,
        "cross_dimension_common_random_numbers": False,
    }:
        errors.append("3D execution/comparison origin differs from the contract")
    stream = row.get("rng_stream", {})
    if stream != {
        "base_seed_label": int(expected["rng_seed"]),
        "checkpoint_seed": int(expected["rng_seed"]) + 1,
        "paired_within_3d_arms": True,
        "cross_dimension_common_random_numbers": False,
    }:
        errors.append("3D RNG declaration differs from the contract")
    return errors


def audit_attempts(manifest, rows, parse_errors, rows_missing, fingerprint):
    cases = campaign.expand_cases(manifest, fingerprint)
    manifest_errors = campaign.validate_manifest(
        manifest, cases, check_runtime=True
    )
    expected = {campaign._logical_key(case): case for case in cases}
    attempts = defaultdict(list)
    invalid_attempts = []
    unexpected = []
    positions = {id(row): index for index, row in enumerate(rows)}
    for row in rows:
        if not isinstance(row, dict):
            invalid_attempts.append({
                "reasons": ["attempt row is not a JSON object"],
                "row": _strict_jsonable(row),
            })
            continue
        try:
            key = campaign._logical_key(row)
        except Exception as error:
            invalid_attempts.append({
                "reasons": [f"attempt key is malformed: {error!r}"],
                "row": _strict_jsonable(row),
            })
            continue
        case = expected.get(key)
        if case is None:
            unexpected.append(_strict_jsonable(row))
            continue
        attempts[key].append(row)
        reasons = validate_attempt(row, case, fingerprint)
        if reasons:
            invalid_attempts.append({
                "reasons": reasons,
                "row": _strict_jsonable(row),
            })
    selected = []
    missing = []
    duplicate_successes = []
    resolved_failures = []
    current_failures = []
    for case in cases:
        valid = [
            row for row in attempts[campaign._logical_key(case)]
            if not validate_attempt(row, case, fingerprint)
        ]
        successes = [row for row in valid if row.get("ok") is True]
        failures = [row for row in valid if row.get("ok") is not True]
        if len(successes) > 1:
            duplicate_successes.append(case["case_id"])
        if not successes:
            missing.append({
                "case_id": case["case_id"],
                "design": case["design"],
                "geometry_tier": case["geometry_tier"],
                "max_reflections": case["numerics"]["max_reflections"],
                "rng_seed": case["rng_seed"],
            })
            current_failures.extend(_strict_jsonable(row) for row in failures)
            continue
        latest = max(successes, key=lambda row: positions[id(row)])
        selected.append(latest)
        for row in failures:
            if positions[id(row)] < positions[id(latest)]:
                resolved_failures.append(_strict_jsonable(row))
            else:
                current_failures.append(_strict_jsonable(row))
    invalid = bool(
        manifest_errors
        or parse_errors
        or invalid_attempts
        or unexpected
        or duplicate_successes
        or current_failures
    )
    complete = bool(
        not rows_missing and not invalid and len(selected) == 24 and not missing
    )
    return {
        "status": (
            "complete" if complete else "missing_rows" if rows_missing
            else "incomplete_or_invalid"
        ),
        "expected_case_count": 24,
        "expected_new_3d_execution_count": 24,
        "expected_2d_reuse_count": 0,
        "attempt_count": len(rows),
        "selected_current_case_count": len(selected),
        "manifest_validation_errors": manifest_errors,
        "parse_errors": parse_errors,
        "rows_missing": rows_missing,
        "invalid_attempts": invalid_attempts,
        "unexpected_attempt_rows": unexpected,
        "resolved_error_attempt_rows": resolved_failures,
        "current_error_attempt_rows": current_failures,
        "duplicate_success_case_ids": sorted(duplicate_successes),
        "missing_cases": missing,
        "selected_rows": selected,
    }


REQUIRED_SNAPSHOT_KEYS = {
    "snapshot_schema_version",
    "snapshot_case_id",
    "snapshot_case_payload_sha256",
    "simulation_dimension",
    "boundary_observed",
    "boundary_expected",
    "mesh_surface_stage",
    "diagnostic_surface_stage",
    "diagnostic_coordinates",
    "diagnostic_material_ids",
    "diagnostic_suppressor_flux",
    "diagnostic_coverage",
    "diagnostic_velocity",
    "diagnostic_adsorption_term",
    "diagnostic_deactivation_term",
    "diagnostic_relative_balance_error",
    "pre_material_names",
    "pre_material_legacy_ids",
    "post_material_names",
    "post_material_legacy_ids",
}
for _stage in ("pre", "post"):
    for _index in range(5):
        REQUIRED_SNAPSHOT_KEYS.add(f"{_stage}_level_set_{_index}_nodes")
        REQUIRED_SNAPSHOT_KEYS.add(f"{_stage}_level_set_{_index}_triangles")


def _scalar_text(value):
    values = np.asarray(value).reshape(-1)
    return str(values[0]) if len(values) == 1 else None


def _scalar_integer(value):
    values = np.asarray(value).reshape(-1)
    if len(values) != 1 or not np.issubdtype(values.dtype, np.integer):
        return None
    return int(values[0])


def _expected_material_ids():
    return (
        float(ps.Material.Si.legacyId()),
        float(ps.Material.SiO2.legacyId()),
        float(ps.Material.TaN.legacyId()),
        float(metrics3d.cu_seed_material().legacyId()),
        float(ps.Material.Cu.legacyId()),
    )


def _load_mesh_stack(saved, stage, errors):
    names = tuple(
        str(value)
        for value in np.asarray(saved[f"{stage}_material_names"]).reshape(-1)
    )
    ids = np.asarray(
        saved[f"{stage}_material_legacy_ids"], dtype=float
    ).reshape(-1)
    if names != metrics3d.EXPECTED_MATERIAL_NAMES:
        errors.append(
            f"{stage} snapshot material names differ from five-level-set stack"
        )
    if ids.shape != (5,) or not np.array_equal(
        ids, np.asarray(_expected_material_ids())
    ):
        errors.append(f"{stage} snapshot material IDs differ from exact stack")
    meshes = []
    for index in range(5):
        nodes = np.asarray(
            saved[f"{stage}_level_set_{index}_nodes"], dtype=float
        )
        triangles_raw = np.asarray(
            saved[f"{stage}_level_set_{index}_triangles"]
        )
        if nodes.ndim != 2 or nodes.shape[1:] != (3,) or not len(nodes):
            errors.append(f"{stage} level set {index} nodes are not nonempty Nx3")
        elif not np.all(np.isfinite(nodes)):
            errors.append(
                f"{stage} level set {index} nodes contain nonfinite values"
            )
        elif any(np.ptp(nodes[:, axis]) <= 0.0 for axis in range(3)):
            errors.append(
                f"{stage} level set {index} is coplanar or dimensionally degenerate"
            )
        if (
            triangles_raw.ndim != 2
            or triangles_raw.shape[1:] != (3,)
            or not len(triangles_raw)
            or not np.issubdtype(triangles_raw.dtype, np.integer)
        ):
            errors.append(
                f"{stage} level set {index} lacks integer triangle connectivity"
            )
            triangles = np.empty((0, 3), dtype=int)
        else:
            triangles = np.asarray(triangles_raw, dtype=int)
            if len(nodes) and (
                np.min(triangles) < 0 or np.max(triangles) >= len(nodes)
            ):
                errors.append(
                    f"{stage} level set {index} triangle index is out of range"
                )
        meshes.append({
            "material_name": names[index] if index < len(names) else "invalid",
            "nodes": nodes,
            "triangles": triangles,
        })
    return meshes, ids


def _raw_diagnostic_audit(raw, row, plating_ids):
    errors = []
    coordinates = raw["coordinates"]
    if (
        coordinates.ndim != 2
        or coordinates.shape[1:] != (3,)
        or not len(coordinates)
    ):
        errors.append("diagnostic coordinates are not nonempty Nx3")
    elif any(np.ptp(coordinates[:, axis]) <= 0.0 for axis in range(3)):
        errors.append("diagnostic coordinates are coplanar or dimensionally degenerate")
    count = len(coordinates)
    for name, values in raw.items():
        if name != "coordinates" and values.shape != (count,):
            errors.append(f"diagnostic array does not align: {name}")
    if any(not np.all(np.isfinite(value)) for value in raw.values()):
        errors.append("diagnostic arrays contain nonfinite values")
    if errors:
        return None, None, errors
    plating = np.isin(raw["material_ids"], np.asarray(plating_ids, dtype=float))
    model = row["model"]
    bounds_valid = bool(
        np.any(plating)
        and np.min(raw["suppressor_flux"]) >= 0.0
        and np.min(raw["coverage"]) >= 0.0
        and np.max(raw["coverage"]) <= 1.0
        and np.min(raw["velocity"][plating])
        >= float(model["suppressed_deposition_rate"]) - 1e-12
        and np.max(raw["velocity"][plating])
        <= float(model["active_deposition_rate"]) + 1e-12
        and (
            np.all(plating)
            or np.max(np.abs(raw["velocity"][~plating])) <= 1e-12
        )
    )
    scale = np.maximum.reduce([
        np.abs(raw["adsorption_term"]),
        np.abs(raw["deactivation_term"]),
        np.full(count, np.finfo(float).eps),
    ])
    balance = float(
        np.max(
            np.abs(raw["adsorption_term"] - raw["deactivation_term"]) / scale
        )
    )
    return bounds_valid, balance, []


def review_case(row, project_root):
    errors = []
    snapshot = _resolve(project_root, row.get("diagnostic_snapshot_path", ""))
    if not snapshot.is_file():
        return None, [f"3D diagnostic snapshot is missing: {snapshot}"]
    if _file_sha256(snapshot) != row.get("diagnostic_snapshot_sha256"):
        return None, ["3D diagnostic snapshot hash mismatch"]
    try:
        with np.load(snapshot, allow_pickle=False) as saved:
            missing = sorted(REQUIRED_SNAPSHOT_KEYS - set(saved.files))
            if missing:
                return None, [f"3D snapshot lacks required arrays: {missing}"]
            raw = {
                "coordinates": np.asarray(saved["diagnostic_coordinates"], dtype=float),
                "material_ids": np.asarray(saved["diagnostic_material_ids"], dtype=float),
                "suppressor_flux": np.asarray(saved["diagnostic_suppressor_flux"], dtype=float),
                "coverage": np.asarray(saved["diagnostic_coverage"], dtype=float),
                "velocity": np.asarray(saved["diagnostic_velocity"], dtype=float),
                "adsorption_term": np.asarray(saved["diagnostic_adsorption_term"], dtype=float),
                "deactivation_term": np.asarray(saved["diagnostic_deactivation_term"], dtype=float),
            }
            before_meshes, pre_ids = _load_mesh_stack(saved, "pre", errors)
            after_meshes, post_ids = _load_mesh_stack(saved, "post", errors)
            saved_balance = np.asarray(
                saved["diagnostic_relative_balance_error"], dtype=float
            ).reshape(-1)
            diagnostic_stage = _scalar_text(saved["diagnostic_surface_stage"])
            mesh_stage = _scalar_text(saved["mesh_surface_stage"])
            schema_version = _scalar_integer(saved["snapshot_schema_version"])
            snapshot_dimension = _scalar_integer(saved["simulation_dimension"])
            snapshot_case_id = _scalar_text(saved["snapshot_case_id"])
            snapshot_payload_hash = _scalar_text(
                saved["snapshot_case_payload_sha256"]
            )
            boundary_observed = [
                str(value)
                for value in np.asarray(saved["boundary_observed"]).reshape(-1)
            ]
            boundary_expected = [
                str(value)
                for value in np.asarray(saved["boundary_expected"]).reshape(-1)
            ]
    except Exception as error:
        return None, [f"cannot read 3D snapshot: {error!r}"]
    if schema_version != 1:
        errors.append("unexpected 3D snapshot schema version")
    if snapshot_dimension != 3 or row.get("simulation_dimension") != 3:
        errors.append("snapshot or row simulation dimension is not exactly 3")
    if snapshot_case_id != row.get("case_id"):
        errors.append("snapshot case ID differs from row")
    try:
        expected_payload_hash = campaign._canonical_row_sha256(
            campaign._case_payload(row)
        )
    except Exception as error:
        expected_payload_hash = None
        errors.append(f"row case payload cannot be hashed: {error!r}")
    if snapshot_payload_hash != expected_payload_hash:
        errors.append("snapshot case-payload hash differs from row")
    expected_boundary = ["0", "0", "1"]
    if boundary_observed != expected_boundary or boundary_expected != expected_boundary:
        errors.append(
            "snapshot boundary contract differs from reflective/reflective/infinite"
        )
    if diagnostic_stage != "pre-final-advection surface":
        errors.append("unexpected 3D diagnostic surface stage")
    if mesh_stage != "complete pre/post five-level-set stack":
        errors.append("unexpected 3D mesh surface stage")
    if len(saved_balance) != 1 or not np.isfinite(saved_balance[0]):
        errors.append("saved balance error is not one finite scalar")
    if errors:
        return None, errors

    plating_ids = [float(pre_ids[-2]), float(pre_ids[-1])]
    if (
        plating_ids != list(_expected_material_ids()[-2:])
        or not np.array_equal(pre_ids, post_ids)
        or row.get("plating_material_legacy_ids") != plating_ids
    ):
        return None, ["exact CuSeed/Cu plating material ID contract differs"]
    try:
        reference = metrics3d.reference_from_meshes(before_meshes, row)
        protected = metrics3d.protected_stack_delta(
            before_meshes[:-1], after_meshes[:-1]
        )
        structure = metrics3d.surface_structure(after_meshes[-1], reference)
    except Exception as error:
        return None, [f"independent 3D stack/reference review failed: {error!r}"]
    if not _structures_close(reference, row.get("reference")):
        errors.append("row reference or H/a differs from saved pre-advection stack")
    if not _structures_close(protected, row.get("protected_stack")):
        errors.append("row protected-stack result differs from saved pre/post stack")
    if not _structures_close(structure, row.get("surface_structure")):
        errors.append("row cavity structure differs from saved post-advection Cu")
    row_boundary = row.get("boundary_contract", {})
    if (
        row_boundary.get("pass") is not True
        or row_boundary.get("observed") != boundary_observed
        or row_boundary.get("expected") != boundary_expected
    ):
        errors.append("row boundary contract differs from snapshot")
    bounds_valid, raw_balance, raw_errors = _raw_diagnostic_audit(
        raw, row, plating_ids
    )
    errors.extend(raw_errors)
    diagnostics = row.get("model_diagnostics", {})
    if not raw_errors:
        if diagnostics.get("finite") is not True:
            errors.append("row diagnostics do not declare finite raw arrays")
        if diagnostics.get("point_count") != len(raw["coordinates"]):
            errors.append("row diagnostic point count differs from raw snapshot")
        if diagnostics.get("bounds_valid") is not bounds_valid:
            errors.append("row diagnostic bounds differ from raw snapshot")
        if diagnostics.get("material_ids") != sorted(
            np.unique(raw["material_ids"]).tolist()
        ):
            errors.append("row diagnostic material IDs differ from raw snapshot")
        if not math.isclose(
            float(saved_balance[0]), raw_balance, rel_tol=0.0, abs_tol=1e-12
        ):
            errors.append("saved model balance differs from recomputed raw balance")
        if not math.isclose(
            float(diagnostics.get("relative_balance_error", math.nan)),
            raw_balance,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            errors.append("row model balance differs from recomputed raw balance")
    if errors:
        return None, errors
    parity = metrics3d.analytic_parity(raw, row["model"], plating_ids)
    if not _structures_close(parity, row.get("analytic_law_parity")):
        errors.append("analytic law parity differs from raw 3D snapshot")
    phase_regions = {}
    phase_decisions = {}
    guards = {
        "diagnostic_balance_valid": bool(
            bounds_valid is True
            and raw_balance <= row["target"]["max_balance_error"]
        ),
        "analytic_parity_valid": all(
            value <= row["target"]["analytic_parity_abs_tolerance"]
            for name, value in parity.items()
            if name.endswith("max_abs_error")
        ),
        "full_cylinder_and_stack_valid": bool(
            boundary_observed == expected_boundary
            and reference["seed_surface_connected"] is True
            and reference["cavity_open_at_mouth"] is True
        ),
        "protected_stack_survives": protected["survives"] is True,
        "cavity_remains_open_without_sealed_component": bool(
            structure["cavity_open"] is True
            and structure["unexpected_sealed_component"] is False
        ),
    }
    try:
        for offset in row["analysis"]["sector_offsets_degrees"]:
            label = f"offset_{float(offset):g}_degrees"
            regions, masks = metrics3d.region_statistics(
                raw["coordinates"],
                raw["material_ids"],
                raw["suppressor_flux"],
                raw["coverage"],
                raw["velocity"],
                plating_ids,
                reference,
                offset,
            )
            plating = np.isin(raw["material_ids"], plating_ids)
            if any(np.any(mask & ~plating) for mask in masks.values()):
                errors.append(f"{label} regional mask includes non-plating material")
            decision = metrics3d.transport_decision(
                regions,
                reference,
                row["analysis"]["minimum_sector_point_count"],
                guards,
            )
            if not decision["conditions"][
                "all_required_sectors_finite_and_populated"
            ]:
                errors.append(f"{label} required sector metrics are ineligible")
            phase_regions[label] = regions
            phase_decisions[label] = decision
    except Exception as error:
        errors.append(f"3D regional review failed closed: {error!r}")
    if not _structures_close(phase_regions, row.get("analysis_regions")):
        errors.append("saved 3D regional statistics differ from raw snapshot")
    if not _structures_close(
        phase_decisions, row.get("transport_sign_by_sector_phase")
    ):
        errors.append("saved 3D transport decisions differ from raw snapshot")
    phase_passes = [decision["pass"] for decision in phase_decisions.values()]
    stable = len(set(phase_passes)) == 1
    if stable != row.get("sector_phase_class_stable"):
        errors.append("saved sector-phase stability differs from raw snapshot")
    if errors:
        return None, errors
    return {
        "row": row,
        "raw": raw,
        "phase_regions": phase_regions,
        "phase_decisions": phase_decisions,
        "phase_class_stable": stable,
        "reference": reference,
        "protected_stack": protected,
        "surface_structure": structure,
    }, []


def response_values(record):
    decisions = list(record["phase_decisions"].values())
    return {
        "worst_floor_to_each_lower_flux_ratio": max(
            value
            for decision in decisions
            for value in decision["floor_to_lower_flux_ratios"]
        ),
        "minimum_lower_minus_floor_coverage": min(
            value
            for decision in decisions
            for value in decision["lower_minus_floor_coverage"]
        ),
        "worst_floor_to_each_lower_velocity_ratio": min(
            value
            for decision in decisions
            for value in decision["floor_to_lower_velocity_ratios"]
        ),
        "minimum_floor_minus_middle_upper_velocity": min(
            decision["minimum_floor_minus_fastest_middle_upper_velocity"]
            for decision in decisions
        ),
        "realized_min_floor_to_fastest_wall_velocity_ratio": min(
            decision["realized_min_floor_to_fastest_wall_velocity_ratio"]
            for decision in decisions
        ),
    }


def reflection_convergence(records, manifest):
    grouped = defaultdict(dict)
    for record in records:
        row = record["row"]
        if row["design"] != campaign.CANDIDATE_NAME:
            continue
        grouped[(row["geometry_tier"], row["rng_seed"])][
            row["numerics"]["max_reflections"]
        ] = record
    response_deltas = {}
    tolerances = manifest["reflection_convergence"][
        "maximum_paired_absolute_delta"
    ]
    for response in RESPONSES:
        deltas = []
        invalid = []
        for (tier, seed), arms in grouped.items():
            if set(arms) != {1600, 3200}:
                invalid.append({
                    "geometry_tier": tier,
                    "rng_seed": seed,
                    "reason": "missing_reflection_arm",
                })
                continue
            low = response_values(arms[1600]).get(response)
            high = response_values(arms[3200]).get(response)
            if not (_number(low) and _number(high)):
                invalid.append({
                    "geometry_tier": tier,
                    "rng_seed": seed,
                    "reason": "nonfinite_response",
                })
                continue
            deltas.append(high - low)
        eligible_response = bool(len(deltas) == 8 and not invalid)
        tolerance = float(tolerances[response])
        worst_absolute = float(np.max(np.abs(deltas))) if deltas else None
        response_deltas[response] = {
            "eligible": eligible_response,
            "paired_stream_count": len(deltas),
            "invalid_pairs": invalid,
            "mean_signed_delta_3200_minus_1600": (
                float(np.mean(deltas)) if deltas else None
            ),
            "worst_absolute_delta": worst_absolute,
            "tolerance": tolerance,
            "pass": bool(
                eligible_response and worst_absolute is not None
                and worst_absolute <= tolerance
            ),
        }
    class_changes = []
    condition_changes = []
    for (tier, seed), arms in grouped.items():
        if set(arms) != {1600, 3200}:
            continue
        low_class = tuple(
            decision["pass"] for decision in arms[1600]["phase_decisions"].values()
        )
        high_class = tuple(
            decision["pass"] for decision in arms[3200]["phase_decisions"].values()
        )
        if low_class != high_class:
            class_changes.append({
                "geometry_tier": tier,
                "rng_seed": seed,
                "at_1600": low_class,
                "at_3200": high_class,
            })
        low_conditions = {
            phase: decision["conditions"]
            for phase, decision in arms[1600]["phase_decisions"].items()
        }
        high_conditions = {
            phase: decision["conditions"]
            for phase, decision in arms[3200]["phase_decisions"].items()
        }
        for phase in sorted(set(low_conditions) | set(high_conditions)):
            before = low_conditions.get(phase, {})
            after = high_conditions.get(phase, {})
            for condition in sorted(set(before) | set(after)):
                if before.get(condition) != after.get(condition):
                    condition_changes.append({
                        "geometry_tier": tier,
                        "rng_seed": seed,
                        "sector_phase": phase,
                        "condition": condition,
                        "at_1600": before.get(condition),
                        "at_3200": after.get(condition),
                    })
    eligible = bool(
        len(grouped) == 8
        and all(item["eligible"] for item in response_deltas.values())
    )
    class_stable = bool(eligible and not class_changes and not condition_changes)
    responses_within_tolerance = bool(
        eligible and all(item["pass"] for item in response_deltas.values())
    )
    return {
        "eligible": eligible,
        "class_stable": class_stable,
        "responses_within_tolerance": responses_within_tolerance,
        "converged": bool(class_stable and responses_within_tolerance),
        "class_changes": class_changes,
        "condition_changes": condition_changes,
        "response_deltas": response_deltas,
        "authority": "reflection-depth consistency only; not 3D grid/ray convergence",
    }


def independently_review_2d(parent_rows, manifest, project_root):
    records_by_id = {}
    reviewed_records = []
    errors = []
    for row in parent_rows.values():
        try:
            reviewed, case_errors = parent_review.review_new_case(
                row, project_root
            )
        except Exception as error:
            reviewed = None
            case_errors = [f"independent 2D review raised: {error!r}"]
        if case_errors:
            errors.append({
                "case_id": row.get("case_id"),
                "reasons": case_errors,
            })
        if reviewed is not None and not case_errors:
            records_by_id[row["case_id"]] = reviewed
            reviewed_records.append(reviewed)
    if errors or len(reviewed_records) != 24:
        return None, errors
    parent_artifact = manifest["matched_2d_comparison"]
    try:
        parent_manifest = json.loads(
            _resolve(
                project_root, parent_artifact["source_manifest_path"]
            ).read_text()
        )
        pinned_summary = json.loads(
            _resolve(
                project_root, parent_artifact["source_summary_path"]
            ).read_text()
        )
    except Exception as error:
        return None, [{
            "case_id": None,
            "reasons": [f"cannot parse hash-verified 2D artifacts: {error!r}"],
        }]
    controls = [
        record for record in reviewed_records
        if record["public"]["design"] == campaign.CONTROL_NAME
    ]
    candidates = [
        record for record in reviewed_records
        if record["public"]["design"] == campaign.CANDIDATE_NAME
    ]
    arm_B = parent_review._arm_summary(
        controls,
        parent_manifest,
        "matched_B_cap6400_reflections_800",
        800,
    )
    arm_C = parent_review._arm_summary(
        [
            record for record in candidates
            if record["public"]["max_reflections"] == 3200
        ],
        parent_manifest,
        "new_C_reflections_3200",
        3200,
    )
    directions = parent_review.multiresponse_paired_directions(
        controls, candidates
    )
    for label, current, pinned in (
        ("B800 arm", arm_B, pinned_summary.get("parent_B_comparison")),
        ("C3200 arm", arm_C, pinned_summary.get("reflection_arms", {}).get("3200")),
        (
            "B-to-C directions",
            directions,
            pinned_summary.get("multiresponse_paired_directions"),
        ),
    ):
        if not _structures_close(current, pinned):
            errors.append({
                "case_id": None,
                "reasons": [f"independent 2D {label} differs from pinned summary"],
            })
    if errors:
        return None, errors
    return {
        "records_by_id": records_by_id,
        "record_count": len(reviewed_records),
        "arm_B800": arm_B,
        "arm_C3200": arm_C,
        "directions": directions,
    }, []


def _three_d_direction_values(records):
    controls = {}
    candidates = {}
    for record in records:
        row = record["row"]
        key = (row["geometry_tier"], row["rng_seed"])
        if row["design"] == campaign.CONTROL_NAME:
            controls[key] = record
        elif row["design"] == campaign.CANDIDATE_NAME and row["numerics"][
            "max_reflections"
        ] == 3200:
            candidates[key] = record
    keys = sorted(set(controls) & set(candidates))
    values = {}
    for response in SHARED_2D_3D_RESPONSES:
        response_deltas = {}
        for key in keys:
            old = response_values(controls[key])[response]
            new = response_values(candidates[key])[response]
            if _number(old) and _number(new):
                higher_is_better = RESPONSES[response]
                response_deltas[key] = (
                    new - old if higher_is_better else old - new
                )
        values[response] = response_deltas
    return keys, values


def paired_B_to_C_directions(records, parent_evidence):
    three_keys, three_values = _three_d_direction_values(records)
    two_results = parent_evidence["directions"]["responses"]
    results = {}
    for response in SHARED_2D_3D_RESPONSES:
        three = three_values[response]
        two = two_results.get(response, {})
        eligible = bool(
            len(three_keys) == 8
            and set(three) == set(three_keys)
            and two.get("eligible") is True
            and two.get("paired_stream_count") == 8
        )
        two_mean = two.get("mean_oriented_improvement")
        three_mean = float(np.mean(list(three.values()))) if three else None
        if not eligible or not (_number(two_mean) and _number(three_mean)):
            classification = "ineligible"
            eligible = False
        elif float(two_mean) == 0.0 or float(three_mean) == 0.0:
            classification = "ineligible"
            eligible = False
        elif np.sign(two_mean) == np.sign(three_mean):
            classification = "agreement"
        else:
            classification = "reversal"
        results[response] = {
            "eligible": eligible,
            "classification": classification,
            "two_d": {
                "paired_stream_count": two.get("paired_stream_count"),
                "improved_count": two.get("improved_count"),
                "worsened_count": two.get("worsened_count"),
                "unchanged_count": two.get("unchanged_count"),
                "mean_oriented_improvement": two_mean,
                "aggregate_direction": (
                    "improves" if two_mean is not None and two_mean > 0.0
                    else "worsens" if two_mean is not None and two_mean < 0.0
                    else "unchanged_or_ineligible"
                ),
            },
            "three_d": {
                "paired_stream_count": len(three),
                "improved_count": sum(value > 0.0 for value in three.values()),
                "worsened_count": sum(value < 0.0 for value in three.values()),
                "unchanged_count": sum(value == 0.0 for value in three.values()),
                "mean_oriented_improvement": three_mean,
                "aggregate_direction": (
                    "improves" if three_mean is not None and three_mean > 0.0
                    else "worsens" if three_mean is not None and three_mean < 0.0
                    else "unchanged_or_ineligible"
                ),
            },
        }
    return {
        "eligible": bool(
            len(three_keys) == 8
            and all(item["eligible"] for item in results.values())
        ),
        "three_d_within_dimension_paired_stream_count": len(three_keys),
        "two_d_within_dimension_paired_stream_count": parent_evidence[
            "directions"
        ].get("paired_stream_count"),
        "cross_dimension_common_random_numbers": False,
        "interpretation": (
            "B800-to-C3200 is paired only within each dimension. The comparison "
            "uses aggregate mean directions, never per-seed cross-dimensional deltas."
        ),
        "responses": results,
    }


def _three_d_arm_class(records, design, max_reflections):
    selected = [
        record for record in records
        if record["row"]["design"] == design
        and record["row"]["numerics"]["max_reflections"] == max_reflections
    ]
    passes = [
        record["phase_class_stable"]
        and all(item["pass"] for item in record["phase_decisions"].values())
        for record in selected
    ]
    if len(passes) != 8:
        classification = "ineligible"
    elif all(passes):
        classification = "pass"
    elif not any(passes):
        classification = "no_go"
    else:
        classification = "mixed"
    return {
        "eligible": len(passes) == 8,
        "stream_count": len(passes),
        "transport_sign_pass_count": sum(passes),
        "classification": classification,
    }


def dimensional_comparison(records, parent_evidence, response_comparison):
    classes = {}
    for label, design, reflections, parent_key in (
        ("B800", campaign.CONTROL_NAME, 800, "arm_B800"),
        ("C3200", campaign.CANDIDATE_NAME, 3200, "arm_C3200"),
    ):
        two = parent_evidence[parent_key]
        three = _three_d_arm_class(records, design, reflections)
        eligible = bool(
            two.get("required_metrics_valid") is True
            and two.get("stream_count") == 8
            and two.get("classification") in {"pass", "no_go", "mixed"}
            and three["eligible"]
        )
        if not eligible:
            comparison = "ineligible"
        elif two["classification"] == three["classification"]:
            comparison = "agreement"
        elif "mixed" in {two["classification"], three["classification"]}:
            comparison = "mixed"
        else:
            comparison = "reversal"
        classes[label] = {
            "eligible": eligible,
            "two_d_class": two.get("classification"),
            "two_d_combined_pass": two.get("combined_2d_pass"),
            "three_d_class": three["classification"],
            "three_d_transport_sign_pass_count": three[
                "transport_sign_pass_count"
            ],
            "stream_count": three["stream_count"],
            "classification": comparison,
        }
    return {
        "eligible": bool(
            all(item["eligible"] for item in classes.values())
            and response_comparison.get("eligible") is True
        ),
        "cross_dimension_common_random_numbers": False,
        "classes": classes,
        "responses": response_comparison.get("responses", {}),
        "any_reversal": bool(
            any(item["classification"] == "reversal" for item in classes.values())
            or any(
                item.get("classification") == "reversal"
                for item in response_comparison.get("responses", {}).values()
            )
        ),
    }


def decision_from_evidence(
    authoritative, convergence, phase_stable, dimensional_evidence=None
):
    base = {
        "authority": "dimensional_transport_screen_only",
        "morphology_authorized": False,
        "terminal_model_family_pivot_authorized": False,
        "automatic_model_family_pivot_authorized": False,
        "full_traveler_authorized": False,
        "process_recipe_authorized": False,
        "automatic_additional_launch_authorized": False,
        "conditional_numerical_and_unseen_arms_required": True,
    }
    if not convergence.get("eligible"):
        return {
            **base,
            "classification": "reflection_comparison_ineligible_blocks_inference",
            "reason": "C1600/C3200 lacks a complete finite eight-stream comparison.",
        }
    if not convergence.get("class_stable"):
        return {
            **base,
            "classification": "reflection_depth_class_change_inconclusive",
            "reason": "At least one C stream changes class between 1600 and 3200 reflections.",
        }
    if not convergence.get("responses_within_tolerance"):
        return {
            **base,
            "classification": "reflection_response_not_converged",
            "reason": (
                "At least one paired C1600/C3200 response exceeds its frozen "
                "absolute tolerance. The dimensional screen is inconclusive."
            ),
        }
    if not phase_stable:
        return {
            **base,
            "classification": "angular_sector_phase_change_inconclusive",
            "reason": "At least one 3D row changes class between the 0 and 22.5 degree sector partitions.",
        }
    if not dimensional_evidence or not dimensional_evidence.get("eligible"):
        return {
            **base,
            "classification": "cross_dimensional_comparison_ineligible",
            "reason": (
                "The hash-verified 2D B800/C3200 classes and response directions "
                "were not independently compared with the reviewed 3D evidence."
            ),
        }
    if dimensional_evidence.get("any_reversal"):
        return {
            **base,
            "classification": "three_dimensional_transport_reversal_screen_requires_numerics",
            "reason": (
                "At least one independently reviewed arm class or aggregate "
                "B800-to-C3200 response direction reverses between 2D and 3D. "
                "Conditional 3D numerical and unseen-seed checks are required."
            ),
        }
    if any(
        item.get("classification") == "mixed"
        for item in dimensional_evidence.get("classes", {}).values()
    ):
        return {
            **base,
            "classification": "cross_dimensional_class_mixed_inconclusive",
            "reason": "At least one 3D B800/C3200 arm has mixed stream classes.",
        }
    passes = [
        all(decision["pass"] for decision in record["phase_decisions"].values())
        for record in authoritative
    ]
    if len(passes) != 8:
        return {
            **base,
            "classification": "authoritative_C_arm_incomplete",
            "reason": "The C3200 arm does not contain eight reviewed streams.",
        }
    if all(passes):
        return {
            **base,
            "classification": "three_dimensional_transport_reversal_screen_requires_numerics",
            "reason": (
                "C3200 passes this 24-cell dimensional screen, but 3D grid/ray/cap "
                "qualification and unseen seeds are still required before morphology."
            ),
        }
    if not any(passes):
        return {
            **base,
            "classification": "three_dimensional_transport_no_go_screen_requires_numerics",
            "reason": (
                "C3200 fails all eight 3D streams in this dimensional screen. "
                "This can stop the tested proxy from morphology only after the "
                "predeclared numerical and unseen checks; it is not physical impossibility."
            ),
        }
    return {
        **base,
        "classification": "three_dimensional_transport_mixed_inconclusive",
        "reason": "C3200 has mixed tier/seed outcomes and cannot support a dimensional conclusion.",
    }


def arm_tier_H_over_a_summary(records, manifest):
    result = {}
    for design, reflections in (
        (campaign.CONTROL_NAME, 800),
        (campaign.CANDIDATE_NAME, 1600),
        (campaign.CANDIDATE_NAME, 3200),
    ):
        arm_key = f"{design}_reflections_{reflections}"
        result[arm_key] = {
            "analytic_envelope_status": None,
            "tiers": {},
        }
        for tier in campaign.GEOMETRY_TIERS:
            selected = [
                record for record in records
                if record["row"]["design"] == design
                and record["row"]["numerics"]["max_reflections"] == reflections
                and record["row"]["geometry_tier"] == tier
            ]
            heights = [record["reference"]["height_H"] for record in selected]
            radii = [
                record["reference"]["mouth_radius_minimum"] for record in selected
            ]
            required = [
                record["reference"]["kinematic_threshold_H_over_a_mouth"]
                for record in selected
            ]
            realized = [
                response_values(record)[
                    "realized_min_floor_to_fastest_wall_velocity_ratio"
                ]
                for record in selected
            ]
            transport_passes = [
                all(item["pass"] for item in record["phase_decisions"].values())
                for record in selected
            ]
            flux_passes = [
                all(
                    item["conditions"][
                        "floor_to_each_lower_flux_ratio_strictly_below_0p95"
                    ]
                    for item in record["phase_decisions"].values()
                )
                for record in selected
            ]
            result[arm_key]["tiers"][tier] = {
                "stream_count": len(selected),
                "H_min": float(min(heights)) if heights else None,
                "H_max": float(max(heights)) if heights else None,
                "a_min": float(min(radii)) if radii else None,
                "a_max": float(max(radii)) if radii else None,
                "required_H_over_a_min": float(min(required)) if required else None,
                "required_H_over_a_max": float(max(required)) if required else None,
                "realized_floor_to_fastest_wall_minimum": (
                    float(min(realized)) if realized else None
                ),
                "realized_floor_to_fastest_wall_maximum": (
                    float(max(realized)) if realized else None
                ),
                "transport_pass_count": sum(transport_passes),
                "flux_preliminary_pass_count": sum(flux_passes),
                "H_over_a_pass_count": sum(
                    value > threshold
                    for value, threshold in zip(realized, required)
                ),
            }
        flux_pass_count = sum(
            item["flux_preliminary_pass_count"]
            for item in result[arm_key]["tiers"].values()
        )
        result[arm_key]["analytic_envelope_status"] = (
            "not_evaluated_dimensional_screen_only"
            if flux_pass_count == 8
            else manifest["analysis"][
                "analytic_envelope_status_on_flux_failure"
            ]
        )
    return result


def build_summary(manifest, rows, parse_errors, rows_missing, fingerprint, project_root):
    audit = audit_attempts(manifest, rows, parse_errors, rows_missing, fingerprint)
    selected = audit.pop("selected_rows")
    summary = {
        **audit,
        "campaign": manifest.get("campaign"),
        "expected_runtime_fingerprint": fingerprint,
        "reviewer_sha256": _file_sha256(Path(__file__).resolve()),
        "verified_2d_comparison_count": 0,
        "independently_reviewed_2d_case_count": 0,
        "reviewed_3d_case_count": 0,
        "snapshot_or_metric_errors": [],
        "reflection_convergence": None,
        "paired_B_to_C_directions": None,
        "dimensional_comparison": None,
        "arm_tier_H_over_a": {},
        "decision": {
            "classification": "insufficient_audited_3d_evidence",
            "authority": "none",
            "morphology_authorized": False,
            "terminal_model_family_pivot_authorized": False,
            "automatic_model_family_pivot_authorized": False,
            "full_traveler_authorized": False,
            "process_recipe_authorized": False,
            "automatic_additional_launch_authorized": False,
            "reason": "The exact 24-cell 3D artifact has not cleared audit.",
        },
    }
    if audit["status"] != "complete":
        return summary
    parents, parent_errors = campaign.load_verified_2d_comparison(
        manifest, project_root
    )
    if parent_errors:
        summary["status"] = "incomplete_or_invalid"
        summary["snapshot_or_metric_errors"] = [{
            "case_id": None,
            "reasons": parent_errors,
        }]
        return summary
    parent_evidence, independent_parent_errors = independently_review_2d(
        parents, manifest, project_root
    )
    if independent_parent_errors or parent_evidence is None:
        summary["status"] = "incomplete_or_invalid"
        summary["snapshot_or_metric_errors"] = independent_parent_errors
        return summary
    records = []
    errors = []
    for row in selected:
        try:
            record, case_errors = review_case(row, project_root)
        except Exception as error:
            record = None
            case_errors = [f"independent 3D case review raised: {error!r}"]
        if case_errors:
            errors.append({"case_id": row.get("case_id"), "reasons": case_errors})
        if record is not None:
            records.append(record)
    summary["verified_2d_comparison_count"] = len(parents)
    summary["independently_reviewed_2d_case_count"] = parent_evidence[
        "record_count"
    ]
    summary["reviewed_3d_case_count"] = len(records)
    summary["snapshot_or_metric_errors"] = errors
    if errors or len(records) != 24 or len(parents) != 24:
        summary["status"] = "incomplete_or_invalid"
        return summary
    convergence = reflection_convergence(records, manifest)
    paired = paired_B_to_C_directions(records, parent_evidence)
    comparison = dimensional_comparison(records, parent_evidence, paired)
    authoritative = [
        record for record in records
        if record["row"]["design"] == campaign.CANDIDATE_NAME
        and record["row"]["numerics"]["max_reflections"] == 3200
    ]
    phase_stable = all(record["phase_class_stable"] for record in records)
    decision = decision_from_evidence(
        authoritative, convergence, phase_stable, comparison
    )
    summary.update({
        "status": "complete",
        "reflection_convergence": convergence,
        "paired_B_to_C_directions": paired,
        "dimensional_comparison": comparison,
        "arm_tier_H_over_a": arm_tier_H_over_a_summary(records, manifest),
        "decision": decision,
    })
    return summary


def markdown(summary):
    lines = [
        "# Matched 3D Cu transport bridge",
        "",
        f"Status: **{summary['status']}**; reviewed 3D cells: "
        f"{summary['reviewed_3d_case_count']}/24; verified 2D comparisons: "
        f"{summary['verified_2d_comparison_count']}/24.",
        "",
        "This is a dimensional transport screen, not morphology or a recipe result.",
        "",
        f"Decision: **{summary['decision']['classification']}** — "
        f"{summary['decision']['reason']}",
        "",
        "Morphology authorized: **no**. Terminal model-family pivot authorized: **no**.",
    ]
    comparison = summary.get("dimensional_comparison")
    if isinstance(comparison, dict):
        lines.extend([
            "",
            "## Independently reviewed 2D versus 3D",
            "",
            "| Evidence | 2D | 3D | Read |",
            "|---|---:|---:|---|",
        ])
        for label, item in comparison.get("classes", {}).items():
            lines.append(
                f"| {label} hard-gate class | {item['two_d_class']} | "
                f"{item['three_d_class']} | {item['classification']} |"
            )
        for response, item in comparison.get("responses", {}).items():
            lines.append(
                f"| {response} direction | "
                f"{item['two_d']['aggregate_direction']} | "
                f"{item['three_d']['aggregate_direction']} | "
                f"{item['classification']} |"
            )
        lines.extend([
            "",
            "B-to-C recipes are paired within each dimension only; the seed labels "
            "are not cross-dimensional common random numbers.",
        ])
    arms = summary.get("arm_tier_H_over_a", {})
    if arms:
        lines.extend([
            "",
            "## H/a dimensional screen",
            "",
            "| Arm | Tier | H | a | Required H/a | Realized worst | Passes |",
            "|---|---|---:|---:|---:|---:|---:|",
        ])
        for arm, arm_result in arms.items():
            for tier, item in arm_result["tiers"].items():
                lines.append(
                    f"| {arm} | {tier} | {item['H_min']:.6g} | "
                    f"{item['a_min']:.6g} | {item['required_H_over_a_max']:.6g} | "
                    f"{item['realized_floor_to_fastest_wall_minimum']:.6g} | "
                    f"{item['transport_pass_count']}/{item['stream_count']} |"
                )
            lines.append(
                f"\nAnalytic-envelope status for `{arm}`: "
                f"`{arm_result['analytic_envelope_status']}`."
            )
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
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    rows, parse_errors, rows_missing = load_jsonl(args.rows)
    fingerprint = campaign.runtime_fingerprint(args.project_root)
    summary = build_summary(
        manifest, rows, parse_errors, rows_missing, fingerprint, args.project_root
    )
    _atomic_write(
        args.json,
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )
    _atomic_write(args.markdown, markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "selected": summary["selected_current_case_count"],
        "decision": summary["decision"]["classification"],
    }, allow_nan=False))


if __name__ == "__main__":
    main()

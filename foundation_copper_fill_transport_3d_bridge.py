"""Frozen 24-case matched 2D-versus-3D Cu transport bridge.

The campaign is a dimensional mechanism screen.  It cannot authorize
morphology, a terminal model-family pivot, or a full-traveler claim.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import math
import os
import subprocess
import time
import traceback
from pathlib import Path

import numpy as np
import viennals._core as ls_core
import viennaps as ps
import viennaps._core as ps_core

import copper_fill_transport_3d as metrics3d


ps.Logger.setLogLevel(ps.LogLevel.ERROR)


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_copper_fill_transport_3d_bridge_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_3d_bridge_rows.jsonl"
)
EXACT_BINARY_PATH = Path(
    "/tmp/viennaps-copper-exact/viennaps/"
    "_core.cpython-313-darwin.so"
)
EXACT_BINARY_SHA256 = (
    "8970850eb6d3ffbd621a454e70b8d4504e4d9d7d6e953312915c92fdc1c87a8d"
)
CONTROL_NAME = "stick_0p0125_power_0p0_cap6400_control"
CANDIDATE_NAME = "stick_0p00625_power_0p0"
GEOMETRY_TIERS = ("continuity", "nominal_hbm")
PAIRED_BASE_SEEDS = (102000, 103000, 104000, 105000)
MAX_WORKERS = 2

CASE_FIELDS = (
    "manifest_version",
    "campaign",
    "labels",
    "simulation_dimension",
    "design",
    "bridge_role",
    "geometry_tier",
    "geometry",
    "layers",
    "model",
    "numerics",
    "target",
    "analysis",
    "reflection_convergence",
    "decision_policy",
    "provenance",
    "runtime_fingerprint",
    "rng_seed",
    "reflection_residual_upper_bound",
    "matched_2d_parent_case_id",
)


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_row_sha256(row):
    payload = json.dumps(
        row, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def case_id(case):
    payload = json.dumps(
        case, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def jsonable(value):
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def append_row(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _close(first, second, tolerance=1e-15):
    try:
        return math.isclose(
            float(first), float(second), rel_tol=0.0, abs_tol=tolerance
        )
    except (TypeError, ValueError):
        return False


def _resolve(project_root, path):
    path = Path(path)
    return path if path.is_absolute() else Path(project_root) / path


def runtime_fingerprint(project_root=ROOT):
    root = Path(project_root)
    return {
        "runner_sha256": _file_sha256(root / Path(__file__).name),
        "metrics_3d_sha256": _file_sha256(root / "copper_fill_transport_3d.py"),
        "patch_sha256": _file_sha256(
            root / "patches/viennaps-copper-suppression-fill.patch"
        ),
        "viennaps_binary_path": str(Path(ps_core.__file__).resolve()),
        "viennaps_binary_sha256": _file_sha256(ps_core.__file__),
        "viennals_binary_sha256": _file_sha256(ls_core.__file__),
    }


def _case_payload(row):
    return {field: row.get(field) for field in CASE_FIELDS}


def _logical_key(row):
    numerics = row.get("numerics", {})
    return (
        row.get("design"),
        row.get("geometry_tier"),
        int(numerics.get("max_reflections", -1)),
        int(row.get("rng_seed", -1)),
    )


def _parent_map(manifest):
    return {
        (
            item["design"],
            item["geometry_tier"],
            item["max_reflections"],
            item["rng_seed"],
        ): item
        for item in manifest["matched_2d_comparison"]["rows"]
    }


def expand_cases(manifest, fingerprint=None):
    fingerprint = runtime_fingerprint() if fingerprint is None else dict(fingerprint)
    parents = _parent_map(manifest)
    cases = []
    for design in manifest["designs"]:
        for max_reflections in design["reflection_arms"]:
            for tier in manifest["geometry_tiers"]:
                for seed in manifest["rng_seeds"]:
                    model = {**manifest["model"], **design["model"]}
                    numerics = {
                        **manifest["numerics"],
                        "max_reflections": max_reflections,
                    }
                    key = (design["name"], tier["name"], max_reflections, seed)
                    parent = parents.get(key)
                    case = {
                        "manifest_version": manifest["manifest_version"],
                        "campaign": manifest["campaign"],
                        "labels": manifest["labels"],
                        "simulation_dimension": manifest["simulation_dimension"],
                        "design": design["name"],
                        "bridge_role": design["bridge_role"],
                        "geometry_tier": tier["name"],
                        "geometry": {**manifest["geometry"], **tier["geometry"]},
                        "layers": manifest["layers"],
                        "model": model,
                        "numerics": numerics,
                        "target": manifest["target"],
                        "analysis": manifest["analysis"],
                        "reflection_convergence": manifest[
                            "reflection_convergence"
                        ],
                        "decision_policy": manifest["decision_policy"],
                        "provenance": manifest["provenance"],
                        "runtime_fingerprint": fingerprint,
                        "rng_seed": seed,
                        "reflection_residual_upper_bound": (
                            1.0 - float(model["suppressor_sticking_probability"])
                        ) ** int(max_reflections),
                        "matched_2d_parent_case_id": (
                            parent["parent_case_id"] if parent else None
                        ),
                    }
                    case["case_id"] = case_id(case)
                    cases.append(case)
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("3D bridge manifest generated duplicate case IDs")
    return cases


def _source_head(source_dir):
    try:
        return subprocess.check_output(
            ["git", "-C", str(source_dir), "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return None


def validate_runtime(manifest, project_root=ROOT):
    errors = []
    root = Path(project_root)
    provenance = manifest.get("provenance", {})
    actual_binary = Path(ps_core.__file__).resolve()
    if actual_binary != Path(provenance.get("viennaps_binary_path", "")).resolve():
        errors.append("active ViennaPS binary path differs from the exact Cu runtime")
    if not actual_binary.is_file() or _file_sha256(actual_binary) != provenance.get(
        "viennaps_binary_sha256"
    ):
        errors.append("active ViennaPS binary hash differs from the exact Cu runtime")
    if not hasattr(ps.d3, "CopperSuppressionFill"):
        errors.append("ps.d3.CopperSuppressionFill binding is unavailable")
    if _file_sha256(ls_core.__file__) != provenance.get("viennals_binary_sha256"):
        errors.append("active ViennaLS binary hash differs from provenance")
    patch = root / provenance.get("extension_patch_path", "")
    if not patch.is_file() or _file_sha256(patch) != provenance.get(
        "extension_patch_sha256"
    ):
        errors.append("CopperSuppressionFill patch hash differs")
    source = root / provenance.get("viennaps_source_path", "")
    if _source_head(source) != provenance.get("viennaps_source_commit"):
        errors.append("ViennaPS source checkout is missing or at the wrong commit")
    if source.is_dir() and patch.is_file():
        reverse = subprocess.run(
            ["git", "-C", str(source), "apply", "--reverse", "--check", str(patch)],
            capture_output=True,
            text=True,
            check=False,
        )
        if reverse.returncode != 0:
            errors.append("ViennaPS source is not in the exact patched state")
    return errors


def validate_manifest(manifest, cases=None, check_runtime=True):
    errors = []
    if manifest.get("manifest_version") != 1:
        errors.append("manifest_version must equal 1")
    if manifest.get("campaign") != "foundation-copper-fill-matched-3d-bridge":
        errors.append("campaign name differs from the frozen 3D bridge")
    if manifest.get("labels") != [
        "full-traveler",
        "critical-review",
        "matched-3d-transport",
    ]:
        errors.append("required campaign labels changed")
    if manifest.get("simulation_dimension") != 3:
        errors.append("simulation_dimension must be explicitly 3")
    if manifest.get("geometry") != {
        "radius": 0.15,
        "mask_height": 0.30,
        "x_extent": 1.0,
        "lateral_y_extent": 1.0,
        "mouth_offset": 0.02,
        "field_radius_band": [0.35, 0.45],
        "hole_shape": "FULL",
        "lateral_boundary": "REFLECTIVE",
        "vertical_boundary": "INFINITE",
    }:
        errors.append("full-cylinder geometry or boundary contract changed")
    if manifest.get("geometry_tiers") != [
        {"name": "continuity", "geometry": {"depth": 1.25}},
        {"name": "nominal_hbm", "geometry": {"depth": 3.0}},
    ]:
        errors.append("continuity/nominal geometry tiers changed")
    if manifest.get("layers") != {
        "liner": 0.03,
        "barrier": 0.01,
        "seed": 0.01,
    }:
        errors.append("ideal five-material stack changed")
    if manifest.get("model") != {
        "suppressor_sticking_probability": 0.00625,
        "suppressor_source_power": 0.0,
        "gas_mean_free_path": -1.0,
        "adsorption_strength": 40.0,
        "deactivation_rate": 0.25,
        "active_deposition_rate": 0.2,
        "suppressed_deposition_rate": 0.01,
    }:
        errors.append("base C model controls changed")
    expected_designs = [
        {
            "name": CONTROL_NAME,
            "bridge_role": "matched_cap_2d_3d_control",
            "model": {
                "suppressor_sticking_probability": 0.0125,
                "adsorption_strength": 20.0,
            },
            "reflection_arms": [800],
        },
        {
            "name": CANDIDATE_NAME,
            "bridge_role": "reflection_converged_2d_miss",
            "model": {
                "suppressor_sticking_probability": 0.00625,
                "adsorption_strength": 40.0,
            },
            "reflection_arms": [1600, 3200],
        },
    ]
    if manifest.get("designs") != expected_designs:
        errors.append("B/C design identities or reflection arms changed")
    for design in manifest.get("designs", []):
        model = {**manifest.get("model", {}), **design.get("model", {})}
        if not _close(
            model.get("adsorption_strength", math.nan)
            * model.get("suppressor_sticking_probability", math.nan),
            0.25,
        ):
            errors.append(f"{design.get('name')} no longer preserves K*s=0.25")
    if manifest.get("numerics") != {
        "grid_delta": 0.005,
        "rays_per_point": 2000,
        "max_reflections": 3200,
        "max_boundary_hits": 6400,
        "smoothing_neighbors": 1,
        "min_node_distance_factor": 0.05,
        "disk_radius": 0.0,
        "time_step_ratio": 0.4999,
        "checkpoint_interval": 0.025,
        "threads_per_worker": 1,
        "ignore_voids": True,
    }:
        errors.append("frozen 3D numerical controls changed")
    if tuple(manifest.get("rng_seeds", ())) != PAIRED_BASE_SEEDS:
        errors.append("paired base seed labels changed")
    if manifest.get("target") != {
        "max_balance_error": 1e-10,
        "analytic_parity_abs_tolerance": 1e-12,
    }:
        errors.append("diagnostic balance/parity targets changed")
    if manifest.get("analysis") != {
        "sector_count": 8,
        "sector_offsets_degrees": [0.0, 22.5],
        "minimum_sector_point_count": 50,
        "floor_to_lower_flux_ratio_upper_bound_strict": 0.95,
        "floor_to_lower_velocity_ratio_lower_bound_strict": 1.05,
        "height_axis": 2,
        "radial_axes": [0, 1],
        "mouth_offset": 0.02,
        "kinematic_gate": "min_floor_sector_velocity/max_wall_sector_velocity > H/min_mouth_radius",
        "analytic_envelope_status_on_flux_failure": "not_evaluated_preliminary_flux_gate_failed",
    }:
        errors.append("3D regional or H/a analysis contract changed")
    if manifest.get("reflection_convergence") != {
        "comparison_max_reflections": 1600,
        "authoritative_max_reflections": 3200,
        "reference_safety_factor": 10.0,
        "method": (
            "Pair identical 3D geometry-tier and RNG labels. Every hard-gate "
            "class must remain unchanged and every paired response delta must "
            "remain within its frozen absolute tolerance. The first four "
            "tolerances are inherited unchanged from the audited 2D boundary "
            "confirmation; the fifth uses the same dimensionless velocity-ratio "
            "tolerance as the lower-wall velocity response."
        ),
        "parent_B_pure_reflection_worst_absolute_effect": {
            "worst_floor_to_each_lower_flux_ratio": 0.000013152254139003894,
            "minimum_lower_minus_floor_coverage": 0.0000016063018598577727,
            "worst_floor_to_each_lower_velocity_ratio": 0.000014915255280523176,
            "minimum_floor_minus_middle_upper_velocity": 0.0000007478862363947611,
            "realized_min_floor_to_fastest_wall_velocity_ratio": 0.000014915255280523176,
        },
        "maximum_paired_absolute_delta": {
            "worst_floor_to_each_lower_flux_ratio": 0.00013152254139003894,
            "minimum_lower_minus_floor_coverage": 0.000016063018598577727,
            "worst_floor_to_each_lower_velocity_ratio": 0.00014915255280523176,
            "minimum_floor_minus_middle_upper_velocity": 0.000007478862363947611,
            "realized_min_floor_to_fastest_wall_velocity_ratio": 0.00014915255280523176,
        },
    }:
        errors.append("3D reflection-convergence tolerances changed")
    else:
        reflection = manifest["reflection_convergence"]
        for response, effect in reflection[
            "parent_B_pure_reflection_worst_absolute_effect"
        ].items():
            if not _close(
                reflection["maximum_paired_absolute_delta"][response],
                reflection["reference_safety_factor"] * effect,
            ):
                errors.append(
                    f"3D reflection tolerance is not 10x its reference effect: {response}"
                )
    policy = manifest.get("decision_policy", {})
    if policy != {
        "core_authority": "dimensional_transport_screen_only",
        "morphology_authorized": False,
        "terminal_model_family_pivot_authorized": False,
        "automatic_model_family_pivot_authorized": False,
        "automatic_additional_launch_authorized": False,
        "full_traveler_authorized": False,
        "process_recipe_authorized": False,
        "terminal_requirements": [
            "conditional_3d_numerical_arms",
            "boundary_cap_challenge",
            "four_unseen_seeds_on_both_tiers",
        ],
        "invalid_or_incomplete": "blocks_dimensional_inference",
        "mixed_sector_phase_or_reflection_class": "inconclusive",
        "same_seed_numbers_across_dimensions": (
            "matched_labels_not_common_random_numbers"
        ),
    }:
        errors.append("3D core decision authority or terminal guards changed")
    commissioning = manifest.get("commissioning", {})
    if commissioning != {
        "case_keys": [
            [CANDIDATE_NAME, "continuity", 1600, 102000],
            [CANDIDATE_NAME, "nominal_hbm", 3200, 102000],
        ],
        "authority": "runtime_and_memory_calibration_only",
        "matrix_changes": False,
    }:
        errors.append("two-cell commissioning selection or authority changed")
    provenance = manifest.get("provenance", {})
    for name, expected in {
        "viennaps_source_path": "ViennaPS",
        "viennaps_source_commit": "2956ed587984c6dc38be24c6e2390e10c9b2f0a7",
        "extension_patch_path": "patches/viennaps-copper-suppression-fill.patch",
        "extension_patch_sha256": "c0791af6f28a7e5214064f9e914f6c7c665e1c61ed730bc81caf7f097edd0d81",
        "viennaps_binary_path": str(EXACT_BINARY_PATH),
        "viennaps_binary_sha256": EXACT_BINARY_SHA256,
        "viennals_binary_sha256": "a92d0fabb3d1cf0e58edb5eb2e55576193a53c2c189b0db5217786d3a6f7fb2a",
        "dimensional_claim": "same normalized stack and controls; seed labels are not cross-dimensional common random numbers",
    }.items():
        if provenance.get(name) != expected:
            errors.append(f"qualified provenance changed: {name}")
    parent = manifest.get("matched_2d_comparison", {})
    for name, expected in {
        "source_manifest_sha256": "feaf595a701c71910312a450b9d63fdce9bb47231c4a1e9aa5b5723f69401c54",
        "source_rows_sha256": "e296cc59cda9bfa7cd1c232d0656eb00de805a960a427d88555e1fea3367bbd8",
        "source_summary_sha256": "ee918859226366638b2b4837eab40dae5e8c827db036cfccd91298c07e2a829d",
        "source_review_sha256": "86fe2b5d110ade358b57212078e4a46efa1daad9584dbff51d7489771e591a15",
        "source_runner_sha256": "2bf93fee08305154c75dd0fc4b5d7cd2a3fe1ed3e214d80ea54c1a40068f8790",
        "source_reviewer_sha256": "4669f908f6c5b5d3fda08fbfc30fbd85a2b948b894e45fa6b1206d04c29ce7b7",
    }.items():
        if parent.get(name) != expected:
            errors.append(f"matched 2D artifact provenance changed: {name}")
    parent_rows = parent.get("rows", [])
    expected_keys = {
        (design, tier, reflections, seed)
        for design, arms in ((CONTROL_NAME, (800,)), (CANDIDATE_NAME, (1600, 3200)))
        for tier in GEOMETRY_TIERS
        for reflections in arms
        for seed in PAIRED_BASE_SEEDS
    }
    observed_parent_keys = {
        (
            item.get("design"),
            item.get("geometry_tier"),
            item.get("max_reflections"),
            item.get("rng_seed"),
        )
        for item in parent_rows
    }
    if len(parent_rows) != 24 or observed_parent_keys != expected_keys:
        errors.append("matched 2D row map must contain the exact 24 bridge cells")
    cases = expand_cases(manifest, {"test": "fingerprint"}) if cases is None else cases
    observed_cases = [_logical_key(case) for case in cases]
    if len(observed_cases) != 24 or set(observed_cases) != expected_keys:
        errors.append("3D core must contain exactly the matched 24 logical cells")
    if len(observed_cases) != len(set(observed_cases)):
        errors.append("3D core contains duplicate logical cells")
    if any(case.get("matched_2d_parent_case_id") is None for case in cases):
        errors.append("a 3D case lacks its exact 2D comparison pointer")
    if manifest.get("runtime_estimate") != {
        "expected_logical_cases": 24,
        "new_3d_simulations": 24,
        "reused_2d_simulations": 0,
        "worker_cap": 2,
        "primary_ray_launches_per_flux_evaluation_estimate": 4176000000,
        "estimate_confidence": "low until two-cell commissioning",
    }:
        errors.append("3D runtime size, reuse count, or worker cap changed")
    if check_runtime:
        errors.extend(validate_runtime(manifest))
    return errors


def load_verified_2d_comparison(manifest, project_root=ROOT):
    root = Path(project_root)
    parent = manifest["matched_2d_comparison"]
    errors = []
    paths = {
        name: _resolve(root, parent[f"source_{name}_path"])
        for name in ("manifest", "rows", "summary", "review")
    }
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"matched 2D {name} artifact is missing: {path}")
        elif _file_sha256(path) != parent[f"source_{name}_sha256"]:
            errors.append(f"matched 2D {name} artifact hash mismatch")
    if _file_sha256(root / parent["source_runner_path"]) != parent[
        "source_runner_sha256"
    ]:
        errors.append("matched 2D runner source hash mismatch")
    if _file_sha256(root / parent["source_reviewer_path"]) != parent[
        "source_reviewer_sha256"
    ]:
        errors.append("matched 2D reviewer source hash mismatch")
    if errors:
        return {}, errors
    try:
        summary = json.loads(paths["summary"].read_text())
    except Exception as error:
        return {}, [f"matched 2D summary does not parse: {error}"]
    if summary.get("status") != "complete" or summary.get(
        "metric_valid_case_count"
    ) != 24:
        errors.append("matched 2D review is not complete 24/24 evidence")
    if summary.get("reviewer_sha256") != parent["source_reviewer_sha256"]:
        errors.append("matched 2D summary does not identify the hash-bound reviewer")
    if summary.get("decision", {}).get("classification") != (
        "two_dimensional_transport_no_go_requires_matched_3d_before_pivot"
    ):
        errors.append("matched 2D decision is not the frozen bridge trigger")
    if summary.get("reflection_convergence", {}).get("converged") is not True:
        errors.append("matched 2D C1600/C3200 reflection review is not converged")
    for label, arm in (
        ("B800", summary.get("parent_B_comparison", {})),
        ("C3200", summary.get("reflection_arms", {}).get("3200", {})),
    ):
        if not (
            arm.get("required_metrics_valid") is True
            and arm.get("stream_count") == 8
            and arm.get("classification") == "no_go"
            and arm.get("combined_2d_pass") is False
            and arm.get("all_eight_transport_sign_pass") is False
            and arm.get("broad_analytic_envelope", {}).get("evaluation_status")
            == "not_evaluated_preliminary_flux_gate_failed"
        ):
            errors.append(f"matched 2D {label} reviewed class is not the frozen no-go")
    directions = summary.get("multiresponse_paired_directions", {})
    expected_responses = {
        "worst_floor_to_each_lower_flux_ratio",
        "minimum_lower_minus_floor_coverage",
        "worst_floor_to_each_lower_velocity_ratio",
        "minimum_floor_minus_middle_upper_velocity",
    }
    direction_rows = directions.get("responses", {})
    if not (
        directions.get("eligible") is True
        and directions.get("paired_stream_count") == 8
        and set(direction_rows) == expected_responses
        and all(
            item.get("eligible") is True
            and item.get("paired_stream_count") == 8
            and isinstance(item.get("mean_oriented_improvement"), (int, float))
            and math.isfinite(float(item["mean_oriented_improvement"]))
            for item in direction_rows.values()
        )
    ):
        errors.append("matched 2D B-to-C response directions are ineligible")
    rows = []
    for line_number, line in enumerate(paths["rows"].read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception as error:
            errors.append(f"matched 2D rows line {line_number} does not parse: {error}")
    by_case = {row.get("case_id"): row for row in rows}
    if len(by_case) != len(rows):
        errors.append("matched 2D rows contain duplicate case IDs")
    verified = {}
    for item in parent["rows"]:
        row = by_case.get(item["parent_case_id"])
        key = (
            item["design"],
            item["geometry_tier"],
            item["max_reflections"],
            item["rng_seed"],
        )
        if row is None:
            errors.append(f"matched 2D row missing: {item['parent_case_id']}")
            continue
        numerics = row.get("numerics", {})
        if not (
            row.get("ok") is True
            and _logical_key(row) == key
            and _close(numerics.get("grid_delta"), 0.005)
            and numerics.get("rays_per_point") == 2000
            and numerics.get("max_boundary_hits") == 6400
        ):
            errors.append(f"matched 2D logical cell differs: {row.get('case_id')}")
        if _canonical_row_sha256(row) != item["parent_row_canonical_sha256"]:
            errors.append(f"matched 2D row hash mismatch: {row.get('case_id')}")
        if row.get("diagnostic_snapshot_path") != item["snapshot_path"] or row.get(
            "diagnostic_snapshot_sha256"
        ) != item["snapshot_sha256"]:
            errors.append(f"matched 2D snapshot declaration differs: {row.get('case_id')}")
        snapshot = _resolve(root, item["snapshot_path"])
        if not snapshot.is_file() or _file_sha256(snapshot) != item["snapshot_sha256"]:
            errors.append(f"matched 2D snapshot hash mismatch: {row.get('case_id')}")
        verified[key] = row
    if len(verified) != 24:
        errors.append("matched 2D comparison map is incomplete")
    return verified, errors


def _model_parameters(case):
    values = case["model"]
    params = ps.CopperSuppressionFillParams()
    params.suppressorStickingProbability = values[
        "suppressor_sticking_probability"
    ]
    params.suppressorSourcePower = values["suppressor_source_power"]
    params.gasMeanFreePath = values["gas_mean_free_path"]
    params.adsorptionStrength = values["adsorption_strength"]
    params.deactivationRate = values["deactivation_rate"]
    params.activeDepositionRate = values["active_deposition_rate"]
    params.suppressedDepositionRate = values["suppressed_deposition_rate"]
    params.platingMaterials = [metrics3d.cu_seed_material(), ps.Material.Cu]
    return params


def _set_process_parameters(process, case):
    numerics = case["numerics"]
    ray = ps.RayTracingParameters()
    ray.useRandomSeeds = False
    ray.rngSeed = int(case["rng_seed"]) + 1
    ray.raysPerPoint = int(numerics["rays_per_point"])
    ray.normalizationType = ps.NormalizationType.SOURCE
    ray.ignoreFluxBoundaries = False
    ray.maxReflections = int(numerics["max_reflections"])
    ray.maxBoundaryHits = int(numerics["max_boundary_hits"])
    ray.smoothingNeighbors = int(numerics["smoothing_neighbors"])
    ray.minNodeDistanceFactor = float(numerics["min_node_distance_factor"])
    ray.diskRadius = float(numerics["disk_radius"])
    process.setParameters(ray)
    advection = ps.AdvectionParameters()
    advection.ignoreVoids = bool(numerics["ignore_voids"])
    advection.timeStepRatio = float(numerics["time_step_ratio"])
    process.setParameters(advection)
    process.setFluxEngineType(ps.FluxEngineType.CPU_DISK)


def _model_diagnostics(model, case):
    raw = {
        "coordinates": np.asarray(model.getLastCoordinates(), dtype=float),
        "material_ids": np.asarray(model.getLastMaterialIds(), dtype=float),
        "suppressor_flux": np.asarray(model.getLastSuppressorFlux(), dtype=float),
        "coverage": np.asarray(model.getLastCoverage(), dtype=float),
        "velocity": np.asarray(model.getLastVelocity(), dtype=float),
        "adsorption_term": np.asarray(model.getLastAdsorptionTerm(), dtype=float),
        "deactivation_term": np.asarray(model.getLastDeactivationTerm(), dtype=float),
    }
    count = len(raw["coordinates"])
    if raw["coordinates"].shape != (count, 3) or count == 0:
        raise ValueError("3D model returned no aligned Nx3 diagnostic coordinates")
    for name, values in raw.items():
        if name == "coordinates":
            continue
        if values.shape != (count,):
            raise ValueError(f"3D diagnostic array does not align: {name}")
    if any(not np.all(np.isfinite(values)) for values in raw.values()):
        raise ValueError("3D model diagnostics contain nonfinite values")
    plating_ids = [
        float(metrics3d.cu_seed_material().legacyId()),
        float(ps.Material.Cu.legacyId()),
    ]
    plating = np.isin(raw["material_ids"], plating_ids)
    model_spec = case["model"]
    bounds_valid = bool(
        np.any(plating)
        and np.min(raw["suppressor_flux"]) >= 0.0
        and np.min(raw["coverage"]) >= 0.0
        and np.max(raw["coverage"]) <= 1.0
        and np.min(raw["velocity"][plating])
        >= float(model_spec["suppressed_deposition_rate"]) - 1e-12
        and np.max(raw["velocity"][plating])
        <= float(model_spec["active_deposition_rate"]) + 1e-12
        and (
            np.all(plating)
            or np.max(np.abs(raw["velocity"][~plating])) <= 1e-12
        )
    )
    return {
        "diagnostic_surface": "pre-final-advection surface",
        "point_count": count,
        "finite": True,
        "bounds_valid": bounds_valid,
        "relative_balance_error": float(model.getLastRelativeBalanceError()),
        "material_ids": sorted(np.unique(raw["material_ids"]).tolist()),
    }, raw, plating_ids


def _mesh_snapshot_fields(stage, meshes):
    fields = {
        f"{stage}_material_names": np.asarray(
            [mesh["material_name"] for mesh in meshes]
        ),
        f"{stage}_material_legacy_ids": np.asarray(
            [float(mesh["material"].legacyId()) for mesh in meshes], dtype=float
        ),
    }
    for index, mesh in enumerate(meshes):
        fields[f"{stage}_level_set_{index}_nodes"] = np.asarray(
            mesh["nodes"], dtype=float
        )
        fields[f"{stage}_level_set_{index}_triangles"] = np.asarray(
            mesh["triangles"], dtype=int
        )
    return fields


def _save_snapshot(
    snapshot_dir,
    case,
    before_meshes,
    after_meshes,
    boundary,
    diagnostics,
    raw,
):
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{case['case_id']}_c0001.npz"
    temporary = path.with_suffix(".npz.tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(
            handle,
            snapshot_schema_version=np.asarray([1], dtype=int),
            snapshot_case_id=np.asarray([case["case_id"]]),
            snapshot_case_payload_sha256=np.asarray([
                _canonical_row_sha256(_case_payload(case))
            ]),
            simulation_dimension=np.asarray([3], dtype=int),
            boundary_observed=np.asarray(boundary["observed"]),
            boundary_expected=np.asarray(boundary["expected"]),
            mesh_surface_stage=np.asarray(["complete pre/post five-level-set stack"]),
            diagnostic_surface_stage=np.asarray([diagnostics["diagnostic_surface"]]),
            diagnostic_coordinates=raw["coordinates"],
            diagnostic_material_ids=raw["material_ids"],
            diagnostic_suppressor_flux=raw["suppressor_flux"],
            diagnostic_coverage=raw["coverage"],
            diagnostic_velocity=raw["velocity"],
            diagnostic_adsorption_term=raw["adsorption_term"],
            diagnostic_deactivation_term=raw["deactivation_term"],
            diagnostic_relative_balance_error=np.asarray([
                diagnostics["relative_balance_error"]
            ]),
            **_mesh_snapshot_fields("pre", before_meshes),
            **_mesh_snapshot_fields("post", after_meshes),
        )
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    return path


def _snapshot_directory(output):
    return output.parent / f"{output.stem}_snapshots"


def _evidence_origin():
    return {
        "mode": "executed_matched_3d_bridge",
        "parent_simulation_reused": False,
        "matched_2d_row_reused_for_context_only": True,
        "cross_dimension_common_random_numbers": False,
    }


def _rng_stream(case):
    return {
        "base_seed_label": int(case["rng_seed"]),
        "checkpoint_seed": int(case["rng_seed"]) + 1,
        "paired_within_3d_arms": True,
        "cross_dimension_common_random_numbers": False,
    }


def _row_matches_case(row, case):
    return bool(
        isinstance(row, dict)
        and row.get("case_id") == case["case_id"]
        and row.get("case_id") == case_id(_case_payload(row))
        and all(row.get(field) == case.get(field) for field in CASE_FIELDS)
    )


def _completed_case_ids(path, cases):
    path = Path(path)
    if not path.exists():
        return set()
    expected = {case["case_id"]: case for case in cases}
    attempts = {case_id: [] for case_id in expected}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as error:
            raise ValueError(
                f"existing 3D rows line {line_number} is malformed: {error}"
            ) from error
        if not isinstance(row, dict):
            raise ValueError(
                f"existing 3D rows line {line_number} is not a JSON object"
            )
        case = expected.get(row.get("case_id"))
        if case is None:
            raise ValueError(
                f"existing 3D rows line {line_number} is an unexpected case"
            )
        if not _row_matches_case(row, case):
            raise ValueError(
                f"existing 3D rows line {line_number} has stale or changed payload"
            )
        if row.get("ok") not in (True, False):
            raise ValueError(
                f"existing 3D rows line {line_number} lacks a boolean status"
            )
        if row.get("evidence_origin") != _evidence_origin():
            raise ValueError(
                f"existing 3D rows line {line_number} has invalid evidence origin"
            )
        if row.get("rng_stream") != _rng_stream(case):
            raise ValueError(
                f"existing 3D rows line {line_number} has invalid RNG declaration"
            )
        attempts[case["case_id"]].append((line_number, row))
    completed = set()
    for current_case_id, case_attempts in attempts.items():
        successes = [
            (index, row)
            for index, (_, row) in enumerate(case_attempts)
            if row["ok"] is True
        ]
        if len(successes) > 1:
            raise ValueError(f"duplicate successful 3D case: {current_case_id}")
        if not successes:
            continue
        success_index, row = successes[0]
        if success_index != len(case_attempts) - 1:
            raise ValueError(
                f"successful 3D case has a later attempt: {current_case_id}"
            )
        declaration = row.get("diagnostic_snapshot_path")
        if not isinstance(declaration, str) or not declaration:
            raise ValueError(f"successful 3D case lacks a snapshot: {current_case_id}")
        snapshot = Path(declaration)
        expected_snapshot = _snapshot_directory(path) / f"{current_case_id}_c0001.npz"
        if snapshot.resolve() != expected_snapshot.resolve():
            raise ValueError(
                f"successful 3D case snapshot path differs: {current_case_id}"
            )
        if not snapshot.is_file() or row.get(
            "diagnostic_snapshot_sha256"
        ) != _file_sha256(snapshot):
            raise ValueError(
                f"successful 3D case snapshot hash differs: {current_case_id}"
            )
        completed.add(current_case_id)
    return completed


def run_case(task):
    case, snapshot_dir = task
    started = time.time()
    try:
        ps.setNumThreads(int(case["numerics"]["threads_per_worker"]))
        geometry = metrics3d.build_seeded_stack(case)
        boundary = metrics3d.boundary_contract(geometry)
        reference, before_meshes = metrics3d.reference_from_geometry(geometry, case)
        protected_before = before_meshes[:-1]
        if not boundary["pass"]:
            raise ValueError("3D domain boundary contract failed")

        model = ps.d3.CopperSuppressionFill(_model_parameters(case))
        process = ps.d3.Process(
            geometry, model, float(case["numerics"]["checkpoint_interval"])
        )
        _set_process_parameters(process, case)
        process.apply()

        metrics3d.validate_material_stack(geometry)
        after_meshes = metrics3d.level_set_surface_meshes(geometry)
        protected = metrics3d.protected_stack_delta(
            protected_before, after_meshes[:-1]
        )
        structure = metrics3d.surface_structure(after_meshes[-1], reference)
        diagnostics, raw, plating_ids = _model_diagnostics(model, case)
        parity = metrics3d.analytic_parity(raw, case["model"], plating_ids)
        parity_limit = float(case["target"]["analytic_parity_abs_tolerance"])
        parity_valid = all(
            value <= parity_limit
            for name, value in parity.items()
            if name.endswith("max_abs_error")
        )
        guards = {
            "diagnostic_balance_valid": bool(
                diagnostics["finite"]
                and diagnostics["bounds_valid"]
                and diagnostics["relative_balance_error"]
                <= float(case["target"]["max_balance_error"])
            ),
            "analytic_parity_valid": parity_valid,
            "full_cylinder_and_stack_valid": bool(
                boundary["pass"]
                and reference["seed_surface_connected"]
                and reference["cavity_open_at_mouth"]
                and metrics3d.material_stack_names(geometry)
                == metrics3d.EXPECTED_MATERIAL_NAMES
            ),
            "protected_stack_survives": protected["survives"],
            "cavity_remains_open_without_sealed_component": bool(
                structure["cavity_open"]
                and not structure["unexpected_sealed_component"]
            ),
        }
        phase_results = {}
        phase_regions = {}
        for offset in case["analysis"]["sector_offsets_degrees"]:
            label = f"offset_{float(offset):g}_degrees"
            regions, _ = metrics3d.region_statistics(
                raw["coordinates"],
                raw["material_ids"],
                raw["suppressor_flux"],
                raw["coverage"],
                raw["velocity"],
                plating_ids,
                reference,
                offset,
            )
            decision = metrics3d.transport_decision(
                regions,
                reference,
                int(case["analysis"]["minimum_sector_point_count"]),
                guards,
            )
            phase_regions[label] = regions
            phase_results[label] = decision
        phase_passes = [item["pass"] for item in phase_results.values()]
        phase_class_stable = len(set(phase_passes)) == 1

        snapshot = _save_snapshot(
            snapshot_dir,
            case,
            before_meshes,
            after_meshes,
            boundary,
            diagnostics,
            raw,
        )
        return jsonable({
            **case,
            "ok": True,
            "scope": "matched 3D one-checkpoint transport screen; not morphology",
            "production_doe_eligible": False,
            "morphology_ranking_eligible": False,
            "target_pass": False,
            "transport_screen_pass": None,
            "evidence_origin": _evidence_origin(),
            "reference": reference,
            "boundary_contract": boundary,
            "protected_stack": protected,
            "surface_structure": structure,
            "model_diagnostics": diagnostics,
            "analytic_law_parity": parity,
            "analysis_regions": phase_regions,
            "transport_sign_by_sector_phase": phase_results,
            "sector_phase_class_stable": phase_class_stable,
            "plating_material_legacy_ids": plating_ids,
            "diagnostic_snapshot_path": str(snapshot),
            "diagnostic_snapshot_sha256": _file_sha256(snapshot),
            "rng_stream": _rng_stream(case),
            "last_checkpoint": 1,
            "elapsed_s": time.time() - started,
        })
    except Exception as error:
        return jsonable({
            **case,
            "ok": False,
            "production_doe_eligible": False,
            "morphology_ranking_eligible": False,
            "target_pass": False,
            "transport_screen_pass": None,
            "evidence_origin": _evidence_origin(),
            "rng_stream": _rng_stream(case),
            "error": repr(error),
            "traceback": traceback.format_exc(),
            "elapsed_s": time.time() - started,
        })


def _commissioning_cases(cases, manifest):
    selected = {tuple(key) for key in manifest["commissioning"]["case_keys"]}
    result = [case for case in cases if _logical_key(case) in selected]
    if len(result) != 2:
        raise ValueError("commissioning mode must select exactly two frozen cases")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--commissioning",
        action="store_true",
        help="run only the two predeclared cells from the unchanged 24-case matrix",
    )
    args = parser.parse_args()
    if args.workers < 1 or args.workers > MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")
    manifest = json.loads(args.manifest.read_text())
    cases = expand_cases(manifest)
    errors = validate_manifest(manifest, cases)
    if errors:
        raise ValueError("invalid 3D bridge manifest: " + "; ".join(errors))
    _, parent_errors = load_verified_2d_comparison(manifest)
    if parent_errors:
        raise ValueError(
            "matched 2D comparison failed verification: "
            + "; ".join(parent_errors)
        )
    done = _completed_case_ids(args.output, cases)
    eligible = _commissioning_cases(cases, manifest) if args.commissioning else cases
    pending = [case for case in eligible if case["case_id"] not in done]
    print(
        f"logical=24 mode={'commissioning' if args.commissioning else 'full'} "
        f"eligible={len(eligible)} complete={len(done)} pending={len(pending)} "
        "authority=dimensional_transport_screen_only",
        flush=True,
    )
    if not pending:
        return
    tasks = [(case, _snapshot_directory(args.output)) for case in pending]
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, row in enumerate(executor.map(run_case, tasks), start=1):
            append_row(args.output, row)
            print(
                f"[{completed}/{len(tasks)}] {row['case_id']} "
                f"ok={row['ok']} elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

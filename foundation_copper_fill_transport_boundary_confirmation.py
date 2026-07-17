"""Confirm the fine copper-transport boundary and reflection cap."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import math
from pathlib import Path

import viennaps._core as ps_core

import foundation_copper_fill_transport_sign_screen as coarse
import foundation_metric_audit as foundation


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_copper_fill_transport_boundary_confirmation_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_boundary_confirmation_rows.jsonl"
)
CONTROL_NAME = "stick_0p0125_power_0p0_cap6400_control"
CANDIDATE_NAME = "stick_0p00625_power_0p0"
GEOMETRY_TIERS = ("continuity", "nominal_hbm")
REFLECTION_ARMS = (1600, 3200)
PAIRED_BASE_SEEDS = (102000, 103000, 104000, 105000)
MAX_WORKERS = 4

CASE_FIELDS = (
    "manifest_version",
    "campaign",
    "labels",
    "design",
    "boundary_role",
    "geometry_tier",
    "geometry",
    "layers",
    "model",
    "numerics",
    "target",
    "analysis",
    "decision_policy",
    "provenance",
    "runtime_fingerprint",
    "rng_seed",
    "reflection_residual_upper_bound",
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


def _resolve(project_root, path):
    path = Path(path)
    return path if path.is_absolute() else Path(project_root) / path


def _close(first, second, tolerance=1e-15):
    try:
        return math.isclose(
            float(first), float(second), rel_tol=0.0, abs_tol=tolerance
        )
    except (TypeError, ValueError):
        return False


def _runtime_fingerprint():
    root = Path(__file__).resolve().parent
    return {
        "runner_sha256": _file_sha256(root / Path(__file__).name),
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
        "viennaps_binary_sha256": _file_sha256(ps_core.__file__),
    }


def _logical_key(row):
    numerics = row.get("numerics", {})
    return (
        row.get("design"),
        row.get("geometry_tier"),
        int(numerics.get("max_reflections", -1)),
        int(row.get("rng_seed", -1)),
    )


def expand_cases(manifest, runtime_fingerprint=None):
    fingerprint = (
        _runtime_fingerprint()
        if runtime_fingerprint is None
        else dict(runtime_fingerprint)
    )
    cases = []
    for design in manifest["designs"]:
        for max_reflections in design["reflection_arms"]:
            for tier in manifest["geometry_tiers"]:
                for rng_seed in manifest["rng_seeds"]:
                    model = {**manifest["model"], **design["model"]}
                    numerics = {
                        **manifest["numerics"],
                        "max_reflections": max_reflections,
                    }
                    case = {
                    "manifest_version": manifest["manifest_version"],
                    "campaign": manifest["campaign"],
                    "labels": manifest["labels"],
                    "design": design["name"],
                    "boundary_role": design["boundary_role"],
                    "geometry_tier": tier["name"],
                    "geometry": {**manifest["geometry"], **tier["geometry"]},
                    "layers": manifest["layers"],
                    "model": model,
                    "numerics": numerics,
                    "target": manifest["target"],
                    "analysis": manifest["analysis"],
                    "decision_policy": manifest["decision_policy"],
                    "provenance": manifest["provenance"],
                    "runtime_fingerprint": fingerprint,
                    "rng_seed": rng_seed,
                    "reflection_residual_upper_bound": (
                        1.0
                        - float(model[
                            "suppressor_sticking_probability"
                        ])
                    ) ** int(max_reflections),
                    }
                    case["case_id"] = foundation.case_id(case)
                    cases.append(case)
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("boundary manifest contains duplicate case IDs")
    return cases


def validate_manifest(manifest, cases=None):
    errors = []
    if manifest.get("manifest_version") != 1:
        errors.append("manifest_version must equal 1")
    if manifest.get("campaign") != (
        "foundation-copper-fill-transport-lower-boundary-confirmation"
    ):
        errors.append("campaign name differs from the frozen boundary confirmation")
    if manifest.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("required generation labels changed")
    if manifest.get("geometry") != {
        "radius": 0.15,
        "mask_height": 0.3,
        "x_extent": 1.0,
        "field_sample_xs": [-0.4, -0.35, 0.35, 0.4],
        "mouth_offset": 0.02,
    }:
        errors.append("common full-2D geometry changed")
    if manifest.get("geometry_tiers") != [
        {"name": "continuity", "geometry": {"depth": 1.25, "y_extent": 1.6}},
        {"name": "nominal_hbm", "geometry": {"depth": 3.0, "y_extent": 3.5}},
    ]:
        errors.append("continuity/nominal geometry tiers changed")
    if manifest.get("layers") != {
        "liner": 0.03, "barrier": 0.01, "seed": 0.01
    }:
        errors.append("protected exact stack changed")
    frozen_model = {
        "suppressor_sticking_probability": 0.00625,
        "suppressor_source_power": 0.0,
        "gas_mean_free_path": -1.0,
        "adsorption_strength": 40.0,
        "deactivation_rate": 0.25,
        "active_deposition_rate": 0.2,
        "suppressed_deposition_rate": 0.01,
    }
    if manifest.get("model") != frozen_model:
        errors.append("s=0.00625/K=40 model controls changed")
    frozen_designs = [
        {
            "name": CONTROL_NAME,
            "boundary_role": "matched_boundary_hit_control",
            "model": {
                "suppressor_sticking_probability": 0.0125,
                "suppressor_source_power": 0.0,
                "adsorption_strength": 20.0,
            },
            "reflection_arms": [800],
            "K_times_sticking": 0.25,
            "pi_a": 5.0,
        },
        {
            "name": CANDIDATE_NAME,
            "boundary_role": "second_lower_sticking_expansion",
            "model": {
                "suppressor_sticking_probability": 0.00625,
                "suppressor_source_power": 0.0,
                "adsorption_strength": 40.0,
            },
            "reflection_arms": [1600, 3200],
            "K_times_sticking": 0.25,
            "pi_a": 5.0,
        },
    ]
    if manifest.get("designs") != frozen_designs:
        errors.append("matched control or boundary design identity changed")
    for design in manifest.get("designs", []):
        model = {**manifest.get("model", {}), **design.get("model", {})}
        pi_a = (
            model.get("adsorption_strength", math.nan)
            * model.get("suppressor_sticking_probability", math.nan)
            / (model.get("deactivation_rate", math.nan) * model.get(
                "active_deposition_rate", math.nan
            ))
        )
        if not _close(
            model.get("adsorption_strength", math.nan)
            * model.get("suppressor_sticking_probability", math.nan),
            0.25,
        ) or not _close(pi_a, 5.0):
            errors.append(f"{design.get('name')} does not preserve K*s=0.25/Pi_A=5")
    frozen_numerics = {
        "grid_delta": 0.005,
        "rays_per_point": 2000,
        "max_reflections": 1600,
        "max_boundary_hits": 6400,
        "smoothing_neighbors": 1,
        "min_node_distance_factor": 0.05,
        "disk_radius": 0.0,
        "time_step_ratio": 0.4999,
        "checkpoint_interval": 0.025,
        "max_duration": 0.025,
        "save_every": 1,
        "threads_per_worker": 1,
        "require_disjoint_replicate_rng_streams": True,
    }
    if manifest.get("numerics") != frozen_numerics:
        errors.append("non-reflection numerical controls changed")
    if manifest.get("reflection_arms") != [1600, 3200]:
        errors.append("reflection arms must remain [1600, 3200]")
    bounds = manifest.get("reflection_residual_bounds", {})
    expected_bounds = {
        CONTROL_NAME: {"800": (1.0 - 0.0125) ** 800},
        CANDIDATE_NAME: {
            "1600": (1.0 - 0.00625) ** 1600,
            "3200": (1.0 - 0.00625) ** 3200,
        },
    }
    for design, design_bounds in expected_bounds.items():
        for reflections, expected in design_bounds.items():
            if not _close(bounds.get(design, {}).get(reflections), expected):
                errors.append(f"reflection residual bound changed: {design}/{reflections}")
    if bounds.get("boundary_hit_cap") != 6400:
        errors.append("boundary-hit cap must remain 6400")
    if tuple(manifest.get("rng_seeds", ())) != PAIRED_BASE_SEEDS:
        errors.append("paired RNG streams changed")
    frozen_target = {
        "min_overburden": 0.15,
        "max_balance_error": 1e-10,
        "liner_min_thickness": 0.02,
        "liner_min_conformality": 0.995,
        "barrier_seed_min_thickness": 0.012,
        "barrier_seed_min_conformality": 0.985,
    }
    if manifest.get("target") != frozen_target:
        errors.append("target gates changed")
    frozen_analysis = {
        "pi_a": 5.0,
        "pi_a_definition": "adsorptionStrength*stickingProbability/(deactivationRate*activeDepositionRate)",
        "quantiles": [0.1, 0.5, 0.9],
        "floor_to_each_lower_flux_ratio_upper_bound_strict": 0.95,
        "floor_to_each_lower_velocity_ratio_lower_bound_strict": 1.05,
        "analytic_pi_a": [3.75, 5.0, 6.25],
        "analytic_suppressed_rate_R": [0.0, 0.01, 0.05, 0.2],
        "analytic_envelope_log10_pi_a": {
            "minimum": -6.0,
            "maximum": 6.0,
            "count": 97,
            "include_zero_and_infinite_limits": True,
        },
        "analytic_envelope_R_over_Va": [
            0.0, 0.000001, 0.0001, 0.001, 0.01, 0.05, 0.1,
            0.25, 0.5, 0.75, 0.9, 0.99, 1.0,
        ],
        "analytic_envelope_near_threshold_fraction": 0.8,
        "analytic_parity_abs_tolerance": 1e-12,
        "kinematic_threshold": "H/a from the exact post-seed cavity; floor velocity divided by the fastest of the six separate wall regions must exceed it on every paired stream",
    }
    if manifest.get("analysis") != frozen_analysis:
        errors.append("analysis gates or broad envelope changed")
    convergence = manifest.get("reflection_convergence", {})
    if convergence.get("authoritative_max_reflections") != 3200:
        errors.append("3200-reflection authority changed")
    if convergence.get("comparison_max_reflections") != 1600:
        errors.append("1600-reflection comparison arm changed")
    if convergence.get("maximum_paired_absolute_delta") != {
        "worst_floor_to_each_lower_flux_ratio": 0.00013152254139003894,
        "minimum_lower_minus_floor_coverage": 0.000016063018598577727,
        "worst_floor_to_each_lower_velocity_ratio": 0.00014915255280523176,
        "minimum_floor_minus_middle_upper_velocity": 0.000007478862363947611,
    }:
        errors.append("reflection convergence tolerances changed")
    if convergence.get("parent_B_pure_reflection_worst_absolute_effect") != {
        "worst_floor_to_each_lower_flux_ratio": 0.000013152254139003894,
        "minimum_lower_minus_floor_coverage": 0.0000016063018598577727,
        "worst_floor_to_each_lower_velocity_ratio": 0.000014915255280523176,
        "minimum_floor_minus_middle_upper_velocity": 7.478862363947611e-7,
    }:
        errors.append("parent reflection-effect evidence changed")
    tolerances = convergence.get("maximum_paired_absolute_delta", {})
    parent_effects = convergence.get(
        "parent_B_pure_reflection_worst_absolute_effect", {}
    )
    if set(tolerances) != set(parent_effects) or any(
        not _close(tolerances[name], 10.0 * parent_effects[name])
        for name in set(tolerances) & set(parent_effects)
    ):
        errors.append("reflection tolerances are not exactly 10x parent effects")
    parent = manifest.get("parent_comparison", {})
    for name, expected in {
        "reuse_count": 0,
        "source_manifest_sha256": "849e4966dc20e8a3f5611732cd456eb3f150d24dfe9de596cdfebd224e2df0dc",
        "source_rows_sha256": "1ce9e97ae833af8080073e66758cb0cf9a6cade4fa2efb8229f4120b6656f6e6",
        "source_summary_sha256": "276f1c891aaf5af050dcef3919e11278c2674588bc9301982a7d9ac4b35f02d6",
        "source_review_sha256": "b48f7923c92c07614e4138dc0eff95fd5da974b2e7932fee46a93ecf217bdf1e",
        "source_runner_sha256": "7774ff17683abaa9208c7cffdf6cc9bc2cca928f78eae6ab19b176ac3da01ecc",
        "source_reviewer_sha256": "a6de78e88451a3a0e4fb6cecae8f67e1c98bb9af0a5749e2e2b6b3fd138d74df",
    }.items():
        if parent.get(name) != expected:
            errors.append(f"parent comparison provenance changed: {name}")
    if parent.get("historical_comparison_cell") != {
        "design": "stick_0p0125_power_0p0",
        "grid_delta": 0.005,
        "rays_per_point": 2000,
        "max_reflections": 800,
    }:
        errors.append("historical parent comparison cell changed")
    parent_rows = parent.get("rows", [])
    if len(parent_rows) != 8 or {
        (item.get("geometry_tier"), item.get("rng_seed"))
        for item in parent_rows
    } != {
        (tier, seed) for tier in GEOMETRY_TIERS for seed in PAIRED_BASE_SEEDS
    }:
        errors.append("parent B comparison map must contain eight paired rows")
    if manifest.get("rejected_design") != {
        "name": "candidate_only_16_cells_with_inherited_maxBoundaryHits_1000",
        "logical_cells": 16,
        "decision": "rejected_before_launch",
        "reason": "maxBoundaryHits=1000 is below maxReflections 1600/3200, so the advertised absorption residual would not bound total ray termination. Raising the cap makes historical B rows non-exact; eight matched-cap B controls are therefore added instead of comparing against a boundary-cap-confounded parent.",
    }:
        errors.append("rejected 16-cell boundary-cap-confounded design changed")
    policy = manifest.get("decision_policy", {})
    if not all(policy.get(name) is False for name in (
        "automatic_morphology_authorized",
        "automatic_model_family_pivot_authorized",
        "automatic_further_boundary_launch_authorized",
    )):
        errors.append("an automatic downstream authority was enabled")
    if policy.get("matched_3d_required_before_morphology") is not True:
        errors.append("matched 3D gate before morphology changed")
    if policy.get("matched_3d_required_before_model_family_pivot") is not True:
        errors.append("matched 3D gate before model-family pivot changed")
    if not _close(
        policy.get("minimum_boundary_improvement_over_matched_control"),
        0.016714424655445925,
    ):
        errors.append("minimum continued-boundary improvement changed")
    runtime = manifest.get("runtime_estimate", {})
    if runtime.get("expected_logical_cases") != 24 or runtime.get(
        "new_simulations"
    ) != 24 or runtime.get("parent_reuse_simulations") != 0 or runtime.get(
        "worker_cap"
    ) != 4:
        errors.append("runtime size or worker cap changed")
    provenance = manifest.get("provenance", {})
    for name, expected in {
        "viennaps_source_commit": "2956ed587984c6dc38be24c6e2390e10c9b2f0a7",
        "extension_patch_sha256": "c0791af6f28a7e5214064f9e914f6c7c665e1c61ed730bc81caf7f097edd0d81",
        "viennaps_binary_sha256": "8970850eb6d3ffbd621a454e70b8d4504e4d9d7d6e953312915c92fdc1c87a8d",
    }.items():
        if provenance.get(name) != expected:
            errors.append(f"qualified build provenance changed: {name}")
    root = Path(__file__).resolve().parent
    patch = root / "patches/viennaps-copper-suppression-fill.patch"
    if not patch.is_file() or _file_sha256(patch) != provenance.get(
        "extension_patch_sha256"
    ):
        errors.append("active extension patch differs from provenance")
    if _file_sha256(ps_core.__file__) != provenance.get("viennaps_binary_sha256"):
        errors.append("active ViennaPS binary differs from provenance")
    if _file_sha256(root / "foundation_copper_fill_transport_confirmation.py") != parent.get(
        "source_runner_sha256"
    ):
        errors.append("parent comparison runner source drifted")
    if _file_sha256(root / "review_copper_fill_transport_confirmation.py") != parent.get(
        "source_reviewer_sha256"
    ):
        errors.append("parent comparison reviewer source drifted")

    cases = expand_cases(manifest, {"test": "manifest"}) if cases is None else cases
    expected_cells = {
        (design, tier, reflections, seed)
        for design, arms in (
            (CONTROL_NAME, (800,)),
            (CANDIDATE_NAME, REFLECTION_ARMS),
        )
        for tier in GEOMETRY_TIERS
        for reflections in arms
        for seed in PAIRED_BASE_SEEDS
    }
    observed = [_logical_key(case) for case in cases]
    if len(observed) != 24 or set(observed) != expected_cells:
        errors.append("boundary matrix must contain exactly 24 new logical cells")
    if len(observed) != len(set(observed)):
        errors.append("boundary matrix contains duplicate logical cells")
    effective_seeds = [int(seed) + 1 for seed in manifest.get("rng_seeds", [])]
    if len(effective_seeds) != len(set(effective_seeds)):
        errors.append("effective single-checkpoint RNG streams overlap")
    return errors


def load_verified_parent_comparison(manifest, project_root=None):
    root = Path(__file__).resolve().parent if project_root is None else Path(project_root)
    parent = manifest["parent_comparison"]
    errors = []
    paths = {
        name: _resolve(root, parent[f"source_{name}_path"])
        for name in ("manifest", "rows", "summary", "review")
    }
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"parent {name} artifact is missing: {path}")
        elif _file_sha256(path) != parent[f"source_{name}_sha256"]:
            errors.append(f"parent {name} artifact hash mismatch")
    if errors:
        return {}, errors
    try:
        source_manifest = json.loads(paths["manifest"].read_text())
        source_summary = json.loads(paths["summary"].read_text())
    except Exception as error:
        return {}, [f"parent JSON does not parse: {error}"]
    if source_manifest.get("labels") != manifest["labels"]:
        errors.append("parent labels differ")
    if source_summary.get("status") != "complete" or source_summary.get(
        "metric_valid_case_count"
    ) != 128:
        errors.append("parent summary is not the complete 128-cell review")
    decision = source_summary.get("decision", {})
    trigger = parent["trigger_evidence"]
    if decision.get("classification") != trigger["classification"]:
        errors.append("parent decision differs from the boundary trigger")
    source_trigger = decision.get("boundary_expansion_evidence", {})
    for name in (
        "design_A_high_fidelity_worst",
        "design_B_high_fidelity_worst",
        "B_improvement_over_A",
        "largest_absolute_paired_numerical_effect_or_interaction",
    ):
        manifest_name = {
            "design_A_high_fidelity_worst": "design_A_high_fidelity_worst_flux_ratio",
            "design_B_high_fidelity_worst": "design_B_high_fidelity_worst_flux_ratio",
        }.get(name, name)
        if not _close(source_trigger.get(name), trigger.get(manifest_name)):
            errors.append(f"parent trigger value differs: {name}")
    rows = []
    for line_number, line in enumerate(paths["rows"].read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception as error:
            errors.append(f"parent rows line {line_number} does not parse: {error}")
    by_case = {}
    for row in rows:
        if row.get("case_id") in by_case:
            errors.append(f"parent case duplicated: {row.get('case_id')}")
        by_case[row.get("case_id")] = row
    verified = {}
    cell = parent["historical_comparison_cell"]
    for item in parent["rows"]:
        row = by_case.get(item["parent_case_id"])
        if row is None:
            errors.append(f"parent comparison row missing: {item['parent_case_id']}")
            continue
        if _canonical_row_sha256(row) != item["parent_row_canonical_sha256"]:
            errors.append(f"parent row hash mismatch: {row.get('case_id')}")
        numerics = row.get("numerics", {})
        if not (
            row.get("ok") is True
            and row.get("design") == cell["design"]
            and row.get("geometry_tier") == item["geometry_tier"]
            and row.get("rng_seed") == item["rng_seed"]
            and _close(numerics.get("grid_delta"), cell["grid_delta"])
            and numerics.get("rays_per_point") == cell["rays_per_point"]
            and numerics.get("max_reflections") == cell["max_reflections"]
        ):
            errors.append(f"parent logical cell differs: {row.get('case_id')}")
        if row.get("diagnostic_snapshot_path") != item["snapshot_path"] or row.get(
            "diagnostic_snapshot_sha256"
        ) != item["snapshot_sha256"]:
            errors.append(f"parent snapshot declaration differs: {row.get('case_id')}")
        snapshot = _resolve(root, item["snapshot_path"])
        if not snapshot.is_file() or _file_sha256(snapshot) != item["snapshot_sha256"]:
            errors.append(f"parent snapshot hash mismatch: {row.get('case_id')}")
        verified[(item["geometry_tier"], item["rng_seed"])] = row
    if len(verified) != 8:
        errors.append("verified parent comparison is incomplete")
    return verified, errors


def _snapshot_directory(output):
    return output.parent / f"{output.stem}_snapshots"


def _completed_case_ids(path):
    path = Path(path)
    if not path.exists():
        return set()
    completed = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        snapshot_declaration = row.get("diagnostic_snapshot_path")
        if not isinstance(snapshot_declaration, str) or not snapshot_declaration:
            continue
        try:
            snapshot = Path(snapshot_declaration)
        except (TypeError, ValueError):
            continue
        if (
            row.get("ok") is True
            and isinstance(row.get("case_id"), str)
            and row.get("case_id")
            and snapshot.is_file()
            and row.get("diagnostic_snapshot_sha256") == _file_sha256(snapshot)
        ):
            completed.add(row["case_id"])
    return completed


def run_case(task):
    case, snapshot_dir = task
    row = coarse.run_case((case, snapshot_dir))
    row["evidence_origin"] = {
        "mode": "executed_boundary_confirmation",
        "reflection_residual_upper_bound": case[
            "reflection_residual_upper_bound"
        ],
        "parent_simulation_reused": False,
    }
    return foundation.jsonable(row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")
    manifest = json.loads(args.manifest.read_text())
    cases = expand_cases(manifest)
    errors = validate_manifest(manifest, cases)
    if errors:
        raise ValueError("invalid boundary manifest: " + "; ".join(errors))
    _, parent_errors = load_verified_parent_comparison(manifest)
    if parent_errors:
        raise ValueError("parent comparison verification failed: " + "; ".join(parent_errors))
    done = _completed_case_ids(args.output)
    pending = [case for case in cases if case["case_id"] not in done]
    print(
        f"logical={len(cases)} parent_reuse=0 complete={len(done)} pending={len(pending)}",
        flush=True,
    )
    if not pending:
        return
    tasks = [(case, _snapshot_directory(args.output)) for case in pending]
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, row in enumerate(executor.map(run_case, tasks), start=1):
            foundation.append_row(args.output, row)
            print(
                f"[{completed}/{len(tasks)}] {row['case_id']} ok={row['ok']} "
                f"elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

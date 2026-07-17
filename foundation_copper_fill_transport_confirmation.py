"""Confirm copper suppressor transport across numerical settings."""

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
    "foundation_copper_fill_transport_confirmation_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_confirmation_rows.jsonl"
)

DESIGN_NAMES = (
    "stick_0p025_power_0p0",
    "stick_0p0125_power_0p0",
)
GEOMETRY_TIERS = ("continuity", "nominal_hbm")
GRID_LEVELS = (0.01, 0.005)
RAY_LEVELS = (1000, 2000)
REFLECTION_LEVELS = (400, 800)
PAIRED_BASE_SEEDS = (102000, 103000, 104000, 105000)
HIGH_FIDELITY_CELL = {
    "grid_delta": 0.005,
    "rays_per_point": 2000,
    "max_reflections": 800,
}
MAX_WORKERS = 4

CASE_FIELDS = (
    "manifest_version",
    "campaign",
    "labels",
    "geometry_tier",
    "design",
    "boundary_role",
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


def _cell_key(case):
    return (
        case.get("design"),
        case.get("geometry_tier"),
        float(case.get("numerics", {}).get("grid_delta", math.nan)),
        int(case.get("numerics", {}).get("rays_per_point", -1)),
        int(case.get("numerics", {}).get("max_reflections", -1)),
        int(case.get("rng_seed", -1)),
    )


def _reuse_key(case):
    return case.get("geometry_tier"), int(case.get("rng_seed", -1))


def is_parent_reuse_case(case, manifest):
    reuse = manifest["parent_reuse"]["reuse_cell"]
    numerics = case["numerics"]
    return bool(
        case["design"] == reuse["design"]
        and _close(numerics["grid_delta"], reuse["grid_delta"])
        and numerics["rays_per_point"] == reuse["rays_per_point"]
        and numerics["max_reflections"] == reuse["max_reflections"]
    )


def expand_cases(manifest, runtime_fingerprint=None):
    fingerprint = (
        _runtime_fingerprint()
        if runtime_fingerprint is None
        else dict(runtime_fingerprint)
    )
    cases = []
    for design in manifest["designs"]:
        for grid_delta in manifest["numerical_factorial"]["grid_delta"]:
            for rays_per_point in manifest["numerical_factorial"][
                "rays_per_point"
            ]:
                for max_reflections in manifest["numerical_factorial"][
                    "max_reflections"
                ]:
                    for tier in manifest["geometry_tiers"]:
                        for rng_seed in manifest["rng_seeds"]:
                            model = {**manifest["model"], **design["model"]}
                            numerics = {
                                **manifest["numerics"],
                                "grid_delta": grid_delta,
                                "rays_per_point": rays_per_point,
                                "max_reflections": max_reflections,
                            }
                            case = {
                                "manifest_version": manifest["manifest_version"],
                                "campaign": manifest["campaign"],
                                "labels": manifest["labels"],
                                "geometry_tier": tier["name"],
                                "design": design["name"],
                                "boundary_role": design["boundary_role"],
                                "geometry": {
                                    **manifest["geometry"],
                                    **tier["geometry"],
                                },
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
                                    (1.0 - float(model[
                                        "suppressor_sticking_probability"
                                    ])) ** int(max_reflections)
                                ),
                            }
                            case["case_id"] = foundation.case_id(case)
                            cases.append(case)
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("manifest contains duplicate confirmation case IDs")
    return cases


def validate_manifest(manifest, cases=None):
    """Return every frozen-design violation; empty authorizes the 120 new cells."""
    errors = []
    if manifest.get("manifest_version") != 1:
        errors.append("manifest_version must equal 1")
    if manifest.get("campaign") != (
        "foundation-copper-fill-transport-numerical-confirmation"
    ):
        errors.append("campaign name differs from the frozen confirmation")
    if manifest.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("required generation labels are missing or reordered")

    frozen_geometry = {
        "radius": 0.15,
        "mask_height": 0.3,
        "x_extent": 1.0,
        "field_sample_xs": [-0.4, -0.35, 0.35, 0.4],
        "mouth_offset": 0.02,
    }
    frozen_tiers = [
        {"name": "continuity", "geometry": {"depth": 1.25, "y_extent": 1.6}},
        {"name": "nominal_hbm", "geometry": {"depth": 3.0, "y_extent": 3.5}},
    ]
    if manifest.get("geometry") != frozen_geometry:
        errors.append("common full-2D geometry differs from the frozen geometry")
    if manifest.get("geometry_tiers") != frozen_tiers:
        errors.append("paired continuity/nominal geometry tiers changed")
    if manifest.get("layers") != {
        "liner": 0.03,
        "barrier": 0.01,
        "seed": 0.01,
    }:
        errors.append("protected stack differs from the frozen exact stack")
    frozen_target = {
        "min_overburden": 0.15,
        "max_balance_error": 1e-10,
        "liner_min_thickness": 0.02,
        "liner_min_conformality": 0.995,
        "barrier_seed_min_thickness": 0.012,
        "barrier_seed_min_conformality": 0.985,
    }
    if manifest.get("target") != frozen_target:
        errors.append("target gates differ from the frozen confirmation target")

    expected_designs = [
        {
            "name": "stick_0p025_power_0p0",
            "boundary_role": "coarse_best_miss",
            "model": {
                "suppressor_sticking_probability": 0.025,
                "suppressor_source_power": 0.0,
                "adsorption_strength": 10.0,
            },
        },
        {
            "name": "stick_0p0125_power_0p0",
            "boundary_role": "lower_sticking_expansion",
            "model": {
                "suppressor_sticking_probability": 0.0125,
                "suppressor_source_power": 0.0,
                "adsorption_strength": 20.0,
            },
        },
    ]
    if manifest.get("designs") != expected_designs:
        errors.append("design names or frozen s/power/K coefficients changed")
    for design in manifest.get("designs", []):
        model = design.get("model", {})
        sticking = model.get("suppressor_sticking_probability")
        adsorption = model.get("adsorption_strength")
        if not _close(float(sticking) * float(adsorption), 0.25):
            errors.append(f"{design.get('name')} does not preserve K*s=0.25")

    factorial = manifest.get("numerical_factorial", {})
    if factorial.get("grid_delta") != [0.01, 0.005]:
        errors.append("grid factorial must be [0.01, 0.005]")
    if factorial.get("rays_per_point") != [1000, 2000]:
        errors.append("ray factorial must be [1000, 2000]")
    if factorial.get("max_reflections") != [400, 800]:
        errors.append("reflection truncation arm must be [400, 800]")
    if factorial.get("high_fidelity_cell") != HIGH_FIDELITY_CELL:
        errors.append("high-fidelity decision cell changed")
    if factorial.get("paired_effect_encoding") != {
        "grid_refinement": {"low": 0.01, "high": 0.005},
        "ray_refinement": {"low": 1000, "high": 2000},
        "reflection_refinement": {"low": 400, "high": 800},
    }:
        errors.append("paired factorial effect encoding changed")
    if tuple(manifest.get("rng_seeds", ())) != PAIRED_BASE_SEEDS:
        errors.append("four paired RNG streams changed")

    numerics = manifest.get("numerics", {})
    frozen_numerics = {
        "grid_delta": 0.01,
        "rays_per_point": 1000,
        "max_reflections": 400,
        "max_boundary_hits": 1000,
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
    if numerics != frozen_numerics:
        errors.append("non-factorial numerical controls changed")
    model = manifest.get("model", {})
    if model != {
        "suppressor_sticking_probability": 0.025,
        "suppressor_source_power": 0.0,
        "gas_mean_free_path": -1.0,
        "adsorption_strength": 10.0,
        "deactivation_rate": 0.25,
        "active_deposition_rate": 0.2,
        "suppressed_deposition_rate": 0.01,
    }:
        errors.append("base model controls changed")
    analysis = manifest.get("analysis", {})
    if not (
        _close(analysis.get("pi_a"), 5.0)
        and analysis.get("quantiles") == [0.1, 0.5, 0.9]
        and _close(
            analysis.get("floor_to_each_lower_flux_ratio_upper_bound_strict"),
            0.95,
        )
        and _close(
            analysis.get("floor_to_each_lower_velocity_ratio_lower_bound_strict"),
            1.05,
        )
        and _close(analysis.get("analytic_parity_abs_tolerance"), 1e-12)
        and _close(
            analysis.get("analytic_envelope_near_threshold_fraction"), 0.8
        )
    ):
        errors.append("analysis thresholds or parity guard changed")
    envelope = analysis.get("analytic_envelope_log10_pi_a", {})
    if envelope != {
        "minimum": -6.0,
        "maximum": 6.0,
        "count": 97,
        "include_zero_and_infinite_limits": True,
    }:
        errors.append("twelve-decade analytic envelope changed")
    if analysis.get("analytic_envelope_R_over_Va") != [
        0.0, 0.000001, 0.0001, 0.001, 0.01, 0.05, 0.1,
        0.25, 0.5, 0.75, 0.9, 0.99, 1.0,
    ]:
        errors.append("analytic R/Va envelope changed")

    bounds = manifest.get("reflection_residual_bounds", {})
    for design in expected_designs:
        name = design["name"]
        sticking = design["model"]["suppressor_sticking_probability"]
        for reflections in REFLECTION_LEVELS:
            observed = bounds.get(name, {}).get(str(reflections))
            expected = (1.0 - sticking) ** reflections
            if not _close(observed, expected):
                errors.append(
                    f"reflection residual bound changed: {name}/{reflections}"
                )

    reuse = manifest.get("parent_reuse", {})
    frozen_parent_hashes = {
        "source_manifest_sha256": "8de1df03adf902730f9b425141e311d185311c026b2be8732a68d998b59ffc25",
        "source_rows_sha256": "5bc5e441819a6b7e01493c493c2788e2cf1692083b96e570a0590e9a47b22141",
        "source_summary_sha256": "a9937f834d6e430e48638b57ac097a1f68b0bb6cd25d25f60127c68d6a629f48",
        "source_review_sha256": "5c19191e4ea07825a8137195cf850be82395c10f9c087fedbcc4b16f3b1532fe",
    }
    for name, expected in frozen_parent_hashes.items():
        if reuse.get(name) != expected:
            errors.append(f"frozen parent hash changed: {name}")
    compatibility = reuse.get("traveler_metrics_compatibility", {})
    if compatibility != {
        "parent_sha256": "e2d5cd51b58e485ce3a5b122d7e69f72a151a4b3c856ef441f1f0a1b302c2eec",
        "current_sha256": "7e34ab0449074be154a556e1a07ab275a9936b56a9964b2462c9a1505900bd20",
        "declared_change": "One standalone material_region_connectivity_2d helper was added after material_region_mesh; no import, global, pre-existing function, Cu-fill topology function, or regional function changed.",
        "functional_re_review_required": True,
        "functional_re_review": "Recompute regional statistics, equilibrium parity, fill topology, transition classification, and material-gating/protected-stack evidence from every reused raw snapshot with the current code and require exact/toleranced agreement with the saved parent row.",
    }:
        errors.append("traveler_metrics parent/current compatibility contract changed")
    current_tm = Path(__file__).resolve().parent / "traveler_metrics.py"
    if current_tm.is_file() and _file_sha256(current_tm) != compatibility.get(
        "current_sha256"
    ):
        errors.append("current traveler_metrics hash differs from the compatibility contract")
    if reuse.get("reuse_cell") != {
        "design": "stick_0p025_power_0p0",
        "grid_delta": 0.01,
        "rays_per_point": 1000,
        "max_reflections": 400,
    }:
        errors.append("parent reuse cell changed")
    reuse_rows = reuse.get("rows", [])
    if len(reuse_rows) != 8:
        errors.append("exactly eight parent rows must be frozen for reuse")
    expected_reuse_keys = {
        (tier, seed) for tier in GEOMETRY_TIERS for seed in PAIRED_BASE_SEEDS
    }
    observed_reuse_keys = {
        (item.get("geometry_tier"), item.get("rng_seed"))
        for item in reuse_rows
    }
    if observed_reuse_keys != expected_reuse_keys:
        errors.append("parent reuse map does not cover both tiers and four streams")
    if any(
        not item.get("parent_case_id")
        or not item.get("parent_row_canonical_sha256")
        or not item.get("snapshot_path")
        or not item.get("snapshot_sha256")
        for item in reuse_rows
    ):
        errors.append("parent reuse row/hash/snapshot provenance is incomplete")

    conditional = manifest.get("boundary_expansion", {}).get(
        "conditional_design", {}
    )
    expected_conditional = {
        "name": "stick_0p00625_power_0p0",
        "suppressor_sticking_probability": 0.00625,
        "suppressor_source_power": 0.0,
        "adsorption_strength": 40.0,
        "grid_delta": 0.005,
        "rays_per_point": 2000,
        "max_reflections": [1600, 3200],
        "reflection_residual_bounds": [
            (1.0 - 0.00625) ** 1600,
            (1.0 - 0.00625) ** 3200,
        ],
    }
    if conditional != expected_conditional:
        errors.append("conditional lower-bound expansion changed")
    if manifest.get("boundary_expansion", {}).get(
        "automatic_launch_authorized"
    ) is not False:
        errors.append("conditional boundary expansion must not auto-launch")
    policy = manifest.get("decision_policy", {})
    if policy.get("matched_3d_required_before_morphology") is not True:
        errors.append("matched 3D gate before morphology is missing")
    if policy.get("matched_3d_required_before_model_family_pivot") is not True:
        errors.append("matched 3D gate before a model-family pivot is missing")

    provenance = manifest.get("provenance", {})
    for name, expected in {
        "viennaps_source_commit": "2956ed587984c6dc38be24c6e2390e10c9b2f0a7",
        "extension_patch_sha256": "c0791af6f28a7e5214064f9e914f6c7c665e1c61ed730bc81caf7f097edd0d81",
        "viennaps_binary_sha256": "8970850eb6d3ffbd621a454e70b8d4504e4d9d7d6e953312915c92fdc1c87a8d",
    }.items():
        if provenance.get(name) != expected:
            errors.append(f"qualified build provenance changed: {name}")
    project_root = Path(__file__).resolve().parent
    patch_path = project_root / "patches/viennaps-copper-suppression-fill.patch"
    if not patch_path.is_file() or _file_sha256(patch_path) != provenance.get(
        "extension_patch_sha256"
    ):
        errors.append("active extension patch file differs from frozen provenance")
    if _file_sha256(ps_core.__file__) != provenance.get(
        "viennaps_binary_sha256"
    ):
        errors.append("active ViennaPS binary differs from frozen provenance")

    cases = (
        expand_cases(manifest, {"test": "manifest"})
        if cases is None
        else cases
    )
    observed = [_cell_key(case) for case in cases]
    expected = {
        (design, tier, grid, rays, reflections, seed)
        for design in DESIGN_NAMES
        for tier in GEOMETRY_TIERS
        for grid in GRID_LEVELS
        for rays in RAY_LEVELS
        for reflections in REFLECTION_LEVELS
        for seed in PAIRED_BASE_SEEDS
    }
    if len(observed) != 128 or set(observed) != expected:
        errors.append("confirmation matrix must contain exactly 128 logical cells")
    if len(set(observed)) != len(observed):
        errors.append("confirmation matrix contains duplicate logical cells")
    reuse_cases = [case for case in cases if is_parent_reuse_case(case, manifest)]
    if len(reuse_cases) != 8:
        errors.append("exactly eight logical cells must be parent reuse")
    if len(cases) - len(reuse_cases) != 120:
        errors.append("exactly 120 logical cells must require new execution")

    effective_seeds = [int(seed) + 1 for seed in manifest.get("rng_seeds", [])]
    if len(effective_seeds) != len(set(effective_seeds)):
        errors.append("single-checkpoint effective RNG streams overlap")
    if any(
        right - left <= 1
        for left, right in zip(effective_seeds, effective_seeds[1:])
    ):
        errors.append("paired base streams are not separated beyond the checkpoint horizon")
    return errors


def load_verified_parent_rows(manifest, project_root=None):
    """Return parent rows by (tier, seed), or all provenance errors."""
    root = Path(__file__).resolve().parent if project_root is None else Path(project_root)
    reuse = manifest["parent_reuse"]
    errors = []
    paths = {
        name: _resolve(root, reuse[f"source_{name}_path"])
        for name in ("manifest", "rows", "summary", "review")
    }
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"parent {name} artifact is missing: {path}")
        elif _file_sha256(path) != reuse[f"source_{name}_sha256"]:
            errors.append(f"parent {name} artifact hash mismatch")
    if errors:
        return {}, errors

    try:
        source_manifest = json.loads(paths["manifest"].read_text())
        source_summary = json.loads(paths["summary"].read_text())
    except Exception as error:
        return {}, [f"parent JSON artifact does not parse: {error}"]
    if source_manifest.get("labels") != manifest["labels"]:
        errors.append("parent manifest generation labels differ")
    if source_summary.get("status") != "complete":
        errors.append("parent summary is not complete")
    if source_summary.get("metric_valid_case_count") != 168:
        errors.append("parent summary does not retain 168 metric-valid cells")

    parent_rows = []
    for line_number, line in enumerate(paths["rows"].read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            parent_rows.append(json.loads(line))
        except Exception as error:
            errors.append(f"parent rows line {line_number} does not parse: {error}")
    by_case_id = {}
    for row in parent_rows:
        case_id = row.get("case_id")
        if case_id in by_case_id:
            errors.append(f"parent case_id is duplicated: {case_id}")
        by_case_id[case_id] = row

    verified = {}
    reuse_cell = reuse["reuse_cell"]
    for item in reuse["rows"]:
        key = (item["geometry_tier"], item["rng_seed"])
        row = by_case_id.get(item["parent_case_id"])
        if row is None:
            errors.append(f"frozen parent case is missing: {item['parent_case_id']}")
            continue
        if _canonical_row_sha256(row) != item["parent_row_canonical_sha256"]:
            errors.append(f"parent row canonical hash mismatch: {row.get('case_id')}")
        if row.get("ok") is not True:
            errors.append(f"parent row is not successful: {row.get('case_id')}")
        if row.get("labels") != manifest["labels"]:
            errors.append(f"parent row labels differ: {row.get('case_id')}")
        numerics = row.get("numerics", {})
        if not (
            row.get("design") == reuse_cell["design"]
            and row.get("geometry_tier") == item["geometry_tier"]
            and row.get("rng_seed") == item["rng_seed"]
            and _close(numerics.get("grid_delta"), reuse_cell["grid_delta"])
            and numerics.get("rays_per_point") == reuse_cell["rays_per_point"]
            and numerics.get("max_reflections") == reuse_cell["max_reflections"]
        ):
            errors.append(f"parent row logical cell differs: {row.get('case_id')}")
        if row.get("diagnostic_snapshot_path") != item["snapshot_path"]:
            errors.append(f"parent snapshot path differs: {row.get('case_id')}")
        if row.get("diagnostic_snapshot_sha256") != item["snapshot_sha256"]:
            errors.append(f"parent row snapshot hash differs: {row.get('case_id')}")
        snapshot = _resolve(root, item["snapshot_path"])
        if not snapshot.is_file():
            errors.append(f"parent snapshot is missing: {snapshot}")
        elif _file_sha256(snapshot) != item["snapshot_sha256"]:
            errors.append(f"parent snapshot file hash mismatch: {row.get('case_id')}")
        provenance = row.get("provenance", {})
        for name in (
            "viennaps_source_commit",
            "extension_patch_sha256",
            "viennaps_binary_sha256",
        ):
            if provenance.get(name) != manifest["provenance"].get(name):
                errors.append(
                    f"parent row qualified provenance differs: {row.get('case_id')}/{name}"
                )
        if row.get("runtime_fingerprint", {}).get(
            "traveler_metrics_sha256"
        ) != reuse["traveler_metrics_compatibility"]["parent_sha256"]:
            errors.append(
                f"parent traveler_metrics fingerprint differs: {row.get('case_id')}"
            )
        verified[key] = row
    if set(verified) != {
        (tier, seed) for tier in GEOMETRY_TIERS for seed in PAIRED_BASE_SEEDS
    }:
        errors.append("verified parent reuse map is incomplete")
    return verified, errors


def build_parent_reuse_row(case, parent_row, manifest):
    if not is_parent_reuse_case(case, manifest):
        raise ValueError("only the frozen A/0.01/1000/400 cell may reuse a parent")
    item = next(
        item
        for item in manifest["parent_reuse"]["rows"]
        if (item["geometry_tier"], item["rng_seed"]) == _reuse_key(case)
    )
    return foundation.jsonable({
        **case,
        "ok": True,
        "scope": "verified parent reuse for paired numerical confirmation",
        "production_doe_eligible": False,
        "morphology_ranking_eligible": False,
        "target_pass": False,
        "transport_screen_pass": None,
        "diagnostic_snapshot_path": item["snapshot_path"],
        "diagnostic_snapshot_sha256": item["snapshot_sha256"],
        "evidence_origin": {
            "mode": "verified_parent_reuse",
            "parent_case_id": parent_row["case_id"],
            "parent_row_canonical_sha256": item[
                "parent_row_canonical_sha256"
            ],
            "parent_rows_sha256": manifest["parent_reuse"][
                "source_rows_sha256"
            ],
            "parent_snapshot_sha256": item["snapshot_sha256"],
        },
        "elapsed_s": 0.0,
    })


def _snapshot_directory(output):
    return output.parent / f"{output.stem}_snapshots"


def _completed_case_ids(path):
    """Resume only a successful row whose referenced snapshot still matches."""
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
        snapshot = Path(row.get("diagnostic_snapshot_path", ""))
        if (
            row.get("ok") is True
            and row.get("case_id")
            and snapshot.is_file()
            and row.get("diagnostic_snapshot_sha256") == _file_sha256(snapshot)
        ):
            completed.add(row["case_id"])
    return completed


def materialize_parent_reuse(manifest, cases, output, project_root=None):
    """Append each verified parent pointer once; never rerun those eight cells."""
    parents, errors = load_verified_parent_rows(manifest, project_root)
    if errors:
        raise ValueError("parent reuse verification failed: " + "; ".join(errors))
    done = _completed_case_ids(output)
    appended = []
    for case in cases:
        if not is_parent_reuse_case(case, manifest) or case["case_id"] in done:
            continue
        row = build_parent_reuse_row(case, parents[_reuse_key(case)], manifest)
        foundation.append_row(Path(output), row)
        appended.append(row["case_id"])
    return appended


def run_case(task):
    case, snapshot_dir, manifest = task
    if is_parent_reuse_case(case, manifest):
        raise RuntimeError(
            "refusing to execute a frozen parent-reuse cell; verify and reuse it"
        )
    row = coarse.run_case((case, snapshot_dir))
    row["evidence_origin"] = {
        "mode": "executed_confirmation",
        "reflection_residual_upper_bound": case[
            "reflection_residual_upper_bound"
        ],
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
        raise ValueError("invalid transport confirmation manifest: " + "; ".join(errors))
    reused = materialize_parent_reuse(manifest, cases, args.output)
    done = _completed_case_ids(args.output)
    pending = [
        case
        for case in cases
        if case["case_id"] not in done and not is_parent_reuse_case(case, manifest)
    ]
    print(
        f"logical={len(cases)} parent_reused={sum(is_parent_reuse_case(case, manifest) for case in cases)} "
        f"new_reuse_rows={len(reused)} complete={len(done)} execute_pending={len(pending)}",
        flush=True,
    )
    if not pending:
        return

    tasks = [
        (case, _snapshot_directory(args.output), manifest) for case in pending
    ]
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

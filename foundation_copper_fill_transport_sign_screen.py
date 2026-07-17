"""Screen whether suppressor transport supports bottom-up growth."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import math
import time
import traceback
from pathlib import Path

import numpy as np
import viennaps as ps
import viennaps._core as ps_core

import foundation_copper_fill_trajectory as trajectory
import foundation_metric_audit as foundation
import review_copper_fill_regional_kinematics as regional
import tsv_process as tp


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_copper_fill_transport_sign_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_sign_rows.jsonl"
)

STICKING_LEVELS = (0.025, 0.05, 0.1, 0.2, 0.5, 0.8, 1.0)
SOURCE_POWER_LEVELS = (0.0, 1.0, 4.0)
PAIRED_BASE_SEEDS = (102000, 103000, 104000, 105000)
GEOMETRY_TIERS = ("continuity", "nominal_hbm")
REGION_NAMES = (
    "floor",
    "left_lower_wall",
    "right_lower_wall",
    "left_middle_wall",
    "right_middle_wall",
    "left_upper_wall",
    "right_upper_wall",
    "mouth_shoulder",
    "field",
)
WALL_REGION_NAMES = (
    "left_lower_wall",
    "right_lower_wall",
    "left_middle_wall",
    "right_middle_wall",
    "left_upper_wall",
    "right_upper_wall",
)
QUANTITIES = ("suppressor_flux", "coverage", "normal_velocity")
QUANTILES = (0.1, 0.5, 0.9)


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_fingerprint():
    root = Path(__file__).resolve().parent
    return {
        "runner_sha256": _file_sha256(root / Path(__file__).name),
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


def _token(value):
    text = f"{float(value):.3f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text.replace(".", "p")


def expected_design_name(sticking, source_power):
    return f"stick_{_token(sticking)}_power_{_token(source_power)}"


def expand_cases(manifest, runtime_fingerprint=None):
    fingerprint = (
        _runtime_fingerprint()
        if runtime_fingerprint is None
        else dict(runtime_fingerprint)
    )
    cases = []
    for tier in manifest["geometry_tiers"]:
        for design in manifest["designs"]:
            for seed in design["rng_seeds"]:
                case = {
                    "manifest_version": manifest["manifest_version"],
                    "labels": manifest["labels"],
                    "geometry_tier": tier["name"],
                    "design": design["name"],
                    "geometry": {
                        **manifest["geometry"],
                        **tier["geometry"],
                    },
                    "layers": manifest["layers"],
                    "model": {**manifest["model"], **design["model"]},
                    "numerics": {
                        **manifest["numerics"],
                        **design.get("numerics", {}),
                    },
                    "target": manifest["target"],
                    "analysis": manifest["analysis"],
                    "provenance": manifest["provenance"],
                    "runtime_fingerprint": fingerprint,
                    "rng_seed": seed,
                }
                case["case_id"] = foundation.case_id(case)
                cases.append(case)
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("manifest contains duplicate transport-sign case IDs")
    return cases


def _close(first, second, tolerance=1e-12):
    return math.isclose(
        float(first), float(second), rel_tol=0.0, abs_tol=tolerance
    )


def validate_manifest(manifest, cases=None):
    """Return all frozen-matrix violations; an empty list authorizes launch."""
    errors = []
    if manifest.get("manifest_version") != 8:
        errors.append(f"unexpected manifest_version: {manifest.get('manifest_version')}")
    if manifest.get("campaign") != "foundation-copper-fill-transport-sign-screen":
        errors.append(f"unexpected campaign: {manifest.get('campaign')}")
    if manifest.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("generation labels must be full-traveler and critical-review")
    cases = expand_cases(manifest, {"test": "manifest"}) if cases is None else cases

    frozen_geometry = {
        "radius": 0.15,
        "mask_height": 0.3,
        "x_extent": 1.0,
        "field_sample_xs": [-0.4, -0.35, 0.35, 0.4],
        "mouth_offset": 0.02,
    }
    frozen_tiers = [
        {
            "name": "continuity",
            "geometry": {"depth": 1.25, "y_extent": 1.6},
        },
        {
            "name": "nominal_hbm",
            "geometry": {"depth": 3.0, "y_extent": 3.5},
        },
    ]
    if manifest.get("geometry") != frozen_geometry:
        errors.append("common geometry differs from the frozen centered full-2D geometry")
    if manifest.get("geometry_tiers") != frozen_tiers:
        errors.append("geometry tiers must be paired continuity and nominal_hbm")
    if manifest.get("layers") != {
        "liner": 0.03,
        "barrier": 0.01,
        "seed": 0.01,
    }:
        errors.append("ideal protected layer stack differs from the frozen stack")

    model = manifest.get("model", {})
    numerics = manifest.get("numerics", {})
    analysis = manifest.get("analysis", {})
    frozen_model = {
        "suppressor_sticking_probability": 0.025,
        "suppressor_source_power": 0.0,
        "gas_mean_free_path": -1.0,
        "adsorption_strength": 10.0,
        "deactivation_rate": 0.25,
        "active_deposition_rate": 0.2,
        "suppressed_deposition_rate": 0.01,
    }
    if model != frozen_model:
        errors.append("base model coefficients differ from the frozen values")
    exact_values = {
        "deactivation_rate": 0.25,
        "active_deposition_rate": 0.2,
        "suppressed_deposition_rate": 0.01,
        "gas_mean_free_path": -1.0,
    }
    for name, expected in exact_values.items():
        if name not in model or not _close(model[name], expected):
            errors.append(f"model {name} must equal {expected:g}")
    numerical_values = {
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
    }
    for name, expected in numerical_values.items():
        if name not in numerics or not _close(numerics[name], expected):
            errors.append(f"numerics {name} must equal {expected:g}")
    if numerics.get("require_disjoint_replicate_rng_streams") is not True:
        errors.append("disjoint replicate RNG streams must be required")
    frozen_numerics = {
        **numerical_values,
        "require_disjoint_replicate_rng_streams": True,
    }
    if numerics != frozen_numerics:
        errors.append("numerical controls differ from the frozen one-checkpoint screen")
    frozen_target = {
        "min_overburden": 0.15,
        "max_balance_error": 1e-10,
        "liner_min_thickness": 0.02,
        "liner_min_conformality": 0.995,
        "barrier_seed_min_thickness": 0.012,
        "barrier_seed_min_conformality": 0.985,
    }
    if manifest.get("target") != frozen_target:
        errors.append("target and exact-stack gates differ from the frozen values")
    if tuple(analysis.get("quantiles", ())) != QUANTILES:
        errors.append(f"analysis quantiles must equal {QUANTILES}")
    if not _close(analysis.get("pi_a", math.nan), 5.0):
        errors.append("analysis pi_a must equal 5")
    if not _close(
        analysis.get("floor_to_each_lower_flux_ratio_upper_bound_strict", math.nan),
        0.95,
    ):
        errors.append("floor/lower flux threshold must remain strictly below 0.95")
    if not _close(
        analysis.get("floor_to_each_lower_velocity_ratio_lower_bound_strict", math.nan),
        1.05,
    ):
        errors.append("floor/lower velocity threshold must remain strictly above 1.05")
    if not _close(analysis.get("analytic_parity_abs_tolerance", math.nan), 1e-12):
        errors.append("analytic parity tolerance must equal 1e-12")
    if tuple(analysis.get("analytic_pi_a", ())) != (3.75, 5.0, 6.25):
        errors.append("analytic Pi_A levels must equal (3.75, 5, 6.25)")
    if tuple(analysis.get("analytic_suppressed_rate_R", ())) != (
        0.0,
        0.01,
        0.05,
        0.2,
    ):
        errors.append("analytic R levels must equal (0, .01, .05, .2)")
    envelope = analysis.get("analytic_envelope_log10_pi_a", {})
    if not (
        _close(envelope.get("minimum", math.nan), -6.0)
        and _close(envelope.get("maximum", math.nan), 6.0)
        and envelope.get("count") == 97
        and envelope.get("include_zero_and_infinite_limits") is True
    ):
        errors.append("analytic Pi_A envelope must be log10 [-6, 6] with 97 points and exact limits")
    if tuple(analysis.get("analytic_envelope_R_over_Va", ())) != (
        0.0,
        0.000001,
        0.0001,
        0.001,
        0.01,
        0.05,
        0.1,
        0.25,
        0.5,
        0.75,
        0.9,
        0.99,
        1.0,
    ):
        errors.append("analytic R/Va envelope differs from the frozen 13-level grid")
    if not _close(
        analysis.get("analytic_envelope_near_threshold_fraction", math.nan),
        0.8,
    ):
        errors.append("analytic near-threshold guard must equal 0.8 H/a")
    reflection_contract = analysis.get("ray_reflection_contract", {})
    if reflection_contract != {
        "minimum_sticking": 0.025,
        "coarse_max_reflections": 400,
        "unabsorbed_weight_upper_bound": (1.0 - 0.025) ** 400,
        "confirmation_max_reflections": [400, 800],
        "confirmation_800_bound": (1.0 - 0.025) ** 800,
    }:
        errors.append("ray-reflection truncation contract differs from the frozen bounds")

    provenance = manifest.get("provenance", {})
    frozen_provenance = {
        "viennaps_source_commit": "2956ed587984c6dc38be24c6e2390e10c9b2f0a7",
        "extension_patch_sha256": "c0791af6f28a7e5214064f9e914f6c7c665e1c61ed730bc81caf7f097edd0d81",
        "viennaps_binary_sha256": "8970850eb6d3ffbd621a454e70b8d4504e4d9d7d6e953312915c92fdc1c87a8d",
    }
    for key, expected_value in frozen_provenance.items():
        if provenance.get(key) != expected_value:
            errors.append(f"provenance {key} differs from the qualified build")
    if provenance.get("geometry_authority") != (
        "continuity and nominal_hbm must both clear; high_ar_stress remains a later robustness challenge"
    ):
        errors.append("geometry authority statement is missing or changed")
    if provenance.get("dimensional_authority") != (
        "matched 3D transport confirmation is required before terminal model-family qualification or pivot"
    ):
        errors.append("matched-3D authority statement is missing or changed")

    expected = {
        (tier, sticking, power, seed)
        for tier in ("continuity", "nominal_hbm")
        for sticking in STICKING_LEVELS
        for power in SOURCE_POWER_LEVELS
        for seed in PAIRED_BASE_SEEDS
    }
    observed = []
    for design in manifest["designs"]:
        if set(design.get("model", {})) != {
            "suppressor_sticking_probability",
            "suppressor_source_power",
            "adsorption_strength",
        }:
            errors.append(f"{design.get('name')} changes an unfrozen model field")
        if design.get("numerics"):
            errors.append(f"{design.get('name')} overrides frozen numerics")
    for case in cases:
        case_model = case["model"]
        sticking = float(case_model["suppressor_sticking_probability"])
        power = float(case_model["suppressor_source_power"])
        adsorption = float(case_model["adsorption_strength"])
        expected_name = expected_design_name(sticking, power)
        if case["design"] != expected_name:
            errors.append(
                f"design {case['design']} must be named {expected_name}"
            )
        if not _close(adsorption, 0.25 / sticking):
            errors.append(
                f"{case['design']} adsorption_strength must equal 0.25/sticking"
            )
        pi_a = (
            adsorption
            * sticking
            / (
                float(case_model["deactivation_rate"])
                * float(case_model["active_deposition_rate"])
            )
        )
        if not _close(pi_a, 5.0):
            errors.append(f"{case['design']} does not preserve Pi_A=5")
        observed.append((case["geometry_tier"], sticking, power, int(case["rng_seed"])))
    observed_set = set(observed)
    if len(observed) != 168:
        errors.append(f"expected 168 paired-tier cases, got {len(observed)}")
    if len(observed_set) != len(observed):
        errors.append("duplicate sticking/source-power/base-seed cells")
    missing = sorted(expected - observed_set)
    extra = sorted(observed_set - expected)
    if missing:
        errors.append(f"missing matrix cells: {missing}")
    if extra:
        errors.append(f"unexpected matrix cells: {extra}")
    seed_sets = {tuple(design.get("rng_seeds", ())) for design in manifest["designs"]}
    if seed_sets != {PAIRED_BASE_SEEDS}:
        errors.append("every design must use the same four paired base seeds")
    try:
        trajectory._validate_replicate_rng_streams(manifest)
    except Exception as error:
        errors.append(f"RNG stream contract failed: {error}")
    return errors


def _authoritative_region_masks(coordinates, reference):
    """Classify points with the frozen regional cuts."""
    coordinates = np.asarray(coordinates, dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] < 2:
        raise ValueError("diagnostic coordinates must be Nx2-or-greater")
    count = len(coordinates)
    zeros = np.zeros(1, dtype=float)
    base_masks = {
        name: np.zeros(count, dtype=bool) for name in regional.REGION_NAMES
    }
    for index, coordinate in enumerate(coordinates):
        singleton = regional.region_statistics(
            coordinate.reshape(1, -1), zeros, zeros, zeros, reference
        )
        for name in regional.REGION_NAMES:
            base_masks[name][index] = singleton[name]["point_count"] == 1

    geometry = regional._reference_geometry(reference)
    x = coordinates[:, 0]
    left = x < geometry["center_x"]
    right = x > geometry["center_x"]
    half_width = geometry["a"]
    if not _close(geometry["center_x"], 0.0):
        raise ValueError("trajectory far-field diagnostic assumes a centered via")
    far_field = np.abs(x) > float(reference["via_x_bounds"][1]) + half_width
    return {
        "floor": base_masks["floor"],
        "left_lower_wall": base_masks["lower_wall"] & left,
        "right_lower_wall": base_masks["lower_wall"] & right,
        "left_middle_wall": base_masks["mid_wall"] & left,
        "right_middle_wall": base_masks["mid_wall"] & right,
        "left_upper_wall": base_masks["upper_wall"] & left,
        "right_upper_wall": base_masks["upper_wall"] & right,
        # The existing near-via "field" cut samples the two mouth shoulders.
        "mouth_shoulder": base_masks["field"],
        "field": far_field,
    }


def _quantity_statistics(values, mask):
    selected = np.asarray(values, dtype=float)[mask]
    if not len(selected):
        return {
            "mean": None,
            "q10": None,
            "q50": None,
            "q90": None,
        }
    quantiles = np.quantile(selected, QUANTILES)
    return {
        "mean": float(np.mean(selected)),
        "q10": float(quantiles[0]),
        "q50": float(quantiles[1]),
        "q90": float(quantiles[2]),
    }


def detailed_region_statistics(
    coordinates,
    suppressor_flux,
    coverage,
    velocity,
    reference,
    diagnostic_summary=None,
    masks=None,
):
    """Return count, mean, and fixed quantiles in each audited region."""
    coordinates = np.asarray(coordinates, dtype=float)
    arrays = {
        "suppressor_flux": np.asarray(suppressor_flux, dtype=float),
        "coverage": np.asarray(coverage, dtype=float),
        "normal_velocity": np.asarray(velocity, dtype=float),
    }
    if any(values.shape != (len(coordinates),) for values in arrays.values()):
        raise ValueError("regional diagnostic arrays do not align")
    if not np.all(np.isfinite(coordinates)) or any(
        not np.all(np.isfinite(values)) for values in arrays.values()
    ):
        raise ValueError("regional diagnostic arrays contain nonfinite values")
    masks = (
        _authoritative_region_masks(coordinates, reference)
        if masks is None
        else masks
    )
    result = {
        name: {
            "point_count": int(np.count_nonzero(masks[name])),
            **{
                quantity: _quantity_statistics(values, masks[name])
                for quantity, values in arrays.items()
            },
        }
        for name in REGION_NAMES
    }

    # Fail immediately if future edits drift from the imported regional cuts.
    aggregate = regional.region_statistics(
        coordinates,
        arrays["suppressor_flux"],
        arrays["coverage"],
        arrays["normal_velocity"],
        reference,
    )
    mappings = {
        "floor": ("floor",),
        "lower_wall": ("left_lower_wall", "right_lower_wall"),
        "mid_wall": ("left_middle_wall", "right_middle_wall"),
        "upper_wall": ("left_upper_wall", "right_upper_wall"),
        "field": ("mouth_shoulder",),
    }
    for source_name, split_names in mappings.items():
        split_mask = np.logical_or.reduce([masks[name] for name in split_names])
        if int(np.count_nonzero(split_mask)) != aggregate[source_name]["point_count"]:
            raise ValueError(f"regional count drift for {source_name}")
        for quantity, values in arrays.items():
            imported_name = (
                "normal_velocity_mean"
                if quantity == "normal_velocity"
                else f"{quantity}_mean"
            )
            expected = aggregate[source_name][imported_name]
            actual = _quantity_statistics(values, split_mask)["mean"]
            if expected is None and actual is None:
                continue
            if expected is None or actual is None or not _close(expected, actual):
                raise ValueError(f"regional mean drift for {source_name}/{quantity}")

    if diagnostic_summary is not None:
        field = result["field"]
        summary_keys = {
            "suppressor_flux": "field_flux_mean",
            "coverage": "field_coverage_mean",
            "normal_velocity": "field_velocity_mean",
        }
        for quantity, key in summary_keys.items():
            expected = diagnostic_summary.get(key)
            actual = field[quantity]["mean"]
            if expected is None or actual is None or not _close(expected, actual):
                raise ValueError(f"far-field mean differs from model diagnostic: {quantity}")
    return result


def analytic_diagnostics(
    flux,
    material_ids,
    plating_material_ids,
    *,
    pi_a,
    deactivation_rate,
    active_rate,
    suppressed_rate,
):
    """Evaluate the exact equilibrium law on a saved C++ transport field."""
    flux = np.asarray(flux, dtype=float)
    material_ids = np.asarray(material_ids, dtype=float)
    if flux.shape != material_ids.shape:
        raise ValueError("flux and material IDs do not align")
    plating = np.isin(material_ids, np.asarray(plating_material_ids, dtype=float))
    adsorption = float(pi_a) * float(deactivation_rate) * float(active_rate) * flux
    local_active = np.where(plating, float(active_rate), 0.0)
    local_suppressed = np.where(plating, float(suppressed_rate), 0.0)
    coverage = np.zeros_like(flux)
    positive = adsorption > 0.0
    deactivation_active = float(deactivation_rate) * local_active
    quadratic = float(deactivation_rate) * (local_active - local_suppressed)
    scale = np.maximum(adsorption, deactivation_active)
    solvable = positive & (scale > 0.0)
    normalized_linear = np.zeros_like(flux)
    normalized_constant = np.zeros_like(flux)
    normalized_quadratic = np.zeros_like(flux)
    normalized_linear[solvable] = (
        adsorption[solvable] + deactivation_active[solvable]
    ) / scale[solvable]
    normalized_constant[solvable] = adsorption[solvable] / scale[solvable]
    normalized_quadratic[solvable] = quadratic[solvable] / scale[solvable]
    linear_root = solvable & (
        normalized_quadratic
        <= np.finfo(float).eps * normalized_linear
    )
    coverage[linear_root] = np.clip(
        normalized_constant[linear_root] / normalized_linear[linear_root],
        0.0,
        1.0,
    )
    quadratic_root = solvable & ~linear_root
    discriminant = np.maximum(
        0.0,
        normalized_linear[quadratic_root] ** 2
        - 4.0
        * normalized_quadratic[quadratic_root]
        * normalized_constant[quadratic_root],
    )
    denominator = normalized_linear[quadratic_root] + np.sqrt(discriminant)
    values = np.ones_like(denominator)
    valid_denominator = denominator > 0.0
    values[valid_denominator] = (
        2.0
        * normalized_constant[quadratic_root][valid_denominator]
        / denominator[valid_denominator]
    )
    coverage[quadratic_root] = np.clip(values, 0.0, 1.0)
    coverage[positive & (scale <= 0.0)] = 1.0
    velocity = local_active * (1.0 - coverage) + local_suppressed * coverage
    adsorption_term = adsorption * (1.0 - coverage)
    deactivation_term = float(deactivation_rate) * velocity * coverage
    scale = np.maximum.reduce([
        np.abs(adsorption_term),
        np.abs(deactivation_term),
        np.full_like(adsorption_term, np.finfo(float).eps),
    ])
    return {
        "coverage": coverage,
        "velocity": velocity,
        "adsorption_term": adsorption_term,
        "deactivation_term": deactivation_term,
        "relative_balance_error": float(
            np.max(np.abs(adsorption_term - deactivation_term) / scale)
        ),
    }


def _snapshot_directory(output):
    return output.parent / f"{output.stem}_snapshots"


def _completed_case_ids(path):
    """Resume only successful rows whose raw snapshot still matches its hash."""
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
        snapshot_path = Path(row.get("diagnostic_snapshot_path", ""))
        if (
            row.get("ok")
            and row.get("case_id")
            and snapshot_path.is_file()
            and row.get("diagnostic_snapshot_sha256")
            == _file_sha256(snapshot_path)
        ):
            completed.add(row["case_id"])
    return completed


def run_case(task):
    case, snapshot_dir = task
    started = time.time()
    try:
        if not hasattr(ps, "CopperSuppressionFill"):
            raise RuntimeError(
                "CopperSuppressionFill binding is unavailable; use the qualified build"
            )
        ps.setNumThreads(int(case["numerics"]["threads_per_worker"]))
        invariants = trajectory._validate_case_invariants(case)
        geometry = trajectory._build_seeded_stack(case)
        trajectory._validate_material_stack(geometry)
        reference = trajectory._reference_geometry(geometry, case)
        previous_mesh = trajectory.tm.raw_level_set_meshes(geometry)[-1]

        model = ps.CopperSuppressionFill(trajectory._model_parameters(case))
        process = ps.Process(
            geometry, model, float(case["numerics"]["checkpoint_interval"])
        )
        trajectory._set_process_parameters(process, case, 1)
        process.apply()

        meshes = trajectory.tm.raw_level_set_meshes(geometry)
        fill_mesh = meshes[-1]
        topology = trajectory._fill_topology_metrics_2d(
            fill_mesh,
            field_y=reference["field_y"],
            floor_y=reference["floor_y"],
            via_x_bounds=reference["via_x_bounds"],
            field_sample_xs=reference["field_sample_xs"],
            center_x=0.0,
            tolerance=0.1 * case["numerics"]["grid_delta"],
            initial_cavity_area=reference["initial_cavity_area"],
            grid_delta=case["numerics"]["grid_delta"],
            mouth_sample_y=reference["mouth_sample_y"],
            area_sample_count=reference["metric_sampling"]["area_sample_count"],
            overburden_sample_count=reference["metric_sampling"][
                "overburden_sample_count"
            ],
        )
        transition = trajectory._topology_transition_check(
            reference["initial_topology"],
            topology,
            invariants,
            case["numerics"]["grid_delta"],
            previous_mesh=previous_mesh,
            reference=reference,
        )
        protected = trajectory._protected_stack_delta(
            reference["protected_meshes"], meshes[:-1]
        )
        diagnostic_summary, raw = trajectory._model_diagnostics(
            model, reference, case
        )
        regions = detailed_region_statistics(
            raw["coordinates"],
            raw["suppressor_flux"],
            raw["coverage"],
            raw["velocity"],
            reference,
            diagnostic_summary=diagnostic_summary,
        )
        elapsed = float(case["numerics"]["checkpoint_interval"])
        snapshot_path = trajectory._save_fill_snapshot(
            snapshot_dir,
            case["case_id"],
            1,
            elapsed,
            fill_mesh,
            diagnostic_summary,
            raw,
        )
        snapshot_sha256 = _file_sha256(snapshot_path)
        checkpoint = foundation.jsonable({
            "checkpoint": 1,
            "elapsed": elapsed,
            "topology": topology,
            "topology_transition": transition,
            "protected_stack": protected,
            "model_diagnostics": diagnostic_summary,
            "analysis_regions": regions,
            "snapshot_path": snapshot_path,
        })
        plating_material_ids = sorted({
            float(tp.CU_SEED_MATERIAL.legacyId()),
            float(ps.Material.Cu.legacyId()),
        })
        return foundation.jsonable({
            **case,
            "ok": True,
            "scope": "one-checkpoint uncalibrated transport-sign diagnostic",
            "production_doe_eligible": False,
            "morphology_ranking_eligible": False,
            "target_pass": False,
            "transport_screen_pass": None,
            "reference": {
                key: value
                for key, value in reference.items()
                if key != "protected_meshes"
            },
            "trajectory": [checkpoint],
            "last_checkpoint": 1,
            "numerical_invariants": invariants,
            "plating_material_legacy_ids": plating_material_ids,
            "diagnostic_snapshot_path": snapshot_path,
            "diagnostic_snapshot_sha256": snapshot_sha256,
            "rng_stream": {
                "base_seed": int(case["rng_seed"]),
                "checkpoint_seed": int(case["rng_seed"]) + 1,
                "paired_across_designs": True,
            },
            "elapsed_s": time.time() - started,
        })
    except Exception as error:
        return foundation.jsonable({
            **case,
            "ok": False,
            "production_doe_eligible": False,
            "morphology_ranking_eligible": False,
            "error": repr(error),
            "traceback": traceback.format_exc(),
            "elapsed_s": time.time() - started,
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    cases = expand_cases(manifest)
    manifest_errors = validate_manifest(manifest, cases)
    if manifest_errors:
        raise ValueError("invalid transport-sign manifest: " + "; ".join(manifest_errors))
    done = _completed_case_ids(args.output)
    pending = [case for case in cases if case["case_id"] not in done]
    if args.limit is not None:
        pending = pending[: args.limit]
    print(
        f"manifest cases={len(cases)} complete={len(done)} pending={len(pending)}",
        flush=True,
    )
    if not pending:
        return

    tasks = [(case, _snapshot_directory(args.output)) for case in pending]
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, row in enumerate(executor.map(run_case, tasks), start=1):
            foundation.append_row(args.output, row)
            print(
                f"[{completed}/{len(tasks)}] {row['case_id']} "
                f"ok={row['ok']} elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

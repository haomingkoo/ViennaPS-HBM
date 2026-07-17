"""Checkpointed ideal-stack qualification for CopperSuppressionFill.

This is a model-mechanism qualification, not a calibrated electroplating DOE.
It uses a full 2D trench so centerline voids are not clipped by symmetry.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import math
import os
import time
import traceback
from pathlib import Path

import numpy as np
import viennaps as ps
import viennaps._core as ps_core

import foundation_metric_audit as foundation
import traveler_metrics as tm
import tsv_process as tp


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/copper_fill_trajectory_rows.jsonl"
)


def _expected_material_stack():
    return (
        ps.Material.Si,
        ps.Material.SiO2,
        ps.Material.TaN,
        tp.CU_SEED_MATERIAL,
        ps.Material.Cu,
    )


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_fingerprint():
    project_root = Path(__file__).resolve().parent
    return {
        "runner_sha256": _file_sha256(project_root / Path(__file__).name),
        "traveler_metrics_sha256": _file_sha256(
            project_root / "traveler_metrics.py"
        ),
        "tsv_process_sha256": _file_sha256(project_root / "tsv_process.py"),
        "viennaps_binary_sha256": _file_sha256(ps_core.__file__),
    }


def _validate_material_stack(geometry):
    expected = _expected_material_stack()
    if geometry.getNumberOfLevelSets() != len(expected):
        raise ValueError(
            f"expected {len(expected)} material levels, "
            f"got {geometry.getNumberOfLevelSets()}"
        )
    material_map = geometry.getMaterialMap()
    actual = tuple(
        material_map.getMaterialAtIdx(index)
        for index in range(geometry.getNumberOfLevelSets())
    )
    if actual != expected:
        raise ValueError(f"unexpected material stack: {actual}")
    return actual


def expand_cases(manifest):
    cases = []
    runtime_fingerprint = _runtime_fingerprint()
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
                "runtime_fingerprint": runtime_fingerprint,
                "rng_seed": seed,
            }
            case["case_id"] = foundation.case_id(case)
            cases.append(case)
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("manifest contains duplicate Cu-fill trajectory cases")
    return cases


def _validate_replicate_rng_streams(manifest):
    """Reject overlapping base+checkpoint RNG schedules when requested."""
    if not manifest.get("numerics", {}).get(
        "require_disjoint_replicate_rng_streams", False
    ):
        return None
    seed_sets = [tuple(design["rng_seeds"]) for design in manifest["designs"]]
    if not seed_sets or any(seeds != seed_sets[0] for seeds in seed_sets[1:]):
        raise ValueError(
            "paired comparisons require the same replicate base seeds in "
            "every design"
        )
    seeds = seed_sets[0]
    if len(set(seeds)) != len(seeds):
        raise ValueError("replicate base seeds must be unique")
    max_checkpoint_count = max(
        int(math.ceil(
            float({**manifest["numerics"], **design.get("numerics", {})}[
                "max_duration"
            ])
            / float({**manifest["numerics"], **design.get("numerics", {})}[
                "checkpoint_interval"
            ])
        ))
        for design in manifest["designs"]
    )
    for index, first in enumerate(seeds):
        for second in seeds[index + 1:]:
            if abs(int(second) - int(first)) <= max_checkpoint_count:
                raise ValueError(
                    "replicate RNG streams overlap under rngSeed=base+checkpoint: "
                    f"bases {first} and {second} are not separated by more than "
                    f"{max_checkpoint_count} checkpoints"
                )
    return {
        "base_seeds": list(seeds),
        "max_checkpoint_count": max_checkpoint_count,
        "minimum_base_seed_separation": min(
            abs(int(second) - int(first))
            for index, first in enumerate(seeds)
            for second in seeds[index + 1:]
        ) if len(seeds) > 1 else None,
        "paired_across_designs": True,
        "checkpoint_seed_ranges_disjoint": True,
    }


def _validate_case_invariants(case):
    numerics = case["numerics"]
    max_front_displacement = (
        case["model"]["active_deposition_rate"]
        * numerics["checkpoint_interval"]
    )
    max_front_cells = max_front_displacement / numerics["grid_delta"]
    if max_front_cells > 1.0 + 1e-12:
        raise ValueError(
            "checkpoint interval permits more than one grid cell of active "
            f"front motion: {max_front_cells} cells"
        )
    return {
        "max_front_displacement": max_front_displacement,
        "max_front_cells_per_checkpoint": max_front_cells,
        "void_interfaces_frozen": True,
        "full_2d_cross_section": True,
    }


def _topology_transition_check(
    previous_topology,
    current_topology,
    numerical_invariants,
    grid_delta,
    previous_mesh=None,
    reference=None,
):
    """Classify large depth jumps as resolved motion, seam risk, or loss."""
    previous_depth = float(previous_topology["open_void_depth"])
    current_depth = float(current_topology["open_void_depth"])
    observed_depth_drop = max(0.0, previous_depth - current_depth)
    allowed_depth_drop = (
        numerical_invariants["max_front_displacement"] + 2.0 * grid_delta
    )
    closed_void_created = bool(
        current_topology["closed_void_count"]
        > previous_topology["closed_void_count"]
    )
    disappearing_tail_max_width = None
    disappearing_tail_height = observed_depth_drop
    closure_width_bound = (
        2.0 * numerical_invariants["max_front_displacement"] + grid_delta
    )
    if (
        previous_topology["open_void"]
        and observed_depth_drop > allowed_depth_drop + 1e-12
        and previous_mesh is not None
        and reference is not None
    ):
        lower_y = reference["field_y"] - previous_depth
        upper_y = reference["field_y"] - current_depth
        sample_count = max(
            8,
            int(math.ceil((upper_y - lower_y) / (0.5 * grid_delta))),
        )
        sample_edges = np.linspace(lower_y, upper_y, sample_count + 1)
        sample_ys = 0.5 * (sample_edges[:-1] + sample_edges[1:])
        widths = []
        for sample_y in sample_ys:
            intersections = tm.line_intersections_at_y(
                previous_mesh["nodes"],
                previous_mesh["lines"],
                sample_y,
                x_bounds=reference["via_x_bounds"],
            )
            left = intersections[intersections <= 0.0]
            right = intersections[intersections >= 0.0]
            if len(left) and len(right):
                widths.append(float(np.min(right) - np.max(left)))
        if widths:
            disappearing_tail_max_width = max(widths)

    depth_motion_resolved = bool(
        not previous_topology["open_void"]
        or observed_depth_drop <= allowed_depth_drop + 1e-12
    )
    narrow_tail_merger = bool(
        not depth_motion_resolved
        and not closed_void_created
        and disappearing_tail_max_width is not None
        and disappearing_tail_max_width <= closure_width_bound + 1e-12
    )
    if depth_motion_resolved:
        classification = "resolved_front_motion"
        valid = True
        reason = None
    elif closed_void_created:
        classification = "resolved_closed_void_creation"
        valid = True
        reason = None
    elif narrow_tail_merger:
        classification = "unresolved_narrow_tail_merger"
        valid = False
        reason = (
            "opposing fronts removed a long sub-resolution tail; seam-free "
            "closure cannot be certified"
        )
    else:
        classification = "nonconservative_or_unmeasurable_cavity_loss"
        valid = False
        reason = (
            "open cavity disappeared faster than bounded front motion without "
            "a resolved narrow-tail or closed-void transition"
        )
    return {
        "valid": valid,
        "classification": classification,
        "previous_open_void_depth": previous_depth,
        "current_open_void_depth": current_depth,
        "observed_open_void_depth_drop": observed_depth_drop,
        "allowed_open_void_depth_drop": allowed_depth_drop,
        "closed_void_created": closed_void_created,
        "disappearing_tail_height": disappearing_tail_height,
        "disappearing_tail_max_width": disappearing_tail_max_width,
        "disappearing_tail_aspect_ratio": (
            disappearing_tail_height
            / max(disappearing_tail_max_width, 1e-15)
            if disappearing_tail_max_width is not None
            else None
        ),
        "closure_width_bound": closure_width_bound,
        "unresolved_seam_risk": narrow_tail_merger,
        "reason": reason,
    }


def _fill_topology_metrics_2d(mesh, **kwargs):
    """Keep degenerate closed mesh fragments visible as invalid topology."""
    summaries = tm.component_summaries(mesh["nodes"], mesh["lines"])
    degenerate = [
        summary
        for summary in summaries
        if summary["closed"] and summary["node_count"] < 3
    ]
    lines = mesh["lines"]
    if degenerate:
        blocked_nodes = set()
        for summary in degenerate:
            blocked_nodes.update(summary["node_indices"].tolist())
        lines = np.asarray([
            edge
            for edge in np.asarray(lines, dtype=int)
            if not (
                int(edge[0]) in blocked_nodes
                and int(edge[1]) in blocked_nodes
            )
        ], dtype=int)
    metrics = tm.fill_topology_metrics_2d(
        mesh["nodes"],
        lines,
        **kwargs,
    )
    if degenerate:
        metrics["degenerate_closed_component_count"] = len(degenerate)
        metrics["unexpected_component_count"] += len(degenerate)
        metrics["component_count"] += len(degenerate)
        metrics["seam_or_mesh_defect"] = True
        metrics["topology_valid"] = False
        metrics["void_free"] = False
    else:
        metrics["degenerate_closed_component_count"] = 0
    return metrics


def _surface_height(mesh, x):
    value = tm.surface_height_at_x(mesh["nodes"], mesh["lines"], x)
    if value is None:
        raise ValueError(f"surface has no intersection at x={x}")
    return value


def _build_seeded_stack(case):
    geometry_spec = case["geometry"]
    geometry = ps.Domain(
        gridDelta=case["numerics"]["grid_delta"],
        xExtent=geometry_spec["x_extent"],
        yExtent=geometry_spec["y_extent"],
    )
    ps.MakeHole(
        domain=geometry,
        holeRadius=geometry_spec["radius"],
        holeDepth=geometry_spec["depth"],
        maskHeight=geometry_spec["mask_height"],
        holeShape=ps.HoleShape.FULL,
    ).apply()
    tp.strip_pattern_mask(geometry)

    stack = (
        (ps.Material.SiO2, case["layers"]["liner"]),
        (ps.Material.TaN, case["layers"]["barrier"]),
        (tp.CU_SEED_MATERIAL, case["layers"]["seed"]),
    )
    for material, thickness in stack:
        geometry.duplicateTopLevelSet(material)
        ps.Process(
            geometry,
            ps.IsotropicProcess(rate=thickness),
            1.0,
        ).apply()
    geometry.duplicateTopLevelSet(ps.Material.Cu)
    return geometry


def _reference_geometry(geometry, case):
    meshes = tm.raw_level_set_meshes(geometry)
    expected = _validate_material_stack(geometry)
    actual = tuple(mesh["material"] for mesh in meshes)
    if actual != expected:
        raise ValueError(f"unexpected material stack: {actual}")

    field_xs = tuple(case["geometry"]["field_sample_xs"])
    seed_mesh = meshes[-2]
    field_y = float(np.mean([_surface_height(seed_mesh, x) for x in field_xs]))
    floor_y = _surface_height(seed_mesh, 0.0)
    mouth_y = field_y - case["geometry"]["mouth_offset"]
    wall_xs = tm.line_intersections_at_y(
        seed_mesh["nodes"],
        seed_mesh["lines"],
        mouth_y,
    )
    left = wall_xs[wall_xs < 0.0]
    right = wall_xs[wall_xs > 0.0]
    if not len(left) or not len(right):
        raise ValueError("post-seed cavity mouth is not resolved on both sides")
    via_x_bounds = (float(np.max(left)), float(np.min(right)))
    grid_delta = case["numerics"]["grid_delta"]
    area_sample_count = max(
        201,
        int(math.ceil(
            (via_x_bounds[1] - via_x_bounds[0]) / (0.5 * grid_delta)
        )),
    )
    overburden_sample_count = max(
        201,
        int(math.ceil(
            (max(field_xs) - min(field_xs)) / (0.5 * grid_delta)
        )),
    )

    fill_mesh = meshes[-1]
    initial = _fill_topology_metrics_2d(
        fill_mesh,
        field_y=field_y,
        floor_y=floor_y,
        via_x_bounds=via_x_bounds,
        field_sample_xs=field_xs,
        center_x=0.0,
        tolerance=0.1 * case["numerics"]["grid_delta"],
        grid_delta=case["numerics"]["grid_delta"],
        mouth_sample_y=mouth_y,
        area_sample_count=area_sample_count,
        overburden_sample_count=overburden_sample_count,
    )
    if not initial["open_void"] or initial["remaining_void_area"] <= 0.0:
        raise ValueError("initial post-seed cavity was not measured as open")

    layer_names = ("liner", "barrier", "seed")
    layer_metrics = {}
    for index, name in enumerate(layer_names, start=1):
        inner = meshes[index - 1]
        outer = meshes[index]
        inner_field_y = float(
            np.mean([_surface_height(inner, x) for x in field_xs])
        )
        inner_floor_y = _surface_height(inner, 0.0)
        layer_metrics[name] = tm.layer_thickness_metrics_2d(
            inner["nodes"],
            inner["lines"],
            outer["nodes"],
            outer["lines"],
            surface_y=inner_field_y,
            floor_y=inner_floor_y,
            via_radius=case["geometry"]["radius"],
            field_x=abs(field_xs[-1]),
            floor_x=0.0,
        )
    liner_outer = meshes[1]
    seed_outer = meshes[3]
    combined_field_y = float(
        np.mean([_surface_height(liner_outer, x) for x in field_xs])
    )
    combined_floor_y = _surface_height(liner_outer, 0.0)
    layer_metrics["barrier_seed_combined"] = tm.layer_thickness_metrics_2d(
        liner_outer["nodes"],
        liner_outer["lines"],
        seed_outer["nodes"],
        seed_outer["lines"],
        surface_y=combined_field_y,
        floor_y=combined_floor_y,
        via_radius=case["geometry"]["radius"],
        field_x=abs(field_xs[-1]),
        floor_x=0.0,
    )
    liner_metrics = layer_metrics["liner"]
    combined_metrics = layer_metrics["barrier_seed_combined"]
    layer_gates = {
        "liner": bool(
            liner_metrics["minimum_local_thickness"]
            >= case["target"]["liner_min_thickness"]
            and liner_metrics["floor_to_field_conformality"]
            >= case["target"]["liner_min_conformality"]
            and liner_metrics["lower_wall_to_field_conformality"]
            >= case["target"]["liner_min_conformality"]
            and liner_metrics["layer_continuous"]
            and liner_metrics["aperture_open"]
        ),
        "barrier_seed": bool(
            combined_metrics["minimum_local_thickness"]
            >= case["target"]["barrier_seed_min_thickness"]
            and combined_metrics["floor_to_field_conformality"]
            >= case["target"]["barrier_seed_min_conformality"]
            and layer_metrics["barrier"]["layer_continuous"]
            and layer_metrics["seed"]["layer_continuous"]
            and combined_metrics["aperture_open"]
        ),
    }
    if not all(layer_gates.values()):
        raise ValueError(f"ideal pre-fill stack misses functional gates: {layer_gates}")

    return {
        "field_y": field_y,
        "floor_y": floor_y,
        "via_x_bounds": via_x_bounds,
        "field_sample_xs": field_xs,
        "mouth_sample_y": mouth_y,
        "initial_cavity_area": initial["remaining_void_area"],
        "metric_sampling": {
            "area_sample_count": area_sample_count,
            "overburden_sample_count": overburden_sample_count,
            "maximum_profile_spacing_in_grid_cells": 0.5,
        },
        "initial_topology": initial,
        "layer_metrics": layer_metrics,
        "layer_gates": layer_gates,
        "protected_meshes": meshes[:-1],
    }


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
    params.platingMaterials = [tp.CU_SEED_MATERIAL, ps.Material.Cu]
    return params


def _set_process_parameters(process, case, checkpoint_index):
    numerics = case["numerics"]
    ray = ps.RayTracingParameters()
    ray.useRandomSeeds = False
    ray.rngSeed = case["rng_seed"] + checkpoint_index
    ray.raysPerPoint = numerics["rays_per_point"]
    ray.normalizationType = ps.NormalizationType.SOURCE
    ray.ignoreFluxBoundaries = False
    ray.maxReflections = numerics["max_reflections"]
    ray.maxBoundaryHits = numerics["max_boundary_hits"]
    ray.smoothingNeighbors = numerics["smoothing_neighbors"]
    ray.minNodeDistanceFactor = numerics["min_node_distance_factor"]
    ray.diskRadius = numerics["disk_radius"]
    process.setParameters(ray)

    advection = ps.AdvectionParameters()
    advection.ignoreVoids = True
    advection.timeStepRatio = numerics["time_step_ratio"]
    process.setParameters(advection)
    process.setFluxEngineType(ps.FluxEngineType.CPU_DISK)


def _protected_stack_delta(reference_meshes, current_meshes):
    if len(reference_meshes) != len(current_meshes):
        return {"survives": False, "reason": "level-set count changed"}
    max_node_delta = 0.0
    for reference, current in zip(reference_meshes, current_meshes):
        if reference["material"] != current["material"]:
            return {"survives": False, "reason": "material order changed"}
        if (
            reference["nodes"].shape != current["nodes"].shape
            or reference["lines"].shape != current["lines"].shape
        ):
            return {"survives": False, "reason": "protected mesh shape changed"}
        if not np.array_equal(reference["lines"], current["lines"]):
            return {"survives": False, "reason": "protected connectivity changed"}
        if reference["nodes"].size:
            max_node_delta = max(
                max_node_delta,
                float(np.max(np.abs(reference["nodes"] - current["nodes"]))),
            )
    return {
        "survives": bool(max_node_delta <= 1e-12),
        "max_node_delta": max_node_delta,
    }


def _model_diagnostics(model, reference, case):
    coordinates = np.asarray(model.getLastCoordinates(), dtype=float)
    material_ids = np.asarray(model.getLastMaterialIds(), dtype=float)
    flux = np.asarray(model.getLastSuppressorFlux(), dtype=float)
    coverage = np.asarray(model.getLastCoverage(), dtype=float)
    velocity = np.asarray(model.getLastVelocity(), dtype=float)
    adsorption_term = np.asarray(model.getLastAdsorptionTerm(), dtype=float)
    deactivation_term = np.asarray(model.getLastDeactivationTerm(), dtype=float)
    if not len(coordinates):
        raise ValueError("model returned no diagnostic surface points")
    half_width = 0.5 * (
        reference["via_x_bounds"][1] - reference["via_x_bounds"][0]
    )
    field = np.abs(coordinates[:, 0]) > reference["via_x_bounds"][1] + half_width
    center = np.abs(coordinates[:, 0]) < 0.2 * half_width
    plating_ids = {
        float(tp.CU_SEED_MATERIAL.legacyId()),
        float(ps.Material.Cu.legacyId()),
    }
    plating = np.isin(material_ids, list(plating_ids))
    nonplating = ~plating
    suppressed_rate = case["model"]["suppressed_deposition_rate"]
    active_rate = case["model"]["active_deposition_rate"]

    def mean(values, mask):
        return float(np.mean(values[mask])) if np.any(mask) else None

    finite = bool(
        np.all(np.isfinite(flux))
        and np.all(np.isfinite(coverage))
        and np.all(np.isfinite(velocity))
    )
    relative_balance_error = float(model.getLastRelativeBalanceError())
    bounds_valid = bool(
        finite
        and np.min(flux) >= 0.0
        and np.min(coverage) >= 0.0
        and np.max(coverage) <= 1.0
        and np.any(plating)
        and np.min(velocity[plating]) >= suppressed_rate - 1e-12
        and np.max(velocity[plating]) <= active_rate + 1e-12
        and (not np.any(nonplating) or np.max(np.abs(velocity[nonplating])) <= 1e-12)
    )
    summary = {
        "diagnostic_surface": "pre-final-advection surface",
        "point_count": len(coordinates),
        "material_ids": sorted(np.unique(material_ids).tolist()),
        "finite": finite,
        "bounds_valid": bounds_valid,
        "flux_min": float(np.min(flux)),
        "coverage_min": float(np.min(coverage)),
        "coverage_max": float(np.max(coverage)),
        "velocity_min": float(np.min(velocity)),
        "velocity_max": float(np.max(velocity)),
        "field_flux_mean": mean(flux, field),
        "center_flux_mean": mean(flux, center),
        "field_coverage_mean": mean(coverage, field),
        "center_coverage_mean": mean(coverage, center),
        "field_velocity_mean": mean(velocity, field),
        "center_velocity_mean": mean(velocity, center),
        "plating_velocity_min": float(np.min(velocity[plating])),
        "plating_velocity_max": float(np.max(velocity[plating])),
        "nonplating_velocity_max_abs": (
            float(np.max(np.abs(velocity[nonplating])))
            if np.any(nonplating)
            else 0.0
        ),
        "relative_balance_error": relative_balance_error,
        "valid": bool(
            bounds_valid
            and relative_balance_error <= case["target"]["max_balance_error"]
        ),
    }
    raw = {
        "coordinates": coordinates,
        "material_ids": material_ids,
        "suppressor_flux": flux,
        "coverage": coverage,
        "velocity": velocity,
        "adsorption_term": adsorption_term,
        "deactivation_term": deactivation_term,
    }
    return summary, raw


def _save_fill_snapshot(
    snapshot_dir,
    case_id,
    checkpoint_index,
    elapsed,
    mesh,
    diagnostic_summary,
    diagnostic_arrays,
):
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{case_id}_c{checkpoint_index:04d}.npz"
    temporary_path = snapshot_dir / f".{case_id}_c{checkpoint_index:04d}.tmp.npz"
    np.savez_compressed(
        temporary_path,
        elapsed=np.asarray([elapsed]),
        nodes=mesh["nodes"],
        lines=mesh["lines"],
        mesh_surface_stage=np.asarray(["post-checkpoint advection"]),
        diagnostic_surface_stage=np.asarray([
            diagnostic_summary["diagnostic_surface"]
        ]),
        diagnostic_relative_balance_error=np.asarray([
            diagnostic_summary["relative_balance_error"]
        ]),
        diagnostic_coordinates=diagnostic_arrays["coordinates"],
        diagnostic_material_ids=diagnostic_arrays["material_ids"],
        diagnostic_suppressor_flux=diagnostic_arrays["suppressor_flux"],
        diagnostic_coverage=diagnostic_arrays["coverage"],
        diagnostic_velocity=diagnostic_arrays["velocity"],
        diagnostic_adsorption_term=diagnostic_arrays["adsorption_term"],
        diagnostic_deactivation_term=diagnostic_arrays["deactivation_term"],
    )
    os.replace(temporary_path, path)
    return str(path)


def _successful_case_ids(path):
    if not path.exists():
        return set()
    return {
        row["case_id"]
        for row in (
            json.loads(line)
            for line in path.read_text().splitlines()
            if line.strip()
        )
        if row.get("ok")
    }


def _load_progress(progress_dir, case):
    progress_path = progress_dir / f"{case['case_id']}.json"
    if not progress_path.exists():
        return None
    progress = json.loads(progress_path.read_text())
    if progress.get("case_id") != case["case_id"]:
        raise ValueError("Cu-fill progress case ID does not match the manifest")
    domain_path = Path(progress["domain_path"])
    if not domain_path.exists():
        raise ValueError(f"Cu-fill progress domain is missing: {domain_path}")
    geometry = ps.Domain()
    ps.Reader(geometry, str(domain_path)).apply()
    _validate_material_stack(geometry)
    return progress, geometry


def _write_progress(progress_dir, case, geometry, progress):
    progress_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = int(progress["checkpoint"])
    domain_path = progress_dir / (
        f"{case['case_id']}_c{checkpoint:04d}.vpsd"
    )
    temporary_domain = progress_dir / (
        f".{case['case_id']}_c{checkpoint:04d}.tmp.vpsd"
    )
    progress_path = progress_dir / f"{case['case_id']}.json"
    previous_domain = None
    if progress_path.exists():
        previous_payload = json.loads(progress_path.read_text())
        previous_domain = Path(previous_payload["domain_path"])

    ps.Writer(geometry, str(temporary_domain)).apply()
    os.replace(temporary_domain, domain_path)
    temporary_progress = progress_dir / f".{case['case_id']}.tmp.json"
    payload = foundation.jsonable({
        **progress,
        "case_id": case["case_id"],
        "domain_path": str(domain_path),
    })
    with temporary_progress.open("w") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_progress, progress_path)
    if previous_domain and previous_domain != domain_path:
        previous_domain.unlink(missing_ok=True)
    return str(domain_path)


def run_case(task):
    case, snapshot_dir, progress_dir = task
    started = time.time()
    try:
        if not hasattr(ps, "CopperSuppressionFill"):
            raise RuntimeError(
                "CopperSuppressionFill binding is unavailable; rebuild the "
                "qualified ViennaPS extension first"
            )
        ps.setNumThreads(case["numerics"]["threads_per_worker"])
        numerical_invariants = _validate_case_invariants(case)
        initial_geometry = _build_seeded_stack(case)
        reference = _reference_geometry(initial_geometry, case)
        saved = _load_progress(progress_dir, case)
        if saved:
            progress, geometry = saved
            trajectory = progress["trajectory"]
            elapsed = float(progress["elapsed"])
            previous_state = (
                tuple(progress["previous_state"])
                if progress.get("previous_state") is not None
                else None
            )
            pinch_off_seen = bool(progress["pinch_off_seen"])
            invalid_topology_seen = bool(progress["invalid_topology_seen"])
            topology_transition_failure_seen = bool(
                progress.get("topology_transition_failure_seen", False)
            )
            protected_failure_seen = bool(progress["protected_failure_seen"])
            model_failure_seen = bool(progress["model_failure_seen"])
            target_pass = bool(progress["target_pass"])
            start_checkpoint = int(progress["checkpoint"])
            resumed_from_checkpoint = start_checkpoint
        else:
            geometry = initial_geometry
            trajectory = []
            elapsed = 0.0
            previous_state = None
            pinch_off_seen = False
            invalid_topology_seen = False
            topology_transition_failure_seen = False
            protected_failure_seen = False
            model_failure_seen = False
            target_pass = False
            start_checkpoint = 0
            resumed_from_checkpoint = None
        checkpoint_interval = case["numerics"]["checkpoint_interval"]
        checkpoint_count = int(
            np.ceil(case["numerics"]["max_duration"] / checkpoint_interval)
        )

        terminal_failure = bool(
            pinch_off_seen
            or invalid_topology_seen
            or topology_transition_failure_seen
            or protected_failure_seen
            or model_failure_seen
        )
        for checkpoint_index in range(start_checkpoint + 1, checkpoint_count + 1):
            if target_pass or terminal_failure:
                break
            duration = min(
                checkpoint_interval,
                case["numerics"]["max_duration"] - elapsed,
            )
            previous_fill_mesh = tm.raw_level_set_meshes(geometry)[-1]
            model = ps.CopperSuppressionFill(_model_parameters(case))
            process = ps.Process(geometry, model, duration)
            _set_process_parameters(process, case, checkpoint_index)
            process.apply()
            elapsed += duration

            meshes = tm.raw_level_set_meshes(geometry)
            fill_mesh = meshes[-1]
            topology = _fill_topology_metrics_2d(
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
                overburden_sample_count=reference["metric_sampling"]["overburden_sample_count"],
            )
            previous_topology = (
                trajectory[-1]["topology"]
                if trajectory
                else reference["initial_topology"]
            )
            topology_transition = _topology_transition_check(
                previous_topology,
                topology,
                numerical_invariants,
                case["numerics"]["grid_delta"],
                previous_mesh=previous_fill_mesh,
                reference=reference,
            )
            protected = _protected_stack_delta(
                reference["protected_meshes"],
                meshes[:-1],
            )
            diagnostics, diagnostic_arrays = _model_diagnostics(
                model,
                reference,
                case,
            )
            pinch_off_seen = pinch_off_seen or topology["pinch_off_failure"]
            invalid_topology_seen = (
                invalid_topology_seen or not topology["topology_valid"]
            )
            topology_transition_failure_seen = bool(
                topology_transition_failure_seen
                or not topology_transition["valid"]
            )
            protected_failure_seen = (
                protected_failure_seen or not protected["survives"]
            )
            model_failure_seen = model_failure_seen or not diagnostics["valid"]
            target_pass = bool(
                topology["topology_valid"]
                and topology["void_free"]
                and topology["overburden_min"] >= case["target"]["min_overburden"]
                and not pinch_off_seen
                and not invalid_topology_seen
                and not topology_transition_failure_seen
                and not protected_failure_seen
                and not model_failure_seen
                and protected["survives"]
                and diagnostics["valid"]
            )
            state = (
                topology["open_void"],
                topology["closed_void_count"],
                topology["topology_valid"],
                topology_transition["valid"],
                topology["positive_overburden"],
                target_pass,
            )
            save_snapshot = bool(
                state != previous_state
                or target_pass
                or pinch_off_seen
                or invalid_topology_seen
                or topology_transition_failure_seen
                or protected_failure_seen
                or model_failure_seen
                or checkpoint_index % case["numerics"]["save_every"] == 0
                or checkpoint_index == checkpoint_count
            )
            snapshot_path = (
                _save_fill_snapshot(
                    snapshot_dir,
                    case["case_id"],
                    checkpoint_index,
                    elapsed,
                    fill_mesh,
                    diagnostics,
                    diagnostic_arrays,
                )
                if save_snapshot
                else None
            )
            checkpoint_row = foundation.jsonable({
                "checkpoint": checkpoint_index,
                "elapsed": elapsed,
                "topology": topology,
                "topology_transition": topology_transition,
                "protected_stack": protected,
                "model_diagnostics": diagnostics,
                "pinch_off_seen": pinch_off_seen,
                "invalid_topology_seen": invalid_topology_seen,
                "topology_transition_failure_seen": topology_transition_failure_seen,
                "protected_failure_seen": protected_failure_seen,
                "model_failure_seen": model_failure_seen,
                "target_pass": target_pass,
                "snapshot_path": snapshot_path,
            })
            trajectory.append(checkpoint_row)
            previous_state = state
            terminal_failure = bool(
                pinch_off_seen
                or invalid_topology_seen
                or topology_transition_failure_seen
                or protected_failure_seen
                or model_failure_seen
            )
            _write_progress(
                progress_dir,
                case,
                geometry,
                {
                    "checkpoint": checkpoint_index,
                    "elapsed": elapsed,
                    "trajectory": trajectory,
                    "previous_state": previous_state,
                    "pinch_off_seen": pinch_off_seen,
                    "invalid_topology_seen": invalid_topology_seen,
                    "topology_transition_failure_seen": topology_transition_failure_seen,
                    "protected_failure_seen": protected_failure_seen,
                    "model_failure_seen": model_failure_seen,
                    "target_pass": target_pass,
                    "terminal_failure": terminal_failure,
                },
            )
            if (
                target_pass
                or pinch_off_seen
                or invalid_topology_seen
                or topology_transition_failure_seen
                or protected_failure_seen
                or model_failure_seen
                or duration <= 0.0
            ):
                break

        return foundation.jsonable({
            **case,
            "ok": True,
            "scope": "coarse uncalibrated full-2D-trench mechanism screen",
            "reference": {
                key: value
                for key, value in reference.items()
                if key != "protected_meshes"
            },
            "trajectory": trajectory,
            "target_pass": target_pass,
            "screen_pass": target_pass,
            "production_doe_eligible": False,
            "numerical_invariants": numerical_invariants,
            "pinch_off_seen": pinch_off_seen,
            "invalid_topology_seen": invalid_topology_seen,
            "topology_transition_failure_seen": topology_transition_failure_seen,
            "protected_failure_seen": protected_failure_seen,
            "model_failure_seen": model_failure_seen,
            "resumed_from_checkpoint": resumed_from_checkpoint,
            "last_checkpoint": (
                int(trajectory[-1]["checkpoint"])
                if trajectory
                else start_checkpoint
            ),
            "elapsed_s": time.time() - started,
        })
    except Exception as error:
        return foundation.jsonable({
            **case,
            "ok": False,
            "production_doe_eligible": False,
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
    _validate_replicate_rng_streams(manifest)
    cases = expand_cases(manifest)
    done = _successful_case_ids(args.output)
    pending = [case for case in cases if case["case_id"] not in done]
    if args.limit is not None:
        pending = pending[:args.limit]
    print(
        f"manifest cases={len(cases)} complete={len(done)} pending={len(pending)}",
        flush=True,
    )
    if not pending:
        return

    snapshot_dir = args.output.parent / "copper_fill_trajectory_snapshots"
    progress_dir = args.output.parent / "copper_fill_trajectory_progress"
    tasks = [(case, snapshot_dir, progress_dir) for case in pending]
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, row in enumerate(executor.map(run_case, tasks), start=1):
            foundation.append_row(args.output, row)
            print(
                f"[{completed}/{len(tasks)}] {row['case_id']} "
                f"ok={row['ok']} pass={row.get('target_pass')} "
                f"elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

"""Generate independent saved-output studies for the TSV teaching page."""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import viennals as ls
import viennaps as ps

import full_2d_layer_metrics as layer_metrics
import foundation_cmp_qualification as cmp_controls
import layer_process_models as layer_models
import native_domain_checkpoint as checkpoint
from process_config import PROCESS_CONFIG
import traveler_metrics as tm
import tsv_process as tp


OUTPUT = Path("step_experiments.json")
CONFIG = PROCESS_CONFIG["teaching_experiments"]
GEOMETRY = PROCESS_CONFIG["defaults"]["geometry"]
TARGETS = PROCESS_CONFIG["targets"]
SURFACE_Y = CONFIG["surface_y"]
MAX_RADIUS = CONFIG["profile_max_radius"]


def _refresh_provenance():
    data = json.loads(OUTPUT.read_text())
    hashes = {
        source["path"]: checkpoint.file_sha256(source["path"])
        for source in data["provenance"]["sources"]
    }
    section_names = {
        "Declared study product spec": "Assumed study comparison bands",
        "Step target specs": "Step comparison and handoff rules",
    }

    def visit(value):
        if isinstance(value, dict):
            path = value.get("path")
            if path in hashes and "sha256" in value:
                value["sha256"] = hashes[path]
            section = value.get("section")
            if section in section_names:
                value["section"] = section_names[section]
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    data["provenance"]["builder_sha256"] = hashes["build_step_experiments.py"]
    OUTPUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(OUTPUT)


def _surface_path(mesh):
    segments = np.asarray(mesh["nodes"])[np.asarray(mesh["lines"], dtype=int)][:, :, :2]
    return "".join(
        f"M{start[0]:.5f} {start[1]:.5f}L{end[0]:.5f} {end[1]:.5f}"
        for start, end in segments
    )


def _material_id(material):
    if material == ps.Material.Mask:
        return "mask"
    if material == ps.Material.Si:
        return "silicon"
    if material == ps.Material.SiO2:
        return "liner"
    if material == ps.Material.TaN:
        return "barrier"
    if material == tp.CU_SEED_MATERIAL:
        return "seed"
    if material == ps.Material.Cu:
        return "copper"
    return str(material)


def _materials(geometry):
    return [
        {"id": _material_id(mesh["material"]), "surface_path": _surface_path(mesh)}
        for mesh in tm.raw_level_set_meshes(geometry)
    ]


def _annotate_lineage(frames):
    parent_hash = None
    for frame in frames:
        payload = json.dumps(frame, sort_keys=True, separators=(",", ":"))
        frame_hash = hashlib.sha256(payload.encode()).hexdigest()
        frame["frame_hash"] = frame_hash
        frame["parent_frame_hash"] = parent_hash
        parent_hash = frame_hash
    if parent_hash is None:
        raise ValueError("lineage must contain at least one frame")
    return parent_hash[:12]


def _base_via():
    traveler = PROCESS_CONFIG["traveler"]
    saved = checkpoint.load_domain_checkpoint(
        traveler["source"], expected_sha256=traveler["source_sha256"]
    )
    source = checkpoint.extract_raw_silicon_domain(saved)
    silicon = next(
        mesh
        for mesh in tm.raw_level_set_meshes(source)
        if mesh["material"] == ps.Material.Si
    )
    surface = ls.Mesh()
    for node in silicon["nodes"]:
        surface.insertNextNode([float(node[0]), float(node[1]), 0.0])
    for line in silicon["lines"]:
        surface.insertNextLine([int(line[0]), int(line[1])])

    geometry = ps.Domain(
        gridDelta=GEOMETRY["grid_delta"],
        xExtent=GEOMETRY["x_extent"],
        yExtent=GEOMETRY["y_extent"],
    )
    ps.MakePlane(geometry, height=0.0, material=ps.Material.Si).apply()
    level_set = geometry.getLevelSets()[0]
    ls.FromSurfaceMesh(level_set, surface).apply()
    resampled = ps.Domain()
    resampled.insertNextLevelSetAsMaterial(level_set, ps.Material.Si, False)
    return resampled


def _mask_study():
    frames = []
    for radius in CONFIG["mask_radii"]:
        for taper in CONFIG["mask_tapers"]:
            for mask_height in CONFIG["mask_heights"]:
                geometry = tp.make_initial_geometry(
                    radius=radius,
                    mask_height=mask_height,
                    taper=taper,
                    hole_shape=ps.HoleShape.FULL,
                )
                mask = next(
                    mesh
                    for mesh in tm.raw_level_set_meshes(geometry)
                    if mesh["material"] == ps.Material.Mask
                )
                metrics = tm.pattern_metrics_2d(
                    mask["nodes"],
                    mask["lines"],
                    surface_y=SURFACE_Y,
                    target_cd=TARGETS["pattern"]["width"],
                    target_mask_height=TARGETS["pattern"]["mask_height"],
                    max_radius=MAX_RADIUS,
                )
                frames.append(
                    {
                        "setting": {
                            "opening_width": 2 * radius,
                            "mask_taper": taper,
                            "mask_height": mask_height,
                        },
                        "materials": _materials(geometry),
                        "metrics": {
                            "opening_cd_bottom": metrics["opening_cd_bottom"],
                            "opening_cd_top": metrics["opening_cd_top"],
                            "mask_height": metrics["mask_height"],
                            "meets_screen": bool(
                                abs(metrics["cd_bias"])
                                < CONFIG["measurement_tolerance"]
                                and abs(
                                    metrics["mask_height"]
                                    - TARGETS["pattern"]["mask_height"]
                                )
                                <= CONFIG["mask_height_tolerance"]
                            ),
                        },
                    }
                )
    return {
        "id": "mask",
        "title": "Mask opening results",
        "scope": "Ideal mask-geometry sweep; no exposure or develop model.",
        "starts_from": "Ideal mask constructor.",
        "claim_level": "implementation_check",
        "acceptance": {
            "status": "declared",
            "basis": {
                "classification": "assumed_study_target",
                "physical_qualification": False,
                "source": {
                    "path": "program.md",
                    "section": "Step comparison and handoff rules",
                },
            },
            "rules": [
                {
                    "metric": "opening_cd_bottom",
                    "operator": "equal_within",
                    "value": TARGETS["pattern"]["width"],
                    "tolerance": CONFIG["measurement_tolerance"],
                },
                {
                    "metric": "mask_height",
                    "operator": "equal_within",
                    "value": TARGETS["pattern"]["mask_height"],
                    "tolerance": CONFIG["mask_height_tolerance"],
                },
            ],
        },
        "parameters": [
            {
                "key": "opening_width",
                "label": "Opening width",
                "values": [2 * value for value in CONFIG["mask_radii"]],
            },
            {
                "key": "mask_taper",
                "label": "Wall taper",
                "values": CONFIG["mask_tapers"],
                "unit": "°",
            },
            {
                "key": "mask_height",
                "label": "Mask height",
                "values": CONFIG["mask_heights"],
            },
        ],
        "default_frame": 10,
        "target_frame": 10,
        "view_box": CONFIG["view_box_mask"],
        "frames": frames,
    }


def _bosch_study():
    frames = []
    selected_cycles = set(CONFIG["bosch_cycles"])

    def save_frame(domain, cycle, passivation):
        if cycle not in selected_cycles:
            return
        silicon = next(
            mesh
            for mesh in tm.raw_level_set_meshes(domain)
            if mesh["material"] == ps.Material.Si
        )
        floor_y = float(np.min(silicon["nodes"][:, 1]))
        measured = tm.etch_profile_metrics_2d(
            silicon["nodes"],
            silicon["lines"],
            surface_y=SURFACE_Y,
            floor_y=floor_y,
            target_cd=TARGETS["etch"]["target_width"],
            max_radius=MAX_RADIUS,
        )
        depth_ok = (
            abs(measured["depth"] - TARGETS["etch"]["target_depth"])
            <= TARGETS["etch"]["depth_tolerance"]
        )
        frames.append(
            {
                "setting": {
                    "completed_cycles": cycle,
                    "passivation_thickness": passivation,
                },
                "materials": _materials(domain),
                "metrics": {
                    "depth": measured["depth"],
                    "maximum_cd_error": measured["max_cd_error"],
                    "bow": measured["max_bow"],
                    "meets_screen": bool(
                        depth_ok
                        and measured["max_cd_error"]
                        <= TARGETS["etch"]["max_width_error"]
                        and measured["max_bow"] <= TARGETS["etch"]["max_wall_bulge"]
                    ),
                },
            }
        )

    for passivation in CONFIG["bosch_passivation_thickness"]:
        geometry = tp.make_initial_geometry(hole_shape=ps.HoleShape.FULL)
        tp.bosch_etch(
            geometry,
            num_cycles=max(selected_cycles),
            deposition_thickness=passivation,
            on_cycle=lambda domain, cycle, value=passivation: save_frame(
                domain, cycle, value
            ),
            rays_per_point=CONFIG["rays_per_point"],
            rng_seed=CONFIG["rng_seed"],
        )
    return {
        "id": "bosch",
        "title": "Dry-etch cycle teaching study",
        "scope": "Failing 2D cycle study. This is not the selected traveler.",
        "starts_from": "Fresh target-width mask. Cycle 0 follows the opening etch.",
        "claim_level": "teaching_screen",
        "acceptance": {
            "status": "declared",
            "basis": {
                "classification": "assumed_study_target",
                "physical_qualification": False,
                "source": {
                    "path": "program.md",
                    "section": "Assumed study comparison bands",
                },
            },
            "rules": [
                {
                    "metric": "depth",
                    "operator": "equal_within",
                    "value": TARGETS["etch"]["target_depth"],
                    "tolerance": TARGETS["etch"]["depth_tolerance"],
                },
                {
                    "metric": "maximum_cd_error",
                    "operator": "maximum",
                    "value": TARGETS["etch"]["max_width_error"],
                },
                {
                    "metric": "bow",
                    "operator": "maximum",
                    "value": TARGETS["etch"]["max_wall_bulge"],
                },
            ],
        },
        "parameters": [
            {
                "key": "completed_cycles",
                "label": "Etch cycles",
                "values": CONFIG["bosch_cycles"],
            },
            {
                "key": "passivation_thickness",
                "label": "Wall protection per cycle",
                "values": CONFIG["bosch_passivation_thickness"],
            },
        ],
        "default_frame": 4,
        "view_box": CONFIG["view_box_full"],
        "frames": frames,
    }


def _layer_measure(inner, outer):
    measured = layer_metrics.layer_thickness_metrics_full_2d(
        inner["nodes"],
        inner["lines"],
        outer["nodes"],
        outer["lines"],
        surface_y=SURFACE_Y,
        floor_y=-TARGETS["etch"]["target_depth"],
        via_radius=GEOMETRY["radius"],
    )
    return {
        "minimum_thickness": measured["minimum_local_thickness"],
        "lower_wall_coverage": measured["lower_wall_to_field_conformality"],
        "floor_coverage": measured["floor_to_field_conformality"],
        "remaining_aperture": measured["minimum_remaining_aperture"],
        "continuous": measured["layer_continuous"],
        "aperture_open": measured["aperture_open"],
    }


def _liner_study():
    frames = []
    for sticking in CONFIG["liner_sticking"]:
        for dose in CONFIG["liner_doses"]:
            geometry = _base_via()
            substrate = tm.raw_level_set_meshes(geometry)[-1]
            tp.deposit_conformal(
                geometry,
                ps.Material.SiO2,
                dose,
                sticking=sticking,
                rays_per_point=CONFIG["rays_per_point"],
                rng_seed=CONFIG["rng_seed"],
            )
            outer = tm.raw_level_set_meshes(geometry)[-1]
            metrics = _layer_measure(substrate, outer)
            metrics["meets_screen"] = bool(
                metrics["minimum_thickness"] >= TARGETS["liner"]["min_thickness"]
                and metrics["lower_wall_coverage"]
                >= TARGETS["liner"]["min_floor_coverage"]
                and metrics["continuous"]
                and metrics["aperture_open"]
            )
            frames.append(
                {
                    "setting": {
                        "sticking_probability": sticking,
                        "deposition_amount": dose,
                    },
                    "materials": _materials(geometry),
                    "metrics": metrics,
                }
            )
    return {
        "id": "liner",
        "title": "Liner deposition results",
        "scope": "Shows how particle sticking changes wall coverage. Coefficients are uncalibrated.",
        "starts_from": "Focused saved etch profile, resampled on the teaching grid.",
        "claim_level": "teaching_screen",
        "acceptance": {
            "status": "declared",
            "basis": {
                "classification": "assumed_study_target",
                "physical_qualification": False,
                "source": {
                    "path": "program.md",
                    "section": "Step comparison and handoff rules",
                },
            },
            "rules": [
                {
                    "metric": "minimum_thickness",
                    "operator": "minimum",
                    "value": TARGETS["liner"]["min_thickness"],
                },
                {
                    "metric": "lower_wall_coverage",
                    "operator": "minimum",
                    "value": TARGETS["liner"]["min_floor_coverage"],
                },
                {"metric": "continuous", "operator": "must_be_true"},
                {"metric": "aperture_open", "operator": "must_be_true"},
            ],
        },
        "parameters": [
            {
                "key": "sticking_probability",
                "label": "Particle sticking",
                "values": CONFIG["liner_sticking"],
            },
            {
                "key": "deposition_amount",
                "label": "Deposition amount",
                "values": CONFIG["liner_doses"],
            },
        ],
        "default_frame": 4,
        "view_box": CONFIG["view_box_full"],
        "frames": frames,
    }


def _fixed_liner():
    geometry = _base_via()
    layer_models.deposit_isotropic_control(
        geometry, ps.Material.SiO2, dose=CONFIG["liner_dose"]
    )
    return geometry


def _barrier_study():
    frames = []
    for fraction in CONFIG["barrier_isotropic_fraction"]:
        for dose in CONFIG["barrier_doses"]:
            geometry = _fixed_liner()
            inner = tm.raw_level_set_meshes(geometry)[-1]
            layer_models.deposit_directional_fraction(
                geometry, ps.Material.TaN, field_dose=dose, isotropic_fraction=fraction
            )
            outer = tm.raw_level_set_meshes(geometry)[-1]
            metrics = _layer_measure(inner, outer)
            metrics["meets_screen"] = bool(
                metrics["minimum_thickness"] >= TARGETS["barrier"]["min_thickness"]
                and metrics["lower_wall_coverage"]
                >= TARGETS["barrier"]["min_floor_coverage"]
                and metrics["continuous"]
                and metrics["aperture_open"]
            )
            frames.append(
                {
                    "setting": {
                        "isotropic_fraction": fraction,
                        "deposition_amount": dose,
                    },
                    "materials": _materials(geometry),
                    "metrics": metrics,
                }
            )
    return {
        "id": "barrier",
        "title": "Barrier deposition results",
        "scope": "Directional-versus-isotropic geometry control.",
        "starts_from": "Resampled focused etch profile with a fixed liner.",
        "claim_level": "teaching_screen",
        "acceptance": {
            "status": "declared",
            "basis": {
                "classification": "assumed_study_target",
                "physical_qualification": False,
                "source": {
                    "path": "program.md",
                    "section": "Step comparison and handoff rules",
                },
            },
            "rules": [
                {
                    "metric": "minimum_thickness",
                    "operator": "minimum",
                    "value": TARGETS["barrier"]["min_thickness"],
                },
                {
                    "metric": "lower_wall_coverage",
                    "operator": "minimum",
                    "value": TARGETS["barrier"]["min_floor_coverage"],
                },
                {"metric": "continuous", "operator": "must_be_true"},
                {"metric": "aperture_open", "operator": "must_be_true"},
            ],
        },
        "parameters": [
            {
                "key": "isotropic_fraction",
                "label": "All-angle fraction",
                "values": CONFIG["barrier_isotropic_fraction"],
            },
            {
                "key": "deposition_amount",
                "label": "Deposition amount",
                "values": CONFIG["barrier_doses"],
            },
        ],
        "default_frame": 4,
        "view_box": CONFIG["view_box_full"],
        "frames": frames,
    }


def _fixed_barrier():
    geometry = _fixed_liner()
    layer_models.deposit_directional_fraction(
        geometry,
        ps.Material.TaN,
        field_dose=CONFIG["barrier_dose"],
        isotropic_fraction=0.3,
    )
    return geometry


def _seed_study():
    frames = []
    for fraction in CONFIG["seed_isotropic_fraction"]:
        for dose in CONFIG["seed_doses"]:
            geometry = _fixed_barrier()
            inner = tm.raw_level_set_meshes(geometry)[-1]
            layer_models.deposit_directional_fraction(
                geometry,
                tp.CU_SEED_MATERIAL,
                field_dose=dose,
                isotropic_fraction=fraction,
            )
            outer = tm.raw_level_set_meshes(geometry)[-1]
            metrics = _layer_measure(inner, outer)
            metrics["meets_screen"] = None
            frames.append(
                {
                    "setting": {
                        "isotropic_fraction": fraction,
                        "deposition_amount": dose,
                    },
                    "materials": _materials(geometry),
                    "metrics": metrics,
                }
            )
    return {
        "id": "seed",
        "title": "Seed deposition results",
        "scope": "Directional-versus-isotropic geometry control. No seed limit is declared.",
        "starts_from": "Resampled focused etch profile with fixed liner and barrier layers.",
        "claim_level": "no_gate_declared",
        "acceptance": {
            "status": "not_declared",
            "basis": {
                "classification": "no_limit_declared",
                "physical_qualification": False,
                "source": {
                    "path": "program.md",
                    "section": "Step comparison and handoff rules",
                },
            },
            "rules": [],
        },
        "parameters": [
            {
                "key": "isotropic_fraction",
                "label": "All-angle fraction",
                "values": CONFIG["seed_isotropic_fraction"],
            },
            {
                "key": "deposition_amount",
                "label": "Deposition amount",
                "values": CONFIG["seed_doses"],
            },
        ],
        "default_frame": 4,
        "view_box": CONFIG["view_box_full"],
        "frames": frames,
    }


def _cmp_study():
    frames = []
    for duration in CONFIG["cmp_removal_durations"]:
        for oxide_rate in CONFIG["cmp_oxide_rate_ratios"]:
            stack = cmp_controls.build_analytic_stack(
                "raised_plug", grid_delta=GEOMETRY["grid_delta"]
            )
            law = cmp_controls.default_candidate_law(stack.stop_y)
            rates = dict(law.material_rate_ratios)
            rates[ps.Material.SiO2] = oxide_rate
            law = cmp_controls.HeightMaterialRemovalLaw(
                stack.stop_y, law.compliance_length, law.residual_contact, rates
            )
            cmp_controls.apply_native_control(
                stack, "uniform_material_selective", duration=duration, law=law
            )
            meshes = tm.raw_level_set_meshes(stack.geometry)
            copper = next(mesh for mesh in meshes if mesh["material"] == ps.Material.Cu)
            oxide = next(
                mesh for mesh in meshes if mesh["material"] == ps.Material.SiO2
            )
            silicon = next(
                mesh for mesh in meshes if mesh["material"] == ps.Material.Si
            )
            field_height = tm.surface_height_at_x(
                copper["nodes"], copper["lines"], CONFIG["cmp_field_x"]
            )
            plug_height = tm.surface_height_at_x(
                copper["nodes"], copper["lines"], CONFIG["cmp_plug_x"]
            )
            oxide_height = tm.surface_height_at_x(
                oxide["nodes"], oxide["lines"], CONFIG["cmp_field_x"]
            )
            silicon_height = tm.surface_height_at_x(
                silicon["nodes"], silicon["lines"], CONFIG["cmp_field_x"]
            )
            if None in (field_height, plug_height, oxide_height, silicon_height):
                raise RuntimeError("CMP teaching heights could not be measured")
            frames.append(
                {
                    "setting": {
                        "removal_amount": duration,
                        "oxide_rate_ratio": oxide_rate,
                    },
                    "materials": _materials(stack.geometry),
                    "metrics": {
                        "field_relative_to_target": field_height - stack.stop_y,
                        "plug_relative_to_target": plug_height - stack.stop_y,
                        "stop_retained_thickness": oxide_height - silicon_height,
                        "meets_screen": None,
                    },
                }
            )
    return {
        "id": "cmp",
        "title": "CMP removal results",
        "scope": "Material-selective removal control; no pad pressure or calibrated polish time.",
        "starts_from": "Analytic stack with a raised copper plug.",
        "claim_level": "no_gate_declared",
        "acceptance": {
            "status": "not_declared",
            "basis": {
                "classification": "no_limit_declared",
                "physical_qualification": False,
                "source": {
                    "path": "program.md",
                    "section": "Step comparison and handoff rules",
                },
            },
            "rules": [],
        },
        "parameters": [
            {
                "key": "removal_amount",
                "label": "Removal amount",
                "values": CONFIG["cmp_removal_durations"],
            },
            {
                "key": "oxide_rate_ratio",
                "label": "Oxide rate relative to copper",
                "values": CONFIG["cmp_oxide_rate_ratios"],
            },
        ],
        "default_frame": 4,
        "view_box": CONFIG["view_box_full"],
        "frames": frames,
    }


def _failure_chain():
    frames = []
    geometry = tp.make_initial_geometry(hole_shape=ps.HoleShape.FULL)
    frames.append(
        {
            "step": "Mask",
            "outcome": "Opening starts at the target width.",
            "materials": _materials(geometry),
        }
    )

    geometry, _ = tp.bosch_etch(
        geometry,
        num_cycles=CONFIG["failure_chain_cycles"],
        rays_per_point=CONFIG["rays_per_point"],
        rng_seed=CONFIG["rng_seed"],
    )
    silicon = next(
        mesh
        for mesh in tm.raw_level_set_meshes(geometry)
        if mesh["material"] == ps.Material.Si
    )
    floor_y = float(np.min(silicon["nodes"][:, 1]))
    etched = tm.etch_profile_metrics_2d(
        silicon["nodes"],
        silicon["lines"],
        surface_y=SURFACE_Y,
        floor_y=floor_y,
        target_cd=TARGETS["etch"]["target_width"],
        max_radius=MAX_RADIUS,
    )
    frames.append(
        {
            "step": "Dry etch",
            "outcome": "Depth passes. Width and bow miss.",
            "materials": _materials(geometry),
            "metrics": {
                "depth": etched["depth"],
                "maximum_width_error": etched["max_cd_error"],
                "bow": etched["max_bow"],
            },
        }
    )
    tp.strip_pattern_mask(geometry)

    inner = tm.raw_level_set_meshes(geometry)[-1]
    tp.deposit_conformal(
        geometry,
        ps.Material.SiO2,
        CONFIG["liner_dose"],
        sticking=CONFIG["failure_chain_liner_sticking"],
        rays_per_point=CONFIG["rays_per_point"],
        rng_seed=CONFIG["rng_seed"] + 1,
    )
    liner = _layer_measure(inner, tm.raw_level_set_meshes(geometry)[-1])
    frames.append(
        {
            "step": "Liner",
            "outcome": "The layer stays connected but deep coverage misses.",
            "materials": _materials(geometry),
            "metrics": {
                "deep_coverage": liner["lower_wall_coverage"],
                "continuous": liner["continuous"],
            },
        }
    )

    inner = tm.raw_level_set_meshes(geometry)[-1]
    layer_models.deposit_directional_fraction(
        geometry,
        ps.Material.TaN,
        field_dose=CONFIG["barrier_dose"],
        isotropic_fraction=CONFIG["failure_chain_directional_fraction"],
    )
    barrier = _layer_measure(inner, tm.raw_level_set_meshes(geometry)[-1])
    frames.append(
        {
            "step": "Barrier",
            "outcome": "The lower-wall barrier is not connected.",
            "materials": _materials(geometry),
            "metrics": {
                "deep_coverage": barrier["lower_wall_coverage"],
                "continuous": barrier["continuous"],
            },
        }
    )

    inner = tm.raw_level_set_meshes(geometry)[-1]
    layer_models.deposit_directional_fraction(
        geometry,
        tp.CU_SEED_MATERIAL,
        field_dose=CONFIG["seed_dose"],
        isotropic_fraction=CONFIG["failure_chain_directional_fraction"],
    )
    seed = _layer_measure(inner, tm.raw_level_set_meshes(geometry)[-1])
    seed_mesh = tm.raw_level_set_meshes(geometry)[-1]
    field_y = tm.surface_height_at_x(
        seed_mesh["nodes"],
        seed_mesh["lines"],
        CONFIG["failure_chain_field_sample_xs"][1],
    )
    if field_y is None:
        raise RuntimeError("failure-chain seed field could not be measured")
    seed_floor_y = float(np.min(seed_mesh["nodes"][:, 1]))
    frames.append(
        {
            "step": "Seed",
            "outcome": "The lower-wall seed is not connected.",
            "materials": _materials(geometry),
            "metrics": {
                "deep_coverage": seed["lower_wall_coverage"],
                "continuous": seed["continuous"],
            },
        }
    )

    tp.cu_fill(
        geometry,
        CONFIG["failure_chain_fill_thickness"],
        directional=True,
        iso_ratio=CONFIG["failure_chain_fill_isotropic_ratio"],
    )
    copper = tm.raw_level_set_meshes(geometry)[-1]
    topology = tm.fill_topology_metrics_2d(
        copper["nodes"],
        copper["lines"],
        field_y=field_y,
        floor_y=seed_floor_y,
        via_x_bounds=tuple(CONFIG["failure_chain_via_x_bounds"]),
        field_sample_xs=tuple(CONFIG["failure_chain_field_sample_xs"]),
        center_x=0.0,
        tolerance=GEOMETRY["grid_delta"],
        grid_delta=GEOMETRY["grid_delta"],
    )
    frames.append(
        {
            "step": "Copper fill",
            "outcome": "The geometric fill control traps a void. It continues even though the seed check failed.",
            "materials": _materials(geometry),
            "metrics": {
                "closed_void_count": topology["closed_void_count"],
                "remaining_void_area": topology["remaining_void_area"],
            },
        }
    )
    run_id = _annotate_lineage(frames)
    return {
        "run_id": run_id,
        "title": "Geometry-only handoff chain",
        "scope": "Every frame comes from the same simulated geometry lineage.",
        "guardrail": (
            "The geometric fill control carries the shape forward but does not use "
            "electrical seed continuity. This reproduces geometry propagation, not fab "
            "causality."
        ),
        "view_box": CONFIG["view_box_full"],
        "frames": frames,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provenance-only", action="store_true")
    args = parser.parse_args()
    if args.provenance_only:
        _refresh_provenance()
        return

    ps.setDimension(2)
    ps.setNumThreads(4)
    data = {
        "schema_version": 2,
        "coordinate_system": {
            "x_units": "model length",
            "y_units": "model length",
            "y_positive": "up",
            "view_box": CONFIG["view_box_full"],
        },
        "provenance": {
            "grid_spacing": GEOMETRY["grid_delta"],
            "upstream_etch_case_id": PROCESS_CONFIG["traveler"]["source_case_id"],
            "upstream_etch_checkpoint": PROCESS_CONFIG["traveler"]["source"],
            "upstream_etch_checkpoint_sha256": PROCESS_CONFIG["traveler"][
                "source_sha256"
            ],
            "upstream_resampling": (
                "Saved surface mesh converted to a level set at the teaching grid spacing"
            ),
            "rays_per_point": CONFIG["rays_per_point"],
            "rng_seed": CONFIG["rng_seed"],
            "stochastic_robustness": "single saved seed; repeatability not established",
            "config_sha256": checkpoint.file_sha256("config/process.toml"),
            "builder_sha256": checkpoint.file_sha256(Path(__file__)),
            "viennaps_version": version("viennaps"),
            "viennals_version": version("viennals"),
            "sources": [
                {"path": path, "sha256": checkpoint.file_sha256(path)}
                for path in (
                    "build_step_experiments.py",
                    "config/process.toml",
                    "tsv_process.py",
                    "layer_process_models.py",
                    "foundation_cmp_qualification.py",
                    "program.md",
                    "traveler_metrics.py",
                    "full_2d_layer_metrics.py",
                    PROCESS_CONFIG["traveler"]["source"],
                )
            ],
        },
        "studies": [
            _mask_study(),
            _bosch_study(),
            _liner_study(),
            _barrier_study(),
            _seed_study(),
            _cmp_study(),
        ],
        "failure_chain": _failure_chain(),
    }
    OUTPUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()

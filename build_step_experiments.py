"""Generate independent saved-output studies for the TSV teaching page."""

from __future__ import annotations

import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import viennaps as ps

import full_2d_layer_metrics as layer_metrics
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


def _surface_path(mesh):
    segments = np.asarray(mesh["nodes"])[np.asarray(mesh["lines"], dtype=int)][
        :, :, :2
    ]
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
    geometry = ps.Domain(
        gridDelta=GEOMETRY["grid_delta"],
        xExtent=GEOMETRY["x_extent"],
        yExtent=GEOMETRY["y_extent"],
    )
    ps.MakeHole(
        domain=geometry,
        holeRadius=GEOMETRY["radius"],
        holeDepth=TARGETS["etch"]["target_depth"],
        maskHeight=GEOMETRY["mask_height"],
        maskTaperAngle=0.0,
        holeShape=ps.HoleShape.FULL,
    ).apply()
    return tp.strip_pattern_mask(geometry)


def _mask_study():
    frames = []
    for radius in CONFIG["mask_radii"]:
        geometry = tp.make_initial_geometry(
            radius=radius,
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
                "setting": {"opening_width": 2 * radius},
                "materials": _materials(geometry),
                "metrics": {
                    "opening_cd_bottom": metrics["opening_cd_bottom"],
                    "opening_cd_top": metrics["opening_cd_top"],
                    "mask_height": metrics["mask_height"],
                    "meets_screen": bool(
                        abs(metrics["cd_bias"]) < CONFIG["measurement_tolerance"]
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
        "input_label": "Opening width",
        "default_frame": 1,
        "view_box": CONFIG["view_box_mask"],
        "frames": frames,
    }


def _bosch_study():
    geometry = tp.make_initial_geometry(hole_shape=ps.HoleShape.FULL)
    frames = []

    def save_frame(domain, cycle):
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
        depth_ok = abs(measured["depth"] - TARGETS["etch"]["target_depth"]) <= TARGETS[
            "etch"
        ]["depth_tolerance"]
        frames.append(
            {
                "setting": {"completed_cycles": cycle},
                "materials": _materials(domain),
                "metrics": {
                    "depth": measured["depth"],
                    "maximum_cd_error": measured["max_cd_error"],
                    "bow": measured["max_bow"],
                    "meets_screen": bool(
                        depth_ok
                        and measured["max_cd_error"]
                        <= TARGETS["etch"]["max_width_error"]
                        and measured["max_bow"]
                        <= TARGETS["etch"]["max_wall_bulge"]
                    ),
                },
            }
        )

    tp.bosch_etch(
        geometry,
        on_cycle=save_frame,
        rays_per_point=CONFIG["rays_per_point"],
        rng_seed=CONFIG["rng_seed"],
    )
    return {
        "id": "bosch",
        "title": "Dry-etch cycle teaching study",
        "scope": "Failing 2D cycle study. This is not the selected traveler.",
        "starts_from": "Fresh target-width mask. Cycle 0 follows the opening etch.",
        "input_label": "Completed cycles",
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
        geometry = _base_via()
        substrate = tm.raw_level_set_meshes(geometry)[-1]
        tp.deposit_conformal(
            geometry,
            ps.Material.SiO2,
            CONFIG["liner_dose"],
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
                "setting": {"sticking_probability": sticking},
                "materials": _materials(geometry),
                "metrics": metrics,
            }
        )
    return {
        "id": "liner",
        "title": "Liner deposition results",
        "scope": "Shows how particle sticking changes wall coverage. Coefficients are uncalibrated.",
        "starts_from": "Ideal etched via.",
        "input_label": "Sticking probability",
        "default_frame": 0,
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
        geometry = _fixed_liner()
        inner = tm.raw_level_set_meshes(geometry)[-1]
        layer_models.deposit_directional_fraction(
            geometry,
            ps.Material.TaN,
            field_dose=CONFIG["barrier_dose"],
            isotropic_fraction=fraction,
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
                "setting": {"isotropic_fraction": fraction},
                "materials": _materials(geometry),
                "metrics": metrics,
            }
        )
    return {
        "id": "barrier",
        "title": "Barrier deposition results",
        "scope": "Directional-versus-isotropic geometry control.",
        "starts_from": "Ideal via with a fixed liner.",
        "input_label": "All-angle fraction",
        "default_frame": 2,
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
        geometry = _fixed_barrier()
        inner = tm.raw_level_set_meshes(geometry)[-1]
        layer_models.deposit_directional_fraction(
            geometry,
            tp.CU_SEED_MATERIAL,
            field_dose=CONFIG["seed_dose"],
            isotropic_fraction=fraction,
        )
        outer = tm.raw_level_set_meshes(geometry)[-1]
        metrics = _layer_measure(inner, outer)
        metrics["meets_screen"] = None
        frames.append(
            {
                "setting": {"isotropic_fraction": fraction},
                "materials": _materials(geometry),
                "metrics": metrics,
            }
        )
    return {
        "id": "seed",
        "title": "Seed deposition results",
        "scope": "Directional-versus-isotropic geometry control. No seed limit is declared.",
        "starts_from": "Ideal via with fixed liner and barrier layers.",
        "input_label": "All-angle fraction",
        "default_frame": 2,
        "view_box": CONFIG["view_box_full"],
        "frames": frames,
    }


def _cmp_study():
    summary = json.loads(Path("publication_interim_data.json").read_text())
    traveler = summary["screening_traveler"]
    fill_artifact = traveler["artifacts"]["fill"]
    source = Path(fill_artifact["path"])
    endpoint = traveler["cmp"]["endpoint_y"]
    frames = []
    for offset in CONFIG["cmp_endpoint_offsets"]:
        geometry = checkpoint.load_domain_checkpoint(
            source, expected_sha256=fill_artifact["sha256"]
        )
        chosen_endpoint = endpoint + offset
        ps.Planarize(geometry, chosen_endpoint).apply()
        copper = next(
            mesh
            for mesh in tm.raw_level_set_meshes(geometry)
            if mesh["material"] == ps.Material.Cu
        )
        field_height = tm.surface_height_at_x(
            copper["nodes"], copper["lines"], CONFIG["cmp_field_x"]
        )
        plug_height = tm.surface_height_at_x(
            copper["nodes"], copper["lines"], CONFIG["cmp_plug_x"]
        )
        if field_height is None or plug_height is None:
            raise RuntimeError("CMP teaching heights could not be measured")
        frames.append(
            {
                "setting": {"endpoint_offset": offset},
                "materials": _materials(geometry),
                "metrics": {
                    "field_copper_height": field_height,
                    "plug_height": plug_height,
                    "target_surface": endpoint,
                    "field_relative_to_target": field_height - endpoint,
                    "plug_relative_to_target": plug_height - endpoint,
                    "meets_screen": bool(
                        field_height is not None
                        and field_height <= endpoint + CONFIG["measurement_tolerance"]
                        and plug_height is not None
                        and plug_height >= endpoint - CONFIG["measurement_tolerance"]
                    ),
                },
            }
        )
    return {
        "id": "cmp",
        "title": "CMP endpoint results",
        "scope": "Moves an ideal removal plane. It does not model polish pressure or time.",
        "starts_from": "Prescribed void-free copper control.",
        "input_label": "Endpoint offset",
        "default_frame": 1,
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
        seed_mesh["nodes"], seed_mesh["lines"], CONFIG["failure_chain_field_sample_xs"][1]
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
    ps.setDimension(2)
    ps.setNumThreads(4)
    data = {
        "schema_version": 1,
        "coordinate_system": {
            "x_units": "model length",
            "y_units": "model length",
            "y_positive": "up",
            "view_box": CONFIG["view_box_full"],
        },
        "provenance": {
            "grid_spacing": GEOMETRY["grid_delta"],
            "rays_per_point": CONFIG["rays_per_point"],
            "rng_seed": CONFIG["rng_seed"],
            "stochastic_robustness": "single saved seed; repeatability not established",
            "config_sha256": checkpoint.file_sha256("config/process.toml"),
            "builder_sha256": checkpoint.file_sha256(Path(__file__)),
            "viennaps_version": version("viennaps"),
            "viennals_version": version("viennals"),
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

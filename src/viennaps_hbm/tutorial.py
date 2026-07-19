"""Run one compact, chronological TSV teaching example."""

from __future__ import annotations

import json
import math
import argparse
from pathlib import Path

import viennaps as ps

from .config import DEFAULT_CONFIG, load_config
from . import process
from .layer_metrics import layer_thickness_metrics_full_2d
from .layer_process_models import deposit_directional_fraction
from . import traveler_metrics as metrics


def _mesh(domain, material):
    return next(
        item
        for item in metrics.raw_level_set_meshes(domain)
        if item["material"] == material
    )


def _finite_values(values):
    return all(value is not None and math.isfinite(float(value)) for value in values)


def run_tutorial(config_path=DEFAULT_CONFIG, output_dir="tutorial-output"):
    """Run the six-step example and return its measured summary."""
    config = load_config(config_path)
    tutorial = config["tutorial"]
    geometry = config["defaults"]["geometry"]
    etch = tutorial["etch"]
    surface_y = tutorial["surface_y"]
    field_xs = tuple(tutorial["field_xs"])

    ps.setDimension(2)
    ps.setNumThreads(int(tutorial["threads"]))
    ps.Logger.setLogLevel(ps.LogLevel.ERROR)

    domain = process.make_initial_geometry(
        radius=tutorial["mask"]["radius"],
        mask_height=tutorial["mask"]["height"],
        taper=tutorial["mask"]["taper_degrees"],
        grid_delta=geometry["grid_delta"],
        x_extent=geometry["x_extent"],
        y_extent=geometry["y_extent"],
        hole_shape=ps.HoleShape.FULL,
    )
    mask = _mesh(domain, ps.Material.Mask)
    mask_result = metrics.pattern_metrics_2d(
        mask["nodes"],
        mask["lines"],
        surface_y=surface_y,
        target_cd=config["targets"]["pattern"]["width"],
        target_mask_height=config["targets"]["pattern"]["mask_height"],
        max_radius=tutorial["max_profile_radius"],
    )

    process.bosch_etch(
        domain,
        num_cycles=etch["cycles"],
        etch_time=etch["time_per_cycle"],
        initial_etch_time=etch["initial_time"],
        ion_source_exponent=etch["ion_source_exponent"],
        neutral_sticking_probability=etch["neutral_sticking"],
        deposition_thickness=etch["wall_protection"],
        deposition_sticking_probability=etch["wall_protection_sticking"],
        neutral_rate=etch["neutral_rate"],
        ion_rate=etch["ion_rate"],
        theta_r_min=etch["minimum_reflection_angle"],
        rays_per_point=etch["rays_per_point"],
        rng_seed=tutorial["random_seed"],
        mask_ion_rate=etch["mask_ion_rate"],
    )
    silicon = _mesh(domain, ps.Material.Si)
    floor_y = float(silicon["nodes"][:, 1].min())
    etch_result = metrics.etch_profile_metrics_2d(
        silicon["nodes"],
        silicon["lines"],
        surface_y=surface_y,
        floor_y=floor_y,
        target_cd=config["targets"]["etch"]["target_width"],
        max_radius=tutorial["max_profile_radius"],
    )

    process.strip_pattern_mask(domain)
    liner_inner = metrics.raw_level_set_meshes(domain)[-1]
    liner = tutorial["liner"]
    process.deposit_conformal(
        domain,
        ps.Material.SiO2,
        liner["amount"],
        sticking=liner["sticking"],
        rays_per_point=liner["rays_per_point"],
        rng_seed=tutorial["random_seed"] + 1,
    )
    liner_outer = metrics.raw_level_set_meshes(domain)[-1]
    liner_result = layer_thickness_metrics_full_2d(
        liner_inner["nodes"],
        liner_inner["lines"],
        liner_outer["nodes"],
        liner_outer["lines"],
        surface_y=surface_y,
        floor_y=floor_y,
        via_radius=tutorial["mask"]["radius"],
        field_xs=field_xs,
        sample_count=tutorial["layer_samples"],
    )

    barrier = tutorial["barrier"]
    deposit_directional_fraction(
        domain,
        ps.Material.TaN,
        field_dose=barrier["amount"],
        isotropic_fraction=barrier["all_angle_fraction"],
    )
    seed = tutorial["seed"]
    deposit_directional_fraction(
        domain,
        process.CU_SEED_MATERIAL,
        field_dose=seed["amount"],
        isotropic_fraction=seed["all_angle_fraction"],
    )

    seed_mesh = metrics.raw_level_set_meshes(domain)[-1]
    seed_floor_y = float(seed_mesh["nodes"][:, 1].min())
    field_y = metrics.surface_height_at_x(
        seed_mesh["nodes"], seed_mesh["lines"], field_xs[1]
    )
    if field_y is None:
        raise RuntimeError("seed surface is unresolved at the field sample")

    copper = tutorial["copper"]
    process.cu_fill(
        domain,
        copper["amount"],
        all_angle_fraction=copper["all_angle_fraction"],
    )
    copper_mesh = metrics.raw_level_set_meshes(domain)[-1]
    fill_result = metrics.fill_topology_metrics_2d(
        copper_mesh["nodes"],
        copper_mesh["lines"],
        field_y=field_y,
        floor_y=seed_floor_y,
        via_x_bounds=tuple(tutorial["via_x_bounds"]),
        field_sample_xs=field_xs,
        center_x=0.0,
        tolerance=geometry["grid_delta"],
        grid_delta=geometry["grid_delta"],
    )

    ps.Planarize(domain, tutorial["cmp"]["plane_y"]).apply()
    copper_after_cmp = metrics.raw_level_set_meshes(domain)[-1]

    etch_names = ("depth", "cd_top", "cd_middle", "cd_bottom", "max_bow")
    if not _finite_values(etch_result[name] for name in etch_names):
        raise RuntimeError("etch measurements are incomplete")
    summary = {
        "scope": {
            "copper": "geometric growth; not electroplating physics",
            "cmp": "ideal plane cut; not pad or slurry physics",
            "equipment_recipe": False,
        },
        "stages": ["mask", "etch", "liner", "barrier", "seed", "copper", "cmp"],
        "mask": {"opening_cd": mask_result["opening_cd_bottom"]},
        "etch": {name: etch_result[name] for name in etch_names},
        "liner": {
            "minimum_thickness": liner_result["minimum_local_thickness"],
            "aperture_open": liner_result["aperture_open"],
        },
        "copper": {
            name: fill_result[name]
            for name in (
                "void_free",
                "open_void",
                "closed_void_count",
                "remaining_void_area",
                "topology_valid",
            )
        },
        "cmp": {"copper_surface_nodes": len(copper_after_cmp["nodes"])},
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    return summary


def main():
    """Run the tutorial from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--output", default="tutorial-output")
    args = parser.parse_args()
    result = run_tutorial(args.config, args.output)
    print("Completed: " + " -> ".join(result["stages"]))
    print(f"Measurements: {Path(args.output) / 'summary.json'}")

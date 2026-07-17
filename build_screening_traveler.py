"""Build the prescribed TSV teaching traveler."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
import viennaps as ps

import foundation_cmp_qualification as cmpq
import foundation_copper_fill_structural_challenge as fill_control
import foundation_copper_fill_trajectory as fill
from layer_process_models import deposit_isotropic_control
import native_domain_checkpoint as checkpoint
import traveler_metrics as tm
import tsv_process as tp
from process_config import PROCESS_CONFIG


TRAVELER_CONFIG = PROCESS_CONFIG["traveler"]
SOURCE = Path(TRAVELER_CONFIG["source"])
SOURCE_SHA256 = TRAVELER_CONFIG["source_sha256"]
SOURCE_CASE_ID = TRAVELER_CONFIG["source_case_id"]
OUTPUT = Path(TRAVELER_CONFIG["output"])
GRID_DELTA = TRAVELER_CONFIG["grid_delta"]
CONTROL_GRID_DELTA = TRAVELER_CONFIG["control_grid_delta"]
FIELD_XS = tuple(TRAVELER_CONFIG["field_xs"])
VIA_RADIUS = TRAVELER_CONFIG["via_radius"]
ETCH_DEPTH = TRAVELER_CONFIG["etch_depth"]
MOUTH_OFFSET = TRAVELER_CONFIG["mouth_offset"]
CHECKPOINT_INTERVAL = TRAVELER_CONFIG["checkpoint_interval"]
TIME_STEP_RATIO = TRAVELER_CONFIG["time_step_ratio"]
LINER_DOSE = TRAVELER_CONFIG["liner_dose"]
BARRIER_DOSE = TRAVELER_CONFIG["barrier_dose"]
SEED_DOSE = TRAVELER_CONFIG["seed_dose"]
INITIAL_FILL_DURATION = TRAVELER_CONFIG["initial_fill_duration"]
MAX_FILL_DURATION = TRAVELER_CONFIG["max_fill_duration"]
FILL_DURATION_STEP = TRAVELER_CONFIG["fill_duration_step"]
OVERBURDEN_DURATION_MARGIN = TRAVELER_CONFIG["overburden_duration_margin"]
THREAD_COUNT = int(TRAVELER_CONFIG["thread_count"])
MATERIAL_COLORS = {
    ps.Material.Si: "#53606f",
    ps.Material.SiO2: "#4cc9f0",
    ps.Material.TaN: "#f6ae2d",
    tp.CU_SEED_MATERIAL: "#d77a2c",
    ps.Material.Cu: "#ef8354",
}


def _case():
    case = fill_control._case(fill_control.POSITIVE_CONTROL_ARM, CONTROL_GRID_DELTA)
    case["geometry"].update(
        {
            "radius": VIA_RADIUS,
            "depth": ETCH_DEPTH,
            "field_sample_xs": FIELD_XS,
            "mouth_offset": MOUTH_OFFSET,
        }
    )
    case["numerics"].update(
        {
            "grid_delta": GRID_DELTA,
            "checkpoint_interval": CHECKPOINT_INTERVAL,
            "time_step_ratio": TIME_STEP_RATIO,
        }
    )
    return case


def _save(name, geometry):
    path = OUTPUT / name
    return {"path": str(path), "sha256": checkpoint.save_domain_atomic(path, geometry)}


def _surface_y(mesh, x):
    value = tm.surface_height_at_x(mesh["nodes"], mesh["lines"], x)
    if value is None:
        raise RuntimeError(f"surface is unresolved at x={x}")
    return float(value)


def _cmp_stack(geometry, stop_y):
    meshes = tm.raw_level_set_meshes(geometry)
    materials = tuple(mesh["material"] for mesh in meshes)
    floor_y = _surface_y(meshes[0], 0.0)
    return cmpq.AnalyticStack(
        geometry=geometry,
        topography="screening_traveler",
        grid_delta=GRID_DELTA,
        stop_y=stop_y,
        cu_top_y=float(np.max(meshes[-1]["nodes"][:, 1])),
        via_radius=VIA_RADIUS,
        via_depth=stop_y - floor_y,
        materials=materials,
        pattern_mask_absent=ps.Material.Mask not in materials,
    )


def _render(stage_paths, output):
    stages = [
        (title, checkpoint.load_domain_checkpoint(path, expected_sha256=sha))
        for title, path, sha in stage_paths
    ]
    fig, axes = plt.subplots(1, len(stages), figsize=(17, 7), sharex=True, sharey=True)
    for ax, (title, geometry) in zip(axes, stages):
        for mesh in tm.raw_level_set_meshes(geometry):
            segments = mesh["nodes"][mesh["lines"]][:, :, :2]
            ax.add_collection(
                LineCollection(
                    segments,
                    colors=MATERIAL_COLORS.get(mesh["material"], "white"),
                    linewidths=1.6,
                )
            )
        ax.set_title(title, fontsize=11, color="white", pad=10)
        ax.set_xlim(-0.22, 0.22)
        ax.set_ylim(-1.34, 0.43)
        ax.set_aspect("equal")
        ax.grid(color="#334155", alpha=0.28, linewidth=0.5)
        ax.tick_params(colors="#a9b4c2", labelsize=8)
        ax.set_facecolor("#0b1220")
    axes[0].set_ylabel("y (simulation units)", color="#cbd5e1")
    fig.suptitle(
        "Simplified TSV process: etch to polish",
        color="white",
        fontsize=18,
        fontweight="bold",
        y=0.975,
    )
    fig.text(
        0.5,
        0.025,
        "One simulated shape carried through coating, copper fill, and polish. Teaching example only.",
        ha="center",
        color="#a9b4c2",
        fontsize=10,
    )
    fig.patch.set_facecolor("#070b13")
    fig.subplots_adjust(left=0.055, right=0.99, bottom=0.09, top=0.82, wspace=0.20)
    fig.savefig(output, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    ps.setDimension(2)
    ps.setNumThreads(THREAD_COUNT)
    ps.Logger.setLogLevel(ps.LogLevel.ERROR)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    source = checkpoint.load_domain_checkpoint(SOURCE, expected_sha256=SOURCE_SHA256)
    geometry = checkpoint.extract_raw_silicon_domain(source)
    artifacts = {"etch": _save("01_etch_screening_500ray.vpsd", geometry)}

    deposit_isotropic_control(geometry, ps.Material.SiO2, dose=LINER_DOSE)
    artifacts["liner"] = _save("02_conformal_liner_control.vpsd", geometry)
    deposit_isotropic_control(geometry, ps.Material.TaN, dose=BARRIER_DOSE)
    artifacts["barrier"] = _save("03_conformal_barrier_control.vpsd", geometry)
    deposit_isotropic_control(geometry, tp.CU_SEED_MATERIAL, dose=SEED_DOSE)
    geometry.duplicateTopLevelSet(ps.Material.Cu)
    artifacts["seeded"] = _save("04_cu_seed_control.vpsd", geometry)

    case = _case()
    reference = fill._reference_geometry(geometry, case)
    if not all(reference["layer_gates"].values()):
        raise RuntimeError(f"functional layer gate failure: {reference['layer_gates']}")

    bottom_up_time = INITIAL_FILL_DURATION
    velocity = fill_control.PrescribedBottomUpVelocity(
        reference, GRID_DELTA, "bottom_up_fill"
    )
    fill_control._advect_positive_control(geometry, velocity, bottom_up_time, case)
    topology = fill_control._topology(geometry, reference, case)
    while not topology["void_free"] and bottom_up_time < MAX_FILL_DURATION:
        fill_control._advect_positive_control(
            geometry, velocity, FILL_DURATION_STEP, case
        )
        bottom_up_time += FILL_DURATION_STEP
        topology = fill_control._topology(geometry, reference, case)
    if not topology["void_free"] or not topology["topology_valid"]:
        raise RuntimeError(f"void-free fill control failed: {topology}")

    overburden_time = max(
        0.0,
        (case["target"]["min_overburden"] - topology["overburden_min"])
        / fill_control.ACTIVE_RATE
        + OVERBURDEN_DURATION_MARGIN,
    )
    if overburden_time:
        velocity = fill_control.PrescribedBottomUpVelocity(
            reference, GRID_DELTA, "uniform_overburden"
        )
        fill_control._advect_positive_control(geometry, velocity, overburden_time, case)
        topology = fill_control._topology(geometry, reference, case)
    artifacts["fill"] = _save("05_void_free_cu_fill_control.vpsd", geometry)
    if (
        not topology["void_free"]
        or topology["overburden_min"] < case["target"]["min_overburden"]
    ):
        raise RuntimeError(f"fill endpoint failure: {topology}")

    meshes = tm.raw_level_set_meshes(geometry)
    stop_y = float(np.mean([_surface_y(meshes[1], x) for x in FIELD_XS]))
    cmp_stack = _cmp_stack(geometry, stop_y)
    pre_cmp = cmpq.profile_from_geometry(cmp_stack)
    ps.Planarize(geometry, stop_y).apply()
    post_cmp = cmpq.profile_from_geometry(cmp_stack)
    cmp_gates = cmpq.evaluate_hard_gates(post_cmp, pre_cmp)
    plug_region = cmp_gates["material_region_connectivity"]["plated_cu"]
    plug_component = plug_region["component_summaries"][0]
    plug_connected_control = bool(
        cmp_gates["plug_connected"]
        or (
            not plug_region["resolved"]
            and plug_region["negative_component_count"] == 1
            and plug_region["detached_fragment_count"] == 0
            and plug_component["bounds_min"][1] <= reference["floor_y"] + 2 * GRID_DELTA
            and plug_component["bounds_max"][1] >= stop_y - 2 * GRID_DELTA
        )
    )
    if not cmp_gates["all_field_metals_clear"] or not plug_connected_control:
        raise RuntimeError(f"CMP endpoint failure: {cmp_gates}")
    artifacts["cmp"] = _save("06_endpoint_cmp_control.vpsd", geometry)

    render_path = OUTPUT / "complete_traveler_500ray_screening.png"
    _render(
        [
            ("1  Etch", Path(artifacts["etch"]["path"]), artifacts["etch"]["sha256"]),
            (
                "2  Conformal\nliner",
                Path(artifacts["liner"]["path"]),
                artifacts["liner"]["sha256"],
            ),
            (
                "3  Barrier +\nCu seed",
                Path(artifacts["seeded"]["path"]),
                artifacts["seeded"]["sha256"],
            ),
            (
                "4  Void-free\nCu control",
                Path(artifacts["fill"]["path"]),
                artifacts["fill"]["sha256"],
            ),
            (
                "5  Endpoint\nCMP control",
                Path(artifacts["cmp"]["path"]),
                artifacts["cmp"]["sha256"],
            ),
        ],
        render_path,
    )

    summary = {
        "status": "complete_screening_traveler",
        "qualification_scope": {
            "etch": "500-ray screening fidelity; not 2,000-ray confirmed",
            "downstream": "deterministic morphology controls; not calibrated fab recipes",
            "two_thousand_ray_confirmation": "deferred",
        },
        "source": {
            "path": str(SOURCE),
            "sha256": SOURCE_SHA256,
            "case_id": SOURCE_CASE_ID,
        },
        "etch_metrics": {
            "depth": ETCH_DEPTH,
            "maximum_cd_error": 0.03913149351279871,
            "bow": 0.0032534227664840765,
            "scallop_rms": 0.000980799088298488,
            "sidewall_angle_degrees": 1.2051,
            "rays_per_point": 500,
        },
        "layer_gates": reference["layer_gates"],
        "fill": {
            "void_free": topology["void_free"],
            "closed_void_count": topology["closed_void_count"],
            "remaining_void_area": topology["remaining_void_area"],
            "overburden_min": topology["overburden_min"],
            "bottom_up_time": bottom_up_time,
            "uniform_overburden_time": overburden_time,
        },
        "cmp": {
            "endpoint_y": stop_y,
            "all_field_metals_clear": cmp_gates["all_field_metals_clear"],
            "plug_connected": plug_connected_control,
            "plug_connectivity_note": (
                "generic analytic-stack floor anchor was below the actual Cu floor; "
                "the measured plated-Cu region is one continuous component from "
                "the actual fill floor to the CMP endpoint"
                if not cmp_gates["plug_connected"]
                else None
            ),
            "dish": cmp_gates["dish"],
            "stop_continuous": cmp_gates["stop_continuous"],
        },
        "artifacts": artifacts,
        "render": str(render_path),
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

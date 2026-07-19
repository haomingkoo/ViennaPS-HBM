"""Bounded CMP controls on one deterministic, distinct-material stack."""

import json
from pathlib import Path

import numpy as np
import viennaps as ps

import traveler_metrics as tm
import tsv_process as tp


GRID_DELTA = 0.01
VIA_RADIUS = 0.15
FIELD_SAMPLE_XS = (0.3, 0.4)
BASE_CU_TOP_Y = 0.18
FIELD_BUMP_TOP_Y = 0.23
RATE_SEED_FILE = (
    Path(__file__).resolve().parents[1]
    / "ViennaPS/examples/sputterDeposition/rates2D.csv"
)


def build_stack():
    geometry = ps.Domain(gridDelta=GRID_DELTA, xExtent=1.0, yExtent=1.5)
    ps.MakeHole(
        domain=geometry,
        holeRadius=VIA_RADIUS,
        holeDepth=1.25,
        maskHeight=0.3,
        holeShape=ps.HoleShape.QUARTER,
    ).apply()
    tp.strip_pattern_mask(geometry)
    for material, thickness in (
        (ps.Material.SiO2, 0.03),
        (ps.Material.TaN, 0.01),
        (tp.CU_SEED_MATERIAL, 0.01),
    ):
        geometry.duplicateTopLevelSet(material)
        ps.Process(
            geometry, ps.IsotropicProcess(rate=thickness), 1.0
        ).apply()
    stop = tm.raw_level_set_meshes(geometry)[1]
    stop_y = max(tm.line_intersections_at_x(stop["nodes"], stop["lines"], 0.4))
    ps.MakePlane(
        domain=geometry,
        height=BASE_CU_TOP_Y,
        material=ps.Material.Cu,
        addToExisting=True,
    ).apply()
    # A known field step makes the height-weighted arm a real topography test.
    bump = ps.ls.Domain(geometry.getGrid())
    ps.ls.MakeGeometry(
        bump,
        ps.ls.Box([0.25, BASE_CU_TOP_Y], [0.45, FIELD_BUMP_TOP_Y]),
    ).apply()
    geometry.applyBooleanOperation(
        bump, ps.ls.BooleanOperationEnum.UNION, False
    )
    return geometry, stop_y


def measure(geometry, stop_y):
    meshes = tm.raw_level_set_meshes(geometry)
    return tm.cmp_profile_metrics_2d(
        post_cu_nodes=meshes[4]["nodes"],
        post_cu_lines=meshes[4]["lines"],
        post_seed_nodes=meshes[3]["nodes"],
        post_seed_lines=meshes[3]["lines"],
        post_barrier_nodes=meshes[2]["nodes"],
        post_barrier_lines=meshes[2]["lines"],
        post_stop_nodes=meshes[1]["nodes"],
        post_stop_lines=meshes[1]["lines"],
        post_substrate_nodes=meshes[0]["nodes"],
        post_substrate_lines=meshes[0]["lines"],
        field_sample_xs=FIELD_SAMPLE_XS,
        center_x=0.01,
        target_field_y=stop_y,
        pre_stop_field_y=stop_y,
        stop_initial_thickness=0.03,
        pre_cu_center_y=BASE_CU_TOP_Y,
        pre_substrate_field_y=-0.0001,
    )


def material_bounds(geometry):
    """Reference bounds for functional material-retention checks."""
    materials = {
        "substrate": ps.Material.Si,
        "stop_liner": ps.Material.SiO2,
        "barrier": ps.Material.TaN,
        "seed": tp.CU_SEED_MATERIAL,
        "plug": ps.Material.Cu,
    }
    result = {}
    for name, material in materials.items():
        nodes = tm.material_region_mesh(geometry, material)["nodes"]
        result[name] = None if not len(nodes) else {
            "min": nodes[:, :2].min(axis=0),
            "max": nodes[:, :2].max(axis=0),
        }
    return result


def protected_material_gates(geometry, metrics, reference):
    """Require functional via-spanning material, not any surviving fragment."""
    post = material_bounds(geometry)
    # Numerical survival tolerance only; this does not relax a product target.
    tolerance = 2.0 * GRID_DELTA
    # Radius 0.12 is the declared 0.15 target minus its 0.03 tolerance.
    minimum_radius = VIA_RADIUS - 0.03 - tolerance
    target_y = reference["stop_liner"]["max"][1]

    def retains_via_span(name):
        before, after = reference[name], post[name]
        return bool(
            before is not None
            and after is not None
            and after["min"][1] <= before["min"][1] + tolerance
            and after["max"][1] >= target_y - tolerance
            and after["max"][0] >= minimum_radius
        )

    materials = geometry.getMaterialMap()
    pattern_mask_stripped = all(
        materials.getMaterialAtIdx(index) != ps.Material.Mask
        for index in range(geometry.getNumberOfLevelSets())
    )
    surface_nodes = np.asarray(geometry.getSurfaceMesh(False).getNodes())
    gates = {
        "domain_nonempty": bool(surface_nodes.ndim == 2 and len(surface_nodes)),
        "pattern_mask_stripped": pattern_mask_stripped,
        "stop_liner_survives": bool(
            metrics.get("stop_layer_survives", False)
            and metrics.get("field_erosion") is not None
            and metrics["field_erosion"] <= tolerance
            and retains_via_span("stop_liner")
        ),
        "barrier_survives_in_via": retains_via_span("barrier"),
        "seed_survives_in_via": retains_via_span("seed"),
        "cu_plug_survives": bool(
            metrics.get("plug_survives", False) and retains_via_span("plug")
        ),
        "substrate_survives": bool(
            metrics.get("substrate_loss") is not None
            and metrics["substrate_loss"] <= tolerance
            and post["substrate"] is not None
        ),
    }
    gates["all_protected_materials_survive"] = all(gates.values())
    return gates


def snapshot(geometry, stop_y, reference, stage_duration, total_duration=None):
    metrics = measure(geometry, stop_y)
    return {
        "stage_duration": float(stage_duration),
        "total_duration": float(
            stage_duration if total_duration is None else total_duration
        ),
        "metrics": metrics,
        "gates": protected_material_gates(geometry, metrics, reference),
    }


def run_planarize_control():
    geometry, stop_y = build_stack()
    reference = material_bounds(geometry)
    ps.Planarize(geometry, stop_y).apply()
    return {
        "arm": "planarize_ideal_endpoint",
        "evidence_class": "ideal geometry and metric control; not CMP physics",
        "stop_y": stop_y,
        "endpoint": snapshot(geometry, stop_y, reference, 0.0),
    }


def run_selective_first_clear_control(step=0.005, maximum_duration=0.2):
    """Remove plated Cu only and stop at its first field-clear event."""
    geometry, stop_y = build_stack()
    reference = material_bounds(geometry)
    model = ps.IsotropicProcess(
        materialRates={ps.Material.Cu: -1.0}, defaultRate=0.0
    )
    result = None
    for index in range(1, int(round(maximum_duration / step)) + 1):
        ps.Process(geometry, model, step).apply()
        result = snapshot(geometry, stop_y, reference, index * step)
        if result["metrics"]["plated_cu_endpoint_reached"]:
            break
    return {
        "arm": "isotropic_plated_cu_first_clear",
        "evidence_class": "perfect-selectivity limiting control",
        "stop_y": stop_y,
        "rates": {"plated_Cu": -1.0, "all_other_materials": 0.0},
        "step": step,
        "first_clear": result,
    }


def height_weighted_rate(y, stop_y, compliance):
    """Uncalibrated high-surface weighting used only in the controlled arm."""
    return -max(0.0, min(1.0, (y - stop_y) / compliance))


def run_height_weighted_control(
    bulk_step=0.01,
    maximum_bulk_duration=0.5,
    compliance=0.10,
    endpoint_step=0.0025,
    maximum_endpoint_duration=0.05,
    post_endpoint_overpolish=0.005,
):
    """Height-weighted plated-Cu clear followed by explicit selective overpolish."""
    geometry, stop_y = build_stack()
    reference = material_bounds(geometry)
    bulk_model = ps.CSVFileProcess(
        ratesFile=str(RATE_SEED_FILE),
        direction=[0.0, -1.0, 0.0],
        offset=[0.0, 0.0],
        isotropicComponent=0.0,
        directionalComponent=1.0,
        maskMaterials=[
            ps.Material.Mask,
            ps.Material.Si,
            ps.Material.SiO2,
            ps.Material.TaN,
            tp.CU_SEED_MATERIAL,
        ],
        calculateVisibility=True,
    )
    bulk_model.setCustomInterpolator(
        lambda coordinate: height_weighted_rate(
            coordinate[1], stop_y, compliance
        )
    )

    first_clear = None
    for index in range(1, int(round(maximum_bulk_duration / bulk_step)) + 1):
        ps.Process(geometry, bulk_model, bulk_step).apply()
        first_clear = snapshot(geometry, stop_y, reference, index * bulk_step)
        if first_clear["metrics"]["plated_cu_endpoint_reached"]:
            break

    endpoint = None
    post_endpoint = None
    overpolish_rates = {
        ps.Material.Cu: -1.0,
        tp.CU_SEED_MATERIAL: -1.0,
        ps.Material.TaN: -1.0,
        ps.Material.SiO2: 0.0,
        ps.Material.Si: 0.0,
    }
    if first_clear["metrics"]["plated_cu_endpoint_reached"]:
        endpoint_model = ps.IsotropicProcess(
            materialRates=overpolish_rates, defaultRate=0.0
        )
        for index in range(
            1, int(round(maximum_endpoint_duration / endpoint_step)) + 1
        ):
            ps.Process(geometry, endpoint_model, endpoint_step).apply()
            endpoint_duration = index * endpoint_step
            endpoint = snapshot(
                geometry,
                stop_y,
                reference,
                endpoint_duration,
                first_clear["total_duration"] + endpoint_duration,
            )
            if endpoint["metrics"]["endpoint_reached"]:
                break
        if endpoint is not None and endpoint["metrics"]["endpoint_reached"]:
            ps.Process(
                geometry, endpoint_model, post_endpoint_overpolish
            ).apply()
            post_endpoint = snapshot(
                geometry,
                stop_y,
                reference,
                endpoint["stage_duration"] + post_endpoint_overpolish,
                endpoint["total_duration"] + post_endpoint_overpolish,
            )

    return {
        "arm": "height_weighted_plated_cu_then_selective_overpolish",
        "evidence_class": "uncalibrated phenomenological control; not CMP physics",
        "overpolish_evidence_class": (
            "uncalibrated equal metal rates with an ideal zero-rate SiO2 stop"
        ),
        "bulk_law": "-clip((surface_y - stop_y) / compliance, 0, 1)",
        "stop_y": stop_y,
        "initial_center_cu_y": BASE_CU_TOP_Y,
        "initial_field_bump_y": FIELD_BUMP_TOP_Y,
        "compliance": compliance,
        "bulk_step": bulk_step,
        "endpoint_step": endpoint_step,
        "overpolish_rates": {
            "plated_Cu": -1.0,
            "Cu_seed": -1.0,
            "TaN": -1.0,
            "SiO2_stop": 0.0,
            "Si": 0.0,
        },
        "first_clear": first_clear,
        "endpoint": endpoint,
        "post_endpoint_overpolish": post_endpoint,
    }


def test_planarize_is_an_ideal_endpoint_control():
    result = run_planarize_control()
    metrics = result["endpoint"]["metrics"]
    assert metrics["valid"]
    assert metrics["endpoint_reached"]
    assert metrics["stop_layer_survives"]
    assert metrics["dish"] <= 1e-9
    assert result["endpoint"]["gates"]["all_protected_materials_survive"]


def test_selective_isotropic_reaches_first_clear_without_protected_loss():
    result = run_selective_first_clear_control()
    first_clear = result["first_clear"]
    assert first_clear["metrics"]["plated_cu_endpoint_reached"]
    assert not first_clear["metrics"]["seed_endpoint_reached"]
    assert not first_clear["metrics"]["barrier_endpoint_reached"]
    assert first_clear["metrics"]["field_erosion"] == 0.0
    assert first_clear["metrics"]["substrate_loss"] == 0.0
    assert first_clear["gates"]["all_protected_materials_survive"]


def test_height_weighted_arm_records_endpoint_and_post_endpoint_overpolish():
    assert height_weighted_rate(0.03, 0.03, 0.1) == 0.0
    assert height_weighted_rate(0.13, 0.03, 0.1) == -1.0
    result = run_height_weighted_control()
    first_clear = result["first_clear"]
    endpoint = result["endpoint"]
    post_endpoint = result["post_endpoint_overpolish"]
    assert "uncalibrated" in result["evidence_class"]
    assert first_clear["metrics"]["plated_cu_endpoint_reached"]
    exposed_field_y = (
        result["stop_y"]
        + first_clear["metrics"]["residual_field_seed_max"]
        + first_clear["metrics"]["residual_field_barrier_max"]
    )
    assert (
        result["initial_field_bump_y"] - exposed_field_y
        > first_clear["metrics"]["cu_removed_at_center"]
    )
    assert endpoint["metrics"]["endpoint_reached"]
    assert endpoint["gates"]["all_protected_materials_survive"]
    assert post_endpoint["metrics"]["endpoint_reached"]
    assert post_endpoint["gates"]["all_protected_materials_survive"]
    assert post_endpoint["stage_duration"] > endpoint["stage_duration"]
    assert post_endpoint["total_duration"] > endpoint["total_duration"]
    assert post_endpoint["metrics"]["dish"] > endpoint["metrics"]["dish"]
    assert post_endpoint["metrics"]["field_erosion"] == 0.0
    assert post_endpoint["metrics"]["substrate_loss"] == 0.0


def test_one_rate_overpolish_is_a_destructive_control():
    geometry, stop_y = build_stack()
    reference = material_bounds(geometry)
    ps.Process(geometry, ps.IsotropicProcess(rate=-1.0), 0.30).apply()
    metrics = measure(geometry, stop_y)
    gates = protected_material_gates(geometry, metrics, reference)
    assert not metrics["valid"]
    assert metrics["stop_layer_consumed"]
    assert metrics["substrate_loss"] > 0.10
    assert not gates["stop_liner_survives"]
    assert not gates["substrate_survives"]
    assert not gates["all_protected_materials_survive"]


if __name__ == "__main__":
    ps.setNumThreads(1)
    test_planarize_is_an_ideal_endpoint_control()
    test_selective_isotropic_reaches_first_clear_without_protected_loss()
    test_height_weighted_arm_records_endpoint_and_post_endpoint_overpolish()
    test_one_rate_overpolish_is_a_destructive_control()
    print(json.dumps({
        "planarize": run_planarize_control(),
        "selective_first_clear": run_selective_first_clear_control(),
        "height_weighted": run_height_weighted_control(),
    }, indent=2))
    print("controlled CMP checks: PASS")

"""Analytic checks for asymmetric full-width 2D film metrics."""

import math

import numpy as np
import viennals as ls
import viennaps as ps

import full_2d_layer_metrics as fullfilm
import layer_process_models as models
import traveler_metrics as tm
import tsv_process as tp


ps.Logger.setLogLevel(ps.LogLevel.ERROR)


class MaterialGeometry:
    def __init__(self, level_set):
        self.level_set = level_set

    def getMaterialLevelSet(self, _material):
        return self.level_set


def full_via_layer(*, left_wall=-0.13, right_wall=0.13,
                   left_field=0.02, right_field=0.02, floor=-0.98):
    inner = np.asarray([
        [-0.5, 0.0],
        [-0.15, 0.0],
        [-0.15, -1.0],
        [0.15, -1.0],
        [0.15, 0.0],
        [0.5, 0.0],
    ])
    outer = np.asarray([
        [-0.5, left_field],
        [left_wall, left_field],
        [left_wall, floor],
        [right_wall, floor],
        [right_wall, right_field],
        [0.5, right_field],
    ])
    lines = np.column_stack((np.arange(5), np.arange(1, 6)))
    return inner, lines, outer, lines.copy()


def measure(inner, inner_lines, outer, outer_lines):
    return fullfilm.layer_thickness_metrics_full_2d(
        inner,
        inner_lines,
        outer,
        outer_lines,
        surface_y=0.0,
        floor_y=-1.0,
        via_radius=0.15,
    )


def material_box(x0, y0, x1, y1, *, grid_delta):
    level_set = ls.Domain(
        [-0.5, 0.5, -1.2, 0.2],
        [ls.BoundaryConditionEnum.REFLECTIVE_BOUNDARY] * 2,
        grid_delta,
    )
    ls.MakeGeometry(level_set, ls.Box([x0, y0], [x1, y1])).apply()
    return level_set


def union(level_set, other):
    ls.BooleanOperation(
        level_set, other, ls.BooleanOperationEnum.UNION
    ).apply()


def subtract(level_set, other):
    ls.BooleanOperation(
        level_set, other, ls.BooleanOperationEnum.RELATIVE_COMPLEMENT
    ).apply()


def material_u_shape(
    *,
    left_wall=0.02,
    right_wall=0.02,
    left_field=0.02,
    right_field=0.02,
    floor=0.02,
    grid_delta=0.0025,
):
    material = material_box(
        -0.15, -1.0, -0.15 + left_wall, left_field,
        grid_delta=grid_delta,
    )
    for box in (
        material_box(
            0.15 - right_wall, -1.0, 0.15, right_field,
            grid_delta=grid_delta,
        ),
        material_box(
            -0.15, -1.0, 0.15, -1.0 + floor,
            grid_delta=grid_delta,
        ),
        material_box(
            -0.5, 0.0, -0.15 + left_wall, left_field,
            grid_delta=grid_delta,
        ),
        material_box(
            0.15 - right_wall, 0.0, 0.5, right_field,
            grid_delta=grid_delta,
        ),
    ):
        union(material, box)
    return material


def measure_material(
    level_set,
    layer,
    *,
    grid_delta=0.0025,
):
    return fullfilm.material_layer_metrics_full_2d(
        MaterialGeometry(level_set),
        "test-material",
        *layer,
        surface_y=0.0,
        floor_y=-1.0,
        via_radius=0.15,
        grid_delta=grid_delta,
    )


def test_symmetric_full_width_film():
    metrics = measure(*full_via_layer())
    for key in (
        "left_field_thickness",
        "right_field_thickness",
        "left_lower_wall_thickness",
        "right_lower_wall_thickness",
        "floor_thickness",
        "minimum_local_thickness",
    ):
        assert math.isclose(metrics[key], 0.02, abs_tol=1e-12), key
    assert math.isclose(metrics["floor_to_field_conformality"], 1.0)
    assert math.isclose(metrics["lower_wall_to_field_conformality"], 1.0)
    assert math.isclose(metrics["minimum_remaining_aperture"], 0.26)
    assert metrics["aperture_open"]
    assert metrics["layer_continuous"]


def test_asymmetry_uses_conservative_field_reference():
    metrics = measure(*full_via_layer(
        left_wall=-0.14,
        right_wall=0.12,
        left_field=0.02,
        right_field=0.04,
    ))
    assert math.isclose(metrics["left_lower_wall_thickness"], 0.01)
    assert math.isclose(metrics["right_lower_wall_thickness"], 0.03)
    assert math.isclose(metrics["field_thickness"], 0.04)
    assert metrics["field_thickness_reference"] == "maximum_of_left_and_right"
    assert math.isclose(metrics["lower_wall_to_field_conformality"], 0.25)
    assert math.isclose(metrics["field_thickness_asymmetry"], 0.5)


def test_clipped_quarter_section_is_rejected():
    inner = np.asarray([
        [0.0, -0.98],
        [0.15, -0.98],
        [0.15, 0.0],
        [0.5, 0.0],
    ])
    outer = np.asarray([
        [0.0, -0.96],
        [0.13, -0.96],
        [0.13, 0.02],
        [0.5, 0.02],
    ])
    lines = np.column_stack((np.arange(3), np.arange(1, 4)))
    try:
        measure(inner, lines, outer, lines)
    except ValueError as error:
        assert "required field or floor sample" in str(error)
    else:
        raise AssertionError("full-width metric accepted a clipped quarter section")


def test_material_region_connectivity_passes_intact_film():
    metrics = measure_material(
        material_u_shape(),
        full_via_layer(),
    )
    assert metrics["layer_continuous"]
    assert metrics["material_connectivity_resolved"]
    assert metrics["material_region_connected_field_to_floor"]
    assert metrics["detached_material_fragment_count"] == 0


def test_material_region_cut_fails_despite_good_sampled_thickness():
    material = material_u_shape()
    subtract(
        material,
        material_box(0.12, -0.64, 0.16, -0.59, grid_delta=0.0025),
    )
    metrics = measure_material(material, full_via_layer())
    assert math.isclose(metrics["minimum_local_thickness"], 0.02)
    assert metrics["layer_continuous"]
    assert metrics["material_connectivity_resolved"]
    assert not metrics["material_region_connected_field_to_floor"]


def test_subresolution_pinhole_risk_is_unresolved_not_connected():
    layer = full_via_layer(left_wall=-0.145)
    metrics = measure_material(material_u_shape(left_wall=0.005), layer)
    assert metrics["minimum_local_thickness"] <= 0.005 + 1e-12
    assert not metrics["material_connectivity_resolved"]
    assert not metrics["material_region_connected_field_to_floor"]
    assert "local_thickness_at_or_below_resolution_limit" in (
        metrics["material_connectivity_unresolved_reasons"]
    )


def test_asymmetric_but_resolved_film_uses_conservative_margin():
    layer = full_via_layer(
        left_wall=-0.14,
        right_wall=0.12,
        left_field=0.02,
        right_field=0.04,
        floor=-0.97,
    )
    material = material_u_shape(
        left_wall=0.01,
        right_wall=0.03,
        left_field=0.02,
        right_field=0.04,
        floor=0.03,
    )
    metrics = measure_material(material, layer)
    assert math.isclose(metrics["minimum_local_thickness"], 0.01)
    assert math.isclose(metrics["lower_wall_to_field_conformality"], 0.25)
    assert metrics["material_connectivity_resolved"]
    assert metrics["material_region_connected_field_to_floor"]


def test_distinct_sio2_tan_and_cuseed_regions_remain_connected():
    geometry = ps.Domain(gridDelta=0.01, xExtent=1.0, yExtent=1.0)
    ps.MakeHole(
        domain=geometry,
        holeRadius=0.15,
        holeDepth=0.5,
        maskHeight=0.0,
        maskTaperAngle=0.0,
        holeShape=ps.HoleShape.FULL,
    ).apply()
    deposited = []
    surface_y = 0.0
    floor_y = -0.5
    via_radius = 0.15
    for material in (
        ps.Material.SiO2,
        ps.Material.TaN,
        tp.CU_SEED_MATERIAL,
    ):
        inner = tm.raw_level_set_meshes(geometry)[-1]
        models.deposit_isotropic_control(geometry, material, dose=0.03)
        outer = tm.raw_level_set_meshes(geometry)[-1]
        deposited.append((
            material, inner, outer, surface_y, floor_y, via_radius
        ))
        surface_y += 0.03
        floor_y += 0.03
        via_radius -= 0.03

    assert geometry.getNumberOfLevelSets() == 4
    for material, inner, outer, surface_y, floor_y, via_radius in deposited:
        metrics = fullfilm.material_layer_metrics_full_2d(
            geometry,
            material,
            inner["nodes"],
            inner["lines"],
            outer["nodes"],
            outer["lines"],
            surface_y=surface_y,
            floor_y=floor_y,
            via_radius=via_radius,
            grid_delta=0.01,
        )
        assert metrics["material_connectivity_resolved"], material
        assert metrics["material_region_connected_field_to_floor"], material


if __name__ == "__main__":
    test_symmetric_full_width_film()
    test_asymmetry_uses_conservative_field_reference()
    test_clipped_quarter_section_is_rejected()
    test_material_region_connectivity_passes_intact_film()
    test_material_region_cut_fails_despite_good_sampled_thickness()
    test_subresolution_pinhole_risk_is_unresolved_not_connected()
    test_asymmetric_but_resolved_film_uses_conservative_margin()
    test_distinct_sio2_tan_and_cuseed_regions_remain_connected()
    print("full-width layer metric checks: PASS")

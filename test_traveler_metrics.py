import math

import numpy as np
import viennals as ls

import traveler_metrics as tm


class MaterialGeometry:
    def __init__(self, level_set):
        self.level_set = level_set

    def getMaterialLevelSet(self, _material):
        return self.level_set


def material_box(x0, y0, x1, y1, *, grid_delta=0.005):
    level_set = ls.Domain(
        [-0.5, 0.5, -1.4, 0.2],
        [ls.BoundaryConditionEnum.REFLECTIVE_BOUNDARY] * 2,
        grid_delta,
    )
    ls.MakeGeometry(level_set, ls.Box([x0, y0], [x1, y1])).apply()
    return level_set


def combine_material(level_set, other, operation):
    ls.BooleanOperation(level_set, other, operation).apply()


def u_shaped_material(*, grid_delta=0.005):
    material = material_box(
        -0.16, -1.25, -0.13, 0.02, grid_delta=grid_delta
    )
    combine_material(
        material,
        material_box(0.13, -1.25, 0.16, 0.02, grid_delta=grid_delta),
        ls.BooleanOperationEnum.UNION,
    )
    combine_material(
        material,
        material_box(-0.16, -1.25, 0.16, -1.22, grid_delta=grid_delta),
        ls.BooleanOperationEnum.UNION,
    )
    return material


def material_connectivity(level_set, *, local_thickness=0.03):
    return tm.material_region_connectivity_2d(
        MaterialGeometry(level_set),
        "test-material",
        floor_y=-1.235,
        field_y=0.0,
        via_radius=0.15,
        grid_delta=0.005,
        local_minimum_thickness=local_thickness,
    )


def wall(radius_fn, depth=1.0, count=401):
    fractions = np.linspace(0.0, 1.0, count)
    nodes = np.column_stack(([radius_fn(f) for f in fractions], -depth * fractions))
    lines = np.column_stack((np.arange(count - 1), np.arange(1, count)))
    return nodes, lines


def closed_square(x0, y0, x1, y1, offset=0):
    nodes = np.asarray([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=float)
    lines = np.asarray([[0, 1], [1, 2], [2, 3], [3, 0]], dtype=int) + offset
    return nodes, lines


def quarter_via_layer(radius=0.15, depth=1.0, thickness=0.02):
    inner = np.asarray([
        [0.0, -depth], [radius, -depth], [radius, 0.0], [0.5, 0.0]
    ])
    outer = np.asarray([
        [0.0, -depth + thickness],
        [radius - thickness, -depth + thickness],
        [radius - thickness, thickness],
        [0.5, thickness],
    ])
    lines = np.asarray([[0, 1], [1, 2], [2, 3]])
    return inner, lines, outer, lines.copy()


def test_vertical_wall_cd_profile():
    nodes, lines = wall(lambda _: 0.15)
    metrics = tm.etch_profile_metrics_2d(
        nodes, lines, surface_y=0.0, floor_y=-1.0, target_cd=0.30
    )
    assert math.isclose(metrics["cd_top"], 0.30, abs_tol=1e-12)
    assert math.isclose(metrics["cd_middle"], 0.30, abs_tol=1e-12)
    assert math.isclose(metrics["cd_bottom"], 0.30, abs_tol=1e-12)
    assert math.isclose(metrics["sidewall_angle_deg"], 0.0, abs_tol=1e-12)
    assert metrics["max_bow"] < 1e-12
    assert metrics["scallop_rms"] < 1e-12


def test_pattern_metrics_measure_cd_height_and_taper():
    vertical_nodes, vertical_lines = wall(lambda _: 0.15, depth=-0.3)
    vertical = tm.pattern_metrics_2d(
        vertical_nodes,
        vertical_lines,
        surface_y=0.0,
        target_cd=0.30,
        target_mask_height=0.30,
    )
    assert math.isclose(vertical["opening_cd_bottom"], 0.30, abs_tol=1e-12)
    assert math.isclose(vertical["opening_cd_top"], 0.30, abs_tol=1e-12)
    assert math.isclose(vertical["mask_height"], 0.30, abs_tol=1e-12)
    assert math.isclose(vertical["mask_sidewall_angle_deg"], 0.0, abs_tol=1e-12)

    tapered_nodes, tapered_lines = wall(lambda f: 0.15 + 0.02 * f, depth=-0.3)
    tapered = tm.pattern_metrics_2d(
        tapered_nodes,
        tapered_lines,
        surface_y=0.0,
        target_cd=0.30,
        target_mask_height=0.30,
    )
    assert tapered["opening_cd_top"] > tapered["opening_cd_bottom"]
    assert tapered["mask_sidewall_angle_deg"] > 0.0

    full_nodes = np.asarray([
        [-0.15, 0.0],
        [-0.17, 0.3],
        [0.17, 0.3],
        [0.15, 0.0],
    ])
    full_lines = np.asarray([[0, 1], [1, 2], [2, 3]])
    full = tm.pattern_metrics_2d(
        full_nodes,
        full_lines,
        surface_y=0.0,
        target_cd=0.30,
        target_mask_height=0.30,
    )
    assert full["geometry_kind"] == "full"
    assert math.isclose(full["opening_cd_bottom"], 0.302, abs_tol=1e-12)
    assert math.isclose(full["opening_center_middle"], 0.0, abs_tol=1e-12)
    assert math.isclose(full["opening_center_shift"], 0.0, abs_tol=1e-12)

    shifted_nodes = full_nodes.copy()
    shifted_nodes[0, 0] += 0.01
    shifted = tm.pattern_metrics_2d(
        shifted_nodes,
        full_lines,
        surface_y=0.0,
        target_cd=0.30,
        target_mask_height=0.30,
    )
    assert shifted["opening_center_shift"] < 0.0
    assert shifted["mask_left_sidewall_angle_deg"] != shifted["mask_right_sidewall_angle_deg"]


def test_taper_and_bow_are_distinct():
    tapered_nodes, lines = wall(lambda f: 0.16 - 0.04 * f)
    tapered = tm.etch_profile_metrics_2d(
        tapered_nodes, lines, surface_y=0.0, floor_y=-1.0, target_cd=0.30
    )
    assert tapered["sidewall_angle_deg"] > 2.0
    assert tapered["max_bow"] < 1e-12
    assert tapered["cd_top"] > tapered["cd_bottom"]

    bowed_nodes, lines = wall(lambda f: 0.15 + 0.02 * math.sin(math.pi * f))
    bowed = tm.etch_profile_metrics_2d(
        bowed_nodes, lines, surface_y=0.0, floor_y=-1.0, target_cd=0.30
    )
    assert bowed["max_bow"] > 0.01
    assert abs(bowed["sidewall_angle_deg"]) < 0.5


def test_parallel_layer_distance():
    inner_nodes, _ = wall(lambda _: 0.15)
    outer_nodes, outer_lines = wall(lambda _: 0.13)
    distances = tm.point_to_polyline_distances(inner_nodes[20:-20], outer_nodes, outer_lines)
    assert np.allclose(distances, 0.02, atol=1e-12)


def test_layer_metrics_measure_local_thickness_conformality_and_aperture():
    inner, inner_lines, outer, outer_lines = quarter_via_layer()
    metrics = tm.layer_thickness_metrics_2d(
        inner,
        inner_lines,
        outer,
        outer_lines,
        surface_y=0.0,
        floor_y=-1.0,
        via_radius=0.15,
    )
    for key in (
        "field_thickness",
        "upper_wall_thickness",
        "middle_wall_thickness",
        "lower_wall_thickness",
        "floor_thickness",
        "minimum_local_thickness",
    ):
        assert math.isclose(metrics[key], 0.02, abs_tol=1e-12), key
    assert math.isclose(metrics["floor_to_field_conformality"], 1.0, abs_tol=1e-12)
    assert math.isclose(metrics["minimum_remaining_aperture"], 0.26, abs_tol=1e-12)
    assert metrics["layer_continuous"]
    assert metrics["aperture_open"]


def test_layer_metrics_detect_nonuniformity_and_pinhole():
    inner, lines, _, _ = quarter_via_layer()
    outer = np.asarray([
        [0.0, -0.98],
        [0.15, -0.98],
        [0.15, -0.70],
        [0.13, 0.02],
        [0.5, 0.02],
    ])
    outer_lines = np.asarray([[0, 1], [1, 2], [2, 3], [3, 4]])
    metrics = tm.layer_thickness_metrics_2d(
        inner,
        lines,
        outer,
        outer_lines,
        surface_y=0.0,
        floor_y=-1.0,
        via_radius=0.15,
    )
    assert metrics["lower_wall_thickness"] < metrics["upper_wall_thickness"]
    assert metrics["minimum_local_thickness"] <= 1e-10
    assert metrics["pinhole_detected"]


def test_line_components_distinguish_closed_and_open_contours():
    outer_nodes, outer_lines = closed_square(-1, -1, 1, 1)
    inner_nodes, inner_lines = closed_square(-0.2, -0.2, 0.2, 0.2, offset=4)
    nodes = np.vstack((outer_nodes, inner_nodes, [[2.0, 0.0], [3.0, 0.0]]))
    lines = np.vstack((outer_lines, inner_lines, [[8, 9]]))
    summaries = tm.component_summaries(nodes, lines)
    assert len(summaries) == 3
    assert sorted(summary["closed"] for summary in summaries) == [False, True, True]


def test_material_region_connectivity_uses_solid_not_two_surface_contours():
    annulus = material_box(-0.16, -1.25, 0.16, 0.02)
    combine_material(
        annulus,
        material_box(-0.13, -1.22, 0.13, -0.02),
        ls.BooleanOperationEnum.RELATIVE_COMPLEMENT,
    )
    surface = ls.Mesh()
    ls.ToSurfaceMesh(annulus, surface).apply()
    assert len(tm.component_summaries(surface.getNodes(), surface.getLines())) == 2

    regular_grid = ls.Mesh()
    ls.ToMesh(annulus, regular_grid).apply()
    point_data_count = regular_grid.getCellData().getScalarDataSize()
    connectivity = material_connectivity(annulus)
    regular_grid_after = ls.Mesh()
    ls.ToMesh(annulus, regular_grid_after).apply()
    assert (
        regular_grid_after.getCellData().getScalarDataSize()
        == point_data_count
    )
    assert connectivity["resolved"]
    assert connectivity["negative_component_count"] == 1
    assert connectivity["floor_to_both_mouths_connected"]
    assert len(connectivity["spanning_component_ids"]) == 1


def test_material_region_connectivity_detects_full_and_one_wall_cuts():
    full_cut = u_shaped_material()
    combine_material(
        full_cut,
        material_box(-0.20, -0.64, 0.20, -0.59),
        ls.BooleanOperationEnum.RELATIVE_COMPLEMENT,
    )
    full = material_connectivity(full_cut)
    assert full["resolved"]
    assert full["negative_component_count"] == 3
    assert not full["floor_to_both_mouths_connected"]

    right_cut = u_shaped_material()
    combine_material(
        right_cut,
        material_box(0.12, -0.64, 0.18, -0.59),
        ls.BooleanOperationEnum.RELATIVE_COMPLEMENT,
    )
    right = material_connectivity(right_cut)
    assert right["resolved"]
    assert right["negative_component_count"] == 2
    assert not right["floor_to_both_mouths_connected"]
    # One component still spans the old floor-to-field y extent.  A y-span
    # test alone therefore misses the severed right wall.
    assert any(
        summary["bounds_min"][1] <= -1.235
        and summary["bounds_max"][1] >= 0.0
        for summary in right["component_summaries"]
    )


def test_material_region_connectivity_marks_subresolution_and_fragments():
    subresolution = material_connectivity(
        u_shaped_material(), local_thickness=0.010
    )
    assert not subresolution["resolved"]
    assert "local_thickness_at_or_below_resolution_limit" in (
        subresolution["unresolved_reasons"]
    )
    assert subresolution["spanning_component_ids"]
    assert not subresolution["floor_to_both_mouths_connected"]

    fragment = u_shaped_material()
    combine_material(
        fragment,
        material_box(0.30, -0.80, 0.35, -0.75),
        ls.BooleanOperationEnum.UNION,
    )
    fragmented = material_connectivity(fragment)
    assert fragmented["floor_to_both_mouths_connected"]
    assert fragmented["negative_component_count"] == 2
    assert fragmented["detached_fragment_count"] == 1
    assert len(fragmented["detached_fragment_ids"]) == 1


def test_fill_topology_distinguishes_complete_open_and_sealed_fill():
    flat_nodes = np.asarray([[-1.0, 0.10], [1.0, 0.10]])
    flat_lines = np.asarray([[0, 1]])
    complete = tm.fill_topology_metrics_2d(
        flat_nodes,
        flat_lines,
        field_y=0.0,
        floor_y=-1.0,
        via_x_bounds=(-0.15, 0.15),
        field_sample_xs=(-0.5, 0.5),
    )
    assert complete["void_free"]
    assert complete["positive_overburden"]
    assert math.isclose(complete["center_fill_height"], 1.10, abs_tol=1e-12)

    open_nodes = np.asarray([
        [-1.0, 0.10],
        [-0.15, 0.10],
        [-0.15, -1.0],
        [0.15, -1.0],
        [0.15, 0.10],
        [1.0, 0.10],
    ])
    open_lines = np.column_stack((np.arange(5), np.arange(1, 6)))
    open_fill = tm.fill_topology_metrics_2d(
        open_nodes,
        open_lines,
        field_y=0.0,
        floor_y=-1.0,
        via_x_bounds=(-0.15, 0.15),
        field_sample_xs=(-0.5, 0.5),
        initial_cavity_area=0.3,
        grid_delta=0.01,
    )
    assert open_fill["open_void"]
    assert not open_fill["void_free"]
    assert not open_fill["mouth_pinched_off"]
    assert math.isclose(open_fill["open_void_area"], 0.3, abs_tol=0.002)
    assert math.isclose(open_fill["fill_fraction"], 0.0, abs_tol=0.01)
    assert math.isclose(open_fill["mouth_aperture"], 0.3, abs_tol=1e-12)
    assert open_fill["mouth_open"]

    shallow_open_nodes = open_nodes.copy()
    shallow_open_nodes[2:4, 1] = -0.01
    shallow_open = tm.fill_topology_metrics_2d(
        shallow_open_nodes,
        open_lines,
        field_y=0.0,
        floor_y=-1.0,
        via_x_bounds=(-0.15, 0.15),
        field_sample_xs=(-0.5, 0.5),
        mouth_sample_y=-0.02,
        grid_delta=0.01,
    )
    assert shallow_open["open_void"]
    assert shallow_open["mouth_open"]
    assert not shallow_open["pinch_off_failure"]
    assert shallow_open["mouth_sample_y"] > -0.01

    asymmetric_open_nodes = np.asarray([
        [-0.5, 0.10],
        [0.05, 0.10],
        [0.05, -0.50],
        [0.14, -0.50],
        [0.14, 0.10],
        [0.5, 0.10],
    ])
    asymmetric_open_lines = np.column_stack((np.arange(5), np.arange(1, 6)))
    asymmetric_open = tm.fill_topology_metrics_2d(
        asymmetric_open_nodes,
        asymmetric_open_lines,
        field_y=0.0,
        floor_y=-1.0,
        via_x_bounds=(-0.15, 0.15),
        field_sample_xs=(-0.5, 0.5),
        center_x=0.0,
        grid_delta=0.01,
    )
    assert asymmetric_open["open_void"]
    assert asymmetric_open["topology_valid"]
    assert not asymmetric_open["mouth_open"]
    assert not asymmetric_open["pinch_off_failure"]

    void_nodes, void_lines = closed_square(-0.05, -0.8, 0.05, -0.2, offset=2)
    sealed_nodes = np.vstack((flat_nodes, void_nodes))
    sealed_lines = np.vstack((flat_lines, void_lines))
    sealed = tm.fill_topology_metrics_2d(
        sealed_nodes,
        sealed_lines,
        field_y=0.0,
        floor_y=-1.0,
        via_x_bounds=(-0.15, 0.15),
        field_sample_xs=(-0.5, 0.5),
    )
    assert sealed["closed_void_count"] == 1
    assert math.isclose(sealed["closed_void_area"], 0.06, abs_tol=1e-12)
    assert math.isclose(sealed["maximum_void_height"], 0.6, abs_tol=1e-12)
    assert sealed["mouth_pinched_off"]
    assert sealed["pinch_off_failure"]
    assert not sealed["void_free"]

    seam_nodes = np.vstack((flat_nodes, [[-0.04, -0.7], [0.04, -0.3]]))
    seam_lines = np.vstack((flat_lines, [[2, 3]]))
    seam = tm.fill_topology_metrics_2d(
        seam_nodes,
        seam_lines,
        field_y=0.0,
        floor_y=-1.0,
        via_x_bounds=(-0.15, 0.15),
        field_sample_xs=(-0.5, 0.5),
    )
    assert seam["open_internal_component_count"] == 1
    assert seam["seam_or_mesh_defect"]
    assert not seam["topology_valid"]
    assert not seam["void_free"]

    clipped_void_nodes = np.vstack((flat_nodes, [
        [0.0, -0.8],
        [0.05, -0.8],
        [0.05, -0.2],
        [0.0, -0.2],
    ]))
    clipped_void_lines = np.vstack((flat_lines, [[2, 3], [3, 4], [4, 5]]))
    clipped_void = tm.fill_topology_metrics_2d(
        clipped_void_nodes,
        clipped_void_lines,
        field_y=0.0,
        floor_y=-1.0,
        via_x_bounds=(0.0, 0.15),
        field_sample_xs=(0.4, 0.5),
        center_x=0.01,
    )
    assert clipped_void["open_internal_component_count"] == 1
    assert not clipped_void["topology_valid"]
    assert not clipped_void["void_free"]

    shoulder_recess_nodes = np.asarray([
        [-0.5, 0.20],
        [-0.15, 0.20],
        [-0.14, 0.01],
        [-0.05, 0.20],
        [0.0, 0.20],
        [0.05, 0.20],
        [0.14, 0.01],
        [0.15, 0.20],
        [0.5, 0.20],
    ])
    shoulder_recess_lines = np.column_stack((np.arange(8), np.arange(1, 9)))
    shoulder_recess = tm.fill_topology_metrics_2d(
        shoulder_recess_nodes,
        shoulder_recess_lines,
        field_y=0.0,
        floor_y=-1.0,
        via_x_bounds=(-0.15, 0.15),
        field_sample_xs=(-0.5, -0.4, 0.4, 0.5),
    )
    assert shoulder_recess["void_free"]
    assert shoulder_recess["sampled_overburden_min"] >= 0.15
    assert shoulder_recess["overburden_min"] < 0.02
    assert not shoulder_recess["overburden_min"] >= 0.15


def test_cmp_metrics_distinguish_endpoint_dish_residual_and_stop_loss():
    stop_nodes = np.asarray([[-1.0, 0.0], [1.0, 0.0]])
    lines = np.asarray([[0, 1]])
    plug_nodes = np.asarray([[-0.15, 0.0], [0.15, 0.0]])
    ideal = tm.cmp_profile_metrics_2d(
        post_cu_nodes=plug_nodes,
        post_cu_lines=lines,
        post_stop_nodes=stop_nodes,
        post_stop_lines=lines,
        field_sample_xs=(-0.5, 0.5),
        center_x=0.0,
        target_field_y=0.0,
        pre_stop_field_y=0.0,
        stop_initial_thickness=0.05,
        pre_cu_center_y=0.1,
    )
    assert ideal["valid"]
    assert ideal["endpoint_reached"]
    assert ideal["stop_layer_survives"]
    assert math.isclose(ideal["dish"], 0.0, abs_tol=1e-12)

    recessed_plug = plug_nodes.copy()
    recessed_plug[:, 1] = -0.03
    dished = tm.cmp_profile_metrics_2d(
        post_cu_nodes=recessed_plug,
        post_cu_lines=lines,
        post_stop_nodes=stop_nodes,
        post_stop_lines=lines,
        field_sample_xs=(-0.5, 0.5),
        center_x=0.0,
        target_field_y=0.0,
        pre_stop_field_y=0.0,
        stop_initial_thickness=0.05,
    )
    assert dished["endpoint_reached"]
    assert math.isclose(dished["dish"], 0.03, abs_tol=1e-12)

    residual_cu = np.asarray([[-1.0, 0.02], [1.0, 0.02]])
    uncleared = tm.cmp_profile_metrics_2d(
        post_cu_nodes=residual_cu,
        post_cu_lines=lines,
        post_stop_nodes=stop_nodes,
        post_stop_lines=lines,
        field_sample_xs=(-0.5, 0.5),
        center_x=0.0,
        target_field_y=0.0,
        pre_stop_field_y=0.0,
        stop_initial_thickness=0.05,
    )
    assert not uncleared["copper_endpoint_reached"]
    assert math.isclose(uncleared["residual_field_cu_max"], 0.02, abs_tol=1e-12)

    eroded_stop = stop_nodes.copy()
    eroded_stop[:, 1] = -0.02
    eroded = tm.cmp_profile_metrics_2d(
        post_cu_nodes=recessed_plug,
        post_cu_lines=lines,
        post_stop_nodes=eroded_stop,
        post_stop_lines=lines,
        field_sample_xs=(-0.5, 0.5),
        center_x=0.0,
        target_field_y=0.0,
        pre_stop_field_y=0.0,
        stop_initial_thickness=0.01,
    )
    assert eroded["stop_layer_consumed"]
    assert not eroded["valid"]


if __name__ == "__main__":
    test_vertical_wall_cd_profile()
    test_pattern_metrics_measure_cd_height_and_taper()
    test_taper_and_bow_are_distinct()
    test_parallel_layer_distance()
    test_layer_metrics_measure_local_thickness_conformality_and_aperture()
    test_layer_metrics_detect_nonuniformity_and_pinhole()
    test_line_components_distinguish_closed_and_open_contours()
    test_material_region_connectivity_uses_solid_not_two_surface_contours()
    test_material_region_connectivity_detects_full_and_one_wall_cuts()
    test_material_region_connectivity_marks_subresolution_and_fragments()
    test_fill_topology_distinguishes_complete_open_and_sealed_fill()
    test_cmp_metrics_distinguish_endpoint_dish_residual_and_stop_loss()
    print("traveler metric checks: PASS")

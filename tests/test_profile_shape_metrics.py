"""Checks for the tutorial-only via shape comparison."""

import math

import numpy as np

import profile_shape_metrics as psm


def full_via_with_floor(floor_fn, radius=0.15, count=61):
    floor_xs = np.linspace(-radius, radius, count)
    floor = np.column_stack((floor_xs, [floor_fn(x) for x in floor_xs]))
    nodes = np.vstack(([-radius, 0.0], floor, [radius, 0.0]))
    lines = np.column_stack((np.arange(len(nodes) - 1), np.arange(1, len(nodes))))
    return nodes, lines


def measure(nodes, lines, **overrides):
    options = {
        "surface_y": 0.0,
        "target_cd": 0.30,
        "target_depth": 1.0,
        "domain_x_bounds": (-0.5, 0.5),
        "grid_delta": 0.01,
    }
    options.update(overrides)
    return psm.measure_target_via_profile_2d(nodes, lines, **options)


def test_floor_shape_and_target_error():
    flat_nodes, flat_lines = full_via_with_floor(lambda _x: -1.0)
    flat = measure(flat_nodes, flat_lines)
    assert flat["state"] == "complete"
    assert flat["metrics"]["floor_flatness_pv"] < 1e-12
    assert flat["metrics"]["floor_sample_count"] == 15
    assert flat["metrics"]["floor_resolution_status"] == "flat_within_resolution"
    assert flat["metrics"]["profile_shape_rmse"] < 1e-12
    assert flat["metrics"]["profile_max_deviation"] < 1e-12
    assert flat["metrics"]["profile_symmetry_rms"] < 1e-12

    bowl_nodes, bowl_lines = full_via_with_floor(
        lambda x: -1.0 + 0.06 * (x / 0.07) ** 2
    )
    bowl = measure(bowl_nodes, bowl_lines)
    assert bowl["metrics"]["floor_flatness_pv"] > 0.04
    assert bowl["metrics"]["floor_horizontal_rms"] > 0.01
    assert bowl["metrics"]["floor_center_relief"] > 0.04
    assert bowl["metrics"]["floor_resolution_status"] == "resolved_nonflatness"
    assert bowl["metrics"]["profile_shape_rmse"] > flat["metrics"]["profile_shape_rmse"]

    tilt_nodes, tilt_lines = full_via_with_floor(lambda x: -1.0 + 0.5 * x)
    tilt = measure(tilt_nodes, tilt_lines)
    assert tilt["metrics"]["floor_flatness_pv"] > 0.05
    assert abs(tilt["metrics"]["floor_center_relief"]) < 1e-12


def test_floor_translation_and_unavailable_states():
    nodes, lines = full_via_with_floor(lambda x: -1.0 + 0.04 * (x / 0.07) ** 2)
    baseline = measure(nodes, lines)
    shifted_nodes = nodes.copy()
    shifted_nodes[:, 1] -= 0.25
    shifted = measure(shifted_nodes, lines, surface_y=-0.25)
    for name in ("floor_flatness_pv", "floor_horizontal_rms", "floor_center_relief"):
        assert math.isclose(
            baseline["metrics"][name], shifted["metrics"][name], abs_tol=1e-12
        )

    missing_lines = lines[~np.isin(lines[:, 0], (16, 17))]
    missing = measure(nodes, missing_lines)
    assert missing["state"] == "valid_categorical_modeled_state"
    assert missing["reason_codes"] == ["floor_intersection_missing"]
    partial = measure(nodes, missing_lines, allow_partial_floor=True)
    assert partial["state"] == "partial"
    assert partial["metrics"]["profile_shape_rmse"] is None
    assert partial["metrics"]["profile_wall_rmse"] is not None

    extra_index = len(nodes)
    multiple_nodes = np.vstack((nodes, [-0.02, -0.80], [0.02, -0.80]))
    multiple_lines = np.vstack((lines, [extra_index, extra_index + 1]))
    multiple = measure(multiple_nodes, multiple_lines)
    assert multiple["reason_codes"] == ["floor_intersection_multiple"]


if __name__ == "__main__":
    test_floor_shape_and_target_error()
    test_floor_translation_and_unavailable_states()
    print("profile shape metric checks: PASS")

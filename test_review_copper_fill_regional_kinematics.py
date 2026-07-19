from pathlib import Path
import tempfile

import numpy as np

import review_copper_fill_access_surface as access
import review_copper_fill_regional_kinematics as review
import test_review_copper_fill_boundary_refinement as fixtures


def reference():
    return {
        "field_y": 1.0,
        "floor_y": 0.0,
        "via_x_bounds": [-0.5, 0.5],
        "initial_topology": {
            "open_void_depth": 1.0,
            "remaining_void_area": 0.5,
            "mouth_aperture": 1.0,
        },
    }


def regional_arrays(include_lower=True):
    points = [
        [0.0, 0.02, 0.0],
        [0.4, 0.50, 0.0],
        [0.4, 0.80, 0.0],
        [0.4, 0.98, 0.0],
    ]
    if include_lower:
        points.insert(1, [0.4, 0.20, 0.0])
    coordinates = np.asarray(points)
    values = np.arange(1.0, len(points) + 1.0)
    return coordinates, values, values + 10.0, values + 20.0


def test_region_means_preserve_floor_over_lower_direction_and_empty_region():
    arrays = regional_arrays()
    result = review.region_statistics(*arrays, reference())

    assert set(result) == set(review.REGION_NAMES)
    assert all(region["point_count"] == 1 for region in result.values())
    assert result["floor"]["normal_velocity_mean"] == 21.0
    assert result["lower_wall"]["normal_velocity_mean"] == 22.0
    assert review.floor_lower_ratios(result)["normal_velocity"] == 21.0 / 22.0

    empty = review.region_statistics(*regional_arrays(False), reference())
    assert empty["lower_wall"]["point_count"] == 0
    assert empty["lower_wall"]["normal_velocity_mean"] is None
    assert review.floor_lower_ratios(empty)["normal_velocity"] is None


def test_dynamic_width_uses_separate_sides_and_conservative_minimum():
    nodes = np.asarray([
        [-0.5, 1.0, 0.0],
        [-0.4, 1.0, 0.0],
        [-0.4, 0.0, 0.0],
        [0.3, 0.0, 0.0],
        [0.3, 1.0, 0.0],
        [0.5, 1.0, 0.0],
    ])
    lines = np.asarray([[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]])
    result = review.dynamic_width_threshold(nodes, lines, reference(), 0.01)

    assert result["measurable"]
    assert np.isclose(result["remaining_axial_distance"], 1.0)
    assert np.isclose(result["left_half_width"], 0.4)
    assert np.isclose(result["right_half_width"], 0.3)
    assert np.isclose(result["conservative_half_width"], 0.3)
    assert np.isclose(result["conservative_threshold"], 1.0 / 0.3)
    assert not result["at_or_below_detection_limit"]


def test_common_time_extracts_progress_and_rates():
    row = {
        "reference": reference(),
        "trajectory": [{
            "checkpoint": 30,
            "elapsed": 0.75,
            "topology": {
                "topology_valid": True,
                "open_void_depth": 0.9,
                "remaining_void_area": 0.4,
                "mouth_aperture": 0.8,
                "mouth_open": True,
                "fill_fraction": 0.2,
            },
            "topology_transition": {"valid": True},
            "model_diagnostics": {"valid": True},
        }],
    }
    result, errors = review.common_time_metrics(row)

    assert errors == []
    assert np.isclose(result["depth_advance"], 0.1)
    assert np.isclose(result["area_reduction"], 0.1)
    assert np.isclose(result["mouth_loss"], 0.2)
    assert np.isclose(result["depth_advance_rate"], 0.1 / 0.75)
    assert np.isclose(result["fill_fraction_rate"], 0.2 / 0.75)


def test_missing_snapshot_is_an_explicit_error(tmp_path):
    result, errors = review.snapshot_profile(
        tmp_path / "missing.npz",
        {"checkpoint": 1, "elapsed": 0.025},
        reference(),
        0.01,
    )
    assert result is None
    assert errors and "missing" in errors[0]


def test_partial_matrix_and_current_error_block_regional_conclusion(tmp_path):
    manifest = fixtures.manifest()
    cases = access.expand_cases(manifest, fixtures.FINGERPRINT)
    partial = [fixtures.result_row(case) for case in cases[:-1]]
    summary = review.build_summary(
        manifest, partial, [], False, fixtures.FINGERPRINT, tmp_path
    )
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["decision"]["classification"] == "insufficient_audited_evidence"

    rows = fixtures.all_current_rows(manifest)
    error = {
        **cases[0],
        "ok": False,
        "production_doe_eligible": False,
        "error": "current worker error",
    }
    summary = review.build_summary(
        manifest, [error, *rows], [], False, fixtures.FINGERPRINT, tmp_path
    )
    assert summary["status"] == "incomplete_or_invalid"
    assert len(summary["current_fingerprint_error_attempt_rows"]) == 1


def test_no_go_requires_the_observed_ratio_direction_and_large_shortfall():
    rejected = review.classify_coefficient_screen([0.8, 1.0], 10.0, 0.2, 0.01)
    assert rejected["classification"] == "coefficient_screen_rejected"
    assert rejected["all_initial_floor_lower_velocity_ratios_at_most_one"]
    assert rejected["va_to_vs_ceiling"] == 20.0
    assert rejected["ordering_constrained_velocity_ratio_ceiling"] == 1.0
    assert rejected[
        "ordering_constrained_ceiling_below_nominal_threshold"
    ]

    favorable = review.classify_coefficient_screen([1.01, 1.2], 10.0, 0.2, 0.01)
    assert favorable["classification"] == "coefficient_screen_not_rejected"

    not_far_below = review.classify_coefficient_screen([1.0], 1.5, 0.2, 0.01)
    assert not_far_below["classification"] == "coefficient_screen_not_rejected"


if __name__ == "__main__":
    test_region_means_preserve_floor_over_lower_direction_and_empty_region()
    test_dynamic_width_uses_separate_sides_and_conservative_minimum()
    test_common_time_extracts_progress_and_rates()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        test_missing_snapshot_is_an_explicit_error(path)
        test_partial_matrix_and_current_error_block_regional_conclusion(path)
    test_no_go_requires_the_observed_ratio_direction_and_large_shortfall()

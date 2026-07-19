import math

import numpy as np

import tsv_process as tp


def test_etch_target_score_names_depth_and_width():
    ok, score = tp.target_score("etch", {
        "depth": -1.25,
        "bulge": 0.02,
        "width_error": 0.04,
    })
    assert ok
    assert math.isfinite(score)


def test_thickness_gates_are_hard_targets():
    ok, _ = tp.target_score("liner", {
        "thickness": 0.018,
        "coverage": 1.0,
    })
    assert not ok


def test_fill_requires_topology_and_overburden():
    ok, score = tp.target_score("fill", {
        "void_free": True,
        "closed_void_count": 0,
        "remaining_void_area": 0.0,
        "overburden_min": 0.18,
    })
    assert ok
    assert score == 0.0

    ok, score = tp.target_score("fill", {
        "void_free": False,
        "closed_void_count": 1,
        "remaining_void_area": 0.02,
        "overburden_min": 0.18,
    })
    assert not ok
    assert score == tp.TOPOLOGY_FAILURE_PENALTY


def test_fill_centerline_gap_shrinks_as_fill_rises():
    empty = np.array([[0.0, -1.25], [0.4, 0.30]])
    partial = np.array([[0.0, -0.50], [0.4, 0.30]])
    flat = np.array([[0.0, 0.30], [0.4, 0.30]])
    assert tp.fill_centerline_gap(empty) == 1.55
    assert tp.fill_centerline_gap(partial) == 0.80
    assert tp.fill_centerline_gap(flat) == 0.0


def test_legacy_fill_tip_gap_has_opposite_monotonic_direction():
    floor = -1.25
    low = np.array([[0.0, floor]])
    high = np.array([[0.0, -0.50]])
    assert tp.fill_tip_gap(low, floor) == 0.0
    assert tp.fill_tip_gap(high, floor) == 0.75


if __name__ == "__main__":
    test_etch_target_score_names_depth_and_width()
    test_thickness_gates_are_hard_targets()
    test_fill_requires_topology_and_overburden()
    test_fill_centerline_gap_shrinks_as_fill_rises()
    test_legacy_fill_tip_gap_has_opposite_monotonic_direction()
    print("target spec checks: PASS")

import math

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


def test_fill_gap_zero_is_the_target():
    ok, score = tp.target_score("fill", {
        "thickness": 0.18,
        "tip_gap": 0.12,
    })
    assert not ok
    assert score == 0.12


if __name__ == "__main__":
    test_etch_target_score_names_depth_and_width()
    test_thickness_gates_are_hard_targets()
    test_fill_gap_zero_is_the_target()
    print("target spec checks: PASS")

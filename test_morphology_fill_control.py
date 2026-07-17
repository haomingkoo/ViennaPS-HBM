"""Focused checks for the morphology-only fill controls."""

import morphology_fill_control as control


def test_morphology_only_positive_control_reaches_each_topology_state():
    result = control.run_morphology_only_positive_control()
    assert result["scope"] == control.MORPHOLOGY_ONLY_SCOPE

    incomplete = result["stages"]["incomplete_fill"]
    assert incomplete["open_void"]
    assert incomplete["closed_void_count"] == 0
    assert not incomplete["void_free"]
    assert not incomplete["positive_overburden"]
    assert 0.0 < incomplete["fill_fraction"] < 1.0
    assert incomplete["mouth_open"]

    closed = result["stages"]["void_free_closure"]
    assert not closed["open_void"]
    assert closed["closed_void_count"] == 0
    assert closed["void_free"]
    assert not closed["positive_overburden"]
    assert closed["fill_fraction"] == 1.0

    overburden = result["stages"]["positive_overburden"]
    assert not overburden["open_void"]
    assert overburden["closed_void_count"] == 0
    assert overburden["void_free"]
    assert overburden["positive_overburden"]
    assert overburden["overburden_min"] > 0.07


def test_morphology_only_failed_control_preserves_pinched_off_void():
    result = control.run_morphology_only_failed_fill_control()
    assert result["scope"] == control.MORPHOLOGY_ONLY_SCOPE
    metrics = result["metrics"]
    assert not metrics["open_void"]
    assert metrics["closed_void_count"] == 1
    assert metrics["mouth_pinched_off"]
    assert metrics["pinch_off_failure"]
    assert not metrics["mouth_open"]
    assert not metrics["void_free"]
    assert metrics["closed_void_area"] > 0.1
    assert metrics["maximum_void_height"] > 0.8


if __name__ == "__main__":
    test_morphology_only_positive_control_reaches_each_topology_state()
    test_morphology_only_failed_control_preserves_pinched_off_void()
    print("morphology-only fill controls: PASS")

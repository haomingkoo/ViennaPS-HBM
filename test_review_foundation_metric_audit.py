"""Pattern and Bosch review gates include the mask, not only silicon CD."""

import copy

import review_foundation_metric_audit as review


BASE_ROW = {
    "grid_delta": 0.005,
    "target": {
        "opening_cd": 0.30,
        "mask_height": 0.30,
        "max_width_error": 0.06,
        "etch_depth": 1.25,
        "depth_tolerance": 0.10,
        "max_wall_bulge": 0.03,
    },
    "pattern": {
        "opening_cd_bottom": 0.30,
        "opening_cd_middle": 0.30,
        "opening_cd_top": 0.30,
        "mask_height": 0.30,
        "opening_valid": True,
    },
    "etch": {
        "depth": 1.25,
        "max_cd_error": 0.01,
        "max_bow": 0.01,
    },
    "mask_remaining_height": 0.20,
    "post_etch_mask": {"opening_valid": True},
}


def test_complete_row_passes_every_foundation_gate():
    assert all(review.row_passes(BASE_ROW).values())


def test_closed_initial_opening_fails_pattern_gate():
    row = copy.deepcopy(BASE_ROW)
    row["pattern"]["opening_valid"] = False
    passes = review.row_passes(row)
    assert passes["pattern_width"]
    assert not passes["pattern_opening"]


def test_consumed_or_subresolution_mask_fails_etch_gate():
    consumed = copy.deepcopy(BASE_ROW)
    consumed["mask_remaining_height"] = 0.0
    consumed["post_etch_mask"] = None
    assert not review.row_passes(consumed)["etch_mask_resolved"]

    unresolved = copy.deepcopy(BASE_ROW)
    unresolved["mask_remaining_height"] = 0.01
    assert not review.row_passes(unresolved)["etch_mask_resolved"]


if __name__ == "__main__":
    test_complete_row_passes_every_foundation_gate()
    test_closed_initial_opening_fails_pattern_gate()
    test_consumed_or_subresolution_mask_fails_etch_gate()
    print("foundation pattern/Bosch review checks: PASS")

"""Synthetic guards for broad pattern/Bosch screen review and ranking."""

import copy

import pattern_bosch_screen_runner as runner
import review_pattern_bosch_screen as review
import test_pattern_bosch_screen_runner as runner_fixture


MANIFEST = runner_fixture.manifest()


def case_with_review():
    case = runner.expand_cases(MANIFEST)[0]
    case["review"] = MANIFEST["design"]["review"]
    return case


def measured(depth=1.25, cd=0.02, bow=0.01, mask=0.3):
    return {
        "etch": {
            "depth": depth,
            "max_cd_error": cd,
            "max_bow": bow,
            "scallop_rms": 0.001,
        },
        "mask_remaining_height": mask,
        "post_etch_mask": {"opening_valid": True},
    }


def initial(height=0.3):
    return {
        "opening_cd_bottom": 0.3,
        "mask_height": height,
        "opening_valid": True,
    }


def gates(all_pass=True):
    result = {name: all_pass for name in review.PRIMITIVE_GATES}
    result["pattern_pass"] = all_pass
    result["etch_pass"] = all_pass
    return result


def reviewed_row(recipe_id, seed, *, passed, score_shift=0.0, valid=True, boundary=False):
    current_gates = gates(passed)
    miss = {
        "invalid": not valid,
        "primitive_gates": {name: passed for name in review.PRIMITIVE_GATES},
        "failed_primitive_gates": [] if passed else ["etch_bow"],
        "primitive_gate_failure_count": 0 if passed else 1,
        "continuous_miss_terms": {},
        "score": score_shift if passed else 1000.0 + score_shift,
    }
    coordinates = {factor["name"]: 0.5 for factor in MANIFEST["design"]["factors"]}
    if boundary:
        coordinates["etch_time"] = 1.0
    return {
        "case_id": f"{recipe_id}-{seed}",
        "recipe_id": recipe_id,
        "rng_seed": seed,
        "valid": valid,
        "errors": [] if valid else ["invalid"],
        "selection_eligible": True,
        "selected_cycle": 12,
        "initial_pattern": initial(),
        "selected_cycle_metrics": measured(),
        "gates": current_gates,
        "hard_gate_pass": bool(valid and passed),
        "miss": miss,
        "normalized_coordinates": coordinates,
        "recipe": {factor["name"]: MANIFEST["design"]["recipes"][0]["recipe"][factor["name"]] for factor in MANIFEST["design"]["factors"]},
        "design_class": "latin_hypercube",
        "anchor_reasons": [],
    }


def test_penalties_and_selection_eligibility_dominate_continuous_miss():
    case = case_with_review()
    passing_gates = gates(True)
    score = review.miss_score(initial(), measured(), passing_gates, case)
    assert score["score"] == 0.0

    ineligible = copy.deepcopy(passing_gates)
    ineligible["selection_eligible"] = False
    score = review.miss_score(initial(), measured(), ineligible, case)
    assert score["score"] >= 1000.0

    invalid = review.miss_score(
        initial(), measured(), passing_gates, case, ["nonfinite"]
    )
    assert invalid["score"] >= 1000000.0


def test_four_seed_aggregation_prefers_valid_feasible_and_warns_boundary():
    manifest = MANIFEST
    seeds = manifest["design"]["rng_base_seeds"]
    rows = []
    rows += [reviewed_row("feasible", seed, passed=True, score_shift=index * 0.1, boundary=True) for index, seed in enumerate(seeds)]
    rows += [reviewed_row("miss", seed, passed=index < 3, score_shift=0.01) for index, seed in enumerate(seeds)]
    rows += [reviewed_row("invalid", seed, passed=True, valid=index != 0) for index, seed in enumerate(seeds)]
    aggregates = review.aggregate_recipes(rows, manifest)
    decision = review.decision_from_review(rows, aggregates, len(rows))
    assert decision["best_feasible"]["recipe_id"] == "feasible"
    assert decision["best_observed_miss"]["recipe_id"] == "miss"
    assert decision["best_feasible"]["boundary_warnings"]
    assert not decision["recipe_authorized"]
    assert not decision["full_traveler_authorized"]


def test_incomplete_matrix_never_authorizes_refinement():
    manifest = MANIFEST
    seeds = manifest["design"]["rng_base_seeds"]
    rows = [reviewed_row("partial", seed, passed=True) for seed in seeds]
    aggregates = review.aggregate_recipes(rows, manifest)
    decision = review.decision_from_review(rows, aggregates, 640)
    assert not decision["complete_valid_matrix"]
    assert not decision["targeted_pattern_bosch_refinement_authorized"]


def test_adverse_tail_direction_is_explicit():
    high_bad = review.response_summary([1.0, 2.0, 3.0, 4.0])
    assert high_bad["higher_is_worse"]
    assert high_bad["worst"] == 4.0
    low_bad = review.response_summary(
        [0.1, 0.2, 0.3, 0.4], higher_is_worse=False
    )
    assert not low_bad["higher_is_worse"]
    assert low_bad["worst"] == 0.1
    assert low_bad["adverse_p90"] < low_bad["mean"]


if __name__ == "__main__":
    test_penalties_and_selection_eligibility_dominate_continuous_miss()
    test_four_seed_aggregation_prefers_valid_feasible_and_warns_boundary()
    test_incomplete_matrix_never_authorizes_refinement()
    test_adverse_tail_direction_is_explicit()
    print("pattern/Bosch broad-screen review checks: PASS")

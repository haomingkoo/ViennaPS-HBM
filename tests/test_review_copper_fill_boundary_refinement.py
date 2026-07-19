import copy
import tempfile
from pathlib import Path

import review_copper_fill_access_surface as access
import review_copper_fill_boundary_refinement as review


FINGERPRINT = {
    "runner_sha256": "runner",
    "traveler_metrics_sha256": "metrics",
    "tsv_process_sha256": "process",
    "viennaps_binary_sha256": "binary",
}


def manifest():
    data = {
        "manifest_version": 6,
        "campaign": "foundation-copper-fill-low-sticking-boundary-refinement-v2",
        "geometry": {"radius": 0.15},
        "layers": {"liner": 0.03, "barrier": 0.01, "seed": 0.01},
        "model": {
            "suppressor_sticking_probability": 0.05,
            "adsorption_strength": 5.0,
            "deactivation_rate": 0.25,
            "active_deposition_rate": 0.2,
        },
        "numerics": {
            "grid_delta": 0.01,
            "checkpoint_interval": 0.025,
            "max_duration": 8.0,
            "require_disjoint_replicate_rng_streams": True,
        },
        "target": {"min_overburden": 0.15},
        "provenance": {"viennaps_binary_sha256": "binary"},
        "designs": [],
    }
    for coverage_lambda in review.LAMBDA_LEVELS:
        for sticking in review.STICKING_LEVELS:
            data["designs"].append({
                "name": review.expected_design_name(coverage_lambda, sticking),
                "model": {
                    "suppressor_sticking_probability": sticking,
                    "adsorption_strength": coverage_lambda * 0.25 / sticking,
                },
                "rng_seeds": list(review.SEEDS),
            })
    return data


def checkpoint(index, depth, *, elapsed, hard=None, target=False):
    advance = 1.25 - depth
    topology = {
        "topology_valid": hard != "invalid_topology",
        "open_void_depth": depth,
        "remaining_void_area": max(0.0, 0.25 - 0.12 * advance),
        "mouth_aperture": 0.2 - 0.01 * advance,
        "mouth_open": True,
        "fill_fraction": min(1.0, advance / 1.25),
        "overburden_min": depth - 1.25,
        "overburden_nonuniformity": 0.02,
        "pinch_off_failure": hard == "pinch_off_or_closed_void",
        "degenerate_closed_component_count": (
            1 if hard == "degenerate_closed_fragment" else 0
        ),
    }
    transition_failure = hard == "unresolved_narrow_tail_merger"
    return {
        "checkpoint": index,
        "elapsed": elapsed,
        "topology": topology,
        "topology_transition": {
            "valid": not transition_failure,
            "classification": (
                "unresolved_narrow_tail_merger"
                if transition_failure
                else "resolved_front_motion"
            ),
        },
        "protected_stack": {"survives": hard != "protected_stack_changed"},
        "model_diagnostics": {
            "valid": hard != "invalid_model_diagnostic",
            "center_velocity_mean": 0.12,
            "field_velocity_mean": 0.02,
        },
        "topology_transition_failure_seen": transition_failure,
        "invalid_topology_seen": hard in {
            "invalid_topology",
            "degenerate_closed_fragment",
        },
        "pinch_off_seen": hard == "pinch_off_or_closed_void",
        "protected_failure_seen": hard == "protected_stack_changed",
        "model_failure_seen": hard == "invalid_model_diagnostic",
        "target_pass": target,
    }


def result_row(case, *, outcome="censored", progress=None):
    coverage_lambda = access.recompute_lambda(case["model"])
    if progress is None:
        progress = 0.2 + 0.25 * coverage_lambda
    first = checkpoint(1, 1.15, elapsed=0.5)
    if outcome == "censored":
        second = checkpoint(2, 1.25 - progress, elapsed=8.0)
    elif outcome == "target":
        second = checkpoint(2, 0.0, elapsed=4.0, target=True)
    else:
        second = checkpoint(
            2,
            1.25 - progress,
            elapsed=2.0,
            hard=outcome,
        )
    trajectory = [first, second]
    failures = review._hard_failures(second)
    return {
        **case,
        "ok": True,
        "production_doe_eligible": False,
        "reference": {
            "initial_cavity_area": 0.25,
            "initial_topology": {
                "topology_valid": True,
                "open_void_depth": 1.25,
                "remaining_void_area": 0.25,
                "mouth_aperture": 0.2,
            },
        },
        "trajectory": trajectory,
        "last_checkpoint": 2,
        "topology_transition_failure_seen": (
            "unresolved_narrow_tail_merger" in failures
        ),
        "invalid_topology_seen": (
            "invalid_topology" in failures
            or "degenerate_closed_fragment" in failures
        ),
        "pinch_off_seen": "pinch_off_or_closed_void" in failures,
        "protected_failure_seen": "protected_stack_changed" in failures,
        "model_failure_seen": "invalid_model_diagnostic" in failures,
        "target_pass": outcome == "target",
        "screen_pass": outcome == "target",
    }


def all_current_rows(data, outcome="censored"):
    return [
        result_row(case, outcome=outcome)
        for case in access.expand_cases(data, FINGERPRINT)
    ]


def test_complete_72_case_matrix_ranks_worst_seed_and_censor_is_not_pass():
    data = manifest()
    rows = all_current_rows(data)
    summary = review.build_summary(data, rows, [], False, FINGERPRINT)

    assert summary["status"] == "complete"
    assert summary["selected_current_case_count"] == 72
    assert summary["metric_valid_case_count"] == 72
    assert len(summary["recipes"]) == 18
    assert len(summary["next_model_experiment_ranking"]) == 18
    assert summary["accepted_pass_count"] == 0
    assert all(recipe["censored_case_count"] == 4 for recipe in summary["recipes"])
    winner = summary["next_model_experiment_ranking"][0]
    assert winner["coverage_lambda"] == 1.25
    assert winner["censored_case_count"] == 4
    assert not winner["accepted_pass"]
    assert summary["next_decision"]["classification"] == (
        "expand_boundary_before_promotion"
    )
    assert "lambda" in summary["next_decision"]["boundary_axes"]


def test_manifest_name_or_lambda_value_mismatch_is_rejected():
    data = manifest()
    cases = access.expand_cases(data, FINGERPRINT)
    assert review.validate_manifest(data, cases) == []

    wrong_name = copy.deepcopy(data)
    wrong_name["designs"][0]["name"] = "lambda_0p625_stick_0p025"
    errors = review.validate_manifest(
        wrong_name, access.expand_cases(wrong_name, FINGERPRINT)
    )
    assert any("names lambda" in error for error in errors)

    wrong_value = copy.deepcopy(data)
    wrong_value["designs"][0]["model"]["adsorption_strength"] = 6.0
    errors = review.validate_manifest(
        wrong_value, access.expand_cases(wrong_value, FINGERPRINT)
    )
    assert any("parameters give" in error for error in errors)


def test_partial_current_error_and_duplicate_current_success_block_ranking():
    data = manifest()
    cases = access.expand_cases(data, FINGERPRINT)
    partial = [result_row(case) for case in cases[:-1]]
    summary = review.build_summary(data, partial, [], False, FINGERPRINT)
    assert summary["status"] == "incomplete_or_invalid"
    assert len(summary["missing_cases"]) == 1
    assert summary["next_model_experiment_ranking"] == []

    rows = all_current_rows(data)
    error = {
        **cases[0],
        "ok": False,
        "production_doe_eligible": False,
        "error": "current worker error",
    }
    summary = review.build_summary(
        data, [error, *rows], [], False, FINGERPRINT
    )
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["current_fingerprint_error_attempt_rows"] == [error]

    summary = review.build_summary(
        data, [rows[0], *rows], [], False, FINGERPRINT
    )
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["duplicate_success_case_ids"] == [cases[0]["case_id"]]


def test_superseded_success_and_error_are_visible_but_do_not_block_current():
    data = manifest()
    current = all_current_rows(data)
    old_fingerprint = {**FINGERPRINT, "runner_sha256": "old-runner"}
    old_cases = access.expand_cases(data, old_fingerprint)
    old_success = result_row(old_cases[0])
    old_error = {
        **old_cases[1],
        "ok": False,
        "production_doe_eligible": False,
        "error": "old worker error",
    }
    summary = review.build_summary(
        data,
        [old_success, old_error, *current],
        [],
        False,
        FINGERPRINT,
    )
    assert summary["status"] == "complete"
    assert summary["selected_current_case_count"] == 72
    assert summary["superseded_fingerprint_attempt_rows"] == [
        old_success,
        old_error,
    ]
    assert summary["superseded_fingerprint_error_attempt_rows"] == [old_error]
    assert summary["current_fingerprint_error_attempt_rows"] == []


def test_missing_rows_safe(tmp_path):
    data = manifest()
    summary = review.build_summary(data, [], [], True, FINGERPRINT)
    assert summary["status"] == "missing_rows"
    assert len(summary["recipes"]) == 18
    assert summary["next_model_experiment_ranking"] == []
    assert summary["next_decision"]["classification"] == (
        "complete_current_matrix_before_decision"
    )


if __name__ == "__main__":
    test_complete_72_case_matrix_ranks_worst_seed_and_censor_is_not_pass()
    test_manifest_name_or_lambda_value_mismatch_is_rejected()
    test_partial_current_error_and_duplicate_current_success_block_ranking()
    test_superseded_success_and_error_are_visible_but_do_not_block_current()
    with tempfile.TemporaryDirectory() as directory:
        test_missing_rows_safe(Path(directory))
    print("Cu-fill boundary-refinement reviewer checks: PASS")

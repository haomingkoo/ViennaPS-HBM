import copy
import json
import math
import tempfile
from pathlib import Path

import review_copper_fill_access_surface as review


FINGERPRINT = {
    "runner_sha256": "runner",
    "traveler_metrics_sha256": "metrics",
    "tsv_process_sha256": "process",
    "viennaps_binary_sha256": "binary",
}


def manifest():
    data = {
        "manifest_version": 4,
        "campaign": "foundation-copper-fill-access-coverage-surface",
        "geometry": {"radius": 0.15},
        "layers": {"liner": 0.03, "barrier": 0.01, "seed": 0.01},
        "model": {
            "suppressor_sticking_probability": 0.2,
            "adsorption_strength": 0.25,
            "deactivation_rate": 0.25,
            "active_deposition_rate": 0.2,
        },
        "numerics": {
            "grid_delta": 0.01,
            "checkpoint_interval": 0.025,
            "max_duration": 3.0,
        },
        "target": {"min_overburden": 0.15},
        "provenance": {"viennaps_binary_sha256": "binary"},
        "designs": [],
    }
    for coverage_lambda in review.LAMBDA_LEVELS:
        for sticking in review.STICKING_LEVELS:
            adsorption = coverage_lambda * 0.25 / sticking
            data["designs"].append({
                "name": review.expected_design_name(coverage_lambda, sticking),
                "model": {
                    "suppressor_sticking_probability": sticking,
                    "adsorption_strength": adsorption,
                },
                "rng_seeds": list(review.SEEDS),
            })
    return data


def model_diagnostics(strength):
    return {
        "valid": True,
        "field_coverage_mean": 0.8,
        "center_coverage_mean": 0.8 - 0.1 * strength,
        "field_velocity_mean": 0.02,
        "center_velocity_mean": 0.02 + 0.1 * strength,
    }


def topology(fill_fraction, mouth=0.15):
    return {
        "topology_valid": True,
        "fill_fraction": fill_fraction,
        "remaining_void_area": 0.2 * (1.0 - fill_fraction),
        "mouth_aperture": mouth,
        "overburden_min": -0.5 * (1.0 - fill_fraction),
        "pinch_off_failure": False,
    }


def checkpoint(index, fill_fraction, strength, *, seam=False, elapsed=None):
    height = 0.4 / strength if seam else 0.01
    width = 0.01 if seam else None
    return {
        "checkpoint": index,
        "elapsed": 0.1 * index if elapsed is None else elapsed,
        "topology": topology(fill_fraction),
        "topology_transition": {
            "valid": not seam,
            "classification": (
                "unresolved_narrow_tail_merger"
                if seam
                else "resolved_front_motion"
            ),
            "disappearing_tail_height": height,
            "disappearing_tail_max_width": width,
            "disappearing_tail_aspect_ratio": (
                height / width if seam else None
            ),
            "closure_width_bound": 0.02,
            "unresolved_seam_risk": seam,
        },
        "protected_stack": {"survives": True},
        "model_diagnostics": model_diagnostics(strength),
        "pinch_off_seen": False,
        "invalid_topology_seen": False,
        "topology_transition_failure_seen": seam,
        "protected_failure_seen": False,
        "model_failure_seen": False,
        "target_pass": False,
    }


def seam_row(case):
    strength = review.recompute_lambda(case["model"])
    progress = min(0.9, 0.25 + 0.2 * strength)
    trajectory = [
        checkpoint(1, progress - 0.05, strength),
        checkpoint(2, progress, strength, seam=True),
    ]
    return {
        **case,
        "ok": True,
        "production_doe_eligible": False,
        "trajectory": trajectory,
        "last_checkpoint": 2,
        "topology_transition_failure_seen": True,
        "invalid_topology_seen": False,
        "pinch_off_seen": False,
        "protected_failure_seen": False,
        "model_failure_seen": False,
        "target_pass": False,
        "screen_pass": False,
    }


def censored_row(case):
    strength = review.recompute_lambda(case["model"])
    item = checkpoint(1, 0.95, strength, elapsed=3.0)
    return {
        **case,
        "ok": True,
        "production_doe_eligible": False,
        "trajectory": [item],
        "last_checkpoint": 1,
        "topology_transition_failure_seen": False,
        "invalid_topology_seen": False,
        "pinch_off_seen": False,
        "protected_failure_seen": False,
        "model_failure_seen": False,
        "target_pass": False,
        "screen_pass": False,
    }


def all_seam_rows(data):
    return [
        seam_row(case)
        for case in review.expand_cases(data, FINGERPRINT)
    ]


def test_complete_surface_aggregates_points_main_effects_and_seed_spread():
    data = manifest()
    rows = all_seam_rows(data)

    summary = review.build_summary(data, rows, [], False, FINGERPRINT)

    assert summary["status"] == "complete"
    assert summary["selected_case_count"] == 32
    assert summary["metric_valid_case_count"] == 32
    assert len(summary["points"]) == 16
    assert len(summary["lambda_main_surface"]) == 4
    assert len(summary["sticking_main_surface"]) == 4
    point = next(
        item
        for item in summary["points"]
        if item["coverage_lambda"] == 1.0
        and item["sticking_probability"] == 0.2
    )
    assert point["n"] == 2
    assert point["hard_failure_type_counts"] == {
        "unresolved_narrow_tail_merger": 2
    }
    assert point["metrics"]["tail_height"]["mean"] == 0.4
    assert point["seed_spread"]["tail_height"] == 0.0
    assert math.isclose(
        point["metrics"]["initial_coverage_contrast"]["mean"], 0.1
    )
    assert math.isclose(
        point["metrics"]["terminal_velocity_contrast"]["mean"], 0.1
    )
    assert summary["accepted_pass_count"] == 0
    assert summary["next_model_experiment_ranking"]
    assert summary["next_model_experiment_ranking"][0][
        "next_model_experiment_only"
    ]


def test_censored_point_is_visible_and_never_a_pass():
    data = manifest()
    cases = review.expand_cases(data, FINGERPRINT)
    rows = [
        censored_row(case)
        if case["design"] == "lambda_2p0_stick_0p8"
        else seam_row(case)
        for case in cases
    ]

    summary = review.build_summary(data, rows, [], False, FINGERPRINT)

    point = next(
        item
        for item in summary["points"]
        if item["coverage_lambda"] == 2.0
        and item["sticking_probability"] == 0.8
    )
    assert point["censored_case_count"] == 2
    assert point["hard_failure_case_count"] == 0
    assert point["accepted_pass_count"] == 0
    assert summary["accepted_pass_count"] == 0
    assert summary["next_model_experiment_ranking"][0]["design"] == (
        "lambda_2p0_stick_0p8"
    )
    assert "Censored trajectories are not passes" in review.markdown(summary)


def test_lambda_name_or_value_mismatch_invalidates_manifest():
    data = manifest()
    cases = review.expand_cases(data, FINGERPRINT)
    assert review.validate_manifest(data, cases) == []

    wrong_name = copy.deepcopy(data)
    wrong_name["designs"][0]["name"] = "lambda_0p5_stick_0p05"
    errors = review.validate_manifest(
        wrong_name, review.expand_cases(wrong_name, FINGERPRINT)
    )
    assert any("names lambda" in error for error in errors)

    wrong_value = copy.deepcopy(data)
    wrong_value["designs"][0]["model"]["adsorption_strength"] = 2.0
    errors = review.validate_manifest(
        wrong_value, review.expand_cases(wrong_value, FINGERPRINT)
    )
    assert any("parameters give" in error for error in errors)


def test_current_fingerprint_and_invalid_metrics_are_hard_audit_failures():
    data = manifest()
    rows = all_seam_rows(data)
    rows[0] = copy.deepcopy(rows[0])
    rows[0]["runtime_fingerprint"]["runner_sha256"] = "old"
    rows[1]["trajectory"][0]["model_diagnostics"][
        "field_coverage_mean"
    ] = None

    summary = review.build_summary(data, rows, [], False, FINGERPRINT)

    assert summary["status"] == "incomplete_or_invalid"
    assert summary["invalid_attempts"]
    assert summary["invalid_metric_rows"]
    assert summary["next_model_experiment_ranking"] == []


def test_partial_or_missing_rows_are_safe_and_unranked(tmp_path):
    data = manifest()
    summary = review.build_summary(data, [], [], True, FINGERPRINT)
    assert summary["status"] == "missing_rows"
    assert len(summary["points"]) == 16
    assert all(point["n"] == 0 for point in summary["points"])
    assert summary["next_model_experiment_ranking"] == []

    path = tmp_path / "live.jsonl"
    row = all_seam_rows(data)[0]
    path.write_text(json.dumps(row) + "\n{\"unfinished\":")
    rows, errors, missing = review.load_jsonl(path)
    assert len(rows) == 1
    assert len(errors) == 1
    assert errors[0]["raw_line"] == '{"unfinished":'
    assert not missing
    summary = review.build_summary(data, rows, errors, missing, FINGERPRINT)
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["parse_errors"] == errors


def test_current_fingerprint_error_attempt_blocks_even_after_valid_retry():
    data = manifest()
    cases = review.expand_cases(data, FINGERPRINT)
    failed = {
        **cases[0],
        "ok": False,
        "production_doe_eligible": False,
        "error": "synthetic worker error",
    }
    summary = review.build_summary(
        data,
        [failed, *all_seam_rows(data)],
        [],
        False,
        FINGERPRINT,
    )
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["error_attempt_rows"] == [failed]
    assert summary["current_fingerprint_error_attempt_rows"] == [failed]
    assert summary["selected_case_count"] == 32
    assert summary["next_model_experiment_ranking"] == []


def test_old_success_and_errors_remain_visible_without_blocking_clean_matrix():
    data = manifest()
    current = all_seam_rows(data)
    old_fingerprint = {**FINGERPRINT, "runner_sha256": "old-runner"}
    old_cases = review.expand_cases(data, old_fingerprint)
    old_success = seam_row(old_cases[0])
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
    assert summary["selected_case_count"] == 32
    assert summary["metric_valid_case_count"] == 32
    assert summary["superseded_fingerprint_attempt_count"] == 2
    assert summary["superseded_fingerprint_attempt_rows"] == [
        old_success,
        old_error,
    ]
    assert summary["superseded_fingerprint_error_attempt_rows"] == [old_error]
    assert summary["current_fingerprint_error_attempt_rows"] == []
    assert summary["invalid_attempts"] == []
    assert summary["next_model_experiment_ranking"]


if __name__ == "__main__":
    test_complete_surface_aggregates_points_main_effects_and_seed_spread()
    test_censored_point_is_visible_and_never_a_pass()
    test_lambda_name_or_value_mismatch_invalidates_manifest()
    test_current_fingerprint_and_invalid_metrics_are_hard_audit_failures()
    with tempfile.TemporaryDirectory() as directory:
        test_partial_or_missing_rows_are_safe_and_unranked(Path(directory))
    test_current_fingerprint_error_attempt_blocks_even_after_valid_retry()
    test_old_success_and_errors_remain_visible_without_blocking_clean_matrix()
    print("Cu-fill access-surface reviewer checks: PASS")

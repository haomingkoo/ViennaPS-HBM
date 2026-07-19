import json
import tempfile
from pathlib import Path

import review_copper_fill_trajectory as review


FINGERPRINT = {
    "runner_sha256": "runner",
    "traveler_metrics_sha256": "metrics",
    "tsv_process_sha256": "process",
    "viennaps_binary_sha256": "binary",
}


def manifest():
    return {
        "manifest_version": 1,
        "campaign": "synthetic",
        "geometry": {"radius": 0.15},
        "layers": {"liner": 0.03, "barrier": 0.01, "seed": 0.01},
        "model": {
            "adsorption_strength": 0.0,
            "active_deposition_rate": 0.2,
        },
        "numerics": {
            "grid_delta": 0.01,
            "checkpoint_interval": 0.05,
            "max_duration": 1.0,
        },
        "target": {"min_overburden": 0.15},
        "provenance": {"viennaps_binary_sha256": "binary"},
        "designs": [
            {
                "name": "low",
                "model": {"adsorption_strength": 0.0},
                "rng_seeds": [10],
            },
            {
                "name": "high",
                "model": {"adsorption_strength": 0.5},
                "rng_seeds": [10],
            },
        ],
    }


def topology(
    depth,
    area,
    *,
    overburden=-0.1,
    valid=True,
    closed=0,
):
    open_void = depth > 0
    void_free = valid and not open_void and not closed
    return {
        "topology_valid": valid,
        "open_void": open_void,
        "open_void_depth": depth,
        "closed_void_count": closed,
        "void_free": void_free,
        "remaining_void_area": area,
        "fill_fraction": 1.0 - area / 0.2,
        "mouth_aperture": 0.1 if open_void else 0.0,
        "overburden_min": overburden,
        "overburden_mean": overburden + 0.01,
        "overburden_nonuniformity": 0.01,
        "pinch_off_failure": bool(closed),
        "void_area_detection_limit": 0.0001,
    }


def checkpoint(index, topo, *, target=False, invalid=False, seam=False):
    result = {
        "checkpoint": index,
        "elapsed": 0.05 * index,
        "topology": topo,
        "protected_stack": {"survives": True},
        "model_diagnostics": {"valid": True},
        "pinch_off_seen": False,
        "invalid_topology_seen": invalid,
        "topology_transition_failure_seen": seam,
        "protected_failure_seen": False,
        "model_failure_seen": False,
        "target_pass": target,
    }
    if seam:
        result["topology_transition"] = {
            "valid": False,
            "classification": "unresolved_narrow_tail_merger",
            "unresolved_seam_risk": True,
            "disappearing_tail_height": 0.79,
            "disappearing_tail_max_width": 0.015,
            "disappearing_tail_aspect_ratio": 52.6666666667,
            "closure_width_bound": 0.03,
            "previous_open_void_depth": 0.99,
            "current_open_void_depth": 0.20,
            "observed_open_void_depth_drop": 0.79,
            "reason": "seam-free closure cannot be certified",
        }
    else:
        result["topology_transition"] = {
            "valid": True,
            "classification": "resolved_front_motion",
        }
    return result


def result_row(case, trajectory, *, ok=True, error=None):
    row = {
        **case,
        "ok": ok,
        "production_doe_eligible": False,
    }
    if not ok:
        row.update({"error": error or "synthetic error"})
        return row
    invalid = any(item["invalid_topology_seen"] for item in trajectory)
    seam = any(item["topology_transition_failure_seen"] for item in trajectory)
    target = any(item["target_pass"] for item in trajectory)
    row.update({
        "reference": {
            "initial_cavity_area": 0.2,
            "via_x_bounds": [-0.1, 0.1],
            "initial_topology": topology(1.0, 0.2),
        },
        "numerical_invariants": {"max_front_displacement": 0.01},
        "trajectory": trajectory,
        "target_pass": target,
        "screen_pass": target,
        "pinch_off_seen": False,
        "invalid_topology_seen": invalid,
        "topology_transition_failure_seen": seam,
        "protected_failure_seen": False,
        "model_failure_seen": False,
        "last_checkpoint": trajectory[-1]["checkpoint"],
    })
    return row


def test_rejects_reported_pass_after_unresolved_seam_transition():
    data = manifest()
    low, high = review.expand_expected_cases(data, FINGERPRINT)
    low_row = result_row(low, [
        checkpoint(1, topology(0.99, 0.18)),
        checkpoint(2, topology(0.20, 0.02), seam=True),
        checkpoint(3, topology(0.0, 0.0, overburden=0.05)),
        checkpoint(4, topology(0.0, 0.0, overburden=0.16), target=True),
    ])
    high_row = result_row(high, [
        checkpoint(1, topology(0.99, 0.18)),
        checkpoint(
            2,
            topology(0.98, 0.17, valid=False),
            invalid=True,
        ),
    ])

    summary = review.build_summary(
        data, [low_row, high_row], [], False, FINGERPRINT
    )

    assert summary["status"] == "complete_with_unresolved_seam_failures"
    assert summary["reported_screen_pass_count"] == 1
    assert summary["review_valid_screen_pass_count"] == 0
    assert summary["transition_plausibility_failure_count"] >= 1
    low_summary = summary["designs"][0]["cases"][0]
    failure = low_summary["transition_plausibility_failures"][0]
    assert failure["type"] == "unresolved_narrow_tail_merger"
    assert failure["tail_height"] == 0.79
    assert failure["tail_maximum_width"] == 0.015
    assert failure["closure_width_bound"] == 0.03
    assert low_summary["events"]["first_reported_target_pass"]["checkpoint"] == 4
    assert low_summary["events"]["first_review_valid_target_pass"] is None
    assert summary["best_valid_miss"]["checkpoint"] == 1
    report = review.markdown(summary)
    assert "hard seam failures" in report
    assert "lambda × sticking" in report


def test_preserves_error_attempt_before_recovered_result():
    data = manifest()
    cases = review.expand_expected_cases(data, FINGERPRINT)
    error = result_row(cases[0], [], ok=False, error="worker vanished")
    recovered = result_row(cases[0], [
        checkpoint(1, topology(0.99, 0.18)),
    ])
    other = result_row(cases[1], [
        checkpoint(1, topology(0.99, 0.18)),
    ])

    summary = review.build_summary(
        data, [error, recovered, other], [], False, FINGERPRINT
    )

    assert summary["status"] == "complete_with_recovered_attempts"
    assert summary["error_attempt_count"] == 1
    assert summary["error_attempt_rows"][0]["error"] == "worker vanished"
    assert summary["selected_case_count"] == 2


def test_missing_and_partially_written_jsonl_are_reviewable(tmp_path):
    missing = tmp_path / "missing.jsonl"
    rows, parse_errors, absent = review.load_jsonl(missing)
    assert rows == []
    assert parse_errors == []
    assert absent

    data = manifest()
    summary = review.build_summary(
        data, rows, parse_errors, absent, FINGERPRINT
    )
    assert summary["status"] == "missing_rows"
    assert all(
        case["status"] == "missing"
        for design in summary["designs"]
        for case in design["cases"]
    )

    case = review.expand_expected_cases(data, FINGERPRINT)[0]
    path = tmp_path / "live.jsonl"
    path.write_text(json.dumps(result_row(case, [
        checkpoint(1, topology(0.99, 0.18)),
    ])) + "\n{\"case_id\":")
    rows, parse_errors, absent = review.load_jsonl(path)
    assert len(rows) == 1
    assert len(parse_errors) == 1
    assert parse_errors[0]["raw_line"] == '{"case_id":'
    summary = review.build_summary(
        data, rows, parse_errors, absent, FINGERPRINT
    )
    assert summary["status"] == "incomplete_or_invalid_output"
    assert summary["parse_errors"] == parse_errors


def test_runtime_fingerprint_and_duplicate_successes_are_hard_audit_failures():
    data = manifest()
    cases = review.expand_expected_cases(data, FINGERPRINT)
    row = result_row(cases[0], [
        checkpoint(1, topology(0.99, 0.18)),
    ])
    duplicate = json.loads(json.dumps(row))
    wrong = json.loads(json.dumps(result_row(cases[1], [
        checkpoint(1, topology(0.99, 0.18)),
    ])))
    wrong["runtime_fingerprint"]["viennaps_binary_sha256"] = "other"

    summary = review.build_summary(
        data, [row, duplicate, wrong], [], False, FINGERPRINT
    )

    assert summary["status"] == "incomplete_or_invalid_output"
    assert summary["duplicate_success_case_ids"] == [cases[0]["case_id"]]
    assert summary["invalid_attempts"]
    assert any(
        "runtime fingerprint" in reason
        for reason in summary["invalid_attempts"][0]["reasons"]
    )


def test_self_consistent_old_fingerprint_is_preserved_as_superseded():
    data = manifest()
    cases = review.expand_expected_cases(data, FINGERPRINT)
    current = [
        result_row(case, [checkpoint(1, topology(0.99, 0.18))])
        for case in cases
    ]
    old_fingerprint = {**FINGERPRINT, "runner_sha256": "old-runner"}
    old_case = review.expand_expected_cases(data, old_fingerprint)[0]
    old_row = result_row(old_case, [
        checkpoint(1, topology(0.99, 0.18)),
    ])

    summary = review.build_summary(
        data, [old_row, *current], [], False, FINGERPRINT
    )

    assert summary["status"] == "complete_coarse_screen"
    assert summary["superseded_fingerprint_attempt_count"] == 1
    assert summary["superseded_fingerprint_attempt_rows"] == [old_row]
    assert summary["invalid_attempts"] == []


def test_rejects_contradictory_void_free_target():
    data = manifest()
    case = review.expand_expected_cases(data, FINGERPRINT)[0]
    contradictory = topology(0.0, 0.0, overburden=0.16)
    contradictory.update({
        "void_free": True,
        "open_void": False,
        "open_void_depth": 0.99,
        "remaining_void_area": 0.18,
    })
    row = result_row(case, [checkpoint(1, contradictory, target=True)])
    errors = review._trajectory_validation_errors(row)
    assert any("open_void disagrees" in error for error in errors)
    assert any("void_free disagrees" in error for error in errors)


def test_rejects_missing_checkpoint_gate_records():
    data = manifest()
    case = review.expand_expected_cases(data, FINGERPRINT)[0]
    item = checkpoint(1, topology(0.0, 0.0, overburden=0.16), target=True)
    del item["protected_stack"]
    del item["model_diagnostics"]
    del item["topology_transition"]
    row = result_row(case, [item])
    errors = review._trajectory_validation_errors(row)
    assert any("target_pass does not satisfy" in error for error in errors)


if __name__ == "__main__":
    test_rejects_reported_pass_after_unresolved_seam_transition()
    test_preserves_error_attempt_before_recovered_result()
    with tempfile.TemporaryDirectory() as directory:
        test_missing_and_partially_written_jsonl_are_reviewable(
            Path(directory)
        )
    test_runtime_fingerprint_and_duplicate_successes_are_hard_audit_failures()
    test_self_consistent_old_fingerprint_is_preserved_as_superseded()
    test_rejects_contradictory_void_free_target()
    test_rejects_missing_checkpoint_gate_records()
    print("Cu-fill trajectory reviewer checks: PASS")

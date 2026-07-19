"""Guards for the clean 24-cell lower-sticking boundary confirmation."""

from __future__ import annotations

import copy
import json
import math
import tempfile
from pathlib import Path

import foundation_copper_fill_transport_boundary_confirmation as campaign
import review_copper_fill_transport_boundary_confirmation as review


ROOT = Path(__file__).resolve().parents[1]
FAKE_FINGERPRINT = {
    "runner_sha256": "runner",
    "coarse_runner_sha256": "coarse",
    "trajectory_runner_sha256": "trajectory",
    "regional_kinematics_sha256": "regional",
    "traveler_metrics_sha256": "metrics",
    "tsv_process_sha256": "process",
    "viennaps_binary_sha256": "binary",
}


def manifest():
    return json.loads((ROOT / campaign.DEFAULT_MANIFEST).read_text())


def _attempt(case, ok=True):
    return {
        **case,
        "ok": ok,
        "production_doe_eligible": False,
        "morphology_ranking_eligible": False,
        "evidence_origin": {
            "mode": "executed_boundary_confirmation",
            "reflection_residual_upper_bound": case[
                "reflection_residual_upper_bound"
            ],
            "parent_simulation_reused": False,
        },
        **({} if ok else {"error": "synthetic retry"}),
    }


def test_clean_matrix_size_coupling_cap_and_no_reuse():
    data = manifest()
    cases = campaign.expand_cases(data, FAKE_FINGERPRINT)
    assert campaign.validate_manifest(data, cases) == []
    assert len(cases) == 24
    assert len({campaign._logical_key(case) for case in cases}) == 24
    counts = {}
    for case in cases:
        key = (case["design"], case["numerics"]["max_reflections"])
        counts[key] = counts.get(key, 0) + 1
        assert case["numerics"]["max_boundary_hits"] == 6400
        model = case["model"]
        assert math.isclose(
            model["adsorption_strength"]
            * model["suppressor_sticking_probability"],
            0.25,
            abs_tol=1e-15,
        )
        assert math.isclose(
            model["adsorption_strength"]
            * model["suppressor_sticking_probability"]
            / (model["deactivation_rate"] * model["active_deposition_rate"]),
            5.0,
            abs_tol=1e-15,
        )
        assert math.isclose(
            case["reflection_residual_upper_bound"],
            (1.0 - model["suppressor_sticking_probability"])
            ** case["numerics"]["max_reflections"],
            abs_tol=1e-15,
        )
    assert counts == {
        (campaign.CONTROL_NAME, 800): 8,
        (campaign.CANDIDATE_NAME, 1600): 8,
        (campaign.CANDIDATE_NAME, 3200): 8,
    }
    assert data["parent_comparison"]["reuse_count"] == 0
    assert data["runtime_estimate"]["new_simulations"] == 24
    assert data["runtime_estimate"]["worker_cap"] == 4
    tolerances = data["reflection_convergence"][
        "maximum_paired_absolute_delta"
    ]
    parent_effects = data["reflection_convergence"][
        "parent_B_pure_reflection_worst_absolute_effect"
    ]
    assert set(tolerances) == set(parent_effects)
    assert all(
        math.isclose(tolerances[name], 10.0 * parent_effects[name], abs_tol=1e-18)
        for name in tolerances
    )


def test_confounded_16_cell_design_is_durably_rejected():
    data = manifest()
    rejected = data["rejected_design"]
    assert rejected["logical_cells"] == 16
    assert rejected["decision"] == "rejected_before_launch"
    assert "maxBoundaryHits=1000" in rejected["reason"]
    assert "eight matched-cap B controls" in rejected["reason"]

    bad_cap = copy.deepcopy(data)
    bad_cap["numerics"]["max_boundary_hits"] = 1000
    errors = campaign.validate_manifest(bad_cap)
    assert any("numerical controls" in error for error in errors)

    missing_control = copy.deepcopy(data)
    missing_control["designs"] = missing_control["designs"][1:]
    errors = campaign.validate_manifest(missing_control)
    assert any("matched control" in error for error in errors)
    assert any("24 new logical cells" in error for error in errors)


def test_target_analysis_and_authority_drift_fail_closed():
    data = manifest()
    drifted = copy.deepcopy(data)
    drifted["target"]["max_balance_error"] = 1e-8
    assert any("target gates" in error for error in campaign.validate_manifest(drifted))

    relaxed = copy.deepcopy(data)
    relaxed["analysis"]["floor_to_each_lower_flux_ratio_upper_bound_strict"] = 1.0
    assert any("analysis gates" in error for error in campaign.validate_manifest(relaxed))

    authority = copy.deepcopy(data)
    authority["decision_policy"]["automatic_morphology_authorized"] = True
    assert any("automatic downstream authority" in error for error in campaign.validate_manifest(authority))


def test_historical_parent_is_verified_but_not_reused():
    data = manifest()
    parents, errors = campaign.load_verified_parent_comparison(data, ROOT)
    assert errors == []
    assert len(parents) == 8
    assert all(row["numerics"]["max_boundary_hits"] == 1000 for row in parents.values())
    assert all(
        case["numerics"]["max_boundary_hits"] == 6400
        for case in campaign.expand_cases(data, FAKE_FINGERPRINT)
    )

    tampered = copy.deepcopy(data)
    tampered["parent_comparison"]["rows"][0][
        "parent_row_canonical_sha256"
    ] = "0" * 64
    _, errors = campaign.load_verified_parent_comparison(tampered, ROOT)
    assert any("parent row hash mismatch" in error for error in errors)


def test_resume_requires_success_and_matching_snapshot():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output = root / "rows.jsonl"
        snapshot = root / "snapshot.npz"
        snapshot.write_bytes(b"snapshot")
        good = {
            "case_id": "good",
            "ok": True,
            "diagnostic_snapshot_path": str(snapshot),
            "diagnostic_snapshot_sha256": campaign._file_sha256(snapshot),
        }
        error = {"case_id": "error", "ok": False}
        bad_hash = {
            "case_id": "bad",
            "ok": True,
            "diagnostic_snapshot_path": str(snapshot),
            "diagnostic_snapshot_sha256": "0" * 64,
        }
        output.write_text("\n".join([
            json.dumps(good),
            json.dumps(error),
            json.dumps(bad_hash),
            "[]",
            json.dumps({
                "case_id": "bad-path",
                "ok": True,
                "diagnostic_snapshot_path": [],
            }),
            "{",
        ]))
        assert campaign._completed_case_ids(output) == {"good"}


def test_attempt_retry_recovery_and_post_success_failure():
    data = manifest()
    cases = campaign.expand_cases(data, FAKE_FINGERPRINT)
    successes = [_attempt(case) for case in cases]
    retry = _attempt(cases[0], ok=False)
    audit = review.audit_attempts(
        data, [retry, *successes], [], False, FAKE_FINGERPRINT
    )
    assert audit["status"] == "complete"
    assert audit["resolved_current_error_attempt_rows"] == [retry]
    assert audit["selected_current_case_count"] == 24

    audit = review.audit_attempts(
        data, [*successes, retry], [], False, FAKE_FINGERPRINT
    )
    assert audit["status"] == "incomplete_or_invalid"
    assert audit["current_error_attempt_rows"] == [retry]


def _reflection_records(delta=0.0, condition_change=False):
    records = []
    for tier in campaign.GEOMETRY_TIERS:
        for seed in campaign.PAIRED_BASE_SEEDS:
            for reflections in campaign.REFLECTION_ARMS:
                value = 1.0 + (delta if reflections == 3200 else 0.0)
                conditions = {
                    "all_required_regions_nonempty_and_finite": True,
                    "diagnostic_balance_valid": True,
                    "diagnostic_and_structure_guards_valid": True,
                    "floor_to_each_lower_flux_ratio_strictly_below_0p95": False,
                    "floor_coverage_strictly_below_each_lower_wall": True,
                    "floor_to_each_lower_velocity_ratio_strictly_above_1p05": False,
                    "floor_velocity_strictly_above_each_middle_and_upper_side": True,
                }
                if condition_change and tier == "continuity" and seed == 102000 and reflections == 3200:
                    conditions["floor_to_each_lower_flux_ratio_strictly_below_0p95"] = True
                records.append({"public": {
                    "geometry_tier": tier,
                    "rng_seed": seed,
                    "max_reflections": reflections,
                    "transport_sign": {"conditions": conditions},
                    "responses": {name: value for name in review.RESPONSES},
                }})
    return records


def _arm_classes(low="no_go", high="no_go"):
    return {1600: {"classification": low}, 3200: {"classification": high}}


def test_reflection_convergence_uses_paired_tolerances_and_classes():
    data = manifest()
    converged = review.reflection_convergence(
        _reflection_records(delta=1e-6), _arm_classes(), data
    )
    assert converged["converged"]
    assert not converged["condition_changes"]

    too_large = review.reflection_convergence(
        _reflection_records(delta=0.001), _arm_classes(), data
    )
    assert not too_large["converged"]
    assert not too_large["response_deltas"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["pass"]

    changed = review.reflection_convergence(
        _reflection_records(condition_change=True), _arm_classes(), data
    )
    assert not changed["converged"]
    assert changed["condition_changes"]

    changed_class = review.reflection_convergence(
        _reflection_records(), _arm_classes("no_go", "pass"), data
    )
    assert not changed_class["converged"]

    nonfinite_records = _reflection_records()
    nonfinite_records[0]["public"]["responses"][
        "worst_floor_to_each_lower_flux_ratio"
    ] = None
    nonfinite = review.reflection_convergence(
        nonfinite_records, _arm_classes(), data
    )
    assert not nonfinite["eligible"]
    assert not nonfinite["converged"]
    assert nonfinite["response_deltas"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["invalid_pairs"]


def test_empty_or_nonfinite_required_metrics_are_invalid_not_normal_misses():
    valid_conditions = {
        "all_required_regions_nonempty_and_finite": True,
        "diagnostic_balance_valid": True,
        "diagnostic_and_structure_guards_valid": True,
    }
    decisions = [{"conditions": dict(valid_conditions)} for _ in range(8)]
    responses = {
        name: {
            "count": 8,
            "mean": 1.0,
            "adverse_p90": 1.0,
            "worst": 1.0,
        }
        for name in review.RESPONSES
    }
    assert review._required_arm_metrics_valid(decisions, responses, 8)

    empty_region = copy.deepcopy(decisions)
    empty_region[0]["conditions"][
        "all_required_regions_nonempty_and_finite"
    ] = False
    assert not review._required_arm_metrics_valid(empty_region, responses, 8)

    missing_response = copy.deepcopy(responses)
    missing_response["worst_floor_to_each_lower_flux_ratio"] = {
        "count": 7,
        "mean": 1.0,
        "adverse_p90": 1.0,
        "worst": None,
    }
    assert not review._required_arm_metrics_valid(
        decisions, missing_response, 8
    )


def test_analytic_envelope_and_realized_kinematics_remain_visible_after_flux_miss():
    envelope = review._analytic_envelope_status({
        "fixed_flux_gate_all_eight": False,
        "analytic_h_over_a_pass": False,
        "best_worst_normalized_margin": None,
    }, 0)
    assert envelope["evaluation_status"] == (
        "not_evaluated_preliminary_flux_gate_failed"
    )
    assert envelope["preliminary_flux_gate_pass_count"] == 0
    assert "not evaluated because" in envelope["evaluation_reason"]

    records = []
    for tier_index, tier in enumerate(campaign.GEOMETRY_TIERS):
        threshold = 10.0 if tier_index == 0 else 25.0
        for seed_index, seed in enumerate(campaign.PAIRED_BASE_SEEDS):
            records.append({"public": {
                "geometry_tier": tier,
                "rng_seed": seed,
                "realized_floor_to_fastest_wall_velocity_ratio": (
                    1.001 + 0.001 * seed_index
                ),
                "kinematic_threshold_H_over_a": threshold,
            }})
    realized = review._realized_kinematic_by_tier(records)
    assert realized["continuity"]["eligible"]
    assert realized["continuity"]["required_H_over_a"] == 10.0
    assert math.isclose(
        realized["continuity"]["realized_minimum"], 1.001, abs_tol=1e-15
    )
    assert math.isclose(
        realized["continuity"]["realized_maximum"], 1.004, abs_tol=1e-15
    )
    assert realized["continuity"]["stream_pass_count"] == 0
    assert realized["nominal_hbm"]["required_H_over_a"] == 25.0
    assert realized["nominal_hbm"]["stream_pass_count"] == 0


def _trend_records(design, reflections, flux):
    return [
        {"public": {
            "design": design,
            "geometry_tier": tier,
            "rng_seed": seed,
            "max_reflections": reflections,
            "responses": {
                "worst_floor_to_each_lower_flux_ratio": flux,
            },
        }}
        for tier in campaign.GEOMETRY_TIERS
        for seed in campaign.PAIRED_BASE_SEEDS
    ]


def test_boundary_decisions_never_auto_authorize_downstream_work():
    control = _trend_records(campaign.CONTROL_NAME, 800, 1.0)
    candidate = _trend_records(campaign.CANDIDATE_NAME, 3200, 0.98)
    convergence = {
        "converged": True,
        "response_deltas": {
            "worst_floor_to_each_lower_flux_ratio": {
                "worst_absolute_delta": 0.001,
            }
        },
    }
    control_summary = {
        "response_summaries": {
            "worst_floor_to_each_lower_flux_ratio": {"worst": 1.0}
        }
    }
    candidate_summary = {
        "response_summaries": {
            "worst_floor_to_each_lower_flux_ratio": {"worst": 0.98}
        },
        "combined_2d_pass": False,
        "classification": "no_go",
    }
    trend = review.boundary_trend(
        control, candidate, convergence, control_summary, candidate_summary,
        manifest()["decision_policy"][
            "minimum_boundary_improvement_over_matched_control"
        ],
    )
    assert trend["continued_boundary_improvement"]
    decision = review.decision_from_evidence(
        candidate_summary, convergence, trend
    )
    assert decision["classification"] == (
        "lower_sticking_boundary_remains_open_requires_sol_review"
    )
    assert decision["morphology_authorized"] is False
    assert decision["model_family_pivot_authorized"] is False
    assert decision["automatic_further_boundary_launch_authorized"] is False

    passing = {**candidate_summary, "combined_2d_pass": True, "classification": "pass"}
    decision = review.decision_from_evidence(passing, convergence, trend)
    assert decision["classification"] == (
        "lower_sticking_boundary_candidate_requires_matched_3d"
    )
    assert decision["morphology_authorized"] is False

    inconclusive = review.decision_from_evidence(
        candidate_summary, {**convergence, "converged": False}, trend
    )
    assert inconclusive["classification"] == (
        "reflection_convergence_inconclusive_refine"
    )

    invalid = review.decision_from_evidence(
        candidate_summary, convergence, trend, required_arms_valid=False
    )
    assert invalid["classification"] == (
        "invalid_hard_gate_evidence_blocks_inference"
    )

    invalid_candidate = copy.deepcopy(candidate)
    invalid_candidate[0]["public"]["responses"][
        "worst_floor_to_each_lower_flux_ratio"
    ] = None
    invalid_summary = copy.deepcopy(candidate_summary)
    invalid_summary["response_summaries"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["worst"] = None
    ineligible_trend = review.boundary_trend(
        control,
        invalid_candidate,
        convergence,
        control_summary,
        invalid_summary,
        manifest()["decision_policy"][
            "minimum_boundary_improvement_over_matched_control"
        ],
    )
    assert not ineligible_trend["eligible"]
    assert not ineligible_trend["continued_boundary_improvement"]
    ineligible_decision = review.decision_from_evidence(
        candidate_summary, convergence, ineligible_trend
    )
    assert ineligible_decision["classification"] == (
        "boundary_trend_ineligible_blocks_inference"
    )
    assert ineligible_decision["classification"] != (
        "two_dimensional_transport_no_go_requires_matched_3d_before_pivot"
    )
    json.dumps(ineligible_trend, allow_nan=False)

    below_envelope = {
        **trend,
        "continued_boundary_improvement": False,
        "worst_response_improvement_B_minus_C": 0.004146586959089649,
        "minimum_boundary_improvement": 0.016714424655445925,
    }
    no_go = review.decision_from_evidence(
        candidate_summary, convergence, below_envelope
    )
    assert no_go["classification"] == (
        "two_dimensional_transport_no_go_requires_matched_3d_before_pivot"
    )
    assert "all 8 paired streams" in no_go["reason"]
    assert "0.00414659" in no_go["reason"]
    assert "0.0167144" in no_go["reason"]
    assert "did not exceed" in no_go["reason"]

    mixed_direction = {
        **below_envelope,
        "improves_every_stream_in_both_tiers": False,
    }
    mixed_no_go = review.decision_from_evidence(
        candidate_summary, convergence, mixed_direction
    )
    assert "did not improve in every paired stream" in mixed_no_go["reason"]
    assert "improved in all 8 paired streams" not in mixed_no_go["reason"]


def test_multiresponse_paired_directions_report_each_response_not_only_flux():
    control = []
    candidate = []
    keys = [
        (tier, seed)
        for tier in campaign.GEOMETRY_TIERS
        for seed in campaign.PAIRED_BASE_SEEDS
    ]
    for index, (tier, seed) in enumerate(keys):
        control.append({"public": {
            "geometry_tier": tier,
            "rng_seed": seed,
            "max_reflections": 800,
            "responses": {
                "worst_floor_to_each_lower_flux_ratio": 1.0,
                "minimum_lower_minus_floor_coverage": 0.10,
                "worst_floor_to_each_lower_velocity_ratio": 1.00,
                "minimum_floor_minus_middle_upper_velocity": 0.20,
            },
        }})
        candidate.append({"public": {
            "geometry_tier": tier,
            "rng_seed": seed,
            "max_reflections": 3200,
            "responses": {
                "worst_floor_to_each_lower_flux_ratio": 0.99,
                "minimum_lower_minus_floor_coverage": (
                    0.20 if index < 5 else 0.05
                ),
                "worst_floor_to_each_lower_velocity_ratio": (
                    1.01 if index < 7 else 0.99
                ),
                "minimum_floor_minus_middle_upper_velocity": 0.10,
            },
        }})
    paired = review.multiresponse_paired_directions(control, candidate)
    assert paired["eligible"]
    responses = paired["responses"]
    assert responses[
        "worst_floor_to_each_lower_flux_ratio"
    ]["improved_count"] == 8
    assert responses[
        "worst_floor_to_each_lower_velocity_ratio"
    ]["improved_count"] == 7
    assert responses[
        "minimum_lower_minus_floor_coverage"
    ]["improved_count"] == 5
    upper_margin = responses[
        "minimum_floor_minus_middle_upper_velocity"
    ]
    assert upper_margin["worsened_count"] == 8
    assert upper_margin["candidate_gate_pass_count"] == 8


def test_historical_cap_context_is_fail_closed_for_invalid_response():
    historical = []
    matched = []
    for tier in campaign.GEOMETRY_TIERS:
        for seed in campaign.PAIRED_BASE_SEEDS:
            base = {
                "geometry_tier": tier,
                "rng_seed": seed,
                "responses": {name: 1.0 for name in review.RESPONSES},
            }
            historical.append({"public": copy.deepcopy(base)})
            matched.append({"public": copy.deepcopy(base)})
    valid = review.historical_boundary_cap_effect(historical, matched)
    assert valid["eligible"]
    assert valid["scope"] == "four paired derived decision responses only"
    assert valid["raw_array_or_byte_identity_evaluated"] is False
    assert valid["raw_array_or_byte_identity_claim"] == "none"
    assert valid["all_four_decision_responses_unchanged"]

    matched[0]["public"]["responses"][
        "worst_floor_to_each_lower_flux_ratio"
    ] = None
    invalid = review.historical_boundary_cap_effect(historical, matched)
    assert not invalid["eligible"]
    assert invalid["response_deltas"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["invalid_pairs"]
    json.dumps(invalid, allow_nan=False)


def test_malformed_and_nonfinite_attempt_rows_remain_visible_and_strict_json():
    data = manifest()
    cases = campaign.expand_cases(data, FAKE_FINGERPRINT)
    successes = [_attempt(case) for case in cases]
    malformed = {"rng_seed": "bad", "numerics": []}
    nonfinite = {"rng_seed": float("nan"), "numerics": {}}
    audit = review.audit_attempts(
        data,
        [*successes, malformed, nonfinite, []],
        [],
        False,
        FAKE_FINGERPRINT,
    )
    assert audit["status"] == "incomplete_or_invalid"
    assert len(audit["invalid_attempts"]) == 3
    assert audit["invalid_attempts"][1]["row"]["rng_seed"] == (
        "invalid_nonfinite"
    )
    json.dumps(audit, allow_nan=False)


def test_missing_rows_and_strict_json_fail_safely():
    data = manifest()
    summary = review.build_summary(
        data, [], [{"line": 1, "error": "truncated"}], True,
        FAKE_FINGERPRINT, ROOT
    )
    assert summary["status"] != "complete"
    assert summary["decision"]["classification"] == (
        "insufficient_audited_evidence"
    )
    encoded = json.dumps(summary, allow_nan=False)
    assert json.loads(encoded)["expected_case_count"] == 24


if __name__ == "__main__":
    test_clean_matrix_size_coupling_cap_and_no_reuse()
    test_confounded_16_cell_design_is_durably_rejected()
    test_target_analysis_and_authority_drift_fail_closed()
    test_historical_parent_is_verified_but_not_reused()
    test_resume_requires_success_and_matching_snapshot()
    test_attempt_retry_recovery_and_post_success_failure()
    test_reflection_convergence_uses_paired_tolerances_and_classes()
    test_empty_or_nonfinite_required_metrics_are_invalid_not_normal_misses()
    test_analytic_envelope_and_realized_kinematics_remain_visible_after_flux_miss()
    test_boundary_decisions_never_auto_authorize_downstream_work()
    test_multiresponse_paired_directions_report_each_response_not_only_flux()
    test_historical_cap_context_is_fail_closed_for_invalid_response()
    test_malformed_and_nonfinite_attempt_rows_remain_visible_and_strict_json()
    test_missing_rows_and_strict_json_fail_safely()
    print("Cu-fill lower-sticking boundary confirmation tests: PASS")

"""Guards for the frozen Cu transport numerical confirmation."""

from __future__ import annotations

import copy
import json
import math
import tempfile
from pathlib import Path

import foundation_copper_fill_transport_confirmation as campaign
import review_copper_fill_transport_confirmation as review


ROOT = Path(__file__).resolve().parent
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


def _origin(case, data):
    if campaign.is_parent_reuse_case(case, data):
        item = next(
            item
            for item in data["parent_reuse"]["rows"]
            if (item["geometry_tier"], item["rng_seed"])
            == campaign._reuse_key(case)
        )
        return {
            "mode": "verified_parent_reuse",
            "parent_case_id": item["parent_case_id"],
            "parent_row_canonical_sha256": item[
                "parent_row_canonical_sha256"
            ],
            "parent_rows_sha256": data["parent_reuse"]["source_rows_sha256"],
            "parent_snapshot_sha256": item["snapshot_sha256"],
        }
    return {
        "mode": "executed_confirmation",
        "reflection_residual_upper_bound": case[
            "reflection_residual_upper_bound"
        ],
    }


def _attempt(case, data, ok=True):
    return {
        **case,
        "ok": ok,
        "production_doe_eligible": False,
        "morphology_ranking_eligible": False,
        "evidence_origin": _origin(case, data),
        **({} if ok else {"error": "synthetic retry"}),
    }


def test_frozen_matrix_parent_map_and_reflection_bounds():
    data = manifest()
    cases = campaign.expand_cases(data, FAKE_FINGERPRINT)
    assert campaign.validate_manifest(data, cases) == []
    assert len(cases) == 128
    assert len({campaign._cell_key(case) for case in cases}) == 128
    reused = [case for case in cases if campaign.is_parent_reuse_case(case, data)]
    assert len(reused) == 8
    assert len(cases) - len(reused) == 120
    assert {case["design"] for case in cases} == set(campaign.DESIGN_NAMES)
    assert "stick_0p0125_power_0p0" in {case["design"] for case in cases}
    assert data["numerical_factorial"]["high_fidelity_cell"] == (
        campaign.HIGH_FIDELITY_CELL
    )
    for case in cases:
        sticking = case["model"]["suppressor_sticking_probability"]
        reflections = case["numerics"]["max_reflections"]
        assert math.isclose(
            case["reflection_residual_upper_bound"],
            (1.0 - sticking) ** reflections,
            rel_tol=0.0,
            abs_tol=1e-15,
        )


def test_target_drift_fails_manifest_validation():
    data = manifest()
    drifted = copy.deepcopy(data)
    drifted["target"]["max_balance_error"] = 1e-8
    errors = campaign.validate_manifest(drifted)
    assert any("target gates" in error for error in errors)

    extra_gate = copy.deepcopy(data)
    extra_gate["target"]["undeclared_relaxation"] = True
    errors = campaign.validate_manifest(extra_gate)
    assert any("target gates" in error for error in errors)


def test_parent_hashes_and_current_code_compatibility():
    data = manifest()
    parents, errors = campaign.load_verified_parent_rows(data, ROOT)
    assert errors == []
    assert len(parents) == 8
    for parent in parents.values():
        compatibility, errors = review._current_code_parent_compatibility(
            parent, ROOT
        )
        assert errors == []
        assert compatibility["compatible"]
        assert compatibility["topology_matches"]
        assert compatibility["transition_matches"]
        assert compatibility["protected_stack_matches"]
        assert compatibility["parent_traveler_metrics_sha256"] == (
            data["parent_reuse"]["traveler_metrics_compatibility"][
                "parent_sha256"
            ]
        )
        assert compatibility["current_traveler_metrics_sha256"] == (
            data["parent_reuse"]["traveler_metrics_compatibility"][
                "current_sha256"
            ]
        )


def test_parent_tamper_or_hash_drift_fails_closed():
    data = manifest()
    tampered = copy.deepcopy(data)
    tampered["parent_reuse"]["rows"][0][
        "parent_row_canonical_sha256"
    ] = "0" * 64
    _, errors = campaign.load_verified_parent_rows(tampered, ROOT)
    assert any("canonical hash mismatch" in error for error in errors)

    artifact_tamper = copy.deepcopy(data)
    artifact_tamper["parent_reuse"]["source_rows_sha256"] = "0" * 64
    _, errors = campaign.load_verified_parent_rows(artifact_tamper, ROOT)
    assert any("parent rows artifact hash mismatch" in error for error in errors)

    code_drift = copy.deepcopy(data)
    code_drift["parent_reuse"]["traveler_metrics_compatibility"][
        "current_sha256"
    ] = "0" * 64
    assert any(
        "compatibility contract" in error or "current traveler_metrics" in error
        for error in campaign.validate_manifest(code_drift)
    )


def test_reuse_is_materialized_once_and_never_executed():
    data = manifest()
    cases = campaign.expand_cases(data, FAKE_FINGERPRINT)
    reuse_case = next(
        case for case in cases if campaign.is_parent_reuse_case(case, data)
    )
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "rows.jsonl"
        first = campaign.materialize_parent_reuse(data, cases, output, ROOT)
        second = campaign.materialize_parent_reuse(data, cases, output, ROOT)
        assert len(first) == 8
        assert second == []
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        assert len(rows) == 8
        assert len({row["case_id"] for row in rows}) == 8
        assert all(
            row["evidence_origin"]["mode"] == "verified_parent_reuse"
            for row in rows
        )
        try:
            campaign.run_case((reuse_case, Path(temporary), data))
        except RuntimeError as error:
            assert "refusing to execute" in str(error)
        else:
            raise AssertionError("a parent reuse case was allowed to execute")


def test_retry_recovery_and_post_success_error_blocking():
    data = manifest()
    cases = campaign.expand_cases(data, FAKE_FINGERPRINT)
    successes = [_attempt(case, data) for case in cases]
    retry_case = next(
        case for case in cases if not campaign.is_parent_reuse_case(case, data)
    )
    error = _attempt(retry_case, data, ok=False)
    audit = review.audit_attempts(
        data, [error, *successes], [], False, FAKE_FINGERPRINT
    )
    assert audit["status"] == "complete"
    assert audit["resolved_current_error_attempt_rows"] == [error]
    assert audit["current_error_attempt_rows"] == []

    audit = review.audit_attempts(
        data, [*successes, error], [], False, FAKE_FINGERPRINT
    )
    assert audit["status"] == "incomplete_or_invalid"
    assert audit["current_error_attempt_rows"] == [error]


def _cell(design, grid, rays, reflections, classification="no_go", passed=False):
    return {
        "design": design,
        "grid_delta": grid,
        "rays_per_point": rays,
        "max_reflections": reflections,
        "high_fidelity": bool(
            grid == 0.005 and rays == 2000 and reflections == 800
        ),
        "classification": classification,
        "combined_2d_pass": passed,
        "response_summaries": {
            "worst_floor_to_each_lower_flux_ratio": {"worst": 1.0},
        },
        "tier_flux_response": {
            "continuity": {"worst": 1.0},
            "nominal_hbm": {"worst": 1.0},
        },
        "broad_analytic_envelope": {"coefficient_boundary_limited": False},
    }


def _all_cells():
    return [
        _cell(design, grid, rays, reflections)
        for design in campaign.DESIGN_NAMES
        for grid in campaign.GRID_LEVELS
        for rays in campaign.RAY_LEVELS
        for reflections in campaign.REFLECTION_LEVELS
    ]


def test_reflection_truncation_arm_and_coarse_pass_are_artifacts():
    data = manifest()
    truncated = copy.deepcopy(data)
    truncated["numerical_factorial"]["max_reflections"] = [400]
    errors = campaign.validate_manifest(truncated)
    assert any("reflection truncation arm" in error for error in errors)

    bad_bound = copy.deepcopy(data)
    bad_bound["reflection_residual_bounds"][
        "stick_0p0125_power_0p0"
    ]["800"] *= 2.0
    errors = campaign.validate_manifest(bad_bound)
    assert any("reflection residual bound" in error for error in errors)

    cells = _all_cells()
    b400 = next(
        cell
        for cell in cells
        if cell["design"] == "stick_0p0125_power_0p0"
        and cell["grid_delta"] == 0.005
        and cell["rays_per_point"] == 2000
        and cell["max_reflections"] == 400
    )
    b400.update({"combined_2d_pass": True, "classification": "pass"})
    artifacts = review.numerical_artifacts(cells)
    assert any(
        item["classification"] == "reflection_truncation_artifact"
        for item in artifacts
    )
    assert any(
        item["classification"] == "artifact_pending_high_fidelity_reproduction"
        for item in artifacts
    )


def _boundary_fixture(improvement, numerical_effect, b_pass=False):
    cells = _all_cells()
    high_a = next(
        cell
        for cell in cells
        if cell["design"] == campaign.DESIGN_NAMES[0]
        and cell["high_fidelity"]
    )
    high_b = next(
        cell
        for cell in cells
        if cell["design"] == campaign.DESIGN_NAMES[1]
        and cell["high_fidelity"]
    )
    high_a["response_summaries"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["worst"] = 1.0
    high_b["response_summaries"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["worst"] = 1.0 - improvement
    high_a["tier_flux_response"] = {
        "continuity": {"worst": 1.0},
        "nominal_hbm": {"worst": 1.1},
    }
    high_b["tier_flux_response"] = {
        "continuity": {"worst": 1.0 - improvement},
        "nominal_hbm": {"worst": 1.1 - improvement},
    }
    high_b["combined_2d_pass"] = b_pass
    high_b["classification"] = "pass" if b_pass else "no_go"
    effects = [{
        "design": campaign.DESIGN_NAMES[0],
        "response": "worst_floor_to_each_lower_flux_ratio",
        "worst_absolute_effect": numerical_effect,
    }]
    return cells, effects


def test_boundary_trigger_is_strict_and_never_auto_launches():
    cells, effects = _boundary_fixture(0.02, 0.02)
    evidence = review.boundary_expansion_evidence(cells, effects)
    assert not evidence["triggered"]
    assert not evidence["B_improvement_strictly_exceeds_numerical_effect"]

    cells, effects = _boundary_fixture(0.0200001, 0.02)
    evidence = review.boundary_expansion_evidence(cells, effects)
    assert evidence["triggered"]
    assert evidence["B_improves_in_both_tiers"]
    decision = review.decision_from_evidence(
        cells,
        effects,
        [],
        [],
        manifest()["boundary_expansion"]["conditional_design"],
    )
    assert decision["classification"] == (
        "lower_sticking_boundary_expansion_required"
    )
    assert decision["automatic_launch_authorized"] is False
    assert decision["conditional_next_design"]["max_reflections"] == [1600, 3200]
    assert decision["morphology_authorized"] is False
    assert decision["model_family_pivot_authorized"] is False

    cells, effects = _boundary_fixture(0.0, 0.02, b_pass=True)
    assert review.boundary_expansion_evidence(cells, effects)["triggered"]


def test_class_changing_interaction_forces_refinement():
    cells = _all_cells()
    target = next(
        cell
        for cell in cells
        if cell["design"] == campaign.DESIGN_NAMES[0]
        and cell["grid_delta"] == 0.005
        and cell["rays_per_point"] == 2000
        and cell["max_reflections"] == 800
    )
    target["classification"] = "pass"
    target["combined_2d_pass"] = True
    interactions = review.class_changing_interactions(cells)
    assert interactions
    decision = review.decision_from_evidence(
        cells,
        [],
        interactions,
        [],
        manifest()["boundary_expansion"]["conditional_design"],
    )
    assert decision["classification"] == (
        "numerical_interaction_inconclusive_refine"
    )
    assert decision["morphology_authorized"] is False


def test_paired_factorial_effects_recover_known_main_and_interaction():
    records = []
    for design in campaign.DESIGN_NAMES:
        for tier in campaign.GEOMETRY_TIERS:
            for seed in campaign.PAIRED_BASE_SEEDS:
                for grid in campaign.GRID_LEVELS:
                    for rays in campaign.RAY_LEVELS:
                        for reflections in campaign.REFLECTION_LEVELS:
                            public = {
                                "design": design,
                                "geometry_tier": tier,
                                "rng_seed": seed,
                                "grid_delta": grid,
                                "rays_per_point": rays,
                                "max_reflections": reflections,
                            }
                            g = review._factor_sign(public, "grid_refinement")
                            r = review._factor_sign(public, "ray_refinement")
                            f = review._factor_sign(public, "reflection_refinement")
                            value = 10.0 + 2.0 * g + 3.0 * r + 5.0 * f + 7.0 * g * r
                            public["responses"] = {
                                response: value for response in review.RESPONSES
                            }
                            records.append({"public": public})
    effects = review.paired_factorial_effects(records)
    primary = "worst_floor_to_each_lower_flux_ratio"
    grid = next(
        item for item in effects
        if item["design"] == campaign.DESIGN_NAMES[0]
        and item["response"] == primary
        and item["term"] == "grid_refinement"
    )
    interaction = next(
        item for item in effects
        if item["design"] == campaign.DESIGN_NAMES[0]
        and item["response"] == primary
        and item["term"] == "grid_refinement:ray_refinement"
    )
    assert grid["paired_stratum_count"] == 8
    assert math.isclose(grid["mean_signed_effect"], 4.0, abs_tol=1e-12)
    assert math.isclose(interaction["mean_signed_effect"], 14.0, abs_tol=1e-12)
    assert math.isclose(interaction["worst_absolute_effect"], 14.0, abs_tol=1e-12)


def test_missing_or_truncated_rows_and_strict_json_fail_safely():
    data = manifest()
    summary = review.build_summary(
        data, [], [{"line": 1, "error": "truncated"}], True,
        FAKE_FINGERPRINT, ROOT
    )
    assert summary["status"] != "complete"
    assert summary["decision"]["classification"] == (
        "insufficient_audited_evidence"
    )
    json.dumps(summary, allow_nan=False)
    assert review._json_number(math.inf) == "infinite"
    assert review._json_number(float("nan")) == "invalid_nonfinite"


def test_strict_json_output_contract_is_invoked():
    data = manifest()
    summary = review.build_summary(
        data, [], [], True, FAKE_FINGERPRINT, ROOT
    )
    encoded = json.dumps(summary, sort_keys=True, allow_nan=False)
    assert json.loads(encoded)["status"] == "missing_rows"
    try:
        json.dumps({"forbidden": float("nan")}, allow_nan=False)
    except ValueError:
        pass
    else:
        raise AssertionError("strict JSON unexpectedly accepted NaN")


if __name__ == "__main__":
    test_frozen_matrix_parent_map_and_reflection_bounds()
    test_target_drift_fails_manifest_validation()
    test_parent_hashes_and_current_code_compatibility()
    test_parent_tamper_or_hash_drift_fails_closed()
    test_reuse_is_materialized_once_and_never_executed()
    test_retry_recovery_and_post_success_error_blocking()
    test_reflection_truncation_arm_and_coarse_pass_are_artifacts()
    test_boundary_trigger_is_strict_and_never_auto_launches()
    test_class_changing_interaction_forces_refinement()
    test_paired_factorial_effects_recover_known_main_and_interaction()
    test_missing_or_truncated_rows_and_strict_json_fail_safely()
    test_strict_json_output_contract_is_invoked()
    print("Cu-fill transport numerical confirmation tests: PASS")

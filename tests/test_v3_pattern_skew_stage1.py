"""Focused guards for the V3 27-point pattern-geometry screen."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import tempfile

import build_v3_pattern_skew_stage1 as builder
import freeze_v3_pattern_skew_stage1_manifest as freezer
import review_v3_pattern_skew_stage1 as reviewer
import v3_pattern_skew_stage1_runner as runner


ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return freezer.build_manifest()


def test_design_is_complete_balanced_factorial():
    spec = builder.strict_load(ROOT / builder.DEFAULT_SPEC)
    design = builder.build_design(spec)
    assert design["logical_case_count"] == 27
    assert len(design["points"]) == 27
    assert len({builder.canonical_json(row["values"]) for row in design["points"]}) == 27
    for factor in builder.FACTOR_NAMES:
        assert {
            level: sum(row["levels"][factor] == level for row in design["points"])
            for level in builder.LEVEL_NAMES
        } == {"low": 9, "nominal": 9, "high": 9}
    assert design["numerics"]["grid_delta"] == 0.00125
    assert design["numerics"]["rays_per_point"] == 2000
    assert design["pattern_gate_policy"] == {
        "opening_cd_measurement": "raw mask intersection at surface y=0",
        "opening_cd_target": 0.3,
        "opening_cd_numerical_allowance_grid_cells": 1.0,
        "bottom_middle_top_cd_role": (
            "profile diagnostics sampled above the surface; not the "
            "surface-opening gate"
        ),
        "interpretation": (
            "the product target remains exactly 0.30; one grid cell is a "
            "numerical construction allowance, not a product tolerance"
        ),
    }
    assert design["authority"]["pattern_geometry_screening_only"] is True
    assert design["authority"]["confirmed_factor_authorized"] is False
    assert "dose" in " ".join(design["unsupported_claims"]).lower()
    assert "focus" in " ".join(design["unsupported_claims"]).lower()


def test_freezer_requires_exact_numerical_release_and_binds_hash():
    frozen = manifest()
    declaration = frozen["source_artifacts"]["numerical_release"]
    release_path = ROOT / declaration["path"]
    assert declaration["sha256"] == runner.file_sha256(release_path)
    assert runner.validate_manifest(frozen) == []
    with tempfile.TemporaryDirectory() as directory:
        missing = Path(directory) / "missing.json"
        try:
            freezer.build_manifest(missing)
        except ValueError as error:
            assert "release is missing" in str(error)
        else:
            raise AssertionError("freezer accepted a missing numerical release")
        rejected = json.loads(release_path.read_text())
        rejected["decision"]["rays_per_point"] = 1000
        path = Path(directory) / "rejected.json"
        path.write_text(json.dumps(rejected))
        try:
            freezer.build_manifest(path)
        except ValueError as error:
            assert "rays_per_point differs" in str(error)
        else:
            raise AssertionError("freezer accepted the rejected 1,000-ray setting")
        malformed = json.loads(release_path.read_text())
        del malformed["ray_bridge"]["metric_results"]["max_bow"][
            "observed_max_absolute_delta"
        ]
        assert any(
            "max_bow" in error
            for error in runner.validate_numerical_release(malformed)
        )
        wrong_types = json.loads(release_path.read_text())
        wrong_types["decision"]["pass"] = 1
        wrong_types["decision"]["authority"] = {
            name: int(value)
            for name, value in wrong_types["decision"]["authority"].items()
        }
        type_errors = runner.validate_numerical_release(wrong_types)
        assert any("pass differs" in error for error in type_errors)
        assert "numerical release authority differs" in type_errors
        fail_open = json.loads(release_path.read_text())
        fail_open["decision"]["pass"] = False
        fail_open["ray_bridge"]["all_rows_independently_valid"] = False
        fail_open["ray_bridge"]["no_hard_gate_flips"] = False
        release_errors = runner.validate_numerical_release(fail_open)
        assert any("pass differs" in error for error in release_errors)
        assert any("not independently valid" in error for error in release_errors)
        assert any("hard-gate flips" in error for error in release_errors)
        path = Path(directory) / "fail-open.json"
        path.write_text(json.dumps(fail_open))
        try:
            freezer.build_manifest(path)
        except ValueError as error:
            assert "release rejected" in str(error)
        else:
            raise AssertionError("freezer accepted a failed numerical release")


def test_frozen_manifest_check_rejects_missing_and_stale_files():
    frozen = manifest()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        try:
            freezer.check_frozen(path, frozen)
        except ValueError as error:
            assert "missing" in str(error)
        else:
            raise AssertionError("missing frozen manifest passed check")
        freezer.freeze(path, frozen)
        freezer.check_frozen(path, frozen)
        path.write_text(path.read_text() + " ")
        try:
            freezer.check_frozen(path, frozen)
        except ValueError as error:
            assert "stale or differs" in str(error)
        else:
            raise AssertionError("stale frozen manifest passed check")


def test_cases_share_exact_declared_nuisance_block():
    frozen = manifest()
    cases = runner.expand_cases(frozen)
    assert len(cases) == len({case["case_id"] for case in cases}) == 27
    assert {
        (
            case["rng_seed"],
            case["rng_stream"]["first_process_seed"],
            case["rng_stream"]["last_process_seed"],
            case["rng_stream"]["process_seed_horizon"],
        )
        for case in cases
    } == {(81000, 81000, 81042, 43)}
    assert all(
        case["rng_stream"]["same_interval_reused_across_all_pattern_cases"] is True
        and case["rng_stream"]["pointwise_common_random_numbers_claimed"] is False
        and case["rng_stream"]["independent_replicate"] is False
        and case["numerics"]["rays_per_point"] == 2000
        and case["numerics"]["threads_per_worker"] == 7
        and case["geometry"]["radius"]
        == case["pattern"]["input_geometry"]["opening_cd"] / 2.0
        for case in cases
    )
    fingerprint = frozen["runtime_fingerprint"]
    for name in (
        "python_version",
        "numpy_version",
        "numpy_proxy_sha256",
        "viennaps_proxy_sha256",
        "viennals_proxy_sha256",
        "viennaps_binary_sha256",
        "viennals_binary_sha256",
    ):
        assert fingerprint[name]


def test_campaign_lock_and_partial_execution_guard():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        descriptor, lock_path = runner.acquire_campaign_lock(output)
        assert lock_path.is_file()
        try:
            try:
                runner.acquire_campaign_lock(output)
            except RuntimeError as error:
                assert "another Stage 1 runner" in str(error)
            else:
                raise AssertionError("concurrent Stage 1 runner acquired the lock")
        finally:
            runner.release_campaign_lock(descriptor)
        descriptor, _ = runner.acquire_campaign_lock(output)
        runner.release_campaign_lock(descriptor)
        previous = Path.cwd()
        try:
            import os

            os.chdir(directory)
            assert runner.project_path(runner.DEFAULT_OUTPUT) == (
                ROOT / runner.DEFAULT_OUTPUT
            )
            rooted = runner.project_path(runner.DEFAULT_OUTPUT).with_suffix(
                runner.DEFAULT_OUTPUT.suffix + ".lock"
            )
            assert rooted == (ROOT / runner.DEFAULT_OUTPUT).with_suffix(
                runner.DEFAULT_OUTPUT.suffix + ".lock"
            )
        finally:
            os.chdir(previous)
    runner.validate_execution_options(limit=None, dry_run=False)
    runner.validate_execution_options(limit=3, dry_run=True)
    try:
        runner.validate_execution_options(limit=3, dry_run=False)
    except ValueError as error:
        assert "only with --dry-run" in str(error)
    else:
        raise AssertionError("partial scientific execution remained enabled")


def test_pattern_is_remeasured_from_geometry():
    case = next(
        case for case in runner.expand_cases(manifest())
        if set(case["pattern"]["levels"].values()) == {"nominal"}
    )
    measured, invalid = runner.measure_initial_pattern(case)
    assert invalid == []
    assert measured["opening_valid"] is True
    assert measured["geometry_kind"] == "full"
    assert abs(measured["opening_cd_surface"] - 0.30) <= 0.00125
    assert measured["opening_cd_bottom"] != case["pattern"]["input_geometry"]["opening_cd"]
    assert measured["mask_height"] != case["pattern"]["input_geometry"]["mask_height"]


def test_surface_cd_gate_passes_nominal_and_rejects_low_high_for_all_tapers():
    cases = runner.expand_cases(manifest())
    for case in cases:
        initial, invalid = runner.measure_initial_pattern(case)
        assert invalid == []
        measured = {
            "etch": {
                "depth": 1.25,
                "max_cd_error": 0.0,
                "max_bow": 0.0,
            },
            "mask_remaining_height": 0.30,
            "post_etch_mask": {"opening_valid": True},
        }
        gates = runner.classify_gates(initial, measured, case)
        expected = case["pattern"]["levels"]["opening_cd"] == "nominal"
        assert gates["pattern_width"] is expected


def test_resume_rejects_duplicate_success_and_stale_payload():
    cases = runner.expand_cases(manifest())
    case = cases[0]
    row = {**case, "ok": True, "evidence_origin": runner.evidence_origin()}
    original = runner.validate_success_row
    runner.validate_success_row = lambda *_args, **_kwargs: []
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_text(json.dumps(row) + "\n")
            successes, attempts, failures = runner.audit_existing_rows(path, cases)
            assert set(successes) == {case["case_id"]}
            assert attempts == 1
            assert failures == []
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")
            try:
                runner.audit_existing_rows(path, cases)
            except ValueError as error:
                assert "attempt follows success" in str(error)
            else:
                raise AssertionError("duplicate success remained resumable")
            stale = copy.deepcopy(row)
            stale["numerics"]["rays_per_point"] = 1000
            path.write_text(json.dumps(stale) + "\n")
            try:
                runner.audit_existing_rows(path, cases)
            except ValueError as error:
                assert "stale case payload" in str(error)
            else:
                raise AssertionError("stale row remained resumable")
    finally:
        runner.validate_success_row = original


def _synthetic_rows(frozen):
    rows = []
    for case in runner.expand_cases(frozen):
        values = case["pattern"]["input_geometry"]
        cd = values["opening_cd"]
        height = values["mask_height"]
        taper = values["mask_taper"]
        cd_code = {"low": -1.0, "nominal": 0.0, "high": 1.0}[
            case["pattern"]["levels"]["opening_cd"]
        ]
        taper_code = {"low": -1.0, "nominal": 0.0, "high": 1.0}[
            case["pattern"]["levels"]["mask_taper"]
        ]
        nominal_cd_height_interaction = 0.008 * (
            case["pattern"]["levels"]["opening_cd"] == "nominal"
            and case["pattern"]["levels"]["mask_height"] == "nominal"
        )
        gates = {
            "pattern_width": abs(cd - 0.30) <= 0.00125,
            "pattern_height": abs(height - 0.30) <= 0.00125,
            "pattern_opening": True,
            "etch_depth": True,
            "etch_cd_profile": True,
            "etch_bow": True,
            "etch_mask_resolved": True,
        }
        gates["pattern_pass"] = all(
            gates[name] for name in ("pattern_width", "pattern_height", "pattern_opening")
        )
        gates["etch_pass"] = all(
            gates[name]
            for name in ("etch_depth", "etch_cd_profile", "etch_bow", "etch_mask_resolved")
        )
        rows.append({
            **case,
            "initial_pattern": {
                "opening_cd_surface": cd,
                "opening_cd_bottom": cd + 0.001,
                "opening_cd_middle": cd + 0.002 + 0.0002 * taper,
                "opening_cd_top": cd + 0.003 + 0.0004 * taper,
                "mask_height": height - 0.0001,
                "opening_center_shift": 0.0,
                "mask_sidewall_angle_deg": taper,
            },
            "selected_cycle_metrics": {
                "etch": {
                    "depth": 1.25 + 0.10 * (cd - 0.30),
                    "cd_top": cd + 0.004 * taper,
                    "cd_middle": cd + 0.002 * taper,
                    "cd_bottom": cd - 0.001 * taper,
                    "max_cd_error": abs(cd - 0.30) + 0.002 * abs(taper),
                    "sidewall_angle_deg": 0.5 * taper,
                    "max_bow": 0.010 + 0.008 * cd_code * taper_code,
                    "scallop_rms": (
                        0.003
                        + 0.0001 * abs(taper)
                        + nominal_cd_height_interaction
                    ),
                },
                "mask_remaining_height": height - 0.001,
            },
            "selected_cycle": 12,
            "target_depth_crossing": {
                "status": "bracketed",
                "interpolated_cycle": 12.0 - cd_code - 0.25 * taper_code,
                "lower_cycle": 11,
                "upper_cycle": 12,
                "lower_depth": 1.20,
                "upper_depth": 1.26,
                "authority": "descriptive_depth_rate_hypothesis_only",
            },
            "rng_consumption": {
                "actual_process_seed_count": 37,
                "actual_last_process_seed": 81036,
                "declared_maximum_process_seed_count": 43,
                "declared_maximum_last_process_seed": 81042,
                "early_stop_shortened_stream": True,
            },
            "selection_eligible": True,
            "gates": gates,
            "hard_gate_pass": gates["pattern_pass"] and gates["etch_pass"],
            "checkpoint_path": f"synthetic/{case['case_id']}.vpsd",
            "checkpoint_sha256": "0" * 64,
        })
    return rows


def test_review_separates_design_correlation_effects_and_confirmation():
    frozen = manifest()
    summary = reviewer.review(frozen, _synthetic_rows(frozen), attempt_count=27)
    assert summary["status"] == "complete"
    assert summary["design_independence"]["maximum_absolute_off_diagonal_correlation"] < 1e-12
    assert summary["direct_screen_effects"]["opening_cd"]["etch_cd_top"][
        "exceeds_effective_screen_threshold"
    ] is True
    assert summary["effective_screen_thresholds"]["etch_depth"][
        "effective_screen_threshold"
    ] == 0.051056695133322005
    assert summary["effective_screen_thresholds"]["etch_cd_bottom"][
        "effective_screen_threshold"
    ] == 0.015617701745986146
    assert summary["effective_screen_thresholds"]["etch_max_bow"][
        "effective_screen_threshold"
    ] == 0.006730895804307968
    assert summary["effective_screen_thresholds"]["etch_cd_top"][
        "effective_screen_threshold"
    ] == 0.012
    assert summary["effective_screen_thresholds"]["etch_depth"][
        "three_times_paired_stochastic_sd"
    ] is None
    interaction = summary["interaction_hypothesis_screens"][
        "opening_cd__x__mask_taper"
    ]["etch_max_bow"]
    assert math.isclose(
        interaction["low_high_difference_of_differences"], 0.032
    )
    assert interaction["exceeds_effective_screen_threshold"] is True
    assert "etch_max_bow" in summary["confirmation_candidates"]["interactions"][
        "opening_cd__x__mask_taper"
    ]
    nominal_interaction = summary["interaction_hypothesis_screens"][
        "opening_cd__x__mask_height"
    ]["etch_scallop_rms"]
    assert math.isclose(
        nominal_interaction["low_high_difference_of_differences"], 0.0,
        abs_tol=1e-12,
    )
    assert nominal_interaction["three_by_three_residual_span"] > 0.0025
    assert nominal_interaction["exceeds_effective_screen_threshold"] is True
    taper_curvature = summary["direct_screen_effects"]["mask_taper"][
        "etch_sidewall_angle_deg"
    ]["nominal_minus_linear_edge_interpolation"]
    assert math.isclose(taper_curvature, 0.0, abs_tol=1e-12)
    assert summary["knob_output_correlations"]["opening_cd"]["etch_cd_top"]["pearson"] > 0.9
    assert summary["failure_visibility"]["hard_gate_failure_count"] == 24
    assert summary["decision"]["confirmed_factors"] == []
    assert summary["decision"]["classification"] == (
        "screen_complete_requires_disjoint_confirmation"
    )
    assert summary["rng_interpretation"]["stochastic_variance_estimated"] is False
    assert summary["target_depth_crossing"]["bracketed_count"] == 27
    assert summary["target_depth_crossing"]["censored_count"] == 0
    assert summary["rng_consumption"]["actual_last_process_seed_range"] == [
        81036, 81036
    ]
    assert summary["authority"]["recipe_authorized"] is False


def test_target_depth_crossing_interpolates_or_censors():
    history = [
        {"cycle": 0, "depth": 0.2, "metrics_valid": True},
        {"cycle": 1, "depth": 1.2, "metrics_valid": True},
        {"cycle": 2, "depth": 1.3, "metrics_valid": True},
    ]
    crossing = runner.target_depth_crossing(history, 1.25)
    assert crossing["status"] == "bracketed"
    assert math.isclose(crossing["interpolated_cycle"], 1.5)
    shallow = runner.target_depth_crossing(history[:2], 1.25)
    assert shallow["status"] == "right_censored_shallow_at_cycle_horizon"
    assert shallow["interpolated_cycle"] is None


def test_empty_interim_review_is_valid_and_non_authoritative():
    summary = reviewer.review(manifest(), [], attempt_count=0)
    json.dumps(summary, allow_nan=False)
    assert summary["status"] == "incomplete"
    assert summary["target_depth_crossing"]["all_cases_bracket_target"] is False
    assert summary["decision"]["classification"] == (
        "screen_incomplete_no_effect_decision"
    )


def test_runner_threads_and_bounded_immediate_completion_contract():
    source = (ROOT / "v3_pattern_skew_stage1_runner.py").read_text()
    assert source.index('os.environ["OMP_NUM_THREADS"]') < source.index("import viennaps as ps")
    assert "r1.run_case(task)" in source
    assert "ps.setDimension(2)" in source
    assert "ps.setNumThreads(int(case[\"numerics\"][\"threads_per_worker\"]))" in (
        ROOT / "foundation_pattern_bosch_gate0_r1.py"
    ).read_text()
    assert "executor.submit" in source
    assert "futures.as_completed" in source
    assert "executor.map" not in source
    assert "gate0.append_row(args.output, row)" in source
    assert 'parser.add_argument("--dry-run", action="store_true")' in source


if __name__ == "__main__":
    test_design_is_complete_balanced_factorial()
    test_freezer_requires_exact_numerical_release_and_binds_hash()
    test_frozen_manifest_check_rejects_missing_and_stale_files()
    test_cases_share_exact_declared_nuisance_block()
    test_campaign_lock_and_partial_execution_guard()
    test_pattern_is_remeasured_from_geometry()
    test_surface_cd_gate_passes_nominal_and_rejects_low_high_for_all_tapers()
    test_resume_rejects_duplicate_success_and_stale_payload()
    test_review_separates_design_correlation_effects_and_confirmation()
    test_target_depth_crossing_interpolates_or_censors()
    test_empty_interim_review_is_valid_and_non_authoritative()
    test_runner_threads_and_bounded_immediate_completion_contract()
    print("V3 pattern-skew Stage 1 guards: PASS")

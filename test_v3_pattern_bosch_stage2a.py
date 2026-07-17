"""Focused methodology guards for V3 Stage 2a."""

from __future__ import annotations

import copy
from functools import lru_cache
import os
from pathlib import Path
import tempfile

import build_v3_pattern_bosch_stage2a as builder
import freeze_v3_pattern_bosch_stage2a_manifest as freezer
import review_v3_pattern_bosch_stage2a as reviewer
import v3_pattern_bosch_stage2a_runner as runner


@lru_cache(maxsize=1)
def manifest():
    return freezer.build_manifest()


def test_design_is_broad_exact_and_independent():
    current = manifest()
    design = current["design"]
    assert design["design"]["recipe_count"] == 96
    assert design["design"]["exact_anchor_count"] == 50
    assert design["design"]["space_filling_interior_count"] == 46
    assert len({row["recipe_id"] for row in design["recipes"]}) == 96
    assert len({builder.common.canonical_json(row["recipe"]) for row in design["recipes"]}) == 96
    preflight = design["design"]["input_independence_preflight"]
    assert preflight["maximum_absolute_pearson"] < 0.15
    assert preflight["maximum_absolute_spearman"] < 0.15
    assert preflight["maximum_vif"] < 1.5
    reasons = {
        reason for row in design["recipes"] for reason in row["anchor_reasons"]
    }
    for name in builder.EXPECTED_FACTOR_NAMES:
        assert f"ofat:{name}:low" in reasons
        assert f"ofat:{name}:high" in reasons
    for first, second in builder.EXPECTED_INTERACTIONS:
        for first_level in ("low", "high"):
            for second_level in ("low", "high"):
                assert (
                    f"interaction:{first}:{second}:{first_level}:{second_level}"
                    in reasons
                )
    assert ("etch_time", "ion_rate") == builder.EXPECTED_INTERACTIONS[0]
    nominal_etch = next(
        factor for factor in design["factors"] if factor["name"] == "etch_time"
    )
    assert builder.to_unit(nominal_etch, nominal_etch["nominal"]) != 0.5


def test_cases_use_nominal_pattern_2000_rays_and_disjoint_intervals():
    cases = runner.expand_cases(manifest())
    assert len(cases) == 96
    intervals = []
    for case in cases:
        assert case["geometry"]["radius"] == 0.15
        assert case["geometry"]["mask_height"] == 0.3
        assert case["recipe"]["mask_taper"] == 2.0
        assert case["recipe"]["mask_ion_rate"] == 0.0
        assert case["numerics"]["grid_delta"] == 0.00125
        assert case["numerics"]["rays_per_point"] == 2000
        assert case["numerics"]["simulation_dimension"] == 2
        assert case["trajectory"]["maximum_cycles"] == 30
        intervals.append((
            case["rng_stream"]["first_process_seed"],
            case["rng_stream"]["last_process_seed"],
        ))
    assert not runner.rng_interval_errors(cases)
    assert intervals[0] == (820000, 820090)
    assert all(first > 81042 for first, _ in intervals)
    assert all(left[1] < right[0] for left, right in zip(intervals, intervals[1:]))
    assert cases[0]["rng_stream"]["reserved_prior_v3_intervals"][-1] == {
        "campaign": "v3_pattern_skew_stage1",
        "first": 81000,
        "last": 81042,
    }


def test_numerical_release_is_hashed_and_effective_thresholds_are_not_practical_only():
    current = manifest()
    declaration = current["source_artifacts"]["v3_numerical_release"]
    assert declaration["path"] == str(runner.DEFAULT_NUMERICAL_RELEASE)
    assert declaration["sha256"] == runner.file_sha256(runner.DEFAULT_NUMERICAL_RELEASE)
    thresholds = current["effective_screen_thresholds"]
    assert thresholds["etch_depth"]["effective_threshold"] == 0.1285326689594815
    assert thresholds["etch_cd_bottom"]["effective_threshold"] == 0.03624901507016212
    assert thresholds["etch_max_bow"]["effective_threshold"] == 0.013919582759196367
    assert thresholds["etch_cd_taper_top_minus_bottom"]["effective_threshold"] == 0.039902894866825696
    assert thresholds["etch_cd_span"]["effective_threshold"] == 0.03123540349197229
    assert all(
        row["paired_stochastic_term"] is None
        and row["independent_stochastic_contrast_term"] is not None
        and row["stochastic_baseline_replicates"] == 4
        and row["paired_stochastic_status"] == "unavailable_for_independent_recipe_streams"
        and row["authority"] == "hypothesis_screening_only"
        for row in thresholds.values()
    )
    assert "v3_pattern_stage1" not in current["source_artifacts"]
    fingerprint = current["runtime_fingerprint"]
    for name in (
        "python_version",
        "python_executable_sha256",
        "numpy_version",
        "numpy_proxy_sha256",
        "viennaps_version",
        "viennaps_proxy_sha256",
        "viennals_proxy_sha256",
        "viennaps_binary_sha256",
        "viennals_binary_sha256",
    ):
        assert fingerprint[name]
    assert fingerprint["simulation_dimension"] == 2


def test_threshold_and_release_tampering_fail_closed():
    current = copy.deepcopy(manifest())
    current["effective_screen_thresholds"]["etch_depth"]["effective_threshold"] = 0.02
    errors = runner.validate_manifest(current, check_runtime=False)
    assert any("effective screen thresholds differ" in error for error in errors)
    release = builder.common.strict_load(runner.DEFAULT_NUMERICAL_RELEASE)
    release["decision"]["rays_per_point"] = 1000
    errors = runner.validate_numerical_release(release)
    assert any("rays_per_point differs" in error for error in errors)
    release = builder.common.strict_load(runner.DEFAULT_NUMERICAL_RELEASE)
    release["ray_bridge"]["pairs"][0]["deltas_2000_minus_1000"]["depth"] = None
    errors = runner.validate_numerical_release(release)
    assert any("pair metric deltas are invalid" in error for error in errors)


def test_mask_erosion_and_cycle_count_are_visible_deferred_controls():
    exclusions = {row["name"]: row for row in manifest()["design"]["excluded_wired_controls"]}
    assert set(exclusions) == {"mask_ion_rate", "num_cycles"}
    assert exclusions["mask_ion_rate"]["held_value"] == 0.0
    assert "boundary-limited" in exclusions["mask_ion_rate"]["evidence_status"]
    assert "Stage 2c" in exclusions["num_cycles"]["required_followup"]


def test_target_depth_crossing_is_interpolated_and_censoring_stays_visible():
    base = {
        "target": {"etch_depth": 1.25},
        "recipe": {"etch_time": 0.5, "initial_etch_time": 0.3},
    }
    bracketed = {
        **base,
        "cycle_history": [
            {"cycle": 0, "depth": 0.1},
            {"cycle": 1, "depth": 0.9},
            {"cycle": 2, "depth": 1.4},
        ],
    }
    crossing = reviewer.target_depth_crossing(bracketed)
    assert crossing["status"] == "interpolated_bracketed_crossing"
    assert abs(crossing["crossing_cycle"] - 1.7) < 1e-12
    assert abs(crossing["model_phase_duration"] - 4.55) < 1e-12
    right = reviewer.target_depth_crossing({
        **base,
        "cycle_history": [
            {"cycle": 0, "depth": 0.1},
            {"cycle": 1, "depth": 0.5},
        ],
    })
    assert right["status"] == "right_censored_after_last_checkpoint"
    assert right["crossing_cycle"] is None
    assert right["bound_cycle"] == 1.0
    left = reviewer.target_depth_crossing({
        **base,
        "cycle_history": [{"cycle": 0, "depth": 1.3}],
    })
    assert left["status"] == "left_censored_before_or_at_first_checkpoint"
    assert left["crossing_cycle"] is None


def test_output_lock_and_full_campaign_only_cli():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "stage2a.jsonl"
        descriptor, path = runner.acquire_campaign_lock(
            output, "v3-pattern-bosch-stage2a"
        )
        try:
            assert path.is_file()
            try:
                runner.acquire_campaign_lock(output, "v3-pattern-bosch-stage2a")
            except RuntimeError as error:
                assert "another Stage 2a runner" in str(error)
            else:
                raise AssertionError("second Stage 2a runner acquired the output lock")
        finally:
            runner.release_campaign_lock(descriptor)
    source = Path(runner.__file__).read_text()
    assert 'add_argument("--limit"' not in source


def test_campaign_paths_are_repo_rooted_from_another_cwd():
    original = Path.cwd()
    with tempfile.TemporaryDirectory() as directory:
        os.chdir(directory)
        try:
            assert runner.project_path(runner.DEFAULT_MANIFEST) == (
                runner.ROOT / runner.DEFAULT_MANIFEST
            ).resolve()
            output = runner.project_path(runner.DEFAULT_OUTPUT)
            assert output == (runner.ROOT / runner.DEFAULT_OUTPUT).resolve()
            checkpoint = runner.r1.checkpoint_path(output, "case", 3)
            assert runner.ROOT.resolve() in checkpoint.resolve().parents
            assert Path(directory).resolve() not in checkpoint.resolve().parents
            descriptor, lock = runner.acquire_campaign_lock(
                output, "v3-pattern-bosch-stage2a"
            )
            try:
                assert runner.ROOT.resolve() in lock.resolve().parents
            finally:
                runner.release_campaign_lock(descriptor)
                lock.unlink(missing_ok=True)
        finally:
            os.chdir(original)


def _synthetic_measured(depth=0.05):
    return {
        "etch": {
            "depth": depth,
            "cd_top": 0.30,
            "cd_middle": 0.30,
            "cd_bottom": 0.30,
            "cd_min": 0.30,
            "cd_max": 0.30,
            "max_cd_error": 0.0,
            "max_bow": 0.0,
            "scallop_rms": 0.0,
            "sidewall_angle_deg": 0.0,
            "sample_cds": [0.30],
            "sample_fractions": [0.5],
        },
        "mask_remaining_height": 0.30,
        "post_etch_mask": {"opening_valid": True},
    }


def test_underetch_and_invalid_metrics_are_scientific_rows_not_executor_crashes():
    case = runner.expand_cases(manifest())[0]
    original_bosch = runner.tp.bosch_etch
    original_measure = runner.r1._measure_domain
    try:
        def underetch(geometry, *, num_cycles, on_cycle, **kwargs):
            for cycle in range(num_cycles + 1):
                on_cycle(geometry, cycle)
            raise AssertionError("etch barely moved: depth=-0.05")

        runner.tp.bosch_etch = underetch
        runner.r1._measure_domain = lambda geometry, current: (
            _synthetic_measured(), []
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rows.jsonl"
            row = runner.run_case((case, output))
            assert row["ok"] is True
            assert row["simulation_completed"] is True
            assert row["metrics_valid"] is True
            assert row["hard_gate_pass"] is False
            assert row["trajectory_classification"] == (
                "shallow_at_cycle_horizon_boundary_limited"
            )
            assert row["underetch_assertion_intercepted"].startswith(
                "etch barely moved:"
            )
            assert row["rng_consumption"]["actual_process_seed_count"] == 91
            assert not runner.validate_success_row(row, case, output)

        def invalid_metrics(geometry, *, on_cycle, **kwargs):
            on_cycle(geometry, 0)
            on_cycle(geometry, 1)

        runner.tp.bosch_etch = invalid_metrics
        runner.r1._measure_domain = lambda geometry, current: (_ for _ in ()).throw(
            ValueError("controlled metric failure")
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rows.jsonl"
            row = runner.run_case((case, output))
            assert row["ok"] is True
            assert row["simulation_completed"] is True
            assert row["metrics_valid"] is False
            assert row["hard_gate_pass"] is False
            assert row["selection_eligible"] is False
            assert row["trajectory_classification"] == "invalid_metrics_failure_boundary"
            assert "no_valid_depth_matched_metric_checkpoint" in row[
                "scientific_invalid_reasons"
            ]
            assert row["checkpoint_path"].endswith(".vpsd")
            assert not runner.validate_success_row(row, case, output)
            reviewed = reviewer.review_case(row, case, output)
            assert reviewed["valid"] is True
            assert reviewed["metrics_valid"] is False
    finally:
        runner.tp.bosch_etch = original_bosch
        runner.r1._measure_domain = original_measure


def synthetic_reviewed_rows():
    rows = []
    for case in runner.expand_cases(manifest()):
        coordinates = case["normalized_coordinates"]
        etch = 2.0 * coordinates["etch_time"] - 1.0
        ion = 2.0 * coordinates["ion_rate"] - 1.0
        depth = 1.25 + 0.20 * etch + 0.10 * ion + 0.16 * etch * ion
        metrics = {name: None for name in reviewer.RESPONSE_METRICS}
        metrics["etch_depth"] = depth
        rows.append({
            "case_id": case["case_id"],
            "recipe_id": case["recipe_id"],
            "design_class": case["design_class"],
            "anchor_reasons": case["anchor_reasons"],
            "valid": True,
            "errors": [],
            "simulation_completed": True,
            "metrics_valid": True,
            "scientific_invalid_reasons": [],
            "hard_gate_pass": True,
            "selection_eligible": True,
            "depth_matched_to_spec": True,
            "depth_horizon_censored": False,
            "trajectory_classification": "depth_selected",
            "target_depth_crossing": {"status": "interpolated_bracketed_crossing"},
            "metrics": metrics,
            "gates": {name: True for name in reviewer.GATE_NAMES},
            "normalized_coordinates": coordinates,
            "recipe": case["recipe"],
        })
    return rows


def test_reviewer_separates_correlations_models_and_unconfirmed_hypotheses():
    current = manifest()
    reviewed = synthetic_reviewed_rows()
    correlations = reviewer.knob_output_correlations(
        reviewed, list(builder.EXPECTED_FACTOR_NAMES)
    )
    assert correlations["etch_depth"]["etch_time"][
        "pearson_transformed_input_to_output"
    ] is not None
    assert correlations["etch_depth"]["etch_time"][
        "spearman_input_to_output"
    ] is not None
    ofat = reviewer.exact_ofat_effects(
        reviewed, current, list(builder.EXPECTED_FACTOR_NAMES)
    )
    assert ofat["etch_depth"]["factor_effects"]["etch_time"][
        "evidence_status"
    ] == "unconfirmed_independent_stream_contrast"
    models = reviewer.grouped_holdout_models(reviewed, current)
    assert models["etch_depth"]["status"] == "fit"
    assert models["etch_depth"]["hypothesis_model_adequate"] is True
    assert models["etch_depth"]["modeled_factor_effects"]["etch_time"][
        "absolute_effect_over_effective_threshold"
    ] > 1.0
    interactions = reviewer.exact_interaction_contrasts(reviewed, current)
    assert interactions["etch_time:ion_rate"]["metrics"]["etch_depth"][
        "evidence_status"
    ] == "unconfirmed_exact_2x2_independent_stream_contrast"
    boundaries = reviewer.failure_boundaries(
        reviewed, list(builder.EXPECTED_FACTOR_NAMES)
    )
    hypotheses = reviewer.hypothesis_register(
        reviewed, current, models, ofat, interactions, boundaries
    )
    assert hypotheses
    assert all(row["status"] == "hypothesis_not_confirmed" for row in hypotheses)
    assert current["authority"]["confirmed_factor_authorized"] is False
    assert current["authority"]["recipe_authorized"] is False
    miss = copy.deepcopy(reviewed[0])
    miss["metrics"]["etch_cd_top"] = 0.31
    miss["depth_matched_to_spec"] = False
    assert reviewer.metric_rows([miss], "etch_cd_top") == []


if __name__ == "__main__":
    test_design_is_broad_exact_and_independent()
    test_cases_use_nominal_pattern_2000_rays_and_disjoint_intervals()
    test_numerical_release_is_hashed_and_effective_thresholds_are_not_practical_only()
    test_threshold_and_release_tampering_fail_closed()
    test_mask_erosion_and_cycle_count_are_visible_deferred_controls()
    test_target_depth_crossing_is_interpolated_and_censoring_stays_visible()
    test_output_lock_and_full_campaign_only_cli()
    test_campaign_paths_are_repo_rooted_from_another_cwd()
    test_underetch_and_invalid_metrics_are_scientific_rows_not_executor_crashes()
    test_reviewer_separates_correlations_models_and_unconfirmed_hypotheses()
    print("V3 Pattern/Bosch Stage 2a tests: PASS")

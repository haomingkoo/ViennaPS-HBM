"""Focused guards for broad-first Bosch discovery."""

import copy
from collections import Counter

import build_pattern_bosch_discovery_s1 as builder
import pattern_bosch_discovery_s1_runner as runner
import review_pattern_bosch_discovery_s1 as review


def manifest():
    spec = builder.common.strict_load(builder.DEFAULT_SPEC)
    design = builder.build_design(spec)
    return {
        "manifest_version": 1,
        "campaign": "pattern-bosch-discovery-s1",
        "labels": ["full-traveler", "critical-review"],
        "design": design,
        "execution": {
            "output": str(runner.DEFAULT_OUTPUT),
            "maximum_workers": 2,
            "threads_per_worker": 7,
            "executor": "direct_checkpointed_batch_no_llm",
        },
        "runtime_fingerprint": runner.runtime_fingerprint(),
        "source_artifacts": {
            "gate0_r1_summary": {"path": "r1.json", "sha256": "a" * 64}
        },
        "authority": design["authority"],
        "provenance": {
            "executor": "direct_checkpointed_batch_no_llm",
            "metric_module": "traveler_metrics.py",
            "native_checkpoint": "ViennaPS .vpsd",
            "design_role": "broad factor discovery, not optimization",
        },
    }


def test_design_is_deterministic_wide_and_not_authoritative():
    spec = builder.common.strict_load(builder.DEFAULT_SPEC)
    first = builder.build_design(spec)
    assert first == builder.build_design(spec)
    assert builder.validate_design(first, spec) == []
    assert first["design"]["recipe_count"] == 96
    assert first["design"]["anchor_count"] == 23
    assert first["design"]["latin_hypercube_count"] == 73
    assert first["design"]["logical_simulation_count"] == 232
    assert len(first["predeclared_interactions"]) == 6
    assert not first["authority"]["recipe_authorized"]
    assert not first["authority"]["process_window_authorized"]


def test_factor_transforms_cover_exact_endpoints():
    spec = builder.common.strict_load(builder.DEFAULT_SPEC)
    by_name = {factor["name"]: factor for factor in spec["factors"]}
    for name, factor in by_name.items():
        assert builder.from_unit(factor, 0.0) == factor["low"]
        assert builder.from_unit(factor, 1.0) == factor["high"]
        assert abs(builder.to_unit(factor, factor["low"])) < 1e-12
        assert abs(builder.to_unit(factor, factor["high"]) - 1.0) < 1e-12
    assert by_name["neutral_rate"]["scale"] == "signed_log_magnitude"
    assert by_name["ion_rate"]["scale"] == "signed_log_magnitude"
    assert by_name["etch_time"]["scale"] == "log"
    assert by_name["deposition_thickness"]["scale"] == "log"
    assert all(factor["range_basis"].strip() for factor in spec["factors"])
    assert (by_name["etch_time"]["low"], by_name["etch_time"]["high"]) == (
        0.2, 2.0
    )
    assert by_name["neutral_rate"]["low"] == -0.2
    assert by_name["deposition_thickness"]["high"] == 0.04
    assert by_name["ion_source_exponent"]["low"] == 50


def test_exact_232_case_matrix_and_sentinel_roles():
    frozen = manifest()
    errors = runner.validate_manifest(
        frozen, check_runtime=True, check_prerequisite=False
    )
    assert errors == [
        "superseded Bosch-only S1 methodology; follow RESEARCH_PLAN_V3.md"
    ]
    cases = runner.expand_cases(frozen)
    assert len(cases) == len({case["case_id"] for case in cases}) == 232
    assert Counter(case["case_role"] for case in cases) == {
        "base_discovery": 192,
        "sentinel_noise": 24,
        "sentinel_fidelity": 16,
    }
    assert all(case["rng_stream"]["process_seed_horizon"] == 91 for case in cases)
    assert all(
        not case["rng_stream"]["same_base_labels_reused_across_recipes"]
        for case in cases
    )
    assert runner.rng_interval_errors(cases) == []
    intervals = Counter(
        (
            case["rng_stream"]["first_process_seed"],
            case["rng_stream"]["last_process_seed"],
        )
        for case in cases
    )
    assert Counter(intervals.values()) == {1: 200, 2: 16}
    assert all(case["geometry"]["radius"] == 0.15 for case in cases)
    assert all(case["geometry"]["mask_height"] == 0.3 for case in cases)
    assert all(case["recipe"]["mask_taper"] == 2.0 for case in cases)
    assert all(case["recipe"]["mask_ion_rate"] == 0.0 for case in cases)
    assert sum(case["numerics"]["rays_per_point"] == 2000 for case in cases) == 16


def test_rng_overlap_guard_allows_only_declared_fidelity_pair():
    cases = runner.expand_cases(manifest())
    changed = copy.deepcopy(cases)
    changed[2]["rng_seed"] = changed[0]["rng_seed"]
    changed[2]["rng_stream"]["first_process_seed"] = changed[0]["rng_seed"]
    changed[2]["rng_stream"]["last_process_seed"] = (
        changed[0]["rng_stream"]["last_process_seed"]
    )
    assert runner.rng_interval_errors(changed)


def test_historical_depth_matched_failure_is_an_exact_anchor():
    design = manifest()["design"]
    failures = [
        row for row in design["recipes"]
        if "prior:legacy_depth_matched_failure" in row["anchor_reasons"]
    ]
    assert len(failures) == 1
    assert failures[0]["recipe"] == {
        "etch_time": 2.0,
        "initial_etch_time": 0.3,
        "neutral_rate": -0.2,
        "neutral_sticking_probability": 0.02,
        "deposition_thickness": 0.04,
        "deposition_sticking_probability": 0.01,
        "ion_source_exponent": 50,
        "theta_r_min": 60.0,
        "ion_rate": -0.1,
    }


def test_r1_prerequisite_uses_ray_and_native_evidence_not_mask_search():
    seeds = list(runner.r1.EXPECTED_SEEDS)
    summary = {
        "ray_bridge": {
            "pass": True,
            "pairs": [{"rng_seed": seed} for seed in seeds],
        },
        "reviewed_cases": [
            {
                "arm": runner.r1.REFERENCE_ARM,
                "rng_seed": seed,
                "rays_per_point": 1000,
                "valid": True,
                "hard_gate_pass": True,
                "native_roundtrip_exact": True,
            }
            for seed in seeds
        ],
        "native_handoffs": {
            "handoff_results": [
                {"rng_seed": seed, "accepted": True} for seed in seeds
            ]
        },
        "mask_bracket": {"pass": False},
    }
    assert runner.validate_r1_prerequisite(summary) == []
    changed = copy.deepcopy(summary)
    changed["ray_bridge"]["pass"] = False
    assert runner.validate_r1_prerequisite(changed)
    changed = copy.deepcopy(summary)
    changed["native_handoffs"]["handoff_results"][0]["rng_seed"] = seeds[1]
    assert runner.validate_r1_prerequisite(changed)


def test_cycle_30_shallow_result_is_censored_not_called_infeasible():
    case = runner.expand_cases(manifest())[0]
    original = runner.r1.run_case
    runner.r1.run_case = lambda _task: {
        **case,
        "ok": True,
        "early_stopped": False,
        "last_recorded_cycle": 30,
        "cycle_history": [{"cycle": 30, "depth": 1.0}],
    }
    try:
        row = runner.run_case((case, runner.DEFAULT_OUTPUT))
    finally:
        runner.r1.run_case = original
    assert row["depth_horizon_censored"]
    assert row["trajectory_classification"] == (
        "shallow_at_cycle_horizon_boundary_limited"
    )


def test_response_model_uses_noise_and_only_predeclared_terms():
    frozen = manifest()
    factor_names = [
        factor["name"] for factor in frozen["design"]["factors"]
    ]
    recipe_means = {}
    for row in frozen["design"]["recipes"]:
        x = row["normalized_coordinates"][factor_names[0]]
        recipe_means[row["recipe_id"]] = {
            "normalized_coordinates": row["normalized_coordinates"],
            "metrics": {
                metric: 2.0 * x for metric in review.RESPONSE_METRICS
            },
        }
    noise = {
        metric: {"pooled_within_recipe_sd": 0.1}
        for metric in review.RESPONSE_METRICS
    }
    models = review.response_models(recipe_means, frozen, noise)
    depth = models["depth"]
    assert depth["status"] == "fit"
    assert depth["term_count"] == 25
    assert depth["all_recipe_fit_count"] == 96
    assert len(depth["folds"]) == 4
    assert all(fold["train_recipe_count"] == 72 for fold in depth["folds"])
    assert all(fold["test_recipe_count"] == 24 for fold in depth["folds"])
    assert depth["grouped_cv_rmse"] < 1e-10
    assert depth["factor_effect_snr"][factor_names[0]] > 19.9
    assert set(depth["predeclared_interaction_contrasts"]) == {
        f"{first}:{second}"
        for first, second in frozen["design"]["predeclared_interactions"]
    }


def test_response_means_are_balanced_and_morphology_is_depth_matched():
    coordinates = {name: 0.5 for name in builder.EXPECTED_FACTOR_NAMES}

    def row(recipe_id, role, seed, depth, cd, eligible=True):
        metrics = {metric: cd for metric in review.RESPONSE_METRICS}
        metrics["depth"] = depth
        return {
            "valid": True,
            "rays_per_point": 1000,
            "case_role": role,
            "recipe_id": recipe_id,
            "rng_seed": seed,
            "selection_eligible": eligible,
            "depth_horizon_censored": not eligible and depth < 1.15,
            "normalized_coordinates": coordinates,
            "metrics": metrics,
        }

    reviewed = [
        row("balanced", "base_discovery", 71000, 1.2, 1.0),
        row("balanced", "base_discovery", 72000, 1.3, 3.0),
        row("balanced", "sentinel_noise", 73000, 1.25, 100.0),
        row("miss", "base_discovery", 71000, 1.0, 4.0, False),
        row("miss", "base_discovery", 72000, 1.2, 6.0, True),
    ]
    means = review.low_fidelity_recipe_means(reviewed)
    assert means["balanced"]["metrics"]["cd_top"] == 2.0
    assert means["balanced"]["metrics"]["depth"] == 1.25
    assert means["miss"]["metrics"]["depth"] == 1.1
    assert means["miss"]["metrics"]["cd_top"] is None


def test_practical_detection_threshold_and_ctq_adequacy_are_explicit():
    frozen = manifest()
    noise = {
        metric: {"pooled_within_recipe_sd": 0.01}
        for metric in review.RESPONSE_METRICS
    }
    fidelity = {
        "maximum_absolute_delta": {
            metric: 0.02 for metric in review.RESPONSE_METRICS
        }
    }
    thresholds = review.practical_detection_thresholds(
        [], noise, fidelity, frozen
    )
    assert thresholds["depth"]["screening_detection_threshold"] > 0.027
    assert thresholds["depth"]["ctq_tolerance"] == 0.1
    assert thresholds["selected_cycle"]["screening_detection_threshold"] == 1.0


if __name__ == "__main__":
    test_design_is_deterministic_wide_and_not_authoritative()
    test_factor_transforms_cover_exact_endpoints()
    test_exact_232_case_matrix_and_sentinel_roles()
    test_rng_overlap_guard_allows_only_declared_fidelity_pair()
    test_historical_depth_matched_failure_is_an_exact_anchor()
    test_r1_prerequisite_uses_ray_and_native_evidence_not_mask_search()
    test_cycle_30_shallow_result_is_censored_not_called_infeasible()
    test_response_model_uses_noise_and_only_predeclared_terms()
    test_response_means_are_balanced_and_morphology_is_depth_matched()
    test_practical_detection_threshold_and_ctq_adequacy_are_explicit()
    print("broad-first Bosch discovery checks: PASS")

"""Focused guards for the V3 Stage-0 numerical release."""

import json
from functools import lru_cache
from pathlib import Path

import review_v3_numerical_release as release


ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def actual_release():
    return release.build_release(
        ROOT / release.DEFAULT_MANIFEST,
        ROOT / release.DEFAULT_ROWS,
        ROOT / release.DEFAULT_R1_SUMMARY,
    )


def test_actual_r1_evidence_releases_only_2000_ray_exploration():
    result = actual_release()
    decision = result["decision"]
    assert decision["classification"] == "approved_for_v3_exploratory_screening"
    assert decision["pass"] is True
    assert decision["grid_delta"] == 0.00125
    assert decision["rays_per_point"] == 2000
    assert decision["dimension"] == 2
    assert decision["rays_1000_rejected"] is True
    assert decision["native_baseline_authorized"] is True
    assert decision["authority"] == {
        "exploratory_screening": True,
        "automatic_launch": False,
        "mask_claims": False,
        "recipe": False,
        "process_window": False,
        "full_traveler": False,
        "fab_recipe": False,
    }


def test_frozen_limits_reject_1000_rays_for_shape_screening():
    result = actual_release()
    bridge = result["ray_bridge"]
    assert bridge["pair_count"] == 4
    assert bridge["all_rows_independently_valid"] is True
    assert bridge["no_hard_gate_flips"] is True
    assert bridge["rays_1000_passes_frozen_bridge"] is False
    assert bridge["failed_metrics"] == ["depth", "cd_bottom", "max_bow"]
    for metric in bridge["failed_metrics"]:
        current = bridge["metric_results"][metric]
        assert current["observed_max_absolute_delta"] > current[
            "frozen_max_absolute_delta"
        ]


def test_all_eight_rows_and_four_2000_ray_shapes_are_independently_valid():
    result = actual_release()
    assert result["row_scope"]["reviewed_fixed_row_count"] == 8
    assert result["row_scope"]["ignored_non_numerical_row_count"] == 0
    assert len(result["reviewed_cases"]) == 8
    assert all(row["valid"] for row in result["reviewed_cases"])
    baselines = result["native_baselines"]
    assert baselines["source_arm"] == "full_ray_anchor_r2000"
    assert baselines["shape_count"] == 4
    assert baselines["authorized"] is True
    assert all(shape["accepted"] for shape in baselines["shapes"])
    assert {shape["rng_seed"] for shape in baselines["shapes"]} == {
        61000, 62000, 63000, 64000
    }


def test_unrun_mask_ladder_is_out_of_scope_not_silently_passed():
    result = actual_release()
    assert result["mask_scope"] == {
        "classification": "not_evaluated_by_this_numerical_release",
        "mask_ladder_required_for_this_decision": False,
        "executed_mask_ladder_rows_used": 0,
        "mask_rate_or_failure_boundary_claim_authorized": False,
    }
    assert result["r1_summary_crosscheck"]["status"] == "incomplete_or_invalid"
    assert result["r1_summary_crosscheck"]["valid"] is True


def test_machine_artifact_has_hashed_inputs_and_no_nan():
    result = actual_release()
    for declaration in result["source_evidence"].values():
        assert len(declaration["sha256"]) == 64
        assert Path(declaration["path"]).is_file()
    json.dumps(result, sort_keys=True, allow_nan=False)


def test_post_run_source_guard_drift_does_not_rewrite_frozen_evidence():
    result = actual_release()
    provenance = result["runtime_provenance"]
    assert provenance["executed_rows_bind_frozen_runtime"] is True
    for drift in provenance["current_source_drift"].values():
        assert len(drift["frozen_sha256"]) == 64
        assert len(drift["current_sha256"]) == 64
        assert drift["frozen_sha256"] != drift["current_sha256"]
    assert provenance["current_source_drift_is_evidence_mutation"] is False


if __name__ == "__main__":
    test_actual_r1_evidence_releases_only_2000_ray_exploration()
    test_frozen_limits_reject_1000_rays_for_shape_screening()
    test_all_eight_rows_and_four_2000_ray_shapes_are_independently_valid()
    test_unrun_mask_ladder_is_out_of_scope_not_silently_passed()
    test_machine_artifact_has_hashed_inputs_and_no_nan()
    test_post_run_source_guard_drift_does_not_rewrite_frozen_evidence()
    print("V3 numerical release guards: PASS")

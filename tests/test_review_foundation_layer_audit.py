"""Scientific decision guards for the foundation-layer review."""

import copy

import review_foundation_layer_audit as review


FINGERPRINT = {
    "runner_sha256": "runner",
    "metric_sha256": "metrics",
    "tsv_process_sha256": "process",
    "runtime_binary_sha256": "binary",
}

THRESHOLDS = {
    "liner_min": 0.0005,
    "liner_floor_field": 0.0025,
    "liner_lower_wall_field": 0.0025,
    "liner_aperture": 0.001,
    "barrier_min": 0.00015,
    "barrier_floor_field": 0.0025,
    "barrier_lower_wall_field": 0.0025,
    "barrier_aperture": 0.001,
    "seed_min": 0.00015,
    "seed_floor_field": 0.0025,
    "seed_lower_wall_field": 0.0025,
    "seed_aperture": 0.001,
    "stack_min": 0.0003,
    "stack_floor_field": 0.0025,
}


def manifest():
    return {
        "manifest_version": 1,
        "geometry": {"radius": 0.15, "depth": 1.25},
        "specs": {
            "liner": {"min_thickness": 0.02, "min_coverage": 0.995},
            "barrier_seed": {"min_thickness": 0.012, "min_coverage": 0.985},
        },
        "baseline": {
            "liner": {"thickness": 0.04, "sticking": 0.01},
            "barrier": {"thickness": 0.008, "iso_ratio": 0.3},
            "seed": {"thickness": 0.008, "iso_ratio": 0.3},
        },
        "rays_per_point": 2000,
        "threads_per_worker": 7,
        "provenance": {"viennaps_package": "test"},
        "designs": [
            {
                "name": "grid_0.0025",
                "comparison_family": "grid_primary",
                "grid_delta": 0.0025,
                "seed_start": 61000,
                "seed_count": 4,
            },
            {
                "name": "grid_0.00125",
                "comparison_family": "grid_primary",
                "grid_delta": 0.00125,
                "seed_start": 61000,
                "seed_count": 4,
            },
            {
                "name": "grid_0.000625",
                "comparison_family": "grid_anchor",
                "grid_delta": 0.000625,
                "seed_start": 61000,
                "seed_count": 2,
            },
        ]
    }


def manifest_v2():
    result = manifest()
    result["manifest_version"] = 2
    result["provenance"] = {
        "viennaps_package": "test",
        **FINGERPRINT,
    }
    result["designs"] = [
        {
            "name": "grid_mid_r2000",
            "comparison_family": "qualification",
            "grid_delta": 0.00125,
            "rays_per_point": 2000,
            "seed_start": 62000,
            "seed_count": 4,
        },
        {
            "name": "grid_fine_r2000",
            "comparison_family": "qualification",
            "grid_delta": 0.000625,
            "rays_per_point": 2000,
            "seed_start": 62000,
            "seed_count": 4,
        },
        {
            "name": "grid_mid_r4000",
            "comparison_family": "qualification",
            "grid_delta": 0.00125,
            "rays_per_point": 4000,
            "seed_start": 62000,
            "seed_count": 4,
        },
    ]
    result["comparison_pairs"] = [
        {
            "name": "grid_mid_to_fine",
            "first": "grid_mid_r2000",
            "second": "grid_fine_r2000",
            "minimum_pairs": 4,
        },
        {
            "name": "ray_2000_to_4000",
            "first": "grid_mid_r2000",
            "second": "grid_mid_r4000",
            "minimum_pairs": 4,
        },
    ]
    result["numerical_acceptance_thresholds"] = dict(THRESHOLDS)
    return result


def metric_block(*, minimum, floor_field, lower_wall_field, aperture=0.2):
    return {
        "minimum_local_thickness": minimum,
        "floor_to_field_conformality": floor_field,
        "lower_wall_to_field_conformality": lower_wall_field,
        "minimum_remaining_aperture": aperture,
        "layer_continuous": True,
        "aperture_open": True,
    }


def build_rows(study, shifts):
    result = []
    for design in study["designs"]:
        for replicate in range(design["seed_count"]):
            shift = shifts[design["name"]]
            row = {
                "case_id": f"{design['name']}-{replicate}",
                "manifest_version": study["manifest_version"],
                "design": design["name"],
                "comparison_family": design["comparison_family"],
                "rng_seed": design["seed_start"] + replicate,
                "geometry": study["geometry"],
                "grid_delta": design["grid_delta"],
                "rays_per_point": design.get(
                    "rays_per_point", study["rays_per_point"]
                ),
                "threads_per_worker": study["threads_per_worker"],
                "liner": study["baseline"]["liner"],
                "barrier": study["baseline"]["barrier"],
                "seed": study["baseline"]["seed"],
                "provenance": study["provenance"],
                "ok": True,
                "specs": study["specs"],
                "liner_metrics": metric_block(
                    minimum=0.03 + shift,
                    floor_field=1.0,
                    lower_wall_field=1.0,
                ),
                "barrier_metrics": metric_block(
                    minimum=0.0061 + shift,
                    floor_field=0.99,
                    lower_wall_field=0.7,
                ),
                "seed_metrics": metric_block(
                    minimum=0.0061 + shift,
                    floor_field=0.99,
                    lower_wall_field=0.7,
                ),
                "passes": {"liner": True, "barrier_seed": True},
            }
            if "comparison_pairs" in study:
                row["runtime_fingerprint"] = {
                    key: study["provenance"].get(key)
                    for key in review.FINGERPRINT_KEYS
                }
            result.append(row)
    return result


def rows():
    return build_rows(manifest(), {
        "grid_0.0025": 0.0,
        "grid_0.00125": 0.0001,
        "grid_0.000625": 0.00015,
    })


def rows_v2(study=None):
    study = study or manifest_v2()
    return build_rows(study, {
        "grid_mid_r2000": 0.0,
        "grid_fine_r2000": 0.00001,
        "grid_mid_r4000": -0.00001,
    })


def test_complete_rows_are_not_mislabeled_as_numerically_qualified():
    summary = review.build_summary(rows(), manifest())
    assert summary["status"] == "complete"
    assert summary["qualification_status"] == "not_established"
    assert not summary["production_doe_authorized"]
    assert summary["paired_deltas"]["grid_primary"]["pairs"] == 4
    assert summary["paired_deltas"]["grid_anchor"]["pairs"] == 2
    assert any("only 2 paired seeds" in item for item in summary["qualification_blockers"])
    assert any("no quantitative" in item for item in summary["qualification_blockers"])


def test_declared_liner_gate_includes_lower_wall_conformality():
    sample = rows()
    sample[0]["liner_metrics"]["lower_wall_to_field_conformality"] = 0.90
    summary = review.build_summary(sample, manifest())
    assert summary["groups"]["grid_0.0025"]["liner_passes"] == 3
    assert summary["runner_gate_disagreements"] == [{
        "case_id": "grid_0.0025-0",
        "gate": "liner",
        "runner": True,
        "declared": False,
    }]


def test_wrong_design_seed_matrix_cannot_look_complete():
    sample = rows()
    sample[-1]["design"] = "grid_0.00125"
    sample[-1]["rng_seed"] = 61000
    summary = review.build_summary(sample, manifest())
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["duplicate_design_seed_keys"] == [["grid_0.00125", 61000]]
    assert summary["missing_design_seed_keys"] == [["grid_0.000625", 61001]]


def test_nonfinite_metric_stays_visible_and_invalidates_data():
    sample = copy.deepcopy(rows())
    sample[0]["liner_metrics"]["minimum_local_thickness"] = float("nan")
    summary = review.build_summary(sample, manifest())
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["valid_metric_count"] == 9
    assert summary["invalid_metric_rows"] == [{
        "case_id": "grid_0.0025-0",
        "reasons": ["liner_min: non-finite"],
    }]


def test_manifest_parameter_drift_invalidates_data():
    sample = rows()
    sample[0]["grid_delta"] = 0.01
    summary = review.build_summary(sample, manifest())
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["case_invariant_mismatches"] == [{
        "case_id": "grid_0.0025-0",
        "reasons": ["grid_delta: row does not match manifest"],
    }]


def test_v2_establishes_only_exploratory_screening_qualification():
    study = manifest_v2()
    summary = review.build_summary(rows_v2(study), study)
    assert summary["status"] == "complete"
    assert summary["qualification_status"] == "established"
    assert summary["production_doe_authorized"]
    assert (
        summary["production_doe_authorization_scope"]
        == "exploratory_layer_factor_screening_only"
    )
    assert not summary["final_recipe_acceptance_authorized"]
    assert summary["qualification_blockers"] == []
    assert summary["case_invariant_mismatches"] == []
    assert summary["runtime_fingerprint"] == FINGERPRINT
    for name in ("grid_mid_to_fine", "ray_2000_to_4000"):
        result = summary["qualification_comparisons"][name]
        assert result["pass"]
        assert result["pairs"] == 4
        assert result["enough_pairs"]
        assert result["no_gate_changes"]
        assert result["thresholds_pass"]
        assert all(item["pass"] for item in result["thresholds"].values())
    report = review.markdown(summary)
    assert "Exploratory layer-factor screening is authorized" in report
    assert "Final-recipe acceptance" in report


def test_v2_rejects_a_maximum_paired_delta_over_threshold():
    study = manifest_v2()
    sample = rows_v2(study)
    fine = next(
        row
        for row in sample
        if row["design"] == "grid_fine_r2000" and row["rng_seed"] == 62000
    )
    fine["liner_metrics"]["minimum_local_thickness"] += 0.001
    summary = review.build_summary(sample, study)
    result = summary["qualification_comparisons"]["grid_mid_to_fine"]
    assert summary["status"] == "complete"
    assert summary["qualification_status"] == "not_established"
    assert not summary["production_doe_authorized"]
    assert not result["thresholds"]["liner_min"]["pass"]
    assert result["thresholds"]["liner_min"]["maximum_absolute_delta"] > 0.0005
    assert not result["pass"]


def test_v2_rejects_boolean_or_functional_gate_changes():
    study = manifest_v2()
    sample = rows_v2(study)
    fine = next(
        row
        for row in sample
        if row["design"] == "grid_fine_r2000" and row["rng_seed"] == 62000
    )
    fine["liner_metrics"]["layer_continuous"] = False
    fine["passes"]["liner"] = False
    summary = review.build_summary(sample, study)
    result = summary["qualification_comparisons"]["grid_mid_to_fine"]
    assert summary["status"] == "complete"
    assert summary["qualification_status"] == "not_established"
    assert not result["no_gate_changes"]
    assert {change["gate"] for change in result["gate_changes"]} == {
        "liner",
        "liner_continuous",
    }


def test_v2_requires_at_least_four_actual_pairs():
    study = manifest_v2()
    study["designs"][1]["seed_count"] = 3
    summary = review.build_summary(rows_v2(study), study)
    assert summary["status"] == "complete"
    assert summary["qualification_status"] == "not_established"
    result = summary["qualification_comparisons"]["grid_mid_to_fine"]
    assert result["pairs"] == 3
    assert not result["enough_pairs"]
    assert not result["pass"]


def test_v2_requires_runtime_fingerprint_to_match_every_row():
    study = manifest_v2()
    sample = rows_v2(study)
    sample[0]["runtime_fingerprint"]["runner_sha256"] = "old-runner"
    summary = review.build_summary(sample, study)
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["qualification_status"] == "not_evaluable"
    assert not summary["production_doe_authorized"]
    assert summary["case_invariant_mismatches"] == [{
        "case_id": "grid_mid_r2000-0",
        "reasons": ["runtime_fingerprint: row does not match manifest"],
    }]


def test_v2_uses_design_level_ray_override_as_an_invariant():
    study = manifest_v2()
    sample = rows_v2(study)
    high_ray = next(row for row in sample if row["design"] == "grid_mid_r4000")
    assert high_ray["rays_per_point"] == 4000
    high_ray["rays_per_point"] = 2000
    summary = review.build_summary(sample, study)
    assert summary["status"] == "incomplete_or_invalid"
    assert summary["case_invariant_mismatches"][0]["reasons"] == [
        "rays_per_point: row does not match manifest"
    ]


def test_v2_requires_every_declared_metric_threshold():
    study = manifest_v2()
    del study["numerical_acceptance_thresholds"]["seed_aperture"]
    summary = review.build_summary(rows_v2(study), study)
    assert summary["status"] == "complete"
    assert summary["qualification_status"] == "not_established"
    assert summary["qualification_manifest_errors"] == [
        "numerical thresholds missing metrics: seed_aperture"
    ]
    assert all(
        not result["thresholds_pass"]
        for result in summary["qualification_comparisons"].values()
    )


def test_v2_rejects_declared_minimum_below_four():
    study = manifest_v2()
    study["comparison_pairs"][0]["minimum_pairs"] = 3
    summary = review.build_summary(rows_v2(study), study)
    assert summary["status"] == "complete"
    assert summary["qualification_status"] == "not_established"
    assert (
        "grid_mid_to_fine: minimum_pairs must be at least 4"
        in summary["qualification_manifest_errors"]
    )


def test_v2_requires_all_four_manifest_fingerprints():
    study = manifest_v2()
    del study["provenance"]["metric_sha256"]
    summary = review.build_summary(rows_v2(study), study)
    assert summary["status"] == "complete"
    assert summary["qualification_status"] == "not_established"
    assert summary["runtime_fingerprint"]["metric_sha256"] is None
    assert (
        "all four runtime fingerprint values must be present in provenance"
        in summary["qualification_manifest_errors"]
    )


if __name__ == "__main__":
    test_complete_rows_are_not_mislabeled_as_numerically_qualified()
    test_declared_liner_gate_includes_lower_wall_conformality()
    test_wrong_design_seed_matrix_cannot_look_complete()
    test_nonfinite_metric_stays_visible_and_invalidates_data()
    test_manifest_parameter_drift_invalidates_data()
    test_v2_establishes_only_exploratory_screening_qualification()
    test_v2_rejects_a_maximum_paired_delta_over_threshold()
    test_v2_rejects_boolean_or_functional_gate_changes()
    test_v2_requires_at_least_four_actual_pairs()
    test_v2_requires_runtime_fingerprint_to_match_every_row()
    test_v2_uses_design_level_ray_override_as_an_invariant()
    test_v2_requires_every_declared_metric_threshold()
    test_v2_rejects_declared_minimum_below_four()
    test_v2_requires_all_four_manifest_fingerprints()
    print("Foundation layer review checks: PASS")

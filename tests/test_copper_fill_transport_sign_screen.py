"""Cheap qualification checks for the frozen Cu-fill transport-sign screen."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import numpy as np
import viennaps as ps

import foundation_copper_fill_transport_sign_screen as runner
import review_copper_fill_regional_kinematics as regional
import review_copper_fill_transport_sign_screen as review


FAKE_FINGERPRINT = {
    "runner_sha256": "runner",
    "trajectory_runner_sha256": "trajectory",
    "regional_kinematics_sha256": "regional",
    "traveler_metrics_sha256": "metrics",
    "tsv_process_sha256": "process",
    "viennaps_binary_sha256": "binary",
}


def manifest():
    return json.loads(runner.DEFAULT_MANIFEST.read_text())


def reference(depth=1.0):
    return {
        "field_y": depth,
        "floor_y": 0.0,
        "via_x_bounds": [-0.5, 0.5],
        "field_sample_xs": [-1.2, 1.2],
        "initial_topology": {
            "open_void_depth": depth,
            "remaining_void_area": 0.8 * depth,
            "mouth_aperture": 0.8,
        },
    }


def regional_fixture(depth=1.0):
    coordinates = np.asarray([
        [0.0, 0.02, 0.0],
        [-0.4, 0.20 * depth, 0.0],
        [0.4, 0.20 * depth, 0.0],
        [-0.4, 0.50 * depth, 0.0],
        [0.4, 0.50 * depth, 0.0],
        [-0.4, 0.80 * depth, 0.0],
        [0.4, 0.80 * depth, 0.0],
        [-0.4, depth - 0.01, 0.0],
        [0.4, depth - 0.01, 0.0],
        [-1.2, depth, 0.0],
        [1.2, depth, 0.0],
    ])
    flux = np.asarray([0.1, 0.9, 1.1, 0.8, 1.2, 0.7, 1.3, 1.0, 1.0, 0.6, 1.4])
    coverage = flux * 0.4
    velocity = 0.2 - 0.1 * coverage
    return coordinates, flux, coverage, velocity


def test_frozen_matrix_identifiability_and_disjoint_stream_contract():
    data = manifest()
    cases = runner.expand_cases(data, FAKE_FINGERPRINT)

    assert len(cases) == 168
    assert len({case["case_id"] for case in cases}) == 168
    assert runner.validate_manifest(data, cases) == []
    assert {
        (
            case["geometry_tier"],
            case["model"]["suppressor_sticking_probability"],
            case["model"]["suppressor_source_power"],
            case["rng_seed"],
        )
        for case in cases
    } == {
        (tier, sticking, power, seed)
        for tier in runner.GEOMETRY_TIERS
        for sticking in runner.STICKING_LEVELS
        for power in runner.SOURCE_POWER_LEVELS
        for seed in runner.PAIRED_BASE_SEEDS
    }
    for case in cases:
        assert case["labels"] == ["full-traveler", "critical-review"]
        model = case["model"]
        assert np.isclose(
            model["adsorption_strength"],
            0.25 / model["suppressor_sticking_probability"],
        )
        assert np.isclose(
            model["adsorption_strength"]
            * model["suppressor_sticking_probability"]
            / (model["deactivation_rate"] * model["active_deposition_rate"]),
            5.0,
        )
        assert model["gas_mean_free_path"] == -1.0
        assert case["numerics"]["max_duration"] == case["numerics"][
            "checkpoint_interval"
        ] == 0.025
        assert case["numerics"]["threads_per_worker"] == 1
        assert case["numerics"]["max_reflections"] == 400
    reflection = data["analysis"]["ray_reflection_contract"]
    assert np.isclose(
        reflection["unabsorbed_weight_upper_bound"], (1.0 - 0.025) ** 400
    )
    assert reflection["confirmation_max_reflections"] == [400, 800]

    wrong_geometry = copy.deepcopy(data)
    wrong_geometry["geometry_tiers"][1]["geometry"]["depth"] = 2.5
    assert any(
        "geometry tiers" in error
        for error in runner.validate_manifest(
            wrong_geometry,
            runner.expand_cases(wrong_geometry, FAKE_FINGERPRINT),
        )
    )
    wrong_rays = copy.deepcopy(data)
    wrong_rays["numerics"]["rays_per_point"] = 500
    assert any(
        "rays_per_point" in error
        for error in runner.validate_manifest(
            wrong_rays, runner.expand_cases(wrong_rays, FAKE_FINGERPRINT)
        )
    )
    wrong_provenance = copy.deepcopy(data)
    wrong_provenance["provenance"]["viennaps_source_commit"] = "wrong"
    assert any(
        "provenance viennaps_source_commit" in error
        for error in runner.validate_manifest(
            wrong_provenance,
            runner.expand_cases(wrong_provenance, FAKE_FINGERPRINT),
        )
    )

    overlapping = copy.deepcopy(data)
    for design in overlapping["designs"]:
        design["rng_seeds"] = [102000, 102001, 102002, 102003]
    errors = runner.validate_manifest(
        overlapping, runner.expand_cases(overlapping, FAKE_FINGERPRINT)
    )
    assert any("paired base seeds" in error for error in errors)
    assert any("RNG stream contract" in error for error in errors)


def test_regions_preserve_left_right_asymmetry_and_imported_spatial_cuts():
    coordinates, flux, coverage, velocity = regional_fixture()
    result = runner.detailed_region_statistics(
        coordinates, flux, coverage, velocity, reference()
    )

    assert set(result) == set(runner.REGION_NAMES)
    assert result["left_lower_wall"]["point_count"] == 1
    assert result["right_lower_wall"]["point_count"] == 1
    assert result["left_lower_wall"]["suppressor_flux"]["mean"] == 0.9
    assert result["right_lower_wall"]["suppressor_flux"]["mean"] == 1.1
    assert result["mouth_shoulder"]["point_count"] == 2
    assert result["field"]["point_count"] == 2
    assert result["field"]["suppressor_flux"]["q10"] < result["field"][
        "suppressor_flux"
    ]["q90"]

    imported = regional.region_statistics(
        coordinates, flux, coverage, velocity, reference()
    )
    assert imported["lower_wall"]["point_count"] == (
        result["left_lower_wall"]["point_count"]
        + result["right_lower_wall"]["point_count"]
    )
    assert np.isclose(imported["lower_wall"]["suppressor_flux_mean"], 1.0)


def _stat(value, count=1):
    return {
        "point_count": count,
        **{
            quantity: {"mean": value, "q10": value, "q50": value, "q90": value}
            for quantity in runner.QUANTITIES
        },
    }


def passing_regions():
    result = {name: _stat(1.0) for name in runner.REGION_NAMES}
    result["floor"] = {
        "point_count": 1,
        "suppressor_flux": {"mean": 0.5, "q10": 0.5, "q50": 0.5, "q90": 0.5},
        "coverage": {"mean": 0.2, "q10": 0.2, "q50": 0.2, "q90": 0.2},
        "normal_velocity": {"mean": 0.15, "q10": 0.15, "q50": 0.15, "q90": 0.15},
    }
    for name in review.LOWER_REGIONS:
        result[name] = {
            "point_count": 1,
            "suppressor_flux": {"mean": 1.0, "q10": 1.0, "q50": 1.0, "q90": 1.0},
            "coverage": {"mean": 0.5, "q10": 0.5, "q50": 0.5, "q90": 0.5},
            "normal_velocity": {"mean": 0.1, "q10": 0.1, "q50": 0.1, "q90": 0.1},
        }
    for name in review.MIDDLE_UPPER_REGIONS:
        result[name]["normal_velocity"] = {
            "mean": 0.12,
            "q10": 0.12,
            "q50": 0.12,
            "q90": 0.12,
        }
    return result


def decide(regions, **overrides):
    arguments = {
        "balance_valid": True,
        "diagnostics_valid": True,
        "topology_valid": True,
        "transition_valid": True,
        "protected_stack_survives": True,
        **overrides,
    }
    return review.transport_case_decision(regions, **arguments)


def test_transport_boundaries_are_strict_and_every_region_is_required():
    assert decide(passing_regions())["pass"]

    flux_edge = passing_regions()
    flux_edge["floor"]["suppressor_flux"] = {
        "mean": 0.95, "q10": 0.95, "q50": 0.95, "q90": 0.95
    }
    assert not decide(flux_edge)["pass"]

    coverage_edge = passing_regions()
    coverage_edge["floor"]["coverage"] = {
        "mean": 0.5, "q10": 0.5, "q50": 0.5, "q90": 0.5
    }
    assert not decide(coverage_edge)["pass"]

    velocity_edge = passing_regions()
    velocity_edge["floor"]["normal_velocity"] = {
        "mean": 0.105, "q10": 0.105, "q50": 0.105, "q90": 0.105
    }
    assert not decide(velocity_edge)["pass"]

    upper_edge = passing_regions()
    upper_edge["left_upper_wall"]["normal_velocity"] = {
        "mean": 0.15, "q10": 0.15, "q50": 0.15, "q90": 0.15
    }
    assert not decide(upper_edge)["pass"]

    empty = passing_regions()
    empty["field"] = _stat(1.0, count=0)
    assert not decide(empty)["pass"]
    assert not decide(passing_regions(), balance_valid=False)["pass"]
    assert not decide(passing_regions(), protected_stack_survives=False)["pass"]


def test_mixed_zero_velocity_ratios_are_visible_and_ineligible():
    # At R=0, one stream can have zero floor and wall velocity (undefined
    # zero/zero) while another retains a finite ratio from saved zero-flux
    # points. The coefficient case must not minimize across that mixture.
    # This is the actual completed-run pattern for continuity /
    # stick_0p025_power_4p0 / Pi_A=6.25 / R=0.
    summary = review._ratio_vector_summary([0.0, 0.0, 0.0, None], 4)
    assert not summary["eligible"]
    assert summary["status"] == (
        "ineligible_undefined_or_nonfinite_stream_ratio"
    )
    assert summary["invalid_stream_indices"] == [3]
    assert summary["stream_ratios"] == [0.0, 0.0, 0.0, None]
    assert summary["worst_ratio"] is None

    nonfinite = review._ratio_vector_summary(
        [float("nan"), 0.8, 0.9, 1.0], 4
    )
    assert not nonfinite["eligible"]
    assert nonfinite["stream_ratios"][0] == "invalid_nonfinite"
    json.dumps(nonfinite, allow_nan=False)


def test_exact_equilibrium_law_matches_cpp_diagnostics():
    geometry = ps.Domain(gridDelta=0.02, xExtent=0.4, yExtent=0.4)
    ps.MakePlane(geometry, height=0.0, material=ps.Material.Si).apply()
    geometry.duplicateTopLevelSet(ps.Material.Cu)
    params = ps.CopperSuppressionFillParams()
    params.suppressorStickingProbability = 0.2
    params.suppressorSourcePower = 1.0
    params.gasMeanFreePath = -1.0
    params.adsorptionStrength = 1.25
    params.deactivationRate = 0.25
    params.activeDepositionRate = 0.2
    params.suppressedDepositionRate = 0.01
    params.platingMaterials = [ps.Material.Si, ps.Material.Cu]
    model = ps.CopperSuppressionFill(params)
    process = ps.Process(geometry, model, 0.005)
    ray = ps.RayTracingParameters()
    ray.useRandomSeeds = False
    ray.rngSeed = 110001
    ray.raysPerPoint = 200
    process.setParameters(ray)
    process.apply()

    flux = np.asarray(model.getLastSuppressorFlux(), dtype=float)
    material_ids = np.asarray(model.getLastMaterialIds(), dtype=float)
    predicted = runner.analytic_diagnostics(
        flux,
        material_ids,
        [ps.Material.Si.legacyId(), ps.Material.Cu.legacyId()],
        pi_a=5.0,
        deactivation_rate=0.25,
        active_rate=0.2,
        suppressed_rate=0.01,
    )
    assert np.allclose(predicted["coverage"], model.getLastCoverage(), atol=1e-14, rtol=0.0)
    assert np.allclose(predicted["velocity"], model.getLastVelocity(), atol=1e-14, rtol=0.0)
    assert np.allclose(predicted["adsorption_term"], model.getLastAdsorptionTerm(), atol=1e-14, rtol=0.0)
    assert np.allclose(predicted["deactivation_term"], model.getLastDeactivationTerm(), atol=1e-14, rtol=0.0)
    assert predicted["relative_balance_error"] < 1e-12


def _minimal_attempt(case, *, ok=True):
    return {
        **case,
        "ok": ok,
        "production_doe_eligible": False,
        "morphology_ranking_eligible": False,
        **({} if ok else {"error": "synthetic current error"}),
    }


def test_fingerprint_audit_requires_exact_168_and_rejects_current_errors():
    data = manifest()
    cases = runner.expand_cases(data, FAKE_FINGERPRINT)
    rows = [_minimal_attempt(case) for case in cases]
    audit = review.audit_attempts(data, rows, [], False, FAKE_FINGERPRINT)
    assert audit["status"] == "complete"
    assert audit["selected_current_case_count"] == 168

    error = _minimal_attempt(cases[0], ok=False)
    resolved = review.audit_attempts(
        data, [error, *rows], [], False, FAKE_FINGERPRINT
    )
    assert resolved["status"] == "complete"
    assert resolved["current_fingerprint_error_attempt_rows"] == []
    assert resolved["resolved_current_fingerprint_error_attempt_rows"] == [error]

    audit = review.audit_attempts(
        data, [*rows, error], [], False, FAKE_FINGERPRINT
    )
    assert audit["status"] == "incomplete_or_invalid"
    assert audit["current_fingerprint_error_attempt_rows"] == [error]

    audit = review.audit_attempts(data, rows[:-1], [], False, FAKE_FINGERPRINT)
    assert audit["status"] == "incomplete_or_invalid"
    assert len(audit["missing_cases"]) == 1


def test_resume_requires_success_and_a_matching_snapshot(tmp_path):
    output = tmp_path / "rows.jsonl"
    snapshot = tmp_path / "snapshot.npz"
    snapshot.write_bytes(b"diagnostic")
    good = {
        "case_id": "good",
        "ok": True,
        "diagnostic_snapshot_path": str(snapshot),
        "diagnostic_snapshot_sha256": runner._file_sha256(snapshot),
    }
    error = {"case_id": "error", "ok": False}
    missing = {
        "case_id": "missing",
        "ok": True,
        "diagnostic_snapshot_path": str(tmp_path / "missing.npz"),
        "diagnostic_snapshot_sha256": "none",
    }
    output.write_text(
        "\n".join([json.dumps(good), json.dumps(error), json.dumps(missing), "{"])
    )
    assert runner._completed_case_ids(output) == {"good"}


def _synthetic_snapshot_row(tmp_path, case):
    depth = float(case["geometry"]["depth"])
    case_reference = reference(depth)
    coordinates, flux, _, _ = regional_fixture(depth)
    flux = np.where(np.arange(len(flux)) == 0, 0.1, 1.0)
    material_ids = np.full(len(flux), float(ps.Material.Cu.legacyId()))
    model = case["model"]
    analytic = runner.analytic_diagnostics(
        flux,
        material_ids,
        [ps.Material.Cu.legacyId()],
        pi_a=5.0,
        deactivation_rate=model["deactivation_rate"],
        active_rate=model["active_deposition_rate"],
        suppressed_rate=model["suppressed_deposition_rate"],
    )
    regions = runner.detailed_region_statistics(
        coordinates,
        flux,
        analytic["coverage"],
        analytic["velocity"],
        case_reference,
    )
    field = regions["field"]
    diagnostics = {
        "valid": True,
        "relative_balance_error": analytic["relative_balance_error"],
        "field_flux_mean": field["suppressor_flux"]["mean"],
        "field_coverage_mean": field["coverage"]["mean"],
        "field_velocity_mean": field["normal_velocity"]["mean"],
    }
    nodes = np.asarray([
        [-0.5, depth, 0.0],
        [-0.4, depth, 0.0],
        [-0.4, 0.0, 0.0],
        [0.4, 0.0, 0.0],
        [0.4, depth, 0.0],
        [0.5, depth, 0.0],
    ])
    lines = np.asarray([[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]])
    path = tmp_path / f"{case['case_id']}.npz"
    np.savez_compressed(
        path,
        elapsed=np.asarray([0.025]),
        nodes=nodes,
        lines=lines,
        mesh_surface_stage=np.asarray(["post-checkpoint advection"]),
        diagnostic_surface_stage=np.asarray(["pre-final-advection surface"]),
        diagnostic_relative_balance_error=np.asarray([
            analytic["relative_balance_error"]
        ]),
        diagnostic_coordinates=coordinates,
        diagnostic_material_ids=material_ids,
        diagnostic_suppressor_flux=flux,
        diagnostic_coverage=analytic["coverage"],
        diagnostic_velocity=analytic["velocity"],
        diagnostic_adsorption_term=analytic["adsorption_term"],
        diagnostic_deactivation_term=analytic["deactivation_term"],
    )
    checkpoint = {
        "checkpoint": 1,
        "elapsed": 0.025,
        "topology": {"topology_valid": True},
        "topology_transition": {"valid": True},
        "protected_stack": {"survives": True},
        "model_diagnostics": diagnostics,
        "analysis_regions": regions,
        "snapshot_path": str(path),
    }
    return {
        **case,
        "ok": True,
        "production_doe_eligible": False,
        "morphology_ranking_eligible": False,
        "target_pass": False,
        "transport_screen_pass": None,
        "reference": case_reference,
        "trajectory": [checkpoint],
        "last_checkpoint": 1,
        "plating_material_legacy_ids": [float(ps.Material.Cu.legacyId())],
        "diagnostic_snapshot_path": str(path),
        "diagnostic_snapshot_sha256": runner._file_sha256(path),
        "rng_stream": {
            "base_seed": case["rng_seed"],
            "checkpoint_seed": case["rng_seed"] + 1,
            "paired_across_designs": True,
        },
    }


def test_complete_synthetic_review_has_no_morphology_ranking(tmp_path):
    data = manifest()
    cases = runner.expand_cases(data, FAKE_FINGERPRINT)
    rows = [_synthetic_snapshot_row(tmp_path, case) for case in cases]
    summary = review.build_summary(
        data, rows, [], False, FAKE_FINGERPRINT, tmp_path
    )

    assert summary["status"] == "complete"
    assert summary["metric_valid_case_count"] == 168
    assert summary["transport_pass_design_count"] == 21
    assert summary["morphology_ranking"] == []
    assert summary["analytic_cross_tier_kinematic_passes"]
    assert any(
        item.get("interior_passing_coefficient_case_count", 0) > 0
        and item.get("R_over_Va") not in {0.0, 1.0}
        for item in summary["analytic_envelope_cross_tier"]
        if item["all_eight_streams_exceed_tier_kinematic_threshold"]
    )
    limits = summary["analytic_envelope_exact_limits"]
    assert limits["required_region_zero_flux_point_count"] == 0
    assert limits["cross_tier_kinematic_passes"] == []
    assert all(
        item["pi_a_zero"]["worst_normalized_margin"] < 1.0
        and item["pi_a_infinity"]["best_worst_normalized_margin"] < 1.0
        for item in limits["designs"]
    )
    json.dumps(summary, allow_nan=False)
    assert summary["decision"]["classification"] == (
        "transport_candidate_requires_numerical_confirmation"
    )


def test_decision_pivots_when_no_analytic_case_clears_kinematics():
    passing_design = {
        "design": "stick_0p2_power_1p0",
        "sticking_probability": 0.2,
        "source_power": 1.0,
        "all_eight_streams_pass": True,
    }
    provisional = review.decision_from_evidence([passing_design], [])
    assert provisional["classification"] == (
        "transport_no_go_requires_numerical_confirmation"
    )
    pivot = review.decision_from_evidence(
        [passing_design], [], numerically_confirmed=True,
        matched_3d_confirmed=True,
    )
    assert pivot["classification"] == "pivot_model_family"

    same_design = [{"design": "stick_0p2_power_1p0"}]
    qualified = review.decision_from_evidence(
        [passing_design], same_design, numerically_confirmed=True,
        matched_3d_confirmed=True,
    )
    assert qualified["classification"] == (
        "transport_sign_and_kinematics_qualified"
    )

    needs_3d = review.decision_from_evidence(
        [passing_design], same_design, numerically_confirmed=True
    )
    assert needs_3d["classification"] == (
        "transport_candidate_requires_matched_3d_confirmation"
    )

    different_design = review.decision_from_evidence(
        [passing_design], [{"design": "stick_0p5_power_1p0"}]
    )
    assert different_design["classification"] == (
        "targeted_kinetic_confirmation_required"
    )

    physical_boundary = {
        "design": "stick_1p0_power_1p0",
        "sticking_probability": 1.0,
        "source_power": 1.0,
        "all_eight_streams_pass": True,
    }
    boundary = review.decision_from_evidence(
        [physical_boundary], [{"design": "stick_1p0_power_1p0"}]
    )
    assert boundary["classification"] == (
        "transport_sign_physical_boundary_refinement_required"
    )
    assert boundary["boundary_warnings"][0]["factors"][0]["action"].startswith(
        "densify"
    )

    coefficient_boundary = review.decision_from_evidence(
        [passing_design],
        [{
            "design": "stick_0p2_power_1p0",
            "coefficient_boundary_details": [{
                "factor": "R_over_Va",
                "boundary": "physical_lower",
                "action": "confirm inward sensitivity at small positive R",
            }],
        }],
    )
    assert coefficient_boundary["classification"] == (
        "coefficient_physical_boundary_refinement_required"
    )


def test_exact_pi_infinity_limit_uses_saved_zero_flux_pattern():
    records = []
    design = "stick_0p2_power_1p0"
    for tier, depth in (("continuity", 1.25), ("nominal_hbm", 3.0)):
        coordinates, flux, _, _ = regional_fixture(depth)
        flux = np.ones_like(flux)
        flux[0] = 0.0
        masks = runner._authoritative_region_masks(coordinates, reference(depth))
        for seed in runner.PAIRED_BASE_SEEDS:
            records.append({
                "public": {
                    "geometry_tier": tier,
                    "design": design,
                    "kinematic_threshold_H_over_a": depth / 0.5,
                },
                "internal": {
                    "raw": {
                        "coordinates": coordinates,
                        "material_ids": np.full(
                            len(flux), float(ps.Material.Cu.legacyId())
                        ),
                        "suppressor_flux": flux,
                    },
                    "masks": masks,
                    "model": {
                        "deactivation_rate": 0.25,
                        "active_deposition_rate": 0.2,
                        "suppressed_deposition_rate": 0.01,
                    },
                    "plating_material_ids": [
                        float(ps.Material.Cu.legacyId())
                    ],
                },
            })
    limits = review.analytic_pi_limits(records, manifest())
    item = next(item for item in limits["designs"] if item["design"] == design)
    assert limits["required_region_zero_flux_point_count"] == 8
    assert item["pi_a_infinity"][
        "all_eight_streams_exceed_tier_threshold"
    ]
    assert any(item["design"] == design for item in limits[
        "cross_tier_kinematic_passes"
    ])


def test_cross_tier_summary_requires_all_four_streams_in_each_tier():
    base = {
        "design": "stick_0p2_power_1p0",
        "sticking_probability": 0.2,
        "source_power": 1.0,
        "stream_count": 4,
        "stream_pass_count": 4,
        "all_four_streams_pass": True,
    }
    all_eight = review._cross_tier_design_summaries([
        {**base, "geometry_tier": "continuity"},
        {**base, "geometry_tier": "nominal_hbm"},
    ])
    selected = next(
        item for item in all_eight if item["design"] == base["design"]
    )
    assert selected["tier_results"]["continuity"]["stream_pass_count"] == 4
    assert selected["tier_results"]["nominal_hbm"]["stream_pass_count"] == 4
    assert selected["all_eight_streams_pass"]

    nominal_miss = review._cross_tier_design_summaries([
        {**base, "geometry_tier": "continuity"},
        {
            **base,
            "geometry_tier": "nominal_hbm",
            "stream_pass_count": 3,
            "all_four_streams_pass": False,
        },
    ])
    selected = next(
        item for item in nominal_miss if item["design"] == base["design"]
    )
    assert selected["tier_results"]["continuity"]["all_four_streams_pass"]
    assert not selected["tier_results"]["nominal_hbm"]["all_four_streams_pass"]
    assert not selected["all_eight_streams_pass"]


if __name__ == "__main__":
    test_frozen_matrix_identifiability_and_disjoint_stream_contract()
    test_regions_preserve_left_right_asymmetry_and_imported_spatial_cuts()
    test_transport_boundaries_are_strict_and_every_region_is_required()
    test_mixed_zero_velocity_ratios_are_visible_and_ineligible()
    test_exact_equilibrium_law_matches_cpp_diagnostics()
    test_fingerprint_audit_requires_exact_168_and_rejects_current_errors()
    with tempfile.TemporaryDirectory() as temporary:
        test_resume_requires_success_and_a_matching_snapshot(Path(temporary))
    with tempfile.TemporaryDirectory() as temporary:
        test_complete_synthetic_review_has_no_morphology_ranking(
            Path(temporary)
        )
    test_decision_pivots_when_no_analytic_case_clears_kinematics()
    test_exact_pi_infinity_limit_uses_saved_zero_flux_pattern()
    test_cross_tier_summary_requires_all_four_streams_in_each_tier()
    print("Cu-fill transport-sign screen tests: PASS")

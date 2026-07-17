"""Small deterministic checks for the pre-DOE CMP qualification harness."""

from dataclasses import replace

import numpy as np
import viennaps as ps

import foundation_cmp_qualification as cmpq


# Test-only decision limits exercise the gate logic.  They are not process
# specifications and are deliberately not installed as research defaults.
TEST_SURVIVAL_THRESHOLDS = {
    "minimum_stop_retained_thickness": 0.020,
    "maximum_stop_erosion": 0.010,
    "maximum_plug_height_loss": 0.005,
    "maximum_plug_area_loss_fraction": 0.005,
}


def evaluate(post, pre, **threshold_overrides):
    thresholds = dict(TEST_SURVIVAL_THRESHOLDS)
    thresholds.update(threshold_overrides)
    return cmpq.evaluate_hard_gates(
        post,
        pre,
        survival_thresholds=thresholds,
    )


def test_height_material_law_is_smooth_deterministic_and_material_selective():
    law = cmpq.HeightMaterialRemovalLaw(
        stop_y=0.03,
        compliance_length=0.10,
        residual_contact=0.05,
        material_rate_ratios={
            ps.Material.Cu: 1.0,
            cmpq.CU_SEED_MATERIAL: 0.8,
            ps.Material.TaN: 0.25,
            ps.Material.SiO2: 0.01,
            ps.Material.Si: 0.01,
        },
    )
    heights = np.linspace(-0.02, 0.18, 21)
    weights = np.asarray([law.contact_weight(height) for height in heights])
    assert np.all(np.diff(weights) >= 0.0)
    assert np.isclose(weights[0], 0.05)
    assert np.isclose(weights[-1], 1.0)
    assert np.isclose(
        law.normal_velocity(0.08, ps.Material.TaN),
        0.25 * law.normal_velocity(0.08, ps.Material.Cu),
    )
    assert law.normal_velocity(0.08, ps.Material.Cu) < 0.0
    assert law.normal_velocity(0.08, ps.Material.Cu) == law.normal_velocity(
        0.08, ps.Material.Cu
    )
    assert "uncalibrated" in law.evidence_label
    assert "not pad-pressure physics" in law.evidence_label


def test_full_stack_variants_have_distinct_materials_and_no_pattern_mask():
    expected_tops = {
        "flat": 0.18,
        "thick_flat": 0.33,
        "raised_shoulders": 0.23,
        "raised_plug": 0.23,
        "asymmetric": 0.23,
    }
    for name, expected_top in expected_tops.items():
        stack = cmpq.build_analytic_stack(name, grid_delta=0.01)
        assert stack.topography == name
        assert stack.pattern_mask_absent
        assert stack.materials == (
            ps.Material.Si,
            ps.Material.SiO2,
            ps.Material.TaN,
            cmpq.CU_SEED_MATERIAL,
            ps.Material.Cu,
        )
        assert np.isclose(stack.stop_y, 0.03, atol=0.011)
        assert np.isclose(stack.cu_top_y, expected_top, atol=0.011)


def test_native_controls_are_declared_exact_and_combined_advection_is_blocked():
    assert cmpq.QUALIFICATION_NUMERICS["grid_pair"] == (0.0025, 0.00125)
    assert cmpq.QUALIFICATION_NUMERICS["overpolish_doses"][-1] == 0.030
    capabilities = cmpq.control_capabilities()
    assert capabilities["planarize_ideal"]["exact"]
    assert capabilities["cu_only_isotropic"]["exact"]
    assert capabilities["uniform_material_selective"]["exact"]
    assert capabilities["height_only_equal_material"]["exact"]
    assert capabilities["destructive_one_rate"]["exact"]
    law = cmpq.default_candidate_law(stop_y=0.03)
    if hasattr(ps, "HeightMaterialCMP"):
        assert capabilities["combined_height_material"]["exact"]
        assert isinstance(
            cmpq.make_combined_viennaps_model(law),
            ps.HeightMaterialCMP,
        )
    else:
        assert not capabilities["combined_height_material"]["exact"]
        try:
            cmpq.make_combined_viennaps_model(law)
        except cmpq.ExactControlUnavailable as error:
            assert "coordinate" in str(error)
            assert "material" in str(error)
        else:
            raise AssertionError("combined model must not silently approximate")


def test_exact_native_process_controls_execute_on_the_full_stack():
    for arm in (
        "cu_only_isotropic",
        "uniform_material_selective",
        "height_only_equal_material",
    ):
        stack = cmpq.build_analytic_stack("flat", grid_delta=0.01)
        initial_top = stack.cu_top_y
        cmpq.apply_native_control(stack, arm, duration=0.001)
        after = cmpq.profile_from_geometry(stack)
        assert np.max(after.cu_top_y) < initial_top


def test_ideal_planarize_preserves_regions_at_both_qualification_grids():
    for grid_delta in cmpq.QUALIFICATION_NUMERICS["grid_pair"]:
        stack = cmpq.build_analytic_stack(
            "raised_shoulders", grid_delta=grid_delta
        )
        before = cmpq.profile_from_geometry(stack)
        assert np.max(np.diff(before.x)) <= 0.5 * stack.grid_delta + 1e-12
        cmpq.apply_native_control(stack, "planarize_ideal")
        after = cmpq.profile_from_geometry(stack)
        blocked = cmpq.evaluate_hard_gates(after, before)
        assert blocked["qualification_blocked"]
        assert not blocked["research_survival_thresholds_declared"]
        assert len(blocked["qualification_blocked_reasons"]) == 4
        assert not blocked["all_hard_gates_pass"]

        metrics = evaluate(after, before)
        assert metrics["plated_cu_first_clear"]
        assert metrics["all_field_metals_clear"]
        assert metrics["field_plated_cu_clear"]
        assert metrics["field_seed_clear"]
        assert metrics["field_tan_clear"]
        assert metrics["stop_continuous"]
        assert metrics["plug_connected"]
        assert metrics["substrate_survives"]
        assert metrics["liner_connectivity_resolved"]
        assert metrics["barrier_connectivity_resolved"]
        assert metrics["seed_connectivity_resolved"]
        assert metrics["plug_connectivity_resolved"]
        assert metrics["liner_continuous"]
        assert metrics["barrier_continuous"]
        assert metrics["seed_continuous"]
        assert metrics["dish"] <= metrics["detection_limit"]
        assert metrics["protrusion"] <= metrics["detection_limit"]


def test_destructive_control_remains_visible_as_substrate_and_stop_loss():
    stack = cmpq.build_analytic_stack("flat", grid_delta=0.01)
    before = cmpq.profile_from_geometry(stack)
    cmpq.apply_native_control(stack, "destructive_one_rate")
    after = cmpq.profile_from_geometry(stack)
    metrics = evaluate(after, before)
    assert metrics["valid"]
    assert not metrics["stop_continuous"]
    assert metrics["substrate_loss"] > 0.10
    assert not metrics["substrate_survives"]
    assert not metrics["all_hard_gates_pass"]


def test_synthetic_hidden_residual_island_and_under_clear_fail_endpoint():
    before, ideal = cmpq.synthetic_profiles()
    island = cmpq.synthetic_failure(ideal, "hidden_residual_island")
    island_metrics = evaluate(island, before)
    assert not island_metrics["field_plated_cu_clear"]
    assert island_metrics["residual_field_plated_cu_max"] > 0.0

    under_clear = cmpq.synthetic_failure(ideal, "under_clear")
    under_metrics = evaluate(under_clear, before)
    assert not under_metrics["endpoint_reached"]
    assert not under_metrics["all_hard_gates_pass"]


def test_synthetic_local_stop_breach_and_disconnected_plug_fail_survival():
    before, ideal = cmpq.synthetic_profiles()
    breached = cmpq.synthetic_failure(ideal, "local_stop_breach")
    breach_metrics = evaluate(breached, before)
    assert not breach_metrics["stop_continuous"]
    assert not breach_metrics["all_protected_materials_survive"]

    disconnected = cmpq.synthetic_failure(ideal, "disconnected_plug")
    disconnected_metrics = evaluate(disconnected, before)
    assert not disconnected_metrics["plug_connected"]
    assert not disconnected_metrics["all_hard_gates_pass"]


def test_synthetic_dish_and_protrusion_are_independent_outputs():
    before, ideal = cmpq.synthetic_profiles()
    dished = cmpq.synthetic_failure(ideal, "dish")
    dish_metrics = evaluate(
        dished,
        before,
        maximum_plug_height_loss=0.020,
        maximum_plug_area_loss_fraction=0.020,
    )
    assert dish_metrics["dish"] > 0.0
    assert dish_metrics["protrusion"] == 0.0
    assert not dish_metrics["planarity_within_detection"]
    assert dish_metrics["all_hard_gates_pass"]
    assert not dish_metrics["all_step_targets_pass"]

    protruding = cmpq.synthetic_failure(ideal, "protrusion")
    protrusion_metrics = evaluate(protruding, before)
    assert protrusion_metrics["dish"] == 0.0
    assert protrusion_metrics["protrusion"] > 0.0
    assert not protrusion_metrics["planarity_within_detection"]
    assert protrusion_metrics["all_hard_gates_pass"]
    assert not protrusion_metrics["all_step_targets_pass"]


def test_synthetic_layer_minimums_and_plug_loss_are_reported():
    before, ideal = cmpq.synthetic_profiles()
    thinned = replace(
        ideal,
        liner_thickness=np.full_like(ideal.x, 0.019),
        barrier_thickness=np.full_like(ideal.x, 0.006),
        seed_thickness=np.full_like(ideal.x, 0.005),
    )
    metrics = evaluate(thinned, before)
    assert not metrics["liner_functional_minimum"]
    assert not metrics["barrier_seed_functional_minimum"]
    assert metrics["plug_height_loss"] >= 0.0
    assert metrics["plug_area_loss"] >= 0.0


def test_y_spans_are_diagnostic_not_the_connectivity_gate():
    before, ideal = cmpq.synthetic_profiles()
    split = replace(
        ideal,
        liner_component_y_spans=((-1.25, -0.60), (-0.50, 0.030)),
    )
    metrics = evaluate(split, before)
    assert metrics["valid"]
    assert metrics["liner_continuous"]
    assert metrics["structural_survival_pass"]


def test_unresolved_region_connectivity_cannot_pass_continuity():
    before, ideal = cmpq.synthetic_profiles()
    unresolved = replace(
        ideal,
        liner_region_connectivity={
            "resolved": False,
            "unresolved_reasons": (
                "local_thickness_at_or_below_resolution_limit",
            ),
            "negative_component_count": 1,
            "floor_to_both_mouths_connected": False,
            "detached_fragment_count": 0,
        },
    )
    metrics = evaluate(unresolved, before)
    assert metrics["valid"]
    assert not metrics["liner_connectivity_resolved"]
    assert not metrics["liner_continuous"]
    assert not metrics["structural_survival_pass"]


def test_one_cell_barrier_and_seed_are_unresolved_before_a_connectivity_decision():
    profile = cmpq.profile_from_geometry(
        cmpq.build_analytic_stack("flat", grid_delta=0.01)
    )
    for connectivity in (
        profile.barrier_region_connectivity,
        profile.seed_region_connectivity,
    ):
        assert connectivity["negative_component_count"] >= 1
        assert not connectivity["resolved"]
        assert not connectivity["floor_to_both_mouths_connected"]
        assert "local_thickness_at_or_below_resolution_limit" in (
            connectivity["unresolved_reasons"]
        )


def test_residual_detection_boundary_and_endpoint_names_are_explicit():
    before, ideal = cmpq.synthetic_profiles()
    field = ideal.field_mask
    for residual_cells in (0.5, 1.0, 2.0):
        cu = ideal.cu_top_y.copy()
        cu[field] += residual_cells * ideal.grid_delta
        metrics = evaluate(replace(ideal, cu_top_y=cu), before)
        assert metrics["plated_cu_first_clear"]
        assert metrics["all_field_metals_clear"]

    cu = ideal.cu_top_y.copy()
    cu[field] += 2.01 * ideal.grid_delta
    above_limit = evaluate(replace(ideal, cu_top_y=cu), before)
    assert not above_limit["plated_cu_first_clear"]
    assert not above_limit["all_field_metals_clear"]

    seed = ideal.seed_top_y.copy()
    seed[field] += 0.005
    cu = ideal.cu_top_y.copy()
    cu[field] = seed[field]
    plated_only = evaluate(
        replace(ideal, seed_top_y=seed, cu_top_y=cu), before
    )
    assert plated_only["plated_cu_first_clear"]
    assert not plated_only["field_seed_clear"]
    assert not plated_only["all_field_metals_clear"]
    assert not plated_only["survival_window_checkpoint_pass"]


def test_almost_consumed_stop_and_excessive_plug_loss_fail_declared_limits():
    before, ideal = cmpq.synthetic_profiles()
    field = ideal.field_mask
    stop = ideal.stop_top_y.copy()
    stop[field] = ideal.substrate_y[field] + 2.5 * ideal.grid_delta
    barrier = ideal.barrier_top_y.copy()
    seed = ideal.seed_top_y.copy()
    cu = ideal.cu_top_y.copy()
    barrier[field] = stop[field]
    seed[field] = stop[field]
    cu[field] = stop[field]
    almost_consumed = replace(
        ideal,
        stop_top_y=stop,
        barrier_top_y=barrier,
        seed_top_y=seed,
        cu_top_y=cu,
    )
    stop_metrics = evaluate(almost_consumed, before)
    assert stop_metrics["stop_continuous"]
    assert not stop_metrics["stop_retention_within_research_limit"]
    assert not stop_metrics["stop_erosion_within_research_limit"]
    assert not stop_metrics["survival_hard_gates_pass"]

    cu = ideal.cu_top_y.copy()
    cu[ideal.via_mask] -= 0.010
    plug_loss = replace(ideal, cu_top_y=cu)
    plug_metrics = evaluate(plug_loss, before)
    assert plug_metrics["plug_connected"]
    assert not plug_metrics["plug_height_loss_within_research_limit"]
    assert not plug_metrics["plug_area_loss_within_research_limit"]
    assert not plug_metrics["survival_hard_gates_pass"]


def test_inversion_missing_erased_and_unexpected_component_states_are_invalid():
    before, ideal = cmpq.synthetic_profiles()
    barrier = ideal.barrier_top_y.copy()
    index = np.flatnonzero(ideal.field_mask)[0]
    barrier[index] = ideal.stop_top_y[index] - ideal.grid_delta
    inversion = evaluate(replace(ideal, barrier_top_y=barrier), before)
    assert not inversion["valid"]
    assert (
        "post:interface_inversion:stop_top_y>barrier_top_y"
        in inversion["invalid_reasons"]
    )
    assert not inversion["all_hard_gates_pass"]

    missing = evaluate(
        replace(
            ideal,
            cu_region_connectivity={
                "resolved": False,
                "unresolved_reasons": ("no_negative_material_component",),
                "negative_component_count": 0,
                "floor_to_both_mouths_connected": False,
                "detached_fragment_count": 0,
            },
        ),
        before,
    )
    assert not missing["valid"]
    assert (
        "post:missing_material_component:plated_cu"
        in missing["invalid_reasons"]
    )

    erased = evaluate(
        replace(
            ideal,
            liner_region_connectivity={
                "resolved": False,
                "unresolved_reasons": ("no_negative_material_component",),
                "negative_component_count": 0,
                "floor_to_both_mouths_connected": False,
                "detached_fragment_count": 0,
            },
            barrier_region_connectivity={
                "resolved": False,
                "unresolved_reasons": ("no_negative_material_component",),
                "negative_component_count": 0,
                "floor_to_both_mouths_connected": False,
                "detached_fragment_count": 0,
            },
            seed_region_connectivity={
                "resolved": False,
                "unresolved_reasons": ("no_negative_material_component",),
                "negative_component_count": 0,
                "floor_to_both_mouths_connected": False,
                "detached_fragment_count": 0,
            },
            cu_region_connectivity={
                "resolved": False,
                "unresolved_reasons": ("no_negative_material_component",),
                "negative_component_count": 0,
                "floor_to_both_mouths_connected": False,
                "detached_fragment_count": 0,
            },
        ),
        before,
    )
    assert not erased["valid"]
    assert "post:empty_or_erased_geometry" in erased["invalid_reasons"]

    unexpected = evaluate(
        replace(
            ideal,
            barrier_region_connectivity={},
            geometry_invalid_reasons=("unexpected_material_state:W",),
        ),
        before,
    )
    assert not unexpected["valid"]
    assert (
        "post:unexpected_connectivity_state:barrier"
        in unexpected["invalid_reasons"]
    )
    assert "post:unexpected_material_state:W" in unexpected["invalid_reasons"]


if __name__ == "__main__":
    test_height_material_law_is_smooth_deterministic_and_material_selective()
    test_full_stack_variants_have_distinct_materials_and_no_pattern_mask()
    test_native_controls_are_declared_exact_and_combined_advection_is_blocked()
    test_exact_native_process_controls_execute_on_the_full_stack()
    test_ideal_planarize_preserves_regions_at_both_qualification_grids()
    test_destructive_control_remains_visible_as_substrate_and_stop_loss()
    test_synthetic_hidden_residual_island_and_under_clear_fail_endpoint()
    test_synthetic_local_stop_breach_and_disconnected_plug_fail_survival()
    test_synthetic_dish_and_protrusion_are_independent_outputs()
    test_synthetic_layer_minimums_and_plug_loss_are_reported()
    test_y_spans_are_diagnostic_not_the_connectivity_gate()
    test_unresolved_region_connectivity_cannot_pass_continuity()
    test_one_cell_barrier_and_seed_are_unresolved_before_a_connectivity_decision()
    test_residual_detection_boundary_and_endpoint_names_are_explicit()
    test_almost_consumed_stop_and_excessive_plug_loss_fail_declared_limits()
    test_inversion_missing_erased_and_unexpected_component_states_are_invalid()
    print("foundation CMP qualification checks: PASS")

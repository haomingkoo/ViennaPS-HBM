"""Prelaunch guards for the staged full-width layer acceptance design."""

import json
from pathlib import Path


SPEC_PATH = Path(
    ".scratch/full-traveler-autoresearch/"
    "layer_model_acceptance_design_spec.json"
)


def load_spec():
    return json.loads(SPEC_PATH.read_text())


def test_authority_and_prerequisites_fail_closed():
    spec = load_spec()
    assert set(spec["labels"]) == {"full-traveler", "critical-review"}
    assert spec["status"] == "design_only_not_launchable"
    assert spec["authority"] == {
        "may_authorize": "exploratory_layer_response_screen_only",
        "automatic_launch_authorized": False,
        "recipe_authorized": False,
        "process_window_authorized": False,
        "full_traveler_authorized": False,
    }
    prerequisites = {item["artifact"] for item in spec["prerequisites"]}
    assert {
        "autoresearch-results/restart_audit/pattern_bosch_gate0_summary.json",
        "autoresearch-results/restart_audit/pattern_bosch_handoff_summary.json",
        "material-region layer connectivity guard",
    } <= prerequisites
    assert len(spec["launch_blockers"]) == 3
    assert any("exit-139" in item for item in spec["launch_blockers"])


def test_fixed_targets_and_shared_full_width_geometries():
    spec = load_spec()
    upstream = spec["upstream_geometry"]
    assert upstream["source_arm"] == "full_reference_fine"
    assert upstream["shape"] == "FULL 2D cross-section"
    assert upstream["rng_seeds"] == [61000, 62000, 63000, 64000]
    assert upstream["shape_count"] == 4
    assert spec["numerics"]["full_width_required"] is True
    assert spec["fixed_targets"]["liner"] == {
        "minimum_local_thickness": 0.02,
        "minimum_floor_to_field_conformality": 0.995,
        "minimum_lower_wall_to_field_conformality": 0.995,
        "material_region_connected_field_to_floor": True,
        "aperture_open": True,
    }
    stack = spec["fixed_targets"]["barrier_seed"]
    assert stack["combined_minimum_local_thickness"] == 0.012
    assert stack["minimum_floor_to_field_conformality_each_layer"] == 0.985
    assert stack["minimum_lower_wall_to_field_conformality_each_layer"] == 0.985
    assert stack["barrier_material_region_connected_field_to_floor"] is True
    assert stack["seed_material_region_connected_field_to_floor"] is True


def test_case_counts_and_surface_designs_are_exact():
    spec = load_spec()
    stages = {stage["id"]: stage for stage in spec["stages"]}
    l0 = stages["L0"]
    expected_l0 = (
        len(l0["model_families"])
        * len(l0["sticking_probabilities"])
        * len(l0["rays_per_point"])
        * len(l0["max_reflections"])
        * len(l0["deposition_seed_labels"])
    )
    assert expected_l0 == l0["full_factorial_cases"] == 48

    l1 = stages["L1"]
    single, teos, control = l1["arms"]
    assert single["arm_count"] == (
        len(single["dose"]) * len(single["sticking_probability"])
    ) == 15
    assert teos["arm_count"] == (
        len(teos["dose"])
        * len(teos["sticking_probability"])
        * len(teos["reaction_order"])
    ) == 48
    assert control["arm_count"] == len(control["dose"]) == 3
    assert control["recipe_eligible"] is False
    assert l1["surface_cases"] == 4 * (15 + 48 + 3) == 264

    l3 = stages["L3"]
    directionality, dose = l3["interaction_blocks"]
    assert directionality["arm_count"] == (
        len(directionality["barrier_isotropic_fraction"])
        * len(directionality["seed_isotropic_fraction"])
    ) == 25
    assert dose["arm_count"] == (
        len(dose["barrier_field_dose"])
        * len(dose["seed_field_dose"])
    ) == 16
    assert l3["surface_cases"] == 2 * 4 * (25 + 16) == 328

    counts = spec["case_counts"]
    assert counts["fixed_preconfirmation"] == 48 + 264 + 328 == 640
    assert counts["maximum_adaptive_confirmation"] == 96 + 96 == 192
    assert counts["maximum_total"] == 832


def test_invalids_boundaries_and_ideal_controls_cannot_win():
    spec = load_spec()
    assert spec["metric_contract"]["invalid_policy"].startswith(
        "Keep invalid rows visible"
    )
    assert spec["decision_order"][:3] == [
        "valid simulation and finite independently recomputed metrics",
        "material-region connectivity and open aperture",
        "fixed liner or barrier/seed product gates",
    ]
    assert any(
        "ideal isotropic control" in boundary.lower()
        and "never recipe eligible" in boundary.lower()
        for boundary in spec["model_boundaries"]
    )
    l3_rule = next(
        stage["decision_rule"] for stage in spec["stages"]
        if stage["id"] == "L3"
    )
    assert "fractions at or above 0.9" in l3_rule
    assert "not an iPVD recipe" in l3_rule


if __name__ == "__main__":
    test_authority_and_prerequisites_fail_closed()
    test_fixed_targets_and_shared_full_width_geometries()
    test_case_counts_and_surface_designs_are_exact()
    test_invalids_boundaries_and_ideal_controls_cannot_win()
    print("layer model-acceptance design checks: PASS")

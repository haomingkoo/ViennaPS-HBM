"""Guards for the broad pattern/Bosch screening design."""

import copy

import viennaps as ps

import build_pattern_bosch_screen_design as screen
import traveler_metrics as tm
import tsv_process as tp


def test_design_is_deterministic_broad_and_depth_matched():
    spec = screen.strict_load(screen.DEFAULT_SPEC)
    first = screen.build_design(spec)
    second = screen.build_design(spec)
    assert first == second
    assert screen.validate_design(first, spec) == []
    assert first["design"]["recipe_count"] == 160
    assert first["design"]["logical_simulation_count"] == 640
    assert first["design"]["anchor_count"] >= 27
    assert first["design"]["maximum_absolute_lhs_factor_correlation"] < 0.20
    assert first["trajectory"]["record_all_scored_cycles"]
    assert first["trajectory"]["first_scored_cycle"] == 1
    assert first["trajectory"]["maximum_cycles"] == 50
    assert first["trajectory"]["early_stop_depth"] == 1.45
    assert first["rng_process_seed_horizon"] == 151
    assert "depth" in first["trajectory"]["selection"]
    assert "num_cycles" not in {factor["name"] for factor in first["factors"]}
    assert all(
        row["recipe"]["mask_height"] == 0.3
        for row in first["recipes"]
        if row["design_class"] == "latin_hypercube"
    )
    assert first["authority"]["automatic_launch_authorized"] is False
    assert first["authority"]["recipe_authorized"] is False
    assert first["review"]["invalid_metric_penalty"] > (
        len(first["review"]["primitive_gates"])
        * first["review"]["primitive_hard_gate_penalty"]
    )


def test_every_factor_boundary_and_four_disjoint_streams_are_present():
    spec = screen.strict_load(screen.DEFAULT_SPEC)
    design = screen.build_design(spec)
    reasons = {
        reason for row in design["recipes"]
        for reason in row["anchor_reasons"]
    }
    for factor in spec["factors"]:
        assert f"{factor['name']}:low" in reasons
        assert f"{factor['name']}:high" in reasons
    assert {
        reason for reason in reasons if reason.startswith("mask_height_erosion:")
    } == {
        f"mask_height_erosion:{height:g}:{erosion:g}"
        for height in (0.24, 0.27, 0.3, 0.33, 0.36)
        for erosion in (0.0, -0.01, -0.02, -0.04)
    }
    horizon = design["rng_process_seed_horizon"]
    seeds = design["rng_base_seeds"]
    assert len(seeds) == 4
    assert all(
        abs(first - second) >= horizon
        for index, first in enumerate(seeds)
        for second in seeds[index + 1:]
    )


def test_taper_stress_endpoints_create_resolved_full_width_masks():
    for taper in (-4.0, 6.0):
        geometry = tp.make_initial_geometry(
            radius=0.15,
            mask_height=0.3,
            grid_delta=0.01,
            x_extent=1.0,
            y_extent=2.0,
            taper=taper,
            hole_shape=ps.HoleShape.FULL,
        )
        mask = tm.material_region_mesh(geometry, ps.Material.Mask)
        metrics = tm.pattern_metrics_2d(
            mask["nodes"], mask["lines"],
            surface_y=0.0, target_cd=0.3, target_mask_height=0.3,
        )
        assert metrics["geometry_kind"] == "full"
        assert metrics["opening_valid"]


def test_target_or_authority_mutation_fails_closed():
    spec = screen.strict_load(screen.DEFAULT_SPEC)
    changed = copy.deepcopy(spec)
    changed["target"]["opening_cd"] = 0.31
    try:
        screen.build_design(changed)
    except ValueError as error:
        assert "product targets differ" in str(error)
    else:
        raise AssertionError("changed target was accepted")

    changed = copy.deepcopy(spec)
    changed["authority"]["recipe_authorized"] = True
    try:
        screen.build_design(changed)
    except ValueError as error:
        assert "authority was expanded" in str(error)
    else:
        raise AssertionError("expanded authority was accepted")


if __name__ == "__main__":
    test_design_is_deterministic_broad_and_depth_matched()
    test_every_factor_boundary_and_four_disjoint_streams_are_present()
    test_taper_stress_endpoints_create_resolved_full_width_masks()
    test_target_or_authority_mutation_fails_closed()
    print("pattern/Bosch broad-screen design checks: PASS")

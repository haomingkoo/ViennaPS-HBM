"""Mechanism and parameterization guards for layer model alternatives."""

import math

import viennaps as ps

import full_2d_layer_metrics as fullfilm
import layer_process_models as models
import traveler_metrics as tm


ps.Logger.setLogLevel(ps.LogLevel.ERROR)


def via(grid_delta=0.01):
    geometry = ps.Domain(gridDelta=grid_delta, xExtent=1.0, yExtent=1.5)
    ps.MakeHole(
        domain=geometry,
        holeRadius=0.15,
        holeDepth=1.0,
        maskHeight=0.0,
        maskTaperAngle=0.0,
        holeShape=ps.HoleShape.FULL,
    ).apply()
    return geometry


def copy(geometry):
    result = ps.Domain()
    result.deepCopy(geometry)
    return result


def layer_metrics(geometry, inner, material):
    outer = tm.raw_level_set_meshes(geometry)[-1]
    assert outer["material"] == material
    return fullfilm.layer_thickness_metrics_full_2d(
        inner["nodes"], inner["lines"],
        outer["nodes"], outer["lines"],
        surface_y=0.0, floor_y=-1.0, via_radius=0.15,
    )


def test_directional_fraction_holds_field_dose_constant():
    assert models.directional_components(0.04, 0.0) == (0.04, 0.0)
    assert models.directional_components(0.04, 1.0) == (0.0, 0.04)
    assert models.directional_components(0.04, 0.5) == (0.02, 0.02)

    base = via()
    inner = tm.material_region_mesh(base, ps.Material.Si)
    directional = copy(base)
    models.deposit_directional_fraction(
        directional, ps.Material.TaN,
        field_dose=0.04, isotropic_fraction=0.0,
    )
    isotropic = copy(base)
    models.deposit_directional_fraction(
        isotropic, ps.Material.TaN,
        field_dose=0.04, isotropic_fraction=1.0,
    )
    directional_metrics = layer_metrics(directional, inner, ps.Material.TaN)
    isotropic_metrics = layer_metrics(isotropic, inner, ps.Material.TaN)
    assert math.isclose(
        directional_metrics["field_thickness"],
        isotropic_metrics["field_thickness"],
        abs_tol=0.012,
    )
    assert directional_metrics["lower_wall_to_field_conformality"] < 0.1
    assert isotropic_metrics["lower_wall_to_field_conformality"] > 0.9


def test_teos_order_one_is_not_assumed_equivalent_to_single_particle():
    base = via(grid_delta=0.02)
    inner = tm.material_region_mesh(base, ps.Material.Si)
    single = copy(base)
    models.deposit_single_particle(
        single, ps.Material.SiO2,
        dose=0.04, sticking_probability=0.01,
        rays_per_point=500, rng_seed=123,
    )
    teos = copy(base)
    models.deposit_teos(
        teos, ps.Material.SiO2,
        dose=0.04, sticking_probability=0.01, reaction_order=1.0,
        rays_per_point=500, rng_seed=123,
    )
    single_metrics = layer_metrics(single, inner, ps.Material.SiO2)
    teos_metrics = layer_metrics(teos, inner, ps.Material.SiO2)
    differences = {
        key: abs(single_metrics[key] - teos_metrics[key])
        for key in (
            "minimum_local_thickness",
            "floor_to_field_conformality",
            "lower_wall_to_field_conformality",
            "minimum_remaining_aperture",
        )
    }
    assert differences["floor_to_field_conformality"] > 0.005
    assert all(math.isfinite(value) for value in differences.values())
    assert max(differences.values()) < 0.05


def test_isotropic_control_and_invalid_parameters():
    base = via()
    inner = tm.material_region_mesh(base, ps.Material.Si)
    control = copy(base)
    models.deposit_isotropic_control(control, ps.Material.SiO2, dose=0.03)
    metrics = layer_metrics(control, inner, ps.Material.SiO2)
    assert metrics["floor_to_field_conformality"] > 0.9
    assert metrics["lower_wall_to_field_conformality"] > 0.9

    for fraction in (-0.1, 1.1):
        try:
            models.directional_components(0.04, fraction)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid isotropic fraction was accepted")


if __name__ == "__main__":
    test_directional_fraction_holds_field_dose_constant()
    test_teos_order_one_is_not_assumed_equivalent_to_single_particle()
    test_isotropic_control_and_invalid_parameters()
    print("layer process-model checks: PASS")

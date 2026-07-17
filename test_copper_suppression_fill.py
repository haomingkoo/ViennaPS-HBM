"""Focused qualification checks for the reduced suppressor-fill candidate."""

import numpy as np
import viennals as ls
import viennals.d2 as ls2
import viennaps as ps

import traveler_metrics as tm
import tsv_process as tp


def ray_parameters(seed=731, rays=1000):
    ray = ps.RayTracingParameters()
    ray.useRandomSeeds = False
    ray.rngSeed = seed
    ray.raysPerPoint = rays
    return ray


def set_process_parameters(process, *, seed=731, rays=1000, ignore_voids=True):
    process.setParameters(ray_parameters(seed=seed, rays=rays))
    advection = ps.AdvectionParameters()
    advection.ignoreVoids = ignore_voids
    process.setParameters(advection)


def candidate_parameters(*, adsorption_strength, plating_materials, sticking=0.2):
    params = ps.CopperSuppressionFillParams()
    params.suppressorStickingProbability = sticking
    params.suppressorSourcePower = 1.0
    params.adsorptionStrength = adsorption_strength
    params.deactivationRate = 0.25
    params.activeDepositionRate = 0.20
    params.suppressedDepositionRate = 0.01
    params.platingMaterials = plating_materials
    return params


def run_flat(adsorption_strength, *, plating_materials, sticking=0.2):
    geometry = ps.Domain(gridDelta=0.02, xExtent=0.5, yExtent=0.5)
    ps.MakePlane(geometry, height=0.0, material=ps.Material.Si).apply()
    geometry.duplicateTopLevelSet(ps.Material.Cu)
    model = ps.CopperSuppressionFill(candidate_parameters(
        adsorption_strength=adsorption_strength,
        plating_materials=plating_materials,
        sticking=sticking,
    ))
    process = ps.Process(geometry, model, 0.05)
    set_process_parameters(process)
    process.apply()
    return {
        "coverage": np.asarray(model.getLastCoverage(), dtype=float),
        "velocity": np.asarray(model.getLastVelocity(), dtype=float),
        "relative_balance_error": float(model.getLastRelativeBalanceError()),
    }


def run_via(seed=811, adsorption_strength=5.0):
    radius = 0.15
    geometry = ps.Domain(gridDelta=0.02, xExtent=1.0, yExtent=1.5)
    ps.MakeHole(
        domain=geometry,
        holeRadius=radius,
        holeDepth=1.25,
        maskHeight=0.3,
        holeShape=ps.HoleShape.FULL,
    ).apply()
    tp.strip_pattern_mask(geometry)
    geometry.duplicateTopLevelSet(tp.CU_SEED_MATERIAL)
    ps.Process(geometry, ps.IsotropicProcess(rate=0.01), 1.0).apply()
    geometry.duplicateTopLevelSet(ps.Material.Cu)

    params = candidate_parameters(
        adsorption_strength=adsorption_strength,
        plating_materials=[tp.CU_SEED_MATERIAL, ps.Material.Cu],
    )
    model = ps.CopperSuppressionFill(params)
    process = ps.Process(geometry, model, 0.03)
    set_process_parameters(process, seed=seed, rays=2000)
    process.apply()

    coordinates = np.asarray(model.getLastCoordinates(), dtype=float)
    flux = np.asarray(model.getLastSuppressorFlux(), dtype=float)
    theta = np.asarray(model.getLastCoverage(), dtype=float)
    velocity = np.asarray(model.getLastVelocity(), dtype=float)
    field = (np.abs(coordinates[:, 0]) > 0.30) & (coordinates[:, 1] > -0.10)
    floor = (np.abs(coordinates[:, 0]) < 0.10) & (coordinates[:, 1] < -1.10)
    assert np.any(field), "no field diagnostic points"
    assert np.any(floor), "no via-floor diagnostic points"
    return {
        "field_flux": float(np.mean(flux[field])),
        "floor_flux": float(np.mean(flux[floor])),
        "field_coverage": float(np.mean(theta[field])),
        "floor_coverage": float(np.mean(theta[floor])),
        "field_velocity": float(np.mean(velocity[field])),
        "floor_velocity": float(np.mean(velocity[floor])),
        "coverage_min": float(np.min(theta)),
        "coverage_max": float(np.max(theta)),
        "relative_balance_error": float(model.getLastRelativeBalanceError()),
    }


def run_matched_convex_concave_access(seed=919):
    bounds = (-1.2, 1.2, -0.8, 0.8)
    boundary_conditions = (
        ls.BoundaryConditionEnum.REFLECTIVE_BOUNDARY,
        ls.BoundaryConditionEnum.INFINITE_BOUNDARY,
    )
    surface = ls2.Domain(bounds, boundary_conditions, 0.01)
    ls2.MakeGeometry(
        surface,
        ls2.Plane((0.0, 0.0), (0.0, 1.0)),
    ).apply()

    convex_cap = ls2.Domain(bounds, boundary_conditions, 0.01)
    ls2.MakeGeometry(
        convex_cap,
        ls2.Sphere((-0.5, 0.0), 0.25),
    ).apply()
    ls2.BooleanOperation(
        surface,
        convex_cap,
        ls.BooleanOperationEnum.UNION,
    ).apply()

    concave_bowl = ls2.Domain(bounds, boundary_conditions, 0.01)
    ls2.MakeGeometry(
        concave_bowl,
        ls2.Sphere((0.5, 0.0), 0.25),
    ).apply()
    ls2.BooleanOperation(
        surface,
        concave_bowl,
        ls.BooleanOperationEnum.RELATIVE_COMPLEMENT,
    ).apply()

    geometry = ps.Domain(
        bounds=bounds,
        boundaryConditions=boundary_conditions,
        gridDelta=0.01,
    )
    geometry.insertNextLevelSetAsMaterial(surface, ps.Material.Cu)
    model = ps.CopperSuppressionFill(candidate_parameters(
        adsorption_strength=0.25,
        plating_materials=[ps.Material.Cu],
    ))
    process = ps.Process(geometry, model, 0.005)
    set_process_parameters(process, seed=seed, rays=1000)
    process.apply()

    coordinates = np.asarray(model.getLastCoordinates(), dtype=float)
    flux = np.asarray(model.getLastSuppressorFlux(), dtype=float)
    coverage = np.asarray(model.getLastCoverage(), dtype=float)
    velocity = np.asarray(model.getLastVelocity(), dtype=float)
    cap_crown = (
        (np.abs(coordinates[:, 0] + 0.5) < 0.08)
        & (coordinates[:, 1] > 0.20)
    )
    bowl_floor = (
        (np.abs(coordinates[:, 0] - 0.5) < 0.08)
        & (coordinates[:, 1] < -0.20)
    )
    assert np.count_nonzero(cap_crown) >= 10
    assert np.count_nonzero(bowl_floor) >= 10
    return {
        "cap_flux": float(np.mean(flux[cap_crown])),
        "bowl_flux": float(np.mean(flux[bowl_floor])),
        "cap_coverage": float(np.mean(coverage[cap_crown])),
        "bowl_coverage": float(np.mean(coverage[bowl_floor])),
        "cap_velocity": float(np.mean(velocity[cap_crown])),
        "bowl_velocity": float(np.mean(velocity[bowl_floor])),
        "relative_balance_error": float(model.getLastRelativeBalanceError()),
    }


def run_sealed_void_control(*, ignore_voids):
    bounds = (-0.6, 0.6, -1.0, 0.4)
    boundary_conditions = (
        ls.BoundaryConditionEnum.REFLECTIVE_BOUNDARY,
        ls.BoundaryConditionEnum.INFINITE_BOUNDARY,
    )
    fill = ls2.Domain(bounds, boundary_conditions, 0.01)
    ls2.MakeGeometry(fill, ls2.Plane((0.0, 0.1), (0.0, 1.0))).apply()
    void = ls2.Domain(bounds, boundary_conditions, 0.01)
    ls2.MakeGeometry(
        void,
        ls2.Box((-0.05, -0.8), (0.05, -0.2)),
    ).apply()
    ls2.BooleanOperation(
        fill,
        void,
        ls.BooleanOperationEnum.RELATIVE_COMPLEMENT,
    ).apply()
    geometry = ps.Domain(
        bounds=bounds,
        boundaryConditions=boundary_conditions,
        gridDelta=0.01,
    )
    geometry.insertNextLevelSetAsMaterial(fill, ps.Material.Cu)

    def measure():
        mesh = tm.raw_level_set_meshes(geometry)[-1]
        return tm.fill_topology_metrics_2d(
            mesh["nodes"],
            mesh["lines"],
            field_y=0.0,
            floor_y=-0.9,
            via_x_bounds=(-0.15, 0.15),
            field_sample_xs=(-0.4, 0.4),
            tolerance=0.001,
        )

    before = measure()
    model = ps.CopperSuppressionFill(candidate_parameters(
        adsorption_strength=0.25,
        plating_materials=[ps.Material.Cu],
    ))
    process = ps.Process(geometry, model, 0.2)
    set_process_parameters(
        process,
        seed=17,
        rays=500,
        ignore_voids=ignore_voids,
    )
    process.apply()
    return before, measure()


def test_flat_limits_and_material_gate():
    active = run_flat(0.0, plating_materials=[ps.Material.Si, ps.Material.Cu])
    suppressed = run_flat(5.0, plating_materials=[ps.Material.Si, ps.Material.Cu])
    gated = run_flat(0.0, plating_materials=[ps.Material.Cu])
    zero_sticking = run_flat(
        5.0,
        plating_materials=[ps.Material.Si, ps.Material.Cu],
        sticking=0.0,
    )
    assert np.all(active["coverage"] == 0.0)
    assert np.max(active["velocity"]) == 0.20
    assert np.min(suppressed["coverage"]) > 0.0
    assert np.max(suppressed["coverage"]) <= 1.0
    assert np.max(suppressed["velocity"]) < np.max(active["velocity"])
    assert np.all(gated["velocity"] == 0.0)
    assert np.all(zero_sticking["coverage"] == 0.0)
    assert np.max(zero_sticking["velocity"]) == 0.20
    assert suppressed["relative_balance_error"] < 1e-12


def test_via_transport_drives_bottom_faster_than_field():
    first = run_via()
    second = run_via()
    comparable = (
        "field_flux",
        "floor_flux",
        "field_coverage",
        "floor_coverage",
        "field_velocity",
        "floor_velocity",
    )
    assert [first[key] for key in comparable] == [second[key] for key in comparable]
    assert first["field_flux"] > first["floor_flux"]
    assert first["field_coverage"] > first["floor_coverage"]
    assert first["floor_velocity"] > first["field_velocity"]
    assert 0.0 <= first["coverage_min"] <= first["coverage_max"] <= 1.0
    assert first["relative_balance_error"] < 1e-12


def test_matched_convex_and_concave_surfaces_follow_access_ordering():
    first = run_matched_convex_concave_access()
    second = run_matched_convex_concave_access()
    assert first == second

    # This checks only the ray-access ordering and the sign of the reduced
    # suppressor response. It is not an electrochemistry validation.
    assert first["cap_flux"] > 1.05 * first["bowl_flux"]
    assert first["cap_coverage"] > first["bowl_coverage"]
    assert first["bowl_velocity"] > 1.05 * first["cap_velocity"]
    assert first["relative_balance_error"] < 1e-12


def test_invalid_parameters_are_rejected():
    invalid = ps.CopperSuppressionFillParams()
    invalid.suppressorStickingProbability = 1.1
    try:
        ps.CopperSuppressionFill(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid sticking probability was accepted")

    invalid = ps.CopperSuppressionFillParams()
    invalid.activeDepositionRate = 0.01
    invalid.suppressedDepositionRate = 0.02
    try:
        ps.CopperSuppressionFill(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("active rate below suppressed rate was accepted")

    invalid = ps.CopperSuppressionFillParams()
    invalid.adsorptionStrength = float("nan")
    try:
        ps.CopperSuppressionFill(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("non-finite adsorption strength was accepted")


def test_extreme_finite_adsorption_does_not_overflow_the_root():
    result = run_flat(
        1e150,
        plating_materials=[ps.Material.Si, ps.Material.Cu],
    )
    assert np.all(np.isfinite(result["coverage"]))
    assert np.all(np.isfinite(result["velocity"]))
    assert np.all((0.0 <= result["coverage"]) & (result["coverage"] <= 1.0))


def test_sealed_voids_are_frozen_by_the_required_advection_guard():
    unguarded_before, unguarded_after = run_sealed_void_control(
        ignore_voids=False
    )
    guarded_before, guarded_after = run_sealed_void_control(ignore_voids=True)
    assert unguarded_after["closed_void_area"] < 0.5 * unguarded_before[
        "closed_void_area"
    ]
    assert guarded_after["closed_void_count"] == 1
    assert guarded_after["closed_void_area"] == guarded_before["closed_void_area"]


def test_seed_to_plated_cu_handoff_and_dielectric_gate():
    def flat_layer(material):
        geometry = ps.Domain(gridDelta=0.01, xExtent=0.5, yExtent=0.5)
        ps.MakePlane(geometry, height=0.0, material=ps.Material.Si).apply()
        geometry.duplicateTopLevelSet(material)
        ps.Process(geometry, ps.IsotropicProcess(rate=0.01), 1.0).apply()
        return geometry

    params = candidate_parameters(
        adsorption_strength=0.25,
        plating_materials=[tp.CU_SEED_MATERIAL, ps.Material.Cu],
    )
    geometry = flat_layer(tp.CU_SEED_MATERIAL)
    seed_model = ps.CopperSuppressionFill(params)
    seed_process = ps.Process(geometry, seed_model, 0.2)
    set_process_parameters(seed_process, seed=19, rays=500)
    seed_process.apply()
    seed_ids = np.asarray(seed_model.getLastMaterialIds(), dtype=float)
    seed_velocities = np.asarray(seed_model.getLastVelocity(), dtype=float)
    assert np.any(seed_ids == tp.CU_SEED_MATERIAL.legacyId())
    assert np.max(seed_velocities) > 0.0

    geometry.duplicateTopLevelSet(ps.Material.Cu)
    cu_model = ps.CopperSuppressionFill(params)
    cu_process = ps.Process(geometry, cu_model, 0.2)
    set_process_parameters(cu_process, seed=19, rays=500)
    cu_process.apply()
    cu_ids = np.asarray(cu_model.getLastMaterialIds(), dtype=float)
    cu_velocities = np.asarray(cu_model.getLastVelocity(), dtype=float)
    assert np.any(cu_ids == ps.Material.Cu.legacyId())
    assert np.max(cu_velocities) > 0.0

    dielectric = flat_layer(ps.Material.SiO2)
    dielectric_model = ps.CopperSuppressionFill(params)
    dielectric_process = ps.Process(dielectric, dielectric_model, 0.2)
    set_process_parameters(dielectric_process, seed=19, rays=500)
    dielectric_process.apply()
    assert np.max(dielectric_model.getLastVelocity()) == 0.0


if __name__ == "__main__":
    ps.setNumThreads(1)
    ps.Logger.setLogLevel(ps.LogLevel.ERROR)
    test_flat_limits_and_material_gate()
    test_via_transport_drives_bottom_faster_than_field()
    test_matched_convex_and_concave_surfaces_follow_access_ordering()
    test_invalid_parameters_are_rejected()
    test_extreme_finite_adsorption_does_not_overflow_the_root()
    test_sealed_voids_are_frozen_by_the_required_advection_guard()
    test_seed_to_plated_cu_handoff_and_dielectric_gate()
    print("copper suppression-fill checks: PASS")

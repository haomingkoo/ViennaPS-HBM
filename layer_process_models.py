"""Explicit model alternatives for TSV liner, barrier, and seed studies."""

from __future__ import annotations

import math

import viennaps as ps


def _positive(name, value):
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def ray_parameters(
    *,
    rays_per_point,
    rng_seed,
    max_reflections=None,
    max_boundary_hits=1000,
):
    parameters = ps.RayTracingParameters()
    parameters.raysPerPoint = int(rays_per_point)
    if parameters.raysPerPoint < 1:
        raise ValueError("rays_per_point must be positive")
    parameters.useRandomSeeds = False
    parameters.rngSeed = int(rng_seed)
    if max_reflections is not None:
        parameters.maxReflections = int(max_reflections)
    parameters.maxBoundaryHits = int(max_boundary_hits)
    if parameters.maxBoundaryHits < 1:
        raise ValueError("max_boundary_hits must be positive")
    return parameters


def _apply_particle_model(
    geometry,
    material,
    model,
    *,
    rays_per_point,
    rng_seed,
    max_reflections=None,
    max_boundary_hits=1000,
):
    geometry.duplicateTopLevelSet(material)
    process = ps.Process(geometry, model, 1.0)
    process.setParameters(ray_parameters(
        rays_per_point=rays_per_point,
        rng_seed=rng_seed,
        max_reflections=max_reflections,
        max_boundary_hits=max_boundary_hits,
    ))
    process.apply()
    return geometry


def deposit_single_particle(
    geometry,
    material,
    *,
    dose,
    sticking_probability,
    source_exponent=1.0,
    rays_per_point,
    rng_seed,
    max_reflections=None,
    max_boundary_hits=1000,
):
    """Diffuse-reflection transport surrogate used by the historical liner."""
    dose = _positive("dose", dose)
    sticking_probability = float(sticking_probability)
    source_exponent = _positive("source_exponent", source_exponent)
    if not 0.0 < sticking_probability <= 1.0:
        raise ValueError("sticking_probability must be in (0, 1]")
    model = ps.SingleParticleProcess(
        rate=dose,
        stickingProbability=sticking_probability,
        sourceExponent=source_exponent,
    )
    return _apply_particle_model(
        geometry,
        material,
        model,
        rays_per_point=rays_per_point,
        rng_seed=rng_seed,
        max_reflections=max_reflections,
        max_boundary_hits=max_boundary_hits,
    )


def deposit_teos(
    geometry,
    material,
    *,
    dose,
    sticking_probability,
    reaction_order,
    rays_per_point,
    rng_seed,
    max_reflections=None,
    max_boundary_hits=1000,
):
    """Installed coverage-coupled TEOS CVD model; coefficients are uncalibrated."""
    dose = _positive("dose", dose)
    reaction_order = _positive("reaction_order", reaction_order)
    sticking_probability = float(sticking_probability)
    if not 0.0 < sticking_probability <= 1.0:
        raise ValueError("sticking_probability must be in (0, 1]")
    model = ps.TEOSDeposition(
        sticking_probability,
        dose,
        reaction_order,
    )
    return _apply_particle_model(
        geometry,
        material,
        model,
        rays_per_point=rays_per_point,
        rng_seed=rng_seed,
        max_reflections=max_reflections,
        max_boundary_hits=max_boundary_hits,
    )


def directional_components(field_dose, isotropic_fraction):
    """Split a fixed nominal horizontal-field dose into directional/isotropic parts."""
    field_dose = _positive("field_dose", field_dose)
    isotropic_fraction = float(isotropic_fraction)
    if not math.isfinite(isotropic_fraction) or not 0.0 <= isotropic_fraction <= 1.0:
        raise ValueError("isotropic_fraction must be in [0, 1]")
    return (
        field_dose * (1.0 - isotropic_fraction),
        field_dose * isotropic_fraction,
    )


def deposit_directional_fraction(
    geometry,
    material,
    *,
    field_dose,
    isotropic_fraction,
    direction=(0.0, -1.0, 0.0),
    calculate_visibility=True,
):
    """Directional model parameterized without changing total horizontal dose."""
    directional, isotropic = directional_components(
        field_dose, isotropic_fraction
    )
    direction = tuple(float(value) for value in direction)
    if len(direction) != 3 or not math.isclose(
        math.sqrt(sum(value * value for value in direction)),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("direction must be a three-component unit vector")
    geometry.duplicateTopLevelSet(material)
    model = ps.DirectionalProcess(
        direction=direction,
        directionalVelocity=directional,
        isotropicVelocity=isotropic,
        calculateVisibility=bool(calculate_visibility),
    )
    ps.Process(geometry, model, 1.0).apply()
    return geometry


def deposit_isotropic_control(geometry, material, *, dose):
    """Morphology-positive control, not a calibrated deposition recipe."""
    dose = _positive("dose", dose)
    geometry.duplicateTopLevelSet(material)
    ps.Process(geometry, ps.IsotropicProcess(rate=dose), 1.0).apply()
    return geometry

"""ViennaPS process steps used by the tutorial."""

import numpy as np
import viennaps as ps


CU_SEED_MATERIAL = ps.MaterialRegistry.instance().registerMaterial("CuSeed")


def _surface_points(domain):
    nodes = np.asarray(domain.getSurfaceMesh().getNodes(), dtype=float)[:, :2]
    bins = np.round(nodes[:, 0] / (domain.getGridDelta() / 2)).astype(int)
    order = np.argsort(nodes[:, 1])
    nodes, bins = nodes[order], bins[order]
    _, first = np.unique(bins[::-1], return_index=True)
    return nodes[np.sort(len(nodes) - 1 - first)]


def make_initial_geometry(
    *, radius, mask_height, grid_delta, x_extent, y_extent, taper, hole_shape
):
    """Create a masked silicon opening."""
    domain = ps.Domain(
        gridDelta=grid_delta,
        xExtent=x_extent,
        yExtent=y_extent,
    )
    ps.MakeHole(
        domain=domain,
        holeRadius=radius,
        holeDepth=0.0,
        maskHeight=mask_height,
        maskTaperAngle=taper,
        holeShape=hole_shape,
    ).apply()
    if domain.getNumberOfLevelSets() < 2:
        raise RuntimeError("expected mask and substrate level sets")
    return domain


def strip_pattern_mask(domain):
    """Remove the temporary mask before film deposition."""
    domain.removeMaterial(ps.Material.Mask)
    materials = domain.getMaterialMap()
    if any(
        materials.getMaterialAtIdx(index) == ps.Material.Mask
        for index in range(domain.getNumberOfLevelSets())
    ):
        raise RuntimeError("pattern mask removal failed")


def bosch_etch(
    domain,
    *,
    num_cycles,
    etch_time,
    initial_etch_time,
    ion_source_exponent,
    neutral_sticking_probability,
    deposition_thickness,
    deposition_sticking_probability,
    neutral_rate,
    ion_rate,
    theta_r_min,
    rays_per_point,
    rng_seed,
    mask_ion_rate,
):
    """Alternate passivation and etch steps."""
    if mask_ion_rate > 0.0:
        raise ValueError("mask_ion_rate must be zero or negative")

    deposition = ps.SingleParticleProcess(
        rate=deposition_thickness,
        stickingProbability=deposition_sticking_probability,
    )
    polymer_removal = ps.SingleParticleProcess(
        rate=-deposition_thickness,
        stickingProbability=1.0,
        sourceExponent=ion_source_exponent,
        maskMaterial=ps.Material.Mask,
    )
    etch = ps.MultiParticleProcess()
    etch.addNeutralParticle(neutral_sticking_probability)
    etch.addIonParticle(
        sourcePower=ion_source_exponent,
        thetaRMin=theta_r_min,
    )

    def rate(fluxes, material):
        if material == ps.Material.Mask:
            return fluxes[1] * mask_ion_rate
        value = fluxes[1] * ion_rate
        if material == ps.Material.Si:
            value += fluxes[0] * neutral_rate
        return value

    etch.setRateFunction(rate)
    process_index = 0

    def apply(model, duration):
        nonlocal process_index
        simulation = ps.Process(domain, model, duration)
        parameters = ps.RayTracingParameters()
        parameters.raysPerPoint = int(rays_per_point)
        parameters.useRandomSeeds = False
        parameters.rngSeed = int(rng_seed) + process_index
        simulation.setParameters(parameters)
        simulation.apply()
        process_index += 1

    apply(etch, initial_etch_time)
    for _ in range(num_cycles):
        domain.duplicateTopLevelSet(ps.Material.Polymer)
        apply(deposition, 1.0)
        apply(polymer_removal, 1.0)
        apply(etch, etch_time)
        domain.removeTopLevelSet()
        domain.removeStrayPoints()

    depth = float(_surface_points(domain)[:, 1].min())
    if depth >= -0.1:
        raise RuntimeError(f"etch barely moved: depth={depth}")
    return domain


def deposit_conformal(
    domain,
    material,
    amount,
    *,
    sticking,
    rays_per_point,
    rng_seed,
):
    """Deposit a film with the single-particle transport model."""
    floor_before = _surface_points(domain)[:, 1].min()
    domain.duplicateTopLevelSet(material)
    model = ps.SingleParticleProcess(
        rate=amount,
        stickingProbability=sticking,
    )
    simulation = ps.Process(domain, model, 1.0)
    parameters = ps.RayTracingParameters()
    parameters.raysPerPoint = int(rays_per_point)
    parameters.useRandomSeeds = False
    parameters.rngSeed = int(rng_seed)
    simulation.setParameters(parameters)
    simulation.apply()
    floor_after = _surface_points(domain)[:, 1].min()
    if floor_after <= floor_before - 0.005:
        raise RuntimeError("deposition enlarged the cavity")


def cu_fill(domain, amount, *, all_angle_fraction):
    """Apply geometric copper growth, not an electroplating model."""
    domain.duplicateTopLevelSet(ps.Material.Cu)
    model = ps.DirectionalProcess(
        direction=[0.0, -1.0, 0.0],
        directionalVelocity=amount,
        isotropicVelocity=amount * all_angle_fraction,
    )
    ps.Process(domain, model, 1.0).apply()

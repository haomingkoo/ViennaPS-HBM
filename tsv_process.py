"""Geometry helpers for the simplified TSV process."""

import numpy as np
import viennaps as ps
import viennals as ls

from process_config import PROCESS_CONFIG

ps.setDimension(2)
ps.Logger.setLogLevel(ps.LogLevel.ERROR)

# Registered materials survive ViennaPS checkpoint round trips.
CU_SEED_MATERIAL = ps.MaterialRegistry.instance().registerMaterial("CuSeed")

CORE_CONFIG = PROCESS_CONFIG["core"]
GEOMETRY_DEFAULTS = PROCESS_CONFIG["defaults"]["geometry"]
BOSCH_DEFAULTS = PROCESS_CONFIG["defaults"]["bosch"]
DEPOSITION_DEFAULTS = PROCESS_CONFIG["defaults"]["deposition"]
FILL_DEFAULTS = PROCESS_CONFIG["defaults"]["fill"]
METRIC_CONFIG = PROCESS_CONFIG["metrics"]

NUMERIC_EPSILON = CORE_CONFIG["numeric_epsilon"]
INVALID_SCORE = CORE_CONFIG["invalid_score"]
MASK_FAILURE_PENALTY = CORE_CONFIG["mask_failure_penalty"]
TOPOLOGY_FAILURE_PENALTY = CORE_CONFIG["topology_failure_penalty"]
MIN_RESOLVED_ETCH_DEPTH = CORE_CONFIG["min_resolved_etch_depth"]
MIN_SIDEWALL_POINTS = int(CORE_CONFIG["min_sidewall_points"])
DEPOSITION_REGRESSION_TOLERANCE = CORE_CONFIG["deposition_regression_tolerance"]
CMP_ENDPOINT_TOLERANCE = CORE_CONFIG["cmp_endpoint_tolerance"]
TARGET_SPECS = PROCESS_CONFIG["targets"]


def wall_bulge(
    points,
    depth,
    radius=GEOMETRY_DEFAULTS["radius"],
    y_top_margin=GEOMETRY_DEFAULTS["profile_top_margin"],
):
    body = points[
        (points[:, 1] > depth * 0.85)
        & (points[:, 1] < y_top_margin)
        & (points[:, 0] > 0.2 * radius)
    ]
    return float(np.max(np.abs(body[:, 0] - radius))) if len(body) else None


def width_error(
    points,
    depth,
    radius=GEOMETRY_DEFAULTS["radius"],
    y_top_margin=GEOMETRY_DEFAULTS["profile_top_margin"],
):
    bulge = wall_bulge(points, depth, radius, y_top_margin)
    return None if bulge is None else float(2.0 * bulge)


def floor_reach_metric(y_before, pts_after):
    floor_after = pts_after[:, 1].min()
    depth_span = abs(y_before)
    coverage = (
        1.0 - abs(floor_after - y_before) / depth_span
        if depth_span > NUMERIC_EPSILON
        else 0.0
    )
    return max(0.0, min(1.0, coverage))


def fill_tip_gap(
    pts_fill,
    via_floor,
    center_half_width=METRIC_CONFIG["center_half_width"],
):
    center = pts_fill[np.abs(pts_fill[:, 0]) < center_half_width]
    if not len(center):
        return None
    return float(center[:, 1].mean() - via_floor)


def fill_centerline_gap(
    pts_fill,
    center_half_width=METRIC_CONFIG["center_half_width"],
    field_min_x=METRIC_CONFIG["field_min_x"],
):
    """Candidate metric: center depression relative to the field surface."""
    center = pts_fill[np.abs(pts_fill[:, 0]) < center_half_width]
    field = pts_fill[pts_fill[:, 0] > field_min_x]
    if not len(center) or not len(field):
        return None
    return max(0.0, float(field[:, 1].mean() - center[:, 1].mean()))


def cmp_dish(points):
    field = points[np.abs(points[:, 0]) > METRIC_CONFIG["cmp_field_min_abs_x"]][:, 1]
    via = points[np.abs(points[:, 0]) < METRIC_CONFIG["cmp_via_max_abs_x"]][:, 1]
    return float(field.mean() - via.mean()) if len(field) and len(via) else None


def target_score(step, metrics):
    """Return (passes_target, score). Lower score is closer to the step spec."""
    spec = TARGET_SPECS[step]
    if step == "pattern":
        radius = metrics.get("radius")
        width = metrics.get("width", 2.0 * radius if radius is not None else None)
        mask_height = metrics.get("mask_height")
        if radius is None or width is None or mask_height is None:
            return False, float("inf")
        score = (
            abs(radius - spec["radius"])
            + abs(width - spec["width"])
            + abs(mask_height - spec["mask_height"])
        )
        return score == 0, float(score)

    if step == "etch":
        depth = metrics.get("depth")
        bulge = metrics.get("bulge")
        if depth is None or bulge is None:
            return False, float("inf")
        width_miss_value = metrics.get("width_error")
        if width_miss_value is None:
            width_miss_value = 2.0 * bulge
        depth_error = abs(abs(depth) - spec["target_depth"])
        depth_miss = max(0.0, depth_error - spec["depth_tolerance"])
        bulge_miss = max(0.0, bulge - spec["max_wall_bulge"])
        width_miss = max(0.0, width_miss_value - spec["max_width_error"])
        passes = depth_miss == 0.0 and bulge_miss == 0.0 and width_miss == 0.0
        shape_score = max(
            bulge / spec["max_wall_bulge"], width_miss_value / spec["max_width_error"]
        )
        score = depth_miss / spec["depth_tolerance"] + shape_score
        return passes, float(score)

    if step in ("liner", "barrier"):
        thickness = metrics.get("thickness")
        coverage = metrics.get("coverage")
        if thickness is None or coverage is None:
            return False, float("inf")
        thickness_miss = (
            max(0.0, spec["min_thickness"] - thickness) / spec["min_thickness"]
        )
        coverage_miss = max(0.0, spec["target_floor_coverage"] - coverage)
        passes = (
            thickness >= spec["min_thickness"]
            and coverage >= spec["min_floor_coverage"]
        )
        return passes, float(thickness_miss + coverage_miss)

    if step == "fill":
        overburden = metrics.get("overburden_min")
        closed_void_count = metrics.get("closed_void_count")
        remaining_void_area = metrics.get("remaining_void_area")
        if (
            overburden is None
            or closed_void_count is None
            or remaining_void_area is None
        ):
            return False, float("inf")
        topology_pass = bool(
            metrics.get("void_free") is True
            and closed_void_count == 0
            and remaining_void_area == 0.0
        )
        overburden_miss = (
            max(0.0, spec["min_overburden"] - overburden) / spec["min_overburden"]
        )
        passes = topology_pass and overburden >= spec["min_overburden"]
        topology_penalty = 0.0 if topology_pass else TOPOLOGY_FAILURE_PENALTY
        return passes, float(topology_penalty + overburden_miss)

    if step == "cmp":
        dish = metrics.get("dish")
        mask_consumed = bool(metrics.get("mask_consumed"))
        if dish is None:
            return False, float("inf")
        mask_penalty = (
            MASK_FAILURE_PENALTY if spec["mask_must_survive"] and mask_consumed else 0.0
        )
        dish_miss = abs(dish - spec["target_dish"])
        return (not mask_consumed and dish_miss == 0.0), float(mask_penalty + dish_miss)

    raise ValueError(f"unknown process step: {step}")


def with_target_score(step, metrics):
    passes, score = target_score(step, metrics)
    if not np.isfinite(score):
        score = INVALID_SCORE
    return {**metrics, "target_pass": bool(passes), "target_score": float(score)}


def all_material_profiles(geometry, bin_width=None):
    """Return one ordered boundary point array per material level set."""
    level_sets = geometry.getLevelSets()
    mat_map = geometry.getMaterialMap()
    if bin_width is None:
        bin_width = geometry.getGridDelta() / 2
    out = []
    for i, lvlset in enumerate(level_sets):
        mat = mat_map.getMaterialAtIdx(i)
        mesh = ls.Mesh()
        ls.ToSurfaceMesh(lvlset, mesh).apply()
        nodes = np.array(mesh.getNodes())
        if nodes.ndim != 2 or len(nodes) == 0:
            # A consumed level set has no mesh.
            out.append((str(mat), np.empty((0, 2))))
            continue
        pts = nodes[:, :2]
        bins = np.round(pts[:, 0] / bin_width).astype(int)
        order = np.argsort(pts[:, 1])
        pts_sorted, bins_sorted = pts[order], bins[order]
        _, first_idx = np.unique(bins_sorted[::-1], return_index=True)
        keep = len(pts_sorted) - 1 - first_idx
        out.append((str(mat), pts_sorted[np.sort(keep)]))
    return out


def profile_points(geometry, bin_width=None):
    """Return the highest surface point in each x bin."""
    mesh = geometry.getSurfaceMesh()
    pts = np.array(mesh.getNodes())[:, :2]
    if bin_width is None:
        bin_width = geometry.getGridDelta() / 2
    bins = np.round(pts[:, 0] / bin_width).astype(int)
    order = np.argsort(pts[:, 1])
    pts, bins = pts[order], bins[order]
    _, first_idx = np.unique(bins[::-1], return_index=True)
    keep = len(pts) - 1 - first_idx
    return pts[np.sort(keep)]


def trim_for_display(points, y_ceiling):
    """Remove points above the plotted via region."""
    return points[points[:, 1] <= y_ceiling]


def sidewall_fit(
    points,
    radius,
    y_top,
    y_bottom,
    margin=GEOMETRY_DEFAULTS["sidewall_fit_margin"],
):
    """Return sidewall slope and RMS residual away from the corners."""
    span = y_top - y_bottom
    lo, hi = y_bottom + margin * span, y_top - margin * span
    sel = (points[:, 1] > lo) & (points[:, 1] < hi) & (points[:, 0] > 0.2 * radius)
    pts = points[sel]
    if len(pts) < MIN_SIDEWALL_POINTS:
        return None, None
    y, x = pts[:, 1], pts[:, 0]
    a, b = np.polyfit(y, x, 1)
    residual = x - (a * y + b)
    return float(a), float(np.sqrt(np.mean(residual**2)))


def make_initial_geometry(
    radius=GEOMETRY_DEFAULTS["radius"],
    mask_height=GEOMETRY_DEFAULTS["mask_height"],
    grid_delta=GEOMETRY_DEFAULTS["grid_delta"],
    x_extent=GEOMETRY_DEFAULTS["x_extent"],
    y_extent=GEOMETRY_DEFAULTS["y_extent"],
    taper=GEOMETRY_DEFAULTS["mask_taper"],
    hole_shape=None,
):
    """Step 1: patterning -- photoresist-masked opening over Si."""
    if hole_shape is None:
        hole_shape = ps.HoleShape.QUARTER
    geometry = ps.Domain(gridDelta=grid_delta, xExtent=x_extent, yExtent=y_extent)
    ps.MakeHole(
        domain=geometry,
        holeRadius=radius,
        holeDepth=0.0,
        maskHeight=mask_height,
        maskTaperAngle=taper,
        holeShape=hole_shape,
    ).apply()
    assert geometry.getNumberOfLevelSets() >= 2, "expected mask + substrate level sets"
    return geometry


def strip_pattern_mask(geometry):
    """Remove the temporary pattern mask before dielectric deposition."""
    geometry.removeMaterial(ps.Material.Mask)
    materials = geometry.getMaterialMap()
    assert all(
        materials.getMaterialAtIdx(index) != ps.Material.Mask
        for index in range(geometry.getNumberOfLevelSets())
    ), "pattern mask removal failed"
    return geometry


def bosch_etch(
    geometry,
    *,
    num_cycles=BOSCH_DEFAULTS["num_cycles"],
    etch_time=BOSCH_DEFAULTS["etch_time"],
    initial_etch_time=BOSCH_DEFAULTS["initial_etch_time"],
    ion_source_exponent=BOSCH_DEFAULTS["ion_source_exponent"],
    neutral_sticking_probability=BOSCH_DEFAULTS["neutral_sticking_probability"],
    deposition_thickness=BOSCH_DEFAULTS["deposition_thickness"],
    deposition_sticking_probability=BOSCH_DEFAULTS["deposition_sticking_probability"],
    neutral_rate=BOSCH_DEFAULTS["neutral_rate"],
    ion_rate=BOSCH_DEFAULTS["ion_rate"],
    on_cycle=None,
    on_polymer=None,
    radius=GEOMETRY_DEFAULTS["radius"],
    theta_r_min=BOSCH_DEFAULTS["theta_r_min"],
    rays_per_point=BOSCH_DEFAULTS["rays_per_point"],
    rng_seed=None,
    mask_ion_rate=BOSCH_DEFAULTS["mask_ion_rate"],
):
    """Apply alternating passivation and etch steps."""
    if mask_ion_rate > 0.0:
        raise ValueError("mask_ion_rate must be zero or negative for mask erosion")
    depo_model = ps.SingleParticleProcess(
        rate=deposition_thickness, stickingProbability=deposition_sticking_probability
    )
    depo_removal = ps.SingleParticleProcess(
        rate=-deposition_thickness,
        stickingProbability=1.0,
        sourceExponent=ion_source_exponent,
        maskMaterial=ps.Material.Mask,
    )

    etch_model = ps.MultiParticleProcess()
    etch_model.addNeutralParticle(neutral_sticking_probability)
    etch_model.addIonParticle(sourcePower=ion_source_exponent, thetaRMin=theta_r_min)

    def rate_fn(fluxes, material):
        if material == ps.Material.Mask:
            return fluxes[1] * mask_ion_rate
        rate = fluxes[1] * ion_rate
        if material == ps.Material.Si:
            rate += fluxes[0] * neutral_rate
        return rate

    etch_model.setRateFunction(rate_fn)

    process_index = 0

    def apply_process(model, duration):
        nonlocal process_index
        process = ps.Process(geometry, model, duration)
        ray_parameters = ps.RayTracingParameters()
        ray_parameters.raysPerPoint = int(rays_per_point)
        if rng_seed is not None:
            ray_parameters.useRandomSeeds = False
            ray_parameters.rngSeed = int(rng_seed) + process_index
        process.setParameters(ray_parameters)
        process.apply()
        process_index += 1

    # Open the mask before the first passivation cycle.
    apply_process(etch_model, initial_etch_time)
    if on_cycle:
        on_cycle(geometry, 0)

    for i in range(num_cycles):
        geometry.duplicateTopLevelSet(ps.Material.Polymer)
        apply_process(depo_model, 1.0)
        if on_polymer:
            on_polymer(geometry, i)
        apply_process(depo_removal, 1.0)
        apply_process(etch_model, etch_time)
        geometry.removeTopLevelSet()
        geometry.removeStrayPoints()
        if on_cycle:
            on_cycle(geometry, i + 1)

    depth = float(profile_points(geometry)[:, 1].min())
    assert depth < -MIN_RESOLVED_ETCH_DEPTH, f"etch barely moved: depth={depth}"
    return geometry, depth


def deposit_conformal(
    geometry,
    material,
    thickness,
    *,
    directional=False,
    sticking=DEPOSITION_DEFAULTS["sticking"],
    iso_ratio=DEPOSITION_DEFAULTS["isotropic_ratio"],
    rays_per_point=DEPOSITION_DEFAULTS["rays_per_point"],
    rng_seed=None,
):
    """Deposit one layer with a geometric transport surrogate."""
    y_before = profile_points(geometry)[:, 1].min()
    geometry.duplicateTopLevelSet(material)
    if directional:
        model = ps.DirectionalProcess(
            direction=[0.0, -1.0, 0.0],
            directionalVelocity=thickness,
            isotropicVelocity=thickness * iso_ratio,
        )
    else:
        model = ps.SingleParticleProcess(rate=thickness, stickingProbability=sticking)
    process = ps.Process(geometry, model, 1.0)
    parameters = ps.RayTracingParameters()
    parameters.raysPerPoint = int(rays_per_point)
    if rng_seed is not None:
        parameters.useRandomSeeds = False
        parameters.rngSeed = int(rng_seed)
    process.setParameters(parameters)
    process.apply()
    y_after = profile_points(geometry)[:, 1].min()
    assert y_after > y_before - DEPOSITION_REGRESSION_TOLERANCE, (
        "conformal deposition should shrink the cavity, not grow it"
    )
    return geometry


def cu_fill(
    geometry,
    thickness,
    *,
    directional=False,
    iso_ratio=FILL_DEFAULTS["isotropic_ratio"],
):
    """Apply legacy geometric copper growth, not electroplating physics."""
    geometry.duplicateTopLevelSet(ps.Material.Cu)
    if directional:
        model = ps.DirectionalProcess(
            direction=[0.0, -1.0, 0.0],
            directionalVelocity=thickness,
            isotropicVelocity=thickness * iso_ratio,
        )
    else:
        model = ps.IsotropicProcess(rate=thickness)
    ps.Process(geometry, model, 1.0).apply()
    return geometry


def cmp_planarize(geometry, target_y):
    """Apply the legacy isotropic-removal control."""
    overburden = float(profile_points(geometry)[:, 1].max()) - target_y
    assert overburden >= 0, "nothing to planarize -- surface already below target"
    if overburden > NUMERIC_EPSILON:
        ps.Process(geometry, ps.IsotropicProcess(rate=-1.0), overburden).apply()
    y_max = float(profile_points(geometry)[:, 1].max())
    assert y_max <= target_y + CMP_ENDPOINT_TOLERANCE, (
        f"CMP did not planarize to target: {y_max} vs {target_y}"
    )
    return geometry

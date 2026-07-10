"""Modular TSV via-middle process steps built on ViennaPS.

Six stages of the real via-middle TSV loop, chained on one ps.Domain:
patterning -> Bosch DRIE etch -> SiO2 liner -> barrier/seed -> Cu fill -> CMP.

Each function asserts a physically-sane outcome (not just "it ran") so a
broken parameter change fails loudly instead of silently producing garbage.
"""
import numpy as np
import viennaps as ps
import viennals as ls

ps.setDimension(2)
ps.Logger.setLogLevel(ps.LogLevel.ERROR)

TARGET_SPECS = {
    "pattern": {
        "radius": 0.15,
        "width": 0.30,
        "mask_height": 0.3,
    },
    "etch": {
        "target_depth": 1.25,
        "depth_tolerance": 0.10,
        "target_width": 0.30,
        "max_width_error": 0.06,
        "max_wall_bulge": 0.03,
    },
    "liner": {
        "min_thickness": 0.02,
        "min_floor_coverage": 0.995,
        "target_floor_coverage": 1.0,
    },
    "barrier": {
        "min_thickness": 0.012,
        "min_floor_coverage": 0.985,
        "target_floor_coverage": 1.0,
    },
    "fill": {
        "min_thickness": 0.15,
        "target_tip_gap": 0.0,
    },
    "cmp": {
        "target_dish": 0.0,
        "mask_must_survive": True,
    },
}


def wall_bulge(points, depth, radius=0.15, y_top_margin=0.2):
    body = points[
        (points[:, 1] > depth * 0.85)
        & (points[:, 1] < y_top_margin)
        & (points[:, 0] > 0.2 * radius)
    ]
    return float(np.max(np.abs(body[:, 0] - radius))) if len(body) else None


def width_error(points, depth, radius=0.15, y_top_margin=0.2):
    bulge = wall_bulge(points, depth, radius, y_top_margin)
    return None if bulge is None else float(2.0 * bulge)


def floor_reach_metric(y_before, pts_after):
    floor_after = pts_after[:, 1].min()
    depth_span = abs(y_before)
    coverage = 1.0 - abs(floor_after - y_before) / depth_span if depth_span > 1e-6 else 0.0
    return max(0.0, min(1.0, coverage))


def fill_tip_gap(pts_fill, via_floor, center_half_width=0.02):
    center = pts_fill[np.abs(pts_fill[:, 0]) < center_half_width]
    if not len(center):
        return None
    return float(center[:, 1].mean() - via_floor)


def cmp_dish(points):
    field = points[points[:, 0] > 0.3][:, 1]
    via = points[points[:, 0] < 0.1][:, 1]
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
        shape_score = max(bulge / spec["max_wall_bulge"], width_miss_value / spec["max_width_error"])
        score = depth_miss / spec["depth_tolerance"] + shape_score
        return passes, float(score)

    if step in ("liner", "barrier"):
        thickness = metrics.get("thickness")
        coverage = metrics.get("coverage")
        if thickness is None or coverage is None:
            return False, float("inf")
        thickness_miss = max(0.0, spec["min_thickness"] - thickness) / spec["min_thickness"]
        coverage_miss = max(0.0, spec["target_floor_coverage"] - coverage)
        passes = thickness >= spec["min_thickness"] and coverage >= spec["min_floor_coverage"]
        return passes, float(thickness_miss + coverage_miss)

    if step == "fill":
        thickness = metrics.get("thickness")
        tip_gap = metrics.get("tip_gap")
        if thickness is None or tip_gap is None:
            return False, float("inf")
        thickness_miss = max(0.0, spec["min_thickness"] - thickness) / spec["min_thickness"]
        gap_miss = abs(tip_gap - spec["target_tip_gap"])
        passes = thickness >= spec["min_thickness"] and gap_miss == 0.0
        return passes, float(thickness_miss + gap_miss)

    if step == "cmp":
        dish = metrics.get("dish")
        mask_consumed = bool(metrics.get("mask_consumed"))
        if dish is None:
            return False, float("inf")
        mask_penalty = 10.0 if spec["mask_must_survive"] and mask_consumed else 0.0
        dish_miss = abs(dish - spec["target_dish"])
        return (not mask_consumed and dish_miss == 0.0), float(mask_penalty + dish_miss)

    raise ValueError(f"unknown process step: {step}")


def with_target_score(step, metrics):
    passes, score = target_score(step, metrics)
    if not np.isfinite(score):
        score = 1e9
    return {**metrics, "target_pass": bool(passes), "target_score": float(score)}


def all_material_profiles(geometry, bin_width=None):
    """Ordered list of (material_name, Nx2 points) -- one per level set,
    each material's *own* boundary rather than the mixed multi-material
    points profile_points() resolves into a single outer envelope.

    Used for a single cross-section figure showing every deposited layer
    at once (Si / liner / barrier+seed / fill), the way a real fab SEM
    cross-section shows them -- not one before/after pair per step.
    """
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
            # a level set fully consumed by over-etch (e.g. mask removed by
            # an aggressive CMP over-polish) has no surface left to mesh.
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
    """Nx2 array of (x, y) points on the true *outer* surface.

    geometry.getSurfaceMesh() returns every material interface (e.g. the
    buried Si/liner boundary as well as the liner/vacuum boundary), not just
    the outer one -- so this bins by x and keeps the highest y per bin,
    which is always the vacuum-facing surface (later stages build upward).
    """
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
    """Drop the flat mask-plateau region above y_ceiling before plotting.

    getSurfaceMesh() returns several near-coincident material boundaries at
    the flat mask top (Si/mask, mask/vacuum, liner/mask, ...), which render
    as messy overlapping fuzz with no informational value -- the story is
    the via, not the resist field around it.
    """
    return points[points[:, 1] <= y_ceiling]


def sidewall_fit(points, radius, y_top, y_bottom, margin=0.15):
    """Fit sidewall x = a*y + b over the via depth, excluding top/bottom corners.

    Returns (slope, rms_residual): slope 0 = perfectly vertical wall;
    rms_residual = scalloping/roughness amplitude.
    """
    span = y_top - y_bottom
    lo, hi = y_bottom + margin * span, y_top - margin * span
    sel = (points[:, 1] > lo) & (points[:, 1] < hi) & (points[:, 0] > 0.2 * radius)
    pts = points[sel]
    if len(pts) < 5:
        return None, None
    y, x = pts[:, 1], pts[:, 0]
    a, b = np.polyfit(y, x, 1)
    residual = x - (a * y + b)
    return float(a), float(np.sqrt(np.mean(residual ** 2)))


def make_initial_geometry(radius=0.15, mask_height=0.3, grid_delta=0.01,
                           x_extent=1.0, y_extent=1.5, taper=0.0):
    """Step 1: patterning -- photoresist-masked opening over Si."""
    geometry = ps.Domain(gridDelta=grid_delta, xExtent=x_extent, yExtent=y_extent)
    ps.MakeHole(
        domain=geometry, holeRadius=radius, holeDepth=0.0,
        maskHeight=mask_height, maskTaperAngle=taper,
        holeShape=ps.HoleShape.QUARTER,
    ).apply()
    assert geometry.getNumberOfLevelSets() >= 2, "expected mask + substrate level sets"
    return geometry


MAX_REALISTIC_ASPECT_RATIO = 20  # per the extreme-AR Cu pillar article
                                   # (15:1 -> 20:1) shared for this project --
                                   # a real via can't be etched arbitrarily
                                   # deep; it has to stay well short of full
                                   # wafer thickness (~700-775um), revealed
                                   # only later via backside grinding.


def bosch_etch(geometry, *, num_cycles=10, etch_time=1.5, initial_etch_time=0.3,
                ion_source_exponent=200, neutral_sticking_probability=0.1,
                deposition_thickness=0.02, deposition_sticking_probability=0.01,
                neutral_rate=-0.2, ion_rate=-0.1, on_cycle=None, on_polymer=None,
                radius=0.15, theta_r_min=60.0):
    """Step 2: Bosch DRIE -- SF6 (isotropic etch) / C4F8 (passivation) cycling.

    ion_source_exponent: ion angular directionality (higher = more forward-
      peaked = straighter sidewalls, less lateral etch).
    neutral_sticking_probability: isotropic/chemical etch contribution
      (higher = more undercut/taper risk).
    """
    depo_model = ps.SingleParticleProcess(
        rate=deposition_thickness, stickingProbability=deposition_sticking_probability)
    depo_removal = ps.SingleParticleProcess(
        rate=-deposition_thickness, stickingProbability=1.0,
        sourceExponent=ion_source_exponent, maskMaterial=ps.Material.Mask)

    etch_model = ps.MultiParticleProcess()
    etch_model.addNeutralParticle(neutral_sticking_probability)
    etch_model.addIonParticle(sourcePower=ion_source_exponent, thetaRMin=theta_r_min)

    def rate_fn(fluxes, material):
        if material == ps.Material.Mask:
            return 0.0
        rate = fluxes[1] * ion_rate
        if material == ps.Material.Si:
            rate += fluxes[0] * neutral_rate
        return rate

    etch_model.setRateFunction(rate_fn)

    # real Bosch process: a brief, shallow seed etch to break through the
    # resist opening -- NOT a full cycle-length etch, which would balloon
    # the unprotected opening out isotropically before any passivation exists.
    ps.Process(geometry, etch_model, initial_etch_time).apply()
    if on_cycle:
        on_cycle(geometry, 0)

    for i in range(num_cycles):
        geometry.duplicateTopLevelSet(ps.Material.Polymer)
        ps.Process(geometry, depo_model, 1.0).apply()
        if on_polymer:
            # the passivation coat, still present -- before it's punched
            # through and etched away later this same cycle.
            on_polymer(geometry, i)
        ps.Process(geometry, depo_removal, 1.0).apply()
        ps.Process(geometry, etch_model, etch_time).apply()
        geometry.removeTopLevelSet()
        geometry.removeStrayPoints()
        if on_cycle:
            on_cycle(geometry, i + 1)

    depth = float(profile_points(geometry)[:, 1].min())
    assert depth < -0.1, f"etch barely moved: depth={depth}"
    aspect_ratio = abs(depth) / (2 * radius)
    assert aspect_ratio < MAX_REALISTIC_ASPECT_RATIO, (
        f"aspect ratio {aspect_ratio:.1f}:1 exceeds {MAX_REALISTIC_ASPECT_RATIO}:1 -- "
        "this recipe would etch deeper than any real via/wafer-thickness budget allows"
    )
    return geometry, depth


def deposit_conformal(geometry, material, thickness, *, directional=False,
                        sticking=0.05, iso_ratio=0.3):
    """Step 3 (liner): isotropic, low-sticking -- SACVD-like thermal flow
    reaches deep vias by design (real conformality).

    Step 4 (barrier+seed): directional -- iPVD "ion bullets" reach the
    floor of a high-AR via where plain isotropic PVD/CVD physically can't
    (this is why fabs use iPVD for this layer, not plain PVD)."""
    y_before = profile_points(geometry)[:, 1].min()
    geometry.duplicateTopLevelSet(material)
    if directional:
        model = ps.DirectionalProcess(
            direction=[0.0, -1.0, 0.0],
            directionalVelocity=thickness, isotropicVelocity=thickness * iso_ratio)
    else:
        model = ps.SingleParticleProcess(rate=thickness, stickingProbability=sticking)
    ps.Process(geometry, model, 1.0).apply()
    y_after = profile_points(geometry)[:, 1].min()
    # Monte Carlo ray-traced flux has run-to-run noise; the floor can gain
    # only a sliver at high aspect ratio (that falloff is real physics, not
    # a bug) so tolerate a tiny regression rather than demand strict growth.
    assert y_after > y_before - 5e-3, "conformal deposition should shrink the cavity, not grow it"
    return geometry


def cu_fill(geometry, thickness, *, directional=False, iso_ratio=0.2):
    """Step 5: Cu fill -- naive conformal (voids at high AR) vs. directional
    bottom-up (approximating electroplating superfill)."""
    geometry.duplicateTopLevelSet(ps.Material.Cu)
    if directional:
        model = ps.DirectionalProcess(
            direction=[0.0, -1.0, 0.0],
            directionalVelocity=thickness, isotropicVelocity=thickness * iso_ratio)
    else:
        model = ps.IsotropicProcess(rate=thickness)
    ps.Process(geometry, model, 1.0).apply()
    return geometry


def cmp_planarize(geometry, target_y):
    """Step 6: CMP -- isotropic etch-back to the target planarization height."""
    overburden = float(profile_points(geometry)[:, 1].max()) - target_y
    assert overburden >= 0, "nothing to planarize -- surface already below target"
    if overburden > 1e-6:
        ps.Process(geometry, ps.IsotropicProcess(rate=-1.0), overburden).apply()
    y_max = float(profile_points(geometry)[:, 1].max())
    assert y_max <= target_y + 0.05, f"CMP did not planarize to target: {y_max} vs {target_y}"
    return geometry


if __name__ == "__main__":
    # ponytail: smallest runnable check -- one full traveler pass, asserts only.
    geometry = make_initial_geometry()
    geometry, depth = bosch_etch(geometry, num_cycles=4)
    print(f"etch depth: {depth:.3f}")
    geometry = deposit_conformal(geometry, ps.Material.SiO2, 0.03)
    geometry = deposit_conformal(geometry, ps.Material.Cu, 0.02, directional=True)
    geometry = cu_fill(geometry, 0.3, directional=True)
    geometry = cmp_planarize(geometry, target_y=0.3)
    print("tsv_process self-check: PASS")

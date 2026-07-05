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
        pts = np.array(mesh.getNodes())[:, :2]
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
                radius=0.15):
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
    etch_model.addIonParticle(sourcePower=ion_source_exponent, thetaRMin=60.0)

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

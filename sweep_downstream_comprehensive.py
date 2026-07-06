"""Comprehensive combined DOE for liner, barrier+seed, Cu fill, and CMP --
denser grids than sweep_downstream.py's earlier 20-30 point passes, matching
the etch DOE's rigor (screen_all_knobs.py already confirmed these are the
only real parameters left to sweep for each step -- see train.md).

Sequential, like sweep_downstream.py: each step's DOE runs on top of the
PREVIOUS step's own winner, not a shared fixed base -- liner tunes against
the real etched via, barrier tunes against the real best-liner via, etc.

CMP is different in kind: screening (prepare.md item 13/14) already found
there's no "winner" -- realistic overpolish always leaves severe dishing,
and eliminating it destroys the mask. So the CMP sweep here reports the
full dishing-vs-overpolish curve honestly, not a single best pick.
"""
import json
import time
import numpy as np
import viennaps as ps
import tsv_process as tp

ETCH = dict(ion_source_exponent=200, neutral_sticking_probability=0.2,
            etch_time=0.5, deposition_thickness=0.01)
PRODUCTION_CYCLES = 12
RADIUS = 0.15

MIN_LINER_THICKNESS = 0.02
MIN_BARRIER_THICKNESS = 0.012
MIN_FILL_THICKNESS = 0.15


def floor_reach_metric(y_before, pts_after):
    floor_after = pts_after[:, 1].min()
    depth_span = abs(y_before)
    coverage = 1.0 - abs(floor_after - y_before) / depth_span if depth_span > 1e-6 else 0.0
    return max(0.0, min(1.0, coverage))


def sweep_liner(geo_base, y_before):
    thicknesses = np.linspace(0.012, 0.05, 8)
    stickings = np.linspace(0.02, 0.3, 8)
    results = []
    for thick in thicknesses:
        for stick in stickings:
            g = ps.Domain(); g.deepCopy(geo_base)
            g.duplicateTopLevelSet(ps.Material.SiO2)
            ps.Process(g, ps.SingleParticleProcess(rate=float(thick), stickingProbability=float(stick)), 1.0).apply()
            coverage = floor_reach_metric(y_before, tp.profile_points(g))
            results.append({"thickness": float(thick), "sticking": float(stick), "coverage": coverage})
    meeting = [r for r in results if r["thickness"] >= MIN_LINER_THICKNESS]
    pool = meeting if meeting else results
    pool.sort(key=lambda r: -r["coverage"])
    return results, pool


def sweep_barrier(geo_base, y_before):
    thicknesses = np.linspace(0.008, 0.03, 8)
    iso_ratios = np.linspace(0.05, 0.5, 8)
    results = []
    for thick in thicknesses:
        for ratio in iso_ratios:
            g = ps.Domain(); g.deepCopy(geo_base)
            g.duplicateTopLevelSet(ps.Material.Cu)
            model = ps.DirectionalProcess(direction=[0.0, -1.0, 0.0],
                                            directionalVelocity=float(thick), isotropicVelocity=float(thick * ratio))
            ps.Process(g, model, 1.0).apply()
            coverage = floor_reach_metric(y_before, tp.profile_points(g))
            results.append({"thickness": float(thick), "iso_ratio": float(ratio), "coverage": coverage})
    meeting = [r for r in results if r["thickness"] >= MIN_BARRIER_THICKNESS]
    pool = meeting if meeting else results
    pool.sort(key=lambda r: -r["coverage"])
    return results, pool


def sweep_fill(geo_base, y_before):
    thicknesses = np.linspace(0.12, 0.35, 10)
    iso_ratios = np.linspace(0.03, 0.3, 8)
    results = []
    for thick in thicknesses:
        for ratio in iso_ratios:
            g = ps.Domain(); g.deepCopy(geo_base)
            g.duplicateTopLevelSet(ps.Material.Cu)
            model = ps.DirectionalProcess(direction=[0.0, -1.0, 0.0],
                                            directionalVelocity=float(thick), isotropicVelocity=float(thick * ratio))
            ps.Process(g, model, 1.0).apply()
            coverage = floor_reach_metric(y_before, tp.profile_points(g))
            results.append({"thickness": float(thick), "iso_ratio": float(ratio), "coverage": coverage})
    meeting = [r for r in results if r["thickness"] >= MIN_FILL_THICKNESS]
    pool = meeting if meeting else results
    pool.sort(key=lambda r: -r["coverage"])
    return results, pool


def sweep_cmp(geo_base, target_y):
    base_overburden = float(tp.profile_points(geo_base)[:, 1].max()) - target_y
    mults = np.concatenate([np.linspace(0.9, 2.0, 12), np.linspace(2.5, 10.0, 8)])
    results = []
    for mult in mults:
        g = ps.Domain(); g.deepCopy(geo_base)
        ps.Process(g, ps.IsotropicProcess(rate=-1.0), base_overburden * float(mult)).apply()
        pts = tp.profile_points(g)
        field = pts[pts[:, 0] > 0.3][:, 1]
        via = pts[pts[:, 0] < 0.1][:, 1]
        mats_present = [str(name) for name, p in tp.all_material_profiles(g) if len(p) > 0]
        mask_gone = not any("Mask" in m for m in mats_present)
        dish = float(field.mean() - via.mean()) if len(field) and len(via) else None
        results.append({"mult": float(mult), "dish": dish, "mask_consumed": mask_gone,
                         "materials_present": mats_present})
    return results


def main():
    t0 = time.time()
    geo_etched = tp.make_initial_geometry(radius=RADIUS)
    geo_etched, depth = tp.bosch_etch(geo_etched, num_cycles=PRODUCTION_CYCLES, **ETCH)
    print(f"production etch: depth={depth:.3f} ({time.time()-t0:.0f}s)")
    y_etched = float(tp.profile_points(geo_etched)[:, 1].min())

    liner_all, liner_ranked = sweep_liner(geo_etched, y_etched)
    best_liner = liner_ranked[0]
    print(f"liner: {len(liner_all)} runs, best={best_liner} ({time.time()-t0:.0f}s)")
    geo_liner = ps.Domain(); geo_liner.deepCopy(geo_etched)
    geo_liner.duplicateTopLevelSet(ps.Material.SiO2)
    ps.Process(geo_liner, ps.SingleParticleProcess(
        rate=best_liner["thickness"], stickingProbability=best_liner["sticking"]), 1.0).apply()
    y_liner = float(tp.profile_points(geo_liner)[:, 1].min())

    barrier_all, barrier_ranked = sweep_barrier(geo_liner, y_liner)
    best_barrier = barrier_ranked[0]
    print(f"barrier: {len(barrier_all)} runs, best={best_barrier} ({time.time()-t0:.0f}s)")
    geo_barrier = ps.Domain(); geo_barrier.deepCopy(geo_liner)
    geo_barrier.duplicateTopLevelSet(ps.Material.Cu)
    ps.Process(geo_barrier, ps.DirectionalProcess(
        direction=[0.0, -1.0, 0.0], directionalVelocity=best_barrier["thickness"],
        isotropicVelocity=best_barrier["thickness"] * best_barrier["iso_ratio"]), 1.0).apply()
    y_barrier = float(tp.profile_points(geo_barrier)[:, 1].min())

    fill_all, fill_ranked = sweep_fill(geo_barrier, y_barrier)
    best_fill = fill_ranked[0]
    print(f"fill: {len(fill_all)} runs, best={best_fill} ({time.time()-t0:.0f}s)")
    geo_fill = ps.Domain(); geo_fill.deepCopy(geo_barrier)
    geo_fill.duplicateTopLevelSet(ps.Material.Cu)
    ps.Process(geo_fill, ps.DirectionalProcess(
        direction=[0.0, -1.0, 0.0], directionalVelocity=best_fill["thickness"],
        isotropicVelocity=best_fill["thickness"] * best_fill["iso_ratio"]), 1.0).apply()

    target_y = float(tp.profile_points(geo_liner)[:, 1].max())  # pre-fill barrier/seed top, same convention as the notebook
    cmp_curve = sweep_cmp(geo_fill, target_y)
    print(f"CMP: {len(cmp_curve)} points across overpolish multiplier ({time.time()-t0:.0f}s)")
    for r in cmp_curve:
        print(f"  mult={r['mult']:.2f} dish={r['dish']:.3f} mask_consumed={r['mask_consumed']}")

    out = {
        "etch": {**ETCH, "num_cycles": PRODUCTION_CYCLES, "depth": depth},
        "best_liner": best_liner, "liner_top5": liner_ranked[:5],
        "best_barrier": best_barrier, "barrier_top5": barrier_ranked[:5],
        "best_fill": best_fill, "fill_top5": fill_ranked[:5],
        "cmp_target_y": target_y, "cmp_curve": cmp_curve,
    }
    with open("sweep_downstream_comprehensive_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\ntotal time: {time.time()-t0:.0f}s")
    print("saved sweep_downstream_comprehensive_results.json")


if __name__ == "__main__":
    main()

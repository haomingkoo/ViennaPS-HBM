"""Sweep liner, barrier/seed, and fill parameters on top of the winning
etch geometry from sweep_big.py -- so "re-tune downstream" means an actual
swept optimum per step, not a formulaic guess.

Each downstream step is a single Process call (not a multi-cycle loop
like the etch), so these sweeps are much cheaper than the etch DOE despite
similar point counts.
"""
import json
import time
import numpy as np
import viennaps as ps
import tsv_process as tp


def load_etch_winner():
    with open("sweep_big_results.json") as f:
        data = json.load(f)
    valid = [r for r in data["results"] if r["bulge"] is not None]
    valid.sort(key=lambda r: r["bulge"])
    return valid[0]


def base_geometry(winner, production_cycles=8):
    geo = tp.make_initial_geometry(radius=0.15)
    geo, depth = tp.bosch_etch(
        geo, num_cycles=production_cycles,
        etch_time=winner["etch_time"], deposition_thickness=winner["depo_thick"],
        ion_source_exponent=winner["ion"], neutral_sticking_probability=winner["neutral"],
    )
    return geo, depth


def floor_reach_metric(geo_before, geo_after):
    """How much of the cavity below the opening got coated -- 1.0 = fully
    conformal to the floor, 0.0 = no coverage reached the floor at all."""
    floor_before = tp.profile_points(geo_before)[:, 1].min()
    pts_after = tp.profile_points(geo_after)
    floor_after = pts_after[:, 1].min()
    # deposition can only shrink the cavity (floor y increases toward 0);
    # compare against how deep the original cavity was.
    depth_span = abs(floor_before)
    coverage = 1.0 - abs(floor_after - floor_before) / depth_span if depth_span > 1e-6 else 0.0
    return max(0.0, min(1.0, coverage))


# Functional minimum thickness per layer -- below this a layer isn't doing
# its real job (electrical isolation / diffusion barrier / fill volume)
# regardless of how well it "reaches," so the sweep must not be allowed to
# just pick the thinnest option as if that were a win.
MIN_LINER_THICKNESS = 0.02
MIN_BARRIER_THICKNESS = 0.012
MIN_FILL_THICKNESS = 0.15


def _best_meeting_minimum(results, thickness_key, minimum):
    meeting = [r for r in results if r[thickness_key] >= minimum]
    pool = meeting if meeting else results  # fall back rather than error if none qualify
    pool.sort(key=lambda r: -r["coverage"])
    return pool


def sweep_liner(geo_base):
    thicknesses = [0.015, 0.02, 0.03, 0.04, 0.05]
    stickings = [0.02, 0.05, 0.08, 0.12, 0.2]
    results = []
    for thick in thicknesses:
        for stick in stickings:
            g = ps.Domain(); g.deepCopy(geo_base)
            g.duplicateTopLevelSet(ps.Material.SiO2)
            ps.Process(g, ps.SingleParticleProcess(rate=thick, stickingProbability=stick), 1.0).apply()
            coverage = floor_reach_metric(geo_base, g)
            results.append({"thickness": thick, "sticking": stick, "coverage": coverage})
    return _best_meeting_minimum(results, "thickness", MIN_LINER_THICKNESS)


def sweep_barrier(geo_base):
    thicknesses = [0.01, 0.015, 0.02, 0.03]
    iso_ratios = [0.1, 0.2, 0.3, 0.4, 0.5]
    results = []
    for thick in thicknesses:
        for ratio in iso_ratios:
            g = ps.Domain(); g.deepCopy(geo_base)
            g.duplicateTopLevelSet(ps.Material.Cu)
            model = ps.DirectionalProcess(direction=[0.0, -1.0, 0.0],
                                            directionalVelocity=thick, isotropicVelocity=thick * ratio)
            ps.Process(g, model, 1.0).apply()
            coverage = floor_reach_metric(geo_base, g)
            results.append({"thickness": thick, "iso_ratio": ratio, "coverage": coverage})
    return _best_meeting_minimum(results, "thickness", MIN_BARRIER_THICKNESS)


def sweep_fill_superconformal(geo_base):
    thicknesses = [0.14, 0.18, 0.22, 0.26, 0.30, 0.35]
    iso_ratios = [0.05, 0.1, 0.15, 0.2, 0.3]
    results = []
    for thick in thicknesses:
        for ratio in iso_ratios:
            g = ps.Domain(); g.deepCopy(geo_base)
            g.duplicateTopLevelSet(ps.Material.Cu)
            model = ps.DirectionalProcess(direction=[0.0, -1.0, 0.0],
                                            directionalVelocity=thick, isotropicVelocity=thick * ratio)
            ps.Process(g, model, 1.0).apply()
            coverage = floor_reach_metric(geo_base, g)
            results.append({"thickness": thick, "iso_ratio": ratio, "coverage": coverage})
    return _best_meeting_minimum(results, "thickness", MIN_FILL_THICKNESS)


def main():
    t0 = time.time()
    winner = load_etch_winner()
    print(f"using etch winner: ion={winner['ion']} neutral={winner['neutral']} "
          f"etch_time={winner['etch_time']} depo_thick={winner['depo_thick']}")

    geo_etched, depth = base_geometry(winner)
    print(f"production etch: depth={depth:.3f} ({time.time()-t0:.0f}s)")

    liner_results = sweep_liner(geo_etched)
    best_liner = liner_results[0]
    print(f"liner sweep: {len(liner_results)} runs, best={best_liner} ({time.time()-t0:.0f}s)")

    geo_liner = ps.Domain(); geo_liner.deepCopy(geo_etched)
    geo_liner.duplicateTopLevelSet(ps.Material.SiO2)
    ps.Process(geo_liner, ps.SingleParticleProcess(
        rate=best_liner["thickness"], stickingProbability=best_liner["sticking"]), 1.0).apply()

    barrier_results = sweep_barrier(geo_liner)
    best_barrier = barrier_results[0]
    print(f"barrier sweep: {len(barrier_results)} runs, best={best_barrier} ({time.time()-t0:.0f}s)")

    geo_barrier = ps.Domain(); geo_barrier.deepCopy(geo_liner)
    geo_barrier.duplicateTopLevelSet(ps.Material.Cu)
    ps.Process(geo_barrier, ps.DirectionalProcess(
        direction=[0.0, -1.0, 0.0], directionalVelocity=best_barrier["thickness"],
        isotropicVelocity=best_barrier["thickness"] * best_barrier["iso_ratio"]), 1.0).apply()

    fill_results = sweep_fill_superconformal(geo_barrier)
    best_fill = fill_results[0]
    print(f"fill sweep: {len(fill_results)} runs, best={best_fill} ({time.time()-t0:.0f}s)")

    out = {
        "etch_winner": winner,
        "production_depth": depth,
        "best_liner": best_liner,
        "best_barrier": best_barrier,
        "best_fill_superconformal": best_fill,
        "liner_top5": liner_results[:5],
        "barrier_top5": barrier_results[:5],
        "fill_top5": fill_results[:5],
    }
    with open("sweep_downstream_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\ntotal time: {time.time()-t0:.0f}s")
    print("saved sweep_downstream_results.json")


if __name__ == "__main__":
    main()

"""Run the archived downstream parameter sweeps."""
import json
import time
import viennaps as ps
import tsv_process as tp
from legacy_metric_guard import require_legacy_metric_override

require_legacy_metric_override()


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


def sweep_liner(geo_base):
    y_before = tp.profile_points(geo_base)[:, 1].min()
    thicknesses = [0.015, 0.02, 0.03, 0.04, 0.05]
    stickings = [0.02, 0.05, 0.08, 0.12, 0.2]
    results = []
    for thick in thicknesses:
        for stick in stickings:
            g = ps.Domain(); g.deepCopy(geo_base)
            g.duplicateTopLevelSet(ps.Material.SiO2)
            ps.Process(g, ps.SingleParticleProcess(rate=thick, stickingProbability=stick), 1.0).apply()
            coverage = tp.floor_reach_metric(y_before, tp.profile_points(g))
            results.append(tp.with_target_score("liner", {
                "thickness": thick, "sticking": stick, "coverage": coverage,
            }))
    return sorted(results, key=lambda r: (not r["target_pass"], r["target_score"]))


def sweep_barrier(geo_base):
    y_before = tp.profile_points(geo_base)[:, 1].min()
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
            coverage = tp.floor_reach_metric(y_before, tp.profile_points(g))
            results.append(tp.with_target_score("barrier", {
                "thickness": thick, "iso_ratio": ratio, "coverage": coverage,
            }))
    return sorted(results, key=lambda r: (not r["target_pass"], r["target_score"]))


def sweep_fill_superconformal(geo_base):
    y_before = tp.profile_points(geo_base)[:, 1].min()
    thicknesses = [0.08, 0.10, 0.12, 0.14, 0.15, 0.155, 0.16, 0.18, 0.22, 0.26, 0.30]
    iso_ratios = [0.0, 0.001, 0.0025, 0.005, 0.01, 0.02, 0.03, 0.05, 0.1, 0.2, 0.3]
    results = []
    for thick in thicknesses:
        for ratio in iso_ratios:
            g = ps.Domain(); g.deepCopy(geo_base)
            g.duplicateTopLevelSet(ps.Material.Cu)
            model = ps.DirectionalProcess(direction=[0.0, -1.0, 0.0],
                                            directionalVelocity=thick, isotropicVelocity=thick * ratio)
            ps.Process(g, model, 1.0).apply()
            pts = tp.profile_points(g)
            coverage = tp.floor_reach_metric(y_before, pts)
            tip_gap = tp.fill_tip_gap(pts, y_before)
            results.append(tp.with_target_score("fill", {
                "thickness": thick, "iso_ratio": ratio, "coverage": coverage, "tip_gap": tip_gap,
            }))
    return sorted(results, key=lambda r: (not r["target_pass"], r["target_score"]))


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
        "target_specs": tp.TARGET_SPECS,
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

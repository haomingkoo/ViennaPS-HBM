"""Run the archived joint five-step sensitivity study."""
import json
import time
import viennaps as ps
import tsv_process as tp
from legacy_metric_guard import require_legacy_metric_override

require_legacy_metric_override()

ETCH_FIXED = dict(ion_source_exponent=200, deposition_thickness=0.01)
ETCH_TOP4_WINNER = dict(neutral_sticking_probability=0.05, initial_etch_time=0.3, neutral_rate=-0.1)
NUM_CYCLES = 14  # depth-matched to the new winner, see prepare.md item 17
RADIUS = 0.15

MASK_TAPERS = [0.0, 4.0]
ETCH_TIMES = [0.4, 0.5]  # centered on the sweep_top4 winner (0.5 is dominant -- item 17)
LINER_THICKNESSES = [0.018, 0.028]
LINER_STICKING = 0.3  # comprehensive-DOE plateau winner, held fixed
BARRIER_THICKNESSES = [0.012, 0.018]
BARRIER_ISO_RATIO = 0.2  # confirmed zero-effect knob, held at a reasonable default
FILL_THICKNESSES = [0.18, 0.22]
FILL_ISO_RATIOS = [0.03, 0.1]
def build_etch_base(mask_taper, etch_time):
    # Reuse one etched shape for fair downstream comparisons.
    geo = ps.Domain(gridDelta=0.01, xExtent=1.0, yExtent=1.5)
    ps.MakeHole(domain=geo, holeRadius=RADIUS, holeDepth=0.0, maskHeight=0.3,
                maskTaperAngle=mask_taper, holeShape=ps.HoleShape.QUARTER).apply()
    geo, depth = tp.bosch_etch(geo, num_cycles=NUM_CYCLES, radius=RADIUS, etch_time=etch_time,
                                **ETCH_FIXED, **ETCH_TOP4_WINNER)
    pts = tp.profile_points(geo)
    bulge = tp.wall_bulge(pts, depth, RADIUS)
    width_error = tp.width_error(pts, depth, RADIUS)
    return geo, depth, bulge, width_error


def run_downstream(geo_etch_base, liner_thick, barrier_thick, fill_thick, fill_iso):
    geo = ps.Domain(); geo.deepCopy(geo_etch_base)
    y_etched = tp.profile_points(geo)[:, 1].min()
    geo = tp.deposit_conformal(geo, ps.Material.SiO2, liner_thick, directional=False, sticking=LINER_STICKING)
    pts_liner = tp.profile_points(geo)
    liner_coverage = tp.floor_reach_metric(y_etched, pts_liner)
    y_liner = pts_liner[:, 1].min()
    geo = tp.deposit_conformal(geo, ps.Material.Cu, barrier_thick, directional=True, iso_ratio=BARRIER_ISO_RATIO)
    pts_barrier = tp.profile_points(geo)
    barrier_coverage = tp.floor_reach_metric(y_liner, pts_barrier)
    via_floor = pts_barrier[:, 1].min()
    geo_fill = tp.cu_fill(geo, fill_thick, directional=True, iso_ratio=fill_iso)
    pts_fill = tp.profile_points(geo_fill)
    return {
        "liner_coverage": liner_coverage,
        "barrier_coverage": barrier_coverage,
        "tip_gap": tp.fill_tip_gap(pts_fill, via_floor),
    }


def score_row(row):
    step_scores = {
        "pattern": tp.with_target_score("pattern", {
            "radius": RADIUS,
            "width": 2.0 * RADIUS,
            "mask_height": 0.3,
        }),
        "etch": tp.with_target_score("etch", {
            "depth": row["depth"],
            "bulge": row["bulge"],
            "width_error": row["width_error"],
        }),
        "liner": tp.with_target_score("liner", {
            "thickness": row["liner_thick"],
            "coverage": row["liner_coverage"],
        }),
        "barrier": tp.with_target_score("barrier", {
            "thickness": row["barrier_thick"],
            "coverage": row["barrier_coverage"],
        }),
        "fill": tp.with_target_score("fill", {
            "thickness": row["fill_thick"],
            "tip_gap": row["tip_gap"],
        }),
    }
    row["target_pass"] = all(s["target_pass"] for s in step_scores.values())
    row["target_score"] = float(sum(s["target_score"] for s in step_scores.values()))
    row["step_scores"] = {step: {"target_pass": score["target_pass"],
                                 "target_score": score["target_score"]}
                          for step, score in step_scores.items()}
    return row


def main():
    t0 = time.time()
    results = []
    n = 0
    total = len(MASK_TAPERS) * len(ETCH_TIMES) * len(LINER_THICKNESSES) * len(BARRIER_THICKNESSES) \
        * len(FILL_THICKNESSES) * len(FILL_ISO_RATIOS)
    for mt in MASK_TAPERS:
        for et in ETCH_TIMES:
            geo_base, depth, bulge, width_error = build_etch_base(mt, et)
            for lt in LINER_THICKNESSES:
                for bt in BARRIER_THICKNESSES:
                    for ft in FILL_THICKNESSES:
                        for fi in FILL_ISO_RATIOS:
                            downstream = run_downstream(geo_base, lt, bt, ft, fi)
                            row = {"mask_taper": mt, "etch_time": et, "liner_thick": lt,
                                   "barrier_thick": bt, "fill_thick": ft, "fill_iso": fi,
                                   "depth": depth, "bulge": bulge, "width_error": width_error,
                                   **downstream}
                            results.append(score_row(row))
                            n += 1
            json.dump(results, open("sweep_joint_5steps_results.json", "w"), indent=2)
            print(f"{n}/{total} ({time.time()-t0:.0f}s) -- finished (mask_taper={mt}, etch_time={et})", flush=True)
    json.dump(results, open("sweep_joint_5steps_results.json", "w"), indent=2)

    valid = [r for r in results if r.get("bulge") is not None and r.get("tip_gap") is not None]
    print(f"\ntotal: {len(results)}, valid: {len(valid)}, time={time.time()-t0:.0f}s")
    by_spec = sorted(valid, key=lambda r: (not r["target_pass"], r["target_score"]))
    by_bulge = sorted(valid, key=lambda r: r["bulge"])
    by_gap = sorted(valid, key=lambda r: r["tip_gap"])
    print("best 3 by all-step target spec:")
    for r in by_spec[:3]:
        print(f"  {r}")
    print("best by etch bulge:")
    print(f"  {by_bulge[0]}")
    print("best by fill tip_gap:")
    print(f"  {by_gap[0]}")
    print(f"does raw-bulge optimum match all-step spec optimum? {by_bulge[0] == by_spec[0]}")
    print(f"does raw-gap optimum match all-step spec optimum? {by_gap[0] == by_spec[0]}")


if __name__ == "__main__":
    main()

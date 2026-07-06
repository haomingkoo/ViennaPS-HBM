"""Joint multi-step DOE across the *effective* tuning knobs found by
per-step screening (prepare.md items 10-16), not per-step isolated
sweeps. Each step so far was optimized against the previous step's own
output in sequence (sweep_downstream.py / sweep_downstream_comprehensive.py)
-- this checks whether that sequential-local optimum is also the joint/
global one, by varying the effective knobs from all 5 steps together and
looking for cross-step interaction.

Effective knobs included (per-step screening rationale in prepare.md):
- Patterning: maskTaperAngle (real, non-monotonic effect, item 16)
- Etch: etch_time (dominant knob, near the sweep_top4 winner)
- Liner: thickness (sticking plateaus above ~0.2 -- item 15, held fixed)
- Barrier: thickness (iso_ratio has zero effect -- item 15, held fixed)
- Fill: thickness AND iso_ratio (both matter for the strict tip-gap
  metric, even though the coarser coverage metric saturates -- item 6, 15)

CMP is deliberately NOT part of this search: item 13/14 already found it's
a documented trade-off curve (dishing vs. mask survival), not a knob with
a joint optimum to discover. It's applied once at the end at a fixed,
realistic setting for reporting only.

Two metrics are tracked, not collapsed into one fake composite score:
etch wall bulge (straightness) and the fill tip-gap (CEAC-limited
residual, the stricter metric from item 6) -- if their optima don't
coincide, that's reported as a real trade-off, not hidden.
"""
import json
import time
import numpy as np
import viennaps as ps
import tsv_process as tp

# etch's non-varied knobs, fixed at the sweep_top4.py winner (prepare.md item 17)
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
CMP_MULT = 1.0  # realistic "clear the nominal overburden" choice -- not searched, see module docstring


def build_etch_base(mask_taper, etch_time):
    # etch uses a ray-traced MultiParticleProcess with real run-to-run MC
    # noise (prepare.md item 12) -- build ONCE per (mask_taper, etch_time)
    # and deep-copy it for every downstream combo, or the etch noise
    # contaminates the liner/barrier/fill comparison (exactly the item-12
    # trap: this script hit it once already before this fix).
    geo = ps.Domain(gridDelta=0.01, xExtent=1.0, yExtent=1.5)
    ps.MakeHole(domain=geo, holeRadius=RADIUS, holeDepth=0.0, maskHeight=0.3,
                maskTaperAngle=mask_taper, holeShape=ps.HoleShape.QUARTER).apply()
    geo, depth = tp.bosch_etch(geo, num_cycles=NUM_CYCLES, radius=RADIUS, etch_time=etch_time,
                                **ETCH_FIXED, **ETCH_TOP4_WINNER)
    pts = tp.profile_points(geo)
    body = pts[(pts[:, 1] > depth * 0.85) & (pts[:, 1] < 0.2) & (pts[:, 0] > 0.2 * RADIUS)]
    bulge = float(np.max(np.abs(body[:, 0] - RADIUS))) if len(body) else None
    return geo, depth, bulge


def run_downstream(geo_etch_base, liner_thick, barrier_thick, fill_thick, fill_iso):
    geo = ps.Domain(); geo.deepCopy(geo_etch_base)
    geo = tp.deposit_conformal(geo, ps.Material.SiO2, liner_thick, directional=False, sticking=LINER_STICKING)
    geo = tp.deposit_conformal(geo, ps.Material.Cu, barrier_thick, directional=True, iso_ratio=BARRIER_ISO_RATIO)
    via_floor = tp.profile_points(geo)[:, 1].min()
    geo_fill = tp.cu_fill(geo, fill_thick, directional=True, iso_ratio=fill_iso)
    pts_fill = tp.profile_points(geo_fill)
    center = pts_fill[np.abs(pts_fill[:, 0]) < 0.02]
    seal = float(center[:, 1].mean()) if len(center) else None
    tip_gap = (seal - via_floor) if seal is not None else None
    return tip_gap


def main():
    t0 = time.time()
    results = []
    n = 0
    total = len(MASK_TAPERS) * len(ETCH_TIMES) * len(LINER_THICKNESSES) * len(BARRIER_THICKNESSES) \
        * len(FILL_THICKNESSES) * len(FILL_ISO_RATIOS)
    for mt in MASK_TAPERS:
        for et in ETCH_TIMES:
            geo_base, depth, bulge = build_etch_base(mt, et)
            for lt in LINER_THICKNESSES:
                for bt in BARRIER_THICKNESSES:
                    for ft in FILL_THICKNESSES:
                        for fi in FILL_ISO_RATIOS:
                            tip_gap = run_downstream(geo_base, lt, bt, ft, fi)
                            results.append({"mask_taper": mt, "etch_time": et, "liner_thick": lt,
                                             "barrier_thick": bt, "fill_thick": ft, "fill_iso": fi,
                                             "depth": depth, "bulge": bulge, "tip_gap": tip_gap})
                            n += 1
            json.dump(results, open("sweep_joint_5steps_results.json", "w"), indent=2)
            print(f"{n}/{total} ({time.time()-t0:.0f}s) -- finished (mask_taper={mt}, etch_time={et})", flush=True)
    json.dump(results, open("sweep_joint_5steps_results.json", "w"), indent=2)

    valid = [r for r in results if r.get("bulge") is not None and r.get("tip_gap") is not None]
    print(f"\ntotal: {len(results)}, valid: {len(valid)}, time={time.time()-t0:.0f}s")
    by_bulge = sorted(valid, key=lambda r: r["bulge"])
    by_gap = sorted(valid, key=lambda r: r["tip_gap"])
    print("best 3 by etch bulge:")
    for r in by_bulge[:3]:
        print(f"  {r}")
    print("best 3 by fill tip_gap:")
    for r in by_gap[:3]:
        print(f"  {r}")
    print(f"do the two optima coincide? {by_bulge[0] == by_gap[0]}")


if __name__ == "__main__":
    main()

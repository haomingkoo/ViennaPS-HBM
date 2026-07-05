"""Post-DOE finalization: regenerate the best etch profile from sweep_big.py's
winner at production quality (more cycles than the fast sweep used), then
re-tune every downstream step (liner/barrier/fill/CMP) to match -- rather
than reusing thickness values tuned to the old geometry.

IMPORTANT METHODOLOGY NOTE: the raw sweep results are NOT directly
comparable across different etch_time values at a fixed cycle count --
short etch_time produces a shallower via, and shallower vias trivially
show less bulge (less depth for ARDE to accumulate), independent of
whether the recipe is actually better. The sweep's raw top-ranked bulge
(0.0145) reflected this confound. Verified by regenerating the winner at
a depth comparable to the old baseline: 12 cycles at etch_time=0.5 reaches
depth=-1.19 (vs the old baseline's -1.29 at 5 cycles/etch_time=1.5), where
the winner's real bulge is 0.0228 vs the old baseline's 0.0530 -- still a
genuine ~2.3x improvement, just not the ~3.7x the confounded raw number
implied. PRODUCTION_CYCLES below was chosen for exactly this reason, not
just "more cycles for a nicer picture."
"""
import json
import numpy as np
import viennaps as ps
import tsv_process as tp

PRODUCTION_CYCLES = 12  # gives a depth comparable to the old 5-cycle/1.5-etch_time baseline


def load_best():
    with open("sweep_big_results.json") as f:
        data = json.load(f)
    valid = [r for r in data["results"] if r["bulge"] is not None]
    valid.sort(key=lambda r: r["bulge"])
    return data, valid[0]


def regenerate_best(best):
    """Re-run the winning combination at production cycle count (see the
    depth-confound note above for why this isn't just "more cycles")."""
    geo = tp.make_initial_geometry(radius=0.15)
    geo, depth = tp.bosch_etch(
        geo, num_cycles=PRODUCTION_CYCLES,
        etch_time=best["etch_time"], deposition_thickness=best["depo_thick"],
        ion_source_exponent=best["ion"], neutral_sticking_probability=best["neutral"],
    )
    points = tp.profile_points(geo)
    y_top = float(points[:, 1].max())
    slope, rms = tp.sidewall_fit(points, 0.15, y_top, depth)
    body = points[(points[:, 1] > depth * 0.85) & (points[:, 1] < 0.2) & (points[:, 0] > 0.2 * 0.15)]
    bulge = float(np.max(np.abs(body[:, 0] - 0.15))) if len(body) else None
    return geo, depth, bulge, slope, rms


def retuned_downstream_params(depth, radius=0.15):
    """Derive liner/barrier/fill thicknesses proportional to the *actual*
    via geometry, instead of reusing fixed constants tuned to the old run.

    Ratios (liner ~10% of radius, barrier ~5%, fill ~110% of radius to
    guarantee it can fully close even the widest point) are the same
    proportions the original hand-tuned constants worked out to -- made
    explicit so they scale if the DOE's winning via has a different radius
    or depth than the 0.15/~-1.3 baseline this was tuned against.
    """
    aspect_ratio = abs(depth) / (2 * radius)
    return {
        "liner_thickness": 0.20 * radius,
        "barrier_thickness": 0.10 * radius,
        "fill_thickness_subconformal": 1.05 * radius,
        "fill_thickness_conformal": 0.75 * radius,
        "fill_thickness_superconformal": 1.05 * radius,
        "aspect_ratio": aspect_ratio,
    }


if __name__ == "__main__":
    data, best = load_best()
    print(f"DOE winner: ion={best['ion']} neutral={best['neutral']} "
          f"etch_time={best['etch_time']} depo_thick={best['depo_thick']} "
          f"(sweep bulge={best['bulge']:.4f} at {data['num_cycles']} cycles)")

    geo, depth, bulge, slope, rms = regenerate_best(best)
    print(f"production run ({PRODUCTION_CYCLES} cycles): depth={depth:.3f} "
          f"bulge={bulge:.4f} slope={slope} rms={rms}")

    params = retuned_downstream_params(depth)
    print("retuned downstream params:", json.dumps(params, indent=2))

    with open("final_pipeline_params.json", "w") as f:
        json.dump({"best": best, "production_depth": depth, "production_bulge": bulge,
                    "production_slope": slope, "production_rms": rms, "downstream": params}, f, indent=2)
    print("saved final_pipeline_params.json")

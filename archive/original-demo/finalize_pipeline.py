"""Rebuild the archived post-DOE pipeline."""
import json
import numpy as np
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
    """Scale archived downstream controls with the via radius."""
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

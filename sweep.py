"""2-parameter sensitivity sweep on the Bosch etch step.

Varies ion directionality (ion_source_exponent) against the isotropic/
chemical etch component (neutral_sticking_probability) to find which one
actually drives sidewall straightness vs. scalloping, and where the stable
"sweet spot" process window sits.
"""
import json
import numpy as np
import viennaps as ps
import tsv_process as tp

ION_EXPONENTS = [50, 125, 200, 400, 800]
NEUTRAL_STICKING = [0.02, 0.06, 0.1, 0.2, 0.3]
RADIUS = 0.15
NUM_CYCLES = 5  # reduced from the 10-cycle "hero" run, for sweep speed


def run_point(ion_exponent, neutral_sticking):
    geometry = tp.make_initial_geometry(radius=RADIUS)
    geometry, depth = tp.bosch_etch(
        geometry, num_cycles=NUM_CYCLES,
        ion_source_exponent=ion_exponent,
        neutral_sticking_probability=neutral_sticking,
    )
    points = tp.profile_points(geometry)
    y_top = float(points[:, 1].max())
    slope, rms = tp.sidewall_fit(points, RADIUS, y_top, depth)
    display_points = tp.trim_for_display(points, 0.31)
    return {
        "ion_source_exponent": ion_exponent,
        "neutral_sticking_probability": neutral_sticking,
        "depth": depth,
        "slope": slope,
        "scallop_rms": rms,
        "profile": display_points.tolist(),
    }


def main():
    results = []
    for ion_exp in ION_EXPONENTS:
        for neutral in NEUTRAL_STICKING:
            r = run_point(ion_exp, neutral)
            slope_s = f"{r['slope']:.4f}" if r["slope"] is not None else "n/a"
            rms_s = f"{r['scallop_rms']:.4f}" if r["scallop_rms"] is not None else "n/a"
            print(f"ion_exp={ion_exp:>4} neutral={neutral:.2f} "
                  f"-> depth={r['depth']:.3f} slope={slope_s} scallop_rms={rms_s}")
            results.append(r)

    with open("sweep_results.json", "w") as f:
        json.dump({
            "radius": RADIUS, "num_cycles": NUM_CYCLES,
            "ion_exponents": ION_EXPONENTS, "neutral_sticking": NEUTRAL_STICKING,
            "results": results,
        }, f)

    # which knob moves the outcome more: variance of scallop_rms across each axis
    rms_grid = np.array(
        [r["scallop_rms"] if r["scallop_rms"] is not None else np.nan for r in results]
    ).reshape(len(ION_EXPONENTS), len(NEUTRAL_STICKING))
    ion_effect = np.ptp(np.nanmean(rms_grid, axis=1))
    neutral_effect = np.ptp(np.nanmean(rms_grid, axis=0))
    dominant = "ion_source_exponent" if ion_effect > neutral_effect else "neutral_sticking_probability"
    print(f"\nion_source_exponent effect range: {ion_effect:.4f}")
    print(f"neutral_sticking_probability effect range: {neutral_effect:.4f}")
    print(f"real tuning knob for scalloping: {dominant}")

    valid = [r for r in results if r["slope"] is not None]
    best = min(valid, key=lambda r: abs(r["slope"]) + r["scallop_rms"])
    print(f"sweet spot: ion_exp={best['ion_source_exponent']} "
          f"neutral={best['neutral_sticking_probability']} "
          f"(slope={best['slope']:.4f}, scallop_rms={best['scallop_rms']:.4f})")


if __name__ == "__main__":
    main()

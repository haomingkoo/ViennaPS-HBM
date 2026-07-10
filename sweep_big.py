"""Expanded 4-parameter sweep on the Bosch etch step.

768 real ViennaPS runs (8x8x4x3): ion_source_exponent x
neutral_sticking_probability x etch_time x deposition_thickness.
Explicitly NOT a calibrated DOE (no fab measurement data, no replication
for noise) -- this is a dense sensitivity sweep over simulation model
coefficients. See README for that caveat in full.
"""
import json
import time
import numpy as np
import tsv_process as tp

ION_EXPONENTS = [50, 125, 200, 300, 400, 600, 800, 1000]
NEUTRAL_STICKING = [0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.25, 0.3]
ETCH_TIMES = [0.5, 1.0, 1.5, 2.0]
DEPOSITION_THICKNESS = [0.01, 0.02, 0.04]
RADIUS = 0.15
NUM_CYCLES = 3  # reduced from the 5-cycle "hero" run -- 768 runs need to be fast


def run_point(ion_exp, neutral, etch_time, depo_thick):
    geometry = tp.make_initial_geometry(radius=RADIUS)
    geometry, depth = tp.bosch_etch(
        geometry, num_cycles=NUM_CYCLES, etch_time=etch_time,
        deposition_thickness=depo_thick,
        ion_source_exponent=ion_exp, neutral_sticking_probability=neutral,
    )
    points = tp.profile_points(geometry)
    y_top = float(points[:, 1].max())
    slope, rms = tp.sidewall_fit(points, RADIUS, y_top, depth)
    bulge = tp.wall_bulge(points, depth, RADIUS)
    result = {
        "ion": ion_exp, "neutral": neutral, "etch_time": etch_time, "depo_thick": depo_thick,
        "depth": depth, "slope": slope, "rms": rms, "bulge": bulge,
        "width_error": tp.width_error(points, depth, RADIUS),
    }
    return tp.with_target_score("etch", result)


def main():
    results = []
    total = len(ION_EXPONENTS) * len(NEUTRAL_STICKING) * len(ETCH_TIMES) * len(DEPOSITION_THICKNESS)
    t0 = time.time()
    n = 0
    for ion_exp in ION_EXPONENTS:
        for neutral in NEUTRAL_STICKING:
            for etch_time in ETCH_TIMES:
                for depo_thick in DEPOSITION_THICKNESS:
                    n += 1
                    r = run_point(ion_exp, neutral, etch_time, depo_thick)
                    results.append(r)
                    elapsed = time.time() - t0
                    rate = n / elapsed
                    eta = (total - n) / rate
                    filled = int(40 * n / total)
                    bar = "#" * filled + "-" * (40 - filled)
                    print(f"[{bar}] {n}/{total}  elapsed={elapsed:.0f}s  eta={eta:.0f}s", flush=True)

    with open("sweep_big_results.json", "w") as f:
        json.dump({
            "ion_exponents": ION_EXPONENTS, "neutral_sticking": NEUTRAL_STICKING,
            "etch_times": ETCH_TIMES, "deposition_thickness": DEPOSITION_THICKNESS,
            "num_cycles": NUM_CYCLES, "radius": RADIUS, "results": results,
        }, f)

    valid = [r for r in results if r["bulge"] is not None]
    valid.sort(key=lambda r: (not r["target_pass"], r["target_score"]))
    print(f"\ntotal runs: {len(results)}, valid (fittable): {len(valid)}")
    print("top 5 by etch target spec:")
    for r in valid[:5]:
        print(f"  ion={r['ion']:>4} neutral={r['neutral']:.2f} etch_time={r['etch_time']} "
              f"depo_thick={r['depo_thick']:.2f} -> depth={r['depth']:.3f} "
              f"bulge={r['bulge']:.4f} score={r['target_score']:.4f} "
              f"pass={r['target_pass']}")

    # which parameter has the biggest effect: range of mean bulge across its levels
    import itertools
    for name, values, key in [
        ("ion_source_exponent", ION_EXPONENTS, "ion"),
        ("neutral_sticking_probability", NEUTRAL_STICKING, "neutral"),
        ("etch_time", ETCH_TIMES, "etch_time"),
        ("deposition_thickness", DEPOSITION_THICKNESS, "depo_thick"),
    ]:
        means = [np.mean([r["bulge"] for r in valid if r[key] == v]) for v in values]
        print(f"{name}: effect range = {max(means) - min(means):.4f}")


if __name__ == "__main__":
    main()

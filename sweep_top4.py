"""Combined 4-parameter DOE on the *real* top-4 knobs found by the
screening pass (screen_all_knobs.py): etch_time and
neutral_sticking_probability (already known, from the original 768-run
DOE) x initial_etch_time and neutral_rate (newly found to matter more
than deposition_thickness/ion_source_exponent, which this sweep holds
fixed at their already-known-good values -- a deliberate scope limit,
not a silent omission: interactions between the top-4 and the
lower-ranked 7 are not tested here).
"""
import json
import time
import numpy as np
import tsv_process as tp

ETCH_TIMES = [0.5, 1.0, 1.5, 2.0]
NEUTRAL_STICKING = [0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.25, 0.3]
INITIAL_ETCH_TIMES = [0.1, 0.2, 0.3, 0.45, 0.6]
NEUTRAL_RATES = [-0.1, -0.15, -0.2, -0.3, -0.4]
FIXED_ION_SOURCE_EXPONENT = 200
FIXED_DEPOSITION_THICKNESS = 0.01
RADIUS = 0.15
NUM_CYCLES = 3


def run_point(etch_time, neutral, initial_etch_time, neutral_rate):
    geometry = tp.make_initial_geometry(radius=RADIUS)
    try:
        geometry, depth = tp.bosch_etch(
            geometry, num_cycles=NUM_CYCLES, etch_time=etch_time,
            neutral_sticking_probability=neutral, initial_etch_time=initial_etch_time,
            neutral_rate=neutral_rate,
            ion_source_exponent=FIXED_ION_SOURCE_EXPONENT,
            deposition_thickness=FIXED_DEPOSITION_THICKNESS,
        )
    except AssertionError as e:
        # some corners of this parameter space are non-functional recipes
        # (e.g. net deposition instead of etch) -- that's a real DOE finding,
        # not a bug; record it and keep going instead of losing the whole sweep.
        return {"etch_time": etch_time, "neutral": neutral, "initial_etch_time": initial_etch_time,
                "neutral_rate": neutral_rate, "depth": None, "bulge": None, "error": str(e)}
    points = tp.profile_points(geometry)
    body = points[(points[:, 1] > depth * 0.85) & (points[:, 1] < 0.2) & (points[:, 0] > 0.2 * RADIUS)]
    bulge = float(np.max(np.abs(body[:, 0] - RADIUS))) if len(body) else None
    return {"etch_time": etch_time, "neutral": neutral, "initial_etch_time": initial_etch_time,
            "neutral_rate": neutral_rate, "depth": depth, "bulge": bulge}


def save(results):
    json.dump({
        "etch_times": ETCH_TIMES, "neutral_sticking": NEUTRAL_STICKING,
        "initial_etch_times": INITIAL_ETCH_TIMES, "neutral_rates": NEUTRAL_RATES,
        "fixed_ion_source_exponent": FIXED_ION_SOURCE_EXPONENT,
        "fixed_deposition_thickness": FIXED_DEPOSITION_THICKNESS,
        "num_cycles": NUM_CYCLES, "radius": RADIUS, "results": results,
    }, open("sweep_top4_results.json", "w"))


def main():
    results = []
    total = len(ETCH_TIMES) * len(NEUTRAL_STICKING) * len(INITIAL_ETCH_TIMES) * len(NEUTRAL_RATES)
    t0 = time.time()
    n = 0
    for et in ETCH_TIMES:
        for neutral in NEUTRAL_STICKING:
            for iet in INITIAL_ETCH_TIMES:
                for nr in NEUTRAL_RATES:
                    n += 1
                    r = run_point(et, neutral, iet, nr)
                    results.append(r)
                    elapsed = time.time() - t0
                    eta = (total - n) / (n / elapsed)
                    filled = int(40 * n / total)
                    bar = "#" * filled + "-" * (40 - filled)
                    print(f"[{bar}] {n}/{total}  elapsed={elapsed:.0f}s  eta={eta:.0f}s", flush=True)
                    if n % 25 == 0:
                        save(results)  # checkpoint -- a later crash shouldn't lose earlier runs

    save(results)

    valid = [r for r in results if r["bulge"] is not None]
    valid.sort(key=lambda r: r["bulge"])
    print(f"\ntotal runs: {len(results)}, valid: {len(valid)}")
    print("top 5 lowest-bulge combinations:")
    for r in valid[:5]:
        print(f"  etch_time={r['etch_time']} neutral={r['neutral']:.2f} "
              f"initial_etch_time={r['initial_etch_time']} neutral_rate={r['neutral_rate']:.2f} "
              f"-> bulge={r['bulge']:.4f}")

    for name, values, key in [
        ("etch_time", ETCH_TIMES, "etch_time"),
        ("neutral_sticking_probability", NEUTRAL_STICKING, "neutral"),
        ("initial_etch_time", INITIAL_ETCH_TIMES, "initial_etch_time"),
        ("neutral_rate", NEUTRAL_RATES, "neutral_rate"),
    ]:
        means = [np.mean([r["bulge"] for r in valid if r[key] == v]) for v in values]
        print(f"{name}: effect range = {max(means) - min(means):.4f}")


if __name__ == "__main__":
    main()

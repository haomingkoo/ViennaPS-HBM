"""Run the archived one-factor Bosch parameter screen."""
import json
import time
import numpy as np
import tsv_process as tp

BASELINE = dict(
    radius=0.15, mask_height=0.3,
    ion_source_exponent=200, neutral_sticking_probability=0.2,
    etch_time=0.5, deposition_thickness=0.01,
    deposition_sticking_probability=0.01, neutral_rate=-0.2, ion_rate=-0.1,
    initial_etch_time=0.3, theta_r_min=60.0,
)
NUM_CYCLES = 12

SCREEN = {
    "deposition_sticking_probability": (0.005, 0.05),
    "neutral_rate": (-0.1, -0.4),
    "ion_rate": (-0.05, -0.2),
    "initial_etch_time": (0.1, 0.6),
    "mask_height": (0.2, 0.4),
    "theta_r_min": (45.0, 75.0),
    "radius": (0.10, 0.20),
}


def run(params):
    radius = params["radius"]
    mask_height = params["mask_height"]
    geo = tp.make_initial_geometry(radius=radius, mask_height=mask_height)
    etch_kwargs = {k: v for k, v in params.items() if k not in ("radius", "mask_height")}
    geo, depth = tp.bosch_etch(geo, num_cycles=NUM_CYCLES, radius=radius, **etch_kwargs)
    pts = tp.profile_points(geo)
    # Scale the wall window with mask height to exclude the mask edge.
    y_top_margin = mask_height * (2.0 / 3.0)  # baseline: 0.3 * 2/3 = 0.2
    body = pts[(pts[:, 1] > depth * 0.85) & (pts[:, 1] < y_top_margin) & (pts[:, 0] > 0.2 * radius)]
    bulge = float(np.max(np.abs(body[:, 0] - radius))) if len(body) else None
    return depth, bulge


def main():
    t0 = time.time()
    base_depth, base_bulge = run(BASELINE)
    print(f"baseline: depth={base_depth:.3f} bulge={base_bulge:.4f} ({time.time()-t0:.0f}s)")

    results = {"baseline": {"depth": base_depth, "bulge": base_bulge}}
    for param, (lo, hi) in SCREEN.items():
        row = {}
        for label, val in [("low", lo), ("high", hi)]:
            p = dict(BASELINE); p[param] = val
            depth, bulge = run(p)
            row[label] = {"value": val, "depth": depth, "bulge": bulge}
            delta = bulge - base_bulge if bulge is not None and base_bulge is not None else None
            print(f"{param} {label}={val}: depth={depth:.3f} bulge={bulge} "
                  f"(delta from baseline: {delta:+.4f})" if delta is not None else
                  f"{param} {label}={val}: depth={depth:.3f} bulge={bulge}", flush=True)
        results[param] = row

    json.dump(results, open("screen_all_knobs_results.json", "w"), indent=2)
    print(f"\ntotal time: {time.time()-t0:.0f}s")
    print("saved screen_all_knobs_results.json")

    print("\n--- ranked by |max effect from baseline| ---")
    ranked = []
    for param, (lo, hi) in SCREEN.items():
        row = results[param]
        deltas = [abs(row[l]["bulge"] - base_bulge) for l in ("low", "high")
                  if row[l]["bulge"] is not None and base_bulge is not None]
        ranked.append((param, max(deltas) if deltas else 0.0))
    ranked.sort(key=lambda r: -r[1])
    for param, eff in ranked:
        print(f"  {param}: max |delta bulge| = {eff:.4f}")


if __name__ == "__main__":
    main()

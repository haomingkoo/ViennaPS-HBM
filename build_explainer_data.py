"""Regenerate explainer_data.json against current findings: the new
top-4 etch winner, the CMP dishing curve, and the taper-tradeoff
replication (which retracted the fill-side of the original claim).

The interactive explorer's `sweep` slice (etch_time x
neutral_sticking_probability) is recomputed at the new winning
initial_etch_time/neutral_rate instead of the old defaults, so the
"sweet spot" it marks matches the recipe actually in production now.
The original 768-run DOE's `effects` are left as-is (still an accurate
record of that DOE); `effects4` is added alongside it for the new
800-run top-4 DOE, same as the notebook's second bar chart.
"""
import json
import numpy as np
import viennaps as ps
import tsv_process as tp

RADIUS = 0.15
ETCH_TIMES = [0.5, 1.0, 1.5, 2.0]
NEUTRAL_RATES = [-0.1, -0.15, -0.2, -0.3, -0.4]
FIXED = dict(ion_source_exponent=200, deposition_thickness=0.01,
             initial_etch_time=0.3, neutral_sticking_probability=0.05)
PRODUCTION_CYCLES = 14
LINER = dict(thickness=0.02, sticking=0.2)
BARRIER = dict(thickness=0.015, iso_ratio=0.1)
FILL_SUPERCONFORMAL = dict(thickness=0.18, iso_ratio=0.05)


def bulge_at(radius, depth, pts):
    body = pts[(pts[:, 1] > depth * 0.85) & (pts[:, 1] < 0.2) & (pts[:, 0] > 0.2 * radius)]
    return float(np.max(np.abs(body[:, 0] - radius))) if len(body) else None


def profile_list(pts, y_ceiling=0.31):
    trimmed = tp.trim_for_display(pts, y_ceiling)
    return [[round(float(x), 3), round(float(y), 3)] for x, y in trimmed]


def main():
    sweep = []
    for et in ETCH_TIMES:
        for nr in NEUTRAL_RATES:
            geo = tp.make_initial_geometry(radius=RADIUS)
            try:
                geo, depth = tp.bosch_etch(geo, num_cycles=PRODUCTION_CYCLES, radius=RADIUS,
                                            etch_time=et, neutral_rate=nr, **FIXED)
            except AssertionError as e:
                # a real non-functional recipe corner (net deposition, not etch) --
                # skip it rather than lose the whole sweep, same as prepare.md item 17
                print(f"sweep: etch_time={et} neutral_rate={nr} SKIPPED ({e})")
                continue
            pts = tp.profile_points(geo)
            bulge = bulge_at(RADIUS, depth, pts)
            sweep.append({"etch_time": et, "neutral_rate": nr, "depth": round(depth, 3),
                          "bulge": bulge, "profile": profile_list(pts)})
            print(f"sweep: etch_time={et} neutral_rate={nr} depth={depth:.3f} bulge={bulge:.4f}")

    with open("sweep_top4_results.json") as f:
        doe4 = json.load(f)
    valid4 = [r for r in doe4["results"] if r["bulge"] is not None]

    def effect_range4(key, values):
        means = [np.mean([r["bulge"] for r in valid4 if r[key] == v]) for v in values]
        return max(means) - min(means)

    params4 = [
        ("etch_time", doe4["etch_times"], "etch_time"),
        ("neutral_sticking_probability", doe4["neutral_sticking"], "neutral"),
        ("initial_etch_time", doe4["initial_etch_times"], "initial_etch_time"),
        ("neutral_rate", doe4["neutral_rates"], "neutral_rate"),
    ]
    effects4 = [{"name": name, "range": round(effect_range4(key, values), 4)} for name, values, key in params4]
    effects4.sort(key=lambda e: -e["range"])

    # current production fill pipeline, for the failure/fix panel
    geo = tp.make_initial_geometry(radius=RADIUS)
    geo, depth = tp.bosch_etch(geo, num_cycles=PRODUCTION_CYCLES, radius=RADIUS,
                                etch_time=0.5, **FIXED)
    geo = tp.deposit_conformal(geo, ps.Material.SiO2, LINER["thickness"], directional=False, sticking=LINER["sticking"])
    geo = tp.deposit_conformal(geo, ps.Material.Cu, BARRIER["thickness"], directional=True, iso_ratio=BARRIER["iso_ratio"])
    pre_fill_pts = tp.profile_points(geo)
    via_floor = float(pre_fill_pts[:, 1].min())

    geo_naive = ps.Domain(); geo_naive.deepCopy(geo)
    geo_naive = tp.cu_fill(geo_naive, 0.16, directional=False, iso_ratio=0.2)
    pts_naive = tp.profile_points(geo_naive)
    seal_naive = float(pts_naive[np.abs(pts_naive[:, 0]) < 0.02][:, 1].mean())

    geo_dir = ps.Domain(); geo_dir.deepCopy(geo)
    geo_dir = tp.cu_fill(geo_dir, FILL_SUPERCONFORMAL["thickness"], directional=True, iso_ratio=FILL_SUPERCONFORMAL["iso_ratio"])
    pts_dir = tp.profile_points(geo_dir)
    seal_dir = float(pts_dir[np.abs(pts_dir[:, 0]) < 0.02][:, 1].mean())

    fill = {
        # y_ceiling must clear the naive fill's still-open seal height
        # (it barely dents the cavity at this thickness, so its "seal" sits
        # close to the original field height) or trimming cuts off exactly
        # the open-void region the figure is supposed to show.
        "pre_fill_profile": profile_list(pre_fill_pts, 0.5),
        "naive_fill_profile": profile_list(pts_naive, 0.5),
        "directional_fill_profile": profile_list(pts_dir, 0.5),
        "via_floor": round(via_floor, 3),
        "seal_naive": round(seal_naive, 3),
        "seal_dir": round(seal_dir, 3),
    }

    # fill explorer: thickness x iso_ratio grid, directional (superconformal) fill
    FILL_THICKNESSES = [0.14, 0.18, 0.22, 0.26, 0.30]
    FILL_ISO_RATIOS = [0.03, 0.05, 0.1, 0.2, 0.3]
    fill_sweep = []
    for thick in FILL_THICKNESSES:
        for iso in FILL_ISO_RATIOS:
            g = ps.Domain(); g.deepCopy(geo)
            g = tp.cu_fill(g, thick, directional=True, iso_ratio=iso)
            pts = tp.profile_points(g)
            center = pts[np.abs(pts[:, 0]) < 0.02]
            seal = float(center[:, 1].mean()) if len(center) else None
            tip_gap = (seal - via_floor) if seal is not None else None
            fill_sweep.append({"thickness": thick, "iso_ratio": iso, "tip_gap": round(tip_gap, 4),
                                "profile": profile_list(pts, 0.5)})
            print(f"fill_sweep: thickness={thick} iso_ratio={iso} tip_gap={tip_gap:.4f}")

    with open("sweep_downstream_comprehensive_results.json") as f:
        cmp_data = json.load(f)
    cmp_curve = [{"mult": r["mult"], "dish": r["dish"], "mask_consumed": r["mask_consumed"]}
                 for r in cmp_data["cmp_curve"]]

    # taper replication -- kept exactly as run for the notebook correction
    # (prepare.md item 21): shown here so the retraction is visible, not
    # hidden, in the explainer too.
    taper = {
        "bulge_taper0": [0.0127, 0.0080, 0.0125, 0.0126, 0.0127, 0.0126, 0.0127, 0.0127, 0.0079, 0.0087],
        "bulge_taper4": [0.0119] * 10,
        "gap_taper0": [0.1354, 0.1904, 0.2047, 0.1406, 0.1355, 0.2046],
        "gap_taper4": [0.2027, 0.2023, 0.2012, 0.1358, 0.1905, 0.2011],
    }

    out = {
        "etch_times": ETCH_TIMES, "neutral_rates": NEUTRAL_RATES, "radius": RADIUS,
        "total_doe_runs": 768, "total_doe4_runs": len(valid4),
        "effects": [{"name": "etch_time", "range": 0.0967},
                    {"name": "neutral_sticking_probability", "range": 0.0856},
                    {"name": "deposition_thickness", "range": 0.0195},
                    {"name": "ion_source_exponent", "range": 0.0086}],
        "effects4": effects4,
        "sweep": sweep, "fill": fill, "cmp_curve": cmp_curve, "taper": taper,
        "fill_thicknesses": FILL_THICKNESSES, "fill_iso_ratios": FILL_ISO_RATIOS,
        "fill_sweep": fill_sweep, "fill_via_floor": round(via_floor, 3),
        "new_winner": {"etch_time": 0.5, "neutral_sticking_probability": 0.05,
                       "initial_etch_time": 0.3, "neutral_rate": -0.1,
                       "cycles": PRODUCTION_CYCLES, "improvement_x": 1.52},
    }
    with open("explainer_data.json", "w") as f:
        json.dump(out, f)
    print("wrote explainer_data.json")


if __name__ == "__main__":
    main()

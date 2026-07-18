"""Run the archived parallel full-flow sensitivity study."""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import math
import os
import random
import statistics
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import viennaps as ps

import tsv_process as tp
from legacy_metric_guard import require_legacy_metric_override

require_legacy_metric_override()

RADIUS = 0.15
MASK_HEIGHT = 0.3
TARGET_Y = 0.3

SPACE = {
    "mask_taper": [0.0, 2.0, 4.0],
    "num_cycles": [11, 12, 13, 14, 15, 16],
    "etch_time": [0.45, 0.5, 0.55, 0.6],
    "neutral_rate": [-0.06, -0.08, -0.10, -0.12, -0.15],
    "neutral_sticking_probability": [0.05, 0.08, 0.12, 0.16, 0.2],
    "initial_etch_time": [0.15, 0.2, 0.3],
    "deposition_thickness": [0.003, 0.005, 0.01],
    "deposition_sticking_probability": [0.003, 0.005, 0.01],
    "ion_source_exponent": [200, 400, 600],
    "theta_r_min": [45.0, 60.0, 75.0],
    "liner_thickness": [0.02, 0.023, 0.028],
    "liner_sticking": [0.05, 0.2, 0.3],
    "barrier_thickness": [0.012, 0.0143, 0.018],
    "barrier_iso_ratio": [0.0, 0.05, 0.18],
    "fill_thickness": [0.15, 0.155, 0.16, 0.18],
    "fill_iso_ratio": [0.0, 0.001, 0.005, 0.01, 0.03],
    "cmp_mult": [1.0, 1.5, 2.0],
}

ANCHORS = [
    {
        "name": "dry_etch_autoresearch_best",
        "mask_taper": 2.0,
        "num_cycles": 12,
        "etch_time": 0.6,
        "neutral_rate": -0.08,
        "neutral_sticking_probability": 0.2,
        "initial_etch_time": 0.3,
        "deposition_thickness": 0.005,
        "deposition_sticking_probability": 0.003,
        "ion_source_exponent": 600,
        "theta_r_min": 45.0,
        "liner_thickness": 0.02,
        "liner_sticking": 0.2,
        "barrier_thickness": 0.015,
        "barrier_iso_ratio": 0.1,
        "fill_thickness": 0.15,
        "fill_iso_ratio": 0.0,
        "cmp_mult": 1.0,
    },
    {
        "name": "previous_production",
        "mask_taper": 0.0,
        "num_cycles": 14,
        "etch_time": 0.5,
        "neutral_rate": -0.10,
        "neutral_sticking_probability": 0.05,
        "initial_etch_time": 0.3,
        "deposition_thickness": 0.01,
        "deposition_sticking_probability": 0.01,
        "ion_source_exponent": 200,
        "theta_r_min": 60.0,
        "liner_thickness": 0.02,
        "liner_sticking": 0.2,
        "barrier_thickness": 0.015,
        "barrier_iso_ratio": 0.1,
        "fill_thickness": 0.15,
        "fill_iso_ratio": 0.0,
        "cmp_mult": 1.0,
    },
    {
        "name": "etch_target_candidate",
        "mask_taper": 0.0,
        "num_cycles": 14,
        "etch_time": 0.5,
        "neutral_rate": -0.12,
        "neutral_sticking_probability": 0.05,
        "initial_etch_time": 0.3,
        "deposition_thickness": 0.01,
        "deposition_sticking_probability": 0.01,
        "ion_source_exponent": 200,
        "theta_r_min": 60.0,
        "liner_thickness": 0.02,
        "liner_sticking": 0.2,
        "barrier_thickness": 0.015,
        "barrier_iso_ratio": 0.1,
        "fill_thickness": 0.15,
        "fill_iso_ratio": 0.0,
        "cmp_mult": 1.0,
    },
]


def jsonable(value):
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def copy_domain(geometry):
    copied = ps.Domain()
    copied.deepCopy(geometry)
    return copied


def sampled_recipes(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    recipes = [dict(anchor, recipe_id=i) for i, anchor in enumerate(ANCHORS[:count])]
    seen = {recipe_key(r) for r in recipes}
    while len(recipes) < count:
        i = len(recipes)
        recipe = {"recipe_id": i, "name": f"lhs_{i:04d}"}
        for key, values in SPACE.items():
            # Stratified enough for a discrete DOE without adding scipy/skopt.
            recipe[key] = values[(i + rng.randrange(len(values))) % len(values)]
        key = recipe_key(recipe)
        if key in seen:
            continue
        seen.add(key)
        recipes.append(recipe)
    return recipes


def recipe_key(recipe: dict) -> tuple:
    return tuple((key, recipe.get(key)) for key in SPACE)


def existing_keys(path: Path) -> set[tuple[int, int]]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        done.add((row["recipe_id"], row["replicate"]))
    return done


def half_width_at_y(points: np.ndarray, y: float) -> float | None:
    if len(points) == 0:
        return None
    band = max(0.015, float(np.ptp(points[:, 1])) * 0.01)
    near = points[(np.abs(points[:, 1] - y) <= band) & (points[:, 0] >= 0.0)]
    if len(near) < 3:
        idx = np.argsort(np.abs(points[:, 1] - y))[:5]
        near = points[idx]
    if len(near) == 0:
        return None
    return float(np.median(near[:, 0]))


def width_profile(points: np.ndarray, depth: float) -> dict:
    levels = {
        "top_width": -0.10,
        "mid_width": depth * 0.50,
        "bottom_width": depth * 0.85,
    }
    out = {}
    for name, y in levels.items():
        half = half_width_at_y(points, y)
        out[name] = None if half is None else 2.0 * half
    if out["top_width"] is not None and out["bottom_width"] is not None:
        out["taper_width_delta"] = out["top_width"] - out["bottom_width"]
    else:
        out["taper_width_delta"] = None
    return out


def etch_metrics(geometry, depth: float) -> dict:
    pts = tp.profile_points(geometry)
    metrics = {
        "depth": float(depth),
        "bulge": tp.wall_bulge(pts, depth, RADIUS),
        "width_error": tp.width_error(pts, depth, RADIUS),
        **width_profile(pts, depth),
    }
    return tp.with_target_score("etch", metrics)


def coverage_step(step: str, y_before: float, points: np.ndarray, thickness: float) -> dict:
    metrics = {
        "thickness": float(thickness),
        "coverage": tp.floor_reach_metric(y_before, points),
    }
    return tp.with_target_score(step, metrics)


def fill_evolution(geo_barrier, fill_thickness: float, fill_iso_ratio: float, via_floor: float) -> dict:
    doses = sorted(set(round(float(x), 4) for x in np.linspace(0.02, fill_thickness, 7)))
    evolution = []
    pinch_dose = None
    for dose in doses:
        g = ps.Domain()
        g.deepCopy(geo_barrier)
        g = tp.cu_fill(g, dose, directional=True, iso_ratio=fill_iso_ratio)
        pts = tp.profile_points(g)
        gap = tp.fill_tip_gap(pts, via_floor)
        widths = width_profile(pts, via_floor)
        row = {"dose": dose, "tip_gap": gap, **widths}
        evolution.append(jsonable(row))
        mid_width = row.get("mid_width")
        if pinch_dose is None and gap is not None and gap > 0.02 and mid_width is not None and mid_width < 0.04:
            pinch_dose = dose
    final = evolution[-1]
    scored = tp.with_target_score("fill", {
        "thickness": float(fill_thickness),
        "tip_gap": final["tip_gap"],
    })
    return {
        **scored,
        "evolution": evolution,
        "pinch_dose": pinch_dose,
        "pinch_before_bottom_fill": pinch_dose is not None,
    }


def cmp_metrics(geo_fill, cmp_mult: float) -> dict:
    g = ps.Domain()
    g.deepCopy(geo_fill)
    overburden = float(tp.profile_points(g)[:, 1].max()) - TARGET_Y
    if overburden > 0:
        ps.Process(g, ps.IsotropicProcess(rate=-1.0), overburden * cmp_mult).apply()
    pts = tp.profile_points(g)
    mats_present = [str(name) for name, p in tp.all_material_profiles(g) if len(p) > 0]
    metrics = {
        "mult": float(cmp_mult),
        "dish": tp.cmp_dish(pts),
        "mask_consumed": not any("Mask" in m for m in mats_present),
        "materials_present": mats_present,
    }
    return tp.with_target_score("cmp", metrics)


def run_task(task: tuple[dict, int]) -> dict:
    recipe, replicate = task
    t0 = time.time()
    base = {"recipe_id": recipe["recipe_id"], "name": recipe["name"], "replicate": replicate, "recipe": recipe}
    try:
        geo = tp.make_initial_geometry(radius=RADIUS, mask_height=MASK_HEIGHT, taper=recipe["mask_taper"])
        geo, depth = tp.bosch_etch(
            geo,
            num_cycles=recipe["num_cycles"],
            etch_time=recipe["etch_time"],
            initial_etch_time=recipe["initial_etch_time"],
            ion_source_exponent=recipe["ion_source_exponent"],
            neutral_sticking_probability=recipe["neutral_sticking_probability"],
            deposition_thickness=recipe["deposition_thickness"],
            deposition_sticking_probability=recipe["deposition_sticking_probability"],
            neutral_rate=recipe["neutral_rate"],
            theta_r_min=recipe["theta_r_min"],
            radius=RADIUS,
        )
        etch = etch_metrics(geo, depth)

        y_etched = float(tp.profile_points(geo)[:, 1].min())
        geo_liner = tp.deposit_conformal(
            copy_domain(geo),
            ps.Material.SiO2,
            recipe["liner_thickness"],
            sticking=recipe["liner_sticking"],
        )
    except Exception as exc:
        return jsonable({**base, "ok": False, "error": repr(exc), "elapsed_s": time.time() - t0})

    try:
        pts_liner = tp.profile_points(geo_liner)
        liner = coverage_step("liner", y_etched, pts_liner, recipe["liner_thickness"])
        y_liner = float(pts_liner[:, 1].min())

        geo_barrier = tp.deposit_conformal(
            copy_domain(geo_liner),
            ps.Material.Cu,
            recipe["barrier_thickness"],
            directional=True,
            iso_ratio=recipe["barrier_iso_ratio"],
        )
        pts_barrier = tp.profile_points(geo_barrier)
        barrier = coverage_step("barrier", y_liner, pts_barrier, recipe["barrier_thickness"])
        via_floor = float(pts_barrier[:, 1].min())

        fill = fill_evolution(
            geo_barrier,
            recipe["fill_thickness"],
            recipe["fill_iso_ratio"],
            via_floor,
        )

        geo_fill = ps.Domain()
        geo_fill.deepCopy(geo_barrier)
        geo_fill = tp.cu_fill(
            geo_fill,
            recipe["fill_thickness"],
            directional=True,
            iso_ratio=recipe["fill_iso_ratio"],
        )
        cmp = cmp_metrics(geo_fill, recipe["cmp_mult"])

        steps = {"etch": etch, "liner": liner, "barrier": barrier, "fill": fill, "cmp": cmp}
        flow_pass = all(step["target_pass"] for step in steps.values())
        flow_score = sum(step["target_score"] for step in steps.values())
        return jsonable({
            **base,
            "ok": True,
            "flow_pass": flow_pass,
            "flow_score": flow_score,
            "steps": steps,
            "elapsed_s": time.time() - t0,
        })
    except Exception as exc:
        return jsonable({**base, "ok": False, "error": repr(exc), "elapsed_s": time.time() - t0})


def aggregate(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[row["recipe_id"]].append(row)

    out = []
    for recipe_id, group in groups.items():
        ok = [r for r in group if r.get("ok")]
        scores = [r["flow_score"] for r in ok]
        fill_gaps = [r["steps"]["fill"]["tip_gap"] for r in ok if r["steps"]["fill"].get("tip_gap") is not None]
        depths = [abs(r["steps"]["etch"]["depth"]) for r in ok]
        bulges = [r["steps"]["etch"]["bulge"] for r in ok if r["steps"]["etch"].get("bulge") is not None]
        row = {
            "recipe_id": recipe_id,
            "name": group[0]["name"],
            "recipe": group[0]["recipe"],
            "runs": len(group),
            "ok_runs": len(ok),
            "flow_pass_rate": mean_bool([r.get("flow_pass", False) for r in ok]),
            "mean_score": mean(scores),
            "p90_score": percentile(scores, 0.90),
            "mean_depth": mean(depths),
            "mean_bulge": mean(bulges),
            "mean_fill_gap": mean(fill_gaps),
            "min_fill_gap": min(fill_gaps) if fill_gaps else None,
            "pinch_rate": mean_bool([r["steps"]["fill"]["pinch_before_bottom_fill"] for r in ok]),
        }
        out.append(row)
    return sorted(out, key=lambda r: (-(r["flow_pass_rate"] or 0), r["p90_score"] or 1e9, r["mean_score"] or 1e9))


def mean(values):
    return float(statistics.mean(values)) if values else None


def mean_bool(values):
    return float(sum(bool(v) for v in values) / len(values)) if values else None


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
    return float(values[idx])


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", type=int, default=24)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="flow_doe_results.jsonl")
    parser.add_argument("--summary", default="flow_doe_summary.json")
    args = parser.parse_args()

    out_path = Path(args.out)
    recipes = sampled_recipes(args.recipes, args.seed)
    done = existing_keys(out_path)
    tasks = [
        (recipe, rep)
        for recipe in recipes
        for rep in range(args.replicates)
        if (recipe["recipe_id"], rep) not in done
    ]

    print(f"flow DOE: recipes={len(recipes)} replicates={args.replicates} "
          f"pending={len(tasks)} workers={args.workers}")
    t0 = time.time()
    with out_path.open("a") as f:
        with futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i, row in enumerate(pool.map(run_task, tasks), 1):
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
                f.flush()
                print(f"{i}/{len(tasks)} recipe={row['recipe_id']} rep={row['replicate']} "
                      f"ok={row.get('ok')} score={row.get('flow_score')} elapsed={time.time()-t0:.0f}s",
                      flush=True)

    rows = load_rows(out_path)
    summary = {
        "target_specs": tp.TARGET_SPECS,
        "space": SPACE,
        "recipes": len(recipes),
        "replicates": args.replicates,
        "rows": len(rows),
        "ranked": aggregate(rows),
    }
    Path(args.summary).write_text(json.dumps(jsonable(summary), indent=2))
    print(f"wrote {args.summary}")


if __name__ == "__main__":
    main()

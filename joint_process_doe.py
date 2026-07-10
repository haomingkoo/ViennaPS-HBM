"""Checkpointed full-process DOE for the TSV via-middle flow.

Samples pattern, Bosch etch, liner, barrier/seed, Cu fill, and CMP knobs
together. Each row is scored against tsv_process.TARGET_SPECS so the run
optimizes the whole traveler, not just one local proxy.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
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


RADIUS = 0.15
MASK_HEIGHT = 0.3
INVALID_SCORE = 1e9

SPACE = {
    "mask_taper": [0.0, 2.0, 4.0, 6.0],
    "num_cycles": [10, 11, 12, 13, 14, 15, 16],
    "etch_time": [0.45, 0.50, 0.55, 0.60, 0.65, 0.70],
    "neutral_rate": [-0.04, -0.06, -0.08, -0.10, -0.12, -0.15],
    "neutral_sticking_probability": [0.05, 0.08, 0.12, 0.16, 0.20, 0.24],
    "initial_etch_time": [0.15, 0.20, 0.30, 0.45],
    "deposition_thickness": [0.003, 0.005, 0.010, 0.015],
    "deposition_sticking_probability": [0.0015, 0.003, 0.005, 0.010, 0.020],
    "ion_source_exponent": [100, 200, 400, 600, 800],
    "theta_r_min": [30.0, 45.0, 60.0, 75.0, 90.0],
    "liner_thick": [0.018, 0.020, 0.024, 0.028, 0.035, 0.045],
    "liner_sticking": [0.02, 0.08, 0.16, 0.24, 0.30, 0.35],
    "barrier_thick": [0.010, 0.012, 0.014, 0.018, 0.024],
    "barrier_iso": [0.0, 0.1, 0.2, 0.4],
    "fill_thick": [0.12, 0.14, 0.15, 0.155, 0.16, 0.18, 0.22],
    "fill_iso": [0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1],
    "cmp_mult": [1.0, 1.2, 1.5, 2.0, 2.2],
}

FOCUS_SPACE = {
    "mask_taper": [0.0, 2.0, 4.0],
    "num_cycles": [11, 12, 13, 14],
    "etch_time": [0.55, 0.60, 0.65],
    "neutral_rate": [-0.06, -0.08, -0.10],
    "neutral_sticking_probability": [0.16, 0.20, 0.24],
    "initial_etch_time": [0.20, 0.30, 0.45],
    "deposition_thickness": [0.003, 0.005, 0.010],
    "deposition_sticking_probability": [0.0015, 0.003, 0.005],
    "ion_source_exponent": [400, 600, 800],
    "theta_r_min": [30.0, 45.0, 60.0],
    "liner_thick": [0.020, 0.024, 0.028, 0.035],
    "liner_sticking": [0.02, 0.16, 0.24, 0.30, 0.35],
    "barrier_thick": [0.012, 0.014, 0.018],
    "barrier_iso": [0.0, 0.1, 0.2],
    "fill_thick": [0.14, 0.15, 0.155, 0.16, 0.18],
    "fill_iso": [0.0, 0.001, 0.005, 0.01, 0.02],
    "cmp_mult": [1.5, 2.0, 2.2],
}

ANCHORS = [
    {
        "name": "dry_best_downstream_best",
        "mask_taper": 2.0,
        "num_cycles": 12,
        "etch_time": 0.60,
        "neutral_rate": -0.08,
        "neutral_sticking_probability": 0.20,
        "initial_etch_time": 0.30,
        "deposition_thickness": 0.005,
        "deposition_sticking_probability": 0.003,
        "ion_source_exponent": 600,
        "theta_r_min": 45.0,
        "liner_thick": 0.020,
        "liner_sticking": 0.02,
        "barrier_thick": 0.014,
        "barrier_iso": 0.1,
        "fill_thick": 0.15,
        "fill_iso": 0.01,
        "cmp_mult": 2.2,
    },
    {
        "name": "depth_centered_dry_alt",
        "mask_taper": 2.0,
        "num_cycles": 14,
        "etch_time": 0.50,
        "neutral_rate": -0.08,
        "neutral_sticking_probability": 0.08,
        "initial_etch_time": 0.30,
        "deposition_thickness": 0.005,
        "deposition_sticking_probability": 0.010,
        "ion_source_exponent": 400,
        "theta_r_min": 45.0,
        "liner_thick": 0.024,
        "liner_sticking": 0.02,
        "barrier_thick": 0.014,
        "barrier_iso": 0.1,
        "fill_thick": 0.15,
        "fill_iso": 0.0,
        "cmp_mult": 2.0,
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


def load_json(path: str | None):
    if not path:
        return None
    return json.loads(Path(path).read_text())


def recipe_key(recipe: dict) -> tuple:
    return tuple((key, recipe.get(key)) for key in SPACE)


def recipe_signature(recipe: dict) -> str:
    payload = json.dumps(dict(recipe_key(recipe)), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def load_space(path: str | None) -> tuple[dict, dict]:
    data = load_json(path)
    if not data:
        return SPACE, FOCUS_SPACE
    space = data.get("space", data)
    focus_space = data.get("focus_space", space)
    missing = [key for key in SPACE if key not in space or key not in focus_space]
    if missing:
        raise ValueError(f"space file missing factors: {missing}")
    return (
        {key: list(space[key]) for key in SPACE},
        {key: list(focus_space[key]) for key in SPACE},
    )


def load_anchors(path: str | None) -> list[dict]:
    data = load_json(path)
    if not data:
        return ANCHORS
    anchors = data.get("anchors", data)
    cleaned = []
    for i, anchor in enumerate(anchors):
        recipe = {key: anchor[key] for key in SPACE}
        recipe["name"] = anchor.get("name", f"anchor_{i:03d}")
        cleaned.append(recipe)
    return cleaned or ANCHORS


def balanced_sample(space: dict, count: int, seed: int, prefix: str) -> list[dict]:
    if count <= 0:
        return []
    rng = random.Random(seed)
    columns = {}
    for key, values in space.items():
        repeats = math.ceil(count / len(values))
        column = list(values) * repeats
        rng.shuffle(column)
        columns[key] = column[:count]
    return [
        {"name": f"{prefix}_{i:04d}", **{key: columns[key][i] for key in SPACE}}
        for i in range(count)
    ]


def random_fill(space: dict, count: int, seed: int, prefix: str) -> list[dict]:
    rng = random.Random(seed)
    return [
        {"name": f"{prefix}_{i:04d}", **{key: rng.choice(space[key]) for key in SPACE}}
        for i in range(count)
    ]


def sampled_recipes(count: int, seed: int, design: str, anchors: list[dict]) -> list[dict]:
    candidates = [dict(anchor) for anchor in anchors[:count]]
    remaining = max(0, count - len(candidates))
    if design == "broad":
        candidates += balanced_sample(SPACE, remaining, seed, "joint_broad")
        fill_space = SPACE
    elif design == "focus":
        candidates += balanced_sample(FOCUS_SPACE, remaining, seed, "joint_focus")
        fill_space = FOCUS_SPACE
    else:
        broad_count = math.ceil(remaining * 0.50)
        focus_count = remaining - broad_count
        candidates += balanced_sample(SPACE, broad_count, seed, "joint_broad")
        candidates += balanced_sample(FOCUS_SPACE, focus_count, seed + 1009, "joint_focus")
        fill_space = SPACE

    recipes = []
    seen = set()
    for candidate in candidates:
        key = recipe_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        recipe = dict(candidate)
        recipe["recipe_id"] = len(recipes)
        recipe["recipe_hash"] = recipe_signature(recipe)
        recipes.append(recipe)

    for candidate in random_fill(fill_space, count * 5, seed + 2003, "joint_fill"):
        if len(recipes) >= count:
            break
        key = recipe_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        recipe = dict(candidate)
        recipe["recipe_id"] = len(recipes)
        recipe["recipe_hash"] = recipe_signature(recipe)
        recipes.append(recipe)
    return recipes


def score_steps(recipe: dict, metrics: dict) -> dict:
    step_scores = {
        "pattern": tp.with_target_score("pattern", {
            "radius": RADIUS,
            "width": 2.0 * RADIUS,
            "mask_height": MASK_HEIGHT,
        }),
        "etch": tp.with_target_score("etch", {
            "depth": metrics.get("depth"),
            "bulge": metrics.get("bulge"),
            "width_error": metrics.get("width_error"),
        }),
        "liner": tp.with_target_score("liner", {
            "thickness": recipe["liner_thick"],
            "coverage": metrics.get("liner_coverage"),
        }),
        "barrier": tp.with_target_score("barrier", {
            "thickness": recipe["barrier_thick"],
            "coverage": metrics.get("barrier_coverage"),
        }),
        "fill": tp.with_target_score("fill", {
            "thickness": recipe["fill_thick"],
            "tip_gap": metrics.get("tip_gap"),
        }),
        "cmp": tp.with_target_score("cmp", {
            "dish": metrics.get("cmp_dish"),
            "mask_consumed": metrics.get("cmp_mask_consumed"),
        }),
    }
    return step_scores


def apply_cmp(geo_fill, target_y: float, mult: float) -> dict:
    overburden = float(tp.profile_points(geo_fill)[:, 1].max()) - target_y
    if overburden > 1e-6:
        ps.Process(geo_fill, ps.IsotropicProcess(rate=-1.0), overburden * mult).apply()
    pts = tp.profile_points(geo_fill)
    materials = [str(name) for name, points in tp.all_material_profiles(geo_fill) if len(points) > 0]
    return {
        "cmp_dish": tp.cmp_dish(pts),
        "cmp_mask_consumed": not any("Mask" in material for material in materials),
        "cmp_materials_present": materials,
    }


def run_task(task: tuple[dict, int]) -> dict:
    recipe, replicate = task
    t0 = time.time()
    base = {
        "recipe_id": recipe["recipe_id"],
        "recipe_hash": recipe["recipe_hash"],
        "name": recipe["name"],
        "replicate": replicate,
        "recipe": recipe,
    }
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
        pts_etched = tp.profile_points(geo)
        y_etched = float(pts_etched[:, 1].min())
        metrics = {
            "depth": depth,
            "bulge": tp.wall_bulge(pts_etched, depth, RADIUS),
            "width_error": tp.width_error(pts_etched, depth, RADIUS),
        }

        geo = tp.deposit_conformal(
            geo, ps.Material.SiO2, recipe["liner_thick"],
            directional=False, sticking=recipe["liner_sticking"])
        pts_liner = tp.profile_points(geo)
        y_liner = float(pts_liner[:, 1].min())
        target_y = float(pts_liner[:, 1].max())
        metrics["liner_coverage"] = tp.floor_reach_metric(y_etched, pts_liner)

        geo = tp.deposit_conformal(
            geo, ps.Material.Cu, recipe["barrier_thick"],
            directional=True, iso_ratio=recipe["barrier_iso"])
        pts_barrier = tp.profile_points(geo)
        y_barrier = float(pts_barrier[:, 1].min())
        metrics["barrier_coverage"] = tp.floor_reach_metric(y_liner, pts_barrier)

        geo = tp.cu_fill(geo, recipe["fill_thick"], directional=True, iso_ratio=recipe["fill_iso"])
        pts_fill = tp.profile_points(geo)
        metrics["fill_coverage"] = tp.floor_reach_metric(y_barrier, pts_fill)
        metrics["tip_gap"] = tp.fill_tip_gap(pts_fill, y_barrier)
        metrics.update(apply_cmp(geo, target_y, recipe["cmp_mult"]))

        step_scores = score_steps(recipe, metrics)
        total_score = float(sum(score["target_score"] for score in step_scores.values()))
        step_pass_count = int(sum(bool(score["target_pass"]) for score in step_scores.values()))
        return jsonable({
            **base,
            "ok": True,
            **metrics,
            "step_scores": step_scores,
            "step_pass_count": step_pass_count,
            "full_target_pass": step_pass_count == len(step_scores),
            "total_score": total_score,
            "elapsed_s": time.time() - t0,
        })
    except Exception as exc:
        return jsonable({**base, "ok": False, "error": repr(exc), "elapsed_s": time.time() - t0})


def row_recipe_hash(row: dict) -> str:
    if row.get("recipe_hash"):
        return row["recipe_hash"]
    return recipe_signature(row.get("recipe", row))


def existing_keys(path: Path) -> set[tuple[str, int]]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            done.add((row_recipe_hash(row), row["replicate"]))
    return done


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def mean(values):
    return float(statistics.mean(values)) if values else None


def mean_bool(values):
    return float(sum(bool(value) for value in values) / len(values)) if values else None


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
    return float(values[idx])


def values_for(rows: list[dict], key: str) -> list:
    return [row[key] for row in rows if row.get(key) is not None]


def range_or_none(values):
    return None if not values else [float(min(values)), float(max(values))]


def aggregate(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row_recipe_hash(row)].append(row)
    out = []
    for recipe_hash, group in grouped.items():
        ok = [row for row in group if row.get("ok")]
        scores = values_for(ok, "total_score")
        out.append({
            "recipe_hash": recipe_hash,
            "recipe_id": group[0].get("recipe_id"),
            "name": group[0]["name"],
            "recipe": group[0]["recipe"],
            "runs": len(group),
            "ok_runs": len(ok),
            "target_pass_rate": mean_bool([row.get("full_target_pass") for row in ok]),
            "mean_step_pass_count": mean(values_for(ok, "step_pass_count")),
            "min_step_pass_count": min(values_for(ok, "step_pass_count"), default=None),
            "mean_total_score": mean(scores),
            "p90_total_score": percentile(scores, 0.90),
            "invalid_score_runs": sum(1 for score in scores if abs(score) >= INVALID_SCORE),
            "mean_depth": mean([abs(value) for value in values_for(ok, "depth")]),
            "depth_range": range_or_none([abs(value) for value in values_for(ok, "depth")]),
            "mean_bulge": mean(values_for(ok, "bulge")),
            "mean_liner_coverage": mean(values_for(ok, "liner_coverage")),
            "mean_barrier_coverage": mean(values_for(ok, "barrier_coverage")),
            "mean_fill_coverage": mean(values_for(ok, "fill_coverage")),
            "mean_tip_gap": mean(values_for(ok, "tip_gap")),
            "mean_cmp_dish": mean(values_for(ok, "cmp_dish")),
            "cmp_mask_consumed_rate": mean_bool([row.get("cmp_mask_consumed") for row in ok]),
        })
    return sorted(out, key=lambda r: (
        r.get("invalid_score_runs") or 0,
        r.get("cmp_mask_consumed_rate") or 0,
        -(r["mean_step_pass_count"] or 0),
        r["p90_total_score"] if r["p90_total_score"] is not None else INVALID_SCORE,
    ))


def main_effects(rows: list[dict]) -> dict:
    effects = {}
    ok_rows = [row for row in rows if row.get("ok")]
    for factor in SPACE:
        by_value = defaultdict(list)
        for row in ok_rows:
            if row.get("total_score") is not None:
                by_value[row["recipe"][factor]].append(row["total_score"])
        means = {str(value): mean(scores) for value, scores in by_value.items()}
        finite = [value for value in means.values() if value is not None]
        effects[factor] = {
            "means": means,
            "range": (max(finite) - min(finite)) if finite else None,
        }
    return effects


def boundary_notes(ranked: list[dict], top_n: int = 10) -> list[str]:
    notes = []
    top = ranked[:top_n]
    for factor, values in SPACE.items():
        if not top:
            continue
        winners = [row["recipe"][factor] for row in top]
        lo, hi = min(values), max(values)
        if all(value == lo for value in winners):
            notes.append(f"top {len(top)} all at low boundary {factor}={lo}; expand lower if physically valid")
        if all(value == hi for value in winners):
            notes.append(f"top {len(top)} all at high boundary {factor}={hi}; expand higher if physically valid")
    return notes


def main() -> None:
    global SPACE, FOCUS_SPACE

    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", type=int, default=128)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--seed", type=int, default=211)
    parser.add_argument("--design", choices=["broad", "focus", "mixed"], default="mixed")
    parser.add_argument("--space-json", default=None)
    parser.add_argument("--anchors-json", default=None)
    parser.add_argument("--out", default="joint_process_doe_results.jsonl")
    parser.add_argument("--summary", default="joint_process_doe_summary.json")
    args = parser.parse_args()

    SPACE, FOCUS_SPACE = load_space(args.space_json)
    anchors = load_anchors(args.anchors_json)
    out_path = Path(args.out)
    recipes = sampled_recipes(args.recipes, args.seed, args.design, anchors)
    done = existing_keys(out_path)
    tasks = [
        (recipe, replicate)
        for recipe in recipes
        for replicate in range(args.replicates)
        if (recipe["recipe_hash"], replicate) not in done
    ]
    print(f"joint process DOE: design={args.design} recipes={len(recipes)} "
          f"replicates={args.replicates} pending={len(tasks)} workers={args.workers}")

    t0 = time.time()
    with out_path.open("a") as f:
        with futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i, row in enumerate(pool.map(run_task, tasks), 1):
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
                f.flush()
                print(f"{i}/{len(tasks)} recipe={row['recipe_id']} hash={row['recipe_hash']} "
                      f"rep={row['replicate']} ok={row.get('ok')} "
                      f"steps={row.get('step_pass_count')} score={row.get('total_score')} "
                      f"elapsed={time.time()-t0:.0f}s",
                      flush=True)

    planned_hashes = {recipe["recipe_hash"] for recipe in recipes}
    rows = [row for row in load_rows(out_path) if row_recipe_hash(row) in planned_hashes]
    ranked = aggregate(rows)
    summary = {
        "target_specs": tp.TARGET_SPECS,
        "space": SPACE,
        "focus_space": FOCUS_SPACE,
        "design": args.design,
        "recipes": len(recipes),
        "replicates": args.replicates,
        "rows": len(rows),
        "ranked": ranked,
        "main_effects": main_effects(rows),
        "boundary_notes": boundary_notes(ranked),
    }
    Path(args.summary).write_text(json.dumps(jsonable(summary), indent=2))
    print(f"wrote {args.summary}")


if __name__ == "__main__":
    main()

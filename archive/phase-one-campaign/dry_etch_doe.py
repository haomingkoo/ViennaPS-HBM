"""Parallel dry-etch DOE with cycle-aware shape metrics.

This is the detailed study for the Bosch etch step only. It treats cycle
count as a real process factor, records per-cycle shape traces, and ranks
recipes against target depth/width/bulge instead of raw "nice looking" shape.
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

import tsv_process as tp
from legacy_metric_guard import require_legacy_metric_override

require_legacy_metric_override()

RADIUS = 0.15
MASK_HEIGHT = 0.3
INVALID_SCORE_CUTOFF = 1e8

SPACE = {
    "mask_taper": [0.0, 2.0, 4.0],
    "num_cycles": [10, 11, 12, 13, 14, 15, 16, 18],
    "etch_time": [0.35, 0.40, 0.45, 0.50, 0.55, 0.60],
    "neutral_rate": [-0.08, -0.10, -0.12, -0.15, -0.18, -0.20],
    "neutral_sticking_probability": [0.03, 0.05, 0.08, 0.12],
    "initial_etch_time": [0.20, 0.30, 0.45],
    "deposition_thickness": [0.005, 0.010, 0.015, 0.020],
    "deposition_sticking_probability": [0.005, 0.010, 0.020],
    "ion_source_exponent": [100, 200, 400, 600],
    "theta_r_min": [45.0, 60.0, 75.0],
}

FOCUS_SPACE = {
    "mask_taper": [0.0, 2.0],
    "num_cycles": [12, 13, 14, 15, 16],
    "etch_time": [0.40, 0.45, 0.50, 0.55],
    "neutral_rate": [-0.08, -0.10, -0.12, -0.15],
    "neutral_sticking_probability": [0.03, 0.05, 0.08],
    "initial_etch_time": [0.20, 0.30, 0.45],
    "deposition_thickness": [0.005, 0.010, 0.015],
    "deposition_sticking_probability": [0.005, 0.010, 0.020],
    "ion_source_exponent": [200, 400, 600],
    "theta_r_min": [45.0, 60.0, 75.0],
}

ANCHORS = [
    {
        "name": "current_production",
        "mask_taper": 0.0,
        "num_cycles": 14,
        "etch_time": 0.50,
        "neutral_rate": -0.10,
        "neutral_sticking_probability": 0.05,
        "initial_etch_time": 0.30,
        "deposition_thickness": 0.010,
        "deposition_sticking_probability": 0.010,
        "ion_source_exponent": 200,
        "theta_r_min": 60.0,
    },
    {
        "name": "target_score_candidate",
        "mask_taper": 0.0,
        "num_cycles": 14,
        "etch_time": 0.50,
        "neutral_rate": -0.12,
        "neutral_sticking_probability": 0.05,
        "initial_etch_time": 0.30,
        "deposition_thickness": 0.010,
        "deposition_sticking_probability": 0.010,
        "ion_source_exponent": 200,
        "theta_r_min": 60.0,
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


def recipe_key(recipe: dict) -> tuple:
    return tuple((key, recipe.get(key)) for key in SPACE)


def recipe_signature(recipe: dict) -> str:
    payload = json.dumps(dict(recipe_key(recipe)), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


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


def load_json(path: str | None):
    if not path:
        return None
    return json.loads(Path(path).read_text())


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


def sampled_recipes(count: int, seed: int, design: str, anchors: list[dict] | None = None) -> list[dict]:
    anchors = anchors or ANCHORS
    candidates = [dict(anchor) for anchor in anchors[:count]]
    remaining = max(0, count - len(candidates))
    if design == "broad":
        candidates += balanced_sample(SPACE, remaining, seed, "etch_broad")
        fill_space = SPACE
    elif design == "focus":
        candidates += balanced_sample(FOCUS_SPACE, remaining, seed, "etch_focus")
        fill_space = FOCUS_SPACE
    else:
        broad_count = math.ceil(remaining * 0.60)
        focus_count = remaining - broad_count
        candidates += balanced_sample(SPACE, broad_count, seed, "etch_broad")
        candidates += balanced_sample(FOCUS_SPACE, focus_count, seed + 1009, "etch_focus")
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

    fill = random_fill(fill_space, count * 5, seed + 2003, "etch_fill")
    for candidate in fill:
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


def row_recipe_hash(row: dict) -> str:
    if row.get("recipe_hash"):
        return row["recipe_hash"]
    recipe = row.get("recipe", row)
    return recipe.get("recipe_hash") or recipe_signature(recipe)


def existing_keys(path: Path) -> set[tuple[str, int]]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            done.add((row_recipe_hash(row), row["replicate"]))
    return done


def width_profile(points: np.ndarray, depth: float) -> dict:
    levels = {
        "top_width": -0.10,
        "mid_width": depth * 0.50,
        "bottom_width": depth * 0.85,
    }
    out = {}
    for name, y in levels.items():
        half_width = half_width_at_y(points, y)
        out[name] = None if half_width is None else 2.0 * half_width
    widths = [out[name] for name in levels if out[name] is not None]
    if out["top_width"] is not None and out["bottom_width"] is not None:
        out["taper_width_delta"] = out["top_width"] - out["bottom_width"]
    else:
        out["taper_width_delta"] = None
    if widths:
        target_width = tp.TARGET_SPECS["etch"]["target_width"]
        out["width_profile_error"] = float(max(abs(width - target_width) for width in widths))
        out["width_profile_span"] = float(max(widths) - min(widths))
    else:
        out["width_profile_error"] = None
        out["width_profile_span"] = None
    return out


def half_width_at_y(points: np.ndarray, y: float) -> float | None:
    if len(points) == 0:
        return None
    band = max(0.015, float(np.ptp(points[:, 1])) * 0.01)
    near = points[(np.abs(points[:, 1] - y) <= band) & (points[:, 0] >= 0.0)]
    if len(near) < 3:
        near = points[np.argsort(np.abs(points[:, 1] - y))[:5]]
    if len(near) == 0:
        return None
    return float(np.median(near[:, 0]))


def sidewall_shape(points: np.ndarray, depth: float, y_top: float) -> dict:
    body = points[
        (points[:, 1] > depth * 0.85)
        & (points[:, 1] < y_top)
        & (points[:, 0] > 0.2 * RADIUS)
    ]
    if len(body) < 5:
        return {"sidewall_slope": None, "scallop_rms": None, "sidewall_point_count": int(len(body))}
    y, x = body[:, 1], body[:, 0]
    slope, intercept = np.polyfit(y, x, 1)
    residual = x - (slope * y + intercept)
    return {
        "sidewall_slope": float(slope),
        "scallop_rms": float(np.sqrt(np.mean(residual ** 2))),
        "sidewall_point_count": int(len(body)),
    }


def score_dry_etch(metrics: dict) -> dict:
    scored = tp.with_target_score("etch", metrics)
    widths = [
        scored[name]
        for name in ("top_width", "mid_width", "bottom_width")
        if scored.get(name) is not None
    ]
    if scored.get("width_profile_error") is None:
        if widths:
            target_width = tp.TARGET_SPECS["etch"]["target_width"]
            scored["width_profile_error"] = float(max(abs(width - target_width) for width in widths))
        else:
            scored["width_profile_error"] = None
    if scored.get("width_profile_span") is None:
        scored["width_profile_span"] = float(max(widths) - min(widths)) if widths else None

    taper = scored.get("taper_width_delta")
    taper_penalty = 0.0 if taper is None else abs(taper) / 0.06
    width_profile_error = scored.get("width_profile_error")
    width_profile_penalty = 0.0 if width_profile_error is None else width_profile_error / 0.06
    scallop_rms = scored.get("scallop_rms")
    scallop_penalty = 0.0 if scallop_rms is None else scallop_rms / 0.03
    scored["dry_etch_score"] = (
        scored["target_score"]
        + taper_penalty
        + 0.5 * width_profile_penalty
        + scallop_penalty
    )
    return scored


def shape_metrics(geometry) -> dict:
    points = tp.profile_points(geometry)
    depth = float(points[:, 1].min())
    y_top = MASK_HEIGHT * (2.0 / 3.0)
    sidewall = sidewall_shape(points, depth, y_top)
    metrics = {
        "depth": depth,
        "bulge": tp.wall_bulge(points, depth, RADIUS, y_top),
        "width_error": tp.width_error(points, depth, RADIUS, y_top),
        **sidewall,
        **width_profile(points, depth),
    }
    return score_dry_etch(metrics)


def run_task(task: tuple[dict, int]) -> dict:
    recipe, replicate = task
    t0 = time.time()
    trace = []

    def on_cycle(geometry, cycle):
        metrics = shape_metrics(geometry)
        trace.append({"cycle": cycle, **metrics})

    base = {
        "recipe_id": recipe["recipe_id"],
        "recipe_hash": recipe["recipe_hash"],
        "name": recipe["name"],
        "replicate": replicate,
        "recipe": recipe,
    }
    try:
        geometry = tp.make_initial_geometry(radius=RADIUS, mask_height=MASK_HEIGHT, taper=recipe["mask_taper"])
        geometry, _ = tp.bosch_etch(
            geometry,
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
            on_cycle=on_cycle,
        )
        final = shape_metrics(geometry)
        return jsonable({
            **base,
            "ok": True,
            "final": final,
            "cycle_trace": trace,
            "elapsed_s": time.time() - t0,
        })
    except Exception as exc:
        return jsonable({**base, "ok": False, "error": repr(exc), "cycle_trace": trace, "elapsed_s": time.time() - t0})


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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


def values_for(finals: list[dict], key: str) -> list:
    return [metrics[key] for metrics in finals if metrics.get(key) is not None]


def mean_depth_gain_per_cycle(rows: list[dict]) -> float | None:
    gains = []
    for row in rows:
        trace = row.get("cycle_trace") or []
        if len(trace) < 2:
            continue
        first, last = trace[0], trace[-1]
        cycles = max(1, last.get("cycle", 0) - first.get("cycle", 0))
        gains.append((abs(last["depth"]) - abs(first["depth"])) / cycles)
    return mean(gains)


def aggregate(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row_recipe_hash(row)].append(row)
    out = []
    for recipe_hash, group in grouped.items():
        ok = [row for row in group if row.get("ok")]
        finals = [score_dry_etch(row["final"]) for row in ok]
        scores = values_for(finals, "dry_etch_score")
        target_scores = values_for(finals, "target_score")
        invalid_metric_runs = len([score for score in scores if score >= INVALID_SCORE_CUTOFF])
        out.append({
            "recipe_hash": recipe_hash,
            "recipe_id": group[0].get("recipe_id"),
            "name": group[0]["name"],
            "recipe": group[0]["recipe"],
            "runs": len(group),
            "ok_runs": len(ok),
            "invalid_metric_runs": invalid_metric_runs,
            "target_pass_rate": mean_bool([m["target_pass"] for m in finals]),
            "mean_dry_etch_score": mean(scores),
            "p90_dry_etch_score": percentile(scores, 0.90),
            "mean_target_score": mean(target_scores),
            "mean_depth": mean([abs(m["depth"]) for m in finals]),
            "depth_range": range_or_none([abs(m["depth"]) for m in finals]),
            "mean_bulge": mean(values_for(finals, "bulge")),
            "mean_width_profile_error": mean(values_for(finals, "width_profile_error")),
            "mean_width_profile_span": mean(values_for(finals, "width_profile_span")),
            "mean_scallop_rms": mean(values_for(finals, "scallop_rms")),
            "mean_sidewall_point_count": mean(values_for(finals, "sidewall_point_count")),
            "mean_taper_width_delta": mean(values_for(finals, "taper_width_delta")),
            "mean_depth_gain_per_cycle": mean_depth_gain_per_cycle(ok),
        })
    return sorted(out, key=lambda r: (-(r["target_pass_rate"] or 0), r["p90_dry_etch_score"] or 1e9))


def range_or_none(values):
    return None if not values else [float(min(values)), float(max(values))]


def main_effects(rows: list[dict]) -> dict:
    effects = {}
    ok_rows = [row for row in rows if row.get("ok")]
    for factor in SPACE:
        by_value = defaultdict(list)
        invalid_by_value = defaultdict(int)
        for row in ok_rows:
            score = score_dry_etch(row["final"]).get("dry_etch_score")
            if score is None:
                continue
            if score >= INVALID_SCORE_CUTOFF:
                invalid_by_value[row["recipe"][factor]] += 1
            else:
                by_value[row["recipe"][factor]].append(score)
        means = {str(value): mean(scores) for value, scores in by_value.items()}
        finite = [v for v in means.values() if v is not None]
        effects[factor] = {
            "means": means,
            "range": (max(finite) - min(finite)) if finite else None,
            "invalid_metric_runs": {str(value): count for value, count in invalid_by_value.items()},
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


def main():
    global SPACE, FOCUS_SPACE

    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", type=int, default=96)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--design", choices=["broad", "focus", "mixed"], default="mixed")
    parser.add_argument("--space-json", default=None)
    parser.add_argument("--anchors-json", default=None)
    parser.add_argument("--out", default="dry_etch_doe_results.jsonl")
    parser.add_argument("--summary", default="dry_etch_doe_summary.json")
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
    print(f"dry etch DOE: design={args.design} recipes={len(recipes)} replicates={args.replicates} "
          f"pending={len(tasks)} workers={args.workers}")

    t0 = time.time()
    with out_path.open("a") as f:
        with futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i, row in enumerate(pool.map(run_task, tasks), 1):
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
                f.flush()
                score = row.get("final", {}).get("dry_etch_score")
                print(f"{i}/{len(tasks)} recipe={row['recipe_id']} hash={row['recipe_hash']} "
                      f"rep={row['replicate']} ok={row.get('ok')} score={score} "
                      f"elapsed={time.time()-t0:.0f}s",
                      flush=True)

    planned_hashes = {recipe["recipe_hash"] for recipe in recipes}
    rows = [row for row in load_rows(out_path) if row_recipe_hash(row) in planned_hashes]
    ranked = aggregate(rows)
    summary = {
        "target_specs": tp.TARGET_SPECS["etch"],
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

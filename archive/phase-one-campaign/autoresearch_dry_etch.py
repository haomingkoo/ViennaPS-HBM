"""Coordinate iterative dry-etch studies."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


BASE_SPACE = {
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

EXPANSION_SPACE = {
    "mask_taper": [0.0, 2.0, 4.0, 6.0],
    "num_cycles": [8, 10, 11, 12, 13, 14, 15, 16, 18, 20],
    "etch_time": [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70],
    "neutral_rate": [-0.04, -0.06, -0.08, -0.10, -0.12, -0.15, -0.18, -0.20, -0.24],
    "neutral_sticking_probability": [0.02, 0.03, 0.05, 0.08, 0.12, 0.16, 0.20],
    "initial_etch_time": [0.10, 0.15, 0.20, 0.30, 0.45, 0.60],
    "deposition_thickness": [0.001, 0.003, 0.005, 0.010, 0.015, 0.020, 0.025],
    "deposition_sticking_probability": [0.003, 0.005, 0.010, 0.020, 0.040, 0.060],
    "ion_source_exponent": [25, 50, 100, 200, 400, 600, 800],
    "theta_r_min": [30.0, 45.0, 60.0, 75.0, 90.0],
}

MIN_FACTOR_VALUES = {
    "num_cycles": 5,
    "etch_time": 4,
    "neutral_rate": 4,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def score_key(row: dict) -> tuple:
    return (
        -(row.get("target_pass_rate") or 0.0),
        row.get("p90_dry_etch_score") if row.get("p90_dry_etch_score") is not None else 1e12,
        row.get("mean_dry_etch_score") if row.get("mean_dry_etch_score") is not None else 1e12,
    )


def ranked_rows(summary: dict) -> list[dict]:
    return sorted(summary.get("ranked", []), key=score_key)


def index_of(values: list, value) -> int:
    for i, item in enumerate(values):
        if item == value:
            return i
    raise ValueError(f"value {value!r} not in {values!r}")


def expand_window(ordered: list, used_values: list, min_count: int) -> list:
    idxs = sorted(index_of(ordered, value) for value in set(used_values) if value in ordered)
    if not idxs:
        return ordered[:min_count]
    lo, hi = min(idxs), max(idxs)
    lo = max(0, lo - 1)
    hi = min(len(ordered) - 1, hi + 1)
    while hi - lo + 1 < min_count and (lo > 0 or hi < len(ordered) - 1):
        if lo > 0:
            lo -= 1
        if hi - lo + 1 >= min_count:
            break
        if hi < len(ordered) - 1:
            hi += 1
    return ordered[lo:hi + 1]


def plan_space(summary: dict, top_n: int) -> tuple[dict, dict, list[str]]:
    rows = ranked_rows(summary)
    top = rows[:top_n]
    source_space = summary.get("space") or BASE_SPACE
    next_space = {}
    next_focus = {}
    notes = []

    for factor, expansion_values in EXPANSION_SPACE.items():
        current_values = source_space.get(factor, BASE_SPACE[factor])
        winners = [row["recipe"][factor] for row in top if row.get("recipe") and factor in row["recipe"]]
        min_count = MIN_FACTOR_VALUES.get(factor, 3)
        if not winners:
            next_space[factor] = current_values
            next_focus[factor] = current_values
            continue

        current_idxs = [index_of(current_values, value) for value in set(winners) if value in current_values]
        all_at_low = bool(current_idxs) and all(idx == 0 for idx in current_idxs)
        all_at_high = bool(current_idxs) and all(idx == len(current_values) - 1 for idx in current_idxs)
        if all_at_low or all_at_high:
            expanded = expand_window(expansion_values, winners, min_count + 1)
            side = "low" if all_at_low else "high"
            notes.append(f"{factor}: top recipes sit on {side} boundary; expanded to {expanded}")
            next_space[factor] = expanded
            next_focus[factor] = expand_window(expanded, winners, min_count)
        else:
            focused = expand_window(expansion_values, winners, min_count)
            notes.append(f"{factor}: focused around top values {sorted(set(winners))} -> {focused}")
            next_space[factor] = focused
            next_focus[factor] = focused
    return next_space, next_focus, notes


def plan_anchors(summary: dict, top_n: int) -> list[dict]:
    anchors = []
    for i, row in enumerate(ranked_rows(summary)[:top_n]):
        recipe = {key: row["recipe"][key] for key in BASE_SPACE}
        recipe["name"] = f"carry_{i:02d}_{row.get('name', 'recipe')}"
        anchors.append(recipe)
    return anchors


def summarize(summary: dict) -> dict:
    rows = ranked_rows(summary)
    best = rows[0] if rows else {}
    effects = summary.get("main_effects", {})
    effect_ranges = [
        (factor, effect.get("range"))
        for factor, effect in effects.items()
        if effect.get("range") is not None
    ]
    effect_ranges.sort(key=lambda item: item[1], reverse=True)
    return {
        "rows": summary.get("rows"),
        "recipes": summary.get("recipes"),
        "replicates": summary.get("replicates"),
        "best_name": best.get("name"),
        "best_recipe": best.get("recipe"),
        "best_target_pass_rate": best.get("target_pass_rate"),
        "best_p90_dry_etch_score": best.get("p90_dry_etch_score"),
        "best_mean_depth": best.get("mean_depth"),
        "best_mean_bulge": best.get("mean_bulge"),
        "boundary_notes": summary.get("boundary_notes", []),
        "top_effect_ranges": effect_ranges[:5],
    }


def append_log(path: Path, generation: int, before: dict, plan: dict, after: dict | None = None) -> None:
    lines = []
    if not path.exists():
        lines.append("# Dry Etch Autoresearch Log\n\n")
    lines.append(f"## Generation {generation}\n\n")
    lines.append("Input best:\n\n")
    lines.append("```json\n")
    lines.append(json.dumps(summarize(before), indent=2, sort_keys=True))
    lines.append("\n```\n\n")
    lines.append("Plan:\n\n")
    lines.append("```json\n")
    lines.append(json.dumps(plan, indent=2, sort_keys=True))
    lines.append("\n```\n\n")
    if after:
        lines.append("Output best:\n\n")
        lines.append("```json\n")
        lines.append(json.dumps(summarize(after), indent=2, sort_keys=True))
        lines.append("\n```\n\n")
    with path.open("a") as f:
        f.write("".join(lines))


def make_plan(summary: dict, generation: int, top_n: int) -> dict:
    space, focus_space, notes = plan_space(summary, top_n)
    anchors = plan_anchors(summary, top_n)
    return {
        "generation": generation,
        "top_n": top_n,
        "space": space,
        "focus_space": focus_space,
        "anchors": anchors,
        "decision_notes": notes,
    }


def run_generation(args, generation: int, plan: dict) -> Path:
    out_dir = Path(args.workdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    space_path = out_dir / f"gen_{generation:03d}_space.json"
    anchors_path = out_dir / f"gen_{generation:03d}_anchors.json"
    results_path = out_dir / f"gen_{generation:03d}_results.jsonl"
    summary_path = out_dir / f"gen_{generation:03d}_summary.json"
    write_json(space_path, {"space": plan["space"], "focus_space": plan["focus_space"]})
    write_json(anchors_path, {"anchors": plan["anchors"]})

    cmd = [
        args.python,
        "-u",
        "dry_etch_doe.py",
        "--recipes", str(args.recipes),
        "--replicates", str(args.replicates),
        "--workers", str(args.workers),
        "--design", args.design,
        "--seed", str(args.seed + generation),
        "--space-json", str(space_path),
        "--anchors-json", str(anchors_path),
        "--out", str(results_path),
        "--summary", str(summary_path),
    ]
    print("running:", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=args.repo, check=True)
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--workdir", default="autoresearch_dry_etch")
    parser.add_argument("--bootstrap-summary", default="dry_etch_doe_summary.json")
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--start-generation", type=int, default=1)
    parser.add_argument("--recipes", type=int, default=96)
    parser.add_argument("--replicates", type=int, default=4)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--design", choices=["broad", "focus", "mixed"], default="mixed")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo)
    args.repo = str(repo)
    bootstrap = repo / args.bootstrap_summary
    if not bootstrap.exists():
        raise FileNotFoundError(f"missing bootstrap summary: {bootstrap}")

    out_dir = repo / args.workdir
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "research_log.md"
    summary = load_json(bootstrap)

    for generation in range(args.start_generation, args.start_generation + args.generations):
        plan = make_plan(summary, generation, args.top_n)
        plan_path = out_dir / f"gen_{generation:03d}_plan.json"
        write_json(plan_path, plan)
        if args.plan_only:
            append_log(log_path, generation, summary, plan)
            print(f"wrote plan {plan_path}")
            continue
        summary_path = run_generation(args, generation, plan)
        next_summary = load_json(summary_path)
        append_log(log_path, generation, summary, plan, next_summary)
        summary = next_summary
    print(f"wrote {log_path}")


if __name__ == "__main__":
    main()

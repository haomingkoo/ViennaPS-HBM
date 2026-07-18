"""Autoresearch controller for full TSV process DOE generations."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import joint_process_doe as joint
import review_joint_process_results as review


EXPANSION_SPACE = {
    "mask_taper": [0.0, 2.0, 4.0, 6.0, 8.0],
    "num_cycles": [9, 10, 11, 12, 13, 14, 15, 16, 18],
    "etch_time": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80],
    "neutral_rate": [-0.03, -0.04, -0.06, -0.08, -0.10, -0.12, -0.15, -0.18],
    "neutral_sticking_probability": [0.03, 0.05, 0.08, 0.12, 0.16, 0.20, 0.24, 0.30],
    "initial_etch_time": [0.10, 0.15, 0.20, 0.30, 0.45, 0.60],
    "deposition_thickness": [0.001, 0.003, 0.005, 0.010, 0.015, 0.020],
    "deposition_sticking_probability": [0.001, 0.0015, 0.003, 0.005, 0.010, 0.020],
    "ion_source_exponent": [50, 100, 200, 400, 600, 800, 1000],
    "theta_r_min": [20.0, 30.0, 45.0, 60.0, 75.0, 90.0],
    "liner_thick": [0.018, 0.020, 0.024, 0.028, 0.035, 0.045, 0.055],
    "liner_sticking": [0.02, 0.08, 0.16, 0.24, 0.30, 0.35, 0.45],
    "barrier_thick": [0.010, 0.012, 0.014, 0.018, 0.024, 0.032],
    "barrier_iso": [0.0, 0.1, 0.2, 0.4, 0.55],
    "fill_thick": [0.12, 0.14, 0.15, 0.155, 0.16, 0.18, 0.22, 0.26],
    "fill_iso": [0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2],
    "cmp_mult": [1.0, 1.2, 1.5, 2.0, 2.2, 2.5, 3.0],
}

MIN_FACTOR_VALUES = {
    "num_cycles": 4,
    "etch_time": 3,
    "neutral_rate": 3,
    "neutral_sticking_probability": 3,
    "fill_thick": 4,
    "fill_iso": 4,
    "cmp_mult": 3,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def ranked_rows(summary: dict) -> list[dict]:
    return sorted(summary.get("ranked", []), key=review.ranking_key)


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
    source_space = summary.get("space") or joint.SPACE
    next_space = {}
    focus_space = {}
    notes = []

    for factor, expansion_values in EXPANSION_SPACE.items():
        current_values = source_space.get(factor, joint.SPACE[factor])
        winners = [row["recipe"][factor] for row in top if row.get("recipe") and factor in row["recipe"]]
        min_count = MIN_FACTOR_VALUES.get(factor, 3)
        if not winners:
            next_space[factor] = current_values
            focus_space[factor] = current_values
            continue

        current_idxs = [index_of(current_values, value) for value in set(winners) if value in current_values]
        all_at_low = bool(current_idxs) and all(idx == 0 for idx in current_idxs)
        all_at_high = bool(current_idxs) and all(idx == len(current_values) - 1 for idx in current_idxs)
        if all_at_low or all_at_high:
            expanded = expand_window(expansion_values, winners, min_count + 1)
            side = "low" if all_at_low else "high"
            notes.append(f"{factor}: top recipes sit on {side} boundary; expanded to {expanded}")
            next_space[factor] = expanded
            focus_space[factor] = expand_window(expanded, winners, min_count)
        else:
            focused = expand_window(expansion_values, winners, min_count)
            notes.append(f"{factor}: focused around top values {sorted(set(winners))} -> {focused}")
            next_space[factor] = focused
            focus_space[factor] = focused
    return next_space, focus_space, notes


def plan_anchors(summary: dict, top_n: int) -> list[dict]:
    anchors = []
    for i, row in enumerate(ranked_rows(summary)[:top_n]):
        recipe = {key: row["recipe"][key] for key in joint.SPACE}
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
        "best_mean_step_pass_count": best.get("mean_step_pass_count"),
        "best_p90_total_score": best.get("p90_total_score"),
        "best_worst_total_score": best.get("worst_total_score"),
        "best_mean_total_score": best.get("mean_total_score"),
        "best_mean_depth": best.get("mean_depth"),
        "best_mean_bulge": best.get("mean_bulge"),
        "best_mean_tip_gap": best.get("mean_tip_gap"),
        "best_mean_cmp_dish": best.get("mean_cmp_dish"),
        "boundary_notes": summary.get("boundary_notes", []),
        "top_effect_ranges": effect_ranges[:8],
    }


def append_log(path: Path, generation: int, before: dict, plan: dict, after: dict | None = None) -> None:
    lines = []
    if not path.exists():
        lines.append("# Joint Process Autoresearch Log\n\n")
    lines.append(f"## Generation {generation}\n\n")
    lines.append("Input best:\n\n```json\n")
    lines.append(json.dumps(summarize(before), indent=2, sort_keys=True))
    lines.append("\n```\n\nPlan:\n\n```json\n")
    lines.append(json.dumps(plan, indent=2, sort_keys=True))
    lines.append("\n```\n\n")
    if after:
        lines.append("Output best:\n\n```json\n")
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
        "joint_process_doe.py",
        "--recipes", str(args.recipes),
        "--replicates", str(args.replicates),
        "--workers", str(args.workers),
        "--shared-upstream",
        "--design", args.design,
        "--seed", str(args.seed + generation),
        "--space-json", str(space_path),
        "--anchors-json", str(anchors_path),
        "--out", str(results_path),
        "--summary", str(summary_path),
        "--allow-legacy-metrics",
    ]
    print("running:", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=args.repo, check=True)
    rows = review.load_rows(results_path)
    review_path = out_dir / f"gen_{generation:03d}_review.md"
    review.write_report(rows, review_path, args.recipes * args.replicates, plan["space"])
    write_json(out_dir / f"gen_{generation:03d}_metric.json", {
        "metric": "full_process_loss",
        "value": review.best_loss(rows),
        "review": str(review_path),
        "next_decision": f"See {review_path}#next-decision",
    })
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--workdir", default="autoresearch-results/joint-process")
    parser.add_argument("--bootstrap-summary", default="joint_process_doe_summary.json")
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--start-generation", type=int, default=1)
    parser.add_argument("--recipes", type=int, default=128)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--seed", type=int, default=401)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--design", choices=["broad", "focus", "mixed"], default="mixed")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--allow-legacy-metrics", action="store_true")
    args = parser.parse_args()

    if not args.allow_legacy_metrics:
        raise SystemExit(review.LEGACY_METRICS_WARNING)

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
        write_json(out_dir / "latest.json", {
            "generation": generation,
            "summary": str(summary_path),
            "next_generation": generation + 1,
            "resume_with": str(summary_path),
        })
        summary = next_summary
    print(f"wrote {log_path}")


if __name__ == "__main__":
    main()

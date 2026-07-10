"""Write a critical markdown review for the full-process DOE results."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


BAD_SCORE = 1e8
STEPS = ("pattern", "etch", "liner", "barrier", "fill", "cmp")


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def mean(values):
    return float(statistics.mean(values)) if values else None


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
    return float(values[idx])


def fmt(value, digits=4):
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if abs(value) >= BAD_SCORE:
        return "invalid-penalty"
    return f"{value:.{digits}g}"


def row_hash(row: dict) -> str:
    return row.get("recipe_hash") or row.get("recipe", {}).get("recipe_hash") or "unknown"


def invalid_metric(row: dict) -> bool:
    score = row.get("total_score")
    if not isinstance(score, (int, float)) or not math.isfinite(score) or abs(score) >= BAD_SCORE:
        return True
    if "cmp_mask_consumed" not in row:
        return True
    step_scores = row.get("step_scores", {})
    return any(
        step not in step_scores
        or not isinstance(step_scores[step].get("target_score"), (int, float))
        or not math.isfinite(step_scores[step]["target_score"])
        for step in STEPS
    )


def step_names(rows: list[dict]) -> list[str]:
    names = []
    for row in rows:
        for step in row.get("step_scores", {}):
            if step not in names:
                names.append(step)
    return names


def ranking_key(row: dict) -> tuple:
    """Canonical full-traveler order: hard gates, passes, then replicated loss."""
    return (
        row.get("failed_runs") or 0,
        row.get("invalid_score_runs") or 0,
        row.get("cmp_mask_consumed_rate") or 0,
        -(row.get("mean_step_pass_count") or 0),
        row.get("p90_total_score") if row.get("p90_total_score") is not None else BAD_SCORE,
        row.get("mean_total_score") if row.get("mean_total_score") is not None else BAD_SCORE,
    )


def aggregate(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row_hash(row)].append(row)

    out = []
    for recipe_hash, group in grouped.items():
        ok = [row for row in group if row.get("ok")]
        valid = [row for row in ok if not invalid_metric(row)]
        scores = [row["total_score"] for row in valid]
        pass_counts = [row.get("step_pass_count", 0) for row in ok]
        steps = step_names(ok)
        step_summary = {}
        for step in steps:
            scored = [row["step_scores"][step] for row in ok if step in row.get("step_scores", {})]
            step_summary[step] = {
                "pass_rate": mean([1.0 if score.get("target_pass") else 0.0 for score in scored]),
                "mean_score": mean([score.get("target_score") for score in scored if score.get("target_score") is not None]),
            }
        out.append({
            "recipe_hash": recipe_hash,
            "name": group[0].get("name"),
            "recipe": group[0].get("recipe", {}),
            "runs": len(group),
            "ok_runs": len(ok),
            "failed_runs": len(group) - len(ok),
            "target_pass_rate": mean([1.0 if row.get("full_target_pass") else 0.0 for row in ok]),
            "mean_step_pass_count": mean(pass_counts),
            "min_step_pass_count": min(pass_counts, default=None),
            "pass_count_range": [min(pass_counts), max(pass_counts)] if pass_counts else None,
            "mean_total_score": mean(scores),
            "p90_total_score": percentile(scores, 0.90),
            "worst_total_score": max(scores, default=None),
            "invalid_score_runs": sum(invalid_metric(row) for row in ok),
            "mean_depth": mean([abs(row["depth"]) for row in ok if row.get("depth") is not None]),
            "depth_range": range_or_none([abs(row["depth"]) for row in ok if row.get("depth") is not None]),
            "mean_bulge": mean([row["bulge"] for row in ok if row.get("bulge") is not None]),
            "mean_liner_coverage": mean([row["liner_coverage"] for row in ok if row.get("liner_coverage") is not None]),
            "mean_barrier_coverage": mean([row["barrier_coverage"] for row in ok if row.get("barrier_coverage") is not None]),
            "mean_fill_coverage": mean([row["fill_coverage"] for row in ok if row.get("fill_coverage") is not None]),
            "mean_tip_gap": mean([row["tip_gap"] for row in ok if row.get("tip_gap") is not None]),
            "mean_cmp_dish": mean([row["cmp_dish"] for row in ok if row.get("cmp_dish") is not None]),
            "cmp_mask_consumed_rate": mean([1.0 if row.get("cmp_mask_consumed") else 0.0 for row in ok]),
            "step_summary": step_summary,
        })

    return sorted(out, key=ranking_key)


def failure_counts(rows: list[dict]) -> Counter:
    counts = Counter()
    for row in rows:
        if not row.get("ok"):
            counts["runner_error"] += 1
            continue
        for step, score in row.get("step_scores", {}).items():
            if not score.get("target_pass"):
                counts[step] += 1
        if row.get("cmp_mask_consumed"):
            counts["cmp_mask_consumed"] += 1
        if invalid_metric(row):
            counts["invalid_metric_penalty"] += 1
    return counts


def boundary_notes(ranked: list[dict], space: dict | None = None, top_n: int = 4) -> list[str]:
    top = ranked[:top_n]
    if not top:
        return []
    if space:
        notes = []
        for factor, domain in space.items():
            values = [row["recipe"][factor] for row in top]
            lo, hi = min(domain), max(domain)
            if all(value == lo for value in values):
                notes.append(f"top {len(top)} all at low boundary {factor}={lo}; expand lower if physically valid")
            if all(value == hi for value in values):
                notes.append(f"top {len(top)} all at high boundary {factor}={hi}; expand higher if physically valid")
        return notes
    return []


def range_or_none(values):
    return None if not values else [float(min(values)), float(max(values))]


def effect_ranges(rows: list[dict], top_n=8) -> list[tuple[str, float]]:
    ok = [row for row in rows if row.get("ok") and row.get("total_score") is not None and abs(row["total_score"]) < BAD_SCORE]
    if not ok:
        return []
    factors = [key for key in ok[0].get("recipe", {}) if key not in {"name", "recipe_id", "recipe_hash"}]
    effects = []
    for factor in factors:
        by_value = defaultdict(list)
        for row in ok:
            by_value[row["recipe"].get(factor)].append(row["total_score"])
        means = [mean(scores) for scores in by_value.values() if scores]
        if len(means) >= 2:
            effects.append((factor, max(means) - min(means)))
    return sorted(effects, key=lambda item: item[1], reverse=True)[:top_n]


def write_report(rows: list[dict], out_path: Path, expected_rows: int | None,
                 space: dict | None = None) -> None:
    ranked = aggregate(rows)
    failures = failure_counts(rows)
    steps = step_names(rows)
    top = ranked[:8]
    best = ranked[0] if ranked else None
    done = len(rows)
    status = f"{done}/{expected_rows}" if expected_rows else str(done)

    lines = [
        "# Joint Process DOE Review\n\n",
        f"Status: {status} checkpointed rows across {len(ranked)} recipes.\n\n",
        "Ranking rule: hard-gate invalid metrics and CMP mask consumption, then maximize replicated "
        "step-target pass count, then minimize p90 full-process score. This prevents a single lucky "
        "replicate, a destructive CMP setting, or a raw proxy score from becoming the story.\n\n",
    ]

    if best:
        failed = [
            step for step, score in best["step_summary"].items()
            if score.get("pass_rate") != 1.0
        ]
        lines += [
            "## Critical read\n\n",
            f"- Current best: `{best['name']}` / `{best['recipe_hash']}` with "
            f"mean step pass count {fmt(best['mean_step_pass_count'])}, "
            f"p90/worst score {fmt(best['p90_total_score'])}/{fmt(best['worst_total_score'])}.\n",
            f"- Failed or unstable specs on current best: {', '.join(failed) if failed else 'none'}.\n",
        ]
        if failed:
            lines.append("- Do not claim a full-process success yet; report the best miss and why it misses.\n")
        if failures["cmp_mask_consumed"]:
            lines.append("- CMP mask consumption appears in the sampled space; high polish can improve dish while destroying the mask.\n")
        if failures["fill"]:
            lines.append("- Fill remains a recurring target miss; tip-gap, not floor coverage, is the gating metric.\n")
        if any(row["invalid_score_runs"] for row in ranked):
            lines.append("- Some recipes hit invalid-metric penalties; keep them as bad-region evidence, not deleted outliers.\n")
        lines.append("\n")

    lines += [
        "## Top candidates\n\n",
        "| Rank | Recipe | Runs | Step pass mean | Pass range | p90 score | worst score | depth | bulge | tip gap | CMP dish | mask consumed |\n",
        "|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|\n",
    ]
    for i, row in enumerate(top, 1):
        lines.append(
            f"| {i} | `{row['name']}` | {row['ok_runs']}/{row['runs']} | "
            f"{fmt(row['mean_step_pass_count'])} | {row['pass_count_range']} | "
            f"{fmt(row['p90_total_score'])} | {fmt(row['worst_total_score'])} | {fmt(row['mean_depth'])} | "
            f"{fmt(row['mean_bulge'])} | {fmt(row['mean_tip_gap'])} | "
            f"{fmt(row['mean_cmp_dish'])} | {fmt(row['cmp_mask_consumed_rate'])} |\n"
        )
    lines.append("\n")

    lines += [
        "## Step failures\n\n",
        "| Failure | Rows |\n",
        "|---|---:|\n",
    ]
    for key, count in failures.most_common():
        lines.append(f"| `{key}` | {count} |\n")
    lines.append("\n")

    if top:
        lines += ["## Best-candidate step stability\n\n", "| Step | Pass rate | Mean score |\n", "|---|---:|---:|\n"]
        for step in steps:
            data = best["step_summary"].get(step, {})
            lines.append(f"| `{step}` | {fmt(data.get('pass_rate'))} | {fmt(data.get('mean_score'))} |\n")
        lines.append("\n")

    boundary = boundary_notes(ranked, space)
    lines += ["## Boundary checks\n\n"]
    if boundary:
        lines += [f"- {note}\n" for note in boundary]
    elif space is None:
        lines.append("- Sampled ranges were not supplied; no boundary claim is made.\n")
    else:
        lines.append("- No top candidate sits on a sampled range boundary.\n")
    lines.append("\n")

    effects = effect_ranges(rows)
    lines += ["## Largest sampled effects\n\n", "| Factor | Mean-score range |\n", "|---|---:|\n"]
    for factor, delta in effects:
        lines.append(f"| `{factor}` | {fmt(delta)} |\n")
    lines.append("\n")

    complete = expected_rows is not None and done >= expected_rows
    lines += ["## Next decision\n\n"]
    if complete:
        lines.append(
            "Run `autoresearch_joint_process.py` from `joint_process_doe_summary.json`, carry the top candidates, "
            "and narrow/expand only after checking boundary notes.\n"
        )
    else:
        lines.append(
            "Finish the current checkpointed bootstrap before calling a winner. Partial results are useful for monitoring, "
            "but the focus half of the mixed design must be included in the first real generation.\n"
        )

    out_path.write_text("".join(lines))


def best_loss(rows: list[dict]) -> float:
    ranked = aggregate(rows)
    if not ranked:
        return BAD_SCORE
    best = ranked[0]
    missing_step_penalty = 100.0 * (6.0 - (best["mean_step_pass_count"] or 0.0))
    mask_penalty = 1000.0 * (best["cmp_mask_consumed_rate"] or 0.0)
    invalid_penalty = BAD_SCORE if best["invalid_score_runs"] else 0.0
    score = best["p90_total_score"] if best["p90_total_score"] is not None else BAD_SCORE
    return float(score + missing_step_penalty + mask_penalty + invalid_penalty)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="joint_process_doe_results.jsonl")
    parser.add_argument("--out", default="joint_process_review.md")
    parser.add_argument("--expected-rows", type=int, default=None)
    parser.add_argument("--metric-only", action="store_true")
    args = parser.parse_args()

    rows = load_rows(Path(args.results))
    if not rows:
        raise SystemExit(f"no rows found in {args.results}")
    if args.metric_only:
        print(best_loss(rows))
        return
    write_report(rows, Path(args.out), args.expected_rows)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

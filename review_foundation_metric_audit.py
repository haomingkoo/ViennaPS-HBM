"""Review pattern/DRIE metric convergence without producing a recipe score."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


DEFAULT_ROWS = Path(
    "autoresearch-results/restart_audit/metric_convergence_rows.jsonl"
)
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/metric_convergence_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/metric_convergence_review.md"
)
DEFAULT_GRID_EXTENSION = Path(
    "autoresearch-results/restart_audit/grid_extension_rows.jsonl"
)

METRICS = {
    "pattern_bottom_cd": ("pattern", "opening_cd_bottom"),
    "pattern_middle_cd": ("pattern", "opening_cd_middle"),
    "pattern_top_cd": ("pattern", "opening_cd_top"),
    "pattern_mask_height": ("pattern", "mask_height"),
    "pattern_center_shift": ("pattern", "opening_center_shift"),
    "post_etch_mask_height": ("mask_remaining_height",),
    "etch_depth": ("etch", "depth"),
    "etch_cd_top": ("etch", "cd_top"),
    "etch_cd_middle": ("etch", "cd_middle"),
    "etch_cd_bottom": ("etch", "cd_bottom"),
    "etch_cd_min": ("etch", "cd_min"),
    "etch_cd_max": ("etch", "cd_max"),
    "etch_max_cd_error": ("etch", "max_cd_error"),
    "etch_sidewall_angle_deg": ("etch", "sidewall_angle_deg"),
    "etch_max_bow": ("etch", "max_bow"),
    "etch_scallop_rms": ("etch", "scallop_rms"),
}


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def metric(row, path):
    value = row
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return float(value) if value is not None and math.isfinite(float(value)) else None


def stats(values):
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"n": 0, "mean": None, "sd": None, "p10": None, "p90": None,
                "min": None, "max": None}
    return {
        "n": len(clean),
        "mean": statistics.fmean(clean),
        "sd": statistics.stdev(clean) if len(clean) > 1 else 0.0,
        "p10": float(np.percentile(clean, 10)),
        "p90": float(np.percentile(clean, 90)),
        "min": min(clean),
        "max": max(clean),
    }


def group_summary(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return {
        str(group): {
            "rows": len(group_rows),
            "metrics": {
                name: stats(metric(row, path) for row in group_rows)
                for name, path in METRICS.items()
            },
            "passes": pass_counts(group_rows),
        }
        for group, group_rows in sorted(groups.items())
    }


def row_passes(row):
    target = row["target"]
    depth = metric(row, METRICS["etch_depth"])
    max_cd_error = metric(row, METRICS["etch_max_cd_error"])
    max_bow = metric(row, METRICS["etch_max_bow"])
    pattern_cd = metric(row, METRICS["pattern_bottom_cd"])
    pattern_height = metric(row, METRICS["pattern_mask_height"])
    remaining_mask_height = metric(row, METRICS["post_etch_mask_height"])
    grid_delta = metric(row, ("grid_delta",))
    pattern = row.get("pattern", {})
    post_etch_mask = row.get("post_etch_mask") or {}
    return {
        "pattern_width": (
            pattern_cd is not None
            and abs(pattern_cd - target["opening_cd"]) <= target["max_width_error"]
        ),
        "pattern_height": (
            pattern_height is not None
            and grid_delta is not None
            and abs(pattern_height - target["mask_height"]) <= grid_delta
        ),
        "pattern_opening": pattern.get("opening_valid") is True,
        "etch_depth": (
            depth is not None
            and abs(depth - target["etch_depth"]) <= target["depth_tolerance"]
        ),
        "etch_cd_profile": (
            max_cd_error is not None
            and max_cd_error <= target["max_width_error"]
        ),
        "etch_bow": (
            max_bow is not None and max_bow <= target["max_wall_bulge"]
        ),
        "etch_mask_resolved": (
            remaining_mask_height is not None
            and grid_delta is not None
            and remaining_mask_height > 2.0 * grid_delta
            and post_etch_mask.get("opening_valid") is True
        ),
    }


def pass_counts(rows):
    counts = Counter()
    for row in rows:
        for name, passed in row_passes(row).items():
            counts[name] += int(passed)
    names = (
        "pattern_width",
        "pattern_height",
        "pattern_opening",
        "etch_depth",
        "etch_cd_profile",
        "etch_bow",
        "etch_mask_resolved",
    )
    return {name: {"pass": counts[name], "total": len(rows)} for name in names}


def paired_differences(rows, factor, reference):
    by_seed = {(row["rng_seed"], row[factor]): row for row in rows}
    levels = sorted({row[factor] for row in rows})
    result = {}
    for level in levels:
        if level == reference:
            continue
        differences = defaultdict(list)
        seeds = sorted({seed for seed, candidate in by_seed if candidate == level})
        for seed in seeds:
            candidate = by_seed.get((seed, level))
            baseline = by_seed.get((seed, reference))
            if candidate is None or baseline is None:
                continue
            for name, path in METRICS.items():
                a, b = metric(candidate, path), metric(baseline, path)
                if a is not None and b is not None:
                    differences[name].append(a - b)
        result[str(level)] = {
            name: {
                "n_pairs": len(values),
                "mean_delta": statistics.fmean(values) if values else None,
                "mean_abs_delta": statistics.fmean(abs(value) for value in values)
                if values else None,
                "max_abs_delta": max((abs(value) for value in values), default=None),
            }
            for name, values in differences.items()
        }
    return result


def fmt(value, digits=5):
    return "—" if value is None else f"{value:.{digits}g}"


def markdown(summary):
    lines = [
        "# Foundation metric convergence review",
        "",
        f"Status: **{summary['status']}**. Rows: {summary['row_count']}/"
        f"{summary['expected_rows']}; valid: {summary['ok_count']}; errors: "
        f"{summary['error_count']}.",
        f"Finer-grid extension: {summary['extension']['row_count']}/"
        f"{summary['extension']['expected_rows']}; valid: "
        f"{summary['extension']['ok_count']}; errors: "
        f"{summary['extension']['error_count']}.",
        "",
        "This audit qualifies measurement and numerical controls. It does not "
        "rank recipes or authorize a DOE.",
        "",
        "## Baseline stochastic spread",
        "",
        "| Metric | n | mean | SD | p10 | p90 | min | max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    baseline = summary["baseline"]["metrics"]
    for name, values in baseline.items():
        lines.append(
            f"| {name} | {values['n']} | {fmt(values['mean'])} | "
            f"{fmt(values['sd'])} | {fmt(values['p10'])} | "
            f"{fmt(values['p90'])} | {fmt(values['min'])} | "
            f"{fmt(values['max'])} |"
        )

    for title, key in (("Grid levels", "grid_groups"), ("Ray-count levels", "ray_groups")):
        lines += ["", f"## {title}", ""]
        for level, group in summary[key].items():
            lines += [f"### {level}", "", "| Metric | mean | SD |", "|---|---:|---:|"]
            for name, values in group["metrics"].items():
                lines.append(f"| {name} | {fmt(values['mean'])} | {fmt(values['sd'])} |")

    lines += [
        "",
        "## Interpretation required",
        "",
        "Sol must compare paired numerical bias with stochastic spread, grid "
        "size, and remaining specification margin. Scallop and thin-layer "
        "claims remain suspended until their feature size is resolved. No "
        "automatic grid or ray-count winner is emitted by this script.",
        "",
    ]
    if summary["errors"]:
        lines += ["## Errors", ""] + [f"- `{error['case_id']}`: {error['error']}" for error in summary["errors"]]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    parser.add_argument("--expected-rows", type=int, default=88)
    parser.add_argument("--grid-extension-rows", type=Path, default=DEFAULT_GRID_EXTENSION)
    parser.add_argument("--expected-extension-rows", type=int, default=8)
    args = parser.parse_args()

    rows = load_rows(args.rows)
    extension_rows = (
        load_rows(args.grid_extension_rows)
        if args.grid_extension_rows.exists() else []
    )
    ok = [row for row in rows if row.get("ok")]
    extension_ok = [row for row in extension_rows if row.get("ok")]
    errors = [
        {"case_id": row.get("case_id"), "error": row.get("error")}
        for row in rows if not row.get("ok")
    ]
    ids = [row.get("case_id") for row in rows]
    all_ids = ids + [row.get("case_id") for row in extension_rows]
    duplicates = sorted(case for case, count in Counter(all_ids).items() if count > 1)
    extension_errors = [
        {"case_id": row.get("case_id"), "error": row.get("error")}
        for row in extension_rows if not row.get("ok")
    ]

    baseline_rows = [row for row in ok if row["design"] == "stochastic_baseline"]
    grid_rows = [row for row in ok if row["design"] == "grid_convergence"] + extension_ok
    ray_rows = [row for row in ok if row["design"] == "ray_convergence"]
    summary = {
        "status": (
            "complete"
            if (
                len(rows) == args.expected_rows
                and len(extension_rows) == args.expected_extension_rows
                and not errors
                and not extension_errors
                and not duplicates
            )
            else "incomplete_or_invalid"
        ),
        "expected_rows": args.expected_rows,
        "row_count": len(rows),
        "ok_count": len(ok),
        "error_count": len(errors),
        "duplicate_case_ids": duplicates,
        "errors": errors,
        "extension": {
            "expected_rows": args.expected_extension_rows,
            "row_count": len(extension_rows),
            "ok_count": len(extension_ok),
            "error_count": len(extension_errors),
            "errors": extension_errors,
        },
        "baseline": {
            "rows": len(baseline_rows),
            "metrics": {
                name: stats(metric(row, path) for row in baseline_rows)
                for name, path in METRICS.items()
            },
            "passes": pass_counts(baseline_rows),
        },
        "grid_groups": group_summary(grid_rows, "grid_delta"),
        "ray_groups": group_summary(ray_rows, "rays_per_point"),
        "grid_paired_delta_from_0.005": paired_differences(
            grid_rows, "grid_delta", 0.005
        ),
        "grid_paired_delta_from_0.0025": paired_differences(
            grid_rows, "grid_delta", 0.0025
        ),
        "ray_paired_delta_from_4000": paired_differences(
            ray_rows, "rays_per_point", 4000
        ),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    args.markdown.write_text(markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "rows": summary["row_count"],
        "ok": summary["ok_count"],
        "errors": summary["error_count"],
        "extension_rows": summary["extension"]["row_count"],
        "extension_errors": summary["extension"]["error_count"],
    }))


if __name__ == "__main__":
    main()

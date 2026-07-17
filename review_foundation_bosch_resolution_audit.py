"""Review single-cycle Bosch passivation/grid resolution."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


METRICS = {
    "polymer_min_wall": ("passivation_metrics", "minimum_wall_thickness"),
    "polymer_lower_wall": ("passivation_metrics", "lower_wall_thickness"),
    "polymer_floor": ("passivation_metrics", "floor_thickness"),
    "polymer_aperture": ("passivation_metrics", "minimum_remaining_aperture"),
    "one_cycle_depth": ("etch_metrics", "depth"),
    "one_cycle_cd_bottom": ("etch_metrics", "cd_bottom"),
    "one_cycle_bow": ("etch_metrics", "max_bow"),
}


def value(row, path):
    result = row
    for key in path:
        result = result[key]
    return float(result)


def stats(values):
    values = list(values)
    return {
        "n": len(values),
        "mean": statistics.fmean(values) if values else None,
        "sd": statistics.stdev(values) if len(values) > 1 else 0.0 if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rows",
        type=Path,
        default=Path("autoresearch-results/restart_audit/bosch_resolution_rows.jsonl"),
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("autoresearch-results/restart_audit/bosch_resolution_summary.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("autoresearch-results/restart_audit/bosch_resolution_review.md"),
    )
    parser.add_argument("--expected-rows", type=int, default=16)
    parser.add_argument(
        "--fine-rows",
        type=Path,
        default=Path("autoresearch-results/restart_audit/bosch_resolution_fine_rows.jsonl"),
    )
    parser.add_argument("--expected-fine-rows", type=int, default=4)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.rows.read_text().splitlines() if line.strip()]
    fine_rows = (
        [
            json.loads(line)
            for line in args.fine_rows.read_text().splitlines()
            if line.strip()
        ]
        if args.fine_rows.exists() else []
    )
    rows += fine_rows
    ok = [row for row in rows if row.get("ok")]
    errors = [row for row in rows if not row.get("ok")]
    ids = [row.get("case_id") for row in rows]
    duplicates = [case for case, count in Counter(ids).items() if count > 1]
    groups = defaultdict(list)
    for row in ok:
        groups[row["grid_delta"]].append(row)

    reference_grid = min(groups) if groups else None
    reference = {
        row["rng_seed"]: row for row in groups.get(reference_grid, [])
    }
    paired = {}
    for grid, group in sorted(groups.items()):
        if grid == reference_grid:
            continue
        deltas = defaultdict(list)
        for row in group:
            other = reference.get(row["rng_seed"])
            if other is None:
                continue
            for metric, path in METRICS.items():
                deltas[metric].append(value(row, path) - value(other, path))
        paired[str(grid)] = {
            metric: {
                **stats(values),
                "mean_abs": statistics.fmean(abs(item) for item in values)
                if values else None,
            }
            for metric, values in deltas.items()
        }

    summary = {
        "status": (
            "complete"
            if (
                len(rows) == args.expected_rows + args.expected_fine_rows
                and len(fine_rows) == args.expected_fine_rows
                and not errors
                and not duplicates
            )
            else "incomplete_or_invalid"
        ),
        "expected_rows": args.expected_rows + args.expected_fine_rows,
        "row_count": len(rows),
        "ok_count": len(ok),
        "error_count": len(errors),
        "duplicate_case_ids": duplicates,
        "errors": [
            {"case_id": row.get("case_id"), "error": row.get("error")}
            for row in errors
        ],
        "grid_groups": {
            str(grid): {
                "rows": len(group),
                "passivation_cells_per_input_dose": 0.005 / grid,
                "metrics": {
                    metric: stats(value(row, path) for row in group)
                    for metric, path in METRICS.items()
                },
            }
            for grid, group in sorted(groups.items())
        },
        "reference_grid": reference_grid,
        "paired_delta_from_finest_grid": paired,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Bosch passivation resolution review",
        "",
        f"Status: **{summary['status']}**. Rows {len(rows)}/"
        f"{args.expected_rows + args.expected_fine_rows}; "
        f"valid {len(ok)}; errors {len(errors)}.",
        "",
        "| Grid | dose/grid | polymer min wall | polymer lower wall | polymer floor | aperture | one-cycle depth | bottom CD | bow |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for grid, group in summary["grid_groups"].items():
        metric = group["metrics"]
        lines.append(
            f"| {grid} | {group['passivation_cells_per_input_dose']:.3g} | "
            f"{metric['polymer_min_wall']['mean']:.6g} | "
            f"{metric['polymer_lower_wall']['mean']:.6g} | "
            f"{metric['polymer_floor']['mean']:.6g} | "
            f"{metric['polymer_aperture']['mean']:.6g} | "
            f"{metric['one_cycle_depth']['mean']:.6g} | "
            f"{metric['one_cycle_cd_bottom']['mean']:.6g} | "
            f"{metric['one_cycle_bow']['mean']:.6g} |"
        )
    lines += [
        "",
        "No full-cycle grid is accepted automatically. Sol must inspect the "
        "paired approach to the finest-grid reference and decide whether another "
        "focused resolution level is required.",
        "",
    ]
    args.markdown.write_text("\n".join(lines))
    print(json.dumps({
        "status": summary["status"],
        "rows": len(rows),
        "ok": len(ok),
        "errors": len(errors),
    }))


if __name__ == "__main__":
    main()

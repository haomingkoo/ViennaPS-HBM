"""Aggregate high-fidelity per-cycle DRIE checkpoints by common cycle count."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def stats(values):
    values = list(values)
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "sd": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def select_logical_rows(rows):
    """Select one valid row per simulator seed while retaining every attempt."""
    valid_by_seed = {}
    errors = []
    superseded_valid = []
    for row in rows:
        seed = row.get("rng_seed", row.get("case_id"))
        if not row.get("ok"):
            errors.append(row)
            continue
        if seed in valid_by_seed:
            superseded_valid.append(valid_by_seed[seed])
        valid_by_seed[seed] = row
    return (
        [valid_by_seed[seed] for seed in sorted(valid_by_seed, key=str)],
        errors,
        superseded_valid,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rows",
        type=Path,
        default=Path("autoresearch-results/restart_audit/bosch_high_fidelity_rows.jsonl"),
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("autoresearch-results/restart_audit/bosch_cycle_history_summary.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("autoresearch-results/restart_audit/bosch_cycle_history_review.md"),
    )
    parser.add_argument("--expected-rows", type=int, default=4)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.rows.read_text().splitlines() if line.strip()]
    ok, errors, superseded_valid = select_logical_rows(rows)
    by_cycle = defaultdict(list)
    for row in ok:
        for checkpoint in row.get("cycle_history", []):
            by_cycle[checkpoint["cycle"]].append(checkpoint)

    target = ok[0]["target"] if ok else {}
    cycle_rows = []
    for cycle, checkpoints in sorted(by_cycle.items()):
        depth_pass = [
            abs(item["depth"] - target["etch_depth"]) <= target["depth_tolerance"]
            for item in checkpoints
        ]
        cd_pass = [
            item["max_cd_error"] <= target["max_width_error"]
            for item in checkpoints
        ]
        bow_pass = [
            item["max_bow"] <= target["max_wall_bulge"]
            for item in checkpoints
        ]
        cycle_rows.append({
            "cycle": cycle,
            "rows": len(checkpoints),
            "depth": stats(item["depth"] for item in checkpoints),
            "cd_top": stats(item["cd_top"] for item in checkpoints),
            "cd_middle": stats(item["cd_middle"] for item in checkpoints),
            "cd_bottom": stats(item["cd_bottom"] for item in checkpoints),
            "max_cd_error": stats(item["max_cd_error"] for item in checkpoints),
            "max_bow": stats(item["max_bow"] for item in checkpoints),
            "scallop_rms": stats(item["scallop_rms"] for item in checkpoints),
            "depth_passes": sum(depth_pass),
            "cd_passes": sum(cd_pass),
            "bow_passes": sum(bow_pass),
            "all_gate_passes": sum(
                a and b and c for a, b, c in zip(depth_pass, cd_pass, bow_pass)
            ),
            "common_pass": bool(
                len(checkpoints) == args.expected_rows
                and all(depth_pass)
                and all(cd_pass)
                and all(bow_pass)
            ),
        })

    common = [row["cycle"] for row in cycle_rows if row["common_pass"]]
    summary = {
        "status": (
            "complete_with_recovered_attempts"
            if len(ok) == args.expected_rows and errors
            else "complete"
            if len(ok) == args.expected_rows
            else "incomplete_or_invalid"
        ),
        "expected_rows": args.expected_rows,
        "attempt_count": len(rows),
        "ok_count": len(ok),
        "attempt_error_count": len(errors),
        "superseded_valid_count": len(superseded_valid),
        "errors": [
            {"case_id": row.get("case_id"), "error": row.get("error")}
            for row in errors
        ],
        "target": target,
        "common_passing_cycles": common,
        "cycles": cycle_rows,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    lines = [
        "# High-fidelity Bosch cycle-history review",
        "",
        f"Status: **{summary['status']}**. Valid simulator seeds "
        f"{len(ok)}/{args.expected_rows}; attempts {len(rows)}; "
        f"failed attempts retained {len(errors)}.",
        "",
        f"Common passing cycles: {common if common else 'none'}.",
        "",
        "| Cycle | n | depth mean | depth range | top CD | mid CD | bottom CD | max CD error | bow | depth pass | CD pass | bow pass | common pass |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in cycle_rows:
        lines.append(
            f"| {row['cycle']} | {row['rows']} | {row['depth']['mean']:.6g} | "
            f"{row['depth']['min']:.6g}–{row['depth']['max']:.6g} | "
            f"{row['cd_top']['mean']:.6g} | {row['cd_middle']['mean']:.6g} | "
            f"{row['cd_bottom']['mean']:.6g} | {row['max_cd_error']['mean']:.6g} | "
            f"{row['max_bow']['mean']:.6g} | {row['depth_passes']} | "
            f"{row['cd_passes']} | {row['bow_passes']} | {int(row['common_pass'])} |"
        )
    args.markdown.write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "status": summary["status"],
        "attempts": len(rows),
        "ok": len(ok),
        "attempt_errors": len(errors),
        "common_passing_cycles": common,
    }))


if __name__ == "__main__":
    main()

"""Summarize controlled fill range results without a scalar score."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rows",
        type=Path,
        default=Path("autoresearch-results/restart_audit/fill_range_rows.jsonl"),
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("autoresearch-results/restart_audit/fill_range_summary.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("autoresearch-results/restart_audit/fill_range_review.md"),
    )
    parser.add_argument("--expected-rows", type=int, default=51)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.rows.read_text().splitlines() if line.strip()]
    ids = [row.get("case_id") for row in rows]
    errors = [row for row in rows if not row.get("ok")]
    duplicates = [case for case, count in Counter(ids).items() if count > 1]
    valid = [row for row in rows if row.get("ok")]
    valid.sort(key=lambda row: (row["design"], row["iso_ratio"], row["dose"]))
    summary = {
        "status": (
            "complete"
            if len(rows) == args.expected_rows and not errors and not duplicates
            else "incomplete_or_invalid"
        ),
        "expected_rows": args.expected_rows,
        "row_count": len(rows),
        "ok_count": len(valid),
        "error_count": len(errors),
        "duplicate_case_ids": duplicates,
        "target_pass_count": sum(row["target_pass"] for row in valid),
        "rows": [{
            "case_id": row["case_id"],
            "design": row["design"],
            "dose": row["dose"],
            "iso_ratio": row["iso_ratio"],
            "target_pass": row["target_pass"],
            **{key: row["metrics"][key] for key in (
                "open_void",
                "closed_void_count",
                "void_free",
                "center_overburden",
                "field_overburden_mean",
                "overburden_min",
                "overburden_nonuniformity",
                "pre_cmp_recess",
            )},
        } for row in valid],
        "errors": [
            {"case_id": row.get("case_id"), "error": row.get("error")}
            for row in errors
        ],
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Controlled fill range review",
        "",
        f"Status: **{summary['status']}**. Rows {len(rows)}/{args.expected_rows}; "
        f"valid {len(valid)}; errors {len(errors)}; target passes "
        f"{summary['target_pass_count']}.",
        "",
        "The models in this table are morphology/range controls, not electrochemical recipe models.",
        "",
        "| Model | dose | iso ratio | open | sealed voids | void-free | center OB | field OB | min OB | relief | target |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["rows"]:
        lines.append(
            f"| {row['design']} | {row['dose']:.4g} | {row['iso_ratio']:.4g} | "
            f"{int(row['open_void'])} | {row['closed_void_count']} | "
            f"{int(row['void_free'])} | {row['center_overburden']:.4g} | "
            f"{row['field_overburden_mean']:.4g} | {row['overburden_min']:.4g} | "
            f"{row['pre_cmp_recess']:.4g} | {int(row['target_pass'])} |"
        )
    args.markdown.write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "status": summary["status"],
        "rows": len(rows),
        "ok": len(valid),
        "errors": len(errors),
        "target_passes": summary["target_pass_count"],
    }))


if __name__ == "__main__":
    main()

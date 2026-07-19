"""Review the completed focused Bosch ion map without rerunning it."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
import statistics
import sys

import foundation_pattern_bosch_gate0 as gate0
import v3_bosch_focused_ion_map_runner as focused_runner
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "evidence/numerical/v3_bosch_focused_ion_map_manifest.json"
ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_focused_ion_map_rows.jsonl"
PRIOR_ROWS = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_rows.jsonl"
OUTPUT = ROOT / "evidence/numerical/v3_bosch_focused_ion_map_review.json"
PRIOR_CASE_ID = "7405eb159356c564"
METRICS = (
    "depth",
    "cd_top",
    "cd_middle",
    "cd_bottom",
    "max_bow",
    "sidewall_angle_deg",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prior_row() -> tuple[dict, int]:
    matches = [
        (gate0.strict_json_loads(line), number)
        for number, line in enumerate(PRIOR_ROWS.read_text().splitlines(), 1)
        if line.strip() and PRIOR_CASE_ID in line
    ]
    if len(matches) != 1 or matches[0][0].get("case_id") != PRIOR_CASE_ID:
        raise ValueError("saved prior best is missing or ambiguous")
    return matches[0]


def measurements(row: dict) -> dict[str, float]:
    etch = row["selected_cycle_metrics"]["etch"]
    result = {name: float(etch[name]) for name in METRICS}
    if any(not math.isfinite(value) for value in result.values()):
        raise ValueError(f"nonfinite focused-map measurement: {row.get('case_id')}")
    return result


def cell_summary(rows: list[dict]) -> dict:
    result = {}
    for metric in METRICS:
        values = [measurements(row)[metric] for row in rows]
        current = {"values": values}
        if len(values) >= 2:
            current.update(mean=statistics.mean(values), sample_sd=statistics.stdev(values))
        result[metric] = current
    return result


def representative(summary: dict, metric: str) -> float:
    values = summary[metric]["values"]
    return summary[metric].get("mean", values[0])


def objectives(summary: dict, target_depth: float, target_cd: float) -> dict:
    return {
        "absolute_depth_deviation": abs(representative(summary, "depth") - target_depth),
        "absolute_top_cd_deviation": abs(representative(summary, "cd_top") - target_cd),
        "absolute_middle_cd_deviation": abs(representative(summary, "cd_middle") - target_cd),
        "absolute_bottom_cd_deviation": abs(representative(summary, "cd_bottom") - target_cd),
        "bow": representative(summary, "max_bow"),
        "absolute_sidewall_angle": abs(representative(summary, "sidewall_angle_deg")),
    }


def dominates(first: dict, second: dict) -> bool:
    return all(first[name] <= second[name] for name in first) and any(
        first[name] < second[name] for name in first
    )


def build_review(
    rows: list[dict],
    manifest: dict,
    prior: dict,
    *,
    rows_path: Path = ROWS,
    prior_line: int,
) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["recipe"]["ion_source_exponent"], row["recipe"]["ion_rate"])].append(row)
    expected_counts = {
        (50, -0.04): 2,
        (141, -0.06324555): 3,
        **{
            (exponent, rate): 1
            for exponent in (50, 141, 400)
            for rate in (-0.04, -0.06324555, -0.1)
            if (exponent, rate) not in {(50, -0.04), (141, -0.06324555)}
        },
    }
    if {cell: len(current) for cell, current in grouped.items()} != expected_counts:
        raise ValueError("focused-map cell counts differ from the frozen design")

    cells = []
    levels = manifest["design"]["design"]["factor_levels"]
    for exponent in levels["ion_source_exponent"]:
        for rate in levels["ion_rate"]:
            current = sorted(grouped[(exponent, rate)], key=lambda row: row["rng_seed"])
            summary = cell_summary(current)
            cells.append({
                "cell_id": f"e{exponent}_i{abs(rate):.8g}",
                "ion_source_exponent": exponent,
                "ion_rate": rate,
                "new_run_count": len(current),
                "case_ids": [row["case_id"] for row in current],
                "measurements": summary,
            })

    prior_summary = {
        metric: {"values": [value]}
        for metric, value in measurements(prior).items()
    }
    target = manifest["design"]["target"]
    target_depth = float(target["etch_depth"])
    target_cd = float(target["opening_cd"])
    compared = {
        cell["cell_id"]: objectives(cell["measurements"], target_depth, target_cd)
        for cell in cells
    }
    compared["prior_saved_best"] = objectives(prior_summary, target_depth, target_cd)
    front = sorted(
        name for name, values in compared.items()
        if not any(
            other_name != name and dominates(other, values)
            for other_name, other in compared.items()
        )
    )
    candidates = [
        {
            "cell_id": name,
            "basis": "pareto_nondominated_against_all_new_cells_and_saved_prior_best",
        }
        for name in front if name != "prior_saved_best"
    ]

    return {
        "schema_version": 1,
        "campaign": "v3-bosch-focused-ion-map-review",
        "status": "complete_descriptive_review",
        "completeness": {
            "required_new_rows": 12,
            "observed_new_rows": len(rows),
            "unique_new_case_ids": len({row["case_id"] for row in rows}),
            "unique_factor_cells": len(cells),
            "all_new_rows_successful": all(row.get("ok") is True for row in rows),
        },
        "provenance": {
            "manifest": {
                "path": str(MANIFEST.relative_to(ROOT)),
                "sha256": digest(MANIFEST),
            },
            "new_rows": {
                "path": str(rows_path.relative_to(ROOT)),
                "sha256": digest(rows_path),
                "line_numbers": list(range(1, 13)),
            },
            "saved_prior_best": {
                "path": str(PRIOR_ROWS.relative_to(ROOT)),
                "sha256": digest(PRIOR_ROWS),
                "line_numbers": [prior_line],
                "case_id": PRIOR_CASE_ID,
                "checkpoint_path": prior["checkpoint_path"],
                "checkpoint_sha256": prior["checkpoint_sha256"],
                "measurements": prior_summary,
            },
        },
        "cells": cells,
        "pareto_analysis": {
            "method": "strict Pareto dominance; every objective is minimized",
            "comparison_targets": {
                "depth": target_depth,
                "top_middle_bottom_cd": target_cd,
                "source": "frozen manifest teaching-comparison values; not pass limits",
            },
            "objectives_by_entry": compared,
            "pareto_front": front,
            "weighted_score_used": False,
            "pass_limits_applied": False,
        },
        "confirmation_candidates": candidates,
        "authority": {
            "candidate_meaning": "cells meriting independent sensitivity or confirmation checks",
            "recipe_authorized": False,
            "process_window_authorized": False,
            "statistical_significance_authorized": False,
        },
    }


def build() -> dict:
    manifest = gate0.strict_json_loads(MANIFEST.read_text())
    expected = stage2a.expand_cases(manifest)
    stage2a.evidence_origin = focused_runner.evidence_origin
    completed = stage2a.audit_existing_rows(ROWS, expected)
    if len(completed) != 12:
        raise ValueError(f"incomplete focused ion map: expected 12 successful rows, found {len(completed)}")
    ordered = [completed[case["case_id"]] for case in expected]
    prior, line_number = prior_row()
    return build_review(ordered, manifest, prior, prior_line=line_number)


def main() -> int:
    try:
        review = build()
    except ValueError as error:
        print(json.dumps({
            "status": "incomplete_evidence",
            "message": str(error),
            "output_written": False,
        }, sort_keys=True))
        return 1
    OUTPUT.write_text(json.dumps(review, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({
        "status": review["status"],
        "cells": review["completeness"]["unique_factor_cells"],
        "confirmation_candidates": len(review["confirmation_candidates"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

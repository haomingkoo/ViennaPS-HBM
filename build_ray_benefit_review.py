"""Summarize the observed cost and stability of Bosch ray counts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parent
ROWS = ROOT / "evidence/numerical/metric_convergence_rows.jsonl"
PHASE_B = ROOT / "evidence/numerical/bosch_ray_phase_b_review.json"
CHEAP = ROOT / "evidence/numerical/v3_bosch_cheap_qualification_review.json"
OUTPUT = ROOT / "evidence/numerical/ray_benefit_review.json"
SCHEMA = ROOT / "schemas/ray-benefit-review.schema.json"
BUILDER = Path(__file__).resolve()
RAY_LEVELS = (250, 1_000, 2_000, 4_000)
METRICS = {
    "depth": "depth",
    "cd_top": "cd_top",
    "cd_middle": "cd_middle",
    "cd_bottom": "cd_bottom",
    "max_bow": "max_bow",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def citation(path: Path, selector: str, line_numbers: list[int] | None = None) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": digest(path),
        "selector": selector,
        "line_numbers": line_numbers,
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def stats(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
        "p10": percentile(values, 0.1),
        "p90": percentile(values, 0.9),
        "sample_sd": statistics.stdev(values),
    }


def load_rows() -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in ROWS.read_text().splitlines() if line.strip()]
    selected = [row for row in rows if row["design"] == "ray_convergence"]
    if len(selected) != 32 or not all(row["ok"] for row in selected):
        raise ValueError("expected 32 successful ray-convergence rows")
    if {row["rays_per_point"] for row in selected} != set(RAY_LEVELS):
        raise ValueError("ray ladder differs")
    if {row["grid_delta"] for row in selected} != {0.01}:
        raise ValueError("ray ladder grid differs")
    if len({row["case_id"] for row in selected}) != len(selected):
        raise ValueError("ray ladder contains duplicate case IDs")
    if len({(row["rays_per_point"], row["rng_seed"]) for row in selected}) != len(selected):
        raise ValueError("ray ladder contains duplicate ray/seed rows")
    recipes = {json.dumps(row["recipe"], sort_keys=True) for row in selected}
    if len(recipes) != 1:
        raise ValueError("ray ladder recipes differ")
    for field in ("geometry", "target", "provenance"):
        values = {json.dumps(row[field], sort_keys=True) for row in selected}
        if len(values) != 1:
            raise ValueError(f"ray ladder {field} differs")
    expected_seeds = set(range(53_000, 53_008))
    for rays in RAY_LEVELS:
        seeds = {row["rng_seed"] for row in selected if row["rays_per_point"] == rays}
        if seeds != expected_seeds:
            raise ValueError(f"seed set differs at {rays} rays")
    return selected


def value(row: dict[str, Any], metric: str) -> float:
    result = row["etch"][METRICS[metric]]
    if not isinstance(result, (int, float)):
        raise ValueError(f"missing {metric} in {row['case_id']}")
    return float(result)


def ladder_review(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {(row["rays_per_point"], row["rng_seed"]): row for row in rows}
    levels = []
    previous = None
    for rays in RAY_LEVELS:
        current = [row for row in rows if row["rays_per_point"] == rays]
        entry: dict[str, Any] = {
            "rays_per_point": rays,
            "run_count": len(current),
            "latency_s": stats([float(row["elapsed_s"]) for row in current]),
            "between_seed_spread": {
                metric: stats([value(row, metric) for row in current])
                for metric in METRICS
            },
            "change_from_previous_level": None,
        }
        if previous is not None:
            paired = {}
            for metric in METRICS:
                changes = [
                    abs(
                        value(by_key[(rays, seed)], metric)
                        - value(by_key[(previous, seed)], metric)
                    )
                    for seed in range(53_000, 53_008)
                ]
                paired[metric] = stats(changes)
            entry["change_from_previous_level"] = {
                "from_rays": previous,
                "to_rays": rays,
                "paired_absolute_change": paired,
                "ratio_of_median_latencies": (
                    entry["latency_s"]["median"] / levels[-1]["latency_s"]["median"]
                ),
            }
        levels.append(entry)
        previous = rays
    return {
        "id": "same_recipe_ray_ladder",
        "scope": "One 2D Bosch recipe at grid 0.01 with eight matched seed labels.",
        "comparison_type": "Successive ray refinement; no level is treated as truth.",
        "levels": levels,
        "limits": [
            "The ladder does not contain 500 rays.",
            "Base seed labels are paired; pointwise common random numbers are not claimed.",
            "Between-seed spread and paired ray-count movement are different quantities.",
            "This single recipe does not establish behavior for every geometry.",
        ],
        "citations": [
            citation(
                ROWS,
                "design=ray_convergence; grid_delta=0.01; rng_seed=53000..53007",
                [
                    line_number
                    for line_number, line in enumerate(ROWS.read_text().splitlines(), 1)
                    if line.strip() and json.loads(line)["design"] == "ray_convergence"
                ],
            )
        ],
    }


def phase_b_review(document: dict[str, Any]) -> dict[str, Any]:
    comparisons = document["comparisons"]
    metrics = {
        "depth": [row["absolute_deltas"]["depth"] for row in comparisons],
        "largest_sampled_cd": [
            max(
                row["absolute_deltas"][name]
                for name in ("cd_top", "cd_middle", "cd_bottom", "cd_min", "cd_max")
            )
            for row in comparisons
        ],
        "max_bow": [row["absolute_deltas"]["max_bow"] for row in comparisons],
    }
    latency = {
        arm: stats([row["runtime_s"][arm] for row in comparisons])
        for arm in ("500", "2000")
    }
    return {
        "id": "diverse_500_to_2000_pairs",
        "scope": "Thirteen 2D Bosch pairs at grid 0.005 across five profile roles.",
        "comparison_type": (
            "All configured inputs except ray count match within each pair. Matching "
            "seed labels do not imply identical particle histories; neither arm is truth."
        ),
        "pair_count": len(comparisons),
        "latency_s": latency,
        "paired_absolute_change": {
            metric: stats(values) for metric, values in metrics.items()
        },
        "complete_measurement_pairs": sum(
            all(row["states"][arm] == "complete_measured" for arm in ("500", "2000"))
            for row in comparisons
        ),
        "selected_cycle_match_count": sum(
            row["measurements"]["500"]["selected_cycle"]
            == row["measurements"]["2000"]["selected_cycle"]
            for row in comparisons
        ),
        "limits": [
            "Only two ray levels were sampled in this panel.",
            "Runtime came from two concurrent workers and is descriptive.",
            "The former assumed-band decision is not used as a fidelity limit here.",
        ],
        "citations": [citation(PHASE_B, "/comparisons")],
    }


def factor_direction_review(document: dict[str, Any]) -> dict[str, Any]:
    gates = document["gate_comparison"]
    return {
        "id": "commissioning_factor_direction_check",
        "scope": "Six Bosch factors with 13 low/high or nominal anchors.",
        "candidate_rays": document["candidate_rays_per_point"],
        "comparison_rays": document["reference_rays_per_point"],
        "factor_ranking_spearman": document["factor_score_ranking_spearman"],
        "broad_outcome_matches": sum(row["match"] for row in gates),
        "trajectory_matches": sum(row["trajectory_match"] for row in gates),
        "anchor_count": len(gates),
        "median_descriptive_speedup": document["runtime"]["median_speedup"],
        "limit": (
            "Commissioning evidence only: ray count, random streams, and early-stop "
            "intervals were not isolated."
        ),
        "citations": [
            citation(CHEAP, "/gate_comparison"),
            citation(CHEAP, "/factor_score_ranking_spearman"),
            citation(CHEAP, "/runtime"),
        ],
    }


def build() -> dict[str, Any]:
    phase_b = json.loads(PHASE_B.read_text())
    cheap = json.loads(CHEAP.read_text())
    return {
        "schema_version": 1,
        "title": "Selected evidence on the benefit and cost of more Bosch rays",
        "status": "reviewed_selected_saved_evidence",
        "question": (
            "How do latency, between-seed spread, paired response movement, and "
            "factor-direction stability change as rays increase?"
        ),
        "interpretation_rules": [
            "No ray count is ground truth.",
            "No fabrication or product limit is used.",
            "Raw response movement is reported in model units.",
            "Different grids and geometry panels are not merged into one curve.",
            "More rays are useful only when the added cost changes a decision or materially stabilizes a needed response.",
        ],
        "datasets": [
            ladder_review(load_rows()),
            phase_b_review(phase_b),
            factor_direction_review(cheap),
        ],
        "excluded_studies": [
            "The current Phase A 250-to-500 panel is not included because only ten pairs returned complete measurements.",
            "The earlier fine-grid 1,000-to-2,000 bridge is not included because it used a different grid, extractor scope, and hard-coded limits.",
            "The partial clean 250/375/500/750 ladder is not included because it has only two cases at 750 rays and no 1,000- or 2,000-ray arm.",
            "The 125- and 250-ray qualification reviews are not included because they belong to a confounded commissioning comparison.",
        ],
        "highest_supported_claim": (
            "Saved results show a substantial runtime cost for added rays, no "
            "monotonic reduction in between-seed spread on the single-profile "
            "ladder, and geometry-dependent paired movement between 500 and 2,000 "
            "rays. Commissioning data preserved broad factor ordering at 500 rays, "
            "but a current-grid multi-level ladder is still missing."
        ),
        "next_evidence": (
            "Before running a current-grid ladder, freeze response-specific useful-change "
            "and repeat-spread criteria. Examine successive levels without assuming "
            "monotonic improvement, and do not declare a plateau from one adjacent comparison."
        ),
        "provenance": {
            "builder": citation(BUILDER, "source file"),
            "schema": citation(SCHEMA, "schema file"),
        },
        "sources": [
            citation(ROWS, "all ray-convergence rows"),
            citation(PHASE_B, "/comparisons"),
            citation(CHEAP, "/gate_comparison"),
        ],
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()

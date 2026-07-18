"""Compare the 500-ray Bosch discovery screen with preserved 2,000-ray anchors."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import build_v3_bosch_cheap_qualification as build
import foundation_pattern_bosch_gate0 as gate0


ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / "autoresearch-results/restart_audit/v3_pattern_bosch_stage2a_rows.jsonl"
CHEAP = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_qualification_rows.jsonl"
REFERENCE_SUMMARY = ROOT / "autoresearch-results/restart_audit/v3_pattern_bosch_stage2a_summary.json"
OUTPUT_JSON = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_qualification_review.json"
OUTPUT_MD = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_qualification_review.md"

METRICS = (
    "depth",
    "selected_cycle",
    "cd_top",
    "cd_middle",
    "cd_bottom",
    "max_cd_error",
    "max_bow",
    "scallop_rms",
    "sidewall_angle_deg",
)
SUMMARY_KEYS = {
    "depth": "etch_depth",
    "selected_cycle": "selected_cycle",
    "cd_top": "etch_cd_top",
    "cd_middle": "etch_cd_middle",
    "cd_bottom": "etch_cd_bottom",
    "max_cd_error": "etch_max_cd_error",
    "max_bow": "etch_max_bow",
    "scallop_rms": "etch_scallop_rms",
    "sidewall_angle_deg": "etch_sidewall_angle_deg",
}
MORPHOLOGY = set(METRICS) - {"depth", "selected_cycle"}


def load_rows(path):
    return [
        gate0.strict_json_loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def reason_map(rows):
    result = {}
    for row in rows:
        for reason in row.get("anchor_reasons", []):
            if reason == "nominal" or reason.startswith("ofat:"):
                result[reason] = row
    return result


def metric(row, name):
    if name == "selected_cycle":
        return float(row["selected_cycle"])
    return float(row["selected_cycle_metrics"]["etch"][name])


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def average_ranks(values):
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + end - 1)
        start = end
    return ranks


def spearman(first, second):
    if len(first) < 3:
        return None
    first = average_ranks(first)
    second = average_ranks(second)
    if np.std(first) == 0 or np.std(second) == 0:
        return None
    return float(np.corrcoef(first, second)[0, 1])


def build_review(
    candidate_path=CHEAP,
    candidate_rays=500,
    campaign="v3-bosch-cheap-qualification",
    campaign_wall_hours=(3 * 3600 + 20 * 60 + 21) / 3600,
):
    reference_rows = load_rows(REFERENCE)
    cheap_rows = load_rows(candidate_path)
    if len(cheap_rows) != 16 or any(row.get("ok") is not True for row in cheap_rows):
        raise ValueError("cheap qualification is incomplete or contains a failed execution")
    reference = reason_map(reference_rows)
    cheap = reason_map(cheap_rows)
    required = {"nominal"} | {
        f"ofat:{factor}:{level}"
        for factor in build.PROMOTED
        for level in ("low", "high")
    }
    if not required <= reference.keys() or not required <= cheap.keys():
        raise ValueError("reference or cheap anchor set is incomplete")

    stage2a_summary = gate0.strict_json_loads(REFERENCE_SUMMARY.read_text())
    thresholds = {
        metric_name: stage2a_summary["effective_screen_thresholds"][summary_name][
            "effective_threshold"
        ]
        for metric_name, summary_name in SUMMARY_KEYS.items()
    }

    gate_rows = []
    for reason in sorted(required):
        ref = reference[reason]
        low = cheap[reason]
        gate_rows.append({
            "anchor": reason,
            "reference_pass": ref["hard_gate_pass"],
            "cheap_pass": low["hard_gate_pass"],
            "match": ref["hard_gate_pass"] == low["hard_gate_pass"],
            "reference_trajectory": ref["trajectory_classification"],
            "cheap_trajectory": low["trajectory_classification"],
            "trajectory_match": (
                ref["trajectory_classification"] == low["trajectory_classification"]
            ),
        })

    effects = {}
    strong_direction_checks = []
    factor_scores = {"reference": {}, "cheap": {}}
    for factor in build.PROMOTED:
        ref_low = reference[f"ofat:{factor}:low"]
        ref_high = reference[f"ofat:{factor}:high"]
        cheap_low = cheap[f"ofat:{factor}:low"]
        cheap_high = cheap[f"ofat:{factor}:high"]
        effects[factor] = {}
        scores = {"reference": [], "cheap": []}
        for name in METRICS:
            morphology_eligible = not (
                name in MORPHOLOGY
                and not (
                    ref_low["gates"]["etch_depth"]
                    and ref_high["gates"]["etch_depth"]
                    and cheap_low["gates"]["etch_depth"]
                    and cheap_high["gates"]["etch_depth"]
                )
            )
            if not morphology_eligible:
                effects[factor][name] = {"status": "excluded_not_depth_matched"}
                continue
            ref_effect = metric(ref_high, name) - metric(ref_low, name)
            cheap_effect = metric(cheap_high, name) - metric(cheap_low, name)
            threshold = thresholds[name]
            ref_ratio = abs(ref_effect) / threshold
            cheap_ratio = abs(cheap_effect) / threshold
            direction_match = bool(
                ref_effect == 0.0
                or cheap_effect == 0.0
                or math.copysign(1.0, ref_effect) == math.copysign(1.0, cheap_effect)
            )
            effects[factor][name] = {
                "reference_high_minus_low": ref_effect,
                "cheap_high_minus_low": cheap_effect,
                "reference_effect_over_threshold": ref_ratio,
                "cheap_effect_over_threshold": cheap_ratio,
                "direction_match": direction_match,
            }
            scores["reference"].append(ref_ratio)
            scores["cheap"].append(cheap_ratio)
            if ref_ratio >= 1.0:
                strong_direction_checks.append({
                    "factor": factor,
                    "metric": name,
                    "reference_effect_over_threshold": ref_ratio,
                    "cheap_effect_over_threshold": cheap_ratio,
                    "direction_match": direction_match,
                    "cheap_remains_screen_positive": cheap_ratio >= 1.0,
                })
        for fidelity in ("reference", "cheap"):
            factor_scores[fidelity][factor] = max(scores[fidelity], default=0.0)

    reference_scores = [factor_scores["reference"][name] for name in build.PROMOTED]
    cheap_scores = [factor_scores["cheap"][name] for name in build.PROMOTED]
    ranking_spearman = spearman(reference_scores, cheap_scores)

    centers = [
        row for row in cheap_rows
        if row.get("anchor_reasons") == ["nominal"]
        or any(reason.startswith("cheap_center_repeat:") for reason in row["anchor_reasons"])
    ]
    center_summary = {}
    for name in METRICS:
        values = [metric(row, name) for row in centers]
        center_summary[name] = {
            "count": len(values),
            "mean": float(np.mean(values)),
            "sample_sd": float(np.std(values, ddof=1)),
            "minimum": min(values),
            "maximum": max(values),
            "range": max(values) - min(values),
            "reference_effective_threshold": thresholds[name],
        }

    paired_elapsed = []
    for reason in sorted(required):
        paired_elapsed.append({
            "anchor": reason,
            "reference_seconds": reference[reason]["elapsed_s"],
            "cheap_seconds": cheap[reason]["elapsed_s"],
            "speedup": reference[reason]["elapsed_s"] / cheap[reason]["elapsed_s"],
        })
    median_speedup = float(np.median([row["speedup"] for row in paired_elapsed]))

    all_gate_match = all(row["match"] for row in gate_rows)
    all_trajectory_match = all(row["trajectory_match"] for row in gate_rows)
    all_strong_directions_match = all(
        row["direction_match"] for row in strong_direction_checks
    )
    retained_factors = {
        factor: any(
            row["factor"] == factor and row["cheap_remains_screen_positive"]
            for row in strong_direction_checks
        )
        for factor in build.PROMOTED
    }
    all_factors_retained = all(retained_factors.values())
    ranking_pass = finite(ranking_spearman) and ranking_spearman >= 0.8
    center_gate_pass = all(row["hard_gate_pass"] for row in centers)
    passed = bool(
        all_gate_match
        and all_trajectory_match
        and all_strong_directions_match
        and all_factors_retained
        and ranking_pass
        and center_gate_pass
    )
    return {
        "campaign": campaign,
        "labels": ["full-traveler", "critical-review"],
        "reference_rays_per_point": 2000,
        "candidate_rays_per_point": candidate_rays,
        "reference_anchor_count": len(required),
        "cheap_case_count": len(cheap_rows),
        "gate_comparison": gate_rows,
        "effect_comparison": effects,
        "strong_effect_checks": strong_direction_checks,
        "factor_scores": factor_scores,
        "factor_score_ranking_spearman": ranking_spearman,
        "retained_promoted_factors": retained_factors,
        "cheap_center_repeats": center_summary,
        "runtime": {
            "paired_anchors": paired_elapsed,
            "median_speedup": median_speedup,
            "campaign_wall_hours": campaign_wall_hours,
        },
        "decision": {
            "classification": (
                "qualified_for_broad_interaction_discovery" if passed
                else "rejected_for_broad_interaction_discovery"
            ),
            "pass": passed,
            "all_anchor_gate_decisions_match": all_gate_match,
            "all_anchor_trajectory_classes_match": all_trajectory_match,
            "all_reference_strong_effect_directions_match": all_strong_directions_match,
            "all_promoted_factors_retained": all_factors_retained,
            "factor_ranking_spearman_at_least_0_8": ranking_pass,
            "all_cheap_centers_pass": center_gate_pass,
            "authority": "broad interaction hypothesis discovery only",
            "confirmation_rays_per_point": 2000,
        },
    }


def markdown(review):
    decision = review["decision"]
    candidate_rays = review["candidate_rays_per_point"]
    lines = [
        "# V3 Bosch cheap-screen qualification review",
        "",
        f"Decision: **{decision['classification']}**.",
        "",
        f"The {candidate_rays}-ray mode is evaluated only as a broad interaction-discovery tool. "
        "It does not inherit product-gate, recipe, process-window, or confirmation authority.",
        "",
        "## Acceptance checks",
        "",
        f"- Anchor gate decisions match: {decision['all_anchor_gate_decisions_match']}",
        f"- Trajectory classes match: {decision['all_anchor_trajectory_classes_match']}",
        f"- Strong-effect directions match: {decision['all_reference_strong_effect_directions_match']}",
        f"- All promoted factors retained: {decision['all_promoted_factors_retained']}",
        f"- Factor-ranking Spearman: {review['factor_score_ranking_spearman']:.3f}",
        f"- All four cheap nominal centers pass: {decision['all_cheap_centers_pass']}",
        f"- Median paired runtime speedup: {review['runtime']['median_speedup']:.2f}x",
        "",
        "## Factor ranking",
        "",
        f"| Factor | 2,000-ray score | {candidate_rays}-ray score | Retained |",
        "|---|---:|---:|---|",
    ]
    for factor in build.PROMOTED:
        lines.append(
            f"| {factor} | {review['factor_scores']['reference'][factor]:.2f} | "
            f"{review['factor_scores']['cheap'][factor]:.2f} | "
            f"{review['retained_promoted_factors'][factor]} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "Passing this bridge means the cheaper mode is adequate to locate large "
        "interaction signals and failure regions. Every promoted interaction, "
        "boundary, and finalist must still be rerun at 2,000 rays with independent "
        "seeds before it becomes a process conclusion.",
        "",
    ])
    return "\n".join(lines)


def main():
    review = build_review()
    OUTPUT_JSON.write_text(json.dumps(review, indent=2, sort_keys=True, allow_nan=False) + "\n")
    OUTPUT_MD.write_text(markdown(review))
    print(json.dumps({
        "classification": review["decision"]["classification"],
        "pass": review["decision"]["pass"],
        "ranking_spearman": review["factor_score_ranking_spearman"],
        "median_speedup": review["runtime"]["median_speedup"],
        "strong_effect_checks": len(review["strong_effect_checks"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

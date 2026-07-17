"""Critical review of the seven exact 500-ray Bosch interaction blocks."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import build_v3_bosch_cheap_interactions as build
import foundation_pattern_bosch_gate0 as gate0


ROOT = Path(__file__).resolve().parent
ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_interactions_rows.jsonl"
STAGE2A = ROOT / "autoresearch-results/restart_audit/v3_pattern_bosch_stage2a_summary.json"
OUTPUT_JSON = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_interactions_review.json"
OUTPUT_MD = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_interactions_review.md"
METRICS = {
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


def load_rows():
    return [
        gate0.strict_json_loads(line)
        for line in ROWS.read_text().splitlines()
        if line.strip()
    ]


def metric(row, name):
    if name == "selected_cycle":
        return float(row["selected_cycle"])
    return float(row["selected_cycle_metrics"]["etch"][name])


def block_key(row):
    reason = row["anchor_reasons"][0].split(":")
    if len(reason) != 5 or reason[0] != "interaction":
        raise ValueError(f"invalid interaction reason: {row['anchor_reasons']}")
    return (reason[1], reason[2]), (reason[3], reason[4])


def build_review():
    rows = load_rows()
    if len(rows) != 28 or any(row.get("ok") is not True for row in rows):
        raise ValueError("interaction campaign is incomplete or invalid")
    grouped = defaultdict(dict)
    for row in rows:
        pair, corner = block_key(row)
        if corner in grouped[pair]:
            raise ValueError(f"duplicate interaction corner: {pair} {corner}")
        grouped[pair][corner] = row
    if set(grouped) != set(build.INTERACTIONS):
        raise ValueError("interaction blocks differ from the frozen declaration")

    summary = gate0.strict_json_loads(STAGE2A.read_text())
    base_thresholds = {
        name: summary["effective_screen_thresholds"][source]["effective_threshold"]
        for name, source in METRICS.items()
    }
    blocks = []
    for pair in build.INTERACTIONS:
        corners = grouped[pair]
        required = {
            ("low", "low"), ("low", "high"),
            ("high", "low"), ("high", "high"),
        }
        if set(corners) != required:
            raise ValueError(f"incomplete block: {pair}")
        pass_corners = [
            f"{first}:{second}"
            for (first, second), row in corners.items()
            if row["hard_gate_pass"]
        ]
        contrasts = {}
        for name in METRICS:
            eligible = not (
                name in MORPHOLOGY
                and not all(row["gates"]["etch_depth"] for row in corners.values())
            )
            ll = metric(corners[("low", "low")], name)
            lh = metric(corners[("low", "high")], name)
            hl = metric(corners[("high", "low")], name)
            hh = metric(corners[("high", "high")], name)
            contrast = hh - hl - lh + ll
            threshold = math.sqrt(2.0) * base_thresholds[name]
            contrasts[name] = {
                "difference_of_differences": contrast,
                "interaction_threshold": threshold,
                "absolute_contrast_over_threshold": abs(contrast) / threshold,
                "depth_matched_morphology_eligible": eligible,
                "screen_positive": eligible and abs(contrast) >= threshold,
            }
        passing_rows = [row for row in corners.values() if row["hard_gate_pass"]]
        best_pass = min(
            passing_rows,
            key=lambda row: (
                row["selected_cycle_metrics"]["etch"]["max_cd_error"],
                row["selected_cycle_metrics"]["etch"]["max_bow"],
            ),
            default=None,
        )
        blocks.append({
            "factors": list(pair),
            "pass_count": len(pass_corners),
            "pass_corners": sorted(pass_corners),
            "gate_pattern": (
                "no_extreme_corner_feasible" if not pass_corners
                else "crossed_pair_only" if set(pass_corners) == {"high:low", "low:high"}
                else "one_corner_feasible" if len(pass_corners) == 1
                else "multiple_corners_feasible"
            ),
            "contrasts": contrasts,
            "best_passing_corner": None if best_pass is None else {
                "anchor": best_pass["anchor_reasons"][0],
                "recipe": best_pass["recipe"],
                "depth": metric(best_pass, "depth"),
                "max_cd_error": metric(best_pass, "max_cd_error"),
                "max_bow": metric(best_pass, "max_bow"),
                "selected_cycle": best_pass["selected_cycle"],
                "checkpoint_path": best_pass["checkpoint_path"],
            },
        })

    passing = [row for row in rows if row["hard_gate_pass"]]
    passing_sorted = sorted(
        passing,
        key=lambda row: (
            row["selected_cycle_metrics"]["etch"]["max_cd_error"],
            row["selected_cycle_metrics"]["etch"]["max_bow"],
        ),
    )
    return {
        "campaign": "v3-bosch-cheap-interactions",
        "labels": ["full-traveler", "critical-review"],
        "valid_case_count": len(rows),
        "hard_gate_pass_count": len(passing),
        "interaction_threshold_policy": (
            "sqrt(2) times the independent two-row effect threshold because a "
            "four-row difference-of-differences has twice the contrast variance; "
            "morphology contrasts require all four corners depth-matched"
        ),
        "blocks": blocks,
        "passing_corners_ranked": [
            {
                "anchor": row["anchor_reasons"][0],
                "recipe": row["recipe"],
                "depth": metric(row, "depth"),
                "max_cd_error": metric(row, "max_cd_error"),
                "max_bow": metric(row, "max_bow"),
                "selected_cycle": row["selected_cycle"],
                "checkpoint_path": row["checkpoint_path"],
            }
            for row in passing_sorted
        ],
        "decision": {
            "classification": "interaction_discovery_complete_refinement_required",
            "interaction_discovery_complete": True,
            "recipe_authorized": False,
            "process_window_authorized": False,
            "full_traveler_authorized": False,
            "next_required_evidence": (
                "interior reduced response surface followed by 2,000-ray independent confirmation"
            ),
        },
    }


def markdown(review):
    lines = [
        "# V3 Bosch interaction review",
        "",
        f"All {review['valid_case_count']} exact interaction corners are valid; "
        f"{review['hard_gate_pass_count']} pass the Bosch hard gates.",
        "",
        "These are 500-ray discovery results. They locate coupled failure regions but "
        "do not authorize a recipe or process window.",
        "",
        "| Interaction | Passing corners | Gate interpretation | Strong eligible contrasts |",
        "|---|---|---|---|",
    ]
    for block in review["blocks"]:
        strong = [
            name for name, result in block["contrasts"].items()
            if result["screen_positive"]
        ]
        lines.append(
            f"| {' × '.join(block['factors'])} | "
            f"{', '.join(block['pass_corners']) or 'none'} | "
            f"{block['gate_pattern']} | {', '.join(strong) or 'none'} |"
        )
    lines.extend([
        "",
        "## Engineering read",
        "",
        "- Etch time and passivation thickness have no feasible extreme corner; refine inward.",
        "- Low etch time can be rescued by stronger ion or neutral removal, proving compensation.",
        "- Neutral rate and neutral sticking pass at crossed settings but fail together at matching extremes.",
        "- Lower-magnitude ion removal passes at both tested ion-directionality extremes; aggressive removal causes profile failures.",
        "- Thick passivation remains a reachability failure even with stronger ion directionality.",
        "",
        "## Next decision",
        "",
        "Fit and sample the interior region around the nominal settings. Do not spend "
        "more runs on the already-rejected extreme corners. Confirm only the promoted "
        "interior candidates at 2,000 rays with independent seeds.",
        "",
    ])
    return "\n".join(lines)


def main():
    review = build_review()
    OUTPUT_JSON.write_text(json.dumps(review, indent=2, sort_keys=True, allow_nan=False) + "\n")
    OUTPUT_MD.write_text(markdown(review))
    print(json.dumps({
        "classification": review["decision"]["classification"],
        "valid": review["valid_case_count"],
        "passing": review["hard_gate_pass_count"],
        "screen_positive_contrasts": sum(
            result["screen_positive"]
            for block in review["blocks"]
            for result in block["contrasts"].values()
        ),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

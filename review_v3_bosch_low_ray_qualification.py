"""Review 125/250-ray Bosch discovery modes against saved 2,000-ray anchors."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import review_v3_bosch_cheap_qualification as review_tools
import v3_bosch_low_ray_qualification as low_ray


ROOT = Path(__file__).resolve().parent
OUTPUT_JSON = ROOT / "autoresearch-results/restart_audit/v3_bosch_low_ray_qualification_review.json"
OUTPUT_MD = ROOT / "autoresearch-results/restart_audit/v3_bosch_low_ray_qualification_review.md"


def source(path):
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def review_candidate(rays):
    path = ROOT / low_ray.rows_path(rays)
    rows = review_tools.load_rows(path)
    expected = 16
    if len(rows) != expected:
        return {
            "candidate_rays_per_point": rays,
            "cheap_case_count": len(rows),
            "expected_case_count": expected,
            "decision": {
                "classification": "partial_not_formally_reviewable",
                "pass": False,
                "authority": "none",
            },
            "study_limit": "No frozen stop event authorizes a formal decision from a partial matrix.",
        }
    worker_hours = sum(row["elapsed_s"] for row in rows) / 2 / 3600
    review = review_tools.build_review(
        candidate_path=path,
        candidate_rays=rays,
        campaign=f"v3-bosch-r{rays}-qualification",
        campaign_wall_hours=worker_hours,
    )
    review["study_limit"] = (
        "Commissioning evidence only: ray count, random streams, and early-stop "
        "intervals were not isolated. A passing saved review does not qualify the mode."
    )
    return review


def markdown(result):
    lines = [
        "# V3 Bosch low-ray qualification",
        "",
        "These modes are evaluated for discovery only. Boundaries, finalists, and "
        "process conclusions still require 2,000-ray confirmation.",
        "",
        "| Rays | Decision | Gate match | Trajectory match | Ranking Spearman | Median speedup |",
        "|---:|---|---|---|---:|---:|",
    ]
    for rays in low_ray.RAY_COUNTS:
        review = result["candidates"][str(rays)]
        decision = review["decision"]
        if review.get("cheap_case_count") != 16:
            lines.append(
                f"| {rays} | {decision['classification']} | n/a | n/a | n/a | n/a |"
            )
            continue
        lines.append(
            f"| {rays} | {decision['classification']} | "
            f"{decision['all_anchor_gate_decisions_match']} | "
            f"{decision['all_anchor_trajectory_classes_match']} | "
            f"{review['factor_score_ranking_spearman']:.3f} | "
            f"{review['runtime']['median_speedup']:.2f}x |"
        )
    lines.extend([
        "",
        f"Provisional discovery floor: **{result['provisional_discovery_rays']} rays per point**.",
        "",
        "No low-ray mode is formally qualified by this commissioning design because it changes more than ray count.",
        "",
    ])
    return "\n".join(lines)


def main():
    candidates = {str(rays): review_candidate(rays) for rays in low_ray.RAY_COUNTS}
    passing = [
        rays for rays in low_ray.RAY_COUNTS
        if candidates[str(rays)]["decision"]["pass"]
    ]
    result = {
        "campaign": "v3-bosch-low-ray-qualification",
        "labels": ["full-traveler", "critical-review"],
        "candidates": candidates,
        "provisional_discovery_rays": min(passing) if passing else 500,
        "formally_qualified_discovery_rays": None,
        "confirmation_rays_per_point": 2000,
        "provenance": {
            "reviewer": source(Path(__file__).resolve()),
            "commissioning_runner": source(ROOT / "v3_bosch_low_ray_qualification.py"),
            "candidate_manifests": {
                str(rays): source(low_ray.manifest_path(rays))
                for rays in low_ray.RAY_COUNTS
            },
        },
        "recipe_authorized": False,
        "process_window_authorized": False,
    }
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    OUTPUT_MD.write_text(markdown(result))
    print(json.dumps({
        "provisional_discovery_rays": result["provisional_discovery_rays"],
        "formally_qualified_discovery_rays": None,
        "decisions": {
            rays: review["decision"]["classification"]
            for rays, review in candidates.items()
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()

"""Review the clean Bosch ray-count ladder."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import v3_bosch_clean_ray_ladder as ladder


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "autoresearch-results/restart_audit/v3_bosch_clean_ray_ladder_review.json"
REPORT = ROOT / "autoresearch-results/restart_audit/v3_bosch_clean_ray_ladder_review.md"
LIMITS = {
    "depth": 0.02,
    "cd_top": 0.01,
    "cd_middle": 0.01,
    "cd_bottom": 0.01,
    "max_cd_error": 0.01,
    "max_bow": 0.005,
    "scallop_rms": 0.0025,
    "sidewall_angle_deg": 0.5,
    "selected_cycle": 1,
    "mask_remaining_height": 0.01,
}


def load_rows(rays: int) -> list[dict]:
    path = ROOT / ladder.rows_path(rays)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def anchor(row: dict) -> str:
    matches = [value for value in row["anchor_reasons"] if value in ladder.ANCHORS]
    if len(matches) != 1:
        raise ValueError(f"row {row.get('case_id')} has no unique sentinel anchor")
    return matches[0]


def metric(row: dict, name: str) -> float:
    if name == "selected_cycle":
        return float(row["selected_cycle"])
    if name == "mask_remaining_height":
        return float(row["selected_cycle_metrics"]["mask_remaining_height"])
    return float(row["selected_cycle_metrics"]["etch"][name])


def compare(candidate: dict, reference: dict) -> dict:
    deltas = {
        name: abs(metric(candidate, name) - metric(reference, name))
        for name in LIMITS
    }
    return {
        "anchor": anchor(candidate),
        "gate_match": candidate["hard_gate_pass"] == reference["hard_gate_pass"],
        "trajectory_match": (
            candidate["trajectory_classification"]
            == reference["trajectory_classification"]
        ),
        "deltas": deltas,
        "within_limits": {
            name: value <= LIMITS[name] for name, value in deltas.items()
        },
    }


def review() -> dict:
    rows = {rays: load_rows(rays) for rays in ladder.RAY_COUNTS}
    counts = {str(rays): len(values) for rays, values in rows.items()}
    expected = len(ladder.ANCHORS)
    if len(rows[2000]) != expected:
        return {
            "campaign": "v3-bosch-clean-ray-ladder",
            "status": "running",
            "counts": counts,
            "expected_per_arm": expected,
            "decision": None,
        }

    reference = {anchor(row): row for row in rows[2000]}
    candidates = {}
    for rays in ladder.RAY_COUNTS[:-1]:
        if len(rows[rays]) != expected:
            candidates[str(rays)] = {"status": "incomplete", "rows": len(rows[rays])}
            continue
        comparisons = [compare(row, reference[anchor(row)]) for row in rows[rays]]
        accepted = all(
            comparison["gate_match"]
            and comparison["trajectory_match"]
            and all(comparison["within_limits"].values())
            for comparison in comparisons
        )
        candidates[str(rays)] = {
            "status": "accepted_for_discovery" if accepted else "rejected",
            "comparisons": comparisons,
            "median_runtime_s": statistics.median(row["elapsed_s"] for row in rows[rays]),
            "median_speedup_vs_2000": statistics.median(
                reference[anchor(row)]["elapsed_s"] / row["elapsed_s"]
                for row in rows[rays]
            ),
        }
    survivors = [
        int(rays)
        for rays, result in candidates.items()
        if result["status"] == "accepted_for_discovery"
    ]
    return {
        "campaign": "v3-bosch-clean-ray-ladder",
        "status": "complete",
        "counts": counts,
        "expected_per_arm": expected,
        "limits": LIMITS,
        "candidates": candidates,
        "decision": {
            "selected_discovery_rays_per_point": min(survivors) if survivors else None,
            "reference_rays_per_point": 2000,
            "authority": "Bosch discovery setting only",
            "boundaries_and_finalists_require_reference": True,
        },
    }


def main() -> None:
    result = review()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    selected = (result.get("decision") or {}).get("selected_discovery_rays_per_point")
    lines = [
        "# Clean Bosch ray-count review",
        "",
        f"Status: **{result['status']}**.",
        "",
        f"Completed rows by arm: {result['counts']}.",
    ]
    if result["status"] == "complete":
        lines.extend(
            [
                "",
                f"Selected discovery setting: **{selected if selected is not None else 'none'}**.",
                "",
                "This decision applies only to broad Bosch discovery. Boundaries and finalists remain at 2,000 rays.",
            ]
        )
    REPORT.write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": result["status"], "selected": selected}, sort_keys=True))


if __name__ == "__main__":
    main()

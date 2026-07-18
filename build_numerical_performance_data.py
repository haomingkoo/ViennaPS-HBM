"""Build chart data for numerical cost and sensitivity."""

from __future__ import annotations

import json
import hashlib
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / "evidence" / "numerical"
OUTPUT = ROOT / "numerical_performance_data.json"

FOUNDATION_ROW_FILES = (
    AUDIT / "metric_convergence_rows.jsonl",
    AUDIT / "grid_extension_rows.jsonl",
)
FOUNDATION_SUMMARY = AUDIT / "metric_convergence_summary.json"
V3_REFERENCE_ROWS = AUDIT / "v3_pattern_bosch_stage2a_rows.jsonl"
V3_REFERENCE_SUMMARY = AUDIT / "v3_pattern_bosch_stage2a_summary.json"
V3_CHEAP_REVIEW = AUDIT / "v3_bosch_cheap_qualification_review.json"
V3_RAY_ROWS = {
    125: AUDIT / "v3_bosch_r125_qualification_rows.jsonl",
    250: AUDIT / "v3_bosch_r250_qualification_rows.jsonl",
    500: AUDIT / "v3_bosch_cheap_qualification_rows.jsonl",
    2000: V3_REFERENCE_ROWS,
}

METRICS = {
    "depth": "etch_depth",
    "cd_bottom": "etch_cd_bottom",
    "max_bow": "etch_max_bow",
    "scallop_rms": "etch_scallop_rms",
}


def load(path: Path):
    return json.loads(path.read_text())


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def citation(path: Path, selector: str, line_numbers=None):
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "selector": selector,
        "line_numbers": line_numbers,
    }


def matching_lines(path: Path, predicate):
    return [
        line_number
        for line_number, line in enumerate(path.read_text().splitlines(), 1)
        if line.strip() and predicate(json.loads(line))
    ]


def load_rows(path: Path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def foundation_metric(row, name):
    return float(row["etch"][name])


def foundation_points(rows, summary, axis):
    key = "grid_delta" if axis == "grid" else "rays_per_point"
    design = "grid" if axis == "grid" else "ray_convergence"
    groups = summary[f"{axis}_groups"]
    points = []
    for value in sorted(groups, key=float):
        group_rows = [
            row for row in rows
            if row["design"].startswith(design) and float(row[key]) == float(value)
        ]
        points.append({
            "value": float(value) if axis == "grid" else int(float(value)),
            "runs": len(group_rows),
            "median_runtime_s": statistics.median(
                row["elapsed_s"] for row in group_rows
            ),
            "responses": {
                public: groups[value]["metrics"][source]
                for public, source in METRICS.items()
            },
            "passes": groups[value]["passes"],
            "citations": [
                citation(
                    FOUNDATION_SUMMARY,
                    f"/{axis}_groups/{value}",
                ),
                *[
                    citation(
                        path,
                        f"design starts with {design}; {key}={value}",
                        matching_lines(
                            path,
                            lambda row: row["design"].startswith(design)
                            and float(row[key]) == float(value),
                        ),
                    )
                    for path in FOUNDATION_ROW_FILES
                    if any(
                        row["design"].startswith(design)
                        and float(row[key]) == float(value)
                        for row in load_rows(path)
                    )
                ],
            ],
        })
    return points


def adjacent_changes(rows, axis, noise):
    key = "grid_delta" if axis == "grid" else "rays_per_point"
    design = "grid" if axis == "grid" else "ray_convergence"
    selected = [row for row in rows if row["design"].startswith(design)]
    values = sorted({row[key] for row in selected})
    changes = []
    for lower, upper in zip(values, values[1:]):
        first = {row["rng_seed"]: row for row in selected if row[key] == lower}
        second = {row["rng_seed"]: row for row in selected if row[key] == upper}
        shared = sorted(first.keys() & second.keys())
        responses = {}
        for public, source in METRICS.items():
            deltas = [
                abs(foundation_metric(second[seed], source.removeprefix("etch_"))
                    - foundation_metric(first[seed], source.removeprefix("etch_")))
                for seed in shared
            ]
            responses[public] = {
                "mean_abs_change": statistics.mean(deltas),
                "max_abs_change": max(deltas),
                "mean_abs_change_in_baseline_sd_units": (
                    statistics.mean(deltas) / noise[source]
                ),
            }
        changes.append({
            "from": lower,
            "to": upper,
            "paired_runs": len(shared),
            "responses": responses,
            "citations": [
                citation(
                    path,
                    f"paired rng_seed; design starts with {design}; {key} in [{lower},{upper}]",
                    matching_lines(
                        path,
                        lambda row: row["design"].startswith(design)
                        and float(row[key]) in {float(lower), float(upper)},
                    ),
                )
                for path in FOUNDATION_ROW_FILES
                if matching_lines(
                    path,
                    lambda row: row["design"].startswith(design)
                    and float(row[key]) in {float(lower), float(upper)},
                )
            ],
        })
    return changes


def anchor_reason(row):
    return next((
        reason for reason in row.get("anchor_reasons", [])
        if reason == "nominal" or reason.startswith("ofat:")
    ), None)


def v3_ray_points(reference, thresholds, cheap_review):
    reference_by_reason = {
        anchor_reason(row): row for row in reference if anchor_reason(row)
    }
    points = []
    for rays, path in V3_RAY_ROWS.items():
        rows = load_rows(path)
        comparisons = []
        normalized_changes = []
        paired_speedups = []
        for row in rows:
            reason = anchor_reason(row)
            if reason is None or reason not in reference_by_reason or rays == 2000:
                continue
            ref = reference_by_reason[reason]
            comparisons.append({
                "anchor": reason,
                "gate_match": row["hard_gate_pass"] == ref["hard_gate_pass"],
                "trajectory_match": (
                    row["trajectory_classification"]
                    == ref["trajectory_classification"]
                ),
            })
            paired_speedups.append(ref["elapsed_s"] / row["elapsed_s"])
            for public, source in METRICS.items():
                candidate = row["selected_cycle_metrics"]["etch"][public]
                reference_value = ref["selected_cycle_metrics"]["etch"][public]
                normalized_changes.append(
                    abs(candidate - reference_value) / thresholds[source]
                )
        gate_mismatches = sum(not row["gate_match"] for row in comparisons)
        trajectory_mismatches = sum(
            not row["trajectory_match"] for row in comparisons
        )
        if rays == 500:
            decision = cheap_review["decision"]
            status = (
                "commissioning_discovery_bridge" if decision["pass"]
                else "saved_review_mismatch"
            )
        elif rays == 2000:
            status = "tested_reference"
        elif len(rows) < 16:
            status = (
                "partial_with_mismatch_observed"
                if gate_mismatches or trajectory_mismatches
                else "partial_not_qualified"
            )
        elif gate_mismatches or trajectory_mismatches:
            status = "complete_with_mismatch_observed"
        else:
            status = "complete_awaiting_saved_review"
        points.append({
            "value": rays,
            "runs": len(rows),
            "expected_candidate_runs": 16 if rays != 2000 else None,
            "paired_anchor_median_speedup_vs_2000": (
                statistics.median(paired_speedups) if paired_speedups else None
            ),
            "gate_mismatches": gate_mismatches,
            "trajectory_mismatches": trajectory_mismatches,
            "maximum_change_over_screen_threshold": (
                max(normalized_changes) if normalized_changes else None
            ),
            "status": status,
            "citations": [
                citation(
                    path,
                    f"all saved rows; rays_per_point={rays}",
                    list(range(1, len(rows) + 1)),
                ),
                *(
                    [citation(
                        V3_REFERENCE_ROWS,
                        "matching nominal/ofat anchor_reasons; rays_per_point=2000",
                        matching_lines(
                            V3_REFERENCE_ROWS,
                            lambda row: anchor_reason(row) in {
                                item["anchor"] for item in comparisons
                            },
                        ),
                    )]
                    if comparisons else []
                ),
                *(
                    [citation(V3_CHEAP_REVIEW, "/decision")]
                    if rays == 500 else []
                ),
            ],
        })
    return points


def main():
    required = tuple(dict.fromkeys((
        *FOUNDATION_ROW_FILES,
        FOUNDATION_SUMMARY,
        *V3_RAY_ROWS.values(),
        V3_REFERENCE_SUMMARY,
        V3_CHEAP_REVIEW,
    )))
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required numerical evidence missing: {missing}")
    foundation_rows = [
        row for path in FOUNDATION_ROW_FILES for row in load_rows(path)
    ]
    foundation_summary = load(FOUNDATION_SUMMARY)
    reference = load_rows(V3_REFERENCE_ROWS)
    reference_summary = load(V3_REFERENCE_SUMMARY)
    cheap_review = load(V3_CHEAP_REVIEW)
    noise = {
        name: values["sd"]
        for name, values in foundation_summary["baseline"]["metrics"].items()
    }
    thresholds = {
        name: values["effective_threshold"]
        for name, values in reference_summary["effective_screen_thresholds"].items()
    }
    result = {
        "schema_version": 2,
        "claim_level": "numerically_characterized",
        "purpose": "show cost, noise, and response cliffs for numerical settings",
        "foundation": {
            "scope": "one coarse-grid Pattern/Bosch recipe; not the active V3 qualification",
            "grid": {
                "points": foundation_points(
                    foundation_rows, foundation_summary, "grid"
                ),
                "adjacent_changes": adjacent_changes(
                    foundation_rows, "grid", noise
                ),
            },
            "rays": {
                "points": foundation_points(
                    foundation_rows, foundation_summary, "ray"
                ),
                "adjacent_changes": adjacent_changes(
                    foundation_rows, "ray", noise
                ),
            },
        },
        "v3_ray_qualification": {
            "scope": "active fine-grid 2D Pattern/Bosch discovery qualification",
            "points": v3_ray_points(reference, thresholds, cheap_review),
        },
        "interpretation": {
            "baseline_sd_units": "descriptive mean absolute paired change divided by baseline sample standard deviation; it is not a pass threshold",
            "no_interpolation": True,
            "runtime_boundary": "fine-grid speedups use paired anchors on one research machine; raw medians from different cases are not compared",
        },
        "provenance": {
            "raw_inputs_committed": True,
            "builder": {
                "path": str(Path(__file__).resolve().relative_to(ROOT)),
                "sha256": sha256(Path(__file__).resolve()),
            },
            "inputs": [
                {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
                for path in required
            ],
            "units": {"geometry": "model length", "runtime": "seconds"},
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()

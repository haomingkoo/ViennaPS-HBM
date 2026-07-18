"""Review the completed Bosch grid-speed bridge without rerunning it."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

import foundation_pattern_bosch_gate0 as gate0
import v3_bosch_grid_speed_bridge_runner as runner
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "evidence/numerical/v3_bosch_grid_speed_bridge_manifest.json"
ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_grid_speed_bridge_rows.jsonl"
FOCUSED_ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_focused_ion_map_rows.jsonl"
OUTPUT = ROOT / "evidence/numerical/v3_bosch_grid_speed_bridge_review.json"
METRICS = ("depth", "cd_top", "cd_middle", "cd_bottom", "max_bow", "sidewall_angle_deg", "scallop_rms")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric_values(row):
    etch = row["selected_cycle_metrics"]["etch"]
    values = {name: float(etch[name]) for name in METRICS}
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError("nonfinite bridge measurement")
    return values


def profile_summary(row):
    etch = row["selected_cycle_metrics"]["etch"]
    cds = etch.get("sample_cds")
    fractions = etch.get("sample_fractions")
    widths = {name: etch[name] for name in ("cd_top", "cd_middle", "cd_bottom")}
    return {
        "available": isinstance(cds, list) and isinstance(fractions, list) and len(cds) == len(fractions) and len(cds) > 1,
        "point_count": len(cds) if isinstance(cds, list) else 0,
        "width_order_widest_to_narrowest": sorted(widths, key=widths.get, reverse=True),
    }


def build_review(new_rows, focused_rows, manifest, *, new_rows_path=ROWS):
    references = manifest["design"]["pairs"]
    focused_by_id = {row["case_id"]: row for row in focused_rows}
    repeats = {}
    for cell_id in references:
        exponent, rate = {
            "e50_i0.04": (50, -0.04),
            "e141_i0.06324555": (141, -0.06324555),
        }[cell_id]
        repeats[cell_id] = [
            row for row in focused_rows
            if (row["recipe"]["ion_source_exponent"], row["recipe"]["ion_rate"]) == (exponent, rate)
        ]
    arms = []
    for row in sorted(new_rows, key=lambda current: (current["rng_stream"]["allocation_id"], current["numerics"]["grid_delta"])):
        cell_id = row["rng_stream"]["allocation_id"].removeprefix("grid_bridge_")
        reference = focused_by_id[references[cell_id]["reference_case_id"]]
        current_values = metric_values(row)
        reference_values = metric_values(reference)
        movement = {}
        for metric in METRICS:
            observed = [metric_values(candidate)[metric] for candidate in repeats[cell_id]]
            movement[metric] = {
                "value": current_values[metric],
                "reference_value": reference_values[metric],
                "signed_delta": current_values[metric] - reference_values[metric],
                "absolute_delta": abs(current_values[metric] - reference_values[metric]),
                "fine_repeat_min": min(observed),
                "fine_repeat_max": max(observed),
                "inside_observed_fine_repeat_range": min(observed) <= current_values[metric] <= max(observed),
            }
        arms.append({
            "cell_id": cell_id,
            "case_id": row["case_id"],
            "grid_delta": row["numerics"]["grid_delta"],
            "rng_seed": row["rng_seed"],
            "movement": movement,
            "profile": {
                "current": profile_summary(row),
                "reference": profile_summary(reference),
                "width_order_preserved": profile_summary(row)["width_order_widest_to_narrowest"] == profile_summary(reference)["width_order_widest_to_narrowest"],
            },
            "runtime": {
                "current_elapsed_s": row["elapsed_s"],
                "reference_elapsed_s": reference["elapsed_s"],
                "reference_over_current_ratio": reference["elapsed_s"] / row["elapsed_s"],
                "interpretation": (
                    "raw wall time from the recorded machine and execution contexts; "
                    "not a causal or general benchmark"
                ),
            },
        })
    if len(arms) != 4:
        raise ValueError(f"expected four bridge rows, found {len(arms)}")
    return {
        "schema_version": 1,
        "campaign": "v3-bosch-grid-speed-bridge-review",
        "status": "complete_observational_review",
        "provenance": {
            "manifest": {"path": str(MANIFEST.relative_to(ROOT)), "sha256": digest(MANIFEST)},
            "new_rows": {"path": str(new_rows_path.relative_to(ROOT)), "sha256": digest(new_rows_path)},
            "focused_rows": {"path": str(FOCUSED_ROWS.relative_to(ROOT)), "sha256": digest(FOCUSED_ROWS)},
            "source_artifacts": manifest["source_artifacts"],
        },
        "arms": arms,
        "interpretation": {
            "accuracy_limit_used": False,
            "fine_grid_treated_as_truth": False,
            "repeat_range_treated_as_acceptance_limit": False,
            "setting_promotion_authorized": False,
            "next_step": "inspect Phase A observations before authorizing another grid or ray arm",
        },
    }


def build():
    manifest = gate0.strict_json_loads(MANIFEST.read_text())
    cases = runner.expand_cases(manifest)
    stage2a.evidence_origin = runner.evidence_origin
    completed = stage2a.audit_existing_rows(ROWS, cases)
    if len(completed) != 4:
        raise ValueError(f"expected four successful bridge rows, found {len(completed)}")
    new_rows = [completed[case["case_id"]] for case in cases]
    focused = [gate0.strict_json_loads(line) for line in FOCUSED_ROWS.read_text().splitlines() if line.strip()]
    return build_review(new_rows, focused, manifest)


def main():
    try:
        review = build()
    except ValueError as error:
        print(json.dumps({"status": "incomplete_evidence", "message": str(error), "output_written": False}, sort_keys=True))
        return 1
    OUTPUT.write_text(json.dumps(review, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"status": review["status"], "arms": len(review["arms"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

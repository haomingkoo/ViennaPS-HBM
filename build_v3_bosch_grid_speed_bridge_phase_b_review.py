"""Review Phase B of the Bosch speed bridge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import build_v3_bosch_grid_speed_bridge_review as phase_a_review
import foundation_pattern_bosch_gate0 as gate0
import v3_bosch_grid_speed_bridge_phase_b_runner as runner
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "evidence/numerical/v3_bosch_grid_speed_bridge_phase_b_manifest.json"
ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_grid_speed_bridge_phase_b_rows.jsonl"
PHASE_A_ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_grid_speed_bridge_rows.jsonl"
FOCUSED_ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_focused_ion_map_rows.jsonl"
OUTPUT = ROOT / "evidence/numerical/v3_bosch_grid_speed_bridge_phase_b_review.json"
METRICS = phase_a_review.METRICS


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [gate0.strict_json_loads(line) for line in path.read_text().splitlines() if line.strip()]


def movement(first, second):
    first_values = phase_a_review.metric_values(first)
    second_values = phase_a_review.metric_values(second)
    return {
        metric: {
            "first": first_values[metric],
            "second": second_values[metric],
            "signed_delta_second_minus_first": second_values[metric] - first_values[metric],
            "absolute_delta": abs(second_values[metric] - first_values[metric]),
        }
        for metric in METRICS
    }


def build_review(new_rows, phase_a_rows, focused_rows, manifest, *, new_rows_path=ROWS):
    new_by_role = {(row["recipe"]["ion_source_exponent"], row["design_class"]): row for row in new_rows}
    phase_a_by_id = {row["case_id"]: row for row in phase_a_rows}
    focused_by_id = {row["case_id"]: row for row in focused_rows}
    comparison_a = []
    comparison_b = []
    for cell_id, cell in manifest["design"]["cells"].items():
        exponent = 50 if cell_id == "e50_i0.04" else 141
        selected_fine = focused_by_id[cell["phase_a_fine_case_id"]]
        alternate_fine = focused_by_id[cell["alternate_fine_case_id"]]
        phase_a_500 = phase_a_by_id[cell["phase_a_grid_case_id"]]
        additional_500 = new_by_role[(exponent, "additional_500_stream")]
        new_1000 = new_by_role[(exponent, "same_stream_1000_ray_arm")]
        streams = []
        for label, fine, coarse in (
            ("phase_a_stream", selected_fine, phase_a_500),
            ("additional_stream", alternate_fine, additional_500),
        ):
            streams.append({
                "stream": label,
                "rng_seed": fine["rng_seed"],
                "movement_0.00125_to_0.0025": movement(fine, coarse),
                "profile_fine": phase_a_review.profile_summary(fine),
                "profile_0.0025": phase_a_review.profile_summary(coarse),
                "raw_runtime": {
                    "fine_elapsed_s": fine["elapsed_s"],
                    "grid_0.0025_elapsed_s": coarse["elapsed_s"],
                    "fine_over_0.0025_ratio": fine["elapsed_s"] / coarse["elapsed_s"],
                },
            })
        comparison_a.append({
            "cell_id": cell_id,
            "streams": streams,
            "repeat_behavior": {
                metric: {
                    "fine_values": [phase_a_review.metric_values(selected_fine)[metric], phase_a_review.metric_values(alternate_fine)[metric]],
                    "grid_0.0025_values": [phase_a_review.metric_values(phase_a_500)[metric], phase_a_review.metric_values(additional_500)[metric]],
                    "signed_movements": [
                        phase_a_review.metric_values(phase_a_500)[metric] - phase_a_review.metric_values(selected_fine)[metric],
                        phase_a_review.metric_values(additional_500)[metric] - phase_a_review.metric_values(alternate_fine)[metric],
                    ],
                }
                for metric in METRICS
            },
        })
        comparison_b.append({
            "cell_id": cell_id,
            "rng_seed": phase_a_500["rng_seed"],
            "movement_500_to_1000": movement(phase_a_500, new_1000),
            "profile_500": phase_a_review.profile_summary(phase_a_500),
            "profile_1000": phase_a_review.profile_summary(new_1000),
            "raw_runtime": {
                "rays_500_elapsed_s": phase_a_500["elapsed_s"],
                "rays_1000_elapsed_s": new_1000["elapsed_s"],
                "rays_1000_over_500_ratio": new_1000["elapsed_s"] / phase_a_500["elapsed_s"],
            },
        })
    if len(new_rows) != 4:
        raise ValueError(f"expected four Phase B rows, found {len(new_rows)}")
    phase_a_005 = [row for row in phase_a_rows if row["numerics"]["grid_delta"] == 0.005]
    return {
        "schema_version": 1,
        "campaign": "v3-bosch-grid-speed-bridge-phase-b-review",
        "status": "complete_observational_review",
        "provenance": {
            "manifest": {"path": str(MANIFEST.relative_to(ROOT)), "sha256": digest(MANIFEST)},
            "new_rows": {"path": str(new_rows_path.relative_to(ROOT)), "sha256": digest(new_rows_path)},
            "phase_a_rows": {"path": str(PHASE_A_ROWS.relative_to(ROOT)), "sha256": digest(PHASE_A_ROWS)},
            "focused_rows": {"path": str(FOCUSED_ROWS.relative_to(ROOT)), "sha256": digest(FOCUSED_ROWS)},
            "source_artifacts": manifest["source_artifacts"],
        },
        "comparison_a_two_stream_grid_movement": comparison_a,
        "comparison_b_same_stream_ray_movement": comparison_b,
        "stopped_grid_0.005": {
            "status": "stopped_after_phase_a",
            "reason": "it altered the selected top-middle-bottom profile measurements in both cells",
            "source_case_ids": [row["case_id"] for row in phase_a_005],
            "scope": "these two cells and recorded streams only",
        },
        "interpretation": {
            "accuracy_limit_used": False,
            "weighted_score_used": False,
            "reference_treated_as_truth": False,
            "repeat_range_treated_as_limit": False,
            "setting_promotion_authorized": False,
            "runtime_statement": "raw wall time from recorded execution contexts; not a causal or general benchmark",
        },
    }


def build():
    manifest = gate0.strict_json_loads(MANIFEST.read_text())
    cases = runner.expand_cases(manifest)
    stage2a.evidence_origin = runner.evidence_origin
    completed = stage2a.audit_existing_rows(ROWS, cases)
    if len(completed) != 4:
        raise ValueError(f"expected four successful Phase B rows, found {len(completed)}")
    return build_review([completed[case["case_id"]] for case in cases], rows(PHASE_A_ROWS), rows(FOCUSED_ROWS), manifest)


def main():
    try:
        review = build()
    except ValueError as error:
        print(json.dumps({"status": "incomplete_evidence", "message": str(error), "output_written": False}, sort_keys=True))
        return 1
    OUTPUT.write_text(json.dumps(review, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"status": review["status"], "new_rows": 4}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

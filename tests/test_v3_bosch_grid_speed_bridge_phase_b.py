"""Verify speed-bridge Phase B without launching it."""

import json
from pathlib import Path
import tempfile

from jsonschema import Draft202012Validator

import build_v3_bosch_grid_speed_bridge_phase_b as builder
import build_v3_bosch_grid_speed_bridge_phase_b_review as reviewer
import foundation_pattern_bosch_gate0 as gate0
import v3_bosch_grid_speed_bridge_phase_b_runner as runner


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_freezes_two_distinct_comparisons():
    manifest = builder.build_manifest()
    cases = runner.expand_cases(manifest)
    assert len(cases) == len({case["case_id"] for case in cases}) == 4
    assert not runner.paired_rng_errors(cases, manifest)
    by_role = {}
    for case in cases:
        by_role.setdefault(case["design_class"], []).append(case)
    assert {case["rng_seed"] for case in by_role["additional_500_stream"]} == {950819, 950910}
    assert {case["rng_seed"] for case in by_role["same_stream_1000_ray_arm"]} == {950728, 950273}
    assert all(case["numerics"]["grid_delta"] == 0.0025 for case in cases)
    assert {case["numerics"]["rays_per_point"] for case in cases} == {500, 1000}
    assert manifest["design"]["analysis_plan"]["accuracy_limit"] is None
    assert manifest["design"]["analysis_plan"]["weighted_score"] is None
    assert manifest["design"]["stopped_arm"]["grid_delta"] == 0.005
    assert not runner.validate_manifest(manifest)


def synthetic(case, offset):
    row = dict(case)
    row.update({
        "ok": True, "elapsed_s": 150 + offset,
        "selected_cycle_metrics": {"etch": {
            "depth": 1.25 + offset * 0.001,
            "cd_top": 0.33, "cd_middle": 0.32, "cd_bottom": 0.31,
            "max_bow": 0.006, "sidewall_angle_deg": 0.2, "scallop_rms": 0.002,
            "sample_cds": [0.33, 0.32, 0.31], "sample_fractions": [0.1, 0.5, 0.85],
        }},
    })
    return row


def test_review_separates_grid_and_ray_questions():
    manifest = builder.build_manifest()
    new_rows = [synthetic(case, index) for index, case in enumerate(runner.expand_cases(manifest))]
    phase_a = reviewer.rows(reviewer.PHASE_A_ROWS)
    focused = reviewer.rows(reviewer.FOCUSED_ROWS)
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        path = Path(directory) / "rows.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in new_rows))
        review = reviewer.build_review(new_rows, phase_a, focused, manifest, new_rows_path=path)
    schema = gate0.strict_json_loads((ROOT / "schemas/v3-bosch-grid-speed-bridge-phase-b-review.schema.json").read_text())
    assert not list(Draft202012Validator(schema).iter_errors(review))
    assert len(review["comparison_a_two_stream_grid_movement"]) == 2
    assert all(len(cell["streams"]) == 2 for cell in review["comparison_a_two_stream_grid_movement"])
    assert len(review["comparison_b_same_stream_ray_movement"]) == 2
    assert review["interpretation"]["accuracy_limit_used"] is False
    assert review["interpretation"]["weighted_score_used"] is False
    assert review["stopped_grid_0.005"]["status"] == "stopped_after_phase_a"


def test_frozen_manifest_is_current():
    frozen = gate0.strict_json_loads(builder.DEFAULT_OUTPUT.read_text())
    rebuilt = builder.build_manifest()
    rebuilt["runtime_fingerprint"] = frozen["runtime_fingerprint"]
    assert frozen == rebuilt


if __name__ == "__main__":
    test_manifest_freezes_two_distinct_comparisons()
    test_review_separates_grid_and_ray_questions()
    test_frozen_manifest_is_current()

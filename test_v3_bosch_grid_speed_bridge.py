"""Verify the Bosch grid-speed bridge without launching it."""

import json
from pathlib import Path
import tempfile

from jsonschema import Draft202012Validator

import build_v3_bosch_grid_speed_bridge as builder
import build_v3_bosch_grid_speed_bridge_review as reviewer
import foundation_pattern_bosch_gate0 as gate0
import v3_bosch_grid_speed_bridge_runner as runner
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent


def test_manifest_freezes_four_paired_runs():
    manifest = builder.build_manifest()
    cases = runner.expand_cases(manifest)
    assert len(cases) == len({case["case_id"] for case in cases}) == 4
    assert not runner.paired_rng_errors(cases)
    assert stage2a.rng_interval_errors(cases)
    grouped = {}
    for case in cases:
        grouped.setdefault(case["rng_stream"]["allocation_id"], []).append(case)
    assert {name: {row["numerics"]["grid_delta"] for row in rows} for name, rows in grouped.items()} == {
        "grid_bridge_e50_i0.04": {0.0025, 0.005},
        "grid_bridge_e141_i0.06324555": {0.0025, 0.005},
    }
    assert {name: {row["rng_seed"] for row in rows} for name, rows in grouped.items()} == {
        "grid_bridge_e50_i0.04": {950728},
        "grid_bridge_e141_i0.06324555": {950273},
    }
    assert manifest["design"]["analysis_plan"]["accuracy_limit"] is None
    assert manifest["design"]["analysis_plan"]["fine_grid_is_truth"] is False
    assert not runner.validate_manifest(manifest)


def synthetic_row(case, offset):
    row = dict(case)
    row.update({
        "ok": True,
        "elapsed_s": 100.0 + offset,
        "selected_cycle_metrics": {"etch": {
            "depth": 1.24 + offset * 0.0001,
            "cd_top": 0.33,
            "cd_middle": 0.32,
            "cd_bottom": 0.31,
            "max_bow": 0.006,
            "sidewall_angle_deg": 0.2,
            "scallop_rms": 0.002,
            "sample_cds": [0.33, 0.32, 0.31],
            "sample_fractions": [0.1, 0.5, 0.85]
        }},
    })
    return row


def test_review_is_observational_and_schema_valid():
    manifest = builder.build_manifest()
    focused = [gate0.strict_json_loads(line) for line in builder.FOCUSED_ROWS.read_text().splitlines() if line.strip()]
    new_rows = [synthetic_row(case, index) for index, case in enumerate(runner.expand_cases(manifest))]
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        path = Path(directory) / "rows.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in new_rows))
        review = reviewer.build_review(new_rows, focused, manifest, new_rows_path=path)
    schema = gate0.strict_json_loads((ROOT / "schemas/v3-bosch-grid-speed-bridge-review.schema.json").read_text())
    assert not list(Draft202012Validator(schema).iter_errors(review))
    assert review["interpretation"]["accuracy_limit_used"] is False
    assert review["interpretation"]["fine_grid_treated_as_truth"] is False
    assert all("signed_delta" in arm["movement"]["depth"] for arm in review["arms"])
    assert all(arm["profile"]["current"]["available"] for arm in review["arms"])


def test_frozen_manifest_is_current():
    frozen = gate0.strict_json_loads(builder.DEFAULT_OUTPUT.read_text())
    rebuilt = builder.build_manifest()
    rebuilt["runtime_fingerprint"] = frozen["runtime_fingerprint"]
    assert frozen == rebuilt


if __name__ == "__main__":
    test_manifest_freezes_four_paired_runs()
    test_review_is_observational_and_schema_valid()
    test_frozen_manifest_is_current()

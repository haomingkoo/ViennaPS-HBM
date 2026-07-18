"""Verify the focused ion-map review contract without launching simulations."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from jsonschema import Draft202012Validator

import build_v3_bosch_focused_ion_map_review as review
import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
SCHEMA = gate0.strict_json_loads(
    (ROOT / "schemas/v3-bosch-focused-ion-map-review.schema.json").read_text()
)


def synthetic_rows(manifest):
    rows = []
    for index, case in enumerate(stage2a.expand_cases(manifest)):
        row = dict(case)
        exponent = case["recipe"]["ion_source_exponent"]
        rate = case["recipe"]["ion_rate"]
        offset = index * 0.0001
        row.update({
            "ok": True,
            "selected_cycle_metrics": {"etch": {
                "depth": 1.25 + abs(rate) * 0.01 + offset,
                "cd_top": 0.30 + exponent * 0.00001 + offset,
                "cd_middle": 0.30 + abs(rate) * 0.01 + offset,
                "cd_bottom": 0.30 + exponent * 0.000005 + offset,
                "max_bow": exponent * 0.000001 + offset,
                "sidewall_angle_deg": rate + offset,
            }},
        })
        rows.append(row)
    return rows


def test_incomplete_default_fails_cleanly():
    try:
        review.build()
    except ValueError as error:
        assert "expected 12 successful rows, found 4" in str(error)
    else:
        raise AssertionError("incomplete focused map unexpectedly reviewed")


def test_complete_review_groups_repeats_and_uses_only_pareto():
    manifest = gate0.strict_json_loads(review.MANIFEST.read_text())
    rows = synthetic_rows(manifest)
    prior, prior_line = review.prior_row()
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        source = Path(directory) / "rows.jsonl"
        source.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        document = review.build_review(
            rows, manifest, prior, rows_path=source, prior_line=prior_line
        )
    assert not list(Draft202012Validator(SCHEMA).iter_errors(document))
    assert document["completeness"]["observed_new_rows"] == 12
    repeated = {cell["cell_id"]: cell for cell in document["cells"] if cell["new_run_count"] > 1}
    assert {name: cell["new_run_count"] for name, cell in repeated.items()} == {
        "e50_i0.04": 2,
        "e141_i0.06324555": 3,
    }
    singleton = next(cell for cell in document["cells"] if cell["new_run_count"] == 1)
    assert set(singleton["measurements"]["depth"]) == {"values"}
    assert set(repeated["e50_i0.04"]["measurements"]["depth"]) == {
        "values", "mean", "sample_sd"
    }
    assert document["pareto_analysis"]["weighted_score_used"] is False
    assert document["pareto_analysis"]["pass_limits_applied"] is False
    assert document["authority"]["recipe_authorized"] is False
    assert all("cell_id" in candidate for candidate in document["confirmation_candidates"])


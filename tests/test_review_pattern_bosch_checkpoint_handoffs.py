"""Synthetic guards for the four-shape Gate-0 handoff review."""

import copy
from pathlib import Path
import tempfile

import foundation_pattern_bosch_gate0 as gate0
import review_pattern_bosch_checkpoint_handoffs as review
from tests import test_pattern_bosch_checkpoint_handoff as fixture


def matrix(directory):
    rows_path = Path(directory) / "rows.jsonl"
    reviewed_cases = []
    for seed in gate0.EXPECTED_SEEDS:
        case = fixture.synthetic_case()
        case["rng_seed"] = seed
        payload = gate0.case_payload(case)
        case["case_id"] = gate0.case_id(payload)
        case["case_payload_sha256"] = gate0.canonical_sha256(payload)
        silicon = fixture.analytic_silicon(case)
        checkpoint = Path(directory) / f"{case['case_id']}.npz"
        fixture.write_checkpoint(checkpoint, case, silicon)
        gate0.append_row(rows_path, {
            **case,
            "ok": True,
            "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": gate0.file_sha256(checkpoint),
        })
        reviewed_cases.append({
            "case_id": case["case_id"],
            "arm": review.SOURCE_ARM,
            "valid": True,
            "pattern_pass": True,
            "etch_pass": True,
        })
    summary = {
        "campaign": "foundation-pattern-bosch-gate0",
        "reviewed_cases": reviewed_cases,
        "decision": {"broad_pattern_bosch_screen_authorized": True},
    }
    return summary, rows_path


def test_four_verified_handoffs_authorize_geometry_reuse_only():
    with tempfile.TemporaryDirectory() as directory:
        gate_summary, rows = matrix(directory)
        result = review.build_summary(gate_summary, rows)
        assert result["reviewed_checkpoint_count"] == 4
        assert all(row["accepted"] for row in result["handoff_results"])
        decision = result["decision"]
        assert decision["reusable_upstream_geometry_authorized"]
        assert not decision["layer_recipe_authorized"]
        assert not decision["process_window_authorized"]
        assert not decision["full_traveler_authorized"]
        review.write_json(Path(directory) / "summary.json", result)


def test_missing_shape_gate0_block_and_bad_hash_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        gate_summary, rows = matrix(directory)
        lines = rows.read_text().splitlines()
        rows.write_text("\n".join(lines[:-1]) + "\n")
        result = review.build_summary(gate_summary, rows)
        assert not result["decision"]["reusable_upstream_geometry_authorized"]
        assert "all four full-reference surface handoffs must pass" in result["blockers"]

    with tempfile.TemporaryDirectory() as directory:
        gate_summary, rows = matrix(directory)
        blocked = copy.deepcopy(gate_summary)
        blocked["decision"]["broad_pattern_bosch_screen_authorized"] = False
        result = review.build_summary(blocked, rows)
        assert not result["decision"]["reusable_upstream_geometry_authorized"]

    with tempfile.TemporaryDirectory() as directory:
        gate_summary, rows = matrix(directory)
        parsed = [gate0.strict_json_loads(line) for line in rows.read_text().splitlines()]
        parsed[0]["checkpoint_sha256"] = "0" * 64
        rows.write_text("".join(gate0.canonical_json(row) + "\n" for row in parsed))
        result = review.build_summary(gate_summary, rows)
        assert result["errors"]
        assert not result["decision"]["reusable_upstream_geometry_authorized"]


if __name__ == "__main__":
    test_four_verified_handoffs_authorize_geometry_reuse_only()
    test_missing_shape_gate0_block_and_bad_hash_fail_closed()
    print("pattern/Bosch checkpoint handoff review checks: PASS")

"""Bosch stochastic replicates must use disjoint ray-tracing seed streams."""

import json
import tempfile
from pathlib import Path

import foundation_metric_audit as audit


def manifest(seed_stride):
    return {
        "manifest_version": 99,
        "geometry": {},
        "recipe": {"num_cycles": 14},
        "target": {},
        "provenance": {},
        "designs": [
            {
                "name": "rng_schedule_test",
                "grid_deltas": [0.005, 0.0025],
                "rays_per_point": [1000],
                "seed_start": 52000,
                "seed_count": 4,
                "seed_stride": seed_stride,
            }
        ],
    }


def test_process_seed_count_matches_bosch_sequence():
    assert audit.bosch_process_seed_count(0) == 1
    assert audit.bosch_process_seed_count(13) == 40
    assert audit.bosch_process_seed_count(14) == 43


def test_adjacent_bases_are_rejected_as_correlated():
    try:
        audit.expand_cases(manifest(seed_stride=1))
    except ValueError as error:
        assert "RNG streams overlap" in str(error)
        assert "required>=43" in str(error)
    else:
        raise AssertionError("adjacent Bosch replicate bases were accepted")


def test_exact_nonoverlap_stride_is_accepted_and_paired_across_numerics():
    cases = audit.expand_cases(manifest(seed_stride=43))
    assert len(cases) == 8
    expected = [52000, 52043, 52086, 52129]
    for grid_delta in (0.005, 0.0025):
        observed = [
            case["rng_seed"]
            for case in cases
            if case["grid_delta"] == grid_delta
        ]
        assert observed == expected
    assert all(case["rng_process_seed_count"] == 43 for case in cases)
    assert all(case["rng_seed_stride"] == 43 for case in cases)


def test_failed_rows_are_retried_but_successes_resume():
    with tempfile.TemporaryDirectory() as directory:
        ledger = Path(directory) / "rows.jsonl"
        ledger.write_text(
            json.dumps({"case_id": "failed", "ok": False})
            + "\n"
            + json.dumps({"case_id": "passed", "ok": True})
            + "\n"
        )
        assert audit.completed_case_ids(ledger) == {"passed"}


if __name__ == "__main__":
    test_process_seed_count_matches_bosch_sequence()
    test_adjacent_bases_are_rejected_as_correlated()
    test_exact_nonoverlap_stride_is_accepted_and_paired_across_numerics()
    test_failed_rows_are_retried_but_successes_resume()
    print("Bosch RNG schedule checks: PASS")

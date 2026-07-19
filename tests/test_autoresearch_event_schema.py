"""Check retry and stop decisions in autoresearch events."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "autoresearch-event.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def event():
    return {
        "timestamp": "2026-07-18T00:00:00Z",
        "manifest_id": "example",
        "manifest_version": 1,
        "manifest_hash": "a" * 64,
        "case_key": "case-1",
        "case_payload_hash": "abc",
        "stage": "etch",
        "state": "failed_transient",
        "attempt": 1,
        "retry_count": 0,
        "retryable": True,
        "inputs": {},
        "environment": {},
        "numerical_profile": {},
        "elapsed_s": 1.0,
        "measurements": None,
        "metrics_valid": None,
        "hard_gate_pass": None,
        "numerical_state": "not_checked",
        "failure_scope": "infrastructure",
        "unresolved_reasons": [],
        "error": {"type": "TimeoutError", "message": "worker timed out"},
        "checkpoint": None,
        "decision": "retry_same_case",
        "next_action": "Retry once with the same case payload.",
        "stop_reason": None,
        "previous_event_hash": None,
        "event_hash": "b" * 64,
    }


def assert_invalid(value):
    assert list(VALIDATOR.iter_errors(value))


def main():
    valid = event()
    assert not list(VALIDATOR.iter_errors(valid))

    bad_timestamp = copy.deepcopy(valid)
    bad_timestamp["timestamp"] = "not-a-date"
    assert_invalid(bad_timestamp)

    second_retry = copy.deepcopy(valid)
    second_retry["attempt"] = 2
    second_retry["retry_count"] = 1
    assert_invalid(second_retry)

    deterministic_retry = copy.deepcopy(valid)
    deterministic_retry["state"] = "failed_deterministic"
    assert_invalid(deterministic_retry)

    false_promotion = copy.deepcopy(valid)
    false_promotion.update({
        "state": "stale_provenance",
        "retryable": False,
        "decision": "promote",
        "unresolved_reasons": ["source hash changed"],
    })
    assert_invalid(false_promotion)

    invalid_geometry = copy.deepcopy(valid)
    invalid_geometry.update({
        "state": "complete_invalid",
        "retryable": False,
        "metrics_valid": False,
        "numerical_state": "failed",
        "failure_scope": "geometry",
        "decision": "adjust_range",
        "next_action": "Reduce the failing range before another design.",
        "unresolved_reasons": ["self-intersecting interface"],
        "error": None,
    })
    assert not list(VALIDATOR.iter_errors(invalid_geometry))

    unqualified_promotion = copy.deepcopy(valid)
    unqualified_promotion.update({
        "state": "complete_measured",
        "retryable": False,
        "measurements": {"depth": 1.25},
        "metrics_valid": True,
        "hard_gate_pass": True,
        "numerical_state": "screening_only",
        "failure_scope": None,
        "error": None,
        "decision": "promote",
        "next_action": "Promote the candidate.",
    })
    assert_invalid(unqualified_promotion)

    stopped = copy.deepcopy(valid)
    stopped.update({
        "state": "needs_investigation",
        "retryable": False,
        "decision": "stop",
        "next_action": "Inspect the saved minimal failure.",
        "stop_reason": "The same failure repeated after one controlled reproduction.",
        "unresolved_reasons": ["deterministic exception"],
    })
    assert not list(VALIDATOR.iter_errors(stopped))
    stopped["stop_reason"] = None
    assert_invalid(stopped)


if __name__ == "__main__":
    main()
    print("autoresearch event schema checks: PASS")

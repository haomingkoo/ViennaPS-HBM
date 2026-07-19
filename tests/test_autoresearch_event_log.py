"""Exercise the autoresearch ledger and retry hook."""

from __future__ import annotations

import copy
from pathlib import Path
import tempfile

from scripts.autoresearch_event_log import action, append_event, validate_log


def payload():
    return {
        "timestamp": "2026-07-18T00:00:00Z",
        "manifest_id": "example",
        "manifest_version": 1,
        "manifest_hash": "a" * 64,
        "case_key": "case-1",
        "case_payload_hash": "b" * 64,
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
    }


def main():
    with tempfile.TemporaryDirectory() as directory:
        log = Path(directory) / "events.jsonl"
        first = append_event(log, payload())
        assert action(first)["run_action"] == "retry"

        second = copy.deepcopy(payload())
        second.update({
            "timestamp": "2026-07-18T00:01:00Z",
            "state": "failed_deterministic",
            "attempt": 2,
            "retry_count": 1,
            "retryable": False,
            "numerical_state": "failed",
            "failure_scope": "numerical",
            "unresolved_reasons": ["same exception after controlled retry"],
            "decision": "stop",
            "next_action": "Inspect the saved minimal failure.",
            "stop_reason": "The same failure repeated after the single retry.",
        })
        final = append_event(log, second)
        assert action(final)["should_stop"]
        errors, events = validate_log(log)
        assert not errors
        assert len(events) == 2

        lines = log.read_text().splitlines()
        log.write_text("\n".join(reversed(lines)) + "\n")
        errors, _ = validate_log(log)
        assert any("previous_event_hash" in error for error in errors)


if __name__ == "__main__":
    main()
    print("autoresearch event ledger checks: PASS")

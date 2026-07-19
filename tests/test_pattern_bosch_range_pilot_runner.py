"""Check the range-pilot runner contract without launching simulations."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from scripts.autoresearch_event_log import append_event
import run_pattern_bosch_range_pilot as runner


ROOT = Path(__file__).resolve().parents[1]
manifest_path = ROOT / "pattern_bosch_range_pilot_design.json"
manifest = json.loads(manifest_path.read_text())
current_manifest = runner.design_builder.build()
assert not runner.validate_manifest(current_manifest)
assert runner.validate_manifest(manifest) == [
    "manifest differs from the current deterministic builder"
]
executed_schema = (
    ROOT / "evidence/bosch/range_pilot/executed_sources/autoresearch-event.schema.json"
)
executed_schema_hash = hashlib.sha256(executed_schema.read_bytes()).hexdigest()
manifest_schema_hash = next(
    source["sha256"]
    for source in manifest["sources"]
    if source["path"] == "schemas/autoresearch-event.schema.json"
)
assert executed_schema_hash == manifest_schema_hash

case = manifest["cases"][0]
case_hash = hashlib.sha256(runner._canonical(case)).hexdigest()
event = {
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "manifest_id": manifest["campaign"],
    "manifest_version": manifest["schema_version"],
    "manifest_hash": "0" * 64,
    "case_key": case["case_id"],
    "case_payload_hash": case_hash,
    "stage": "mask_and_bosch_range_pilot",
    "state": "complete_measured",
    "attempt": 1,
    "retry_count": 0,
    "retryable": False,
    "inputs": {},
    "environment": {},
    "numerical_profile": {},
    "elapsed_s": 1.0,
    "measurements": {"example": 1.0},
    "metrics_valid": True,
    "hard_gate_pass": True,
    "numerical_state": "screening_only",
    "failure_scope": None,
    "unresolved_reasons": ["synthetic stale-manifest test"],
    "error": None,
    "checkpoint": None,
    "decision": "continue_search",
    "next_action": "Continue the bounded pilot.",
    "stop_reason": None,
}

with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / "events.jsonl"
    append_event(output, event)
    try:
        runner._latest_events(output, manifest, runner._sha256(manifest_path))
    except ValueError as error:
        assert "stale manifest hash" in str(error)
    else:
        raise AssertionError("stale manifest event was accepted")

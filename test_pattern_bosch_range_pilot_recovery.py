"""Verify the seven-case range-pilot recovery design."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
document = json.loads(
    (ROOT / "pattern_bosch_range_pilot_recovery_design.json").read_text()
)
bundle = json.loads(
    (ROOT / "evidence/bosch/range_pilot/source_bundle.json").read_text()
)
schema = json.loads(
    (ROOT / "schemas/pattern-bosch-range-pilot-recovery.schema.json").read_text()
)
assert not list(Draft202012Validator(schema).iter_errors(document))
assert len(document["cases"]) == 7
assert len({case["case_id"] for case in document["cases"]}) == 7
assert all(case["parent_event"]["reported_error"] for case in document["cases"])

raw_hashes = {source["path"]: source["sha256"] for source in bundle["raw_sources"]}
for source in document["sources"]:
    path = ROOT / source["path"]
    if path.is_file():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    else:
        assert raw_hashes[source["path"]] == source["sha256"]

recovery_by_case = {event["case_key"]: event for event in bundle["recovery_events"]}
for case in document["cases"]:
    assert case["case_id"] in recovery_by_case
    assert case["parent_event"]["event_hash"] in {
        event["event_hash"] for event in bundle["parent_events"]
    }

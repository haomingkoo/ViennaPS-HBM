"""Verify the committed range-pilot publication bundle."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.autoresearch_event_log import canonical, event_hash, schema_errors


ROOT = Path(__file__).resolve().parent
document = json.loads(
    (ROOT / "evidence/bosch/range_pilot/source_bundle.json").read_text()
)
schema = json.loads(
    (ROOT / "schemas/pattern-bosch-range-pilot-bundle.schema.json").read_text()
)
assert not list(Draft202012Validator(schema).iter_errors(document))
notes = " ".join(document["interpretation_notes"])
assert "supersedes" in notes
assert "do not approve" in notes
assert "do not qualify" in notes
for source in document["superseded_source_versions"]:
    archive = ROOT / source["archive_path"]
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert archive_hash == source["archive_sha256"]
    assert archive_hash == source["manifest_sha256"]

for source in document["committed_sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

for group in ("parent_events", "recovery_events"):
    previous = None
    for event in document[group]:
        assert not schema_errors(event)
        assert event["previous_event_hash"] == previous
        assert event["event_hash"] == event_hash(event)
        previous = event["event_hash"]

for case in document["cases"]:
    selected = document[case["selected_event"]["group"]][case["selected_event"]["index"]]
    assert selected["case_key"] == case["case_id"]
    assert selected["event_hash"] == case["selected_event"]["event_hash"]
    assert hashlib.sha256(case["profile"]["surface_path"].encode()).hexdigest() == case["profile"]["surface_sha256"]

assert hashlib.sha256(canonical(document["cases"])).hexdigest() == document["integrity"]["bundle_payload_sha256"]

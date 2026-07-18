"""Verify the published Phase A ray review and event provenance."""

import hashlib
import json
from pathlib import Path

from build_bosch_ray_phase_a_review import build
from scripts.autoresearch_event_log import validate_log


ROOT = Path(__file__).resolve().parent
review = json.loads(
    (ROOT / "evidence/numerical/bosch_ray_phase_a_review.json").read_text()
)
assert review == build()
assert review["decision"]["candidate_250_rays"] == "rejected_for_phase_b"
assert review["decision"]["candidate_500_rays"] == "requires_fresh_2000_ray_phase_b"
assert review["execution"]["state_counts"] == {
    "complete_measured": 20,
    "failed_deterministic": 12,
}
assert len(review["categorical_mismatches"]) == 4

events = ROOT / "evidence/numerical/bosch_ray_phase_a_events.jsonl"
errors, rows = validate_log(events)
assert not errors
assert len(rows) == 32

for source in review["sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
for checkpoint in review["archived_mismatch_checkpoints"]:
    path = ROOT / checkpoint["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == checkpoint["sha256"]

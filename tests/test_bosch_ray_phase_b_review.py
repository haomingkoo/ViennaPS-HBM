"""Verify the published Phase B ray review and clean-clone provenance."""

import hashlib
import json
from pathlib import Path

from build_bosch_ray_phase_b_review import build
from scripts.autoresearch_event_log import validate_log


ROOT = Path(__file__).resolve().parents[1]
review = json.loads(
    (ROOT / "evidence/numerical/bosch_ray_phase_b_review.json").read_text()
)
assert review == build()
assert review["decision"]["result"] == "reject_500_for_categorical_triage_on_this_panel"
assert review["decision"]["candidate_500_rays"] == "does_not_advance"
assert review["execution"]["state_counts"] == {"complete_measured": 26}
assert review["execution"]["pair_count"] == 13
assert len(review["comparisons"]) == 13
assert len(review["categorical_mismatches"]) == 4
assert {
    (item["pair_id"], tuple(item["mismatches"]))
    for item in review["categorical_mismatches"]
} == {
    ("depth_boundary:stream_1", ("assumed_band_depth",)),
    ("depth_boundary:stream_2", ("assumed_band_depth",)),
    ("depth_boundary:stream_3", ("assumed_band_depth",)),
    ("narrow_profile:stream_2", ("assumed_band_bow",)),
}
assert len(review["archived_mismatch_checkpoints"]) == 8

for comparison in review["comparisons"]:
    assert comparison["measurements"] is not None
    assert comparison["signed_deltas_500_minus_2000"] is not None
    assert comparison["absolute_deltas"] is not None
    assert comparison["continuous_equivalence_qualified"] is False
    for arm in ("500", "2000"):
        measured = comparison["measurements"][arm]
        assert measured["all_required_metrics_finite"]
        assert measured["resolution_available"]
        assert set(measured["assumed_band_margins"]) == {
            "depth_lower",
            "depth_upper",
            "width",
            "bow",
        }

events = ROOT / "evidence/numerical/bosch_ray_phase_b_events.jsonl"
errors, rows = validate_log(events)
assert not errors
assert len(rows) == 26

for source in review["sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
for checkpoint in review["archived_mismatch_checkpoints"]:
    path = ROOT / checkpoint["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == checkpoint["sha256"]

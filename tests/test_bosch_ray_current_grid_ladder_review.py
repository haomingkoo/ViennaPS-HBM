"""Verify the five-level Bosch ray review and its provenance."""

import hashlib
import json
import math
from pathlib import Path

from build_bosch_ray_current_grid_ladder_review import build
from scripts.autoresearch_event_log import validate_log


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "evidence/numerical/bosch_ray_current_grid_ladder_review.json"


document = json.loads(REVIEW.read_text())
assert document == build()
assert document["execution"] == {
    "complete_runs": 45,
    "grid_delta": 0.005,
    "pair_count": 9,
    "planned_runs": 45,
    "profile_samples_per_wall": 76,
    "rays_per_point": [250, 500, 750, 1000, 2000],
}
assert [level["rays_per_point"] for level in document["levels"]] == [
    250,
    500,
    750,
    1000,
    2000,
]
assert all(level["run_count"] == 9 for level in document["levels"])
assert len(document["pairs"]) == 9
assert len(document["adjacent_levels"]) == 4
assert len(document["repeat_spread_by_panel"]) == 15

for pair in document["pairs"]:
    assert len(pair["arms"]) == 5
    assert len(pair["adjacent_movements"]) == 4
    for arm in pair["arms"]:
        assert len(arm["profile"]["samples"]) == 76
        assert arm["event_hash"]
        checkpoint = arm["profile"]["checkpoint"]
        checkpoint_path = ROOT / checkpoint["path"]
        assert checkpoint_path.is_file()
        assert hashlib.sha256(checkpoint_path.read_bytes()).hexdigest() == checkpoint[
            "sha256"
        ]

for level in document["levels"]:
    for summary in [level["runtime_s"], *level["measurements"].values()]:
        assert all(math.isfinite(value) for key, value in summary.items() if key != "count")

events = ROOT / "evidence/numerical/bosch_ray_current_grid_ladder_events.jsonl"
errors, rows = validate_log(events)
assert not errors
assert len(rows) == 27

for source in document["sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

claims = " ".join(
    [document["result_scope"], *document["interpretation_rules"], *document["limits"]]
).lower()
assert "truth" in claims
assert "accuracy" in claims

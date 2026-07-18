"""Verify the claim-limited range-pilot review."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from build_pattern_bosch_range_pilot_review import build


ROOT = Path(__file__).resolve().parent
document = json.loads((ROOT / "pattern_bosch_range_pilot_review.json").read_text())
schema = json.loads(
    (ROOT / "schemas/pattern-bosch-range-pilot-review.schema.json").read_text()
)

assert document == build()
assert not list(Draft202012Validator(schema).iter_errors(document))
assert document["execution"]["state_counts"] == {
    "complete_measured": 20,
    "missing_measurement": 5,
}
assert len(document["response_spans"]) == 14
assert len(document["failures"]) == 5
assert len(document["cases"]) == 25
assert sum(case["display_state"] == "complete_measurements" for case in document["cases"]) == 18
assert sum(case["display_state"] == "low_movement_measured" for case in document["cases"]) == 2
assert sum(case["display_state"] == "measurement_unavailable" for case in document["cases"]) == 5
assert "factor effect or ranking" in document["prohibited_claims"]
assert "failure-boundary location" in document["prohibited_claims"]
assert all(
    item["next_use"].startswith("confirmation candidate only")
    for item in document["confirmation_nominations"]
)
assert len(document["confirmation_nominations"]) == 8
assert not any(
    "mask_height" in reason
    for item in document["confirmation_nominations"]
    for reason in item["reasons"]
)

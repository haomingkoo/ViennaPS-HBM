"""Verify the five-profile Bosch measurement review."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from build_pattern_bosch_unavailable_profile_review import build


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "evidence/bosch/pattern_bosch_unavailable_profile_review.json"
SCHEMA = ROOT / "schemas/pattern-bosch-unavailable-profile-review.schema.json"

document = json.loads(OUTPUT.read_text())
schema = json.loads(SCHEMA.read_text())
assert document == build()
assert not list(Draft202012Validator(schema).iter_errors(document))
assert {case["case_id"] for case in document["cases"]} == {
    "270ed2834457ec9c",
    "fed102f8549822b8",
    "b88f0c3e7a5e9bfb",
    "3ce6823a82555ae4",
    "031eff54b2d11a1a",
}

counts = {}
for case in document["cases"]:
    counts[case["availability_class"]] = counts.get(case["availability_class"], 0) + 1
    checkpoint = ROOT / case["checkpoint"]["path"]
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == case["checkpoint"]["sha256"]
    assert case["numerical_profile"]["qualified"] is False
    assert case["physical_interpretation"] == "unresolved"

assert counts == {
    "extractor_out_of_domain": 2,
    "full_width_measurement_unavailable_one_sided": 2,
    "via_reference_surface_absent": 1,
}

for case in document["cases"]:
    if case["availability_class"] == "extractor_out_of_domain":
        assert case["legacy_search_review"]["state"] == "extractor_domain_failure"
        assert case["full_geometry_review"]["state"] == "complete"
        assert case["full_geometry_review"]["metrics"] is not None
    else:
        assert case["full_geometry_review"]["metrics"] is None

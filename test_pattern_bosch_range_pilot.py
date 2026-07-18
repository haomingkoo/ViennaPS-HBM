"""Verify the frozen coarse mask/Bosch range-pilot design."""

import hashlib
import json
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator

from build_pattern_bosch_range_pilot import FACTOR_ORDER, build, coded_design
from process_config import PROCESS_CONFIG


ROOT = Path(__file__).resolve().parent
document = json.loads((ROOT / "pattern_bosch_range_pilot_design.json").read_text())
projection = json.loads((ROOT / "pattern_bosch_factor_projection.json").read_text())
measurement_contract = json.loads(
    (ROOT / "pattern_bosch_measurement_contract.json").read_text()
)
schema = json.loads(
    (ROOT / "schemas" / "pattern-bosch-range-pilot.schema.json").read_text()
)

rebuilt = build()
archived_schema = (
    ROOT / "evidence/bosch/range_pilot/executed_sources/autoresearch-event.schema.json"
)
archived_schema_hash = hashlib.sha256(archived_schema.read_bytes()).hexdigest()
archived_projection = (
    ROOT / "evidence/bosch/range_pilot/executed_sources/pattern_bosch_factor_projection.json"
)
archived_projection_hash = hashlib.sha256(archived_projection.read_bytes()).hexdigest()
for source in rebuilt["sources"]:
    if source["path"] == "schemas/autoresearch-event.schema.json":
        source["sha256"] = archived_schema_hash
    if source["path"] == "pattern_bosch_factor_projection.json":
        source["sha256"] = archived_projection_hash
assert document == rebuilt
assert not list(Draft202012Validator(schema).iter_errors(document))
assert document["authority"] == "coarse_model_range_pilot_only"
assert document["status"] == "frozen_design"
assert document["endpoint"]["mode"] == "final_completed_cycle"
assert document["endpoint"]["depth_matched_selection"] is False

matrix = coded_design()
assert matrix.shape == (25, 12)
assert set(np.unique(matrix)) == {-1, 0, 1}
assert sum(np.all(row == 0) for row in matrix) == 1
assert document["diagnostics"] == {
    "run_count": 25,
    "linear_model_rank": 13,
    "maximum_absolute_linear_correlation": 0.0,
    "maximum_absolute_main_to_quadratic_cross_product": 0.0,
    "maximum_absolute_main_to_interaction_cross_product": 0.0,
}

included_ids = {
    factor["registry_id"]
    for factor in projection["factors"]
    if factor["disposition"] == "include_range_finding"
}
assert {factor["registry_id"] for factor in document["factors"]} == included_ids
assert tuple(factor["name"] for factor in document["factors"]) == FACTOR_ORDER
assert set(document["required_measurements"]) == {
    metric["id"] for metric in measurement_contract["metrics"]
}
assert "factor effect or ranking" in document["inference_policy"]["prohibited"]
assert "failure-boundary location" in document["inference_policy"]["prohibited"]

configured_levels = PROCESS_CONFIG["pattern_bosch_range_pilot"]["levels"]
for factor in document["factors"]:
    assert factor["levels"] == configured_levels[factor["name"]]

for case, coded_row in zip(document["cases"], matrix, strict=True):
    assert case["coded_levels"] == coded_row.tolist()
    for name, code in zip(FACTOR_ORDER, coded_row, strict=True):
        assert case["recipe"][name] == configured_levels[name][int(code) + 1]

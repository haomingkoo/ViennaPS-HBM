"""Check that the mask/Bosch measurement contract stays blocked until qualified."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from build_pattern_bosch_measurement_contract import build


ROOT = Path(__file__).resolve().parent
contract = json.loads((ROOT / "pattern_bosch_measurement_contract.json").read_text())
assert contract == build()
assert contract["launch_status"] == "blocked_pending_measurement_qualification"
schema = json.loads(
    (ROOT / "schemas/pattern-bosch-measurement-contract.schema.json").read_text()
)
assert not list(Draft202012Validator(schema).iter_errors(contract))

for source in contract["sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

metric_ids = [metric["id"] for metric in contract["metrics"]]
assert len(metric_ids) == len(set(metric_ids))

extractor_source = (ROOT / "traveler_metrics.py").read_text()
for metric in contract["metrics"]:
    assert metric["extractor"]["symbol"] in extractor_source
    assert metric["extractor"]["sha256"] == hashlib.sha256(
        (ROOT / metric["extractor"]["path"]).read_bytes()
    ).hexdigest()
    assert len(metric["definition_sha256"]) == 64
    assert metric["qualification_status"] == "pending"
    assert metric["analytic_reference_evidence"] is not None
    assert metric["feature_present_evidence"] is not None
    if metric["step"] == "bosch_etch":
        assert metric["missingness_evidence"] is not None
    assert metric["resolution_bracket"] is None
    assert metric["save_reload_parity"]["maximum_absolute_difference"] == 0.0
    assert metric["numerical_envelope"] is None
    assert metric["repeat_envelope"] is None
    assert metric["useful_change_threshold"] is None

qualified_without_evidence = json.loads(json.dumps(contract))
qualified_without_evidence["launch_status"] = "qualified_for_screening"
assert list(Draft202012Validator(schema).iter_errors(qualified_without_evidence))

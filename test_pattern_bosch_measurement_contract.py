"""Check that the mask/Bosch measurement contract stays blocked until qualified."""

import hashlib
import json
from pathlib import Path

from build_pattern_bosch_measurement_contract import build


ROOT = Path(__file__).resolve().parent
contract = json.loads((ROOT / "pattern_bosch_measurement_contract.json").read_text())
assert contract == build()
assert contract["launch_status"] == "blocked_pending_measurement_qualification"

for source in contract["sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

metric_ids = [metric["id"] for metric in contract["metrics"]]
assert len(metric_ids) == len(set(metric_ids))

extractor_source = (ROOT / "traveler_metrics.py").read_text()
for metric in contract["metrics"]:
    assert metric["extractor"]["symbol"] in extractor_source
    assert metric["qualification_status"] == "pending"
    assert metric["detection_limit"] is None
    assert metric["known_failure_evidence"] is not None
    assert metric["prescribed_control_evidence"] is not None
    assert metric["save_reload_parity"]["maximum_absolute_difference"] == 0.0
    assert metric["numerical_allowance"] is None
    assert metric["repeat_allowance"] is None
    assert metric["useful_change_threshold"] is None

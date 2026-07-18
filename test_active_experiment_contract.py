"""Verify the public teaching-factor contract against its sources."""

import hashlib
import json
from pathlib import Path

from build_active_experiment_contract import build


ROOT = Path(__file__).resolve().parent
contract = json.loads((ROOT / "active_experiment_contract.json").read_text())
registry = json.loads((ROOT / "factor_registry.json").read_text())
assert contract == build()

for source in contract["sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

factor_ids = [factor["id"] for factor in contract["factors"]]
criterion_ids = [criterion["id"] for criterion in contract["acceptance_criteria"]]
assert len(factor_ids) == len(set(factor_ids))
assert len(criterion_ids) == len(set(criterion_ids))

registry_by_id = {record["id"]: record for record in registry["records"]}

source_text = (ROOT / "build_step_experiments.py").read_text()
for factor in contract["factors"]:
    registry_record = registry_by_id[factor["registry_id"]]
    compatible_steps = {
        "mask": {"pattern"},
        "bosch_etch": {"bosch_etch"},
        "liner": {"liner"},
        "barrier": {"barrier_seed"},
        "seed": {"barrier_seed"},
        "cmp": {"cmp"},
    }
    assert registry_record["step"] in compatible_steps[factor["step"]]
    assert factor["code"]["symbol"] in source_text
    assert len(factor["explored_values"]) >= 2
    assert factor["equipment_to_model_mapping"] is None
    assert factor["doe_status"] == "range_finding_required"
    assert factor["runtime_cost"] is None
    assert factor["restart_from"]

emitted_metrics = {
    metric for factor in contract["factors"] for metric in factor["measurements"]
}
assert all(
    criterion["metric"] in emitted_metrics
    for criterion in contract["acceptance_criteria"]
)

assert all(
    criterion["evidence_class"] == "assumed_comparison_band"
    and criterion["calibrated_pass"] is None
    and criterion["detection_limit"] is None
    for criterion in contract["acceptance_criteria"]
)

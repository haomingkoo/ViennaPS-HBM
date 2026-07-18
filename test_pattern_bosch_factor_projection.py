"""Verify that every mask/Bosch registry record has one explicit disposition."""

import ast
import hashlib
import json
from pathlib import Path

from build_pattern_bosch_factor_projection import (
    COUPLING_NOTES,
    MAIN_RANGE_FINDING,
    MASK_EROSION_BLOCK,
    build,
    is_relevant_record,
    tutorial_role,
)
from process_config import PROCESS_CONFIG


ROOT = Path(__file__).resolve().parent
projection = json.loads((ROOT / "pattern_bosch_factor_projection.json").read_text())
registry = json.loads((ROOT / "factor_registry.json").read_text())
assert projection == build()

for source in projection["sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

projected_ids = [factor["registry_id"] for factor in projection["factors"]]
expected_ids = [
    record["id"]
    for record in registry["records"]
    if is_relevant_record(record)
]
assert projected_ids == expected_ids
assert len(projected_ids) == len(set(projected_ids))

registry_by_id = {record["id"]: record for record in registry["records"]}
for factor in projection["factors"]:
    assert factor["tutorial_role"] == tutorial_role(
        registry_by_id[factor["registry_id"]], factor["disposition"]
    )
assert {
    factor["tutorial_role"]
    for factor in projection["factors"]
    if factor["disposition"] == "response_or_derived_input"
} == {"assumed_study_target"}

included_ids = {
    factor["registry_id"]
    for factor in projection["factors"]
    if factor["disposition"] == "include_range_finding"
}
eligible_ids = {
    record["id"]
    for record in registry["records"]
    if is_relevant_record(record)
    and record["doe_eligibility"] == "range_requalification_required"
}
assert included_ids == MAIN_RANGE_FINDING == eligible_ids - MASK_EROSION_BLOCK

tree = ast.parse((ROOT / "tsv_process.py").read_text())
arguments_by_callable = {
    node.name: {
        argument.arg
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
    }
    for node in tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}

for factor in projection["factors"]:
    if factor["disposition"] not in {
        "include_range_finding",
        "separate_mask_erosion_block",
    }:
        continue
    locator = factor["implementation_locator"]
    assert locator is not None
    value = PROCESS_CONFIG
    for part in locator["config_key"].split("."):
        value = value[part]
    assert value is not None
    assert locator["code_path"] == "tsv_process.py"
    assert locator["argument"] in arguments_by_callable[locator["callable"]]

for factor_id in COUPLING_NOTES:
    factor = next(item for item in projection["factors"] if item["registry_id"] == factor_id)
    assert factor["coupling_note"] == COUPLING_NOTES[factor_id]
assert projection["launch_status"] == "blocked_pending_ranges_measurements_and_numerics"

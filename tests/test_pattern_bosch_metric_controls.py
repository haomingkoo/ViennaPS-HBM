"""Verify the committed mask/Bosch measurement-control evidence."""

import hashlib
import json
import math
from pathlib import Path

from build_pattern_bosch_metric_controls import build


ROOT = Path(__file__).resolve().parents[1]
evidence = json.loads(
    (ROOT / "evidence/bosch/pattern_bosch_metric_controls.json").read_text()
)
generated = build()


def assert_equivalent(saved, rebuilt):
    if isinstance(saved, float):
        assert math.isclose(saved, rebuilt, rel_tol=1e-12, abs_tol=1e-12)
    elif isinstance(saved, dict):
        assert saved.keys() == rebuilt.keys()
        for key in saved:
            assert_equivalent(saved[key], rebuilt[key])
    elif isinstance(saved, list):
        assert len(saved) == len(rebuilt)
        for saved_item, rebuilt_item in zip(saved, rebuilt, strict=True):
            assert_equivalent(saved_item, rebuilt_item)
    else:
        assert saved == rebuilt


for key in (
    "schema_version",
    "scope",
    "sources",
    "full_profile_controls",
    "checks",
    "claim",
    "does_not_prove",
):
    assert_equivalent(evidence[key], generated[key])
assert len(evidence["cases"]) == len(generated["cases"])
for saved_case, generated_case in zip(evidence["cases"], generated["cases"], strict=True):
    assert saved_case["id"] == generated_case["id"]
    assert saved_case["step"] == generated_case["step"]
    assert saved_case["metrics"].keys() == generated_case["metrics"].keys()
    for metric in saved_case["metrics"]:
        assert math.isclose(
            saved_case["metrics"][metric],
            generated_case["metrics"][metric],
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
assert all(evidence["checks"].values())
assert {control["id"]: control["result"]["state"] for control in evidence["full_profile_controls"]} == {
    "full_straight": "complete",
    "full_wide": "complete",
    "full_wide_legacy_window": "extractor_domain_failure",
    "full_one_wall": "valid_categorical_modeled_state",
    "declared_surface_absent": "out_of_scope_region",
    "two_cell_neck": "insufficient_grid_representation",
    "three_cell_neck": "complete",
}

for source in evidence["sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

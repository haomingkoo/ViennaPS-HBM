"""Verify the committed Bosch grid preflight and selected checkpoint."""

import hashlib
import json
from pathlib import Path

import numpy as np

import bosch_grid_preflight as study
import traveler_metrics as tm


ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads(study.MANIFEST.read_text())
expected = study.build_manifest()
expected["sources"][0] = {
    "path": "bosch_grid_preflight.py",
    "sha256": study.digest(ROOT / "bosch_grid_preflight.py"),
}
frozen_contract = next(
    source
    for source in manifest["sources"]
    if source["path"] == "pattern_bosch_measurement_contract.json"
)
current_contract = next(
    source
    for source in expected["sources"]
    if source["path"] == frozen_contract["path"]
)
assert current_contract["sha256"] != frozen_contract["sha256"]
# The frozen campaign is intentionally stale at current HEAD. Normalize only
# to verify that the archived contract is the sole external-source difference.
next(
    source
    for source in expected["sources"]
    if source["path"] == frozen_contract["path"]
)["sha256"] = frozen_contract["sha256"]
assert manifest == expected
frozen_contract_path = (
    ROOT
    / "evidence/numerical/executed_sources/"
    "29110c3_pattern_bosch_measurement_contract.json"
)
assert study.digest(frozen_contract_path) == frozen_contract["sha256"]

result = json.loads(study.OUTPUT.read_text())
assert result["status"] == "complete"
assert result["manifest"]["sha256"] == hashlib.sha256(
    study.MANIFEST.read_bytes()
).hexdigest()
checkpoint = ROOT / result["checkpoint"]["path"]
assert result["checkpoint"]["sha256"] == hashlib.sha256(
    checkpoint.read_bytes()
).hexdigest()
assert result["selected"]["assumed_band_result"]["inside_all"] is True
assert len(result["cycles"]) == manifest["maximum_cycles"] + 1

data = np.load(checkpoint, allow_pickle=False)
remeasured = tm.measure_full_via_profile_2d(
    data["silicon_nodes"],
    data["silicon_lines"],
    surface_y=0.0,
    target_cd=manifest["assumed_comparison_bands"]["opening_cd"],
    domain_x_bounds=(-0.5, 0.5),
    grid_delta=manifest["numerics"]["grid_delta"],
)
assert remeasured["state"] == "complete"
for name, value in result["selected"]["metrics"].items():
    assert np.isclose(remeasured["metrics"][name], value)

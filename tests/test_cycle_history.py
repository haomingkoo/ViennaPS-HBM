"""A single etch run must expose depth-matched cycle checkpoints."""

import tempfile
from pathlib import Path

import numpy as np

import foundation_metric_audit as audit


case = {
    "case_id": "cycle-history-smoke",
    "manifest_version": 0,
    "design": "smoke",
    "grid_delta": 0.02,
    "rays_per_point": 200,
    "threads_per_worker": 1,
    "rng_seed": 777,
    "replicate": 0,
    "save_mesh": False,
    "record_cycle_history": True,
    "save_checkpoint_cycles": [1],
    "geometry": {
        "radius": 0.15,
        "mask_height": 0.3,
        "x_extent": 1.0,
        "y_extent": 1.5,
    },
    "target": {
        "opening_cd": 0.3,
        "mask_height": 0.3,
        "etch_depth": 1.25,
        "depth_tolerance": 0.1,
        "max_width_error": 0.06,
        "max_wall_bulge": 0.03,
    },
    "recipe": {
        "mask_taper": 2.0,
        "num_cycles": 2,
        "etch_time": 0.5,
        "initial_etch_time": 0.3,
        "neutral_rate": -0.08,
        "neutral_sticking_probability": 0.08,
        "deposition_thickness": 0.005,
        "deposition_sticking_probability": 0.01,
        "ion_source_exponent": 400,
        "theta_r_min": 45.0,
        "ion_rate": -0.1,
    },
    "provenance": {"purpose": "test"},
}

with tempfile.TemporaryDirectory() as directory:
    row = audit.run_case((case, Path(directory)))
    assert row["ok"], row
    checkpoint_path = Path(row["cycle_checkpoints"][0]["path"])
    assert checkpoint_path.is_file()
    assert row["cycle_checkpoints"] == [{
        "cycle": 1,
        "path": str(checkpoint_path),
        "sha256": audit.file_sha256(checkpoint_path),
    }]
    with np.load(checkpoint_path, allow_pickle=False) as checkpoint:
        assert checkpoint["case_id"].item() == case["case_id"]
        assert checkpoint["cycle"].item() == 1
        assert checkpoint["silicon_nodes"].shape[1] == 3
        assert checkpoint["silicon_lines"].shape[1] == 2
assert [item["cycle"] for item in row["cycle_history"]] == [0, 1, 2]
depths = [item["depth"] for item in row["cycle_history"]]
assert depths == sorted(depths)

print("cycle history checks: PASS")

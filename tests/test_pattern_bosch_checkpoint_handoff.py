"""Tests for the full-width Gate-0-to-deposition geometry handoff."""

import math
from pathlib import Path
import tempfile

import numpy as np
import viennaps as ps

import foundation_pattern_bosch_gate0 as gate0
import pattern_bosch_checkpoint_handoff as handoff
import traveler_metrics as tm


def synthetic_case():
    case = {
        "manifest_version": 1,
        "campaign": "foundation-pattern-bosch-gate0",
        "labels": ["full-traveler", "critical-review"],
        "arm": "full_reference_fine",
        "role": "full_reference",
        "geometry": {
            "radius": 0.15,
            "mask_height": 0.3,
            "x_extent": 1.0,
            "y_extent": 2.0,
            "hole_shape": "FULL",
        },
        "recipe": {"num_cycles": 14},
        "selected_cycle": 13,
        "numerics": {
            "grid_delta": 0.01,
            "rays_per_point": 2000,
            "threads_per_worker": 1,
            "simulation_dimension": 2,
        },
        "target": dict(gate0.EXPECTED_TARGET),
        "rng_seed": 61000,
        "rng_stream": {},
        "rng_policy": {},
        "runtime_fingerprint": {},
        "reference_recipe": {},
        "authority": {},
        "provenance": {},
    }
    payload = gate0.case_payload(case)
    return {
        **case,
        "case_id": gate0.case_id(payload),
        "case_payload_sha256": gate0.canonical_sha256(payload),
    }


def analytic_silicon(case):
    geometry = ps.Domain(
        gridDelta=case["numerics"]["grid_delta"],
        xExtent=case["geometry"]["x_extent"],
        yExtent=case["geometry"]["y_extent"],
    )
    ps.MakeHole(
        domain=geometry,
        holeRadius=case["geometry"]["radius"],
        holeDepth=case["target"]["etch_depth"],
        maskHeight=case["geometry"]["mask_height"],
        maskTaperAngle=0.0,
        holeShape=ps.HoleShape.FULL,
    ).apply()
    geometry.removeMaterial(ps.Material.Mask)
    return tm.material_region_mesh(geometry, ps.Material.Si)


def write_checkpoint(path, case, silicon):
    gate0.save_cycle_checkpoint(
        path,
        case,
        {"nodes": silicon["nodes"], "lines": silicon["lines"]},
        silicon,
        None,
    )


def test_surface_mesh_roundtrip_preserves_full_width_ctqs():
    case = synthetic_case()
    silicon = analytic_silicon(case)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "checkpoint.npz"
        write_checkpoint(path, case, silicon)
        result = handoff.compare_checkpoint_handoff(
            path, expected_sha256=gate0.file_sha256(path)
        )
    assert result["accepted"]
    assert not result["gate_flip"]
    assert result["maximum_surface_distance"] < 1e-12
    assert max(result["ctq_absolute_deltas"].values()) < 1e-12
    assert result["geometry"].getMaterialsInDomain() == {ps.Material.Si}


def test_checkpoint_hash_and_payload_are_fail_closed():
    case = synthetic_case()
    silicon = analytic_silicon(case)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "checkpoint.npz"
        write_checkpoint(path, case, silicon)
        try:
            handoff.load_verified_checkpoint(path, expected_sha256="0" * 64)
        except ValueError as error:
            assert "file hash differs" in str(error)
        else:
            raise AssertionError("handoff accepted an incorrect checkpoint hash")

        with np.load(path, allow_pickle=False) as snapshot:
            arrays = {key: np.asarray(snapshot[key]).copy() for key in snapshot.files}
        arrays["silicon_nodes"][0, 0] = math.nan
        tampered = Path(directory) / "tampered.npz"
        np.savez_compressed(tampered, **arrays)
        try:
            handoff.load_verified_checkpoint(tampered)
        except ValueError as error:
            assert "silicon nodes are nonfinite" in str(error)
        else:
            raise AssertionError("handoff accepted a malformed silicon mesh")


if __name__ == "__main__":
    test_surface_mesh_roundtrip_preserves_full_width_ctqs()
    test_checkpoint_hash_and_payload_are_fail_closed()
    print("pattern/Bosch checkpoint handoff checks: PASS")

"""Guards for the foundation layer qualification runner."""

import copy
import json

import foundation_layer_audit as layer


def test_runtime_fingerprint_and_design_ray_override_bind_case_ids():
    manifest = json.loads(layer.DEFAULT_MANIFEST.read_text())
    manifest["designs"] = [copy.deepcopy(manifest["designs"][0])]
    manifest["designs"][0]["seed_count"] = 1
    base = layer.expand_cases(manifest)[0]
    assert set(base["runtime_fingerprint"]) == {
        "runner_sha256",
        "metric_sha256",
        "tsv_process_sha256",
        "runtime_binary_sha256",
    }
    assert all(len(value) == 64 for value in base["runtime_fingerprint"].values())

    manifest["designs"][0]["rays_per_point"] = 4000
    changed = layer.expand_cases(manifest)[0]
    assert changed["rays_per_point"] == 4000
    assert changed["case_id"] != base["case_id"]


def test_liner_gate_requires_lower_wall_conformality():
    case = {
        "specs": {
            "liner": {"min_thickness": 0.02, "min_coverage": 0.995},
            "barrier_seed": {"min_thickness": 0.012, "min_coverage": 0.985},
        }
    }
    liner = {
        "minimum_local_thickness": 0.03,
        "floor_to_field_conformality": 0.999,
        "lower_wall_to_field_conformality": 0.90,
        "layer_continuous": True,
        "aperture_open": True,
    }
    metal = {
        "minimum_local_thickness": 0.007,
        "floor_to_field_conformality": 0.99,
        "layer_continuous": True,
        "aperture_open": True,
    }
    assert not layer.step_passes(case, liner, metal, metal)["liner"]
    liner["lower_wall_to_field_conformality"] = 0.999
    assert layer.step_passes(case, liner, metal, metal)["liner"]


if __name__ == "__main__":
    test_runtime_fingerprint_and_design_ray_override_bind_case_ids()
    test_liner_gate_requires_lower_wall_conformality()
    print("Foundation layer runner checks: PASS")

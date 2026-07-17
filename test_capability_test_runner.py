"""Fast guards for the capability-routed standalone test runner."""

from dataclasses import replace
from pathlib import Path

import scripts.run_capability_tests as runner


def test_every_repository_test_is_routed_exactly_once():
    assert runner.validate_test_inventory() == []


def test_custom_model_tests_use_their_exact_runtime():
    assert runner.runtime_for_test("test_copper_suppression_fill.py") == "cu"
    assert runner.runtime_for_test("test_copper_fill_transport_3d_bridge.py") == "cu"
    assert runner.runtime_for_test("test_height_material_cmp.py") == "cmp"
    assert runner.runtime_for_test("test_foundation_cmp_qualification.py") == "cmp"
    assert runner.runtime_for_test("test_traveler_metrics.py") == "stock"


def test_runtime_environments_cannot_inherit_an_ambient_pythonpath():
    stock = runner.runtime_environment(runner.RUNTIMES["stock"])
    copper = runner.runtime_environment(runner.RUNTIMES["cu"])
    cmp_runtime = runner.runtime_environment(runner.RUNTIMES["cmp"])
    assert "PYTHONPATH" not in stock
    assert Path(copper["PYTHONPATH"]) == Path("/tmp/viennaps-copper-exact")
    assert Path(cmp_runtime["PYTHONPATH"]) == Path(
        "/tmp/viennaps-height-material-cmp-exact"
    )


def test_exact_runtime_hashes_and_capabilities():
    row = runner.verify_runtimes(("stock",))[0]
    spec = runner.RUNTIMES["stock"]
    assert row["binary_sha256"] == spec.binary_sha256
    assert row["CopperSuppressionFill"] == spec.copper_suppression_fill
    assert row["HeightMaterialCMP"] == spec.height_material_cmp


def test_hash_drift_fails_closed():
    changed = replace(runner.RUNTIMES["stock"], binary_sha256="0" * 64)
    try:
        runner.verify_runtime(changed)
    except RuntimeError as error:
        assert "binary hash mismatch" in str(error)
    else:
        raise AssertionError("runtime binary drift was accepted")


if __name__ == "__main__":
    test_every_repository_test_is_routed_exactly_once()
    test_custom_model_tests_use_their_exact_runtime()
    test_runtime_environments_cannot_inherit_an_ambient_pythonpath()
    test_exact_runtime_hashes_and_capabilities()
    test_hash_drift_fails_closed()
    print("capability test-runner checks: PASS")

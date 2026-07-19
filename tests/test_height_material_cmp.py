"""Focused checks for the exact no-ray HeightMaterialCMP binding."""

import hashlib
import os
from pathlib import Path
import subprocess

import numpy as np
import viennaps as ps
import viennaps._core as ps_core

import foundation_cmp_qualification as cmpq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASE_COMMIT = "2956ed587984c6dc38be24c6e2390e10c9b2f0a7"
EXPECTED_PATCH_SHA256 = "0b635afc6ac1a4545748009d7d3efef0d2f15e1dc885e4698b409af85e23cc74"
EXPECTED_MODEL_SOURCE_SHA256 = "bbfc0c5b687ae55d62cfedfbcd90a6655b8fe893b2bf264d3c9575e0c172b3fd"
EXPECTED_BINARY_SHA256 = "d42733ed7b3355c9a8a94b45ce32b1d9536b6be9e7ff33165f172a08b49e54ef"


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_law(stop_y=0.03):
    return cmpq.HeightMaterialRemovalLaw(
        stop_y=stop_y,
        compliance_length=0.25,
        residual_contact=0.05,
        material_rate_ratios={
            ps.Material.Cu: 1.0,
            cmpq.CU_SEED_MATERIAL: 0.8,
            ps.Material.TaN: 0.25,
            ps.Material.SiO2: 0.01,
            ps.Material.Si: 0.005,
        },
    )


def raw_parameters():
    params = ps.HeightMaterialCMPParams()
    params.stopHeight = 0.03
    params.complianceLength = 0.25
    params.residualContact = 0.05
    params.platedCuRemovalRate = 1.0
    params.cuSeedMaterial = cmpq.CU_SEED_MATERIAL
    params.cuSeedRemovalRate = 0.8
    params.tantalumNitrideRemovalRate = 0.25
    params.siliconDioxideRemovalRate = 0.01
    params.siliconRemovalRate = 0.005
    return params


def test_python_and_cpp_pointwise_laws_are_identical():
    law = candidate_law()
    model = cmpq.make_combined_viennaps_model(law)
    assert cmpq.control_capabilities()["combined_height_material"]["exact"]
    for height in np.linspace(-0.10, 0.40, 101):
        assert np.isclose(
            model.evaluateContactWeight(height),
            law.contact_weight(height),
            rtol=0.0,
            atol=2e-15,
        )
        for material in law.material_rate_ratios:
            assert np.isclose(
                model.evaluateVelocity(height, material),
                law.normal_velocity(height, material),
                rtol=0.0,
                atol=2e-15,
            )


def test_material_gating_selectivity_and_height_limits():
    model = ps.HeightMaterialCMP(raw_parameters())
    model_3d = ps.d3.HeightMaterialCMP(raw_parameters())
    heights = np.linspace(-0.10, 0.40, 101)
    weights = np.asarray([model.evaluateContactWeight(y) for y in heights])
    assert np.all(np.diff(weights) >= 0.0)
    assert weights[0] == 0.05
    assert weights[-1] == 1.0
    middle = 0.12
    cu = model.evaluateVelocity(middle, ps.Material.Cu)
    assert np.isclose(
        model.evaluateVelocity(middle, cmpq.CU_SEED_MATERIAL),
        0.8 * cu,
    )
    assert np.isclose(
        model.evaluateVelocity(middle, ps.Material.TaN),
        0.25 * cu,
    )
    assert model.evaluateVelocity(middle, ps.Material.Mask) == 0.0
    assert model_3d.evaluateVelocity(middle, ps.Material.Cu) == cu


def run_tiny_full_stack():
    stack = cmpq.build_analytic_stack("raised_shoulders", grid_delta=0.01)
    before = cmpq.profile_from_geometry(stack)
    stack.geometry.enableMetaData(ps.MetaDataLevel.PROCESS)
    cmpq.apply_native_control(
        stack,
        "combined_height_material",
        duration=0.005,
        law=candidate_law(stack.stop_y),
    )
    after = cmpq.profile_from_geometry(stack)
    return stack, before, after


def test_full_stack_advection_is_height_weighted_and_fresh_process_deterministic():
    first_stack, first_before, first_after = run_tiny_full_stack()
    second_stack, second_before, second_after = run_tiny_full_stack()
    assert np.array_equal(first_before.cu_top_y, second_before.cu_top_y)
    assert np.array_equal(first_after.cu_top_y, second_after.cu_top_y)

    shoulder = int(np.argmin(np.abs(first_before.x - 0.35)))
    center = int(np.argmin(np.abs(first_before.x)))
    shoulder_removal = (
        first_before.cu_top_y[shoulder] - first_after.cu_top_y[shoulder]
    )
    center_removal = first_before.cu_top_y[center] - first_after.cu_top_y[center]
    assert shoulder_removal > center_removal > 0.0
    assert first_stack.materials == second_stack.materials

    metadata = first_stack.geometry.getMetaData()
    assert metadata["UncalibratedHeightMaterialAbstraction"] == [1.0]
    assert metadata["PadPressurePhysicsRepresented"] == [0.0]
    assert metadata["RayTracingUsed"] == [0.0]


def test_invalid_parameters_are_rejected():
    mutations = (
        ("stopHeight", float("nan")),
        ("complianceLength", 0.0),
        ("complianceLength", float("nan")),
        ("residualContact", -0.01),
        ("residualContact", 1.01),
        ("residualContact", float("nan")),
        ("platedCuRemovalRate", -0.01),
        ("cuSeedRemovalRate", float("inf")),
        ("tantalumNitrideRemovalRate", -0.01),
        ("siliconDioxideRemovalRate", -0.01),
        ("siliconRemovalRate", -0.01),
    )
    for name, value in mutations:
        params = raw_parameters()
        setattr(params, name, value)
        try:
            ps.HeightMaterialCMP(params)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid {name}={value!r} was accepted")

    undefined_seed = raw_parameters()
    undefined_seed.cuSeedMaterial = ps.Material.Undefined
    try:
        ps.HeightMaterialCMP(undefined_seed)
    except ValueError:
        pass
    else:
        raise AssertionError("undefined CuSeed material was accepted")

    aliased_seed = raw_parameters()
    aliased_seed.cuSeedMaterial = ps.Material.Cu
    try:
        ps.HeightMaterialCMP(aliased_seed)
    except ValueError:
        pass
    else:
        raise AssertionError("CuSeed aliasing plated Cu was accepted")


def test_exact_source_patch_and_binary_hashes():
    assert "PENDING" not in {
        EXPECTED_PATCH_SHA256,
        EXPECTED_MODEL_SOURCE_SHA256,
        EXPECTED_BINARY_SHA256,
    }
    source_dir = Path(os.environ.get(
        "VIENNAPS_CMP_SOURCE_DIR",
        "/tmp/viennaps-height-material-cmp-src",
    ))
    patch_file = PROJECT_ROOT / "patches/viennaps-height-material-cmp.patch"
    model_source = source_dir / "include/viennaps/models/psHeightMaterialCMP.hpp"
    assert subprocess.check_output(
        ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
        text=True,
    ).strip() == EXPECTED_BASE_COMMIT
    assert subprocess.run(
        ["git", "-C", str(source_dir), "apply", "--reverse", "--check", str(patch_file)],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0
    assert file_sha256(patch_file) == EXPECTED_PATCH_SHA256
    assert file_sha256(model_source) == EXPECTED_MODEL_SOURCE_SHA256
    assert file_sha256(ps_core.__file__) == EXPECTED_BINARY_SHA256


if __name__ == "__main__":
    if not hasattr(ps, "HeightMaterialCMP"):
        raise RuntimeError(
            "HeightMaterialCMP binding is absent; run the isolated rebuild script"
        )
    test_python_and_cpp_pointwise_laws_are_identical()
    test_material_gating_selectivity_and_height_limits()
    test_full_stack_advection_is_height_weighted_and_fresh_process_deterministic()
    test_invalid_parameters_are_rejected()
    test_exact_source_patch_and_binary_hashes()
    print("HeightMaterialCMP exact binding checks: PASS")

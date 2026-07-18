#!/usr/bin/env python3
"""Run repository tests under the exact ViennaPS runtime they require.

The repository currently has three intentionally separate ViennaPS binaries.
Planning is the default so an audit does not accidentally launch expensive
simulation-bearing tests. Pass ``portable``, ``stock``, ``cu``, ``cmp``, or
``all`` to run a group after each required runtime is verified.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/bin/python"


@dataclass(frozen=True)
class RuntimeSpec:
    name: str
    root: Path
    pythonpath: Path | None
    binary_sha256: str
    copper_suppression_fill: bool
    height_material_cmp: bool


RUNTIMES = {
    "stock": RuntimeSpec(
        name="stock",
        root=ROOT / ".venv",
        pythonpath=None,
        binary_sha256=(
            "0fb3e28628a60ae1206fde1f584fa55d1590e380569a5d7984fc8b6a34334480"
        ),
        copper_suppression_fill=False,
        height_material_cmp=False,
    ),
    "cu": RuntimeSpec(
        name="cu",
        root=Path("/tmp/viennaps-copper-exact"),
        pythonpath=Path("/tmp/viennaps-copper-exact"),
        binary_sha256=(
            "8970850eb6d3ffbd621a454e70b8d4504e4d9d7d6e953312915c92fdc1c87a8d"
        ),
        copper_suppression_fill=True,
        height_material_cmp=False,
    ),
    "cmp": RuntimeSpec(
        name="cmp",
        root=Path("/tmp/viennaps-height-material-cmp-exact"),
        pythonpath=Path("/tmp/viennaps-height-material-cmp-exact"),
        binary_sha256=(
            "d42733ed7b3355c9a8a94b45ce32b1d9536b6be9e7ff33165f172a08b49e54ef"
        ),
        copper_suppression_fill=False,
        height_material_cmp=True,
    ),
}


TESTS_BY_RUNTIME = {
    "stock": (
        "test_api_knob_audit.py",
        "test_bosch_rng_schedule.py",
        "test_bosch_grid_preflight.py",
        "test_bosch_ray_phase_b_manifest.py",
        "test_capability_test_runner.py",
        "test_cmp_controlled_stack.py",
        "test_cycle_history.py",
        "test_foundation_layer_audit.py",
        "test_freeze_pattern_bosch_screen_manifest.py",
        "test_frozen_campaign_supervisor.py",
        "test_gate0_publication_checkpoint.py",
        "test_full_2d_layer_metrics.py",
        "test_layer_model_acceptance_design.py",
        "test_layer_process_models.py",
        "test_legacy_metric_guard.py",
        "test_mask_erosion.py",
        "test_native_domain_checkpoint.py",
        "test_pattern_bosch_checkpoint_handoff.py",
        "test_pattern_bosch_discovery_s1.py",
        "test_pattern_bosch_gate0.py",
        "test_pattern_bosch_gate0_r1.py",
        "test_pattern_bosch_screen_design.py",
        "test_pattern_bosch_screen_runner.py",
        "test_pattern_bosch_range_pilot_runner.py",
        "test_process_config.py",
        "test_process_reproducibility.py",
        "test_publication_data.py",
        "test_review_bosch_cycle_history.py",
        "test_review_foundation_layer_audit.py",
        "test_review_foundation_metric_audit.py",
        "test_review_pattern_bosch_checkpoint_handoffs.py",
        "test_review_pattern_bosch_screen.py",
        "test_target_specs.py",
        "test_traveler_metrics.py",
        "test_v3_methodology_guards.py",
        "test_v3_numerical_release.py",
        "test_v3_pattern_bosch_stage2a.py",
        "test_v3_pattern_skew_stage1.py",
        "test_watch_pattern_bosch_gate0_r1_anchors.py",
    ),
    "cu": (
        "test_copper_fill_trajectory.py",
        "test_copper_fill_transport_3d_bridge.py",
        "test_copper_fill_transport_boundary_confirmation.py",
        "test_copper_fill_transport_confirmation.py",
        "test_copper_fill_transport_sign_screen.py",
        "test_copper_suppression_fill.py",
        "test_foundation_copper_fill_structural_challenge.py",
        "test_morphology_fill_control.py",
        "test_review_copper_fill_access_surface.py",
        "test_review_copper_fill_boundary_refinement.py",
        "test_review_copper_fill_regional_kinematics.py",
        "test_review_copper_fill_trajectory.py",
        "test_review_copper_fill_transition.py",
        "test_review_copper_fill_transport_effects.py",
    ),
    "cmp": (
        "test_foundation_cmp_qualification.py",
        "test_height_material_cmp.py",
    ),
    "portable": (
        "test_active_experiment_contract.py",
        "test_autoresearch_event_log.py",
        "test_autoresearch_event_schema.py",
        "test_evidence_schema.py",
        "test_ray_benefit_review.py",
        "test_explainer_visual.py",
        "test_factor_registry_provenance.py",
        "test_pattern_bosch_factor_projection.py",
        "test_pattern_bosch_measurement_contract.py",
        "test_pattern_bosch_metric_controls.py",
        "test_pattern_bosch_unavailable_profile_review.py",
        "test_pattern_bosch_range_pilot.py",
        "test_pattern_bosch_range_pilot_bundle.py",
        "test_pattern_bosch_range_pilot_recovery.py",
        "test_pattern_bosch_range_pilot_review.py",
        "test_bosch_ray_phase_a_review.py",
        "test_bosch_ray_phase_b_review.py",
    ),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_environment(spec: RuntimeSpec) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    if spec.pythonpath is not None:
        env["PYTHONPATH"] = str(spec.pythonpath)
    return env


def verify_runtime(spec: RuntimeSpec) -> dict:
    if not PYTHON.is_file():
        raise RuntimeError(f"project Python is missing: {PYTHON}")
    if not spec.root.is_dir():
        raise RuntimeError(f"{spec.name} runtime is missing: {spec.root}")
    probe = subprocess.run(
        [
            str(PYTHON),
            "-c",
            (
                "import json, viennaps as ps, viennaps._core as core; "
                "print(json.dumps({'core': core.__file__, "
                "'copper': hasattr(ps, 'CopperSuppressionFill'), "
                "'cmp': hasattr(ps, 'HeightMaterialCMP')}))"
            ),
        ],
        cwd=ROOT,
        env=runtime_environment(spec),
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError(
            f"{spec.name} runtime probe failed:\n{probe.stdout}{probe.stderr}"
        )
    lines = [line for line in probe.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"{spec.name} runtime probe returned no JSON")
    payload = json.loads(lines[-1])
    core = Path(payload["core"]).resolve()
    expected_root = spec.root.resolve()
    if expected_root not in core.parents:
        raise RuntimeError(
            f"{spec.name} loaded {core}, outside expected runtime {expected_root}"
        )
    observed_hash = file_sha256(core)
    if observed_hash != spec.binary_sha256:
        raise RuntimeError(
            f"{spec.name} binary hash mismatch: expected={spec.binary_sha256} "
            f"observed={observed_hash} path={core}"
        )
    observed_capabilities = (bool(payload["copper"]), bool(payload["cmp"]))
    expected_capabilities = (
        spec.copper_suppression_fill,
        spec.height_material_cmp,
    )
    if observed_capabilities != expected_capabilities:
        raise RuntimeError(
            f"{spec.name} capability mismatch: expected={expected_capabilities} "
            f"observed={observed_capabilities}"
        )
    return {
        "name": spec.name,
        "core": str(core),
        "binary_sha256": observed_hash,
        "CopperSuppressionFill": observed_capabilities[0],
        "HeightMaterialCMP": observed_capabilities[1],
    }


def verify_runtimes(names=("stock", "cu", "cmp")) -> list[dict]:
    return [verify_runtime(RUNTIMES[name]) for name in names]


def validate_test_inventory() -> list[str]:
    routed = [test for tests in TESTS_BY_RUNTIME.values() for test in tests]
    errors = []
    duplicates = sorted({test for test in routed if routed.count(test) > 1})
    if duplicates:
        errors.append(f"tests routed more than once: {duplicates}")
    discovered = {path.name for path in ROOT.glob("test_*.py")}
    listed = set(routed)
    missing = sorted(listed - discovered)
    unknown = sorted(discovered - listed)
    if missing:
        errors.append(f"routed tests are missing: {missing}")
    if unknown:
        errors.append(f"unrouted tests require classification: {unknown}")
    return errors


def runtime_for_test(filename: str) -> str | None:
    matches = [name for name, tests in TESTS_BY_RUNTIME.items() if filename in tests]
    return matches[0] if len(matches) == 1 else None


def run_group(name: str) -> list[str]:
    spec = RUNTIMES.get(name)
    environment = runtime_environment(spec) if spec else dict(os.environ)
    failures = []
    for filename in TESTS_BY_RUNTIME[name]:
        print(f"[{name}] {filename}", flush=True)
        result = subprocess.run(
            [str(PYTHON), str(ROOT / filename)],
            cwd=ROOT,
            env=environment,
            check=False,
        )
        if result.returncode != 0:
            failures.append(filename)
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        nargs="?",
        default="plan",
        choices=("plan", "portable", "stock", "cu", "cmp", "all"),
        help="plan inventories routes; other modes verify runtimes and execute tests",
    )
    args = parser.parse_args(argv)

    inventory_errors = validate_test_inventory()
    if inventory_errors:
        for error in inventory_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    for name in ("portable", "stock", "cu", "cmp"):
        print(f"{name}: {len(TESTS_BY_RUNTIME[name])} tests")
        for filename in TESTS_BY_RUNTIME[name]:
            print(f"  {filename}")

    if args.mode == "plan":
        print("plan only: inventory checked; runtimes not verified; no tests executed")
        return 0

    names = ("portable", "stock", "cu", "cmp") if args.mode == "all" else (args.mode,)
    runtime_names = tuple(name for name in names if name in RUNTIMES)
    try:
        runtime_rows = verify_runtimes(runtime_names)
    except (RuntimeError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for row in runtime_rows:
        print(
            f"verified {row['name']}: {row['binary_sha256']} "
            f"Cu={row['CopperSuppressionFill']} CMP={row['HeightMaterialCMP']}"
        )
    failures = []
    for name in names:
        failures.extend(f"{name}:{test}" for test in run_group(name))
    if failures:
        print(f"failed tests ({len(failures)}):", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print("capability-routed tests: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

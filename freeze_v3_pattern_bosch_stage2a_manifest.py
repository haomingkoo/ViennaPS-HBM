"""Freeze V3 Stage 2a only after the numerical-release evidence passes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import build_v3_pattern_bosch_stage2a as builder
import v3_pattern_bosch_stage2a_runner as runner


def build_manifest(
    numerical_release_path=runner.DEFAULT_NUMERICAL_RELEASE,
    *,
    project_root=runner.ROOT,
):
    root = Path(project_root)
    source = Path(numerical_release_path)
    source = source if source.is_absolute() else root / source
    if not source.is_file():
        raise ValueError("V3 numerical release is missing")
    release = builder.common.strict_load(source)
    prerequisite_errors = runner.validate_numerical_release(release, project_root=root)
    if prerequisite_errors:
        raise ValueError(
            "V3 Stage 2a numerical prerequisite failed: "
            + "; ".join(prerequisite_errors)
        )
    spec = builder.common.strict_load(root / builder.DEFAULT_SPEC)
    design = builder.build_design(spec)
    manifest = {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": "v3-pattern-bosch-stage2a",
        "labels": ["full-traveler", "critical-review"],
        "design": design,
        "effective_screen_thresholds": runner.effective_screen_thresholds(
            release, design, project_root=root
        ),
        "execution": {
            "output": str(runner.DEFAULT_OUTPUT),
            "maximum_workers": 2,
            "threads_per_worker": 7,
            "executor": "direct_checkpointed_batch_no_llm",
            "launch_order": "after_v3_pattern_stage1_review_resource_scheduling_only",
        },
        "runtime_fingerprint": runner.runtime_fingerprint(root),
        "source_artifacts": {
            "v3_numerical_release": {
                "path": str(source.relative_to(root)),
                "sha256": runner.file_sha256(source),
            }
        },
        "authority": design["authority"],
        "provenance": {
            "executor": "direct_checkpointed_batch_no_llm",
            "metric_module": "traveler_metrics.py",
            "native_checkpoint": "ViennaPS .vpsd",
            "design_role": "broad Bosch effect and interaction hypothesis generation, not optimization",
            "stage1_dependency": "none; nominal-pattern Stage 2a is scientifically separable",
            "stage1_launch_order": "Stage 1 runs first only to allocate the two available workers to the earliest checkpoint",
            "noise_status": (
                "thresholds include 3*sqrt(2)*sample SD from the four disjoint "
                "released nominal 2,000-ray baselines; recipe-specific replication "
                "is still required for confirmation"
            ),
        },
    }
    errors = runner.validate_manifest(
        manifest,
        check_runtime=True,
        check_prerequisite=True,
        project_root=root,
    )
    if errors:
        raise ValueError("frozen V3 Stage 2a manifest is invalid: " + "; ".join(errors))
    return manifest


def freeze(path, manifest):
    path = Path(path)
    serialized = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text() != serialized:
            raise ValueError("refusing to overwrite a different frozen manifest")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized)
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--numerical-release",
        type=Path,
        default=runner.DEFAULT_NUMERICAL_RELEASE,
    )
    parser.add_argument("--output", type=Path, default=runner.DEFAULT_MANIFEST)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest(args.numerical_release)
    output_path = runner.project_path(args.output)
    if args.check:
        expected = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if not output_path.is_file() or output_path.read_text() != expected:
            raise ValueError(f"stale or missing manifest: {output_path}")
    else:
        freeze(output_path, manifest)
    preflight = manifest["design"]["design"]["input_independence_preflight"]
    print(json.dumps({
        "manifest_sha256": runner.canonical_sha256(manifest),
        "recipes": manifest["design"]["design"]["recipe_count"],
        "simulations": manifest["design"]["design"]["logical_simulation_count"],
        "max_abs_pearson": preflight["maximum_absolute_pearson"],
        "max_abs_spearman": preflight["maximum_absolute_spearman"],
        "max_vif": preflight["maximum_vif"],
        "recipe_authorized": manifest["authority"]["recipe_authorized"],
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

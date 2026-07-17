"""Freeze V3 Stage 1 only after the numerical release approves 2D screening."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import build_v3_pattern_skew_stage1 as builder
import v3_pattern_skew_stage1_runner as runner


def _stored_path(path, root):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def build_manifest(
    numerical_release_path=runner.DEFAULT_NUMERICAL_RELEASE,
    *,
    project_root=runner.ROOT,
):
    root = Path(project_root)
    spec = builder.strict_load(root / builder.DEFAULT_SPEC)
    design = builder.build_design(spec)
    release_path = Path(numerical_release_path)
    release_path = release_path if release_path.is_absolute() else root / release_path
    if not release_path.is_file():
        raise ValueError("V3 numerical release is missing; Stage 1 remains frozen shut")
    release = builder.strict_load(release_path)
    release_errors = runner.validate_numerical_release(release)
    if release_errors:
        raise ValueError("V3 numerical release rejected: " + "; ".join(release_errors))

    reference_path = root / design["fixed_bosch_recipe"]["source_path"]
    if not reference_path.is_file():
        raise ValueError("reference Bosch recipe source is missing")
    manifest = {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": "v3-pattern-skew-stage1",
        "labels": ["full-traveler", "critical-review"],
        "design": design,
        "execution": {
            "output": str(runner.DEFAULT_OUTPUT),
            "maximum_workers": 2,
            "threads_per_worker": 7,
            "executor": "direct_checkpointed_batch_no_llm",
        },
        "runtime_fingerprint": runner.runtime_fingerprint(root),
        "source_artifacts": {
            "numerical_release": {
                "path": _stored_path(release_path, root),
                "sha256": runner.file_sha256(release_path),
            },
            "reference_recipe": {
                "path": _stored_path(reference_path, root),
                "sha256": runner.file_sha256(reference_path),
            },
        },
        "authority": design["authority"],
        "provenance": {
            "executor": "direct_checkpointed_batch_no_llm",
            "planner": "V3 staged broad-skew methodology",
            "metric_module": "traveler_metrics.py",
            "checkpoint_format": "ViennaPS .vpsd",
            "evidence_role": "single-block pattern geometry screen, not optimization",
        },
    }
    errors = runner.validate_manifest(
        manifest,
        check_runtime=True,
        check_sources=True,
        project_root=root,
    )
    if errors:
        raise ValueError("frozen V3 Stage 1 manifest is invalid: " + "; ".join(errors))
    return manifest


def freeze(path, manifest):
    path = Path(path)
    serialized = serialized_manifest(manifest)
    if path.exists():
        if path.read_text() != serialized:
            raise ValueError("refusing to overwrite a different frozen manifest")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized)
    os.replace(temporary, path)


def serialized_manifest(manifest):
    return json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"


def check_frozen(path, manifest):
    path = Path(path)
    if not path.is_file():
        raise ValueError("frozen Stage 1 manifest is missing")
    if path.read_text() != serialized_manifest(manifest):
        raise ValueError("frozen Stage 1 manifest is stale or differs")


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
        check_frozen(output_path, manifest)
    else:
        freeze(output_path, manifest)
    print(json.dumps({
        "manifest_sha256": runner.canonical_sha256(manifest),
        "cases": manifest["design"]["logical_case_count"],
        "rays_per_point": manifest["design"]["numerics"]["rays_per_point"],
        "screening_only": manifest["authority"]["pattern_geometry_screening_only"],
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

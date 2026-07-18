"""Freeze Phase B of the focused Bosch speed bridge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "evidence/numerical/v3_bosch_grid_speed_bridge_phase_b_manifest.json"
ROWS = Path("autoresearch-results/restart_audit/v3_bosch_grid_speed_bridge_phase_b_rows.jsonl")
CAMPAIGN = "v3-bosch-grid-speed-bridge-phase-b"
SOURCES = {
    "phase_a_manifest": ROOT / "evidence/numerical/v3_bosch_grid_speed_bridge_manifest.json",
    "phase_a_rows": ROOT / "autoresearch-results/restart_audit/v3_bosch_grid_speed_bridge_rows.jsonl",
    "phase_a_review": ROOT / "evidence/numerical/v3_bosch_grid_speed_bridge_review.json",
    "focused_manifest": ROOT / "evidence/numerical/v3_bosch_focused_ion_map_manifest.json",
    "focused_rows": ROOT / "autoresearch-results/restart_audit/v3_bosch_focused_ion_map_rows.jsonl",
    "focused_review": ROOT / "evidence/numerical/v3_bosch_focused_ion_map_review.json",
}
CELLS = {
    "e50_i0.04": {
        "phase_a_fine_case_id": "5f841d553d8100f9",
        "alternate_fine_case_id": "4ce7cae7837b9b50",
        "phase_a_grid_case_id": "42896640bba58b61",
    },
    "e141_i0.06324555": {
        "phase_a_fine_case_id": "1cf4ff64c506b271",
        "alternate_fine_case_id": "b550a7d966b8ddbc",
        "phase_a_grid_case_id": "2d28afa05ca75718",
    },
}


def load_rows(path):
    return {
        row["case_id"]: row
        for line in path.read_text().splitlines() if line.strip()
        for row in [gate0.strict_json_loads(line)]
    }


def build_manifest():
    phase_a_rows = load_rows(SOURCES["phase_a_rows"])
    focused_rows = load_rows(SOURCES["focused_rows"])
    runs = []
    cells = {}
    for cell_id, ids in CELLS.items():
        selected = focused_rows[ids["phase_a_fine_case_id"]]
        alternate = focused_rows[ids["alternate_fine_case_id"]]
        phase_a = phase_a_rows[ids["phase_a_grid_case_id"]]
        if selected["rng_seed"] != phase_a["rng_seed"] or phase_a["numerics"] != {
            "grid_delta": 0.0025, "rays_per_point": 500,
            "threads_per_worker": 7, "simulation_dimension": 2,
        }:
            raise ValueError(f"{cell_id}: Phase A pairing differs")
        if alternate["rng_seed"] == selected["rng_seed"]:
            raise ValueError(f"{cell_id}: alternate stream is not independent")
        cells[cell_id] = {
            **ids,
            "phase_a_seed": selected["rng_seed"],
            "alternate_seed": alternate["rng_seed"],
        }
        runs.extend([
            {
                "run_id": f"{cell_id}_additional500",
                "cell_id": cell_id,
                "role": "additional_500_stream",
                "source_fine_case_id": alternate["case_id"],
                "paired_phase_a_case_id": None,
                "rng_seed": alternate["rng_seed"],
                "grid_delta": 0.0025,
                "rays_per_point": 500,
            },
            {
                "run_id": f"{cell_id}_same_stream1000",
                "cell_id": cell_id,
                "role": "same_stream_1000_ray_arm",
                "source_fine_case_id": selected["case_id"],
                "paired_phase_a_case_id": phase_a["case_id"],
                "rng_seed": selected["rng_seed"],
                "grid_delta": 0.0025,
                "rays_per_point": 1000,
            },
        ])
    manifest = {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": CAMPAIGN,
        "labels": ["full-traveler", "critical-review"],
        "design": {
            "phase": "B",
            "question": "Does grid 0.0025 behave similarly on a second stream, and what moves when rays increase from 500 to 1000 on the Phase A stream?",
            "cells": cells,
            "runs": runs,
            "stopped_arm": {
                "grid_delta": 0.005,
                "status": "stopped_after_phase_a",
                "basis": "it altered selected top-middle-bottom profile measurements in both cells",
                "scope": "these two cells and recorded streams only",
            },
            "analysis_plan": {
                "comparison_a": "two-stream 0.00125-versus-0.0025 raw movement, repeat behavior, and runtime",
                "comparison_b": "same-stream 500-versus-1000 raw movement and runtime at grid 0.0025",
                "accuracy_limit": None,
                "weighted_score": None,
                "reference_is_truth": False,
                "automatic_promotion": False,
            },
        },
        "execution": {
            "output": str(ROWS),
            "maximum_workers": 2,
            "threads_per_worker": 7,
            "executor": "direct_checkpointed_batch_no_llm",
        },
        "runtime_fingerprint": stage2a.runtime_fingerprint(ROOT),
        "source_artifacts": {},
        "authority": {
            "phase_b_execution_authorized": True,
            "builder_or_test_may_launch": False,
            "numerical_setting_authorized": False,
            "recipe_authorized": False,
        },
        "provenance": {
            "paired_seed_reuse_declared": True,
            "pointwise_common_random_numbers_claimed": False,
            "fine_grid_is_numerical_truth": False,
        },
    }
    artifacts = {
        **SOURCES,
        "builder": ROOT / "build_v3_bosch_grid_speed_bridge_phase_b.py",
        "runner": ROOT / "v3_bosch_grid_speed_bridge_phase_b_runner.py",
        "reviewer": ROOT / "build_v3_bosch_grid_speed_bridge_phase_b_review.py",
        "review_schema": ROOT / "schemas/v3-bosch-grid-speed-bridge-phase-b-review.schema.json",
    }
    manifest["source_artifacts"] = {
        name: {"path": str(path.relative_to(ROOT)), "sha256": stage2a.file_sha256(path)}
        for name, path in artifacts.items()
    }
    return manifest


def freeze(path, value):
    serialized = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text() != serialized:
            raise ValueError(f"refusing to overwrite different manifest: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized)
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest()
    serialized = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text() != serialized:
            raise ValueError(f"stale or missing manifest: {args.output}")
    else:
        freeze(args.output.resolve(), manifest)
    print(json.dumps({"campaign": CAMPAIGN, "new_runs": 4, "canonical_sha256": stage2a.canonical_sha256(manifest)}, sort_keys=True))


if __name__ == "__main__":
    main()

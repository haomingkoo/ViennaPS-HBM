"""Freeze Phase A of the focused Bosch grid-speed bridge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
FOCUSED_MANIFEST = ROOT / "evidence/numerical/v3_bosch_focused_ion_map_manifest.json"
FOCUSED_ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_focused_ion_map_rows.jsonl"
FOCUSED_REVIEW = ROOT / "evidence/numerical/v3_bosch_focused_ion_map_review.json"
DEFAULT_OUTPUT = ROOT / "evidence/numerical/v3_bosch_grid_speed_bridge_manifest.json"
ROWS = Path("autoresearch-results/restart_audit/v3_bosch_grid_speed_bridge_rows.jsonl")
CAMPAIGN = "v3-bosch-grid-speed-bridge-phase-a"
REFERENCES = {
    "e50_i0.04": "5f841d553d8100f9",
    "e141_i0.06324555": "1cf4ff64c506b271",
}
GRIDS = (0.0025, 0.005)


def digest(path):
    return stage2a.file_sha256(path)


def reference_rows():
    indexed = {}
    for line_number, line in enumerate(FOCUSED_ROWS.read_text().splitlines(), 1):
        if line.strip():
            row = gate0.strict_json_loads(line)
            if row.get("case_id") in REFERENCES.values():
                indexed[row["case_id"]] = (row, line_number)
    if set(indexed) != set(REFERENCES.values()):
        raise ValueError("a selected focused-map reference row is missing")
    return indexed


def build_manifest():
    focused = gate0.strict_json_loads(FOCUSED_MANIFEST.read_text())
    review = gate0.strict_json_loads(FOCUSED_REVIEW.read_text())
    if review.get("status") != "complete_descriptive_review":
        raise ValueError("focused-map review is incomplete")
    rows = reference_rows()
    runs = []
    pairs = {}
    for cell_id, case_id in REFERENCES.items():
        row, line_number = rows[case_id]
        if row.get("ok") is not True or row["numerics"]["grid_delta"] != 0.00125:
            raise ValueError(f"{cell_id}: selected reference is not a successful fine-grid row")
        pairs[cell_id] = {
            "reference_case_id": case_id,
            "reference_line_number": line_number,
            "reference_grid_delta": 0.00125,
            "reused_rng_seed": row["rng_seed"],
            "reused_process_seed_interval": {
                "first": row["rng_stream"]["first_process_seed"],
                "last": row["rng_stream"]["last_process_seed"],
            },
        }
        for grid in GRIDS:
            runs.append({
                "run_id": f"{cell_id}_g{grid:g}",
                "pair_id": cell_id,
                "grid_delta": grid,
                "reference_case_id": case_id,
                "rng_seed": row["rng_seed"],
            })
    manifest = {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": CAMPAIGN,
        "labels": ["full-traveler", "critical-review"],
        "design": {
            "phase": "A",
            "question": "How do two coarser grids move saved geometry measurements and wall time on two focused cells?",
            "reference_grid_delta": 0.00125,
            "tested_grid_deltas": list(GRIDS),
            "rays_per_point": 500,
            "pairs": pairs,
            "runs": runs,
            "pairing_policy": (
                "reuse each selected base process seed across its two numerical arms; "
                "this does not claim pointwise-identical particle paths"
            ),
            "analysis_plan": {
                "compare": [
                    "raw measurement movement from the selected 0.00125 row",
                    "location relative to the observed 0.00125 repeat min-max",
                    "profile availability and top-middle-bottom width order",
                    "raw wall time and observed wall-time ratio",
                ],
                "accuracy_limit": None,
                "fine_grid_is_truth": False,
                "automatic_setting_promotion": False,
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
            "phase_a_execution_authorized": True,
            "builder_or_test_may_launch": False,
            "numerical_setting_authorized": False,
            "recipe_authorized": False,
        },
        "provenance": {
            "paired_base_seed_reuse": True,
            "pointwise_common_random_numbers_claimed": False,
            "reference_grid_is_numerical_truth": False,
            "existing_artifacts_preserved": True,
        },
    }
    artifacts = {
        "focused_manifest": FOCUSED_MANIFEST,
        "focused_rows": FOCUSED_ROWS,
        "focused_review": FOCUSED_REVIEW,
        "builder": ROOT / "build_v3_bosch_grid_speed_bridge.py",
        "runner": ROOT / "v3_bosch_grid_speed_bridge_runner.py",
        "reviewer": ROOT / "build_v3_bosch_grid_speed_bridge_review.py",
        "review_schema": ROOT / "schemas/v3-bosch-grid-speed-bridge-review.schema.json",
    }
    manifest["source_artifacts"] = {
        name: {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}
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

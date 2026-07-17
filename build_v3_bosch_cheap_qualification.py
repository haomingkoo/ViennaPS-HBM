"""Build the cheap Bosch screening-mode qualification manifest.

This does not replace the frozen 2,000-ray Stage 2a evidence. It reruns the
promoted broad anchors at lower ray count so factor ranking can be compared
before any cheap interaction DOE is authorized.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / ".scratch/full-traveler-autoresearch/v3_pattern_bosch_stage2a_manifest.json"
DEFAULT_OUTPUT = ROOT / ".scratch/full-traveler-autoresearch/v3_bosch_cheap_qualification_manifest.json"
ROWS = Path("autoresearch-results/restart_audit/v3_bosch_cheap_qualification_rows.jsonl")
PROMOTED = (
    "etch_time",
    "deposition_thickness",
    "ion_source_exponent",
    "ion_rate",
    "neutral_rate",
    "neutral_sticking_probability",
)


def _freeze(path, value):
    serialized = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text() != serialized:
            raise ValueError(f"refusing to overwrite different manifest: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized)
    os.replace(temporary, path)


def build_manifest():
    source = gate0.strict_json_loads(SOURCE.read_text())
    source_errors = stage2a.validate_manifest(
        source, check_runtime=False, check_prerequisite=True
    )
    if source_errors:
        raise ValueError("source Stage 2a manifest is invalid: " + "; ".join(source_errors))

    selected = []
    for row in source["design"]["recipes"]:
        reasons = set(row["anchor_reasons"])
        if "nominal" in reasons or any(
            f"ofat:{factor}:{level}" in reasons
            for factor in PROMOTED
            for level in ("low", "high")
        ):
            selected.append(copy.deepcopy(row))
    if len(selected) != 13:
        raise ValueError(f"expected nominal plus 12 promoted anchors, found {len(selected)}")

    nominal = next(row for row in selected if "nominal" in row["anchor_reasons"])
    for repeat in range(1, 4):
        row = copy.deepcopy(nominal)
        row["recipe_id"] = f"{nominal['recipe_id']}_cheap_repeat_{repeat}"
        row["anchor_reasons"] = [f"cheap_center_repeat:{repeat}"]
        row["design_class"] = "cheap_center_repeat"
        selected.append(row)

    design = copy.deepcopy(source["design"])
    design["campaign"] = "v3-bosch-cheap-qualification"
    design["question"] = (
        "Does a 500-ray discovery mode preserve the broad factor ranking, "
        "large-effect directions, and reachability boundaries observed at 2,000 rays?"
    )
    design["evidence_class"] = "cheap-mode qualification; not gate or recipe authority"
    design["numerics"]["rays_per_point"] = 500
    design["trajectory"]["early_stop_depth"] = 1.36
    design["rng_policy"].update({
        "seed_start": 920000,
        "interval_count": len(selected),
        "assignment": "one disjoint cheap-screen interval per logical simulation",
        "interpretation": "discovery-only; compare ranking to preserved 2,000-ray anchors",
    })
    design["recipes"] = selected
    design["design"] = {
        "method": "nominal plus low/high anchors for six promoted controls and three additional center repeats",
        "recipe_count": 13,
        "logical_simulation_count": len(selected),
        "center_repeat_count": 4,
        "promoted_factor_count": len(PROMOTED),
    }
    design["authority"] = {
        "cheap_screen_qualification_only": True,
        "confirmed_factor_authorized": False,
        "recipe_authorized": False,
        "process_window_authorized": False,
        "full_traveler_authorized": False,
    }

    return {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": "v3-bosch-cheap-qualification",
        "labels": ["full-traveler", "critical-review"],
        "design": design,
        "execution": {
            "output": str(ROWS),
            "maximum_workers": 2,
            "threads_per_worker": 7,
            "executor": "direct_checkpointed_batch_no_llm",
            "adaptive_stop": "do not launch interaction DOE unless ranking review passes",
        },
        "runtime_fingerprint": stage2a.runtime_fingerprint(ROOT),
        "source_artifacts": {
            "stage2a_manifest": {
                "path": str(SOURCE.relative_to(ROOT)),
                "sha256": stage2a.file_sha256(SOURCE),
            },
            "stage2a_rows": {
                "path": str(stage2a.DEFAULT_OUTPUT),
                "sha256": stage2a.file_sha256(ROOT / stage2a.DEFAULT_OUTPUT),
            },
        },
        "authority": design["authority"],
        "provenance": {
            "purpose": "qualify a cheap broad-screening mode before combined interactions",
            "reference_rays_per_point": 2000,
            "candidate_rays_per_point": 500,
            "existing_artifacts_preserved": True,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest()
    if not args.check:
        _freeze(args.output.resolve(), manifest)
    print(json.dumps({
        "campaign": manifest["campaign"],
        "logical_simulations": manifest["design"]["design"]["logical_simulation_count"],
        "rays_per_point": manifest["design"]["numerics"]["rays_per_point"],
        "promoted_factors": list(PROMOTED),
        "canonical_sha256": stage2a.canonical_sha256(manifest),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

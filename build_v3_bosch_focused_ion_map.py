"""Freeze a focused Bosch ion-direction response map."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path

import build_v3_pattern_bosch_stage2a as design_tools
import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "evidence/numerical/v3_pattern_bosch_stage2a_manifest.json"
PRIOR_ROWS = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_rows.jsonl"
INTERACTION_REVIEW = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_review.json"
RAY_REVIEW = ROOT / "evidence/numerical/bosch_ray_current_grid_ladder_review.json"
BUILDER = ROOT / "build_v3_bosch_focused_ion_map.py"
RUNNER = ROOT / "v3_bosch_focused_ion_map_runner.py"
DEFAULT_OUTPUT = ROOT / "evidence/numerical/v3_bosch_focused_ion_map_manifest.json"
ROWS = Path("autoresearch-results/restart_audit/v3_bosch_focused_ion_map_rows.jsonl")
PRIOR_CASE_ID = "7405eb159356c564"
CAMPAIGN = "v3-bosch-focused-ion-map"


def transformed_midpoint(factor, first, second):
    if factor["transform"] == "log":
        value = math.sqrt(first * second)
    elif factor["transform"] == "signed_log_magnitude":
        value = -math.sqrt(abs(first * second))
    else:
        value = (first + second) / 2
    if factor["type"] == "int":
        return int(round(value))
    return round(value, int(factor.get("digits", 10)))


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


def _prior_row():
    matches = [
        gate0.strict_json_loads(line)
        for line in PRIOR_ROWS.read_text().splitlines()
        if line.strip() and PRIOR_CASE_ID in line
    ]
    if len(matches) != 1 or matches[0].get("case_id") != PRIOR_CASE_ID:
        raise ValueError("saved best interaction row is missing or ambiguous")
    return matches[0]


def build_manifest():
    source = gate0.strict_json_loads(SOURCE.read_text())
    errors = stage2a.validate_manifest(source, check_runtime=False)
    if errors:
        raise ValueError("source Stage 2a manifest is invalid: " + "; ".join(errors))

    factors = {row["name"]: row for row in source["design"]["factors"]}
    exponent = factors["ion_source_exponent"]
    ion_rate = factors["ion_rate"]
    exponent_levels = (
        exponent["low"],
        transformed_midpoint(exponent, exponent["low"], exponent["nominal"]),
        exponent["nominal"],
    )
    rate_levels = (
        ion_rate["high"],
        transformed_midpoint(ion_rate, ion_rate["high"], ion_rate["nominal"]),
        ion_rate["nominal"],
    )
    nominal = {name: factor["nominal"] for name, factor in factors.items()}
    best_recipe = dict(nominal)
    best_recipe.update(ion_source_exponent=exponent_levels[0], ion_rate=rate_levels[0])

    prior = _prior_row()
    expected_prior = {
        **best_recipe,
        "mask_taper": source["design"]["geometry"]["mask_taper"],
        "mask_ion_rate": source["design"]["fixed_recipe"]["mask_ion_rate"],
    }
    if prior.get("recipe") != expected_prior:
        raise ValueError("saved best row no longer matches the focused-map anchor")

    recipes = []

    def add(recipe, label, repeat):
        recipes.append({
            "recipe_id": f"v3focused_{label}_r{repeat}",
            "design_class": "focused_ion_map",
            "anchor_reasons": [f"{label}:repeat:{repeat}"],
            "normalized_coordinates": {
                name: design_tools.to_unit(factors[name], value)
                for name, value in recipe.items()
            },
            "recipe": recipe,
        })

    for exponent_value in exponent_levels:
        for rate_value in rate_levels:
            if (exponent_value, rate_value) == (exponent_levels[0], rate_levels[0]):
                continue
            recipe = dict(nominal)
            recipe.update(ion_source_exponent=exponent_value, ion_rate=rate_value)
            add(recipe, f"e{exponent_value}_i{abs(rate_value):.8g}", 1)
    for repeat in (1, 2):
        add(dict(best_recipe), "saved_best_repeat", repeat)
    center_recipe = dict(nominal)
    center_recipe.update(ion_source_exponent=exponent_levels[1], ion_rate=rate_levels[1])
    for repeat in (2, 3):
        add(dict(center_recipe), "map_center", repeat)
    if len(recipes) != 12 or len({row["recipe_id"] for row in recipes}) != 12:
        raise ValueError("focused map must contain 12 uniquely identified runs")

    design = copy.deepcopy(source["design"])
    design["campaign"] = CAMPAIGN
    design["question"] = (
        "How do ion arrival directionality and directional removal jointly change "
        "depth, width profile, wall shape, and runtime near the best saved profile?"
    )
    design["evidence_class"] = "focused 500-ray response map with targeted repeats"
    design["numerics"]["rays_per_point"] = 500
    design["trajectory"]["early_stop_depth"] = 1.36
    reserved = list(design["rng_policy"]["reserved_prior_v3_intervals"])
    reserved.extend([
        {"campaign": "v3-pattern-bosch-stage2a", "first": 820000, "last": 828735},
        {"campaign": "v3-bosch-cheap-qualification", "first": 920000, "last": 921455},
        {"campaign": "v3-bosch-cheap-interactions", "first": 930000, "last": 932547},
        {"campaign": "v3-bosch-interior-refinement", "first": 940000, "last": 941637},
    ])
    design["rng_policy"].update({
        "seed_start": 950000,
        "interval_count": len(recipes),
        "reserved_prior_v3_intervals": reserved,
        "assignment": "one disjoint interval per new run, including repeats",
        "interpretation": "focused discovery and repeatability only; no recipe authority",
    })
    design["recipes"] = recipes
    design["predeclared_interactions"] = [{
        "factors": ["ion_source_exponent", "ion_rate"],
        "basis": "the saved exact interaction block moved depth and wall shape strongly",
    }]
    design["design"] = {
        "method": "3x3 transformed ion-direction map with new repeat streams",
        "factor_levels": {
            "ion_source_exponent": list(exponent_levels),
            "ion_rate": list(rate_levels),
        },
        "new_run_count": len(recipes),
        "unique_factor_cells": 9,
        "saved_best_new_repeats": 2,
        "center_new_repeats": 3,
        "saved_best_source_case_id": PRIOR_CASE_ID,
    }
    design["analysis_plan"] = {
        "selection_method": "pareto_raw_measurements",
        "weighted_score_authorized": False,
        "candidate_rank_from_assumed_target_flags": False,
        "responses": [
            "depth", "cd_top", "cd_middle", "cd_bottom", "cd_span",
            "sidewall_angle_deg", "max_bow", "scallop_rms", "selected_cycle",
            "elapsed_s",
        ],
        "floor_shape": "diagnostic_only_until_a_validated_floor_metric_exists",
        "target_flags": "retained as labeled teaching comparisons, not fab limits",
    }
    design["authority"] = {
        "focused_map_only": True,
        "campaign_execution_authorized": True,
        "builder_or_test_may_launch": False,
        "recipe_authorized": False,
        "process_window_authorized": False,
        "full_traveler_authorized": False,
    }
    return {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": CAMPAIGN,
        "labels": ["full-traveler", "critical-review"],
        "design": design,
        "execution": {
            "output": str(ROWS),
            "maximum_workers": 2,
            "threads_per_worker": 7,
            "executor": "direct_checkpointed_batch_no_llm",
        },
        "runtime_fingerprint": stage2a.runtime_fingerprint(ROOT),
        "source_artifacts": {
            "stage2a_manifest": {
                "path": str(SOURCE.relative_to(ROOT)),
                "sha256": stage2a.file_sha256(SOURCE),
            },
            "saved_interaction_rows": {
                "path": str(PRIOR_ROWS.relative_to(ROOT)),
                "sha256": stage2a.file_sha256(PRIOR_ROWS),
            },
            "saved_interaction_review": {
                "path": str(INTERACTION_REVIEW.relative_to(ROOT)),
                "sha256": stage2a.file_sha256(INTERACTION_REVIEW),
            },
            "current_ray_ladder_review": {
                "path": str(RAY_REVIEW.relative_to(ROOT)),
                "sha256": stage2a.file_sha256(RAY_REVIEW),
            },
            "focused_builder": {
                "path": str(BUILDER.relative_to(ROOT)),
                "sha256": stage2a.file_sha256(BUILDER),
            },
            "focused_runner": {
                "path": str(RUNNER.relative_to(ROOT)),
                "sha256": stage2a.file_sha256(RUNNER),
            },
        },
        "authority": design["authority"],
        "provenance": {
            "discovery_rays_per_point": 500,
            "sensitivity_check_rays_per_point": 1000,
            "compute_policy": (
                "use 500 rays for this discovery map and 1,000 rays for later "
                "sensitivity checks; this is not an accuracy or numerical-truth claim"
            ),
            "legacy_2000_ray_role": "preserved comparison evidence, not the default compute policy",
            "existing_artifacts_preserved": True,
        },
    }


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
    print(json.dumps({
        "campaign": manifest["campaign"],
        "simulations": len(manifest["design"]["recipes"]),
        "rays_per_point": manifest["design"]["numerics"]["rays_per_point"],
        "canonical_sha256": stage2a.canonical_sha256(manifest),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

"""Build the reduced 500-ray Bosch interaction-discovery manifest."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

import build_v3_pattern_bosch_stage2a as design_tools
import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
QUALIFICATION = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_qualification_review.json"
SOURCE = ROOT / ".scratch/full-traveler-autoresearch/v3_pattern_bosch_stage2a_manifest.json"
DEFAULT_OUTPUT = ROOT / ".scratch/full-traveler-autoresearch/v3_bosch_cheap_interactions_manifest.json"
ROWS = Path("autoresearch-results/restart_audit/v3_bosch_cheap_interactions_rows.jsonl")
INTERACTIONS = (
    ("etch_time", "deposition_thickness"),
    ("etch_time", "ion_rate"),
    ("etch_time", "neutral_rate"),
    ("etch_time", "neutral_sticking_probability"),
    ("neutral_rate", "neutral_sticking_probability"),
    ("ion_source_exponent", "ion_rate"),
    ("ion_source_exponent", "deposition_thickness"),
)


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


def build_manifest():
    qualification = gate0.strict_json_loads(QUALIFICATION.read_text())
    if qualification.get("decision", {}).get("pass") is not True:
        raise ValueError("500-ray qualification did not pass")
    source = gate0.strict_json_loads(SOURCE.read_text())
    source_errors = stage2a.validate_manifest(source, check_runtime=False)
    if source_errors:
        raise ValueError("source Stage 2a manifest is invalid: " + "; ".join(source_errors))
    factors = {row["name"]: row for row in source["design"]["factors"]}
    nominal = {name: row["nominal"] for name, row in factors.items()}
    recipes = []
    for first, second in INTERACTIONS:
        for first_level in ("low", "high"):
            for second_level in ("low", "high"):
                recipe = dict(nominal)
                recipe[first] = factors[first][first_level]
                recipe[second] = factors[second][second_level]
                recipes.append({
                    "recipe_id": "v3cheapint_" + stage2a.canonical_sha256(recipe)[:12],
                    "design_class": "exact_interaction_corner",
                    "anchor_reasons": [
                        f"interaction:{first}:{second}:{first_level}:{second_level}"
                    ],
                    "normalized_coordinates": {
                        name: design_tools.to_unit(factors[name], value)
                        for name, value in recipe.items()
                    },
                    "recipe": recipe,
                })
    if len(recipes) != 28 or len({row["recipe_id"] for row in recipes}) != 28:
        raise ValueError("interaction matrix is not 28 unique recipes")

    design = copy.deepcopy(source["design"])
    design["campaign"] = "v3-bosch-cheap-interactions"
    design["question"] = (
        "Which predeclared two-control combinations amplify, cancel, or move the "
        "Bosch reachability and morphology failure boundaries?"
    )
    design["evidence_class"] = "qualified 500-ray exact interaction discovery"
    design["numerics"]["rays_per_point"] = 500
    design["trajectory"]["early_stop_depth"] = 1.36
    design["rng_policy"].update({
        "seed_start": 930000,
        "interval_count": len(recipes),
        "assignment": "one disjoint interval per exact interaction corner",
        "interpretation": "interaction discovery only; 2,000-ray confirmation required",
    })
    design["recipes"] = recipes
    design["predeclared_interactions"] = [
        {"factors": list(pair), "basis": "mechanism or strong main-effect coupling"}
        for pair in INTERACTIONS
    ]
    design["design"] = {
        "method": "seven exact 2x2 interaction corner blocks around the nominal recipe",
        "interaction_count": len(INTERACTIONS),
        "corners_per_interaction": 4,
        "recipe_count": len(recipes),
        "logical_simulation_count": len(recipes),
        "shared_main_effect_source": "completed 500-ray qualification anchors",
    }
    design["authority"] = {
        "interaction_hypothesis_discovery_only": True,
        "confirmed_interaction_authorized": False,
        "recipe_authorized": False,
        "process_window_authorized": False,
        "full_traveler_authorized": False,
    }
    return {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": "v3-bosch-cheap-interactions",
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
            "stage2a_manifest": {"path": str(SOURCE.relative_to(ROOT)), "sha256": stage2a.file_sha256(SOURCE)},
            "qualification_review": {"path": str(QUALIFICATION.relative_to(ROOT)), "sha256": stage2a.file_sha256(QUALIFICATION)},
        },
        "authority": design["authority"],
        "provenance": {
            "qualified_discovery_rays_per_point": 500,
            "confirmation_rays_per_point": 2000,
            "existing_artifacts_preserved": True,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest()
    if args.check:
        expected = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if not args.output.is_file() or args.output.read_text() != expected:
            raise ValueError(f"stale or missing manifest: {args.output}")
    else:
        freeze(args.output.resolve(), manifest)
    print(json.dumps({
        "campaign": manifest["campaign"],
        "interactions": len(INTERACTIONS),
        "simulations": len(manifest["design"]["recipes"]),
        "rays_per_point": manifest["design"]["numerics"]["rays_per_point"],
        "canonical_sha256": stage2a.canonical_sha256(manifest),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

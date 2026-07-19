"""Build an 18-case interior Bosch response-surface refinement."""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
import os
from pathlib import Path

import numpy as np

import build_v3_bosch_cheap_interactions as interactions
import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".scratch/full-traveler-autoresearch/v3_pattern_bosch_stage2a_manifest.json"
INTERACTION_REVIEW = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_interactions_review.json"
QUALIFICATION_MANIFEST = ROOT / ".scratch/full-traveler-autoresearch/v3_bosch_cheap_qualification_manifest.json"
INTERACTION_MANIFEST = ROOT / ".scratch/full-traveler-autoresearch/v3_bosch_cheap_interactions_manifest.json"
DEFAULT_OUTPUT = ROOT / ".scratch/full-traveler-autoresearch/v3_bosch_interior_refinement_manifest.json"
ROWS = Path("autoresearch-results/restart_audit/v3_bosch_interior_refinement_rows.jsonl")
FACTORS = (
    "etch_time",
    "deposition_thickness",
    "ion_source_exponent",
    "ion_rate",
    "neutral_rate",
    "neutral_sticking_probability",
)
LEVELS = (-0.5, 0.0, 0.5)


def coded_value(factor, code):
    if code == 0.0:
        return factor["nominal"]
    first = factor["low"] if code < 0 else factor["nominal"]
    second = factor["nominal"] if code < 0 else factor["high"]
    fraction = 0.5
    if factor["transform"] == "log":
        value = math.exp(math.log(first) + fraction * (math.log(second) - math.log(first)))
    elif factor["transform"] == "signed_log_magnitude":
        value = -math.exp(
            math.log(abs(first))
            + fraction * (math.log(abs(second)) - math.log(abs(first)))
        )
    else:
        value = first + fraction * (second - first)
    if factor["type"] == "int":
        return int(round(value))
    return round(value, int(factor.get("digits", 10)))


def encode(factor, value):
    value = float(value)
    low, nominal, high = map(float, (factor["low"], factor["nominal"], factor["high"]))
    if math.isclose(value, nominal, rel_tol=0.0, abs_tol=1e-12):
        return 0.0
    if factor["transform"] == "log":
        def transform(current):
            return math.log(current)
    elif factor["transform"] == "signed_log_magnitude":
        def transform(current):
            return math.log(abs(current))
    else:
        def transform(current):
            return current
    if value < nominal:
        return -(transform(nominal) - transform(value)) / (transform(nominal) - transform(low))
    return (transform(value) - transform(nominal)) / (transform(high) - transform(nominal))


def terms(vector):
    vector = np.asarray(vector, dtype=float)
    values = [1.0, *vector, *(vector * vector)]
    index = {name: position for position, name in enumerate(FACTORS)}
    values.extend(vector[index[first]] * vector[index[second]] for first, second in interactions.INTERACTIONS)
    return np.asarray(values, dtype=float)


def prior_matrix(source, factor_by_name):
    rows = []
    for path in (QUALIFICATION_MANIFEST, INTERACTION_MANIFEST):
        manifest = gate0.strict_json_loads(path.read_text())
        for row in manifest["design"]["recipes"]:
            rows.append(terms([
                encode(factor_by_name[name], row["recipe"][name]) for name in FACTORS
            ]))
    return np.vstack(rows)


def select_design(source, factor_by_name, count=18):
    candidates = np.asarray(list(itertools.product(LEVELS, repeat=len(FACTORS))), dtype=float)
    candidates = candidates[np.any(candidates != 0.0, axis=1)]
    prior = prior_matrix(source, factor_by_name)
    information = prior.T @ prior + np.eye(prior.shape[1]) * 1e-9
    selected = []
    remaining = list(range(len(candidates)))
    for _ in range(count):
        best = None
        for index in remaining:
            row = terms(candidates[index])
            sign, logdet = np.linalg.slogdet(information + np.outer(row, row))
            if sign <= 0:
                continue
            distance = min(
                (float(np.linalg.norm(candidates[index] - candidates[other])) for other in selected),
                default=float(np.linalg.norm(candidates[index])),
            )
            score = (float(logdet), distance)
            if best is None or score > best[0]:
                best = (score, index, row)
        if best is None:
            raise ValueError("D-optimal selection failed")
        _, index, row = best
        selected.append(index)
        remaining.remove(index)
        information += np.outer(row, row)
    matrix = np.vstack([terms(candidates[index]) for index in selected])
    combined = np.vstack([prior, matrix])
    return candidates[selected], {
        "term_count": int(combined.shape[1]),
        "combined_row_count": int(combined.shape[0]),
        "combined_rank": int(np.linalg.matrix_rank(combined)),
        "information_condition_number": float(np.linalg.cond(combined.T @ combined)),
        "selection": "greedy D-optimal augmentation of completed qualification and interaction blocks",
    }


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
    review = gate0.strict_json_loads(INTERACTION_REVIEW.read_text())
    if review.get("decision", {}).get("interaction_discovery_complete") is not True:
        raise ValueError("interaction review is not complete")
    source = gate0.strict_json_loads(SOURCE.read_text())
    source_errors = stage2a.validate_manifest(source, check_runtime=False)
    if source_errors:
        raise ValueError("source Stage 2a manifest is invalid: " + "; ".join(source_errors))
    factor_by_name = {factor["name"]: factor for factor in source["design"]["factors"]}
    coordinates, preflight = select_design(source, factor_by_name)
    if preflight["combined_rank"] != preflight["term_count"]:
        raise ValueError("combined response-surface design is rank deficient")
    nominal = {name: factor["nominal"] for name, factor in factor_by_name.items()}
    recipes = []
    for coordinate in coordinates:
        recipe = dict(nominal)
        for index, name in enumerate(FACTORS):
            recipe[name] = coded_value(factor_by_name[name], float(coordinate[index]))
        recipes.append({
            "recipe_id": "v3interior_" + stage2a.canonical_sha256(recipe)[:12],
            "design_class": "d_optimal_interior_half_step",
            "anchor_reasons": ["interior_response_surface"],
            "normalized_coordinates": {
                name: float(coordinate[index]) for index, name in enumerate(FACTORS)
            },
            "recipe": recipe,
        })
    if len(recipes) != 18 or len({row["recipe_id"] for row in recipes}) != 18:
        raise ValueError("interior design is not 18 unique recipes")

    design = copy.deepcopy(source["design"])
    design["campaign"] = "v3-bosch-interior-refinement"
    design["question"] = (
        "Within transformed half-steps around nominal, where is the feasible Bosch "
        "response surface and which 3-5 candidates merit 2,000-ray confirmation?"
    )
    design["evidence_class"] = "qualified 500-ray interior response-surface refinement"
    design["numerics"]["rays_per_point"] = 500
    design["trajectory"]["early_stop_depth"] = 1.36
    design["rng_policy"].update({
        "seed_start": 940000,
        "interval_count": len(recipes),
        "assignment": "one disjoint interval per interior recipe",
        "interpretation": "interior discovery only; independent 2,000-ray confirmation required",
    })
    design["recipes"] = recipes
    design["predeclared_interactions"] = [
        {"factors": list(pair), "basis": "promoted by exact interaction discovery"}
        for pair in interactions.INTERACTIONS
    ]
    design["design"] = {
        "method": preflight["selection"],
        "levels": list(LEVELS),
        "level_definition": "halfway in each factor's declared transform between low/nominal or nominal/high",
        "recipe_count": len(recipes),
        "logical_simulation_count": len(recipes),
        "preflight": preflight,
    }
    design["authority"] = {
        "interior_refinement_only": True,
        "recipe_authorized": False,
        "process_window_authorized": False,
        "full_traveler_authorized": False,
    }
    return {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": "v3-bosch-interior-refinement",
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
            "interaction_review": {"path": str(INTERACTION_REVIEW.relative_to(ROOT)), "sha256": stage2a.file_sha256(INTERACTION_REVIEW)},
            "qualification_manifest": {"path": str(QUALIFICATION_MANIFEST.relative_to(ROOT)), "sha256": stage2a.file_sha256(QUALIFICATION_MANIFEST)},
            "interaction_manifest": {"path": str(INTERACTION_MANIFEST.relative_to(ROOT)), "sha256": stage2a.file_sha256(INTERACTION_MANIFEST)},
        },
        "authority": design["authority"],
        "provenance": {
            "qualified_discovery_rays_per_point": 500,
            "confirmation_rays_per_point": 2000,
            "rejected_extreme_corners_reused": False,
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
        "simulations": len(manifest["design"]["recipes"]),
        "combined_rank": manifest["design"]["design"]["preflight"]["combined_rank"],
        "term_count": manifest["design"]["design"]["preflight"]["term_count"],
        "canonical_sha256": stage2a.canonical_sha256(manifest),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

"""Build the deterministic 160-recipe broad pattern/Bosch screen."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np


DEFAULT_SPEC = Path(
    ".scratch/full-traveler-autoresearch/"
    "pattern_bosch_broad_screen_design_spec.json"
)
EXPECTED_LABELS = ["full-traveler", "critical-review"]
EXPECTED_TARGET = {
    "opening_cd": 0.3,
    "mask_height": 0.3,
    "etch_depth": 1.25,
    "depth_tolerance": 0.1,
    "max_width_error": 0.06,
    "max_wall_bulge": 0.03,
    "resolved_mask_cells_strict": 2.0,
}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def strict_load(path):
    def reject(constant):
        raise ValueError(f"non-standard JSON constant: {constant}")

    return json.loads(Path(path).read_text(), parse_constant=reject)


def validate_spec(spec):
    errors = []
    if spec.get("labels") != EXPECTED_LABELS:
        errors.append("required labels differ")
    if spec.get("recipe_count") != 160:
        errors.append("broad screen must contain 160 recipes")
    if spec.get("target") != EXPECTED_TARGET:
        errors.append("declared product targets differ")
    if spec.get("geometry") != {
        "hole_shape": "FULL", "x_extent": 1.0, "y_extent": 2.0
    }:
        errors.append("full-width geometry contract differs")
    if spec.get("numerics") != {
        "grid_delta": 0.00125,
        "rays_per_point": 2000,
        "threads_per_worker": 7,
        "maximum_workers": 2,
    }:
        errors.append("high-fidelity numerical controls differ")
    trajectory = spec.get("trajectory", {})
    if not (
        trajectory.get("maximum_cycles") == 50
        and trajectory.get("first_scored_cycle") == 1
        and trajectory.get("early_stop_depth") == 1.45
        and trajectory.get("record_all_scored_cycles") is True
        and "depth" in trajectory.get("selection", "")
    ):
        errors.append("depth-matched trajectory contract differs")
    factors = spec.get("factors", [])
    names = [factor.get("name") for factor in factors]
    if len(factors) != 13 or len(names) != len(set(names)):
        errors.append("exactly 13 unique factors are required")
    if "num_cycles" in names:
        errors.append("cycle count must be selected by depth, not swept")
    reference = spec.get("reference", {})
    if set(reference) != set(names):
        errors.append("reference recipe fields differ from the factor registry")
    for factor in factors:
        name = factor.get("name")
        low, high = factor.get("low"), factor.get("high")
        if not (
            isinstance(low, (int, float))
            and isinstance(high, (int, float))
            and not isinstance(low, bool)
            and not isinstance(high, bool)
            and math.isfinite(float(low))
            and math.isfinite(float(high))
            and low < high
        ):
            errors.append(f"{name}: invalid range")
            continue
        if factor.get("scale") not in ("linear", "log"):
            errors.append(f"{name}: invalid scale")
        if factor.get("scale") == "log" and low <= 0:
            errors.append(f"{name}: log range must be positive")
        if factor.get("type") not in ("float", "int"):
            errors.append(f"{name}: invalid type")
        value = reference.get(name)
        if not isinstance(value, (int, float)) or not low <= value <= high:
            errors.append(f"{name}: reference lies outside the range")
        if factor.get("screen_mode", "joint") not in ("joint", "anchor_only"):
            errors.append(f"{name}: invalid screen mode")
    stress = spec.get("mask_height_erosion_stress")
    if stress != {
        "mask_height": [0.24, 0.27, 0.3, 0.33, 0.36],
        "mask_ion_rate": [0.0, -0.01, -0.02, -0.04],
    }:
        errors.append("mask-height-by-erosion stress block differs")
    if next(
        (factor.get("screen_mode", "joint") for factor in factors
         if factor.get("name") == "mask_height"), None
    ) != "anchor_only":
        errors.append("mask height must be anchor-only in the joint screen")
    maximum_cycles = trajectory.get("maximum_cycles", 0)
    horizon = 1 + 3 * maximum_cycles
    seeds = spec.get("rng_base_seeds", [])
    if len(seeds) != 4 or len(set(seeds)) != 4:
        errors.append("exactly four unique base seeds are required")
    if any(
        abs(first - second) < horizon
        for index, first in enumerate(seeds)
        for second in seeds[index + 1:]
    ):
        errors.append("Bosch replicate streams overlap")
    authority = spec.get("authority", {})
    if any(authority.get(key) is not False for key in (
        "recipe_authorized",
        "process_window_authorized",
        "downstream_recipe_authorized",
        "full_traveler_authorized",
        "automatic_launch_authorized",
    )):
        errors.append("broad-screen authority was expanded")
    review = spec.get("review", {})
    if not (
        review.get("row_recompute_abs_tolerance") == 1e-12
        and review.get("invalid_metric_penalty") == 1000000.0
        and review.get("primitive_hard_gate_penalty") == 1000.0
        and review.get("boundary_warning_fraction") == 0.02
        and review.get("p90_quantile_method") == "linear"
        and review.get("primitive_gates") == [
            "selection_eligible",
            "pattern_width",
            "pattern_height",
            "pattern_opening",
            "etch_depth",
            "etch_cd_profile",
            "etch_bow",
            "etch_mask_resolved",
        ]
    ):
        errors.append("review ranking or penalty contract differs")
    if errors:
        raise ValueError("invalid pattern/Bosch design spec: " + "; ".join(errors))


def from_unit(factor, coordinate):
    low, high = float(factor["low"]), float(factor["high"])
    if factor["scale"] == "log":
        value = math.exp(math.log(low) + coordinate * (math.log(high) - math.log(low)))
    else:
        value = low + coordinate * (high - low)
    if factor["type"] == "int":
        return int(round(value))
    return round(value, int(factor.get("digits", 10)))


def to_unit(factor, value):
    low, high = float(factor["low"]), float(factor["high"])
    value = float(value)
    if factor["scale"] == "log":
        return (math.log(value) - math.log(low)) / (math.log(high) - math.log(low))
    return (value - low) / (high - low)


def latin_hypercube(count, dimensions, rng):
    points = np.empty((count, dimensions), dtype=float)
    for column in range(dimensions):
        points[:, column] = (
            rng.permutation(count) + rng.random(count)
        ) / count
    return points


def space_filling_score(points, anchors):
    differences = points[:, None, :] - points[None, :, :]
    squared = np.sum(differences * differences, axis=2)
    squared[np.diag_indices_from(squared)] = np.inf
    within = float(np.sqrt(np.min(squared)))
    to_anchor = float(np.sqrt(np.min(np.sum(
        (points[:, None, :] - anchors[None, :, :]) ** 2, axis=2
    ))))
    correlation = np.corrcoef(points, rowvar=False)
    off_diagonal = correlation[~np.eye(correlation.shape[0], dtype=bool)]
    max_correlation = float(np.max(np.abs(off_diagonal)))
    minimum_distance = min(within, to_anchor)
    return (
        minimum_distance - 0.10 * max_correlation,
        minimum_distance,
        -max_correlation,
    )


def anchor_rows(spec):
    factors = spec["factors"]
    reference = dict(spec["reference"])
    rows = {}

    def add(recipe, reason):
        key = canonical_json(recipe)
        if key not in rows:
            rows[key] = {"recipe": recipe, "anchor_reasons": []}
        rows[key]["anchor_reasons"].append(reason)

    add(reference, "reference")
    center = {
        factor["name"]: from_unit(factor, 0.5)
        for factor in factors
    }
    add(center, "range_center")
    for factor in factors:
        for boundary, coordinate in (("low", 0.0), ("high", 1.0)):
            recipe = dict(reference)
            recipe[factor["name"]] = from_unit(factor, coordinate)
            add(recipe, f"{factor['name']}:{boundary}")
    stress = spec["mask_height_erosion_stress"]
    for height in stress["mask_height"]:
        for erosion in stress["mask_ion_rate"]:
            recipe = dict(reference)
            recipe["mask_height"] = height
            recipe["mask_ion_rate"] = erosion
            add(recipe, f"mask_height_erosion:{height:g}:{erosion:g}")
    result = []
    for row in rows.values():
        coordinates = {
            factor["name"]: to_unit(factor, row["recipe"][factor["name"]])
            for factor in factors
        }
        result.append({
            "design_class": "anchor",
            "anchor_reasons": sorted(row["anchor_reasons"]),
            "normalized_coordinates": coordinates,
            "recipe": row["recipe"],
        })
    return result


def build_design(spec):
    validate_spec(spec)
    factors = spec["factors"]
    joint_factors = [
        factor for factor in factors
        if factor.get("screen_mode", "joint") == "joint"
    ]
    anchors = anchor_rows(spec)
    lhs_count = spec["recipe_count"] - len(anchors)
    anchor_coordinates = np.asarray([
        [row["normalized_coordinates"][factor["name"]] for factor in joint_factors]
        for row in anchors
    ])
    master = np.random.default_rng(int(spec["design_seed"]))
    best_points = None
    best_score = None
    for _ in range(int(spec["lhs_candidate_count"])):
        candidate = latin_hypercube(
            lhs_count, len(joint_factors),
            np.random.default_rng(int(master.integers(0, 2**63 - 1))),
        )
        score = space_filling_score(candidate, anchor_coordinates)
        if best_score is None or score > best_score:
            best_points, best_score = candidate, score
    lhs_rows = []
    for index, point in enumerate(best_points):
        recipe = dict(spec["reference"])
        recipe.update({
            factor["name"]: from_unit(factor, float(point[column]))
            for column, factor in enumerate(joint_factors)
        })
        coordinates = {
            factor["name"]: to_unit(factor, recipe[factor["name"]])
            for factor in factors
        }
        coordinates.update({
            factor["name"]: float(point[column])
            for column, factor in enumerate(joint_factors)
        })
        lhs_rows.append({
            "design_class": "latin_hypercube",
            "design_index": index,
            "anchor_reasons": [],
            "normalized_coordinates": coordinates,
            "recipe": recipe,
        })
    rows = anchors + lhs_rows
    for row in rows:
        row["recipe_id"] = "pbs_" + canonical_sha256(row["recipe"])[:12]
    correlation = np.corrcoef(best_points, rowvar=False)
    max_correlation = float(np.max(np.abs(
        correlation[~np.eye(correlation.shape[0], dtype=bool)]
    )))
    output = {
        "schema_version": 1,
        "campaign": spec["campaign"],
        "labels": spec["labels"],
        "spec_sha256": canonical_sha256(spec),
        "question": spec["question"],
        "geometry": spec["geometry"],
        "numerics": spec["numerics"],
        "trajectory": spec["trajectory"],
        "rng_base_seeds": spec["rng_base_seeds"],
        "rng_process_seed_horizon": 1 + 3 * spec["trajectory"]["maximum_cycles"],
        "target": spec["target"],
        "factors": factors,
        "unsupported_physical_controls": spec["unsupported_physical_controls"],
        "prerequisites": spec["prerequisites"],
        "decision_rules": spec["decision_rules"],
        "review": spec["review"],
        "authority": spec["authority"],
        "design": {
            "method": "maximin-selected 12-factor Latin hypercube plus reference, center, every one-factor boundary, and a 5-by-4 mask-height-by-erosion stress block",
            "recipe_count": len(rows),
            "anchor_count": len(anchors),
            "latin_hypercube_count": lhs_count,
            "replicates_per_recipe": len(spec["rng_base_seeds"]),
            "logical_simulation_count": len(rows) * len(spec["rng_base_seeds"]),
            "candidate_designs_compared": spec["lhs_candidate_count"],
            "minimum_normalized_lhs_or_anchor_distance": best_score[1],
            "maximum_absolute_lhs_factor_correlation": max_correlation,
        },
        "recipes": rows,
    }
    errors = validate_design(output, spec)
    if errors:
        raise ValueError("generated design is invalid: " + "; ".join(errors))
    return output


def validate_design(design, spec):
    errors = []
    factors = spec["factors"]
    joint_factors = [
        factor for factor in factors
        if factor.get("screen_mode", "joint") == "joint"
    ]
    names = [factor["name"] for factor in factors]
    rows = design.get("recipes", [])
    if len(rows) != 160:
        errors.append("recipe count differs")
    if len({row.get("recipe_id") for row in rows}) != len(rows):
        errors.append("recipe IDs are not unique")
    if len({canonical_json(row.get("recipe")) for row in rows}) != len(rows):
        errors.append("factor combinations are not unique")
    for row in rows:
        recipe = row.get("recipe", {})
        if set(recipe) != set(names):
            errors.append(f"{row.get('recipe_id')}: factor fields differ")
            continue
        for factor in factors:
            value = recipe[factor["name"]]
            if not factor["low"] <= value <= factor["high"]:
                errors.append(f"{row.get('recipe_id')}: factor outside range")
    reasons = {
        reason for row in rows for reason in row.get("anchor_reasons", [])
    }
    expected_reasons = {"reference", "range_center"} | {
        f"{name}:{boundary}" for name in names for boundary in ("low", "high")
    }
    if not expected_reasons.issubset(reasons):
        errors.append("reference, center, or boundary anchors are missing")
    lhs = [row for row in rows if row.get("design_class") == "latin_hypercube"]
    if len(lhs) != design.get("design", {}).get("latin_hypercube_count"):
        errors.append("Latin-hypercube count differs")
    for name in (factor["name"] for factor in joint_factors):
        coordinates = [row["normalized_coordinates"][name] for row in lhs]
        strata = {min(int(value * len(lhs)), len(lhs) - 1) for value in coordinates}
        if len(strata) != len(lhs):
            errors.append(f"{name}: Latin-hypercube strata are not unique")
    anchor_only = [
        factor["name"] for factor in factors
        if factor.get("screen_mode") == "anchor_only"
    ]
    for name in anchor_only:
        if any(row["recipe"][name] != spec["reference"][name] for row in lhs):
            errors.append(f"{name}: anchor-only factor varies in the joint LHS")
    if design.get("design", {}).get("logical_simulation_count") != 640:
        errors.append("logical simulation count differs")
    if design.get("labels") != EXPECTED_LABELS:
        errors.append("generated labels differ")
    if design.get("target") != EXPECTED_TARGET:
        errors.append("generated targets differ")
    return errors


def write_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(
        value, indent=2, sort_keys=True, allow_nan=False
    ) + "\n")
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    spec = strict_load(args.spec)
    design = build_design(spec)
    if args.output:
        write_atomic(args.output, design)
    print(json.dumps({
        "recipes": design["design"]["recipe_count"],
        "simulations": design["design"]["logical_simulation_count"],
        "anchors": design["design"]["anchor_count"],
        "lhs": design["design"]["latin_hypercube_count"],
        "max_abs_factor_correlation": design["design"][
            "maximum_absolute_lhs_factor_correlation"
        ],
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

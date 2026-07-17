"""Build the deterministic broad-first Bosch discovery design."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

import build_pattern_bosch_screen_design as common
import foundation_pattern_bosch_gate0 as gate0


DEFAULT_SPEC = Path(
    ".scratch/full-traveler-autoresearch/"
    "pattern_bosch_discovery_s1_spec.json"
)
EXPECTED_FACTOR_NAMES = (
    "etch_time",
    "initial_etch_time",
    "neutral_rate",
    "neutral_sticking_probability",
    "deposition_thickness",
    "deposition_sticking_probability",
    "ion_source_exponent",
    "theta_r_min",
    "ion_rate",
)


def from_unit(factor, coordinate):
    low, high = float(factor["low"]), float(factor["high"])
    scale = factor["scale"]
    if scale == "log":
        value = math.exp(math.log(low) + coordinate * (math.log(high) - math.log(low)))
    elif scale == "signed_log_magnitude":
        value = -math.exp(
            math.log(abs(low))
            + coordinate * (math.log(abs(high)) - math.log(abs(low)))
        )
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
    if factor["scale"] == "signed_log_magnitude":
        return (
            math.log(abs(value)) - math.log(abs(low))
        ) / (math.log(abs(high)) - math.log(abs(low)))
    return (value - low) / (high - low)


def validate_spec(spec):
    errors = []
    if spec.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("required labels differ")
    if spec.get("recipe_count") != 96:
        errors.append("discovery design must contain 96 recipes")
    if spec.get("geometry") != {
        "hole_shape": "FULL",
        "radius": 0.15,
        "mask_height": 0.3,
        "mask_taper": 2.0,
        "x_extent": 1.0,
        "y_extent": 2.0,
    }:
        errors.append("nominal full-width geometry differs")
    if spec.get("fixed_recipe") != {"mask_ion_rate": 0.0}:
        errors.append("fixed mask-erosion control differs")
    if spec.get("numerics") != {
        "grid_delta": 0.00125,
        "rays_per_point": 1000,
        "fidelity_anchor_rays_per_point": 2000,
        "threads_per_worker": 7,
        "maximum_workers": 2,
        "dimension": 2,
    }:
        errors.append("discovery numerical controls differ")
    trajectory = spec.get("trajectory", {})
    if not (
        trajectory.get("maximum_cycles") == 30
        and trajectory.get("first_scored_cycle") == 1
        and trajectory.get("early_stop_depth") == 1.45
        and trajectory.get("record_all_scored_cycles") is True
        and "depth" in trajectory.get("selection", "")
    ):
        errors.append("depth-matched trajectory differs")
    if spec.get("target") != gate0.EXPECTED_TARGET:
        errors.append("product targets differ")
    factors = spec.get("factors", [])
    names = tuple(factor.get("name") for factor in factors)
    if names != EXPECTED_FACTOR_NAMES:
        errors.append("exact nine-factor registry differs")
    if set(spec.get("reference", {})) != set(EXPECTED_FACTOR_NAMES):
        errors.append("reference recipe fields differ")
    for factor in factors:
        name = factor.get("name")
        low, high = factor.get("low"), factor.get("high")
        if not (
            isinstance(low, (int, float))
            and not isinstance(low, bool)
            and isinstance(high, (int, float))
            and not isinstance(high, bool)
            and math.isfinite(float(low))
            and math.isfinite(float(high))
            and low < high
        ):
            errors.append(f"{name}: invalid range")
            continue
        if factor.get("scale") not in (
            "linear", "log", "signed_log_magnitude"
        ):
            errors.append(f"{name}: invalid scale")
        if factor.get("scale") == "log" and low <= 0:
            errors.append(f"{name}: log range must be positive")
        if factor.get("scale") == "signed_log_magnitude" and not (low < high < 0):
            errors.append(f"{name}: signed-log range must be strictly negative")
        if factor.get("type") not in ("float", "int"):
            errors.append(f"{name}: invalid type")
        if not isinstance(factor.get("range_basis"), str) or not factor[
            "range_basis"
        ].strip():
            errors.append(f"{name}: range basis is missing")
        reference = spec["reference"].get(name)
        if not isinstance(reference, (int, float)) or not low <= reference <= high:
            errors.append(f"{name}: reference outside range")
    horizon = 1 + 3 * trajectory.get("maximum_cycles", 0)
    if spec.get("rng_policy") != {
        "seed_start": 71000,
        "base_replicates_per_recipe": 2,
        "sentinel_extra_replicates_per_recipe": 2,
        "interval_stride": horizon,
        "assignment": (
            "deterministic globally non-overlapping process-seed intervals; "
            "only a same-recipe 1000-versus-2000-ray fidelity pair may reuse "
            "an interval"
        ),
    }:
        errors.append("globally disjoint discovery seed policy differs")
    if spec.get("sentinel_policy") != {
        "replicated_recipe_count": 12,
        "fidelity_recipe_count": 8,
        "selection": (
            "deterministic farthest-first coverage in normalized nine-factor "
            "space, seeded by reference, center, and prior-study anchors"
        ),
    }:
        errors.append("sentinel policy differs")
    prior = spec.get("prior_anchors", [])
    if [row.get("name") for row in prior] != [
        "precursor", "dry_etch_best", "legacy_depth_matched_failure"
    ]:
        errors.append("prior-anchor declarations differ")
    elif any(set(row.get("recipe", {})) != set(EXPECTED_FACTOR_NAMES) for row in prior):
        errors.append("prior-anchor recipe fields differ")
    interactions = spec.get("predeclared_interactions", [])
    if len(interactions) != 6 or any(
        len(pair) != 2 or not set(pair).issubset(EXPECTED_FACTOR_NAMES)
        for pair in interactions
    ) or len({tuple(pair) for pair in interactions}) != 6:
        errors.append("exact six predeclared interactions are required")
    authority = spec.get("authority", {})
    if authority.get("factor_screening_only") is not True or any(
        authority.get(key) is not False
        for key in (
            "recipe_authorized",
            "process_window_authorized",
            "downstream_recipe_authorized",
            "full_traveler_authorized",
            "automatic_launch_authorized",
        )
    ):
        errors.append("discovery authority was expanded")
    if errors:
        raise ValueError("invalid Bosch discovery spec: " + "; ".join(errors))


def anchor_rows(spec):
    factors = spec["factors"]
    reference = dict(spec["reference"])
    rows = {}

    def add(recipe, reason):
        key = common.canonical_json(recipe)
        rows.setdefault(key, {"recipe": recipe, "anchor_reasons": []})[
            "anchor_reasons"
        ].append(reason)

    add(reference, "reference")
    add(
        {factor["name"]: from_unit(factor, 0.5) for factor in factors},
        "range_center",
    )
    for factor in factors:
        for edge, coordinate in (("low", 0.0), ("high", 1.0)):
            recipe = dict(reference)
            recipe[factor["name"]] = from_unit(factor, coordinate)
            add(recipe, f"{factor['name']}:{edge}")
    for prior in spec["prior_anchors"]:
        add(dict(prior["recipe"]), f"prior:{prior['name']}")
    return [
        {
            "design_class": "anchor",
            "anchor_reasons": sorted(row["anchor_reasons"]),
            "normalized_coordinates": {
                factor["name"]: to_unit(
                    factor, row["recipe"][factor["name"]]
                )
                for factor in factors
            },
            "recipe": row["recipe"],
        }
        for row in rows.values()
    ]


def farthest_first(rows, count, seed_reasons):
    by_reason = {
        reason: row
        for row in rows
        for reason in row.get("anchor_reasons", [])
    }
    selected = []
    for reason in seed_reasons:
        row = by_reason.get(reason)
        if row is not None and row not in selected:
            selected.append(row)
    factor_names = EXPECTED_FACTOR_NAMES
    while len(selected) < count:
        remaining = [row for row in rows if row not in selected]

        def distance(row):
            vector = np.asarray([
                row["normalized_coordinates"][name] for name in factor_names
            ])
            return min(
                float(np.linalg.norm(vector - np.asarray([
                    other["normalized_coordinates"][name] for name in factor_names
                ])))
                for other in selected
            )

        selected.append(max(
            remaining,
            key=lambda row: (distance(row), row["recipe_id"]),
        ))
    return [row["recipe_id"] for row in selected]


def build_design(spec):
    validate_spec(spec)
    factors = spec["factors"]
    anchors = anchor_rows(spec)
    lhs_count = spec["recipe_count"] - len(anchors)
    anchor_coordinates = np.asarray([
        [row["normalized_coordinates"][factor["name"]] for factor in factors]
        for row in anchors
    ])
    master = np.random.default_rng(int(spec["design_seed"]))
    best_points = best_score = None
    for _ in range(int(spec["lhs_candidate_count"])):
        candidate = common.latin_hypercube(
            lhs_count,
            len(factors),
            np.random.default_rng(int(master.integers(0, 2**63 - 1))),
        )
        score = common.space_filling_score(candidate, anchor_coordinates)
        if best_score is None or score > best_score:
            best_points, best_score = candidate, score
    lhs = []
    for index, point in enumerate(best_points):
        recipe = {
            factor["name"]: from_unit(factor, float(point[column]))
            for column, factor in enumerate(factors)
        }
        lhs.append({
            "design_class": "latin_hypercube",
            "design_index": index,
            "anchor_reasons": [],
            "normalized_coordinates": {
                factor["name"]: float(point[column])
                for column, factor in enumerate(factors)
            },
            "recipe": recipe,
        })
    rows = anchors + lhs
    for row in rows:
        row["recipe_id"] = "pbds1_" + common.canonical_sha256(row["recipe"])[:12]
    sentinel_seed_reasons = (
        "reference",
        "range_center",
        "prior:precursor",
        "prior:dry_etch_best",
        "prior:legacy_depth_matched_failure",
    )
    sentinel_ids = farthest_first(
        rows,
        spec["sentinel_policy"]["replicated_recipe_count"],
        sentinel_seed_reasons,
    )
    sentinel_rows = [row for row in rows if row["recipe_id"] in sentinel_ids]
    fidelity_ids = farthest_first(
        sentinel_rows,
        spec["sentinel_policy"]["fidelity_recipe_count"],
        sentinel_seed_reasons,
    )
    correlation = np.corrcoef(best_points, rowvar=False)
    off_diagonal = correlation[~np.eye(correlation.shape[0], dtype=bool)]
    result = {
        "schema_version": 1,
        "campaign": spec["campaign"],
        "labels": spec["labels"],
        "spec_sha256": common.canonical_sha256(spec),
        "question": spec["question"],
        "geometry": spec["geometry"],
        "fixed_recipe": spec["fixed_recipe"],
        "numerics": spec["numerics"],
        "trajectory": spec["trajectory"],
        "rng_policy": spec["rng_policy"],
        "rng_process_seed_horizon": 1 + 3 * spec["trajectory"]["maximum_cycles"],
        "target": spec["target"],
        "factors": factors,
        "predeclared_interactions": spec["predeclared_interactions"],
        "decision_rules": spec["decision_rules"],
        "authority": spec["authority"],
        "design": {
            "method": "nine-factor maximin-selected Latin hypercube plus reference, center, every one-factor boundary, and three prior-study anchors",
            "recipe_count": len(rows),
            "anchor_count": len(anchors),
            "latin_hypercube_count": len(lhs),
            "replicates_per_recipe": spec["rng_policy"][
                "base_replicates_per_recipe"
            ],
            "base_simulation_count": len(rows) * spec["rng_policy"][
                "base_replicates_per_recipe"
            ],
            "sentinel_extra_simulation_count": len(sentinel_ids) * spec[
                "rng_policy"
            ]["sentinel_extra_replicates_per_recipe"],
            "fidelity_simulation_count": len(fidelity_ids) * spec[
                "rng_policy"
            ]["base_replicates_per_recipe"],
            "logical_simulation_count": (
                len(rows) * spec["rng_policy"]["base_replicates_per_recipe"]
                + len(sentinel_ids) * spec["rng_policy"][
                    "sentinel_extra_replicates_per_recipe"
                ]
                + len(fidelity_ids) * spec["rng_policy"][
                    "base_replicates_per_recipe"
                ]
            ),
            "candidate_designs_compared": spec["lhs_candidate_count"],
            "minimum_normalized_lhs_or_anchor_distance": best_score[1],
            "maximum_absolute_lhs_factor_correlation": float(
                np.max(np.abs(off_diagonal))
            ),
        },
        "sentinels": {
            "replicated_recipe_ids": sentinel_ids,
            "fidelity_recipe_ids": fidelity_ids,
            "extra_replicates_per_recipe": spec["rng_policy"][
                "sentinel_extra_replicates_per_recipe"
            ],
            "fidelity_rays_per_point": spec["numerics"][
                "fidelity_anchor_rays_per_point"
            ],
        },
        "recipes": rows,
    }
    errors = validate_design(result, spec)
    if errors:
        raise ValueError("generated discovery design is invalid: " + "; ".join(errors))
    return result


def validate_design(design, spec):
    errors = []
    rows = design.get("recipes", [])
    factors = spec["factors"]
    if len(rows) != 96 or design.get("design", {}).get(
        "logical_simulation_count"
    ) != 232:
        errors.append("design size differs")
    if len({row.get("recipe_id") for row in rows}) != len(rows):
        errors.append("recipe IDs are not unique")
    if len({common.canonical_json(row.get("recipe")) for row in rows}) != len(rows):
        errors.append("recipes are not unique")
    expected_fields = set(EXPECTED_FACTOR_NAMES)
    for row in rows:
        if set(row.get("recipe", {})) != expected_fields:
            errors.append(f"{row.get('recipe_id')}: recipe fields differ")
    reasons = {reason for row in rows for reason in row.get("anchor_reasons", [])}
    expected_reasons = {"reference", "range_center"} | {
        f"{name}:{edge}"
        for name in EXPECTED_FACTOR_NAMES
        for edge in ("low", "high")
    }
    if not expected_reasons.issubset(reasons):
        errors.append("reference, center, or factor boundaries are missing")
    lhs = [row for row in rows if row.get("design_class") == "latin_hypercube"]
    if len(lhs) != 96 - len(anchor_rows(spec)):
        errors.append("Latin-hypercube count differs")
    for factor in factors:
        coordinates = [row["normalized_coordinates"][factor["name"]] for row in lhs]
        strata = {min(int(value * len(lhs)), len(lhs) - 1) for value in coordinates}
        if len(strata) != len(lhs):
            errors.append(f"{factor['name']}: LHS strata are not unique")
    sentinels = design.get("sentinels", {})
    replicated = sentinels.get("replicated_recipe_ids", [])
    fidelity = sentinels.get("fidelity_recipe_ids", [])
    recipe_ids = {row["recipe_id"] for row in rows}
    if len(replicated) != 12 or len(set(replicated)) != 12 or not set(
        replicated
    ).issubset(recipe_ids):
        errors.append("replicated sentinel selection differs")
    if len(fidelity) != 8 or len(set(fidelity)) != 8 or not set(
        fidelity
    ).issubset(replicated):
        errors.append("fidelity sentinel selection differs")
    by_id = {row["recipe_id"]: row for row in rows}
    required_seed_reasons = {
        "reference",
        "range_center",
        "prior:precursor",
        "prior:dry_etch_best",
        "prior:legacy_depth_matched_failure",
    }
    for selection, name in ((replicated, "replicated"), (fidelity, "fidelity")):
        selected_reasons = {
            reason for recipe_id in selection
            for reason in by_id[recipe_id].get("anchor_reasons", [])
        }
        if not required_seed_reasons.issubset(selected_reasons):
            errors.append(f"{name} sentinels omit a seeded evidence anchor")
    quality = design.get("design", {})
    if quality.get("maximum_absolute_lhs_factor_correlation", 1.0) >= 0.25:
        errors.append("Latin-hypercube factor correlation is too high")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    spec = common.strict_load(args.spec)
    design = build_design(spec)
    if args.output:
        common.write_atomic(args.output, design)
    print(common.canonical_json({
        "recipes": design["design"]["recipe_count"],
        "simulations": design["design"]["logical_simulation_count"],
        "anchors": design["design"]["anchor_count"],
        "lhs": design["design"]["latin_hypercube_count"],
    }))


if __name__ == "__main__":
    main()

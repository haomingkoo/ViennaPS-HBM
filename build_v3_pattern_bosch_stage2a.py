"""Build the frozen-input V3 Stage 2a broad Bosch screening design."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

import build_pattern_bosch_screen_design as common
import foundation_pattern_bosch_gate0 as gate0


DEFAULT_SPEC = Path(
    ".scratch/full-traveler-autoresearch/v3_pattern_bosch_stage2a_spec.json"
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
EXPECTED_INTERACTIONS = (
    ("etch_time", "ion_rate"),
    ("etch_time", "neutral_rate"),
    ("etch_time", "neutral_sticking_probability"),
    ("neutral_rate", "neutral_sticking_probability"),
    ("etch_time", "deposition_thickness"),
    ("deposition_thickness", "deposition_sticking_probability"),
    ("ion_source_exponent", "theta_r_min"),
)


def from_unit(factor, coordinate):
    low, high = float(factor["low"]), float(factor["high"])
    transform = factor["transform"]
    if transform == "log":
        value = math.exp(math.log(low) + coordinate * (math.log(high) - math.log(low)))
    elif transform == "signed_log_magnitude":
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
    if factor["transform"] == "log":
        return (math.log(value) - math.log(low)) / (math.log(high) - math.log(low))
    if factor["transform"] == "signed_log_magnitude":
        return (
            math.log(abs(value)) - math.log(abs(low))
        ) / (math.log(abs(high)) - math.log(abs(low)))
    return (value - low) / (high - low)


def average_ranks(values):
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + end - 1)
        start = end
    return ranks


def _off_diagonal_max(matrix):
    mask = ~np.eye(matrix.shape[0], dtype=bool)
    return float(np.max(np.abs(matrix[mask])))


def correlation_vif_preflight(matrix):
    matrix = np.asarray(matrix, dtype=float)
    pearson = np.corrcoef(matrix, rowvar=False)
    ranked = np.column_stack([average_ranks(matrix[:, index]) for index in range(matrix.shape[1])])
    spearman = np.corrcoef(ranked, rowvar=False)
    try:
        vifs = np.diag(np.linalg.inv(pearson))
    except np.linalg.LinAlgError:
        vifs = np.full(matrix.shape[1], np.inf)
    return {
        "pearson_matrix": pearson.tolist(),
        "spearman_matrix": spearman.tolist(),
        "maximum_absolute_pearson": _off_diagonal_max(pearson),
        "maximum_absolute_spearman": _off_diagonal_max(spearman),
        "vif_by_column": [float(value) for value in vifs],
        "maximum_vif": float(np.max(vifs)),
    }


def validate_spec(spec):
    errors = []
    if spec.get("schema_version") != 1:
        errors.append("schema version differs")
    if spec.get("methodology_epoch") != "full-traveler-doe-v3":
        errors.append("methodology epoch differs")
    if spec.get("campaign") != "v3-pattern-bosch-stage2a":
        errors.append("campaign differs")
    if spec.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("required labels differ")
    if spec.get("recipe_count") != 96:
        errors.append("Stage 2a must contain 96 unique recipes")
    if spec.get("geometry") != {
        "hole_shape": "FULL",
        "radius": 0.15,
        "mask_height": 0.3,
        "mask_taper": 2.0,
        "x_extent": 1.0,
        "y_extent": 2.0,
    }:
        errors.append("nominal full-width pattern geometry differs")
    if spec.get("fixed_recipe") != {"mask_ion_rate": 0.0}:
        errors.append("fixed mask-ion rate differs")
    exclusions = spec.get("excluded_wired_controls", [])
    if [row.get("name") for row in exclusions] != ["mask_ion_rate", "num_cycles"]:
        errors.append("wired-control exclusions differ")
    for exclusion in exclusions:
        for field in (
            "owning_api",
            "classification",
            "evidence_status",
            "exclusion_rationale",
            "required_followup",
        ):
            if not isinstance(exclusion.get(field), str) or not exclusion[field].strip():
                errors.append(f"{exclusion.get('name')}: exclusion {field} is missing")
    if spec.get("numerics") != {
        "grid_delta": 0.00125,
        "rays_per_point": 2000,
        "threads_per_worker": 7,
        "maximum_workers": 2,
        "dimension": 2,
    }:
        errors.append("V3 Stage 2a numerical controls differ")
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
        errors.append("declared product targets differ")
    factors = spec.get("factors", [])
    if tuple(factor.get("name") for factor in factors) != EXPECTED_FACTOR_NAMES:
        errors.append("exact nine-factor order differs")
    for factor in factors:
        name = factor.get("name")
        low, nominal, high = factor.get("low"), factor.get("nominal"), factor.get("high")
        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in (low, nominal, high)
        ) or not low < nominal < high:
            errors.append(f"{name}: low/nominal/high values are invalid")
        if factor.get("transform") not in ("linear", "log", "signed_log_magnitude"):
            errors.append(f"{name}: transform differs")
        if factor.get("transform") == "log" and low <= 0:
            errors.append(f"{name}: log range is not positive")
        if factor.get("transform") == "signed_log_magnitude" and not low < nominal < high < 0:
            errors.append(f"{name}: signed-log range is not strictly negative")
        if factor.get("type") not in ("float", "int"):
            errors.append(f"{name}: type differs")
        for field in (
            "owning_api", "classification", "units", "expected_mechanism", "range_basis"
        ):
            if not isinstance(factor.get(field), str) or not factor[field].strip():
                errors.append(f"{name}: {field} is missing")
        for field in ("direct_outputs", "downstream_consequences"):
            if not isinstance(factor.get(field), list) or not factor[field]:
                errors.append(f"{name}: {field} is missing")
    interactions = tuple(
        tuple(row.get("factors", ())) for row in spec.get("predeclared_interactions", [])
    )
    if interactions != EXPECTED_INTERACTIONS:
        errors.append("predeclared interaction list differs")
    if any(not row.get("basis") for row in spec.get("predeclared_interactions", [])):
        errors.append("an interaction basis is missing")
    expected_fields = set(EXPECTED_FACTOR_NAMES)
    priors = spec.get("prior_anchors", [])
    if [row.get("name") for row in priors] != [
        "precursor_reference",
        "historical_dry_etch_best",
        "historical_depth_matched_failure",
    ]:
        errors.append("prior anchor declarations differ")
    for prior in priors:
        if set(prior.get("recipe", {})) != expected_fields:
            errors.append(f"{prior.get('name')}: recipe fields differ")
        for factor in factors:
            value = prior.get("recipe", {}).get(factor["name"])
            if not isinstance(value, (int, float)) or not factor["low"] <= value <= factor["high"]:
                errors.append(f"{prior.get('name')}:{factor['name']} outside range")
    horizon = 1 + 3 * trajectory.get("maximum_cycles", 0)
    reserved = [
        {"campaign": "pattern_bosch_gate0_r1", "first": 61000, "last": 61090},
        {"campaign": "pattern_bosch_gate0_r1", "first": 62000, "last": 62090},
        {"campaign": "pattern_bosch_gate0_r1", "first": 63000, "last": 63090},
        {"campaign": "pattern_bosch_gate0_r1", "first": 64000, "last": 64090},
        {"campaign": "v3_pattern_skew_stage1", "first": 81000, "last": 81042},
    ]
    if spec.get("rng_policy") != {
        "seed_start": 820000,
        "interval_stride": horizon,
        "process_seed_horizon": horizon,
        "interval_count": 96,
        "reserved_prior_v3_intervals": reserved,
        "assignment": "one globally non-overlapping process-seed interval per recipe; no stream is reused inside this stage",
        "interpretation": "independent broad coverage for screening; one stream per recipe cannot estimate within-recipe stochastic variance or confirm an effect",
    }:
        errors.append("globally disjoint RNG policy differs")
    preflight = spec.get("design_preflight", {})
    if not (
        preflight.get("pearson_target") == 0.15
        and preflight.get("spearman_target") == 0.15
        and preflight.get("correlation_hard_limit") == 0.25
        and preflight.get("vif_hard_limit") == 1.5
        and preflight.get("correlation_swap_iterations") == 20000
    ):
        errors.append("design-independence limits differ")
    thresholds = spec.get("practical_screen_thresholds", {})
    if not thresholds or any(
        not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0
        for value in thresholds.values()
    ):
        errors.append("screen thresholds are invalid")
    if spec.get("screen_threshold_policy") != (
        "effective threshold = max(practical engineering change, released R1 "
        "numerical shift, two grid cells for geometry outputs, 3*sqrt(2)*sample "
        "SD from the four disjoint released nominal 2000-ray baselines); the "
        "independent-stream screen remains hypothesis-only and finalists require "
        "recipe-specific replication"
    ):
        errors.append("screen-threshold policy differs")
    authority = spec.get("authority", {})
    if authority.get("bosch_hypothesis_screening_only") is not True or any(
        authority.get(key) is not False
        for key in (
            "confirmed_factor_authorized",
            "recipe_authorized",
            "process_window_authorized",
            "downstream_recipe_authorized",
            "traveler_relevance_authorized",
            "full_traveler_authorized",
            "automatic_launch_authorized",
        )
    ):
        errors.append("Stage 2a authority was expanded")
    if errors:
        raise ValueError("invalid V3 Stage 2a spec: " + "; ".join(errors))


def anchor_rows(spec):
    factors = spec["factors"]
    nominal = {factor["name"]: factor["nominal"] for factor in factors}
    rows = {}

    def add(recipe, reason):
        key = common.canonical_json(recipe)
        rows.setdefault(key, {"recipe": recipe, "anchor_reasons": []})[
            "anchor_reasons"
        ].append(reason)

    add(dict(nominal), "nominal")
    for factor in factors:
        for level in ("low", "high"):
            recipe = dict(nominal)
            recipe[factor["name"]] = factor[level]
            add(recipe, f"ofat:{factor['name']}:{level}")
    for prior in spec["prior_anchors"]:
        add(dict(prior["recipe"]), f"prior:{prior['name']}")
    factor_by_name = {factor["name"]: factor for factor in factors}
    for declaration in spec["predeclared_interactions"]:
        first, second = declaration["factors"]
        for first_level in ("low", "high"):
            for second_level in ("low", "high"):
                recipe = dict(nominal)
                recipe[first] = factor_by_name[first][first_level]
                recipe[second] = factor_by_name[second][second_level]
                add(
                    recipe,
                    f"interaction:{first}:{second}:{first_level}:{second_level}",
                )
    result = []
    for row in rows.values():
        result.append({
            "design_class": "exact_anchor",
            "anchor_reasons": sorted(row["anchor_reasons"]),
            "normalized_coordinates": {
                factor["name"]: to_unit(factor, row["recipe"][factor["name"]])
                for factor in factors
            },
            "recipe": row["recipe"],
        })
    return result


def _minimum_distance(points, anchors):
    differences = points[:, None, :] - points[None, :, :]
    squared = np.sum(differences * differences, axis=2)
    squared[np.diag_indices_from(squared)] = np.inf
    within = float(np.sqrt(np.min(squared)))
    to_anchor = float(np.sqrt(np.min(np.sum(
        (points[:, None, :] - anchors[None, :, :]) ** 2, axis=2
    ))))
    return min(within, to_anchor)


def _interaction_term_preflight(matrix, interactions):
    centered = 2.0 * np.asarray(matrix, dtype=float) - 1.0
    columns = [centered[:, index] for index in range(centered.shape[1])]
    names = list(EXPECTED_FACTOR_NAMES)
    for first, second in interactions:
        first_index = EXPECTED_FACTOR_NAMES.index(first)
        second_index = EXPECTED_FACTOR_NAMES.index(second)
        columns.append(centered[:, first_index] * centered[:, second_index])
        names.append(f"{first}:{second}")
    preflight = correlation_vif_preflight(np.column_stack(columns))
    return {
        "term_names": names,
        "maximum_absolute_pearson": preflight["maximum_absolute_pearson"],
        "maximum_absolute_spearman": preflight["maximum_absolute_spearman"],
        "maximum_vif": preflight["maximum_vif"],
        "vif_by_term": dict(zip(names, preflight["vif_by_column"])),
        "interpretation": "centered main and predeclared interaction terms; descriptive alias audit, not a physical effect result",
    }


def optimize_input_independence(points, anchors, *, iterations, seed):
    """Swap LHS column entries without changing any one-factor stratum."""
    points = np.array(points, dtype=float, copy=True)
    rng = np.random.default_rng(int(seed))

    def score(candidate):
        preflight = correlation_vif_preflight(np.vstack([anchors, candidate]))
        worst_correlation = max(
            preflight["maximum_absolute_pearson"],
            preflight["maximum_absolute_spearman"],
        )
        return (
            worst_correlation,
            preflight["maximum_vif"],
            -_minimum_distance(candidate, anchors),
        ), preflight

    current_score, current_preflight = score(points)
    for _ in range(int(iterations)):
        column = int(rng.integers(points.shape[1]))
        first, second = rng.choice(points.shape[0], 2, replace=False)
        points[first, column], points[second, column] = (
            points[second, column], points[first, column]
        )
        candidate_score, candidate_preflight = score(points)
        if candidate_score < current_score:
            current_score = candidate_score
            current_preflight = candidate_preflight
        else:
            points[first, column], points[second, column] = (
                points[second, column], points[first, column]
            )
    return points, current_preflight


def build_design(spec):
    validate_spec(spec)
    factors = spec["factors"]
    anchors = anchor_rows(spec)
    interior_count = spec["recipe_count"] - len(anchors)
    if interior_count < len(factors) * 3:
        raise ValueError("too few space-filling points remain after exact anchors")
    anchor_matrix = np.asarray([
        [row["normalized_coordinates"][factor["name"]] for factor in factors]
        for row in anchors
    ])
    master = np.random.default_rng(int(spec["design_seed"]))
    best = None
    best_score = None
    best_preflight = None
    limits = spec["design_preflight"]
    for _ in range(int(spec["candidate_design_count"])):
        points = common.latin_hypercube(
            interior_count,
            len(factors),
            np.random.default_rng(int(master.integers(0, 2**63 - 1))),
        )
        full = np.vstack([anchor_matrix, points])
        preflight = correlation_vif_preflight(full)
        hard_pass = bool(
            preflight["maximum_absolute_pearson"] < limits["correlation_hard_limit"]
            and preflight["maximum_absolute_spearman"] < limits["correlation_hard_limit"]
            and preflight["maximum_vif"] < limits["vif_hard_limit"]
        )
        target_pass = bool(
            preflight["maximum_absolute_pearson"] < limits["pearson_target"]
            and preflight["maximum_absolute_spearman"] < limits["spearman_target"]
        )
        distance = _minimum_distance(points, anchor_matrix)
        score = (
            int(hard_pass),
            int(target_pass),
            distance,
            -preflight["maximum_vif"],
            -max(
                preflight["maximum_absolute_pearson"],
                preflight["maximum_absolute_spearman"],
            ),
        )
        if best_score is None or score > best_score:
            best = points
            best_score = score
            best_preflight = preflight
    best, best_preflight = optimize_input_independence(
        best,
        anchor_matrix,
        iterations=limits["correlation_swap_iterations"],
        seed=int(spec["design_seed"]) + 1,
    )
    hard_pass = bool(
        best_preflight["maximum_absolute_pearson"] < limits["correlation_hard_limit"]
        and best_preflight["maximum_absolute_spearman"] < limits["correlation_hard_limit"]
        and best_preflight["maximum_vif"] < limits["vif_hard_limit"]
    )
    interior = []
    for index, point in enumerate(best):
        recipe = {
            factor["name"]: from_unit(factor, float(point[column]))
            for column, factor in enumerate(factors)
        }
        interior.append({
            "design_class": "optimized_latin_hypercube",
            "design_index": index,
            "anchor_reasons": [],
            "normalized_coordinates": {
                factor["name"]: float(point[column])
                for column, factor in enumerate(factors)
            },
            "recipe": recipe,
        })
    rows = anchors + interior
    for row in rows:
        row["recipe_id"] = "v3pb2a_" + common.canonical_sha256(row["recipe"])[:12]
    preflight = {
        **best_preflight,
        "factor_names": list(EXPECTED_FACTOR_NAMES),
        "pearson_target": limits["pearson_target"],
        "spearman_target": limits["spearman_target"],
        "correlation_hard_limit": limits["correlation_hard_limit"],
        "vif_hard_limit": limits["vif_hard_limit"],
        "pearson_target_met": best_preflight["maximum_absolute_pearson"] < limits["pearson_target"],
        "spearman_target_met": best_preflight["maximum_absolute_spearman"] < limits["spearman_target"],
        "hard_limits_met": hard_pass,
        "vif_by_factor": dict(zip(EXPECTED_FACTOR_NAMES, best_preflight["vif_by_column"])),
        "interpretation": limits["interpretation"],
    }
    preflight.pop("vif_by_column")
    result = {
        "schema_version": 1,
        "methodology_epoch": spec["methodology_epoch"],
        "campaign": spec["campaign"],
        "labels": spec["labels"],
        "spec_sha256": common.canonical_sha256(spec),
        "question": spec["question"],
        "evidence_class": spec["evidence_class"],
        "geometry": spec["geometry"],
        "fixed_recipe": spec["fixed_recipe"],
        "excluded_wired_controls": spec["excluded_wired_controls"],
        "numerics": spec["numerics"],
        "trajectory": spec["trajectory"],
        "rng_policy": spec["rng_policy"],
        "target": spec["target"],
        "practical_screen_thresholds": spec["practical_screen_thresholds"],
        "screen_threshold_policy": spec["screen_threshold_policy"],
        "factors": factors,
        "predeclared_interactions": spec["predeclared_interactions"],
        "decision_rules": spec["decision_rules"],
        "authority": spec["authority"],
        "design": {
            "method": "exact nominal/OFAT/prior/interaction anchors plus maximin optimized Latin hypercube interior",
            "recipe_count": len(rows),
            "exact_anchor_count": len(anchors),
            "space_filling_interior_count": len(interior),
            "logical_simulation_count": len(rows),
            "candidate_designs_compared": spec["candidate_design_count"],
            "minimum_normalized_interior_or_anchor_distance": _minimum_distance(best, anchor_matrix),
            "input_independence_preflight": preflight,
            "planned_term_alias_preflight": _interaction_term_preflight(
                np.vstack([anchor_matrix, best]), EXPECTED_INTERACTIONS
            ),
        },
        "recipes": rows,
    }
    errors = validate_design(result, spec)
    if errors:
        raise ValueError("generated V3 Stage 2a design is invalid: " + "; ".join(errors))
    return result


def validate_design(design, spec):
    errors = []
    rows = design.get("recipes", [])
    if len(rows) != 96 or design.get("design", {}).get("logical_simulation_count") != 96:
        errors.append("design size differs")
    if len({row.get("recipe_id") for row in rows}) != 96:
        errors.append("recipe IDs are not unique")
    if len({common.canonical_json(row.get("recipe")) for row in rows}) != 96:
        errors.append("recipes are not unique")
    exact_fields = set(EXPECTED_FACTOR_NAMES)
    for row in rows:
        if set(row.get("recipe", {})) != exact_fields:
            errors.append(f"{row.get('recipe_id')}: recipe fields differ")
    reasons = {reason for row in rows for reason in row.get("anchor_reasons", [])}
    required = {"nominal"}
    required.update(
        f"ofat:{name}:{level}"
        for name in EXPECTED_FACTOR_NAMES
        for level in ("low", "high")
    )
    required.update(f"prior:{row['name']}" for row in spec["prior_anchors"])
    required.update(
        f"interaction:{first}:{second}:{first_level}:{second_level}"
        for first, second in EXPECTED_INTERACTIONS
        for first_level in ("low", "high")
        for second_level in ("low", "high")
    )
    missing = required - reasons
    if missing:
        errors.append("exact anchors are missing: " + ",".join(sorted(missing)))
    interior = [row for row in rows if row.get("design_class") == "optimized_latin_hypercube"]
    expected_interior = 96 - len(anchor_rows(spec))
    if len(interior) != expected_interior:
        errors.append("space-filling interior count differs")
    for factor in spec["factors"]:
        coordinates = [row["normalized_coordinates"][factor["name"]] for row in interior]
        strata = {min(int(value * len(interior)), len(interior) - 1) for value in coordinates}
        if len(strata) != len(interior):
            errors.append(f"{factor['name']}: LHS strata are not unique")
    quality = design.get("design", {}).get("input_independence_preflight", {})
    if not (
        quality.get("maximum_absolute_pearson", 1.0) < 0.25
        and quality.get("maximum_absolute_spearman", 1.0) < 0.25
        and quality.get("maximum_vif", math.inf) < 1.5
        and quality.get("hard_limits_met") is True
    ):
        errors.append("input independence hard limits fail")
    if design.get("authority") != spec["authority"]:
        errors.append("authority differs")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    spec_path = args.spec if args.spec.is_absolute() else root / args.spec
    spec = common.strict_load(spec_path)
    design = build_design(spec)
    if args.output:
        output = args.output if args.output.is_absolute() else root / args.output
        common.write_atomic(output, design)
    preflight = design["design"]["input_independence_preflight"]
    print(common.canonical_json({
        "recipes": design["design"]["recipe_count"],
        "anchors": design["design"]["exact_anchor_count"],
        "interior": design["design"]["space_filling_interior_count"],
        "max_abs_pearson": preflight["maximum_absolute_pearson"],
        "max_abs_spearman": preflight["maximum_absolute_spearman"],
        "max_vif": preflight["maximum_vif"],
    }))


if __name__ == "__main__":
    main()

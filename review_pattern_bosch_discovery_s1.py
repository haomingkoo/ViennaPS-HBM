"""Independent response/noise review for broad-first Bosch discovery."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

import numpy as np

import foundation_pattern_bosch_gate0 as gate0
import pattern_bosch_discovery_s1_runner as runner


DEFAULT_MANIFEST = runner.DEFAULT_MANIFEST
DEFAULT_ROWS = runner.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/"
    "pattern_bosch_discovery_s1_summary.json"
)
DEFAULT_MARKDOWN = Path(
    "autoresearch-results/restart_audit/"
    "pattern_bosch_discovery_s1_review.md"
)
RESPONSE_METRICS = (
    "depth",
    "selected_cycle",
    "depth_per_cycle",
    "cd_top",
    "cd_middle",
    "cd_bottom",
    "cd_taper_top_minus_bottom",
    "cd_span",
    "max_cd_error",
    "max_bow",
    "scallop_rms",
    "sidewall_angle_deg",
    "mask_remaining_height",
)
REACHABILITY_METRICS = {"depth", "selected_cycle", "depth_per_cycle"}
CTQ_TOLERANCES = {
    "depth": 0.1,
    "selected_cycle": None,
    "depth_per_cycle": None,
    "cd_top": 0.06,
    "cd_middle": 0.06,
    "cd_bottom": 0.06,
    "cd_taper_top_minus_bottom": None,
    "cd_span": None,
    "max_cd_error": 0.06,
    "max_bow": 0.03,
    "scallop_rms": None,
    "sidewall_angle_deg": None,
    "mask_remaining_height": 0.0025,
}


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def metric_values(row):
    measured = row.get("selected_cycle_metrics") or {}
    etch = measured.get("etch") or {}
    selected_cycle = row.get("selected_cycle")
    depth = etch.get("depth")
    return {
        "depth": depth,
        "selected_cycle": selected_cycle,
        "depth_per_cycle": (
            depth / selected_cycle
            if finite(depth) and finite(selected_cycle) and selected_cycle > 0
            else None
        ),
        "cd_top": etch.get("cd_top"),
        "cd_middle": etch.get("cd_middle"),
        "cd_bottom": etch.get("cd_bottom"),
        "cd_taper_top_minus_bottom": (
            etch["cd_top"] - etch["cd_bottom"]
            if finite(etch.get("cd_top")) and finite(etch.get("cd_bottom"))
            else None
        ),
        "cd_span": (
            etch["cd_max"] - etch["cd_min"]
            if finite(etch.get("cd_max")) and finite(etch.get("cd_min"))
            else None
        ),
        "max_cd_error": etch.get("max_cd_error"),
        "max_bow": etch.get("max_bow"),
        "scallop_rms": etch.get("scallop_rms"),
        "sidewall_angle_deg": etch.get("sidewall_angle_deg"),
        "mask_remaining_height": measured.get("mask_remaining_height"),
    }


def signed_margins(row):
    target = row["target"]
    grid = row["numerics"]["grid_delta"]
    initial = row.get("initial_pattern") or {}
    measured = row.get("selected_cycle_metrics") or {}
    etch = measured.get("etch") or {}

    def margin(limit, value):
        return float(limit - value) if finite(value) else None

    width_error = (
        abs(initial["opening_cd_bottom"] - target["opening_cd"])
        if finite(initial.get("opening_cd_bottom")) else None
    )
    height_error = (
        abs(initial["mask_height"] - target["mask_height"])
        if finite(initial.get("mask_height")) else None
    )
    depth_error = (
        abs(etch["depth"] - target["etch_depth"])
        if finite(etch.get("depth")) else None
    )
    remaining = measured.get("mask_remaining_height")
    return {
        "pattern_width": margin(target["max_width_error"], width_error),
        "pattern_height": margin(grid, height_error),
        "etch_depth": margin(target["depth_tolerance"], depth_error),
        "etch_cd_profile": margin(target["max_width_error"], etch.get("max_cd_error")),
        "etch_bow": margin(target["max_wall_bulge"], etch.get("max_bow")),
        "etch_mask_resolved": (
            float(remaining - target["resolved_mask_cells_strict"] * grid)
            if finite(remaining) else None
        ),
    }


def success_rows(path):
    rows = []
    for line in Path(path).read_text().splitlines() if Path(path).is_file() else []:
        if line.strip():
            row = gate0.strict_json_loads(line)
            if row.get("ok") is True:
                rows.append(row)
    return rows


def review_case(row, case, output):
    errors = runner.validate_success_row(row, case, output)
    return {
        "case_id": case["case_id"],
        "recipe_id": case["recipe_id"],
        "case_role": case["case_role"],
        "rng_seed": case["rng_seed"],
        "rays_per_point": case["numerics"]["rays_per_point"],
        "valid": not errors,
        "errors": errors,
        "hard_gate_pass": row.get("hard_gate_pass") is True,
        "selection_eligible": row.get("selection_eligible") is True,
        "depth_horizon_censored": row.get("depth_horizon_censored") is True,
        "trajectory_classification": row.get("trajectory_classification"),
        "metrics": metric_values(row),
        "signed_margins": signed_margins(row),
        "normalized_coordinates": case["normalized_coordinates"],
        "recipe": case["recipe"],
    }


def low_fidelity_recipe_means(reviewed, expected_base_replicates=2):
    groups = defaultdict(list)
    for row in reviewed:
        if (
            row["valid"]
            and row["rays_per_point"] == 1000
            and row["case_role"] == "base_discovery"
        ):
            groups[row["recipe_id"]].append(row)
    means = {}
    for recipe_id, rows in groups.items():
        complete = len(rows) == expected_base_replicates
        depth_matched = complete and all(row["selection_eligible"] for row in rows)
        means[recipe_id] = {
            "normalized_coordinates": rows[0]["normalized_coordinates"],
            "complete_base_replicates": complete,
            "all_base_replicates_depth_matched": depth_matched,
            "metrics": {
                metric: float(np.mean([
                    row["metrics"][metric]
                    for row in rows
                    if finite(row["metrics"].get(metric))
                    and complete
                    and (metric in REACHABILITY_METRICS or depth_matched)
                ]))
                if any(
                    finite(row["metrics"].get(metric))
                    and complete
                    and (metric in REACHABILITY_METRICS or depth_matched)
                    for row in rows
                )
                else None
                for metric in RESPONSE_METRICS
            },
        }
    return means


def pooled_noise(reviewed):
    groups = defaultdict(list)
    for row in reviewed:
        if row["valid"] and row["rays_per_point"] == 1000:
            groups[row["recipe_id"]].append(row)
    result = {}
    for metric in RESPONSE_METRICS:
        squared = 0.0
        degrees = 0
        recipe_count = 0
        metric_rows = [
            row
            for rows in groups.values()
            for row in rows
            if finite(row["metrics"].get(metric))
            and (metric in REACHABILITY_METRICS or row["selection_eligible"])
        ]
        for rows in groups.values():
            values = [
                row["metrics"].get(metric) for row in rows
                if metric in REACHABILITY_METRICS or row["selection_eligible"]
            ]
            values = [float(value) for value in values if finite(value)]
            if len(values) >= 2:
                mean = float(np.mean(values))
                squared += sum((value - mean) ** 2 for value in values)
                degrees += len(values) - 1
                recipe_count += 1
        result[metric] = {
            "replicated_recipe_count": recipe_count,
            "pooled_within_recipe_contrast_count": degrees,
            "distinct_rng_stream_count": len({row["rng_seed"] for row in metric_rows}),
            "seed_labels_reused_across_recipes": bool(
                len({row["rng_seed"] for row in metric_rows}) < len(metric_rows)
            ),
            "pooled_within_recipe_sd": (
                math.sqrt(squared / degrees) if degrees else None
            ),
            "inference_authorized": False,
            "interpretation": (
                "Descriptive pooled within-recipe variation; the contrast count "
                "is not reported as independent residual degrees of freedom."
            ),
        }
    return result


def reachability_summary(reviewed, manifest):
    rows = [
        row for row in reviewed
        if row["valid"] and row["case_role"] == "base_discovery"
        and row["rays_per_point"] == 1000
    ]
    by_recipe = defaultdict(list)
    for row in rows:
        by_recipe[row["recipe_id"]].append(row)
    target = manifest["design"]["target"]
    expected_replicates = manifest["design"]["design"]["replicates_per_recipe"]
    lower = target["etch_depth"] - target["depth_tolerance"]
    upper = target["etch_depth"] + target["depth_tolerance"]
    return {
        "base_case_count": len(rows),
        "depth_matched_case_count": sum(row["selection_eligible"] for row in rows),
        "cycle_horizon_censored_case_count": sum(
            row["depth_horizon_censored"] for row in rows
        ),
        "shallow_best_checkpoint_count": sum(
            finite(row["metrics"].get("depth"))
            and row["metrics"]["depth"] < lower for row in rows
        ),
        "deep_best_checkpoint_count": sum(
            finite(row["metrics"].get("depth"))
            and row["metrics"]["depth"] > upper for row in rows
        ),
        "all_base_seeds_depth_matched_recipe_count": sum(
            len(recipe_rows) == expected_replicates
            and all(row["selection_eligible"] for row in recipe_rows)
            for recipe_rows in by_recipe.values()
        ),
        "recipe_count": len(by_recipe),
        "interpretation": (
            "Only recipes depth-matched on both base streams enter morphology "
            "response models. Misses remain here as reachability evidence."
        ),
    }


def practical_detection_thresholds(reviewed, noise, fidelity, manifest):
    base_replicates = manifest["design"]["design"]["replicates_per_recipe"]
    grid_resolution = 2.0 * manifest["design"]["numerics"]["grid_delta"]
    result = {}
    for metric in RESPONSE_METRICS:
        sigma = noise[metric]["pooled_within_recipe_sd"]
        stochastic = (
            3.96 * sigma / math.sqrt(base_replicates)
            if finite(sigma) and base_replicates > 0 else None
        )
        numerical = fidelity["maximum_absolute_delta"].get(metric)
        practical_resolution = (
            1.0 if metric == "selected_cycle"
            else None if metric in ("depth_per_cycle", "sidewall_angle_deg")
            else grid_resolution
        )
        components = []
        components.extend(
            value for value in (practical_resolution, stochastic, numerical)
            if finite(value)
        )
        threshold = max(components) if components else None
        tolerance = CTQ_TOLERANCES[metric]
        result[metric] = {
            "base_replicates_per_recipe": base_replicates,
            "practical_resolution": practical_resolution,
            "stochastic_two_mean_mde_95pct_80pct_power": stochastic,
            "maximum_observed_2000_minus_1000_ray_delta": numerical,
            "screening_detection_threshold": threshold,
            "ctq_tolerance": tolerance,
            "threshold_over_ctq_tolerance": (
                threshold / tolerance
                if finite(threshold) and finite(tolerance) and tolerance > 0
                else None
            ),
            "interpretation": (
                "Conservative screening threshold, not a confidence interval; "
                "it combines pooled stochastic variation, observed ray-fidelity "
                "shift, and practical resolution."
            ),
        }
    return result


def model_columns(coordinates, factor_names, interactions):
    values = [float(coordinates[name]) for name in factor_names]
    columns = [1.0, *values, *(value * value for value in values)]
    columns.extend(
        values[factor_names.index(first)] * values[factor_names.index(second)]
        for first, second in interactions
    )
    return columns


def response_models(recipe_means, manifest, noise, detection_thresholds=None):
    factor_names = [factor["name"] for factor in manifest["design"]["factors"]]
    interactions = manifest["design"]["predeclared_interactions"]
    recipe_ids = sorted(recipe_means)
    fold_by_recipe = {
        recipe_id: index % 4 for index, recipe_id in enumerate(recipe_ids)
    }
    result = {}
    for metric in RESPONSE_METRICS:
        usable = [
            recipe_id for recipe_id in recipe_ids
            if finite(recipe_means[recipe_id]["metrics"].get(metric))
        ]
        response_role = (
            "reachability" if metric in REACHABILITY_METRICS
            else "depth_matched_morphology"
        )

        def matrix_for(ids):
            return np.asarray([
                model_columns(
                    recipe_means[recipe_id]["normalized_coordinates"],
                    factor_names,
                    interactions,
                )
                for recipe_id in ids
            ])

        def response_for(ids):
            return np.asarray([
                recipe_means[recipe_id]["metrics"][metric]
                for recipe_id in ids
            ])

        folds = []
        observed_all = []
        predicted_all = []
        main_predicted_all = []
        insufficient = False
        for fold in range(4):
            train = [
                recipe_id for recipe_id in usable
                if fold_by_recipe[recipe_id] != fold
            ]
            test = [
                recipe_id for recipe_id in usable
                if fold_by_recipe[recipe_id] == fold
            ]
            if len(train) < 25 or not test:
                insufficient = True
                break
            train_matrix = matrix_for(train)
            train_response = response_for(train)
            coefficients, _, rank, _ = np.linalg.lstsq(
                train_matrix, train_response, rcond=None
            )
            main_coefficients, _, main_rank, _ = np.linalg.lstsq(
                train_matrix[:, :1 + len(factor_names)],
                train_response,
                rcond=None,
            )
            test_matrix = matrix_for(test)
            observed = response_for(test)
            prediction = test_matrix @ coefficients
            main_prediction = (
                test_matrix[:, :1 + len(factor_names)] @ main_coefficients
            )
            observed_all.extend(observed.tolist())
            predicted_all.extend(prediction.tolist())
            main_predicted_all.extend(main_prediction.tolist())
            folds.append({
                "fold": fold,
                "train_recipe_count": len(train),
                "test_recipe_count": len(test),
                "matrix_rank": int(rank),
                "main_effect_matrix_rank": int(main_rank),
                "rmse": float(np.sqrt(np.mean((prediction - observed) ** 2))),
                "main_effect_only_rmse": float(
                    np.sqrt(np.mean((main_prediction - observed) ** 2))
                ),
            })
        if insufficient:
            result[metric] = {
                "status": "insufficient_complete_recipes",
                "response_role": response_role,
                "usable_recipe_count": len(usable),
            }
            continue
        matrix = matrix_for(usable)
        response = response_for(usable)
        coefficients, _, rank, singular = np.linalg.lstsq(
            matrix, response, rcond=None
        )
        main_rank = np.linalg.matrix_rank(matrix[:, :1 + len(factor_names)])
        observed = np.asarray(observed_all)
        prediction = np.asarray(predicted_all)
        main_prediction = np.asarray(main_predicted_all)
        rmse = float(np.sqrt(np.mean((prediction - observed) ** 2)))
        main_rmse = float(np.sqrt(np.mean((main_prediction - observed) ** 2)))
        sigma = noise[metric]["pooled_within_recipe_sd"]
        detection = (
            (detection_thresholds or {}).get(metric, {}).get(
                "screening_detection_threshold"
            )
        )
        tolerance = CTQ_TOLERANCES[metric]
        center = {name: 0.5 for name in factor_names}
        centerline_effects = {}
        for name in factor_names:
            low = dict(center)
            high = dict(center)
            low[name] = 0.0
            high[name] = 1.0
            centerline_effects[name] = float(
                (
                    np.asarray(model_columns(high, factor_names, interactions))
                    - np.asarray(model_columns(low, factor_names, interactions))
                ) @ coefficients
            )
        result[metric] = {
            "status": "fit",
            "response_role": response_role,
            "term_count": int(matrix.shape[1]),
            "all_recipe_fit_count": len(usable),
            "grouped_cross_validation": "deterministic_recipe_grouped_4_fold",
            "folds": folds,
            "matrix_rank": int(rank),
            "main_effect_matrix_rank": int(main_rank),
            "condition_number": (
                float(singular[0] / singular[-1]) if singular[-1] > 0 else None
            ),
            "grouped_cv_rmse": rmse,
            "main_effect_only_grouped_cv_rmse": main_rmse,
            "main_minus_augmented_grouped_cv_rmse": main_rmse - rmse,
            "augmented_terms_grouped_cv_support": bool(rmse < main_rmse),
            "ctq_tolerance": tolerance,
            "grouped_cv_rmse_over_ctq_tolerance": (
                rmse / tolerance if finite(tolerance) and tolerance > 0 else None
            ),
            "grouped_cv_model_adequate_for_ctq_screening": (
                bool(
                    rank == matrix.shape[1]
                    and all(fold["matrix_rank"] == matrix.shape[1] for fold in folds)
                    and rmse <= 0.25 * tolerance
                )
                if finite(tolerance) and tolerance > 0 else None
            ),
            "grouped_cv_rmse_over_noise_sd": (
                rmse / sigma if finite(sigma) and sigma > 0 else None
            ),
            "centerline_full_range_effects": centerline_effects,
            "factor_effect_snr": {
                name: abs(value) / sigma
                if finite(sigma) and sigma > 0 else None
                for name, value in centerline_effects.items()
            },
            "factor_effect_over_detection_threshold": {
                name: abs(value) / detection
                if finite(detection) and detection > 0 else None
                for name, value in centerline_effects.items()
            },
            "quadratic_coefficients": {
                name: float(coefficients[1 + len(factor_names) + index])
                for index, name in enumerate(factor_names)
            },
            "predeclared_interaction_contrasts": {
                f"{first}:{second}": float(
                    coefficients[1 + 2 * len(factor_names) + index]
                )
                for index, (first, second) in enumerate(interactions)
            },
            "interpretation": (
                "Screening association conditional on the predeclared model. "
                "Interaction coefficients are hypotheses for independent "
                "follow-up, not physical-causality or optimum claims."
            ),
        }
    return result


def fidelity_deltas(reviewed):
    by_key = {
        (row["recipe_id"], row["rng_seed"], row["rays_per_point"]): row
        for row in reviewed if row["valid"]
    }
    pairs = []
    for recipe_id, seed, rays in sorted(by_key):
        if rays != 1000:
            continue
        low = by_key[(recipe_id, seed, rays)]
        high = by_key.get((recipe_id, seed, 2000))
        if high is None:
            continue
        pairs.append({
            "recipe_id": recipe_id,
            "rng_seed": seed,
            "gate_flip": low["hard_gate_pass"] != high["hard_gate_pass"],
            "deltas_2000_minus_1000": {
                metric: (
                    high["metrics"][metric] - low["metrics"][metric]
                    if finite(high["metrics"].get(metric))
                    and finite(low["metrics"].get(metric)) else None
                )
                for metric in RESPONSE_METRICS
            },
        })
    return {
        "paired_count": len(pairs),
        "gate_flip_count": sum(pair["gate_flip"] for pair in pairs),
        "pairs": pairs,
        "maximum_absolute_delta": {
            metric: max(
                (
                    abs(pair["deltas_2000_minus_1000"][metric])
                    for pair in pairs
                    if finite(pair["deltas_2000_minus_1000"].get(metric))
                ),
                default=None,
            )
            for metric in RESPONSE_METRICS
        },
    }


def build_summary(manifest, rows_path):
    errors = runner.validate_manifest(manifest)
    if errors:
        raise ValueError("invalid S1 manifest: " + "; ".join(errors))
    cases = runner.expand_cases(manifest)
    completed = runner.audit_existing_rows(rows_path, cases)
    rows = {row["case_id"]: row for row in success_rows(rows_path)}
    reviewed = [
        review_case(rows[case["case_id"]], case, rows_path)
        for case in cases if case["case_id"] in completed
    ]
    noise = pooled_noise(reviewed)
    recipe_means = low_fidelity_recipe_means(
        reviewed,
        manifest["design"]["design"]["replicates_per_recipe"],
    )
    fidelity = fidelity_deltas(reviewed)
    detection = practical_detection_thresholds(
        reviewed, noise, fidelity, manifest
    )
    expected_case_count = len(cases)
    complete = bool(
        len(reviewed) == expected_case_count
        and all(row["valid"] for row in reviewed)
    )
    return {
        "campaign": manifest["campaign"],
        "labels": manifest["labels"],
        "expected_case_count": expected_case_count,
        "reviewed_case_count": len(reviewed),
        "valid_case_count": sum(row["valid"] for row in reviewed),
        "invalid_cases": [
            {"case_id": row["case_id"], "errors": row["errors"]}
            for row in reviewed if not row["valid"]
        ],
        "hard_gate_pass_count": sum(row["hard_gate_pass"] for row in reviewed),
        "depth_horizon_censored_count": sum(
            row["depth_horizon_censored"] for row in reviewed
        ),
        "reachability": reachability_summary(reviewed, manifest),
        "pooled_noise": noise,
        "practical_detection_thresholds": detection,
        "response_models": response_models(
            recipe_means, manifest, noise, detection
        ),
        "fidelity_bridge": fidelity,
        "reviewed_cases": reviewed,
        "decision": {
            "classification": (
                "complete_broad_factor_discovery"
                if complete else "incomplete_or_invalid_broad_factor_discovery"
            ),
            "complete_valid_matrix": complete,
            "factor_screening_evidence_available": complete,
            "recipe_authorized": False,
            "process_window_authorized": False,
            "downstream_recipe_authorized": False,
            "full_traveler_authorized": False,
        },
        "authority": manifest["authority"],
    }


def markdown(summary):
    lines = [
        "# Broad-first Bosch discovery review",
        "",
        f"Status: `{summary['decision']['classification']}`. Valid cases: "
        f"{summary['valid_case_count']}/{summary['expected_case_count']}.",
        "",
        f"Hard-gate passes: {summary['hard_gate_pass_count']}; cycle-horizon "
        f"censored trajectories: {summary['depth_horizon_censored_count']}.",
        "",
        "This stage estimates factor signal, stochastic noise, response curvature, "
        "and six predeclared interactions. It does not select a recipe or establish "
        "a process window.",
        "",
        "## Fidelity sentinels",
        "",
        f"Paired 1000/2000-ray comparisons: "
        f"{summary['fidelity_bridge']['paired_count']}; hard-gate flips: "
        f"{summary['fidelity_bridge']['gate_flip_count']}.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    manifest = gate0.strict_json_loads(args.manifest.read_text())
    summary = build_summary(manifest, args.rows)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown(summary) + "\n")
    print(json.dumps({
        "classification": summary["decision"]["classification"],
        "valid": summary["valid_case_count"],
        "expected": summary["expected_case_count"],
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

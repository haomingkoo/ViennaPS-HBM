"""Independent hypothesis-only review for the V3 Stage 2a Bosch screen."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

import numpy as np

import build_v3_pattern_bosch_stage2a as builder
import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as runner


DEFAULT_MANIFEST = runner.DEFAULT_MANIFEST
DEFAULT_ROWS = runner.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/v3_pattern_bosch_stage2a_summary.json"
)
DEFAULT_MARKDOWN = Path(
    "autoresearch-results/restart_audit/v3_pattern_bosch_stage2a_review.md"
)
RESPONSE_METRICS = (
    "etch_depth",
    "selected_cycle",
    "target_depth_crossing_cycle",
    "target_depth_crossing_model_duration",
    "etch_depth_per_selected_cycle",
    "etch_cd_top",
    "etch_cd_middle",
    "etch_cd_bottom",
    "etch_cd_taper_top_minus_bottom",
    "etch_cd_span",
    "etch_max_cd_error",
    "etch_max_bow",
    "etch_scallop_rms",
    "etch_sidewall_angle_deg",
    "mask_remaining_height",
)
REACHABILITY_METRICS = {
    "etch_depth",
    "selected_cycle",
    "target_depth_crossing_cycle",
    "target_depth_crossing_model_duration",
    "etch_depth_per_selected_cycle",
}
GATE_NAMES = (
    "selection_eligible",
    "etch_depth",
    "etch_cd_profile",
    "etch_bow",
    "etch_mask_resolved",
)


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def target_depth_crossing(row):
    history = row.get("cycle_history") or []
    target = float(row["target"]["etch_depth"])
    etch_time = float(row["recipe"]["etch_time"])
    initial_time = float(row["recipe"]["initial_etch_time"])
    cycle_phase_duration = 2.0 + etch_time
    samples = [
        (int(record["cycle"]), float(record["depth"]))
        for record in history
        if isinstance(record.get("cycle"), int) and finite(record.get("depth"))
    ]
    if not samples:
        return {
            "status": "invalid_no_finite_cycle_depth",
            "crossing_cycle": None,
            "model_phase_duration": None,
            "bound_cycle": None,
            "bound_model_phase_duration": None,
        }
    first_cycle, first_depth = samples[0]
    if first_depth >= target:
        return {
            "status": "left_censored_before_or_at_first_checkpoint",
            "crossing_cycle": None,
            "model_phase_duration": None,
            "bound_cycle": float(first_cycle),
            "bound_model_phase_duration": initial_time,
        }
    for (low_cycle, low_depth), (high_cycle, high_depth) in zip(samples, samples[1:]):
        if low_depth < target <= high_depth and high_depth > low_depth:
            fraction = (target - low_depth) / (high_depth - low_depth)
            crossing_cycle = low_cycle + fraction * (high_cycle - low_cycle)
            return {
                "status": "interpolated_bracketed_crossing",
                "crossing_cycle": float(crossing_cycle),
                "model_phase_duration": float(
                    initial_time + crossing_cycle * cycle_phase_duration
                ),
                "bound_cycle": None,
                "bound_model_phase_duration": None,
            }
    last_cycle, last_depth = samples[-1]
    if last_depth < target:
        return {
            "status": "right_censored_after_last_checkpoint",
            "crossing_cycle": None,
            "model_phase_duration": None,
            "bound_cycle": float(last_cycle),
            "bound_model_phase_duration": float(
                initial_time + last_cycle * cycle_phase_duration
            ),
        }
    return {
        "status": "unresolved_nonmonotonic_crossing",
        "crossing_cycle": None,
        "model_phase_duration": None,
        "bound_cycle": None,
        "bound_model_phase_duration": None,
    }


def metric_values(row):
    measured = row.get("selected_cycle_metrics") or {}
    etch = measured.get("etch") or {}
    selected_cycle = row.get("selected_cycle")
    depth = etch.get("depth")
    crossing = target_depth_crossing(row)
    return {
        "etch_depth": depth,
        "selected_cycle": selected_cycle,
        "target_depth_crossing_cycle": crossing["crossing_cycle"],
        "target_depth_crossing_model_duration": crossing["model_phase_duration"],
        "etch_depth_per_selected_cycle": (
            depth / selected_cycle
            if finite(depth) and finite(selected_cycle) and selected_cycle > 0
            else None
        ),
        "etch_cd_top": etch.get("cd_top"),
        "etch_cd_middle": etch.get("cd_middle"),
        "etch_cd_bottom": etch.get("cd_bottom"),
        "etch_cd_taper_top_minus_bottom": (
            etch["cd_top"] - etch["cd_bottom"]
            if finite(etch.get("cd_top")) and finite(etch.get("cd_bottom"))
            else None
        ),
        "etch_cd_span": (
            etch["cd_max"] - etch["cd_min"]
            if finite(etch.get("cd_max")) and finite(etch.get("cd_min"))
            else None
        ),
        "etch_max_cd_error": etch.get("max_cd_error"),
        "etch_max_bow": etch.get("max_bow"),
        "etch_scallop_rms": etch.get("scallop_rms"),
        "etch_sidewall_angle_deg": etch.get("sidewall_angle_deg"),
        "mask_remaining_height": measured.get("mask_remaining_height"),
    }, crossing


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
    metrics, crossing = metric_values(row)
    gates = row.get("gates") or {}
    depth_matched = bool(
        finite(metrics.get("etch_depth"))
        and abs(metrics["etch_depth"] - case["target"]["etch_depth"])
        <= case["target"]["depth_tolerance"]
    )
    return {
        "case_id": case["case_id"],
        "recipe_id": case["recipe_id"],
        "design_class": case["design_class"],
        "anchor_reasons": case["anchor_reasons"],
        "rng_seed": case["rng_seed"],
        "rng_interval": {
            "first": case["rng_stream"]["first_process_seed"],
            "last": case["rng_stream"]["last_process_seed"],
        },
        "valid": not errors,
        "errors": errors,
        "simulation_completed": row.get("simulation_completed") is True,
        "metrics_valid": row.get("metrics_valid") is True,
        "scientific_invalid_reasons": row.get("scientific_invalid_reasons") or [],
        "underetch_assertion_intercepted": row.get("underetch_assertion_intercepted"),
        "hard_gate_pass": row.get("hard_gate_pass") is True,
        "selection_eligible": row.get("selection_eligible") is True,
        "depth_matched_to_spec": depth_matched,
        "depth_horizon_censored": row.get("depth_horizon_censored") is True,
        "trajectory_classification": row.get("trajectory_classification"),
        "target_depth_crossing": crossing,
        "metrics": metrics,
        "gates": {
            "selection_eligible": row.get("selection_eligible") is True,
            **{name: gates.get(name) is True for name in GATE_NAMES[1:]},
        },
        "normalized_coordinates": case["normalized_coordinates"],
        "recipe": case["recipe"],
        "checkpoint_path": row.get("checkpoint_path"),
        "checkpoint_sha256": row.get("checkpoint_sha256"),
    }


def metric_rows(reviewed, metric):
    return [
        row for row in reviewed
        if row["valid"]
        and row["metrics_valid"]
        and finite(row["metrics"].get(metric))
        and (metric in REACHABILITY_METRICS or row["depth_matched_to_spec"])
    ]


def correlation(first, second):
    if len(first) < 3 or np.std(first) == 0 or np.std(second) == 0:
        return None
    return float(np.corrcoef(first, second)[0, 1])


def knob_output_correlations(reviewed, factor_names):
    result = {}
    for metric in RESPONSE_METRICS:
        rows = metric_rows(reviewed, metric)
        output = np.asarray([row["metrics"][metric] for row in rows], dtype=float)
        factors = {}
        for name in factor_names:
            values = np.asarray(
                [row["normalized_coordinates"][name] for row in rows], dtype=float
            )
            factors[name] = {
                "case_count": len(rows),
                "pearson_transformed_input_to_output": correlation(values, output),
                "spearman_input_to_output": correlation(
                    builder.average_ranks(values), builder.average_ranks(output)
                ),
                "interpretation": "screening association, not causality or confirmed sensitivity",
            }
        result[metric] = factors
    return result


def exact_anchor_rows(reviewed):
    by_reason = {}
    for row in reviewed:
        for reason in row["anchor_reasons"]:
            by_reason[reason] = row
    return by_reason


def effective_threshold(manifest, metric):
    declaration = manifest["effective_screen_thresholds"].get(metric)
    return declaration.get("effective_threshold") if declaration else None


def exact_ofat_effects(reviewed, manifest, factor_names):
    by_reason = exact_anchor_rows(reviewed)
    result = {}
    for metric in RESPONSE_METRICS:
        rows = metric_rows(reviewed, metric)
        output_sd = float(np.std([row["metrics"][metric] for row in rows], ddof=1)) if len(rows) > 1 else None
        threshold = effective_threshold(manifest, metric)
        factors = {}
        for name in factor_names:
            low = by_reason.get(f"ofat:{name}:low")
            high = by_reason.get(f"ofat:{name}:high")
            usable = bool(
                low and high and low["valid"] and high["valid"]
                and low["metrics_valid"] and high["metrics_valid"]
                and finite(low["metrics"].get(metric))
                and finite(high["metrics"].get(metric))
                and (
                    metric in REACHABILITY_METRICS
                    or (low["depth_matched_to_spec"] and high["depth_matched_to_spec"])
                )
            )
            effect = high["metrics"][metric] - low["metrics"][metric] if usable else None
            factors[name] = {
                "low_case_id": low["case_id"] if low else None,
                "high_case_id": high["case_id"] if high else None,
                "low_value": low["metrics"].get(metric) if low else None,
                "high_value": high["metrics"].get(metric) if high else None,
                "high_minus_low": effect,
                "absolute_effect_over_effective_threshold": (
                    abs(effect) / threshold
                    if finite(effect) and finite(threshold) and threshold > 0 else None
                ),
                "standardized_effect_over_observed_output_sd": (
                    effect / output_sd
                    if finite(effect) and finite(output_sd) and output_sd > 0 else None
                ),
                "paired_noise_term_available": False,
                "evidence_status": "unconfirmed_independent_stream_contrast",
            }
        result[metric] = {
            "effective_threshold": threshold,
            "observed_output_sd": output_sd,
            "factor_effects": factors,
        }
    return result


def model_columns(coordinates, interactions, *, include_interactions=True):
    values = {
        name: 2.0 * float(coordinates[name]) - 1.0
        for name in builder.EXPECTED_FACTOR_NAMES
    }
    columns = [1.0]
    columns.extend(values[name] for name in builder.EXPECTED_FACTOR_NAMES)
    columns.extend(values[name] ** 2 for name in builder.EXPECTED_FACTOR_NAMES)
    if include_interactions:
        columns.extend(values[first] * values[second] for first, second in interactions)
    return columns


def grouped_holdout_models(reviewed, manifest):
    interactions = tuple(
        tuple(row["factors"])
        for row in manifest["design"]["predeclared_interactions"]
    )
    result = {}
    for metric in RESPONSE_METRICS:
        rows = metric_rows(reviewed, metric)
        ordered_ids = sorted(row["recipe_id"] for row in rows)
        fold_by_id = {recipe_id: index % 4 for index, recipe_id in enumerate(ordered_ids)}
        threshold = effective_threshold(manifest, metric)
        full_term_count = 1 + 2 * len(builder.EXPECTED_FACTOR_NAMES) + len(interactions)
        base_term_count = 1 + 2 * len(builder.EXPECTED_FACTOR_NAMES)
        if len(rows) < full_term_count + 8:
            result[metric] = {
                "status": "insufficient_uncensored_or_depth_matched_recipes",
                "usable_recipe_count": len(rows),
                "required_minimum": full_term_count + 8,
                "effective_threshold": threshold,
                "hypothesis_model_adequate": False,
            }
            continue

        def matrix(selected, include_interactions=True):
            return np.asarray([
                model_columns(
                    row["normalized_coordinates"],
                    interactions,
                    include_interactions=include_interactions,
                )
                for row in selected
            ], dtype=float)

        folds = []
        observed_all = []
        full_predicted_all = []
        base_predicted_all = []
        insufficient = False
        for fold in range(4):
            train = [row for row in rows if fold_by_id[row["recipe_id"]] != fold]
            test = [row for row in rows if fold_by_id[row["recipe_id"]] == fold]
            full_train = matrix(train, True)
            base_train = matrix(train, False)
            if (
                len(train) < full_term_count
                or not test
                or np.linalg.matrix_rank(full_train) < full_term_count
                or np.linalg.matrix_rank(base_train) < base_term_count
            ):
                insufficient = True
                break
            response = np.asarray([row["metrics"][metric] for row in train])
            full_coefficients = np.linalg.lstsq(full_train, response, rcond=None)[0]
            base_coefficients = np.linalg.lstsq(base_train, response, rcond=None)[0]
            observed = np.asarray([row["metrics"][metric] for row in test])
            full_prediction = matrix(test, True) @ full_coefficients
            base_prediction = matrix(test, False) @ base_coefficients
            observed_all.extend(observed.tolist())
            full_predicted_all.extend(full_prediction.tolist())
            base_predicted_all.extend(base_prediction.tolist())
            folds.append({
                "fold": fold,
                "train_recipe_count": len(train),
                "test_recipe_count": len(test),
                "full_matrix_rank": int(np.linalg.matrix_rank(full_train)),
                "base_matrix_rank": int(np.linalg.matrix_rank(base_train)),
                "full_rmse": float(np.sqrt(np.mean((full_prediction - observed) ** 2))),
                "base_without_interactions_rmse": float(
                    np.sqrt(np.mean((base_prediction - observed) ** 2))
                ),
            })
        if insufficient:
            result[metric] = {
                "status": "fold_rank_or_sample_failure",
                "usable_recipe_count": len(rows),
                "effective_threshold": threshold,
                "hypothesis_model_adequate": False,
            }
            continue
        observed = np.asarray(observed_all)
        full_prediction = np.asarray(full_predicted_all)
        base_prediction = np.asarray(base_predicted_all)
        full_rmse = float(np.sqrt(np.mean((full_prediction - observed) ** 2)))
        base_rmse = float(np.sqrt(np.mean((base_prediction - observed) ** 2)))
        all_matrix = matrix(rows, True)
        response = np.asarray([row["metrics"][metric] for row in rows])
        coefficients, _, rank, singular = np.linalg.lstsq(all_matrix, response, rcond=None)
        predicted_effects = {}
        center = {name: 0.5 for name in builder.EXPECTED_FACTOR_NAMES}
        output_sd = float(np.std(response, ddof=1)) if len(response) > 1 else None
        for name in builder.EXPECTED_FACTOR_NAMES:
            low = dict(center)
            high = dict(center)
            low[name] = 0.0
            high[name] = 1.0
            effect = float(
                (
                    np.asarray(model_columns(high, interactions, include_interactions=True))
                    - np.asarray(model_columns(low, interactions, include_interactions=True))
                ) @ coefficients
            )
            predicted_effects[name] = {
                "modeled_centerline_high_minus_low": effect,
                "absolute_effect_over_effective_threshold": (
                    abs(effect) / threshold
                    if finite(threshold) and threshold > 0 else None
                ),
                "standardized_effect_over_observed_output_sd": (
                    effect / output_sd
                    if finite(output_sd) and output_sd > 0 else None
                ),
                "evidence_status": "unconfirmed_model_based_hypothesis",
            }
        interaction_offset = 1 + 2 * len(builder.EXPECTED_FACTOR_NAMES)
        interaction_contrasts = {
            f"{first}:{second}": {
                "modeled_corner_difference_of_differences": float(
                    4.0 * coefficients[interaction_offset + index]
                ),
                "absolute_contrast_over_effective_threshold": (
                    abs(4.0 * coefficients[interaction_offset + index]) / threshold
                    if finite(threshold) and threshold > 0 else None
                ),
                "evidence_status": "unconfirmed_model_based_interaction_hypothesis",
            }
            for index, (first, second) in enumerate(interactions)
        }
        improvement = (base_rmse - full_rmse) / base_rmse if base_rmse > 0 else None
        adequate = bool(
            rank == full_term_count
            and finite(threshold)
            and full_rmse <= threshold
        )
        result[metric] = {
            "status": "fit",
            "usable_recipe_count": len(rows),
            "response_role": (
                "reachability" if metric in REACHABILITY_METRICS
                else "depth_matched_morphology"
            ),
            "grouping": "deterministic_recipe_grouped_4_fold; one independent stream per recipe",
            "input_encoding": "linear/log/signed-log physical inputs are first mapped to their declared normalized transformed coordinates; centered main, squared-curvature, and predeclared interaction terms are then fit",
            "full_term_count": full_term_count,
            "base_without_interactions_term_count": base_term_count,
            "matrix_rank": int(rank),
            "condition_number": (
                float(singular[0] / singular[-1]) if singular[-1] > 0 else None
            ),
            "folds": folds,
            "grouped_holdout_rmse": full_rmse,
            "base_without_interactions_grouped_holdout_rmse": base_rmse,
            "interaction_terms_holdout_improvement_fraction": improvement,
            "interaction_terms_meet_5pct_holdout_rule": bool(
                finite(improvement) and improvement >= 0.05
            ),
            "effective_threshold": threshold,
            "grouped_holdout_rmse_over_effective_threshold": (
                full_rmse / threshold
                if finite(threshold) and threshold > 0 else None
            ),
            "hypothesis_model_adequate": adequate,
            "modeled_factor_effects": predicted_effects,
            "modeled_interaction_contrasts": interaction_contrasts,
            "interpretation": "adequacy permits hypothesis ranking only; no effect is confirmed without Stage 2b/2e repeats",
        }
    return result


def exact_interaction_contrasts(reviewed, manifest):
    by_reason = exact_anchor_rows(reviewed)
    result = {}
    for declaration in manifest["design"]["predeclared_interactions"]:
        first, second = declaration["factors"]
        name = f"{first}:{second}"
        result[name] = {"basis": declaration["basis"], "metrics": {}}
        for metric in RESPONSE_METRICS:
            cells = {}
            for first_level in ("low", "high"):
                for second_level in ("low", "high"):
                    reason = f"interaction:{first}:{second}:{first_level}:{second_level}"
                    row = by_reason.get(reason)
                    cells[f"{first_level}:{second_level}"] = row
            usable = all(
                row and row["valid"] and row["metrics_valid"]
                and finite(row["metrics"].get(metric))
                and (metric in REACHABILITY_METRICS or row["depth_matched_to_spec"])
                for row in cells.values()
            )
            contrast = None
            if usable:
                contrast = (
                    cells["high:high"]["metrics"][metric]
                    - cells["high:low"]["metrics"][metric]
                    - cells["low:high"]["metrics"][metric]
                    + cells["low:low"]["metrics"][metric]
                )
            threshold = effective_threshold(manifest, metric)
            result[name]["metrics"][metric] = {
                "difference_of_differences": contrast,
                "absolute_contrast_over_effective_threshold": (
                    abs(contrast) / threshold
                    if finite(contrast) and finite(threshold) and threshold > 0 else None
                ),
                "cell_case_ids": {
                    cell: row["case_id"] if row else None for cell, row in cells.items()
                },
                "paired_noise_term_available": False,
                "evidence_status": "unconfirmed_exact_2x2_independent_stream_contrast",
            }
    return result


def failure_boundaries(reviewed, factor_names):
    by_reason = exact_anchor_rows(reviewed)
    nominal = by_reason.get("nominal")
    result = {}
    for name in factor_names:
        levels = [
            ("low", by_reason.get(f"ofat:{name}:low")),
            ("nominal", nominal),
            ("high", by_reason.get(f"ofat:{name}:high")),
        ]
        factor = {
            row["name"]: row
            for row in builder.common.strict_load(
                runner.ROOT / builder.DEFAULT_SPEC
            )["factors"]
        }[name]
        exact_levels = []
        for level, row in levels:
            exact_levels.append({
                "level": level,
                "input_value": factor[level],
                "case_id": row["case_id"] if row else None,
                "valid": row["valid"] if row else False,
                "gates": row["gates"] if row else None,
                "trajectory_classification": row["trajectory_classification"] if row else None,
            })
        brackets = []
        for gate in GATE_NAMES:
            for (left_level, left), (right_level, right) in zip(levels, levels[1:]):
                if (
                    left and right and left["valid"] and right["valid"]
                    and left["gates"][gate] != right["gates"][gate]
                ):
                    brackets.append({
                        "gate": gate,
                        "left_level": left_level,
                        "left_value": factor[left_level],
                        "left_pass": left["gates"][gate],
                        "right_level": right_level,
                        "right_value": factor[right_level],
                        "right_pass": right["gates"][gate],
                        "status": "observed_OFAT_transition_bracket_hypothesis",
                    })
        whole_design = {}
        for gate in GATE_NAMES:
            passing = [
                row["recipe"][name] for row in reviewed
                if row["valid"] and row["gates"][gate]
            ]
            failing = [
                row["recipe"][name] for row in reviewed
                if row["valid"] and not row["gates"][gate]
            ]
            whole_design[gate] = {
                "pass_count": len(passing),
                "pass_observed_min": min(passing) if passing else None,
                "pass_observed_max": max(passing) if passing else None,
                "fail_count": len(failing),
                "fail_observed_min": min(failing) if failing else None,
                "fail_observed_max": max(failing) if failing else None,
                "interpretation": "multivariate association range; not a one-factor boundary",
            }
        result[name] = {
            "exact_low_nominal_high": exact_levels,
            "exact_ofat_transition_brackets": brackets,
            "whole_design_gate_ranges": whole_design,
        }
    return result


def hypothesis_register(reviewed, manifest, models, ofat, interactions, boundaries):
    hypotheses = []
    for metric, model in models.items():
        if model.get("status") != "fit":
            continue
        if metric == "mask_remaining_height":
            continue
        for name, effect in model["modeled_factor_effects"].items():
            model_ratio = effect["absolute_effect_over_effective_threshold"]
            exact_ratio = ofat[metric]["factor_effects"][name][
                "absolute_effect_over_effective_threshold"
            ]
            if any(finite(value) and value >= 1.0 for value in (model_ratio, exact_ratio)):
                hypotheses.append({
                    "type": "main_effect_confirmation_candidate",
                    "factor": name,
                    "metric": metric,
                    "modeled_effect_over_threshold": model_ratio,
                    "exact_ofat_effect_over_threshold": exact_ratio,
                    "model_adequate": model["hypothesis_model_adequate"],
                    "next_test": "Stage 2b diverse repeat and Stage 2e four-seed low/high confirmation",
                    "status": "hypothesis_not_confirmed",
                })
        if model.get("interaction_terms_meet_5pct_holdout_rule"):
            for name, modeled in model["modeled_interaction_contrasts"].items():
                exact = interactions[name]["metrics"][metric]
                ratios = (
                    modeled["absolute_contrast_over_effective_threshold"],
                    exact["absolute_contrast_over_effective_threshold"],
                )
                if any(finite(value) and value >= 1.0 for value in ratios):
                    hypotheses.append({
                        "type": "interaction_confirmation_candidate",
                        "interaction": name,
                        "metric": metric,
                        "modeled_contrast_over_threshold": ratios[0],
                        "exact_2x2_contrast_over_threshold": ratios[1],
                        "holdout_improvement_fraction": model[
                            "interaction_terms_holdout_improvement_fraction"
                        ],
                        "next_test": "Stage 2e exact 2x2 on four paired disjoint streams",
                        "status": "hypothesis_not_confirmed",
                    })
    for name, boundary in boundaries.items():
        for bracket in boundary["exact_ofat_transition_brackets"]:
            hypotheses.append({
                "type": "failure_boundary_confirmation_candidate",
                "factor": name,
                **bracket,
                "next_test": "expand or bisect only after independent confirmation",
                "status": "hypothesis_not_confirmed",
            })
    return hypotheses


def crossing_summary(reviewed):
    counts = defaultdict(int)
    for row in reviewed:
        counts[row["target_depth_crossing"]["status"]] += 1
    return {
        "status_counts": dict(sorted(counts.items())),
        "definition": "first linearly interpolated cycle at depth 1.25 when consecutive saved checkpoints bracket it",
        "model_phase_duration_definition": "initial_etch_time + crossing_cycle * (1 passivation + 1 passivation-removal + etch_time); simulator process-duration units, not wall-clock or calibrated fab time",
        "censoring_rule": "crossings before the first saved checkpoint are left-censored; trajectories below target at the final checkpoint are right-censored; neither is imputed into correlations or response models",
    }


def build_summary(manifest, rows_path):
    errors = runner.validate_manifest(manifest)
    if errors:
        raise ValueError("invalid V3 Stage 2a manifest: " + "; ".join(errors))
    cases = runner.expand_cases(manifest)
    completed = runner.audit_existing_rows(rows_path, cases)
    rows = {row["case_id"]: row for row in success_rows(rows_path)}
    reviewed = [
        review_case(rows[case["case_id"]], case, rows_path)
        for case in cases if case["case_id"] in completed
    ]
    factor_names = list(builder.EXPECTED_FACTOR_NAMES)
    correlations = knob_output_correlations(reviewed, factor_names)
    ofat = exact_ofat_effects(reviewed, manifest, factor_names)
    models = grouped_holdout_models(reviewed, manifest)
    interactions = exact_interaction_contrasts(reviewed, manifest)
    boundaries = failure_boundaries(reviewed, factor_names)
    hypotheses = hypothesis_register(
        reviewed, manifest, models, ofat, interactions, boundaries
    )
    complete = bool(len(reviewed) == len(cases) and all(row["valid"] for row in reviewed))
    return {
        "campaign": manifest["campaign"],
        "methodology_epoch": manifest["methodology_epoch"],
        "labels": manifest["labels"],
        "expected_case_count": len(cases),
        "reviewed_case_count": len(reviewed),
        "valid_case_count": sum(row["valid"] for row in reviewed),
        "scientific_invalid_metric_count": sum(
            row["valid"] and not row["metrics_valid"] for row in reviewed
        ),
        "scientific_invalid_metric_cases": [
            {
                "case_id": row["case_id"],
                "reasons": row["scientific_invalid_reasons"],
                "checkpoint_path": row["checkpoint_path"],
                "gates": row["gates"],
            }
            for row in reviewed if row["valid"] and not row["metrics_valid"]
        ],
        "invalid_cases": [
            {"case_id": row["case_id"], "errors": row["errors"]}
            for row in reviewed if not row["valid"]
        ],
        "hard_gate_pass_count": sum(row["hard_gate_pass"] for row in reviewed),
        "depth_horizon_censored_count": sum(
            row["depth_horizon_censored"] for row in reviewed
        ),
        "depth_matched_case_count": sum(
            row["valid"] and row["metrics_valid"] and row["depth_matched_to_spec"]
            for row in reviewed
        ),
        "target_depth_crossing": crossing_summary(reviewed),
        "design_input_independence": manifest["design"]["design"][
            "input_independence_preflight"
        ],
        "effective_screen_thresholds": manifest["effective_screen_thresholds"],
        "paired_noise": {
            "status": "unavailable_in_stage2a",
            "reason": "one independent stream was allocated per recipe to maximize broad surface coverage",
            "required_next_stage": "V3 Stage 2b repeatability check",
        },
        "mask_response_interpretation": "Mask remaining height is retained as a hard-gate/numerical diagnostic only. With mask_ion_rate fixed at zero, Stage 2a cannot create a mask-erosion sensitivity hypothesis.",
        "knob_output_correlations": correlations,
        "exact_low_high_effects": ofat,
        "grouped_holdout_models": models,
        "exact_predeclared_interaction_contrasts": interactions,
        "failure_boundary_hypotheses": boundaries,
        "hypothesis_register": hypotheses,
        "excluded_wired_controls": manifest["design"]["excluded_wired_controls"],
        "reviewed_cases": reviewed,
        "decision": {
            "classification": (
                "complete_stage2a_hypothesis_screen"
                if complete else "incomplete_or_invalid_stage2a_screen"
            ),
            "complete_valid_matrix": complete,
            "hypotheses_available": complete,
            "confirmed_factor_authorized": False,
            "recipe_authorized": False,
            "process_window_authorized": False,
            "downstream_recipe_authorized": False,
            "traveler_relevance_authorized": False,
            "full_traveler_authorized": False,
            "next_required_evidence": "Stage 2b repeats, downstream propagation, and Stage 2e paired confirmation",
        },
        "authority": manifest["authority"],
    }


def markdown(summary):
    preflight = summary["design_input_independence"]
    lines = [
        "# V3 Stage 2a broad Bosch review",
        "",
        f"Status: `{summary['decision']['classification']}`. Valid cases: "
        f"{summary['valid_case_count']}/{summary['expected_case_count']}.",
        "",
        "This stage generates effect, interaction, and failure-boundary hypotheses. "
        "It cannot confirm a sensitive knob or recommend a recipe.",
        "",
        "## Design check",
        "",
        f"Maximum absolute input Pearson correlation: {preflight['maximum_absolute_pearson']:.4f}; "
        f"Spearman: {preflight['maximum_absolute_spearman']:.4f}; maximum VIF: "
        f"{preflight['maximum_vif']:.4f}.",
        "",
        "## Evidence limits",
        "",
        "Each recipe has one independent stochastic interval. Paired noise is not "
        "estimated here; Stage 2b and Stage 2e must repeat promoted effects. "
        "Mask erosion is a separate bounded hard-gate challenge, and cycle count is "
        "delegated to the matched-total-dose Stage 2c test.",
        "",
        "Target-depth crossing uses linear interpolation between saved cycle "
        "checkpoints. Its modeled duration is simulator phase duration, not wall-clock "
        "time or a calibrated fab setting.",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    manifest_path = runner.project_path(args.manifest)
    rows_path = runner.project_path(args.rows)
    json_path = runner.project_path(args.json)
    markdown_path = runner.project_path(args.markdown)
    manifest = gate0.strict_json_loads(manifest_path.read_text())
    summary = build_summary(manifest, rows_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown(summary) + "\n")
    print(json.dumps({
        "classification": summary["decision"]["classification"],
        "valid": summary["valid_case_count"],
        "expected": summary["expected_case_count"],
        "hypothesis_count": len(summary["hypothesis_register"]),
        "recipe_authorized": False,
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

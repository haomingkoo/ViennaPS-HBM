"""Independent, bounded review of the V3 pattern-geometry screen."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np

import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_skew_stage1_runner as runner


DEFAULT_SUMMARY = Path(
    "autoresearch-results/restart_audit/v3_pattern_skew_stage1_summary.json"
)
DEFAULT_REVIEW = Path(
    "autoresearch-results/restart_audit/v3_pattern_skew_stage1_review.md"
)
PRIMITIVE_GATES = (
    "pattern_width",
    "pattern_height",
    "pattern_opening",
    "etch_depth",
    "etch_cd_profile",
    "etch_bow",
    "etch_mask_resolved",
)
OUTPUT_PATHS = {
    "pattern_opening_cd_surface": ("initial_pattern", "opening_cd_surface"),
    "pattern_opening_cd_bottom": ("initial_pattern", "opening_cd_bottom"),
    "pattern_opening_cd_middle": ("initial_pattern", "opening_cd_middle"),
    "pattern_opening_cd_top": ("initial_pattern", "opening_cd_top"),
    "pattern_mask_height": ("initial_pattern", "mask_height"),
    "pattern_opening_center_shift": ("initial_pattern", "opening_center_shift"),
    "pattern_mask_sidewall_angle_deg": ("initial_pattern", "mask_sidewall_angle_deg"),
    "etch_depth": ("selected_cycle_metrics", "etch", "depth"),
    "etch_cd_top": ("selected_cycle_metrics", "etch", "cd_top"),
    "etch_cd_middle": ("selected_cycle_metrics", "etch", "cd_middle"),
    "etch_cd_bottom": ("selected_cycle_metrics", "etch", "cd_bottom"),
    "etch_max_cd_error": ("selected_cycle_metrics", "etch", "max_cd_error"),
    "etch_sidewall_angle_deg": ("selected_cycle_metrics", "etch", "sidewall_angle_deg"),
    "etch_max_bow": ("selected_cycle_metrics", "etch", "max_bow"),
    "etch_scallop_rms": ("selected_cycle_metrics", "etch", "scallop_rms"),
    "mask_remaining_height": ("selected_cycle_metrics", "mask_remaining_height"),
    "selected_cycle": ("selected_cycle",),
}
NUMERICAL_METRIC_MAP = {
    "etch_depth": "depth",
    "etch_cd_top": "cd_top",
    "etch_cd_middle": "cd_middle",
    "etch_cd_bottom": "cd_bottom",
    "etch_max_cd_error": "max_cd_error",
    "etch_max_bow": "max_bow",
    "etch_scallop_rms": "scallop_rms",
    "mask_remaining_height": "mask_remaining_height",
}
DIMENSIONAL_OUTPUTS = {
    "pattern_opening_cd_surface",
    "pattern_opening_cd_bottom",
    "pattern_opening_cd_middle",
    "pattern_opening_cd_top",
    "pattern_mask_height",
    "pattern_opening_center_shift",
    "etch_depth",
    "etch_cd_top",
    "etch_cd_middle",
    "etch_cd_bottom",
    "etch_max_cd_error",
    "etch_max_bow",
    "etch_scallop_rms",
    "mask_remaining_height",
}


def _value(row, path):
    value = row
    for name in path:
        if not isinstance(value, dict) or name not in value:
            raise ValueError(f"missing review value: {'.'.join(path)}")
        value = value[name]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"non-numeric review value: {'.'.join(path)}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"nonfinite review value: {'.'.join(path)}")
    return value


def _rank(values):
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + end - 1) + 1.0
        start = end
    return ranks


def _correlation(first, second):
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    if len(first) != len(second) or len(first) < 2:
        return None
    if np.ptp(first) == 0.0 or np.ptp(second) == 0.0:
        return None
    return float(np.corrcoef(first, second)[0, 1])


def _correlations(first, second):
    return {
        "pearson": _correlation(first, second),
        "spearman": _correlation(_rank(first), _rank(second)),
    }


def _observations(rows):
    observations = []
    for row in rows:
        outputs = {name: _value(row, path) for name, path in OUTPUT_PATHS.items()}
        observations.append({
            "case_id": row["case_id"],
            "pattern_id": row["pattern"]["pattern_id"],
            "levels": dict(row["pattern"]["levels"]),
            "inputs": dict(row["pattern"]["input_geometry"]),
            "outputs": outputs,
            "gates": dict(row["gates"]),
            "hard_gate_pass": row["hard_gate_pass"],
            "selection_eligible": row["selection_eligible"],
            "target_depth_crossing": dict(row["target_depth_crossing"]),
            "rng_consumption": dict(row["rng_consumption"]),
            "checkpoint_path": row["checkpoint_path"],
            "checkpoint_sha256": row["checkpoint_sha256"],
        })
    return observations


def design_independence(observations, factor_names):
    matrix = {
        first: {
            second: _correlations(
                [row["inputs"][first] for row in observations],
                [row["inputs"][second] for row in observations],
            )
            for second in factor_names
        }
        for first in factor_names
    }
    off_diagonal = [
        abs(matrix[first][second][method])
        for index, first in enumerate(factor_names)
        for second in factor_names[index + 1:]
        for method in ("pearson", "spearman")
        if matrix[first][second][method] is not None
    ]
    return {
        "correlation_matrix": matrix,
        "maximum_absolute_off_diagonal_correlation": max(off_diagonal, default=0.0),
        "interpretation": (
            "The complete balanced factorial moves each geometry input "
            "independently. This is a design check, not a physical correlation."
        ),
    }


def effective_thresholds(manifest, project_root=runner.ROOT):
    declaration = manifest["source_artifacts"]["numerical_release"]
    path = runner._resolve(project_root, declaration["path"])
    release = gate0.strict_json_loads(path.read_text())
    errors = runner.validate_numerical_release(release)
    if errors or declaration["sha256"] != runner.file_sha256(path):
        raise ValueError("numerical release changed during review")
    released = release["ray_bridge"]["metric_results"]
    practical = manifest["design"]["practical_screen_changes"]
    two_cells = (
        manifest["design"]["threshold_policy"]["geometry_resolution_cells"]
        * manifest["design"]["numerics"]["grid_delta"]
    )
    results = {}
    for output in OUTPUT_PATHS:
        numerical_name = NUMERICAL_METRIC_MAP.get(output)
        numerical = (
            float(released[numerical_name]["observed_max_absolute_delta"])
            if numerical_name is not None else None
        )
        geometry = two_cells if output in DIMENSIONAL_OUTPUTS else None
        components = [float(practical[output])]
        components.extend(
            value for value in (numerical, geometry) if value is not None
        )
        results[output] = {
            "practical_engineering_change": float(practical[output]),
            "released_numerical_fidelity_shift": numerical,
            "two_grid_cells": geometry,
            "three_times_paired_stochastic_sd": None,
            "paired_noise_term_status": (
                "unavailable in this single-block stage; confirmation must "
                "supply disjoint paired blocks"
            ),
            "effective_screen_threshold": max(components),
            "authority": "confirmation_hypothesis_screen_only",
        }
    return results


def screen_effects(observations, factor_names, thresholds):
    results = {}
    for factor in factor_names:
        factor_result = {}
        for output in OUTPUT_PATHS:
            means = {
                level: float(np.mean([
                    row["outputs"][output]
                    for row in observations
                    if row["levels"][factor] == level
                ]))
                for level in ("low", "nominal", "high")
            }
            counts = {
                level: sum(row["levels"][factor] == level for row in observations)
                for level in ("low", "nominal", "high")
            }
            span = max(means.values()) - min(means.values())
            low_to_high = means["high"] - means["low"]
            input_means = {
                level: float(np.mean([
                    row["inputs"][factor]
                    for row in observations
                    if row["levels"][factor] == level
                ]))
                for level in ("low", "nominal", "high")
            }
            nominal_fraction = (
                (input_means["nominal"] - input_means["low"])
                / (input_means["high"] - input_means["low"])
            )
            linear_nominal = means["low"] + nominal_fraction * (
                means["high"] - means["low"]
            )
            curvature = means["nominal"] - linear_nominal
            threshold = float(thresholds[output]["effective_screen_threshold"])
            factor_result[output] = {
                "level_counts": counts,
                "level_input_means": input_means,
                "marginal_means": means,
                "low_to_high_effect": low_to_high,
                "nominal_minus_linear_edge_interpolation": curvature,
                "maximum_marginal_span": span,
                "effective_screen_threshold": threshold,
                "exceeds_effective_screen_threshold": span >= threshold,
                "authority": "confirmation_candidate_only",
            }
        results[factor] = factor_result
    return results


def interaction_screens(observations, factor_names, thresholds):
    results = {}
    for first_index, first in enumerate(factor_names):
        for second in factor_names[first_index + 1:]:
            pair_name = f"{first}__x__{second}"
            pair_results = {}
            for output in OUTPUT_PATHS:
                cell_means = {}
                cell_counts = {}
                for first_level in ("low", "nominal", "high"):
                    for second_level in ("low", "nominal", "high"):
                        values = [
                            row["outputs"][output]
                            for row in observations
                            if row["levels"][first] == first_level
                            and row["levels"][second] == second_level
                        ]
                        key = f"{first_level}__{second_level}"
                        cell_means[key] = float(np.mean(values))
                        cell_counts[key] = len(values)
                difference_of_differences = (
                    cell_means["high__high"]
                    - cell_means["low__high"]
                    - cell_means["high__low"]
                    + cell_means["low__low"]
                )
                threshold = float(
                    thresholds[output]["effective_screen_threshold"]
                )
                grand_mean = float(np.mean([
                    row["outputs"][output] for row in observations
                ]))
                first_means = {
                    level: float(np.mean([
                        row["outputs"][output] for row in observations
                        if row["levels"][first] == level
                    ]))
                    for level in ("low", "nominal", "high")
                }
                second_means = {
                    level: float(np.mean([
                        row["outputs"][output] for row in observations
                        if row["levels"][second] == level
                    ]))
                    for level in ("low", "nominal", "high")
                }
                additive_residuals = {}
                for first_level in ("low", "nominal", "high"):
                    for second_level in ("low", "nominal", "high"):
                        key = f"{first_level}__{second_level}"
                        additive_residuals[key] = (
                            cell_means[key]
                            - first_means[first_level]
                            - second_means[second_level]
                            + grand_mean
                        )
                residual_span = max(additive_residuals.values()) - min(
                    additive_residuals.values()
                )
                exceeds = (
                    abs(difference_of_differences) >= threshold
                    or residual_span >= threshold
                )
                pair_results[output] = {
                    "three_by_three_cell_counts": cell_counts,
                    "three_by_three_cell_means": cell_means,
                    "low_high_difference_of_differences": difference_of_differences,
                    "three_by_three_additive_residuals": additive_residuals,
                    "three_by_three_residual_span": residual_span,
                    "effective_screen_threshold": threshold,
                    "exceeds_effective_screen_threshold": exceeds,
                    "threshold_interpretation": (
                        "V3 hypothesis screen compares DoD or full-grid "
                        "non-additivity with T_y; disjoint-block confirmation "
                        "is still required"
                    ),
                    "authority": "interaction_confirmation_hypothesis_only",
                }
            results[pair_name] = pair_results
    return results


def knob_output_correlations(observations, factor_names):
    return {
        factor: {
            output: _correlations(
                [row["inputs"][factor] for row in observations],
                [row["outputs"][output] for row in observations],
            )
            for output in OUTPUT_PATHS
        }
        for factor in factor_names
    }


def failure_visibility(observations, execution_failures):
    pass_counts = {
        gate: sum(row["gates"].get(gate) is True for row in observations)
        for gate in PRIMITIVE_GATES
    }
    hard_failures = []
    for row in observations:
        failed_gates = [
            gate for gate in PRIMITIVE_GATES if row["gates"].get(gate) is not True
        ]
        if not row["selection_eligible"]:
            failed_gates.insert(0, "depth_matched_selection")
        if failed_gates:
            hard_failures.append({
                "case_id": row["case_id"],
                "pattern_id": row["pattern_id"],
                "inputs": row["inputs"],
                "failed_gates": failed_gates,
                "etch_depth": row["outputs"]["etch_depth"],
                "etch_cd_top": row["outputs"]["etch_cd_top"],
                "etch_cd_middle": row["outputs"]["etch_cd_middle"],
                "etch_cd_bottom": row["outputs"]["etch_cd_bottom"],
                "etch_max_bow": row["outputs"]["etch_max_bow"],
                "mask_remaining_height": row["outputs"]["mask_remaining_height"],
            })
    return {
        "execution_failure_attempt_count": len(execution_failures),
        "execution_failures": execution_failures,
        "primitive_gate_pass_counts": pass_counts,
        "hard_gate_pass_count": sum(row["hard_gate_pass"] is True for row in observations),
        "hard_gate_failure_count": len(hard_failures),
        "hard_gate_failures": hard_failures,
        "note": (
            "Low/high opening CD and mask-height rows deliberately stress the "
            "fixed product target. Their failures remain visible and are not "
            "evidence that a lithography recipe was simulated."
        ),
    }


def target_depth_crossing_review(observations, factor_names):
    bracketed = [
        row for row in observations
        if row["target_depth_crossing"].get("status") == "bracketed"
    ]
    censored = [
        {
            "case_id": row["case_id"],
            "pattern_id": row["pattern_id"],
            "inputs": row["inputs"],
            "status": row["target_depth_crossing"].get("status"),
        }
        for row in observations if row not in bracketed
    ]
    all_bracketed = bool(observations) and len(bracketed) == len(observations)
    result = {
        "bracketed_count": len(bracketed),
        "censored_count": len(censored),
        "censored_rows": censored,
        "all_cases_bracket_target": all_bracketed,
        "authority": (
            "descriptive etch-rate hypothesis only; wall-shape comparisons "
            "still use the selected depth-matched native checkpoint"
        ),
    }
    if bracketed:
        cycles = [
            row["target_depth_crossing"]["interpolated_cycle"]
            for row in bracketed
        ]
        result["observed_cycle_range"] = [min(cycles), max(cycles)]
    else:
        result["observed_cycle_range"] = None
    if all_bracketed:
        result["marginal_mean_cycle_by_factor_level"] = {
            factor: {
                level: float(np.mean([
                    row["target_depth_crossing"]["interpolated_cycle"]
                    for row in bracketed if row["levels"][factor] == level
                ]))
                for level in ("low", "nominal", "high")
            }
            for factor in factor_names
        }
        result["knob_correlations"] = {
            factor: _correlations(
                [row["inputs"][factor] for row in bracketed],
                [
                    row["target_depth_crossing"]["interpolated_cycle"]
                    for row in bracketed
                ],
            )
            for factor in factor_names
        }
    else:
        result["marginal_mean_cycle_by_factor_level"] = None
        result["knob_correlations"] = None
    return result


def rng_consumption_review(observations, policy):
    return {
        "declared_shared_interval": [
            policy["first_process_seed"], policy["last_process_seed"]
        ],
        "actual_last_process_seed_range": (
            [
                min(row["rng_consumption"]["actual_last_process_seed"] for row in observations),
                max(row["rng_consumption"]["actual_last_process_seed"] for row in observations),
            ]
            if observations else None
        ),
        "early_stop_shortened_case_count": sum(
            row["rng_consumption"]["early_stop_shortened_stream"] is True
            for row in observations
        ),
        "rows": [
            {
                "case_id": row["case_id"],
                "pattern_id": row["pattern_id"],
                **row["rng_consumption"],
            }
            for row in observations
        ],
        "interpretation": (
            "The full interval is reserved for every pattern arm; the actual "
            "prefix consumed is reported because early stopping can shorten a run."
        ),
    }


def review(manifest, rows, *, attempt_count=0, execution_failures=None):
    execution_failures = list(execution_failures or [])
    cases = runner.expand_cases(manifest)
    complete = len(rows) == len(cases)
    observations = _observations(rows)
    factor_names = [factor["name"] for factor in manifest["design"]["factors"]]
    summary = {
        "campaign": manifest["campaign"],
        "methodology_epoch": manifest["methodology_epoch"],
        "labels": manifest["labels"],
        "status": "complete" if complete else "incomplete",
        "expected_case_count": len(cases),
        "reviewed_success_count": len(rows),
        "attempt_count": attempt_count,
        "integrity": {
            "manifest_canonical_sha256": runner.canonical_sha256(manifest),
            "runtime_fingerprint": manifest["runtime_fingerprint"],
            "selected_checkpoint_authority": (
                "native domain, selected metrics, selected history record, "
                "case payload, and source/runtime hashes independently checked"
            ),
            "nonselected_history_limit": (
                "the full history has a canonical row hash and internal "
                "selection/crossing checks, but nonselected cycles do not have "
                "independent native checkpoints and remain descriptive"
            ),
            "artifact_write_semantics": (
                "JSON and Markdown are individually atomic; they are not a "
                "transactional pair, and the JSON summary is decision authority"
            ),
        },
        "missing_case_ids": sorted(
            {case["case_id"] for case in cases} - {row["case_id"] for row in rows}
        ),
        "numerics": manifest["design"]["numerics"],
        "pattern_gate_policy": manifest["design"]["pattern_gate_policy"],
        "rng_interpretation": {
            "block_id": manifest["design"]["rng_policy"]["block_id"],
            "shared_interval": [
                manifest["design"]["rng_policy"]["first_process_seed"],
                manifest["design"]["rng_policy"]["last_process_seed"],
            ],
            "stochastic_variance_estimated": False,
            "pointwise_common_random_numbers_claimed": False,
            "effect_confirmation_authorized": False,
            "reason": (
                "All 27 skews use one controlled nuisance block. This isolates "
                "broad geometry contrasts for screening but supplies no "
                "independent stochastic replication."
            ),
        },
        "failure_visibility": failure_visibility(observations, execution_failures),
        "target_depth_crossing": target_depth_crossing_review(
            observations, factor_names
        ),
        "rng_consumption": rng_consumption_review(
            observations, manifest["design"]["rng_policy"]
        ),
        "observations": observations,
        "authority": manifest["authority"],
        "claims_prohibited": manifest["design"]["unsupported_claims"],
    }
    if complete:
        thresholds = effective_thresholds(manifest)
        summary["effective_screen_thresholds"] = thresholds
        summary["design_independence"] = design_independence(observations, factor_names)
        summary["direct_screen_effects"] = screen_effects(
            observations,
            factor_names,
            thresholds,
        )
        summary["interaction_hypothesis_screens"] = interaction_screens(
            observations,
            factor_names,
            thresholds,
        )
        summary["knob_output_correlations"] = knob_output_correlations(
            observations, factor_names
        )
        promoted_main = {
            factor: sorted(
                output for output, result in results.items()
                if result["exceeds_effective_screen_threshold"]
            )
            for factor, results in summary["direct_screen_effects"].items()
        }
        promoted_interactions = {
            pair: sorted(
                output for output, result in results.items()
                if result["exceeds_effective_screen_threshold"]
            )
            for pair, results in summary["interaction_hypothesis_screens"].items()
        }
        summary["confirmation_candidates"] = {
            "main_effects": promoted_main,
            "interactions": promoted_interactions,
        }
        summary["decision"] = {
            "classification": "screen_complete_requires_disjoint_confirmation",
            "confirmed_factors": [],
            "confirmation_candidates": summary["confirmation_candidates"],
            "next_required_evidence": (
                "Repeat every promoted main effect on four disjoint RNG blocks, "
                "then test pattern-by-Bosch interactions and exact downstream "
                "propagation before calling any pattern input traveler-relevant."
            ),
            "recipe_authorized": False,
            "process_window_authorized": False,
            "full_traveler_authorized": False,
            "automatic_launch_authorized": False,
        }
    else:
        summary["effective_screen_thresholds"] = None
        summary["design_independence"] = None
        summary["direct_screen_effects"] = None
        summary["interaction_hypothesis_screens"] = None
        summary["knob_output_correlations"] = None
        summary["confirmation_candidates"] = {
            "main_effects": {},
            "interactions": {},
        }
        summary["decision"] = {
            "classification": "screen_incomplete_no_effect_decision",
            "confirmed_factors": [],
            "recipe_authorized": False,
            "process_window_authorized": False,
            "full_traveler_authorized": False,
            "automatic_launch_authorized": False,
        }
    return summary


def markdown(summary):
    lines = [
        "# V3 Stage 1 pattern-geometry screen",
        "",
        f"Status: **{summary['status']}**. Independently reviewed native checkpoints: "
        f"{summary['reviewed_success_count']}/{summary['expected_case_count']}.",
        "",
        "This stage directly skews measured opening CD, mask height, and mask taper. "
        "It does not simulate exposure dose or focus.",
        "",
        "All cases use grid 0.00125, 2,000 rays per point, the fixed reference "
        "Bosch recipe, depth-matched cycle selection, and one shared 43-seed "
        "nuisance block. The block supports broad screening, not a noise estimate "
        "or confirmation claim.",
        "",
        "## Gate visibility",
        "",
        f"Hard-gate pass: {summary['failure_visibility']['hard_gate_pass_count']}/"
        f"{summary['reviewed_success_count']}; execution failure attempts: "
        f"{summary['failure_visibility']['execution_failure_attempt_count']}.",
        f"Target-depth crossing bracketed: "
        f"{summary['target_depth_crossing']['bracketed_count']}/"
        f"{summary['reviewed_success_count']}; censored: "
        f"{summary['target_depth_crossing']['censored_count']}.",
        "",
        "| Gate | Passes |",
        "|---|---:|",
    ]
    for gate, count in summary["failure_visibility"]["primitive_gate_pass_counts"].items():
        lines.append(f"| {gate} | {count}/{summary['reviewed_success_count']} |")
    if summary["status"] == "complete":
        lines.extend([
            "",
            "## Broad-screen candidates",
            "",
            "A listed output crossed its effective numerical-aware screen threshold. "
            "It is a candidate for disjoint-block confirmation, not a confirmed effect.",
            "",
            "| Geometry input | Outputs crossing the screen threshold |",
            "|---|---|",
        ])
        for factor, outputs in summary["confirmation_candidates"]["main_effects"].items():
            lines.append(f"| {factor} | {', '.join(outputs) if outputs else 'none'} |")
        lines.extend([
            "",
            "Low/high difference-of-differences for all three pattern-input "
            "pairs are listed as interaction hypotheses in the JSON. They also "
            "require disjoint-block confirmation.",
            "",
            "The input-input Pearson/Spearman correlations are reported separately "
            "in the JSON summary; the balanced factorial should keep them at zero. "
            "Knob-output correlations and marginal low/nominal/high effects are also "
            "reported there. Neither is interpreted as a calibrated fab relationship.",
        ])
    lines.extend([
        "",
        "## Decision",
        "",
        f"`{summary['decision']['classification']}`. No recipe, process window, "
        "downstream relevance, or full-traveler claim is authorized.",
        "",
    ])
    return "\n".join(lines)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    os.replace(temporary, path)


def write_text_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value)
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=runner.DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=runner.DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    args = parser.parse_args()
    manifest = gate0.strict_json_loads(args.manifest.read_text())
    manifest_errors = runner.validate_manifest(manifest)
    if manifest_errors:
        raise ValueError("invalid V3 pattern-skew manifest: " + "; ".join(manifest_errors))
    cases = runner.expand_cases(manifest)
    successes, attempts, failures = runner.audit_existing_rows(args.rows, cases)
    rows = [successes[case["case_id"]] for case in cases if case["case_id"] in successes]
    summary = review(
        manifest,
        rows,
        attempt_count=attempts,
        execution_failures=failures,
    )
    write_json(args.summary, summary)
    write_text_atomic(args.review, markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "reviewed": summary["reviewed_success_count"],
        "expected": summary["expected_case_count"],
        "decision": summary["decision"]["classification"],
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

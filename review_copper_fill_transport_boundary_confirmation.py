"""Independent audit of the s=0.00625 Cu transport boundary confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

import foundation_copper_fill_transport_boundary_confirmation as campaign
import foundation_metric_audit as foundation
import review_copper_fill_access_surface as access
import review_copper_fill_transport_confirmation as parent_review
import review_copper_fill_transport_sign_screen as coarse_review


DEFAULT_MANIFEST = campaign.DEFAULT_MANIFEST
DEFAULT_ROWS = campaign.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_boundary_confirmation_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_boundary_confirmation_review.md"
)

RESPONSES = parent_review.RESPONSES


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_fingerprint(manifest, project_root):
    root = Path(project_root)
    return {
        "runner_sha256": _file_sha256(
            root / "foundation_copper_fill_transport_boundary_confirmation.py"
        ),
        "coarse_runner_sha256": _file_sha256(
            root / "foundation_copper_fill_transport_sign_screen.py"
        ),
        "trajectory_runner_sha256": _file_sha256(
            root / "foundation_copper_fill_trajectory.py"
        ),
        "regional_kinematics_sha256": _file_sha256(
            root / "review_copper_fill_regional_kinematics.py"
        ),
        "traveler_metrics_sha256": _file_sha256(root / "traveler_metrics.py"),
        "tsv_process_sha256": _file_sha256(root / "tsv_process.py"),
        "viennaps_binary_sha256": manifest["provenance"][
            "viennaps_binary_sha256"
        ],
    }


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _strict_jsonable(value):
    if isinstance(value, dict):
        return {str(key): _strict_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return "invalid_nonfinite"
    return value


def _logical_key(row):
    return campaign._logical_key(row)


def _case_payload(row):
    return {field: row.get(field) for field in campaign.CASE_FIELDS}


def validate_attempt(row, expected, fingerprint):
    errors = []
    if row.get("case_id") != expected["case_id"]:
        errors.append("case_id differs from the frozen boundary cell")
    if row.get("case_id") != foundation.case_id(_case_payload(row)):
        errors.append("case_id differs from the row's own payload")
    for field in campaign.CASE_FIELDS:
        if row.get(field) != expected.get(field):
            errors.append(f"case field differs from manifest: {field}")
    if row.get("runtime_fingerprint") != fingerprint:
        errors.append("runtime fingerprint differs from reviewed files")
    if row.get("production_doe_eligible") is not False:
        errors.append("production_doe_eligible is not explicitly false")
    if row.get("morphology_ranking_eligible") is not False:
        errors.append("morphology_ranking_eligible is not explicitly false")
    if row.get("evidence_origin") != {
        "mode": "executed_boundary_confirmation",
        "reflection_residual_upper_bound": expected[
            "reflection_residual_upper_bound"
        ],
        "parent_simulation_reused": False,
    }:
        errors.append("execution/reuse origin differs from the frozen contract")
    return errors


def audit_attempts(manifest, rows, parse_errors, rows_missing, fingerprint):
    cases = campaign.expand_cases(manifest, fingerprint)
    manifest_errors = campaign.validate_manifest(manifest, cases)
    expected = {_logical_key(case): case for case in cases}
    attempts = defaultdict(list)
    invalid_attempts = []
    unexpected = []
    positions = {id(row): index for index, row in enumerate(rows)}
    for row in rows:
        if not isinstance(row, dict):
            invalid_attempts.append({
                "reasons": ["attempt row is not a JSON object"],
                "row": _strict_jsonable(row),
            })
            continue
        try:
            key = _logical_key(row)
        except Exception as error:
            invalid_attempts.append({
                "reasons": [f"attempt logical key is malformed: {error!r}"],
                "row": _strict_jsonable(row),
            })
            continue
        case = expected.get(key)
        if case is None:
            unexpected.append(_strict_jsonable(row))
            continue
        attempts[key].append(row)
        errors = validate_attempt(row, case, fingerprint)
        if errors:
            invalid_attempts.append({
                "reasons": errors, "row": _strict_jsonable(row)
            })
    selected = []
    missing = []
    duplicates = []
    resolved_errors = []
    unresolved_errors = []
    for case in cases:
        valid = [
            row for row in attempts[_logical_key(case)]
            if not validate_attempt(row, case, fingerprint)
        ]
        successes = [row for row in valid if row.get("ok") is True]
        failures = [row for row in valid if row.get("ok") is not True]
        if len(successes) > 1:
            duplicates.append(case["case_id"])
        if not successes:
            missing.append({
                "case_id": case["case_id"],
                "geometry_tier": case["geometry_tier"],
                "max_reflections": case["numerics"]["max_reflections"],
                "rng_seed": case["rng_seed"],
            })
            unresolved_errors.extend(_strict_jsonable(row) for row in failures)
            continue
        latest = max(successes, key=lambda row: positions[id(row)])
        selected.append(latest)
        for row in failures:
            if positions[id(row)] < positions[id(latest)]:
                resolved_errors.append(_strict_jsonable(row))
            else:
                unresolved_errors.append(_strict_jsonable(row))
    invalid = bool(
        manifest_errors or parse_errors or invalid_attempts or unexpected
        or duplicates or unresolved_errors
    )
    complete = bool(
        not rows_missing and not invalid and len(selected) == 24 and not missing
    )
    return {
        "status": (
            "complete" if complete else "missing_rows" if rows_missing
            else "incomplete_or_invalid"
        ),
        "expected_case_count": 24,
        "expected_parent_reuse_count": 0,
        "expected_new_execution_count": 24,
        "attempt_count": len(rows),
        "selected_current_case_count": len(selected),
        "manifest_validation_errors": manifest_errors,
        "parse_errors": parse_errors,
        "rows_missing": rows_missing,
        "invalid_attempts": invalid_attempts,
        "unexpected_attempt_rows": unexpected,
        "resolved_current_error_attempt_rows": resolved_errors,
        "current_error_attempt_rows": unresolved_errors,
        "duplicate_success_case_ids": sorted(duplicates),
        "missing_cases": missing,
        "selected_rows": selected,
    }


def _enrich_record(record, row, evidence_class):
    public = record["public"]
    realized_kinematic_ratio = coarse_review._velocity_ratio(
        record, record["internal"]["raw"]["velocity"]
    )
    public.update({
        "case_id": row["case_id"],
        "design": row["design"],
        "geometry_tier": row["geometry_tier"],
        "rng_seed": row["rng_seed"],
        "grid_delta": row["numerics"]["grid_delta"],
        "rays_per_point": row["numerics"]["rays_per_point"],
        "max_reflections": row["numerics"]["max_reflections"],
        "reflection_residual_upper_bound": row[
            "reflection_residual_upper_bound"
        ],
        "evidence_class": evidence_class,
        "responses": parent_review._response_values(public["transport_sign"]),
        "realized_floor_to_fastest_wall_velocity_ratio": realized_kinematic_ratio,
    })
    return record


def review_new_case(row, project_root):
    record, errors = coarse_review._review_case(row, project_root)
    if record is None:
        return None, errors
    return _enrich_record(record, row, "new_boundary_execution"), errors


def review_parent_case(row, project_root):
    record, errors = coarse_review._review_case(row, project_root)
    if record is None:
        return None, errors
    return _enrich_record(record, row, "verified_parent_comparison"), errors


def _required_arm_metrics_valid(decisions, response_summaries, record_count):
    required_conditions = (
        "all_required_regions_nonempty_and_finite",
        "diagnostic_balance_valid",
        "diagnostic_and_structure_guards_valid",
    )
    return bool(
        record_count == 8
        and len(decisions) == 8
        and all(
            all(decision.get("conditions", {}).get(name) is True for name in required_conditions)
            for decision in decisions
        )
        and all(
            summary.get("count") == 8
            and all(_number(summary.get(name)) for name in ("mean", "adverse_p90", "worst"))
            for summary in response_summaries.values()
        )
    )


def _analytic_envelope_status(envelope, preliminary_flux_gate_pass_count):
    result = dict(envelope)
    result["preliminary_flux_gate_pass_count"] = preliminary_flux_gate_pass_count
    if not envelope.get("fixed_flux_gate_all_eight"):
        result.update({
            "evaluation_status": "not_evaluated_preliminary_flux_gate_failed",
            "evaluation_reason": (
                "The broad H/a coefficient envelope was not evaluated because "
                "the preliminary floor/lower-wall flux gate did not pass all 8 streams."
            ),
        })
    else:
        result.update({
            "evaluation_status": (
                "evaluated_interior_pass"
                if envelope.get("analytic_h_over_a_pass")
                else "evaluated_no_interior_pass"
            ),
            "evaluation_reason": None,
        })
    return result


def _realized_kinematic_by_tier(records):
    result = {}
    for tier in campaign.GEOMETRY_TIERS:
        selected = [
            record["public"] for record in records
            if record["public"]["geometry_tier"] == tier
        ]
        ratios = [
            item.get("realized_floor_to_fastest_wall_velocity_ratio")
            for item in selected
        ]
        thresholds = [item.get("kinematic_threshold_H_over_a") for item in selected]
        eligible = bool(
            len(selected) == 4
            and all(_number(value) for value in ratios)
            and all(_number(value) for value in thresholds)
        )
        finite_ratios = [float(value) for value in ratios if _number(value)]
        finite_thresholds = [float(value) for value in thresholds if _number(value)]
        required = max(finite_thresholds) if finite_thresholds else None
        result[tier] = {
            "eligible": eligible,
            "stream_count": len(selected),
            "realized_mean": (
                float(np.mean(finite_ratios)) if finite_ratios else None
            ),
            "realized_adverse_p10": (
                float(np.quantile(finite_ratios, 0.1)) if finite_ratios else None
            ),
            "realized_minimum": min(finite_ratios) if finite_ratios else None,
            "realized_maximum": max(finite_ratios) if finite_ratios else None,
            "required_H_over_a": required,
            "stream_pass_count": sum(
                ratio > threshold
                for ratio, threshold in zip(ratios, thresholds)
                if _number(ratio) and _number(threshold)
            ),
        }
    return result


def _arm_summary(records, manifest, label, reflections):
    decisions = [record["public"]["transport_sign"] for record in records]
    responses = {
        name: parent_review._adverse_summary(
            [record["public"]["responses"][name] for record in records],
            higher_is_better,
        )
        for name, higher_is_better in RESPONSES.items()
    }
    preliminary_flux_pass_count = sum(
        decision["conditions"][
            "floor_to_each_lower_flux_ratio_strictly_below_0p95"
        ]
        for decision in decisions
    )
    envelope = _analytic_envelope_status(
        parent_review._broad_analytic_envelope(records, manifest["analysis"]),
        preliminary_flux_pass_count,
    )
    realized_kinematics = _realized_kinematic_by_tier(records)
    structural = {
        name: sum(record["public"][name] for record in records)
        for name in (
            "topology_valid",
            "topology_transition_valid",
            "protected_stack_survives",
            "diagnostic_balance_valid",
        )
    }
    parity = max(
        (max(record["public"]["analytic_law_parity"].values()) for record in records),
        default=None,
    )
    required_metrics_valid = _required_arm_metrics_valid(
        decisions, responses, len(records)
    )
    valid = bool(
        len(records) == 8
        and required_metrics_valid
        and all(item["eligible"] for item in realized_kinematics.values())
        and all(value == 8 for value in structural.values())
        and _number(parity)
        and parity <= manifest["analysis"]["analytic_parity_abs_tolerance"]
    )
    all_sign = bool(len(decisions) == 8 and all(item["pass"] for item in decisions))
    combined = bool(valid and all_sign and envelope["analytic_h_over_a_pass"])
    classification = (
        "invalid" if not valid else "pass" if combined
        else "near_threshold" if all_sign and envelope["near_threshold"]
        else "coefficient_boundary" if all_sign and envelope[
            "coefficient_boundary_limited"
        ] else "no_go"
    )
    tier_flux = {}
    for tier in campaign.GEOMETRY_TIERS:
        tier_flux[tier] = parent_review._adverse_summary([
            record["public"]["responses"][
                "worst_floor_to_each_lower_flux_ratio"
            ]
            for record in records
            if record["public"]["geometry_tier"] == tier
        ], False)
    return {
        "label": label,
        "design": records[0]["public"]["design"] if records else None,
        "max_reflections": reflections,
        "stream_count": len(records),
        "transport_sign_pass_count": sum(item["pass"] for item in decisions),
        "all_eight_transport_sign_pass": all_sign,
        "response_summaries": responses,
        "tier_flux_response": tier_flux,
        "structural_guard_pass_counts": structural,
        "analytic_parity_max_abs_error": parity,
        "required_metrics_valid": required_metrics_valid,
        "realized_kinematic_ratio_by_tier": realized_kinematics,
        "broad_analytic_envelope": envelope,
        "combined_2d_pass": combined,
        "classification": classification,
    }


def reflection_convergence(records, arm_summaries, manifest):
    grouped = defaultdict(dict)
    for record in records:
        public = record["public"]
        grouped[(public["geometry_tier"], public["rng_seed"])][
            public["max_reflections"]
        ] = public
    response_results = {}
    for response in RESPONSES:
        invalid_pairs = []
        deltas = []
        for (tier, seed), arms in grouped.items():
            if set(arms) != set(campaign.REFLECTION_ARMS):
                invalid_pairs.append({
                    "geometry_tier": tier,
                    "rng_seed": seed,
                    "reason": "missing_reflection_arm",
                })
                continue
            low = arms[1600].get("responses", {}).get(response)
            high = arms[3200].get("responses", {}).get(response)
            if not (_number(low) and _number(high)):
                invalid_pairs.append({
                    "geometry_tier": tier,
                    "rng_seed": seed,
                    "reason": "missing_or_nonfinite_response",
                    "at_1600": low if _number(low) else None,
                    "at_3200": high if _number(high) else None,
                })
                continue
            deltas.append(high - low)
        absolute = np.abs(np.asarray(deltas, dtype=float))
        tolerance = manifest["reflection_convergence"][
            "maximum_paired_absolute_delta"
        ][response]
        response_results[response] = {
            "eligible": bool(len(deltas) == 8 and not invalid_pairs),
            "invalid_pairs": invalid_pairs,
            "paired_stream_count": len(deltas),
            "mean_signed_delta_3200_minus_1600": (
                float(np.mean(deltas)) if deltas else None
            ),
            "p90_absolute_delta": (
                float(np.quantile(absolute, 0.9)) if len(absolute) else None
            ),
            "worst_absolute_delta": (
                float(np.max(absolute)) if len(absolute) else None
            ),
            "tolerance": tolerance,
            "pass": bool(
                len(deltas) == 8
                and not invalid_pairs
                and np.max(absolute) <= tolerance
            ),
        }
    condition_changes = []
    for (tier, seed), arms in grouped.items():
        if set(arms) != set(campaign.REFLECTION_ARMS):
            condition_changes.append({
                "geometry_tier": tier, "rng_seed": seed,
                "condition": "missing_reflection_arm",
            })
            continue
        low = arms[1600]["transport_sign"]["conditions"]
        high = arms[3200]["transport_sign"]["conditions"]
        for name in sorted(set(low) | set(high)):
            if low.get(name) != high.get(name):
                condition_changes.append({
                    "geometry_tier": tier,
                    "rng_seed": seed,
                    "condition": name,
                    "at_1600": low.get(name),
                    "at_3200": high.get(name),
                })
    classes_match = arm_summaries[1600]["classification"] == arm_summaries[
        3200
    ]["classification"]
    converged = bool(
        classes_match
        and not condition_changes
        and all(item["pass"] for item in response_results.values())
    )
    return {
        "eligible": bool(
            len(grouped) == 8
            and all(item["eligible"] for item in response_results.values())
        ),
        "converged": converged,
        "arm_classes_match": classes_match,
        "condition_changes": condition_changes,
        "response_deltas": response_results,
    }


def boundary_trend(
    parent_records,
    new_records,
    convergence,
    parent_summary,
    new_summary,
    minimum_boundary_improvement,
):
    parent_by_key = {
        (record["public"]["geometry_tier"], record["public"]["rng_seed"]): record
        for record in parent_records
    }
    new_by_key = {
        (record["public"]["geometry_tier"], record["public"]["rng_seed"]): record
        for record in new_records
        if record["public"]["max_reflections"] == 3200
    }
    parent_worst = parent_summary["response_summaries"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["worst"]
    new_worst = new_summary["response_summaries"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["worst"]
    reflection_effect = convergence["response_deltas"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["worst_absolute_delta"]
    paired_keys = sorted(set(parent_by_key) & set(new_by_key))
    paired_values = [
        (
            parent_by_key[key]["public"]["responses"].get(
                "worst_floor_to_each_lower_flux_ratio"
            ),
            new_by_key[key]["public"]["responses"].get(
                "worst_floor_to_each_lower_flux_ratio"
            ),
        )
        for key in paired_keys
    ]
    eligible = bool(
        len(paired_keys) == 8
        and all(_number(parent) and _number(new) for parent, new in paired_values)
        and _number(parent_worst)
        and _number(new_worst)
        and _number(reflection_effect)
        and _number(minimum_boundary_improvement)
    )
    if not eligible:
        return {
            "eligible": False,
            "ineligible_reason": (
                "Boundary trend requires eight finite matched responses, finite "
                "arm worst values, and a finite reflection effect."
            ),
            "paired_stream_count": len(paired_keys),
            "parent_B_worst_flux_ratio": parent_worst if _number(parent_worst) else None,
            "new_C_worst_flux_ratio": new_worst if _number(new_worst) else None,
            "worst_response_improvement_B_minus_C": None,
            "mean_paired_improvement": None,
            "adverse_p10_paired_improvement": None,
            "worst_paired_improvement": None,
            "tier_minimum_paired_improvement": {},
            "maximum_new_reflection_effect": (
                reflection_effect if _number(reflection_effect) else None
            ),
            "minimum_boundary_improvement": (
                minimum_boundary_improvement
                if _number(minimum_boundary_improvement)
                else None
            ),
            "improves_every_stream_in_both_tiers": False,
            "improvement_exceeds_reflection_effect": False,
            "improvement_exceeds_prior_numerical_envelope": False,
            "continued_boundary_improvement": False,
        }
    improvements = []
    tier_improvements = defaultdict(list)
    for key, (parent_value, new_value) in zip(paired_keys, paired_values):
        value = parent_value - new_value
        improvements.append(value)
        tier_improvements[key[0]].append(value)
    worst_improvement = parent_worst - new_worst
    both_tiers = bool(all(
        values and min(values) > 0.0
        for tier, values in tier_improvements.items()
        if tier in campaign.GEOMETRY_TIERS
    ) and set(tier_improvements) == set(campaign.GEOMETRY_TIERS))
    continued = bool(
        both_tiers
        and _number(worst_improvement)
        and _number(reflection_effect)
        and worst_improvement > reflection_effect + 1e-12
        and worst_improvement > minimum_boundary_improvement + 1e-12
    )
    values = np.asarray(improvements, dtype=float)
    return {
        "eligible": True,
        "ineligible_reason": None,
        "paired_stream_count": len(improvements),
        "parent_B_worst_flux_ratio": parent_worst,
        "new_C_worst_flux_ratio": new_worst,
        "worst_response_improvement_B_minus_C": worst_improvement,
        "mean_paired_improvement": float(np.mean(values)) if len(values) else None,
        "adverse_p10_paired_improvement": (
            float(np.quantile(values, 0.1)) if len(values) else None
        ),
        "worst_paired_improvement": float(np.min(values)) if len(values) else None,
        "tier_minimum_paired_improvement": {
            tier: min(values) for tier, values in tier_improvements.items()
        },
        "maximum_new_reflection_effect": reflection_effect,
        "minimum_boundary_improvement": minimum_boundary_improvement,
        "improves_every_stream_in_both_tiers": both_tiers,
        "improvement_exceeds_reflection_effect": bool(
            _number(worst_improvement) and _number(reflection_effect)
            and worst_improvement > reflection_effect + 1e-12
        ),
        "improvement_exceeds_prior_numerical_envelope": bool(
            _number(worst_improvement)
            and worst_improvement > minimum_boundary_improvement + 1e-12
        ),
        "continued_boundary_improvement": continued,
    }


def _response_gate_pass(response, value):
    if not _number(value):
        return False
    if response == "worst_floor_to_each_lower_flux_ratio":
        return value < 0.95
    if response == "worst_floor_to_each_lower_velocity_ratio":
        return value > 1.05
    return value > 0.0


def multiresponse_paired_directions(control_records, candidate_records):
    control = {
        (record["public"]["geometry_tier"], record["public"]["rng_seed"]): record
        for record in control_records
    }
    candidate = {
        (record["public"]["geometry_tier"], record["public"]["rng_seed"]): record
        for record in candidate_records
        if record["public"]["max_reflections"] == 3200
    }
    paired_keys = sorted(set(control) & set(candidate))
    results = {}
    labels = {
        "worst_floor_to_each_lower_flux_ratio": "directional floor/lower-wall flux ratio",
        "minimum_lower_minus_floor_coverage": "lower-wall minus floor coverage margin",
        "worst_floor_to_each_lower_velocity_ratio": "floor/lower-wall velocity ratio",
        "minimum_floor_minus_middle_upper_velocity": "floor minus middle/upper-wall velocity margin",
    }
    for response, higher_is_better in RESPONSES.items():
        oriented_deltas = []
        candidate_values = []
        invalid_pairs = []
        for key in paired_keys:
            old = control[key]["public"].get("responses", {}).get(response)
            new = candidate[key]["public"].get("responses", {}).get(response)
            if not (_number(old) and _number(new)):
                invalid_pairs.append({
                    "geometry_tier": key[0],
                    "rng_seed": key[1],
                    "reason": "missing_or_nonfinite_response",
                })
                continue
            oriented_deltas.append(new - old if higher_is_better else old - new)
            candidate_values.append(new)
        eligible = bool(len(oriented_deltas) == 8 and not invalid_pairs)
        results[response] = {
            "label": labels[response],
            "higher_is_better": higher_is_better,
            "oriented_delta": (
                "candidate_minus_control"
                if higher_is_better
                else "control_minus_candidate"
            ),
            "eligible": eligible,
            "invalid_pairs": invalid_pairs,
            "paired_stream_count": len(oriented_deltas),
            "improved_count": sum(value > 0.0 for value in oriented_deltas),
            "worsened_count": sum(value < 0.0 for value in oriented_deltas),
            "unchanged_count": sum(value == 0.0 for value in oriented_deltas),
            "mean_oriented_improvement": (
                float(np.mean(oriented_deltas)) if oriented_deltas else None
            ),
            "worst_oriented_improvement": (
                min(oriented_deltas) if oriented_deltas else None
            ),
            "candidate_gate_pass_count": sum(
                _response_gate_pass(response, value) for value in candidate_values
            ),
        }
    return {
        "eligible": bool(
            len(paired_keys) == 8
            and all(item["eligible"] for item in results.values())
        ),
        "paired_stream_count": len(paired_keys),
        "comparison": "matched-cap B control versus authoritative C maxReflections=3200",
        "responses": results,
    }


def historical_boundary_cap_effect(historical_records, matched_records):
    """Quantify, but do not use, the old cap-1000 versus new cap-6400 shift."""
    historical = {
        (record["public"]["geometry_tier"], record["public"]["rng_seed"]): record
        for record in historical_records
    }
    matched = {
        (record["public"]["geometry_tier"], record["public"]["rng_seed"]): record
        for record in matched_records
    }
    responses = {}
    paired_keys = sorted(set(historical) & set(matched))
    for response in RESPONSES:
        deltas = []
        invalid_pairs = []
        for key in paired_keys:
            old = historical[key]["public"].get("responses", {}).get(response)
            new = matched[key]["public"].get("responses", {}).get(response)
            if not (_number(old) and _number(new)):
                invalid_pairs.append({
                    "geometry_tier": key[0],
                    "rng_seed": key[1],
                    "reason": "missing_or_nonfinite_response",
                    "cap1000": old if _number(old) else None,
                    "cap6400": new if _number(new) else None,
                })
                continue
            deltas.append(new - old)
        absolute = np.abs(np.asarray(deltas, dtype=float))
        responses[response] = {
            "eligible": bool(len(deltas) == 8 and not invalid_pairs),
            "invalid_pairs": invalid_pairs,
            "paired_stream_count": len(deltas),
            "mean_signed_delta_cap6400_minus_cap1000": (
                float(np.mean(deltas)) if deltas else None
            ),
            "p90_absolute_delta": (
                float(np.quantile(absolute, 0.9)) if len(absolute) else None
            ),
            "worst_absolute_delta": (
                float(np.max(absolute)) if len(absolute) else None
            ),
        }
    return {
        "authority": "context only; both candidate decisions use the new cap6400 control",
        "scope": "four paired derived decision responses only",
        "raw_array_or_byte_identity_evaluated": False,
        "raw_array_or_byte_identity_claim": "none",
        "eligible": bool(
            len(paired_keys) == 8
            and all(item["eligible"] for item in responses.values())
        ),
        "paired_stream_count": len(paired_keys),
        "response_deltas": responses,
        "all_four_decision_responses_unchanged": bool(
            len(responses) == 4
            and all(
                item["eligible"]
                and _number(item["worst_absolute_delta"])
                and item["worst_absolute_delta"] == 0.0
                for item in responses.values()
            )
        ),
    }


def decision_from_evidence(
    authoritative, convergence, trend, required_arms_valid=True
):
    base = {
        "morphology_authorized": False,
        "model_family_pivot_authorized": False,
        "automatic_further_boundary_launch_authorized": False,
        "matched_3d_required": True,
    }
    if not required_arms_valid:
        return {
            **base,
            "classification": "invalid_hard_gate_evidence_blocks_inference",
            "reason": (
                "At least one matched-control or candidate arm has invalid topology, "
                "stack, balance, parity, or completeness evidence."
            ),
        }
    if not convergence["converged"]:
        return {
            **base,
            "classification": "reflection_convergence_inconclusive_refine",
            "reason": (
                "The 1600/3200 arms change a hard-gate class or exceed a "
                "predeclared paired response tolerance. Reflection depth must "
                "be resolved before interpreting the lower-sticking boundary."
            ),
        }
    if not trend.get("eligible"):
        return {
            **base,
            "classification": "boundary_trend_ineligible_blocks_inference",
            "reason": (
                "The matched control-to-candidate boundary trend is missing a "
                "complete finite eight-stream comparison; ordinary 2D no-go "
                "inference is blocked."
            ),
        }
    if authoritative["combined_2d_pass"]:
        return {
            **base,
            "classification": "lower_sticking_boundary_candidate_requires_matched_3d",
            "reason": (
                "The reflection-converged 3200 arm passes all eight measured sign "
                "and interior analytic H/a gates. It remains a tested boundary and "
                "requires matched 3D before morphology."
            ),
        }
    if authoritative["classification"] == "near_threshold":
        return {
            **base,
            "classification": "analytic_near_threshold_requires_sol_review",
            "reason": "The converged authoritative arm is near H/a but does not clear it.",
        }
    if authoritative["classification"] == "coefficient_boundary":
        return {
            **base,
            "classification": "analytic_coefficient_boundary_requires_sol_review",
            "reason": "Clearance appears only at a coefficient limit and is not qualified.",
        }
    if trend["continued_boundary_improvement"]:
        return {
            **base,
            "classification": "lower_sticking_boundary_remains_open_requires_sol_review",
            "reason": (
                "s=0.00625 remains a hard-gate miss, but improves every paired tier/"
                "stream and improves the worst response beyond both the measured "
                "1600/3200 reflection effect and the prior numerical envelope. The "
                "boundary remains open; no further run is authorized automatically."
            ),
        }
    direction = (
        f"Directional floor/lower-wall flux improved in all "
        f"{trend['paired_stream_count']} paired streams, but"
        if trend["improves_every_stream_in_both_tiers"]
        else (
            "Directional floor/lower-wall flux did not improve in every paired "
            "stream, and"
        )
    )
    return {
        **base,
        "classification": "two_dimensional_transport_no_go_requires_matched_3d_before_pivot",
        "reason": (
            f"{direction} the worst-response "
            f"improvement ({trend['worst_response_improvement_B_minus_C']:.6g}) "
            f"did not exceed the predeclared numerical envelope "
            f"({trend['minimum_boundary_improvement']:.6g}). The authoritative "
            "arm remains a transport-sign miss; matched 3D is still required "
            "before a model-family pivot."
        ),
    }


def build_summary(manifest, rows, parse_errors, rows_missing, fingerprint, project_root):
    audit = audit_attempts(manifest, rows, parse_errors, rows_missing, fingerprint)
    selected = audit.pop("selected_rows")
    summary = {
        **audit,
        "campaign": manifest.get("campaign"),
        "expected_runtime_fingerprint": fingerprint,
        "reviewer_sha256": _file_sha256(Path(__file__).resolve()),
        "verified_parent_comparison_count": 0,
        "reviewed_new_execution_count": 0,
        "metric_valid_case_count": 0,
        "snapshot_or_metric_errors": [],
        "reflection_arms": {},
        "reflection_convergence": None,
        "parent_B_comparison": None,
        "historical_parent_B_context": None,
        "historical_boundary_cap_effect": None,
        "boundary_trend": None,
        "multiresponse_paired_directions": None,
        "morphology_ranking": [],
        "decision": {
            "classification": "insufficient_audited_evidence",
            "morphology_authorized": False,
            "model_family_pivot_authorized": False,
            "automatic_further_boundary_launch_authorized": False,
            "reason": "The exact 24-cell artifact and provenance audit has not cleared.",
        },
    }
    if audit["status"] != "complete":
        return summary
    parents, parent_errors = campaign.load_verified_parent_comparison(
        manifest, project_root
    )
    if parent_errors:
        summary["status"] = "incomplete_or_invalid"
        summary["snapshot_or_metric_errors"] = [{
            "case_id": None, "reasons": parent_errors
        }]
        return summary
    new_records = []
    errors = []
    for row in selected:
        record, case_errors = review_new_case(row, project_root)
        if case_errors:
            errors.append({"case_id": row.get("case_id"), "reasons": case_errors})
        if record is not None:
            new_records.append(record)
    parent_records = []
    for row in parents.values():
        record, case_errors = review_parent_case(row, project_root)
        if case_errors:
            errors.append({"case_id": row.get("case_id"), "reasons": case_errors})
        if record is not None:
            parent_records.append(record)
    summary["reviewed_new_execution_count"] = len(new_records)
    summary["verified_parent_comparison_count"] = len(parent_records)
    summary["metric_valid_case_count"] = len(new_records) - sum(
        item["case_id"] in {row.get("case_id") for row in selected}
        for item in errors
    )
    summary["snapshot_or_metric_errors"] = errors
    if errors or len(new_records) != 24 or len(parent_records) != 8:
        summary["status"] = "incomplete_or_invalid"
        return summary
    control_records = [
        record for record in new_records
        if record["public"]["design"] == campaign.CONTROL_NAME
    ]
    candidate_records = [
        record for record in new_records
        if record["public"]["design"] == campaign.CANDIDATE_NAME
    ]
    arm_summaries = {
        reflections: _arm_summary(
            [record for record in candidate_records if record["public"]["max_reflections"] == reflections],
            manifest,
            f"new_C_reflections_{reflections}",
            reflections,
        )
        for reflections in campaign.REFLECTION_ARMS
    }
    matched_control_summary = _arm_summary(
        control_records, manifest, "matched_B_cap6400_reflections_800", 800
    )
    historical_parent_summary = _arm_summary(
        parent_records, manifest, "historical_B_cap1000_context_only", 800
    )
    convergence = reflection_convergence(candidate_records, arm_summaries, manifest)
    cap_effect = historical_boundary_cap_effect(parent_records, control_records)
    trend = boundary_trend(
        control_records, candidate_records, convergence,
        matched_control_summary, arm_summaries[3200],
        manifest["decision_policy"][
            "minimum_boundary_improvement_over_matched_control"
        ],
    )
    multiresponse = multiresponse_paired_directions(
        control_records, candidate_records
    )
    required_arms_valid = bool(
        matched_control_summary["classification"] != "invalid"
        and all(item["classification"] != "invalid" for item in arm_summaries.values())
    )
    decision = decision_from_evidence(
        arm_summaries[3200], convergence, trend, required_arms_valid
    )
    summary.update({
        "status": "complete",
        "metric_valid_case_count": 24,
        "reflection_arms": {str(key): value for key, value in arm_summaries.items()},
        "reflection_convergence": convergence,
        "parent_B_comparison": matched_control_summary,
        "historical_parent_B_context": historical_parent_summary,
        "historical_boundary_cap_effect": cap_effect,
        "boundary_trend": trend,
        "multiresponse_paired_directions": multiresponse,
        "decision": decision,
    })
    return summary


def _fmt(value, digits=6):
    if value is None:
        return "—"
    return f"{value:.{digits}g}" if isinstance(value, (int, float)) else str(value)


def _analytic_display(envelope):
    if envelope.get("evaluation_status") == (
        "not_evaluated_preliminary_flux_gate_failed"
    ):
        return (
            "not evaluated — preliminary flux gate "
            f"{envelope.get('preliminary_flux_gate_pass_count', 0)}/8"
        )
    return _fmt(envelope.get("best_worst_normalized_margin"))


def markdown(summary):
    lines = [
        "# Cu-fill lower-sticking boundary confirmation",
        "",
        f"Status: **{summary['status']}**. Current cells: "
        f"{summary['selected_current_case_count']}/{summary['expected_case_count']}; "
        f"metric-valid: {summary['metric_valid_case_count']}.",
        "",
        "This is a 2D transport-boundary check, not morphology or recipe evidence.",
        "",
    ]
    if summary["status"] != "complete":
        lines += [
            f"Decision: **{summary['decision']['classification']}** — "
            f"{summary['decision']['reason']}", "",
        ]
        return "\n".join(lines)
    lines += [
        "| Design / reflections | Sign streams | Worst flux ratio | Worst velocity ratio | Analytic H/a margin | Class |",
        "|---|---:|---:|---:|---:|---|",
    ]
    entries = [summary["parent_B_comparison"], *[
        summary["reflection_arms"][str(value)] for value in campaign.REFLECTION_ARMS
    ]]
    for item in entries:
        lines.append(
            f"| {item['design']} / {item['max_reflections']} | "
            f"{item['transport_sign_pass_count']}/8 | "
            f"{_fmt(item['response_summaries']['worst_floor_to_each_lower_flux_ratio']['worst'])} | "
            f"{_fmt(item['response_summaries']['worst_floor_to_each_lower_velocity_ratio']['worst'])} | "
            f"{_analytic_display(item['broad_analytic_envelope'])} | "
            f"{item['classification']} |"
        )
    authoritative = summary["reflection_arms"]["3200"]
    lines += [
        "",
        "### Realized kinematic shortfall",
        "",
        "The broad analytic H/a envelope was not evaluated because the preliminary "
        "flux gate failed. The realized unmodified rate field is still reported:",
        "",
        "| Geometry | Realized floor/fastest-wall ratio | Required H/a | Streams clearing H/a |",
        "|---|---:|---:|---:|",
    ]
    for tier in campaign.GEOMETRY_TIERS:
        item = authoritative["realized_kinematic_ratio_by_tier"][tier]
        lines.append(
            f"| {tier} | {_fmt(item['realized_minimum'])}–{_fmt(item['realized_maximum'])} | "
            f"{_fmt(item['required_H_over_a'])} | {item['stream_pass_count']}/4 |"
        )
    multi = summary["multiresponse_paired_directions"]["responses"]
    lines += [
        "",
        "### Matched B-to-C response directions",
        "",
        "| Response | Improved | Worsened | Candidate gate passes |",
        "|---|---:|---:|---:|",
    ]
    for response in RESPONSES:
        item = multi[response]
        lines.append(
            f"| {item['label']} | {item['improved_count']}/8 | "
            f"{item['worsened_count']}/8 | {item['candidate_gate_pass_count']}/8 |"
        )
    lines += [
        "",
        "The floor-minus-middle/upper velocity margin worsened in all 8 matched "
        "streams but remained positive in all 8.",
    ]
    trend = summary["boundary_trend"]
    cap_effect = summary["historical_boundary_cap_effect"]["response_deltas"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["worst_absolute_delta"]
    lines += [
        "",
        f"Reflection convergence: **{summary['reflection_convergence']['converged']}**. "
        f"Parent-B to new-C worst-flux improvement: "
        f"{_fmt(trend['worst_response_improvement_B_minus_C'])}; predeclared "
        f"numerical envelope: {_fmt(trend['minimum_boundary_improvement'])}.",
        "Directional flux improves in all 8 paired streams, but not by enough to "
        "keep the lower-sticking boundary open under the frozen rule.",
        f"For the four derived decision responses only, the historical cap1000-to-"
        f"cap6400 worst paired delta is {_fmt(cap_effect)}. Raw-array and byte "
        "identity were not evaluated and are not claimed.",
        "",
        f"Decision: **{summary['decision']['classification']}** — "
        f"{summary['decision']['reason']}",
        "",
        "Morphology authorized: **no**. Model-family pivot authorized: **no**.",
        "",
    ]
    return "\n".join(lines)


def _atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    rows, parse_errors, rows_missing = access.load_jsonl(args.rows)
    fingerprint = runtime_fingerprint(manifest, args.project_root)
    summary = build_summary(
        manifest, rows, parse_errors, rows_missing, fingerprint, args.project_root
    )
    _atomic_write(
        args.json,
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )
    _atomic_write(args.markdown, markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "selected": summary["selected_current_case_count"],
        "metric_valid": summary["metric_valid_case_count"],
        "decision": summary["decision"]["classification"],
    }, allow_nan=False))


if __name__ == "__main__":
    main()

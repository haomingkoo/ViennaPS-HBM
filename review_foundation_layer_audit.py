"""Review layer qualification without ranking recipes."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/foundation_layer_manifest.json"
)
DEFAULT_ROWS = Path("autoresearch-results/restart_audit/layer_rows.jsonl")
DEFAULT_JSON = Path("autoresearch-results/restart_audit/layer_summary.json")
DEFAULT_MD = Path("autoresearch-results/restart_audit/layer_review.md")

METRICS = {
    "liner_min": ("liner_metrics", "minimum_local_thickness"),
    "liner_floor_field": ("liner_metrics", "floor_to_field_conformality"),
    "liner_lower_wall_field": (
        "liner_metrics",
        "lower_wall_to_field_conformality",
    ),
    "liner_aperture": ("liner_metrics", "minimum_remaining_aperture"),
    "barrier_min": ("barrier_metrics", "minimum_local_thickness"),
    "barrier_floor_field": ("barrier_metrics", "floor_to_field_conformality"),
    "barrier_lower_wall_field": (
        "barrier_metrics",
        "lower_wall_to_field_conformality",
    ),
    "barrier_aperture": ("barrier_metrics", "minimum_remaining_aperture"),
    "seed_min": ("seed_metrics", "minimum_local_thickness"),
    "seed_floor_field": ("seed_metrics", "floor_to_field_conformality"),
    "seed_lower_wall_field": (
        "seed_metrics",
        "lower_wall_to_field_conformality",
    ),
    "seed_aperture": ("seed_metrics", "minimum_remaining_aperture"),
    "stack_min": None,
    "stack_floor_field": None,
}

BOOLEAN_METRICS = {
    "liner_continuous": ("liner_metrics", "layer_continuous"),
    "liner_aperture_open": ("liner_metrics", "aperture_open"),
    "barrier_continuous": ("barrier_metrics", "layer_continuous"),
    "barrier_aperture_open": ("barrier_metrics", "aperture_open"),
    "seed_continuous": ("seed_metrics", "layer_continuous"),
    "seed_aperture_open": ("seed_metrics", "aperture_open"),
}

PAIRS = {
    "grid_primary": ("grid_0.0025", "grid_0.00125"),
    "grid_anchor": ("grid_0.00125", "grid_0.000625"),
}

FINGERPRINT_KEYS = (
    "runner_sha256",
    "metric_sha256",
    "tsv_process_sha256",
    "runtime_binary_sha256",
)


def nested_value(row, path):
    result = row
    for key in path:
        result = result[key]
    return result


def value(row, metric):
    if metric == "stack_min":
        return value(row, "barrier_min") + value(row, "seed_min")
    if metric == "stack_floor_field":
        return min(
            value(row, "barrier_floor_field"),
            value(row, "seed_floor_field"),
        )
    return float(nested_value(row, METRICS[metric]))


def stats(values):
    values = list(values)
    return {
        "n": len(values),
        "mean": statistics.fmean(values) if values else None,
        "sd": statistics.stdev(values) if len(values) > 1 else 0.0 if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def declared_passes(row):
    """Recompute the program/manifest gates without trusting runner labels."""
    liner_spec = row["specs"]["liner"]
    stack_spec = row["specs"]["barrier_seed"]
    liner = bool(
        value(row, "liner_min") >= liner_spec["min_thickness"]
        and value(row, "liner_floor_field") >= liner_spec["min_coverage"]
        and value(row, "liner_lower_wall_field") >= liner_spec["min_coverage"]
        and nested_value(row, BOOLEAN_METRICS["liner_continuous"])
        and nested_value(row, BOOLEAN_METRICS["liner_aperture_open"])
    )
    barrier_seed = bool(
        value(row, "stack_min") >= stack_spec["min_thickness"]
        and value(row, "stack_floor_field") >= stack_spec["min_coverage"]
        and nested_value(row, BOOLEAN_METRICS["barrier_continuous"])
        and nested_value(row, BOOLEAN_METRICS["seed_continuous"])
        and nested_value(row, BOOLEAN_METRICS["barrier_aperture_open"])
        and nested_value(row, BOOLEAN_METRICS["seed_aperture_open"])
    )
    return {"liner": liner, "barrier_seed": barrier_seed}


def gate_state(row):
    return {
        **declared_passes(row),
        **{
            metric: bool(nested_value(row, path))
            for metric, path in BOOLEAN_METRICS.items()
        },
    }


def summarize_groups(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["design"]].append(row)
    result = {}
    for name, group in sorted(groups.items()):
        gates = [declared_passes(row) for row in group]
        result[name] = {
            "rows": len(group),
            "liner_passes": sum(gate["liner"] for gate in gates),
            "barrier_seed_passes": sum(gate["barrier_seed"] for gate in gates),
            "gate_counts": {
                metric: sum(bool(nested_value(row, path)) for row in group)
                for metric, path in BOOLEAN_METRICS.items()
            },
            "metrics": {
                metric: stats(value(row, metric) for row in group)
                for metric in METRICS
            },
        }
    return result


def declared_comparison_pairs(manifest):
    declared = manifest.get("comparison_pairs")
    if declared is None:
        return [
            {
                "name": name,
                "first": pair[0],
                "second": pair[1],
                "minimum_pairs": 4,
            }
            for name, pair in PAIRS.items()
        ]
    return declared


def paired_deltas(rows, comparison_pairs):
    by_key = {(row["design"], row["rng_seed"]): row for row in rows}
    result = {}
    for comparison in comparison_pairs:
        family = comparison["name"]
        low_name = comparison["first"]
        high_name = comparison["second"]
        seeds = sorted(
            seed for design, seed in by_key
            if design == low_name and (high_name, seed) in by_key
        )
        changes = []
        for seed in seeds:
            first_state = gate_state(by_key[(low_name, seed)])
            second_state = gate_state(by_key[(high_name, seed)])
            changes.extend(
                {
                    "rng_seed": seed,
                    "gate": gate,
                    "first": first_state[gate],
                    "second": second_state[gate],
                }
                for gate in first_state
                if first_state[gate] != second_state[gate]
            )
        result[family] = {
            "first": low_name,
            "second": high_name,
            "minimum_pairs": comparison["minimum_pairs"],
            "pairs": len(seeds),
            "second_minus_first": {
                metric: stats(
                    value(by_key[(high_name, seed)], metric)
                    - value(by_key[(low_name, seed)], metric)
                    for seed in seeds
                )
                for metric in METRICS
            },
            "absolute_delta": {
                metric: stats(
                    abs(
                        value(by_key[(high_name, seed)], metric)
                        - value(by_key[(low_name, seed)], metric)
                    )
                    for seed in seeds
                )
                for metric in METRICS
            },
            "pass_changes": {
                gate: dict(Counter(
                    f"{int(declared_passes(by_key[(low_name, seed)])[gate])}_to_"
                    f"{int(declared_passes(by_key[(high_name, seed)])[gate])}"
                    for seed in seeds
                ))
                for gate in ("liner", "barrier_seed")
            },
            "gate_changes": changes,
        }
    return result


def expected_case_keys(manifest):
    return {
        (design["name"], design["seed_start"] + replicate)
        for design in manifest["designs"]
        for replicate in range(design["seed_count"])
    }


def expected_runtime_fingerprint(manifest):
    provenance = manifest.get("provenance", {})
    return {key: provenance.get(key) for key in FINGERPRINT_KEYS}


def case_invariant_mismatches(rows, manifest):
    designs = {design["name"]: design for design in manifest["designs"]}
    mismatches = []
    for row in rows:
        design = designs.get(row.get("design"))
        if design is None:
            continue
        expected = {
            "manifest_version": manifest["manifest_version"],
            "comparison_family": design["comparison_family"],
            "geometry": manifest["geometry"],
            "specs": manifest["specs"],
            "grid_delta": design["grid_delta"],
            "rays_per_point": design.get(
                "rays_per_point", manifest.get("rays_per_point")
            ),
            "threads_per_worker": manifest["threads_per_worker"],
            "liner": {**manifest["baseline"]["liner"], **design.get("liner", {})},
            "barrier": {
                **manifest["baseline"]["barrier"],
                **design.get("barrier", {}),
            },
            "seed": {**manifest["baseline"]["seed"], **design.get("seed", {})},
            "provenance": manifest["provenance"],
        }
        if manifest.get("comparison_pairs") is not None:
            expected["runtime_fingerprint"] = expected_runtime_fingerprint(
                manifest
            )
        reasons = [
            f"{key}: row does not match manifest"
            for key, expected_value in expected.items()
            if row.get(key) != expected_value
        ]
        if reasons:
            mismatches.append({"case_id": row.get("case_id"), "reasons": reasons})
    return mismatches


def invalid_metric_rows(rows):
    invalid = []
    for row in rows:
        if not row.get("ok"):
            continue
        reasons = []
        for metric in METRICS:
            try:
                metric_value = value(row, metric)
            except (KeyError, TypeError, ValueError):
                reasons.append(f"{metric}: missing or non-numeric")
                continue
            if not math.isfinite(metric_value):
                reasons.append(f"{metric}: non-finite")
        for metric, path in BOOLEAN_METRICS.items():
            try:
                metric_value = nested_value(row, path)
            except (KeyError, TypeError):
                reasons.append(f"{metric}: missing")
                continue
            if not isinstance(metric_value, bool):
                reasons.append(f"{metric}: not boolean")
        if not reasons:
            try:
                declared_passes(row)
            except (KeyError, TypeError, ValueError):
                reasons.append("declared gate inputs: missing or invalid")
        if reasons:
            invalid.append({"case_id": row.get("case_id"), "reasons": reasons})
    return invalid


def build_summary(rows, manifest):
    ok = [row for row in rows if row.get("ok")]
    errors = [row for row in rows if not row.get("ok")]
    ids = [row.get("case_id") for row in rows]
    duplicates = [case for case, count in Counter(ids).items() if count > 1]
    keys = [(row.get("design"), row.get("rng_seed")) for row in rows]
    duplicate_keys = [key for key, count in Counter(keys).items() if count > 1]
    expected_keys = expected_case_keys(manifest)
    observed_keys = set(keys)
    invalid_metrics = invalid_metric_rows(rows)
    invariant_mismatches = case_invariant_mismatches(rows, manifest)
    invalid_ids = {item["case_id"] for item in invalid_metrics}
    valid_ok = [row for row in ok if row.get("case_id") not in invalid_ids]
    expected_rows = len(expected_keys)
    structurally_complete = bool(
        len(rows) == expected_rows
        and not errors
        and not duplicates
        and not duplicate_keys
        and None not in ids
        and observed_keys == expected_keys
        and not invalid_metrics
        and not invariant_mismatches
    )
    gates = {
        row["case_id"]: declared_passes(row)
        for row in valid_ok
        if row.get("case_id")
    }
    disagreements = []
    for row in valid_ok:
        for gate in ("liner", "barrier_seed"):
            runner_value = bool(row.get("passes", {}).get(gate))
            declared_value = gates.get(row.get("case_id"), {}).get(gate)
            if declared_value is not None and runner_value != declared_value:
                disagreements.append({
                    "case_id": row.get("case_id"),
                    "gate": gate,
                    "runner": runner_value,
                    "declared": declared_value,
                })

    comparisons = declared_comparison_pairs(manifest)
    paired = paired_deltas(valid_ok, comparisons)
    blockers = []
    if not structurally_complete:
        blockers.append("the expected valid design-by-seed matrix is incomplete")
    if disagreements:
        blockers.append("runner pass labels disagree with independently recomputed gates")

    thresholds = manifest.get("numerical_acceptance_thresholds")
    v2_qualification = manifest.get("comparison_pairs") is not None
    comparison_results = {}
    manifest_errors = []
    if not v2_qualification:
        blockers.append(
            "no quantitative convergence tolerances were declared before the run"
        )
        blockers.append(
            f"ray count was held at {manifest.get('rays_per_point')} per point, "
            "so ray-sampling convergence was not tested"
        )
        anchor_pairs = paired.get("grid_anchor", {}).get("pairs", 0)
        if anchor_pairs < 4:
            seed_word = "seed" if anchor_pairs == 1 else "seeds"
            blockers.append(
                f"the finest-grid comparison has only {anchor_pairs} paired "
                f"{seed_word}; it is a spot check, not a stable stochastic estimate"
            )
    else:
        names = [comparison.get("name") for comparison in comparisons]
        if len(names) != len(set(names)):
            manifest_errors.append("comparison pair names are not unique")
        known_designs = {design["name"] for design in manifest["designs"]}
        for comparison in comparisons:
            name = comparison["name"]
            if comparison["first"] not in known_designs:
                manifest_errors.append(
                    f"{name}: first design is not declared"
                )
            if comparison["second"] not in known_designs:
                manifest_errors.append(
                    f"{name}: second design is not declared"
                )
            if comparison["minimum_pairs"] < 4:
                manifest_errors.append(
                    f"{name}: minimum_pairs must be at least 4"
                )

        threshold_keys = set(thresholds or {})
        expected_threshold_keys = set(METRICS)
        if threshold_keys != expected_threshold_keys:
            missing = sorted(expected_threshold_keys - threshold_keys)
            unexpected = sorted(threshold_keys - expected_threshold_keys)
            if missing:
                manifest_errors.append(
                    "numerical thresholds missing metrics: " + ", ".join(missing)
                )
            if unexpected:
                manifest_errors.append(
                    "numerical thresholds contain unknown metrics: "
                    + ", ".join(unexpected)
                )
        for metric, threshold in (thresholds or {}).items():
            if (
                not isinstance(threshold, (int, float))
                or isinstance(threshold, bool)
                or not math.isfinite(float(threshold))
                or threshold < 0
            ):
                manifest_errors.append(
                    f"{metric}: numerical threshold must be finite and non-negative"
                )

        fingerprint = expected_runtime_fingerprint(manifest)
        if not all(fingerprint.values()):
            manifest_errors.append(
                "all four runtime fingerprint values must be present in provenance"
            )

        for comparison in comparisons:
            name = comparison["name"]
            pair = paired[name]
            threshold_results = {}
            for metric in METRICS:
                observed = pair["absolute_delta"][metric]["max"]
                threshold = (thresholds or {}).get(metric)
                threshold_results[metric] = {
                    "maximum_absolute_delta": observed,
                    "threshold": threshold,
                    "pass": bool(
                        observed is not None
                        and isinstance(threshold, (int, float))
                        and not isinstance(threshold, bool)
                        and math.isfinite(float(threshold))
                        and observed <= threshold
                    ),
                }
            enough_pairs = bool(
                comparison["minimum_pairs"] >= 4
                and pair["pairs"] >= comparison["minimum_pairs"]
            )
            no_gate_changes = not pair["gate_changes"]
            thresholds_pass = bool(
                threshold_keys == expected_threshold_keys
                and all(
                    result["pass"] for result in threshold_results.values()
                )
            )
            pair_pass = bool(
                enough_pairs and no_gate_changes and thresholds_pass
            )
            comparison_results[name] = {
                "pass": pair_pass,
                "pairs": pair["pairs"],
                "minimum_pairs": comparison["minimum_pairs"],
                "enough_pairs": enough_pairs,
                "no_gate_changes": no_gate_changes,
                "gate_changes": pair["gate_changes"],
                "thresholds_pass": thresholds_pass,
                "thresholds": threshold_results,
            }
            if not enough_pairs:
                blockers.append(
                    f"{name} has {pair['pairs']} pairs; "
                    f"{comparison['minimum_pairs']} are required"
                )
            if not no_gate_changes:
                blockers.append(f"{name} changes one or more functional gates")
            failed_metrics = [
                metric
                for metric, result in threshold_results.items()
                if not result["pass"]
            ]
            if failed_metrics:
                blockers.append(
                    f"{name} exceeds or lacks thresholds for: "
                    + ", ".join(failed_metrics)
                )

    blockers.extend(manifest_errors)
    qualification_established = bool(
        v2_qualification
        and structurally_complete
        and not disagreements
        and not manifest_errors
        and comparison_results
        and all(result["pass"] for result in comparison_results.values())
    )

    return {
        "status": "complete" if structurally_complete else "incomplete_or_invalid",
        "qualification_status": (
            "established"
            if qualification_established
            else "not_established"
            if structurally_complete
            else "not_evaluable"
        ),
        "production_doe_authorized": qualification_established,
        "production_doe_authorization_scope": (
            "exploratory_layer_factor_screening_only"
            if qualification_established
            else None
        ),
        "final_recipe_acceptance_authorized": False,
        "qualification_blockers": blockers,
        "qualification_manifest_errors": manifest_errors,
        "qualification_comparisons": comparison_results,
        "runtime_fingerprint": expected_runtime_fingerprint(manifest),
        "expected_rows": expected_rows,
        "row_count": len(rows),
        "ok_count": len(ok),
        "valid_metric_count": len(valid_ok),
        "error_count": len(errors),
        "duplicate_case_ids": sorted(duplicates, key=lambda item: str(item)),
        "duplicate_design_seed_keys": [
            list(key) for key in sorted(duplicate_keys, key=str)
        ],
        "missing_design_seed_keys": [
            list(key) for key in sorted(expected_keys - observed_keys, key=str)
        ],
        "unexpected_design_seed_keys": [
            list(key) for key in sorted(observed_keys - expected_keys, key=str)
        ],
        "invalid_metric_rows": invalid_metrics,
        "case_invariant_mismatches": invariant_mismatches,
        "runner_gate_disagreements": disagreements,
        "errors": [
            {"case_id": row.get("case_id"), "error": row.get("error")}
            for row in errors
        ],
        "groups": summarize_groups(valid_ok),
        "paired_deltas": paired,
    }


def fmt(number):
    return "—" if number is None else f"{number:.6g}"


def delta_cell(pair, metric):
    signed = pair["second_minus_first"][metric]["mean"]
    maximum = pair["absolute_delta"][metric]["max"]
    return f"{fmt(signed)} ({fmt(maximum)})"


def markdown(summary):
    lines = [
        "# Foundation layer qualification review",
        "",
        f"Data status: **{summary['status']}**. Numerical qualification: "
        f"**{summary['qualification_status']}**. Rows: {summary['row_count']}/"
        f"{summary['expected_rows']}; simulations OK: {summary['ok_count']}; "
        f"metrics valid: {summary['valid_metric_count']}; errors: "
        f"{summary['error_count']}.",
        "",
        "This block tests local film measurement convergence only. It does "
        "not screen factors or select a production recipe.",
        "",
        "`production_doe_authorized` refers only to exploratory layer-factor "
        "screening. It never accepts a final recipe.",
        "",
        "## Functional gates at the baseline recipe",
        "",
        "Passes below are independently recomputed from the declared targets. "
        "The liner requires both floor/field and lower-wall/field conformality.",
        "",
        "| Design | n | Liner pass | Barrier/seed pass | Continuous L/B/S | Aperture open L/B/S |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, group in summary["groups"].items():
        gates = group["gate_counts"]
        lines.append(
            f"| {name} | {group['rows']} | {group['liner_passes']} | "
            f"{group['barrier_seed_passes']} | "
            f"{gates['liner_continuous']}/{gates['barrier_continuous']}/"
            f"{gates['seed_continuous']} | "
            f"{gates['liner_aperture_open']}/{gates['barrier_aperture_open']}/"
            f"{gates['seed_aperture_open']} |"
        )
    lines += [
        "",
        "| Design | Liner min | Liner floor/field | Liner lower-wall/field | Stack min | Stack floor/field | Barrier lower-wall/field | Seed lower-wall/field | Seed aperture |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, group in summary["groups"].items():
        metric = group["metrics"]
        lines.append(
            f"| {name} | {fmt(metric['liner_min']['mean'])} | "
            f"{fmt(metric['liner_floor_field']['mean'])} | "
            f"{fmt(metric['liner_lower_wall_field']['mean'])} | "
            f"{fmt(metric['stack_min']['mean'])} | "
            f"{fmt(metric['stack_floor_field']['mean'])} | "
            f"{fmt(metric['barrier_lower_wall_field']['mean'])} | "
            f"{fmt(metric['seed_lower_wall_field']['mean'])} | "
            f"{fmt(metric['seed_aperture']['mean'])} |"
        )
    lines += [
        "",
        "## Numerical comparisons",
        "",
        "Each cell is mean signed change (largest absolute paired change). "
        "The same seed label is used in each pair. Where a comparison changes "
        "the mesh, ray ordering can also change, so the seed label alone is "
        "not proof of an identical pathwise random draw.",
        "",
        "| Family | Pair | n | Δ liner min | Δ liner floor/field | Δ liner lower-wall/field | Δ stack min | Δ stack floor/field | Δ seed aperture |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for family, pair in summary["paired_deltas"].items():
        lines.append(
            f"| {family} | {pair['first']} → {pair['second']} | {pair['pairs']} | "
            f"{delta_cell(pair, 'liner_min')} | "
            f"{delta_cell(pair, 'liner_floor_field')} | "
            f"{delta_cell(pair, 'liner_lower_wall_field')} | "
            f"{delta_cell(pair, 'stack_min')} | "
            f"{delta_cell(pair, 'stack_floor_field')} | "
            f"{delta_cell(pair, 'seed_aperture')} |"
        )
    if summary["qualification_comparisons"]:
        lines += [
            "",
            "| Comparison | Pairs | All thresholds pass | No gate changes | Decision |",
            "|---|---:|---:|---:|---:|",
        ]
        for name, result in summary["qualification_comparisons"].items():
            lines.append(
                f"| {name} | {result['pairs']}/{result['minimum_pairs']} | "
                f"{'yes' if result['thresholds_pass'] else 'no'} | "
                f"{'yes' if result['no_gate_changes'] else 'no'} | "
                f"{'pass' if result['pass'] else 'fail'} |"
            )
    lines += ["", "## Qualification decision", ""]
    if summary["qualification_status"] == "established":
        lines += [
            "Every declared comparison has enough paired seeds, stays within "
            "every maximum-absolute-delta threshold, and preserves all "
            "functional and boolean gates.",
            "",
            "Exploratory layer-factor screening is authorized. Final-recipe "
            "acceptance, production readiness, and physical calibration are not.",
        ]
    else:
        lines.extend(
            f"- {blocker}." for blocker in summary["qualification_blockers"]
        )
    if (
        "grid_anchor" in summary["paired_deltas"]
        and summary["paired_deltas"]["grid_anchor"]["pairs"] < 4
    ):
        lines += [
            "",
            "Two fine-grid pairs can reveal a gross grid failure, but they "
            "cannot estimate the fine-grid stochastic spread or support a "
            "tail-stability claim.",
        ]
    lines += [
        "",
        "Continuity here means one resolved boundary component plus positive "
        "thickness at sampled locations. It cannot rule out a defect smaller "
        "than the grid or between sample locations. The reported stack minimum "
        "is the conservative sum of the separate TaN and Cu-seed minima, not a "
        "co-located cross-section measurement. No product-specific separate "
        "TaN and Cu-seed minimum-thickness limits have been declared, so this "
        "block cannot qualify those layers individually.",
        "",
        "A target failure repeated at every grid describes the current baseline "
        "recipe; it does not by itself prove that the metric is unconverged or "
        "that the target is unreachable by tuning.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    rows = [
        json.loads(line)
        for line in args.rows.read_text().splitlines()
        if line.strip()
    ]
    summary = build_summary(rows, manifest)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    args.markdown.write_text(markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "qualification": summary["qualification_status"],
        "production_doe_authorized": summary["production_doe_authorized"],
        "authorization_scope": summary["production_doe_authorization_scope"],
        "final_recipe_acceptance_authorized": summary[
            "final_recipe_acceptance_authorized"
        ],
        "rows": summary["row_count"],
        "ok": summary["ok_count"],
        "errors": summary["error_count"],
    }))


if __name__ == "__main__":
    main()

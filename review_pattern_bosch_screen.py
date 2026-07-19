"""Independent critical review of the broad pattern/Bosch screen."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics

import numpy as np

import foundation_metric_audit as foundation
import foundation_pattern_bosch_gate0 as gate0
import pattern_bosch_screen_runner as runner
import review_pattern_bosch_gate0 as gate0_review


DEFAULT_MANIFEST = runner.DEFAULT_MANIFEST
DEFAULT_ROWS = runner.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/pattern_bosch_broad_screen_summary.json"
)
DEFAULT_MARKDOWN = Path(
    "autoresearch-results/restart_audit/pattern_bosch_broad_screen_review.md"
)
PRIMITIVE_GATES = (
    "selection_eligible",
    "pattern_width",
    "pattern_height",
    "pattern_opening",
    "etch_depth",
    "etch_cd_profile",
    "etch_bow",
    "etch_mask_resolved",
)


def review_fingerprint(project_root=runner.ROOT):
    root = Path(project_root)
    return {
        "reviewer_sha256": foundation.file_sha256(root / Path(__file__).name),
        "runner_sha256": foundation.file_sha256(root / "pattern_bosch_screen_runner.py"),
        "traveler_metrics_sha256": foundation.file_sha256(root / "traveler_metrics.py"),
        "tsv_process_sha256": foundation.file_sha256(root / "tsv_process.py"),
    }


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def continuous_miss_terms(initial, measured, case):
    target = case["target"]
    grid = case["numerics"]["grid_delta"]
    etch = measured.get("etch") or {}

    def excess(value, limit, scale):
        return max(0.0, float(value) - limit) / scale if finite(value) else 0.0

    pattern_width_error = (
        abs(initial["opening_cd_bottom"] - target["opening_cd"])
        if finite(initial.get("opening_cd_bottom")) else None
    )
    pattern_height_error = (
        abs(initial["mask_height"] - target["mask_height"])
        if finite(initial.get("mask_height")) else None
    )
    depth_error = (
        abs(etch["depth"] - target["etch_depth"])
        if finite(etch.get("depth")) else None
    )
    required_mask = target["resolved_mask_cells_strict"] * grid
    mask_remaining = measured.get("mask_remaining_height")
    return {
        "pattern_width_beyond_tolerance": excess(
            pattern_width_error, target["max_width_error"], target["max_width_error"]
        ),
        "pattern_height_beyond_grid_tolerance": excess(
            pattern_height_error, grid, grid
        ),
        "depth_beyond_tolerance": excess(
            depth_error, target["depth_tolerance"], target["depth_tolerance"]
        ),
        "cd_error_beyond_tolerance": excess(
            etch.get("max_cd_error"),
            target["max_width_error"],
            target["max_width_error"],
        ),
        "bow_beyond_tolerance": excess(
            etch.get("max_bow"),
            target["max_wall_bulge"],
            target["max_wall_bulge"],
        ),
        "resolved_mask_height_shortfall": (
            max(0.0, required_mask - mask_remaining) / required_mask
            if finite(mask_remaining) else 0.0
        ),
    }


def miss_score(initial, measured, gates, case, review_errors=()):
    review = case["review"]
    primitive = {
        "selection_eligible": gates.get("selection_eligible") is True,
        **{name: gates.get(name) is True for name in PRIMITIVE_GATES[1:]},
    }
    failures = [name for name, passed in primitive.items() if not passed]
    invalid = bool(review_errors)
    terms = continuous_miss_terms(initial, measured, case)
    score = (
        (review["invalid_metric_penalty"] if invalid else 0.0)
        + len(failures) * review["primitive_hard_gate_penalty"]
        + sum(terms.values())
    )
    return {
        "invalid": invalid,
        "primitive_gates": primitive,
        "failed_primitive_gates": failures,
        "primitive_gate_failure_count": len(failures),
        "continuous_miss_terms": terms,
        "score": float(score),
    }


def _checkpoint_meshes(path):
    with np.load(path, allow_pickle=False) as checkpoint:
        return {
            "initial_mask": {
                "nodes": np.asarray(checkpoint["initial_mask_nodes"], dtype=float),
                "lines": np.asarray(checkpoint["initial_mask_lines"], dtype=int),
            },
            "silicon": {
                "nodes": np.asarray(checkpoint["silicon_nodes"], dtype=float),
                "lines": np.asarray(checkpoint["silicon_lines"], dtype=int),
            },
            "mask": (
                {
                    "nodes": np.asarray(checkpoint["mask_nodes"], dtype=float),
                    "lines": np.asarray(checkpoint["mask_lines"], dtype=int),
                }
                if len(checkpoint["mask_nodes"]) else None
            ),
        }


def review_case(row, case, manifest):
    errors = runner.validate_checkpoint(
        row.get("checkpoint_path", ""),
        case,
        row.get("checkpoint_sha256"),
        expected_selected_cycle=row.get("selected_cycle"),
        expected_selection_eligible=row.get("selection_eligible"),
    )
    recomputed_initial = None
    recomputed_selected = None
    recomputed_gates = None
    if not errors:
        try:
            meshes = _checkpoint_meshes(row["checkpoint_path"])
            initial_invalid = []
            selected_invalid = []
            recomputed_initial = runner.sanitize(
                gate0.measure_pattern(meshes["initial_mask"], case),
                "recomputed_initial",
                initial_invalid,
            )
            recomputed_selected = runner.sanitize(
                gate0.measure_selected_cycle(
                    meshes["silicon"], meshes["mask"], case
                ),
                "recomputed_selected",
                selected_invalid,
            )
            errors.extend(initial_invalid)
            errors.extend(selected_invalid)
        except Exception as error:
            errors.append(f"independent checkpoint measurement failed: {error}")
    tolerance = manifest["design"]["review"]["row_recompute_abs_tolerance"]
    if recomputed_initial is not None and recomputed_selected is not None:
        errors.extend(gate0_review._compare_values(
            recomputed_initial, row.get("initial_pattern"), tolerance,
            "initial_pattern",
        ))
        errors.extend(gate0_review._compare_values(
            recomputed_selected, row.get("selected_cycle_metrics"), tolerance,
            "selected_cycle_metrics",
        ))
        recomputed_gates = runner.classify_gates(
            recomputed_initial, recomputed_selected, case
        )
        recomputed_gates["selection_eligible"] = (
            row.get("selection_eligible") is True
        )
        expected_hard_pass = runner.combined_hard_gate_pass(
            row.get("selection_eligible"), recomputed_gates
        )
        if row.get("gates") != {
            key: value for key, value in recomputed_gates.items()
            if key != "selection_eligible"
        }:
            errors.append("reported gate vector differs from independent review")
        if row.get("hard_gate_pass") is not expected_hard_pass:
            errors.append("reported hard-gate pass differs from independent review")

    history = row.get("cycle_history")
    if not isinstance(history, list) or not history:
        errors.append("cycle history is missing or empty")
        selected_from_history = None
    else:
        cycles = [record.get("cycle") for record in history]
        if cycles != list(range(len(cycles))):
            errors.append("cycle history is not contiguous from cycle zero")
        if cycles and cycles[-1] > case["trajectory"]["maximum_cycles"]:
            errors.append("cycle history exceeds the frozen maximum")
        last_depth = history[-1].get("depth")
        expected_early_stop = bool(
            finite(last_depth)
            and last_depth >= case["trajectory"]["early_stop_depth"]
        )
        if row.get("early_stopped") is not expected_early_stop:
            errors.append("reported early-stop state differs from cycle history")
        if (
            not expected_early_stop
            and cycles
            and cycles[-1] != case["trajectory"]["maximum_cycles"]
        ):
            errors.append("trajectory ended before its maximum without a depth stop")
        selected_from_history, eligible, rank = runner.select_depth_matched(
            history, case
        )
        if selected_from_history is None:
            errors.append("cycle history has no selectable metric record")
        else:
            if selected_from_history["cycle"] != row.get("selected_cycle"):
                errors.append("reported cycle is not the depth-matched selection")
            if eligible is not row.get("selection_eligible"):
                errors.append("reported selection eligibility differs")
            expected_rank = list(rank) if rank is not None else None
            if row.get("selection_rank") != expected_rank:
                errors.append("reported selection rank differs")

    if recomputed_initial is None:
        recomputed_initial = row.get("initial_pattern") or {}
    if recomputed_selected is None:
        recomputed_selected = row.get("selected_cycle_metrics") or {}
    if recomputed_gates is None:
        recomputed_gates = {name: False for name in PRIMITIVE_GATES[1:]}
        recomputed_gates["selection_eligible"] = False
    score = miss_score(
        recomputed_initial,
        recomputed_selected,
        recomputed_gates,
        {**case, "review": manifest["design"]["review"]},
        errors,
    )
    return {
        "case_id": case["case_id"],
        "recipe_id": case["recipe_id"],
        "rng_seed": case["rng_seed"],
        "valid": not errors,
        "errors": errors,
        "selection_eligible": row.get("selection_eligible") is True,
        "selected_cycle": row.get("selected_cycle"),
        "initial_pattern": recomputed_initial,
        "selected_cycle_metrics": recomputed_selected,
        "gates": recomputed_gates,
        "hard_gate_pass": bool(not errors and runner.combined_hard_gate_pass(
            row.get("selection_eligible"), recomputed_gates
        )),
        "miss": score,
        "normalized_coordinates": case["normalized_coordinates"],
        "recipe": case["recipe"],
        "design_class": case["design_class"],
        "anchor_reasons": case["anchor_reasons"],
    }


def quantile(values, probability, method):
    return float(np.quantile(np.asarray(values, dtype=float), probability, method=method))


def response_summary(values, *, method="linear", higher_is_worse=True):
    values = [float(value) for value in values if finite(value)]
    if not values:
        return {
            "n": 0,
            "higher_is_worse": higher_is_worse,
            "mean": None,
            "adverse_p90": None,
            "worst": None,
            "min": None,
            "max": None,
        }
    return {
        "n": len(values),
        "higher_is_worse": higher_is_worse,
        "mean": statistics.fmean(values),
        "adverse_p90": quantile(
            values, 0.90 if higher_is_worse else 0.10, method
        ),
        "worst": max(values) if higher_is_worse else min(values),
        "min": min(values),
        "max": max(values),
    }


def descriptive_summary(values):
    values = [float(value) for value in values if finite(value)]
    return {
        "n": len(values),
        "mean": statistics.fmean(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def aggregate_recipes(reviewed, manifest):
    groups = defaultdict(list)
    for row in reviewed:
        groups[row["recipe_id"]].append(row)
    method = manifest["design"]["review"]["p90_quantile_method"]
    boundary_fraction = manifest["design"]["review"]["boundary_warning_fraction"]
    aggregates = []
    for recipe_id, rows in groups.items():
        rows = sorted(rows, key=lambda row: row["rng_seed"])
        scores = [row["miss"]["score"] for row in rows]
        invalid_count = sum(not row["valid"] for row in rows)
        hard_pass_count = sum(row["hard_gate_pass"] for row in rows)
        failure_counts = [
            row["miss"]["primitive_gate_failure_count"] for row in rows
        ]
        boundary = []
        coordinates = rows[0]["normalized_coordinates"]
        for name, coordinate in coordinates.items():
            if coordinate <= boundary_fraction:
                boundary.append({"factor": name, "edge": "low", "value": rows[0]["recipe"][name]})
            if coordinate >= 1.0 - boundary_fraction:
                boundary.append({"factor": name, "edge": "high", "value": rows[0]["recipe"][name]})
        selected = [row["selected_cycle_metrics"].get("etch", {}) for row in rows]
        mask = [row["selected_cycle_metrics"].get("mask_remaining_height") for row in rows]
        rank = (
            invalid_count,
            4 - hard_pass_count,
            max(failure_counts) if failure_counts else len(PRIMITIVE_GATES),
            max(scores) if scores else float("inf"),
            quantile(scores, 0.90, method) if scores else float("inf"),
            statistics.fmean(scores) if scores else float("inf"),
        )
        aggregates.append({
            "recipe_id": recipe_id,
            "recipe": rows[0]["recipe"],
            "normalized_coordinates": coordinates,
            "design_class": rows[0]["design_class"],
            "anchor_reasons": rows[0]["anchor_reasons"],
            "replicate_count": len(rows),
            "invalid_replicate_count": invalid_count,
            "hard_pass_count": hard_pass_count,
            "all_four_hard_pass": bool(invalid_count == 0 and hard_pass_count == 4),
            "rank": list(rank),
            "score": response_summary(scores, method=method),
            "selected_cycle": descriptive_summary(
                [row["selected_cycle"] for row in rows]
            ),
            "depth": descriptive_summary([item.get("depth") for item in selected]),
            "depth_absolute_error": response_summary([
                abs(item["depth"] - manifest["design"]["target"]["etch_depth"])
                if finite(item.get("depth")) else None
                for item in selected
            ], method=method),
            "max_cd_error": response_summary(
                [item.get("max_cd_error") for item in selected], method=method
            ),
            "max_bow": response_summary(
                [item.get("max_bow") for item in selected], method=method
            ),
            "scallop_rms": response_summary(
                [item.get("scallop_rms") for item in selected], method=method
            ),
            "mask_remaining_height": response_summary(
                mask, method=method, higher_is_worse=False
            ),
            "boundary_warnings": boundary,
        })
    return sorted(aggregates, key=lambda row: tuple(row["rank"]))


def decision_from_review(reviewed, aggregates, expected_count):
    complete = bool(
        len(reviewed) == expected_count
        and all(row["valid"] for row in reviewed)
        and len(aggregates) == 160
        and all(row["replicate_count"] == 4 for row in aggregates)
    )
    feasible = [row for row in aggregates if row["all_four_hard_pass"]]
    misses = [row for row in aggregates if not row["all_four_hard_pass"]]
    return {
        "classification": (
            "complete_screen_with_feasible_candidates"
            if complete and feasible
            else "complete_screen_without_four_seed_feasibility"
            if complete
            else "incomplete_or_invalid_screen"
        ),
        "complete_valid_matrix": complete,
        "four_seed_feasible_recipe_count": len(feasible),
        "best_feasible": feasible[0] if feasible else None,
        "best_observed_miss": misses[0] if misses else None,
        "targeted_pattern_bosch_refinement_authorized": complete,
        "boundary_expansion_required": bool(
            complete
            and (feasible[0] if feasible else misses[0] if misses else {}).get(
                "boundary_warnings"
            )
        ),
        "recipe_authorized": False,
        "process_window_authorized": False,
        "downstream_recipe_authorized": False,
        "full_traveler_authorized": False,
    }


def success_rows(path):
    rows = []
    for line in Path(path).read_text().splitlines() if Path(path).is_file() else []:
        if not line.strip():
            continue
        row = gate0.strict_json_loads(line)
        if row.get("ok") is True:
            rows.append(row)
    return rows


def build_summary(manifest, rows_path, *, check_runtime=True, check_prerequisites=True):
    manifest_errors = runner.validate_manifest(
        manifest,
        check_runtime=check_runtime,
        check_prerequisites=check_prerequisites,
    )
    if manifest_errors:
        raise ValueError("invalid broad-screen manifest: " + "; ".join(manifest_errors))
    cases = runner.expand_cases(manifest)
    completed = runner.audit_existing_rows(rows_path, cases)
    rows = {row["case_id"]: row for row in success_rows(rows_path)}
    reviewed = [
        review_case(rows[case["case_id"]], case, manifest)
        for case in cases if case["case_id"] in completed
    ]
    aggregates = aggregate_recipes(reviewed, manifest)
    decision = decision_from_review(reviewed, aggregates, len(cases))
    return {
        "campaign": manifest["campaign"],
        "labels": manifest["labels"],
        "review_fingerprint": review_fingerprint(),
        "expected_case_count": len(cases),
        "reviewed_case_count": len(reviewed),
        "valid_case_count": sum(row["valid"] for row in reviewed),
        "missing_case_ids": [case["case_id"] for case in cases if case["case_id"] not in completed],
        "invalid_cases": [
            {"case_id": row["case_id"], "errors": row["errors"]}
            for row in reviewed if not row["valid"]
        ],
        "recipe_aggregates": aggregates,
        "decision": decision,
        "authority": manifest["authority"],
    }


def markdown(summary):
    decision = summary["decision"]
    lines = [
        "# Broad pattern/Bosch screen critical review",
        "",
        f"Classification: `{decision['classification']}`. Independently valid "
        f"rows: {summary['valid_case_count']}/{summary['expected_case_count']}.",
        "",
        "A recipe is four-seed feasible only when every selected checkpoint is "
        "valid and passes pattern, depth, CD, bow, and resolved-mask gates.",
        "",
        f"Four-seed feasible recipes: {decision['four_seed_feasible_recipe_count']}.",
    ]
    for label, row in (
        ("Best feasible", decision["best_feasible"]),
        ("Best observed miss", decision["best_observed_miss"]),
    ):
        if row:
            lines += [
                "",
                f"## {label}",
                "",
                f"Recipe `{row['recipe_id']}`; hard passes {row['hard_pass_count']}/4; "
                f"worst score {row['score']['worst']:.6g}; boundary warnings: "
                f"{row['boundary_warnings'] or 'none'}.",
            ]
    lines += [
        "",
        "This screen can authorize targeted interaction/refinement work only. "
        "It cannot authorize a recipe, process window, downstream recipe, or "
        "full traveler.",
        "",
    ]
    return "\n".join(lines)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    manifest = gate0.strict_json_loads(args.manifest.read_text())
    summary = build_summary(manifest, args.rows)
    write_json(args.json, summary)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown(summary) + "\n")
    print(json.dumps({
        "classification": summary["decision"]["classification"],
        "valid": summary["valid_case_count"],
        "feasible_recipes": summary["decision"]["four_seed_feasible_recipe_count"],
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

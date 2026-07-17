"""Independent critical review of the frozen pattern/Bosch Gate-0 campaign."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

import foundation_pattern_bosch_gate0 as campaign
import traveler_metrics as tm


DEFAULT_MANIFEST = campaign.DEFAULT_MANIFEST
DEFAULT_ROWS = campaign.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/pattern_bosch_gate0_summary.json"
)
DEFAULT_MARKDOWN = Path(
    "autoresearch-results/restart_audit/pattern_bosch_gate0_review.md"
)
PAIRED_METRICS = tuple(campaign.EXPECTED_TOLERANCES)


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(
        float(value)
    )


def _compare_values(expected, reported, tolerance, path="metrics") -> list[str]:
    errors = []
    if isinstance(expected, dict):
        if not isinstance(reported, dict):
            return [f"{path} is not a mapping"]
        if set(expected) != set(reported):
            errors.append(f"{path} keys differ")
        for key in sorted(set(expected) & set(reported)):
            errors.extend(_compare_values(
                expected[key], reported[key], tolerance, f"{path}.{key}"
            ))
        return errors
    if isinstance(expected, (list, tuple)):
        if not isinstance(reported, (list, tuple)) or len(expected) != len(reported):
            return [f"{path} sequence shape differs"]
        for index, (first, second) in enumerate(zip(expected, reported)):
            errors.extend(_compare_values(
                first, second, tolerance, f"{path}[{index}]"
            ))
        return errors
    if _finite_number(expected):
        if not _finite_number(reported) or not math.isclose(
            float(expected), float(reported), rel_tol=0.0, abs_tol=tolerance
        ):
            errors.append(f"{path} differs")
        return errors
    if expected != reported:
        errors.append(f"{path} differs")
    return errors


def _pattern_metrics(nodes, lines, case) -> dict:
    return tm.pattern_metrics_2d(
        nodes,
        lines,
        surface_y=0.0,
        target_cd=case["target"]["opening_cd"],
        target_mask_height=case["target"]["mask_height"],
        max_radius=case["target"]["opening_cd"],
    )


def recompute_checkpoint(row, case, output) -> tuple[dict | None, list[str]]:
    errors = campaign.validate_checkpoint(row["checkpoint_path"], case)
    expected_path = campaign.checkpoint_path(
        output, case["case_id"], case["selected_cycle"]
    )
    if Path(row["checkpoint_path"]).resolve() != expected_path.resolve():
        errors.append("review checkpoint path differs")
    if row.get("checkpoint_sha256") != campaign.file_sha256(expected_path):
        errors.append("review checkpoint hash differs")
    if errors:
        return None, errors
    try:
        with np.load(expected_path, allow_pickle=False) as snapshot:
            initial_nodes = np.asarray(snapshot["initial_mask_nodes"], dtype=float)
            initial_lines = np.asarray(snapshot["initial_mask_lines"], dtype=int)
            silicon_nodes = np.asarray(snapshot["silicon_nodes"], dtype=float)
            silicon_lines = np.asarray(snapshot["silicon_lines"], dtype=int)
            mask_nodes = np.asarray(snapshot["mask_nodes"], dtype=float)
            mask_lines = np.asarray(snapshot["mask_lines"], dtype=int)
    except Exception as error:
        return None, [f"review cannot load checkpoint arrays: {error}"]

    try:
        initial_pattern = _pattern_metrics(
            initial_nodes, initial_lines, case
        )
        floor_y = float(np.min(silicon_nodes[:, 1]))
        etch = tm.etch_profile_metrics_2d(
            silicon_nodes,
            silicon_lines,
            surface_y=0.0,
            floor_y=floor_y,
            target_cd=case["target"]["opening_cd"],
            max_radius=case["target"]["opening_cd"],
        )
        mask_remaining = float(np.max(mask_nodes[:, 1])) if len(mask_nodes) else 0.0
        post_mask = None
        if len(mask_nodes):
            try:
                post_mask = _pattern_metrics(mask_nodes, mask_lines, case)
            except ValueError:
                post_mask = None
    except Exception as error:
        return None, [f"independent metric recomputation failed: {error}"]
    return {
        "initial_pattern": campaign.foundation.jsonable(initial_pattern),
        "selected_cycle_metrics": campaign.foundation.jsonable({
            "etch": etch,
            "mask_remaining_height": mask_remaining,
            "post_etch_mask": post_mask,
        }),
    }, []


def classify_gates(recomputed, case) -> dict[str, bool]:
    pattern = recomputed["initial_pattern"]
    selected = recomputed["selected_cycle_metrics"]
    etch = selected["etch"]
    target = case["target"]
    grid_delta = case["numerics"]["grid_delta"]
    post_mask = selected.get("post_etch_mask") or {}
    return {
        "pattern_width": bool(
            abs(pattern["opening_cd_bottom"] - target["opening_cd"])
            <= target["max_width_error"]
        ),
        "pattern_height": bool(
            abs(pattern["mask_height"] - target["mask_height"]) <= grid_delta
        ),
        "pattern_opening": pattern.get("opening_valid") is True,
        "etch_depth": bool(
            abs(etch["depth"] - target["etch_depth"])
            <= target["depth_tolerance"]
        ),
        "etch_cd_profile": bool(
            etch["max_cd_error"] <= target["max_width_error"]
        ),
        "etch_bow": bool(etch["max_bow"] <= target["max_wall_bulge"]),
        "etch_mask_resolved": bool(
            selected["mask_remaining_height"]
            > target["resolved_mask_cells_strict"] * grid_delta
            and post_mask.get("opening_valid") is True
        ),
    }


def review_case(row, case, output, manifest) -> dict:
    recomputed, errors = recompute_checkpoint(row, case, output)
    if recomputed is None:
        return {
            "case_id": case["case_id"],
            "arm": case["arm"],
            "rng_seed": case["rng_seed"],
            "valid": False,
            "errors": errors,
        }
    tolerance = float(manifest["review"]["row_recompute_abs_tolerance"])
    errors.extend(_compare_values(
        recomputed["initial_pattern"],
        row.get("initial_pattern"),
        tolerance,
        "initial_pattern",
    ))
    errors.extend(_compare_values(
        recomputed["selected_cycle_metrics"],
        row.get("selected_cycle_metrics"),
        tolerance,
        "selected_cycle_metrics",
    ))
    gates = classify_gates(recomputed, case)
    etch = recomputed["selected_cycle_metrics"]["etch"]
    metrics = {
        "depth": float(etch["depth"]),
        "cd_top": float(etch["cd_top"]),
        "cd_middle": float(etch["cd_middle"]),
        "cd_bottom": float(etch["cd_bottom"]),
        "max_cd_error": float(etch["max_cd_error"]),
        "max_bow": float(etch["max_bow"]),
        "scallop_rms": float(etch["scallop_rms"]),
        "mask_remaining_height": float(
            recomputed["selected_cycle_metrics"]["mask_remaining_height"]
        ),
    }
    if not all(_finite_number(value) for value in metrics.values()):
        errors.append("recomputed paired metric is nonfinite")
    return {
        "case_id": case["case_id"],
        "arm": case["arm"],
        "role": case["role"],
        "rng_seed": case["rng_seed"],
        "grid_delta": case["numerics"]["grid_delta"],
        "mask_ion_rate": case["recipe"]["mask_ion_rate"],
        "valid": not errors,
        "errors": errors,
        "gates": gates,
        "pattern_pass": all(gates[name] for name in (
            "pattern_width", "pattern_height", "pattern_opening"
        )),
        "etch_pass": all(gates[name] for name in (
            "etch_depth", "etch_cd_profile", "etch_bow", "etch_mask_resolved"
        )),
        "metrics": metrics,
        "recomputed": recomputed,
    }


def paired_comparison(reviewed, manifest, comparison_name) -> dict:
    contract = manifest["review"][comparison_name]
    reference_arm = contract["reference_arm"]
    candidate_arm = contract["candidate_arm"]
    by_key = {(row["arm"], row["rng_seed"]): row for row in reviewed}
    pairs = []
    errors = []
    for seed in campaign.EXPECTED_SEEDS:
        reference = by_key.get((reference_arm, seed))
        candidate = by_key.get((candidate_arm, seed))
        if reference is None or candidate is None:
            errors.append(f"missing paired seed {seed}")
            continue
        if not reference.get("valid") or not candidate.get("valid"):
            errors.append(f"invalid paired seed {seed}")
            continue
        deltas = {
            metric: candidate["metrics"][metric] - reference["metrics"][metric]
            for metric in PAIRED_METRICS
        }
        pairs.append({
            "rng_seed": seed,
            "reference_case_id": reference["case_id"],
            "candidate_case_id": candidate["case_id"],
            "deltas": deltas,
            "gate_flip": reference["gates"] != candidate["gates"],
        })
    metric_results = {}
    for metric, tolerance in manifest["review"][
        "paired_max_absolute_deltas"
    ].items():
        values = [abs(pair["deltas"][metric]) for pair in pairs]
        metric_results[metric] = {
            "tolerance": tolerance,
            "paired_count": len(values),
            "maximum_absolute_delta": max(values) if values else None,
            "pass": bool(
                len(values) == 4 and all(value <= tolerance for value in values)
            ),
        }
    eligible = len(pairs) == 4 and not errors
    no_gate_flips = bool(eligible and not any(pair["gate_flip"] for pair in pairs))
    return {
        "pairing": (
            "shared base-seed labels; not guaranteed pointwise common random "
            "numbers across arms or geometry representations"
        ),
        "reference_arm": reference_arm,
        "candidate_arm": candidate_arm,
        "eligible": eligible,
        "errors": errors,
        "pairs": pairs,
        "metric_results": metric_results,
        "no_gate_flips": no_gate_flips,
        "pass": bool(
            eligible
            and no_gate_flips
            and all(result["pass"] for result in metric_results.values())
        ),
    }


def erosion_response(reviewed, manifest) -> dict:
    arm_order = manifest["review"]["erosion_arm_order"]
    by_key = {(row["arm"], row["rng_seed"]): row for row in reviewed}
    tolerance = float(manifest["review"]["erosion_monotonic_abs_tolerance"])
    seed_rows = []
    errors = []
    for seed in campaign.EXPECTED_SEEDS:
        rows = [by_key.get((arm, seed)) for arm in arm_order]
        if any(row is None or not row.get("valid") for row in rows):
            errors.append(f"erosion sequence missing or invalid for seed {seed}")
            continue
        heights = [row["metrics"]["mask_remaining_height"] for row in rows]
        monotonic = all(
            after <= before + tolerance
            for before, after in zip(heights, heights[1:])
        )
        seed_rows.append({
            "rng_seed": seed,
            "remaining_heights": dict(zip(arm_order, heights)),
            "monotonic_nonincreasing": monotonic,
        })
    arm_classes = {}
    for arm in arm_order:
        rows = [by_key.get((arm, seed)) for seed in campaign.EXPECTED_SEEDS]
        states = [
            row["gates"]["etch_mask_resolved"]
            for row in rows if row is not None and row.get("valid")
        ]
        classification = (
            "all_seed_surviving"
            if len(states) == 4 and all(states)
            else "all_seed_failed"
            if len(states) == 4 and not any(states)
            else "mixed_or_incomplete"
        )
        arm_classes[arm] = {
            "classification": classification,
            "surviving_seed_count": sum(states),
            "valid_seed_count": len(states),
        }
    surviving = [
        arm for arm, result in arm_classes.items()
        if result["classification"] == "all_seed_surviving"
    ]
    failed = [
        arm for arm, result in arm_classes.items()
        if result["classification"] == "all_seed_failed"
    ]
    monotonic = bool(
        len(seed_rows) == 4
        and all(row["monotonic_nonincreasing"] for row in seed_rows)
    )
    return {
        "eligible": len(seed_rows) == 4 and not errors,
        "errors": errors,
        "seed_responses": seed_rows,
        "arm_classes": arm_classes,
        "all_seeds_monotonic": monotonic,
        "all_seed_surviving_arms": surviving,
        "all_seed_failed_arms": failed,
        "pass": bool(monotonic and surviving and failed),
    }


def decision_from_evidence(reviewed, comparisons, erosion, missing_case_ids) -> dict:
    reference = [
        row for row in reviewed if row.get("arm") == "full_reference_fine"
    ]
    complete = bool(
        len(reviewed) == 24
        and not missing_case_ids
        and all(row.get("valid") for row in reviewed)
    )
    reference_pass = bool(
        len(reference) == 4
        and all(row.get("pattern_pass") and row.get("etch_pass") for row in reference)
    )
    blockers = []
    if not complete:
        blockers.append("complete_hash_verified_24_case_matrix_required")
    if not reference_pass:
        blockers.append("full_reference_misses_pattern_or_etch_gate")
    if not comparisons["full_vs_quarter"]["pass"]:
        blockers.append("full_vs_quarter_bridge_failed")
    if not comparisons["grid_bridge"]["pass"]:
        blockers.append("grid_bridge_failed")
    if not erosion["pass"]:
        blockers.append("erosion_response_not_monotonic_or_not_bracketed")
    broad_authorized = not blockers
    return {
        "classification": (
            "gate0_pass_broad_pattern_bosch_screen_authorized"
            if broad_authorized else "gate0_blocked"
        ),
        "blockers": blockers,
        "complete_valid_matrix": complete,
        "full_reference_pass": reference_pass,
        "broad_pattern_bosch_screen_authorized": broad_authorized,
        "recipe_authorized": False,
        "process_window_authorized": False,
        "full_traveler_authorized": False,
        "automatic_downstream_launch_authorized": False,
    }


def _selected_success_rows(path, cases) -> tuple[list[dict], int]:
    path = Path(path)
    campaign.audit_existing_rows(path, cases)
    if not path.exists():
        return [], 0
    expected = {case["case_id"] for case in cases}
    rows = []
    attempt_count = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        attempt_count += 1
        row = campaign.strict_json_loads(line)
        if row.get("case_id") in expected and row.get("ok") is True:
            rows.append(row)
    return rows, attempt_count


def build_summary(manifest, rows_path) -> dict:
    cases = campaign.expand_cases(manifest)
    manifest_errors = campaign.validate_manifest(manifest, cases)
    if manifest_errors:
        raise ValueError("invalid Gate-0 manifest: " + "; ".join(manifest_errors))
    success_rows, attempt_count = _selected_success_rows(rows_path, cases)
    by_id = {row["case_id"]: row for row in success_rows}
    reviewed = [
        review_case(by_id[case["case_id"]], case, rows_path, manifest)
        for case in cases if case["case_id"] in by_id
    ]
    missing = [case["case_id"] for case in cases if case["case_id"] not in by_id]
    comparisons = {
        "full_vs_quarter": paired_comparison(
            reviewed, manifest, "full_vs_quarter"
        ),
        "grid_bridge": paired_comparison(reviewed, manifest, "grid_bridge"),
    }
    erosion = erosion_response(reviewed, manifest)
    decision = decision_from_evidence(reviewed, comparisons, erosion, missing)
    return {
        "campaign": manifest["campaign"],
        "labels": manifest["labels"],
        "authority": manifest["authority"],
        "rng_interpretation": manifest["rng_policy"],
        "status": (
            "complete_gate0_pass"
            if decision["broad_pattern_bosch_screen_authorized"]
            else "complete_gate0_blocked"
            if len(reviewed) == 24 and all(row.get("valid") for row in reviewed)
            else "incomplete_or_invalid"
        ),
        "expected_case_count": 24,
        "attempt_count": attempt_count,
        "selected_success_count": len(success_rows),
        "independently_valid_case_count": sum(row.get("valid", False) for row in reviewed),
        "missing_case_ids": missing,
        "case_review_errors": {
            row["case_id"]: row.get("errors", [])
            for row in reviewed if row.get("errors")
        },
        "gate_pass_counts": {
            gate: sum(row.get("gates", {}).get(gate, False) for row in reviewed)
            for gate in (
                "pattern_width",
                "pattern_height",
                "pattern_opening",
                "etch_depth",
                "etch_cd_profile",
                "etch_bow",
                "etch_mask_resolved",
            )
        },
        "reviewed_cases": reviewed,
        "comparisons": comparisons,
        "erosion_response": erosion,
        "decision": decision,
    }


def markdown(summary) -> str:
    lines = [
        "# Pattern/Bosch Gate-0 critical review",
        "",
        f"Status: **{summary['status']}**. Independently valid checkpoints: "
        f"{summary['independently_valid_case_count']}/24; attempts: "
        f"{summary['attempt_count']}.",
        "",
        "Authority is limited to a broad pattern/Bosch screen. This review "
        "cannot authorize a recipe, process window, downstream launch, or full "
        "traveler.",
        "",
        "The arms share base-seed labels for paired bookkeeping. They are not "
        "claimed to use identical pointwise random draws: FULL and QUARTER "
        "surfaces have different node sampling, and evolving arms may diverge.",
        "",
        "| Arm | Seed | Depth | Top/Mid/Bottom CD | Bow | Scallop | Mask left | Pattern | Etch | Valid |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["reviewed_cases"]:
        metrics = row.get("metrics", {})
        lines.append(
            f"| {row['arm']} | {row['rng_seed']} | "
            f"{metrics.get('depth', float('nan')):.6g} | "
            f"{metrics.get('cd_top', float('nan')):.5g}/"
            f"{metrics.get('cd_middle', float('nan')):.5g}/"
            f"{metrics.get('cd_bottom', float('nan')):.5g} | "
            f"{metrics.get('max_bow', float('nan')):.5g} | "
            f"{metrics.get('scallop_rms', float('nan')):.5g} | "
            f"{metrics.get('mask_remaining_height', float('nan')):.5g} | "
            f"{int(bool(row.get('pattern_pass')))} | "
            f"{int(bool(row.get('etch_pass')))} | "
            f"{int(bool(row.get('valid')))} |"
        )
    lines += ["", "## Numerical bridges", ""]
    for name, result in summary["comparisons"].items():
        lines.append(
            f"- **{name}**: pass={result['pass']}; pairs={len(result['pairs'])}/4; "
            f"no gate flips={result['no_gate_flips']}."
        )
        for metric, values in result["metric_results"].items():
            lines.append(
                f"  - {metric}: max |delta|={values['maximum_absolute_delta']} "
                f"against {values['tolerance']}; pass={values['pass']}"
            )
    erosion = summary["erosion_response"]
    lines += [
        "",
        "## Mask-erosion response",
        "",
        f"All shared-seed sequences monotonic: {erosion['all_seeds_monotonic']}.",
        f"All-seed surviving arms: {erosion['all_seed_surviving_arms'] or 'none'}.",
        f"All-seed failed arms: {erosion['all_seed_failed_arms'] or 'none'}.",
        "",
        "## Decision",
        "",
        f"Classification: `{summary['decision']['classification']}`.",
        f"Blockers: {summary['decision']['blockers'] or 'none'}.",
        "Recipe authorized: no. Process window authorized: no. Full traveler "
        "authorized: no. Automatic downstream launch authorized: no.",
        "",
    ]
    return "\n".join(lines)


def write_json(path, value):
    serialized = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    manifest = campaign.strict_json_loads(args.manifest.read_text())
    summary = build_summary(manifest, args.rows)
    write_json(args.json, summary)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown(summary) + "\n")
    print(json.dumps({
        "status": summary["status"],
        "selected": summary["selected_success_count"],
        "valid": summary["independently_valid_case_count"],
        "broad_screen_authorized": summary["decision"][
            "broad_pattern_bosch_screen_authorized"
        ],
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

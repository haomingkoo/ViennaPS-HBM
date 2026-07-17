"""Independent review of the adaptive pattern/Bosch Gate-0 R1 campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import foundation_pattern_bosch_gate0_r1 as campaign
import native_domain_checkpoint as native_checkpoint


DEFAULT_MANIFEST = campaign.DEFAULT_MANIFEST
DEFAULT_ROWS = campaign.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/pattern_bosch_gate0_r1_summary.json"
)
DEFAULT_MARKDOWN = Path(
    "autoresearch-results/restart_audit/pattern_bosch_gate0_r1_review.md"
)
PAIRED_METRICS = tuple(campaign.gate0.EXPECTED_TOLERANCES)


def review_case(row, case, output, manifest) -> dict:
    errors = campaign.validate_success_row(row, case, output)
    measured = row.get("selected_cycle_metrics") or {}
    gates = row.get("gates") or {}
    try:
        domain = native_checkpoint.load_domain_checkpoint(
            row["checkpoint_path"], expected_sha256=row["checkpoint_sha256"]
        )
        recomputed, invalid = campaign._measure_domain(domain, case)
        errors.extend(campaign._compare_values(
            recomputed,
            measured,
            float(manifest["review"]["row_recompute_abs_tolerance"]),
            "selected_cycle_metrics",
        ))
        if invalid != row.get("selected_metric_invalid_reasons"):
            errors.append("independent invalid-reason vector differs")
        if campaign.domain_mesh_sha256(domain) != row.get("native_mesh_sha256"):
            errors.append("independent native mesh hash differs")
    except Exception as error:
        errors.append(f"independent native reload failed: {error}")
    etch = measured.get("etch") or {}
    metrics = {
        "depth": etch.get("depth"),
        "cd_top": etch.get("cd_top"),
        "cd_middle": etch.get("cd_middle"),
        "cd_bottom": etch.get("cd_bottom"),
        "max_cd_error": etch.get("max_cd_error"),
        "max_bow": etch.get("max_bow"),
        "scallop_rms": etch.get("scallop_rms"),
        "mask_remaining_height": measured.get("mask_remaining_height"),
    }
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in metrics.values()
    ):
        errors.append("review metric is missing or nonnumeric")
    return {
        "case_id": case["case_id"],
        "arm": case["arm"],
        "role": case["role"],
        "rng_seed": case["rng_seed"],
        "rays_per_point": case["numerics"]["rays_per_point"],
        "mask_ion_rate": case["recipe"]["mask_ion_rate"],
        "adaptive": case["adaptive"],
        "valid": not errors,
        "errors": errors,
        "selection_eligible": row.get("selection_eligible") is True,
        "selected_cycle": row.get("selected_cycle"),
        "gates": gates,
        "hard_gate_pass": row.get("hard_gate_pass") is True,
        "metrics": metrics,
        "checkpoint_path": row.get("checkpoint_path"),
        "checkpoint_sha256": row.get("checkpoint_sha256"),
        "native_mesh_sha256": row.get("native_mesh_sha256"),
        "native_roundtrip_exact": row.get("native_roundtrip_exact") is True,
    }


def ray_bridge(reviewed, manifest) -> dict:
    contract = manifest["review"]["ray_bridge"]
    by_key = {(row["arm"], row["rng_seed"]): row for row in reviewed}
    pairs = []
    errors = []
    for seed in campaign.EXPECTED_SEEDS:
        reference = by_key.get((contract["reference_arm"], seed))
        anchor = by_key.get((contract["candidate_arm"], seed))
        if reference is None or anchor is None:
            errors.append(f"missing ray pair {seed}")
            continue
        if not reference["valid"] or not anchor["valid"]:
            errors.append(f"invalid ray pair {seed}")
            continue
        deltas = {
            metric: anchor["metrics"][metric] - reference["metrics"][metric]
            for metric in PAIRED_METRICS
        }
        pairs.append({
            "rng_seed": seed,
            "reference_case_id": reference["case_id"],
            "anchor_case_id": anchor["case_id"],
            "deltas": deltas,
            "gate_flip": bool(
                reference["gates"] != anchor["gates"]
                or reference.get("selection_eligible")
                != anchor.get("selection_eligible")
                or reference["hard_gate_pass"] != anchor["hard_gate_pass"]
            ),
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
                len(values) == len(campaign.EXPECTED_SEEDS)
                and all(value <= tolerance for value in values)
            ),
        }
    eligible = len(pairs) == len(campaign.EXPECTED_SEEDS) and not errors
    no_gate_flips = bool(eligible and not any(pair["gate_flip"] for pair in pairs))
    return {
        "pairing": (
            "shared base-seed labels; pointwise common random numbers are not "
            "claimed across ray counts"
        ),
        "reference_arm": contract["reference_arm"],
        "anchor_arm": contract["candidate_arm"],
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


def mask_bracket(reviewed, manifest) -> dict:
    by_key = {(row["arm"], row["rng_seed"]): row for row in reviewed}
    reference = {
        seed: by_key.get((campaign.REFERENCE_ARM, seed))
        for seed in campaign.EXPECTED_SEEDS
    }
    search_seed = manifest["mask_bracket"]["search_seed"]
    rates = manifest["mask_bracket"]["search_rates"]
    search_results = []
    selected_index = None
    errors = []
    for index, rate in enumerate(rates):
        row = by_key.get((campaign.mask_arm(rate), search_seed))
        if row is None:
            break
        if not row["valid"]:
            errors.append(f"invalid mask search rate {rate}")
            break
        survives = row["gates"].get("etch_mask_resolved") is True
        search_results.append({
            "rate_index": index,
            "mask_ion_rate": rate,
            "case_id": row["case_id"],
            "survives": survives,
            "mask_remaining_height": row["metrics"]["mask_remaining_height"],
        })
        if not survives:
            selected_index = index
            break
    chosen_rate = rates[selected_index] if selected_index is not None else None
    confirmations = []
    if selected_index is not None:
        arm = campaign.mask_arm(chosen_rate)
        for seed in campaign.EXPECTED_SEEDS:
            row = by_key.get((arm, seed))
            baseline = reference.get(seed)
            if row is None:
                errors.append(f"missing mask confirmation seed {seed}")
                continue
            if not row["valid"]:
                errors.append(f"invalid mask confirmation seed {seed}")
                continue
            baseline_survives = bool(
                baseline
                and baseline["valid"]
                and baseline["gates"].get("etch_mask_resolved") is True
            )
            challenge_fails = row["gates"].get("etch_mask_resolved") is False
            monotonic = bool(
                baseline
                and row["metrics"]["mask_remaining_height"]
                <= baseline["metrics"]["mask_remaining_height"] + 1e-12
            )
            confirmations.append({
                "rng_seed": seed,
                "case_id": row["case_id"],
                "baseline_survives": baseline_survives,
                "challenge_fails": challenge_fails,
                "remaining_height_nonincreasing": monotonic,
                "mask_remaining_height": row["metrics"]["mask_remaining_height"],
            })
    prior_searches_survive = bool(
        selected_index is not None
        and len(search_results) == selected_index + 1
        and all(item["survives"] for item in search_results[:-1])
        and search_results[-1]["survives"] is False
    )
    confirmed = bool(
        len(confirmations) == len(campaign.EXPECTED_SEEDS)
        and all(
            item["baseline_survives"]
            and item["challenge_fails"]
            and item["remaining_height_nonincreasing"]
            for item in confirmations
        )
    )
    return {
        "search_rates": rates,
        "search_results": search_results,
        "selected_failure_rate_index": selected_index,
        "selected_failure_rate": chosen_rate,
        "confirmations": confirmations,
        "errors": errors,
        "pass": bool(prior_searches_survive and confirmed and not errors),
    }


def native_handoffs(reviewed) -> dict:
    references = sorted(
        (row for row in reviewed if row["arm"] == campaign.REFERENCE_ARM),
        key=lambda row: row["rng_seed"],
    )
    results = []
    errors = []
    for row in references:
        try:
            domain = native_checkpoint.load_domain_checkpoint(
                row["checkpoint_path"], expected_sha256=row["checkpoint_sha256"]
            )
            silicon = native_checkpoint.extract_raw_silicon_domain(domain)
            silicon_mesh_hash = campaign.domain_mesh_sha256(silicon)
            accepted = bool(
                row["valid"]
                and row["hard_gate_pass"]
                and row["native_roundtrip_exact"]
            )
            results.append({
                "case_id": row["case_id"],
                "rng_seed": row["rng_seed"],
                "checkpoint_path": row["checkpoint_path"],
                "checkpoint_sha256": row["checkpoint_sha256"],
                "silicon_mesh_sha256": silicon_mesh_hash,
                "accepted": accepted,
            })
        except Exception as error:
            errors.append(f"{row['case_id']}: {error}")
    accepted = bool(
        len(results) == len(campaign.EXPECTED_SEEDS)
        and all(row["accepted"] for row in results)
        and not errors
    )
    return {
        "source_arm": campaign.REFERENCE_ARM,
        "reviewed_checkpoint_count": len(results),
        "handoff_results": results,
        "errors": errors,
        "decision": {
            "classification": (
                "native_full_reference_checkpoints_reusable"
                if accepted else "native_full_reference_checkpoint_handoff_blocked"
            ),
            "reusable_upstream_geometry_authorized": accepted,
            "layer_recipe_authorized": False,
            "process_window_authorized": False,
            "full_traveler_authorized": False,
        },
    }


def build_summary(manifest, rows_path) -> dict:
    cases = campaign.expand_cases(manifest)
    manifest_errors = campaign.validate_manifest(manifest, cases)
    if manifest_errors:
        raise ValueError("invalid Gate-0 R1 manifest: " + "; ".join(manifest_errors))
    successes, attempt_count = campaign.audit_existing_rows(rows_path, cases)
    by_id = {case["case_id"]: case for case in cases}
    reviewed = [
        review_case(row, by_id[current_id], rows_path, manifest)
        for current_id, row in successes.items()
    ]
    active = campaign.active_case_ids(cases, successes)
    pending = sorted(active - set(successes))
    terminal = campaign.campaign_terminal(cases, successes)
    reference_rows = [
        row for row in reviewed if row["arm"] == campaign.REFERENCE_ARM
    ]
    references_pass = bool(
        len(reference_rows) == len(campaign.EXPECTED_SEEDS)
        and all(row["valid"] and row["hard_gate_pass"] for row in reference_rows)
    )
    bridge = ray_bridge(reviewed, manifest)
    bracket = mask_bracket(reviewed, manifest)
    handoffs = native_handoffs(reviewed)
    handoff_evidence_pass = handoffs["decision"][
        "reusable_upstream_geometry_authorized"
    ]
    blockers = []
    if not terminal:
        blockers.append("adaptive_campaign_incomplete")
    if any(not row["valid"] for row in reviewed):
        blockers.append("one_or_more_success_rows_invalid")
    if not references_pass:
        blockers.append("full_reference_r1000_does_not_pass_all_four_seeds")
    if not bridge["pass"]:
        blockers.append("ray_1000_to_2000_bridge_failed")
    if not bracket["pass"]:
        blockers.append("mask_failure_bracket_not_confirmed")
    if not handoff_evidence_pass:
        blockers.append("native_reference_handoffs_failed")
    authorized = not blockers
    handoffs["decision"]["classification"] = (
        "native_full_reference_checkpoints_reusable"
        if authorized else "native_full_reference_checkpoint_handoff_blocked"
    )
    handoffs["decision"]["reusable_upstream_geometry_authorized"] = authorized
    decision = {
        "classification": (
            "gate0_r1_pass_broad_pattern_bosch_screen_authorized"
            if authorized else "gate0_r1_blocked"
        ),
        "blockers": blockers,
        "broad_pattern_bosch_screen_authorized": authorized,
        "reusable_upstream_geometry_authorized": authorized,
        "recipe_authorized": False,
        "process_window_authorized": False,
        "full_traveler_authorized": False,
        "automatic_downstream_launch_authorized": False,
    }
    return {
        "campaign": manifest["campaign"],
        "labels": manifest["labels"],
        "authority": manifest["authority"],
        "status": (
            "complete_gate0_r1_pass"
            if authorized else "complete_gate0_r1_blocked"
            if terminal else "incomplete_or_invalid"
        ),
        "potential_case_count": len(cases),
        "active_case_count": len(active),
        "attempt_count": attempt_count,
        "selected_success_count": len(successes),
        "independently_valid_case_count": sum(row["valid"] for row in reviewed),
        "pending_case_ids": pending,
        "reviewed_cases": reviewed,
        "ray_bridge": bridge,
        "mask_bracket": bracket,
        "native_handoffs": handoffs,
        "decision": decision,
    }


def markdown(summary) -> str:
    lines = [
        "# Pattern/Bosch Gate-0 R1 critical review",
        "",
        f"Status: **{summary['status']}**. Valid native checkpoints: "
        f"{summary['independently_valid_case_count']}/"
        f"{summary['selected_success_count']}; attempts: {summary['attempt_count']}.",
        "",
        "| Arm | Seed | Rays | Cycle | Depth | Mask left | Hard pass | Valid |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(
        summary["reviewed_cases"],
        key=lambda item: (item["arm"], item["rng_seed"]),
    ):
        lines.append(
            f"| {row['arm']} | {row['rng_seed']} | {row['rays_per_point']} | "
            f"{row['selected_cycle']} | {row['metrics']['depth']:.6g} | "
            f"{row['metrics']['mask_remaining_height']:.6g} | "
            f"{int(row['hard_gate_pass'])} | {int(row['valid'])} |"
        )
    bridge = summary["ray_bridge"]
    bracket = summary["mask_bracket"]
    handoffs = summary["native_handoffs"]
    lines += [
        "",
        "## Decisions",
        "",
        f"- 1000/2000-ray bridge: pass={bridge['pass']}; "
        f"pairs={len(bridge['pairs'])}/4; no gate flips={bridge['no_gate_flips']}.",
        f"- Mask bracket: pass={bracket['pass']}; selected failure rate="
        f"{bracket['selected_failure_rate']}.",
        f"- Native handoffs: "
        f"{sum(row['accepted'] for row in handoffs['handoff_results'])}/4 accepted.",
        f"- Classification: `{summary['decision']['classification']}`.",
        f"- Blockers: {summary['decision']['blockers'] or 'none'}.",
        "",
        "Recipe authorized: no. Process window authorized: no. Full traveler "
        "authorized: no. Automatic downstream launch authorized: no.",
        "",
    ]
    return "\n".join(lines)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        value, indent=2, sort_keys=True, allow_nan=False
    ) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    manifest = campaign.gate0.strict_json_loads(args.manifest.read_text())
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

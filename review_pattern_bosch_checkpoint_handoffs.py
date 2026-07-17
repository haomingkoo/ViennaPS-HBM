"""Review every reusable full-width Gate-0 silicon checkpoint."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import foundation_pattern_bosch_gate0 as gate0
import pattern_bosch_checkpoint_handoff as handoff


DEFAULT_GATE0_SUMMARY = Path(
    "autoresearch-results/restart_audit/pattern_bosch_gate0_summary.json"
)
DEFAULT_ROWS = gate0.DEFAULT_OUTPUT
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/pattern_bosch_handoff_summary.json"
)
DEFAULT_MARKDOWN = Path(
    "autoresearch-results/restart_audit/pattern_bosch_handoff_review.md"
)
SOURCE_ARM = "full_reference_fine"


def strict_rows(path):
    rows = []
    path = Path(path)
    if not path.is_file():
        return rows
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(gate0.strict_json_loads(line))
        except Exception as error:
            raise ValueError(f"malformed Gate-0 row {line_number}: {error}") from error
    return rows


def validate_row_identity(row):
    payload = gate0.case_payload(row)
    expected_id = gate0.case_id(payload)
    expected_hash = gate0.canonical_sha256(payload)
    if row.get("case_id") != expected_id:
        raise ValueError("Gate-0 success row case ID differs from its payload")
    if row.get("case_payload_sha256") != expected_hash:
        raise ValueError("Gate-0 success row payload hash differs")
    return {**payload, "case_id": expected_id, "case_payload_sha256": expected_hash}


def build_summary(gate0_summary, rows_path):
    decision = gate0_summary.get("decision", {})
    gate0_authorized = decision.get(
        "broad_pattern_bosch_screen_authorized"
    ) is True
    reviewed = {
        row.get("case_id"): row
        for row in gate0_summary.get("reviewed_cases", [])
        if row.get("arm") == SOURCE_ARM
    }
    attempts = [
        row for row in strict_rows(rows_path)
        if row.get("arm") == SOURCE_ARM
    ]
    success_rows = [row for row in attempts if row.get("ok") is True]
    duplicate_ids = sorted(
        case_id for case_id, count in Counter(
            row.get("case_id") for row in success_rows
        ).items() if count > 1
    )
    seed_counts = Counter(row.get("rng_seed") for row in success_rows)
    unexpected_seeds = sorted(
        seed for seed in seed_counts if seed not in gate0.EXPECTED_SEEDS
    )
    missing_seeds = sorted(set(gate0.EXPECTED_SEEDS) - set(seed_counts))
    repeated_seeds = sorted(seed for seed, count in seed_counts.items() if count > 1)

    results = []
    errors = []
    if duplicate_ids:
        errors.append("duplicate successful case IDs")
    if unexpected_seeds:
        errors.append("unexpected full-reference seeds")
    if missing_seeds:
        errors.append("missing full-reference seeds")
    if repeated_seeds:
        errors.append("repeated full-reference seed labels")
    for row in success_rows:
        try:
            case = validate_row_identity(row)
            reviewed_row = reviewed.get(case["case_id"])
            if not reviewed_row:
                raise ValueError("successful checkpoint is absent from the Gate-0 review")
            if not (
                reviewed_row.get("valid") is True
                and reviewed_row.get("pattern_pass") is True
                and reviewed_row.get("etch_pass") is True
            ):
                raise ValueError("Gate-0 review did not accept the upstream case")
            result = handoff.compare_checkpoint_handoff(
                row["checkpoint_path"],
                expected_sha256=row["checkpoint_sha256"],
            )
            if result["case_id"] != case["case_id"]:
                raise ValueError("checkpoint case differs from the successful row")
            result.pop("geometry")
            results.append(gate0.foundation.jsonable(result))
        except Exception as error:
            errors.append(f"{row.get('case_id')}: {error}")

    all_handoffs_accepted = bool(
        len(results) == 4 and all(result["accepted"] for result in results)
    )
    accepted = bool(gate0_authorized and not errors and all_handoffs_accepted)
    blockers = []
    if not gate0_authorized:
        blockers.append("Gate-0 critical review did not authorize the broad screen")
    if errors:
        blockers.append("one or more full-reference checkpoint records are invalid")
    if not all_handoffs_accepted:
        blockers.append("all four full-reference surface handoffs must pass")
    return {
        "source_campaign": gate0_summary.get("campaign"),
        "source_arm": SOURCE_ARM,
        "expected_seeds": list(gate0.EXPECTED_SEEDS),
        "attempt_count": len(attempts),
        "successful_checkpoint_count": len(success_rows),
        "reviewed_checkpoint_count": len(results),
        "gate0_broad_screen_authorized": gate0_authorized,
        "handoff_results": results,
        "errors": errors,
        "blockers": blockers,
        "decision": {
            "classification": (
                "full_reference_checkpoints_reusable"
                if accepted else "full_reference_checkpoint_handoff_blocked"
            ),
            "reusable_upstream_geometry_authorized": accepted,
            "layer_recipe_authorized": False,
            "process_window_authorized": False,
            "full_traveler_authorized": False,
        },
    }


def markdown(summary):
    lines = [
        "# Pattern/Bosch checkpoint handoff review",
        "",
        f"Decision: `{summary['decision']['classification']}`. "
        f"Accepted handoffs: {sum(row['accepted'] for row in summary['handoff_results'])}/4.",
        "",
        "This review only decides whether the four full-width silicon shapes "
        "can be reused as upstream geometry. It does not select a liner, "
        "barrier, seed, or full-traveler recipe.",
        "",
        "| Seed | Max surface drift | Worst normalized CTQ drift | Gate flip | Accepted |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(summary["handoff_results"], key=lambda item: item["rng_seed"]):
        lines.append(
            f"| {row['rng_seed']} | "
            f"{row['maximum_surface_distance']:.6g} | "
            f"{row['maximum_normalized_ctq_delta']:.6g} | "
            f"{int(row['gate_flip'])} | {int(row['accepted'])} |"
        )
    lines += ["", f"Blockers: {summary['blockers'] or 'none'}.", ""]
    return "\n".join(lines)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        value, indent=2, sort_keys=True, allow_nan=False
    ) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate0-summary", type=Path, default=DEFAULT_GATE0_SUMMARY)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    gate0_summary = gate0.strict_json_loads(args.gate0_summary.read_text())
    summary = build_summary(gate0_summary, args.rows)
    write_json(args.json, summary)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown(summary) + "\n")
    print(json.dumps(summary["decision"], sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

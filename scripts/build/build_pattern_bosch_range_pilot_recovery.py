"""Freeze the seven-case pilot classification recovery."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.autoresearch_event_log import validate_log


ROOT = Path(__file__).resolve().parents[2]
PARENT_DESIGN = ROOT / "pattern_bosch_range_pilot_design.json"
PARENT_EVENTS = ROOT / "autoresearch-results/range_pilot/pattern_bosch_dsd25_rows.jsonl"
OUTPUT = ROOT / "pattern_bosch_range_pilot_recovery_design.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    parent = json.loads(PARENT_DESIGN.read_text())
    errors, indexed_rows = validate_log(PARENT_EVENTS)
    if errors:
        raise ValueError("parent event log is invalid: " + "; ".join(errors))
    cases_by_id = {case["case_id"]: case for case in parent["cases"]}
    affected = []
    for line_number, row in indexed_rows:
        if row["state"] != "failed_deterministic":
            continue
        case = dict(cases_by_id[row["case_key"]])
        case["parent_event"] = {
            "path": str(PARENT_EVENTS.relative_to(ROOT)),
            "line": line_number,
            "event_hash": row["event_hash"],
            "reported_error": row["error"],
        }
        affected.append(case)
    if len(affected) != 7:
        raise ValueError("recovery design requires the seven affected parent rows")
    return {
        "schema_version": 1,
        "campaign": "pattern-bosch-range-pilot-recovery-v1",
        "status": "frozen_recovery_design",
        "authority": "classification_and_checkpoint_recovery_only",
        "question": (
            "Can the final geometry be saved before measurement, and do the two "
            "low-movement rows contain usable measurements?"
        ),
        "sources": [
            {"path": str(PARENT_DESIGN.relative_to(ROOT)), "sha256": _sha256(PARENT_DESIGN)},
            {"path": str(PARENT_EVENTS.relative_to(ROOT)), "sha256": _sha256(PARENT_EVENTS)},
            {
                "path": "run_pattern_bosch_range_pilot_recovery.py",
                "sha256": _sha256(ROOT / "run_pattern_bosch_range_pilot_recovery.py"),
            },
            {
                "path": "pattern_bosch_measurement_contract.json",
                "sha256": _sha256(ROOT / "pattern_bosch_measurement_contract.json"),
            },
        ],
        "numerics": parent["numerics"],
        "geometry": parent["geometry"],
        "rng_policy": parent["rng_policy"],
        "comparison_context": parent["comparison_context"],
        "inference_policy": {
            "allowed": [
                "measurement availability",
                "saved final-geometry availability",
                "low-movement guard classification",
                "extractor failure classification",
            ],
            "prohibited": parent["inference_policy"]["prohibited"],
        },
        "execution": {
            "case_cap": 7,
            "retry_policy": "no automatic retry",
            "checkpoint_policy": "save final completed cycle before measurement",
        },
        "cases": affected,
        "output": "autoresearch-results/range_pilot/pattern_bosch_recovery_v1_rows.jsonl",
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"range-pilot recovery design: {len(document['cases'])} cases")


if __name__ == "__main__":
    main()

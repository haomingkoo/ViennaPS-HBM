"""Build the corrected range-pilot review from committed evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics

from scripts.autoresearch_event_log import event_hash, schema_errors


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "pattern_bosch_range_pilot_design.json"
RECOVERY_MANIFEST = ROOT / "pattern_bosch_range_pilot_recovery_design.json"
BUNDLE = ROOT / "evidence/bosch/range_pilot/source_bundle.json"
OUTPUT = ROOT / "pattern_bosch_range_pilot_review.json"
UNAVAILABLE_REVIEW = ROOT / "evidence/bosch/pattern_bosch_unavailable_profile_review.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(
        path.read_text(),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant {value}")
        ),
    )


def _citation(group: str, index: int, row: dict) -> dict:
    return {
        "path": str(BUNDLE.relative_to(ROOT)),
        "selector": f"/{group}/{index}",
        "event_hash": row["event_hash"],
        "case_id": row["case_key"],
    }


def _validated_group(bundle: dict, group: str, expected_manifest_hash: str) -> list[tuple[int, dict, str]]:
    rows = bundle[group]
    previous_hash = None
    for index, row in enumerate(rows):
        errors = schema_errors(row)
        if errors:
            raise ValueError(f"{group}[{index}] invalid: " + "; ".join(errors))
        if row["previous_event_hash"] != previous_hash or row["event_hash"] != event_hash(row):
            raise ValueError(f"{group}[{index}] has a broken hash chain")
        if row["manifest_hash"] != expected_manifest_hash:
            raise ValueError(f"{group}[{index}] has stale provenance")
        previous_hash = row["event_hash"]
    return [(index, row, group) for index, row in enumerate(rows)]


def build() -> dict:
    manifest = _load(MANIFEST)
    bundle = _load(BUNDLE)
    unavailable_review = _load(UNAVAILABLE_REVIEW)
    unavailable_by_case = {
        case["case_id"]: case for case in unavailable_review["cases"]
    }
    committed = {item["path"]: item["sha256"] for item in bundle["committed_sources"]}
    for path, digest in committed.items():
        if _sha256(ROOT / path) != digest:
            raise ValueError(f"committed source hash differs: {path}")

    parent_rows = _validated_group(bundle, "parent_events", _sha256(MANIFEST))
    recovery_rows = _validated_group(
        bundle, "recovery_events", _sha256(RECOVERY_MANIFEST)
    )
    groups = {
        "parent_events": bundle["parent_events"],
        "recovery_events": bundle["recovery_events"],
    }
    profiles = {case["case_id"]: case["profile"] for case in bundle["cases"]}
    combined = []
    for case in sorted(bundle["cases"], key=lambda item: item["design_row"]):
        selected = case["selected_event"]
        row = groups[selected["group"]][selected["index"]]
        if row["case_key"] != case["case_id"] or row["event_hash"] != selected["event_hash"]:
            raise ValueError(f"selected event differs for {case['case_id']}")
        if hashlib.sha256(case["profile"]["surface_path"].encode()).hexdigest() != case["profile"]["surface_sha256"]:
            raise ValueError(f"surface hash differs for {case['case_id']}")
        combined.append((selected["index"], row, selected["group"]))
    if len(combined) != 25 or len({row["case_key"] for _, row, _ in combined}) != 25:
        raise ValueError("corrected review needs 25 unique cases")

    measured = [item for item in combined if item[1]["state"] == "complete_measured"]
    unavailable = [item for item in combined if item[1]["state"] == "missing_measurement"]
    state_counts = Counter(row["state"] for _, row, _ in combined)

    response_spans = []
    for metric_id in manifest["required_measurements"]:
        values = []
        for index, row, group in measured:
            value = row["measurements"][metric_id]["value"]
            if value is not None:
                values.append((float(value), index, row, group))
        if len(values) != 20:
            raise ValueError(f"expected 20 usable values for {metric_id}")
        low = min(values, key=lambda item: item[0])
        high = max(values, key=lambda item: item[0])
        response_spans.append({
            "metric_id": metric_id,
            "units": low[2]["measurements"][metric_id]["units"],
            "observed_minimum": low[0],
            "observed_maximum": high[0],
            "observed_span": high[0] - low[0],
            "usable_rows": 20,
            "minimum_source": _citation(low[3], low[1], low[2]),
            "maximum_source": _citation(high[3], high[1], high[2]),
            "status": (
                "available_unqualified"
                if metric_id.startswith("mask_")
                else "suspended_legacy_positive_wall_mirroring"
            ),
            "interpretation": (
                "raw span at the unqualified coarse setting"
                if metric_id.startswith("mask_")
                else "legacy diagnostic span; not a full-width etch measurement"
            ),
        })

    center = next(
        case for case in manifest["cases"] if all(value == 0 for value in case["coded_levels"])
    )
    row_by_case = {row["case_key"]: item for item in combined for row in [item[1]]}
    nominations: dict[str, set[str]] = defaultdict(set)
    nominations[center["case_id"]].add("design center reference")
    for _, row, _ in recovery_rows:
        observation = (row.get("measurements") or {}).get("pilot_observation", {}).get("value")
        if observation == "low_movement_guard":
            nominations[row["case_key"]].add("measurable low-movement state")
    for _, row, _ in unavailable:
        availability = unavailable_by_case[row["case_key"]]["availability_class"]
        nominations[row["case_key"]].add(availability.replace("_", " "))
    widest = max(measured, key=lambda item: item[1]["measurements"]["mask_opening_cd_top"]["value"])
    nominations[widest[1]["case_key"]].add("widest measured mask opening")

    nominated_rows = []
    for case_id, reasons in sorted(nominations.items()):
        index, row, group = row_by_case[case_id]
        nominated_rows.append({
            "case_id": case_id,
            "state": row["state"],
            "reasons": sorted(reasons),
            "source": _citation(group, index, row),
            "checkpoint": {
                "native_sha256": profiles[case_id]["native_sha256"],
                "surface_sha256": profiles[case_id]["surface_sha256"],
            },
            "next_use": "confirmation candidate only; selection does not imply factor attribution",
        })

    manifest_cases = {case["case_id"]: case for case in manifest["cases"]}
    public_cases = []
    for index, row, group in combined:
        observation = (row.get("measurements") or {}).get("pilot_observation", {}).get("value")
        display_state = (
            "legacy_row_incomplete"
            if row["state"] == "missing_measurement"
            else "legacy_low_movement_row"
            if observation == "low_movement_guard"
            else "legacy_row_complete"
        )
        profile = profiles[row["case_key"]]
        unavailable_case = unavailable_by_case.get(row["case_key"])
        public_cases.append({
            "design_row": manifest_cases[row["case_key"]]["design_row"],
            "case_id": row["case_key"],
            "state": row["state"],
            "display_state": display_state,
            "measurement_availability": (
                unavailable_case["availability_class"] if unavailable_case else None
            ),
            "is_center": row["case_key"] == center["case_id"],
            "controls_changed_together": 12,
            "recipe": row["inputs"]["recipe"],
            "derived_exposures": row["inputs"]["derived_exposures"],
            "elapsed_s": row["elapsed_s"],
            "legacy_measurements": ({metric_id: row["measurements"][metric_id]["value"] for metric_id in manifest["required_measurements"]} if row["state"] == "complete_measured" else None),
            "etch_measurement_status": "suspended_legacy_positive_wall_mirroring",
            "error": row["error"],
            "surface_path": profile["surface_path"],
            "view_box": profile["view_box"],
            "source": _citation(group, index, row),
        })
    failures = [{
        "classification": unavailable_by_case[row["case_key"]]["availability_class"],
        "state": row["state"],
        "elapsed_s": row["elapsed_s"],
        "error": row["error"],
        "recipe": row["inputs"]["recipe"],
        "checkpoint": {"native_sha256": profiles[row["case_key"]]["native_sha256"], "surface_sha256": profiles[row["case_key"]]["surface_sha256"]},
        "source": _citation(group, index, row),
        "interpretation": unavailable_by_case[row["case_key"]]["permitted_claim"],
        "review_source": {
            "path": str(UNAVAILABLE_REVIEW.relative_to(ROOT)),
            "selector": f"/cases/{list(unavailable_by_case).index(row['case_key'])}",
            "sha256": _sha256(UNAVAILABLE_REVIEW),
        },
    } for index, row, group in unavailable]

    parent_elapsed = [row["elapsed_s"] for _, row, _ in parent_rows]
    recovery_elapsed = [row["elapsed_s"] for _, row, _ in recovery_rows]
    return {
        "schema_version": 3,
        "campaign": manifest["campaign"],
        "review_status": "complete_corrected_claim_limited_review",
        "highest_supported_claim": (
            "All 25 coarse pilot states are retained. The legacy extractor returned "
            "values in 20 rows, but its etch-shape values are suspended because it "
            "mirrored one wall in a full-width geometry. Review of the five incomplete "
            "rows found two search-window misses, two one-sided saved surfaces, and one "
            "case without the declared reference surface. No factor effects or process "
            "boundary are supported."
        ),
        "prohibited_claims": manifest["inference_policy"]["prohibited"],
        "sources": [
            {"path": str(BUNDLE.relative_to(ROOT)), "sha256": _sha256(BUNDLE)},
            {"path": str(MANIFEST.relative_to(ROOT)), "sha256": _sha256(MANIFEST)},
            {"path": str(RECOVERY_MANIFEST.relative_to(ROOT)), "sha256": _sha256(RECOVERY_MANIFEST)},
            {"path": "pattern_bosch_measurement_contract.json", "sha256": _sha256(ROOT / "pattern_bosch_measurement_contract.json")},
            {"path": str(UNAVAILABLE_REVIEW.relative_to(ROOT)), "sha256": _sha256(UNAVAILABLE_REVIEW)},
        ],
        "execution": {
            "planned_cases": 25,
            "corrected_case_states": 25,
            "state_counts": dict(sorted(state_counts.items())),
            "parent_event_log_valid": True,
            "recovery_event_log_valid": True,
            "single_shared_seed_label": True,
            "independent_repeats": 0,
            "numerical_status": manifest["numerics"]["status"],
        },
        "runtime": {
            "units": "seconds",
            "original_pilot": {"minimum": min(parent_elapsed), "median": statistics.median(parent_elapsed), "maximum": max(parent_elapsed), "total": sum(parent_elapsed)},
            "classification_recovery": {"minimum": min(recovery_elapsed), "median": statistics.median(recovery_elapsed), "maximum": max(recovery_elapsed), "total": sum(recovery_elapsed)},
            "interpretation": "observed wall time on the recorded machine; no factor attribution",
        },
        "response_spans": response_spans,
        "failures": failures,
        "cases": public_cases,
        "confirmation_nominations": nominated_rows,
        "next_decision": "Qualify the full-width extractor and its resolution, numerical, and repeat envelopes before the 54-case screen.",
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"range-pilot review: {document['execution']['state_counts']} nominations={len(document['confirmation_nominations'])}")


if __name__ == "__main__":
    main()

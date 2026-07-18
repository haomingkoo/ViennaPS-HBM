"""Export committed source evidence for the corrected range-pilot review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.autoresearch_event_log import validate_log


ROOT = Path(__file__).resolve().parent
PARENT_MANIFEST = ROOT / "pattern_bosch_range_pilot_design.json"
PARENT_EVENTS = ROOT / "autoresearch-results/range_pilot/pattern_bosch_dsd25_rows.jsonl"
RECOVERY_MANIFEST = ROOT / "pattern_bosch_range_pilot_recovery_design.json"
RECOVERY_EVENTS = ROOT / "autoresearch-results/range_pilot/pattern_bosch_recovery_v1_rows.jsonl"
OUTPUT = ROOT / "evidence/bosch/range_pilot/source_bundle.json"
EXECUTED_EVENT_SCHEMA = ROOT / "evidence/bosch/range_pilot/executed_sources/autoresearch-event.schema.json"
EXECUTED_REGISTRY_BUILDER = ROOT / "evidence/bosch/range_pilot/executed_sources/build_knob_registry.py"
EXECUTED_FACTOR_REGISTRY = ROOT / "evidence/bosch/range_pilot/executed_sources/factor_registry.json"
EXECUTED_FACTOR_PROJECTION = ROOT / "evidence/bosch/range_pilot/executed_sources/pattern_bosch_factor_projection.json"
EXECUTED_MEASUREMENT_CONTRACT = ROOT / "evidence/bosch/range_pilot/executed_sources/pattern_bosch_measurement_contract.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


def _surface(checkpoint: dict) -> dict:
    path = ROOT / checkpoint["path"]
    if _sha256(path) != checkpoint["sha256"]:
        raise ValueError(f"checkpoint hash differs: {path}")
    with np.load(path, allow_pickle=False) as snapshot:
        nodes = np.asarray(snapshot["silicon_nodes"], dtype=float)
        lines = np.asarray(snapshot["silicon_lines"], dtype=int)
        embedded = {
            "manifest_sha256": str(snapshot["manifest_sha256"].item()),
            "case_id": str(snapshot["case_id"].item()),
            "final_completed_cycle": int(snapshot["final_completed_cycle"].item()),
            "grid_delta": float(snapshot["grid_delta"].item()),
            "rays_per_point": int(snapshot["rays_per_point"].item()),
            "rng_seed": int(snapshot["rng_seed"].item()),
        }
    segments = nodes[lines][:, :, :2]
    surface_path = "".join(
        f"M{start[0]:.5f} {start[1]:.5f}L{end[0]:.5f} {end[1]:.5f}"
        for start, end in segments
    )
    x_min, x_max = float(nodes[:, 0].min()), float(nodes[:, 0].max())
    y_min, y_max = float(nodes[:, 1].min()), float(nodes[:, 1].max())
    pad_x = max((x_max - x_min) * 0.08, 0.03)
    pad_y = max((y_max - y_min) * 0.08, 0.03)
    return {
        "native_path": checkpoint["path"],
        "native_sha256": checkpoint["sha256"],
        "embedded_metadata": embedded,
        "surface_path": surface_path,
        "surface_sha256": hashlib.sha256(surface_path.encode()).hexdigest(),
        "view_box": [
            x_min - pad_x,
            -(y_max + pad_y),
            (x_max - x_min) + 2 * pad_x,
            (y_max - y_min) + 2 * pad_y,
        ],
    }


def _events(path: Path, expected: int) -> list[dict]:
    errors, indexed = validate_log(path)
    if errors:
        raise ValueError(f"{path} is invalid: " + "; ".join(errors))
    if len(indexed) != expected:
        raise ValueError(f"{path} has {len(indexed)} events; expected {expected}")
    return [row for _, row in indexed]


def build() -> dict:
    parent_manifest = json.loads(PARENT_MANIFEST.read_text())
    executed_schema_hash = next(
        source["sha256"]
        for source in parent_manifest["sources"]
        if source["path"] == "schemas/autoresearch-event.schema.json"
    )
    if _sha256(EXECUTED_EVENT_SCHEMA) != executed_schema_hash:
        raise ValueError("archived event schema differs from the executed manifest")
    executed_projection_hash = next(
        source["sha256"]
        for source in parent_manifest["sources"]
        if source["path"] == "pattern_bosch_factor_projection.json"
    )
    if _sha256(EXECUTED_FACTOR_PROJECTION) != executed_projection_hash:
        raise ValueError("archived factor projection differs from the executed manifest")
    executed_projection = json.loads(EXECUTED_FACTOR_PROJECTION.read_text())
    executed_registry_hash = next(
        source["sha256"]
        for source in executed_projection["sources"]
        if source["path"] == "factor_registry.json"
    )
    if _sha256(EXECUTED_FACTOR_REGISTRY) != executed_registry_hash:
        raise ValueError("archived factor registry differs from the executed projection")
    executed_registry = json.loads(EXECUTED_FACTOR_REGISTRY.read_text())
    executed_registry_builder_hash = executed_registry["provenance"]["builder"]["sha256"]
    if _sha256(EXECUTED_REGISTRY_BUILDER) != executed_registry_builder_hash:
        raise ValueError("archived registry builder differs from the executed registry")
    executed_measurement_hash = next(
        source["sha256"]
        for source in parent_manifest["sources"]
        if source["path"] == "pattern_bosch_measurement_contract.json"
    )
    if _sha256(EXECUTED_MEASUREMENT_CONTRACT) != executed_measurement_hash:
        raise ValueError("archived measurement contract differs from the executed manifest")
    parent_events = _events(PARENT_EVENTS, 25)
    recovery_events = _events(RECOVERY_EVENTS, 7)
    recovery_by_case = {row["case_key"]: row for row in recovery_events}
    cases = []
    for design_row, parent in enumerate(parent_events):
        selected = recovery_by_case.get(parent["case_key"], parent)
        source_group = "recovery_events" if selected is not parent else "parent_events"
        source_index = (
            recovery_events.index(selected) if source_group == "recovery_events" else design_row
        )
        if selected["checkpoint"] is None:
            raise ValueError(f"corrected case lacks checkpoint: {selected['case_key']}")
        profile = _surface(selected["checkpoint"])
        if profile["embedded_metadata"]["case_id"] != selected["case_key"]:
            raise ValueError(f"checkpoint case differs: {selected['case_key']}")
        if profile["embedded_metadata"]["manifest_sha256"] != selected["manifest_hash"]:
            raise ValueError(f"checkpoint manifest differs: {selected['case_key']}")
        cases.append({
            "design_row": design_row,
            "case_id": selected["case_key"],
            "selected_event": {
                "group": source_group,
                "index": source_index,
                "event_hash": selected["event_hash"],
            },
            "profile": profile,
        })
    return {
        "schema_version": 1,
        "scope": "Committed source rows and extracted final profiles for the corrected 25-case range-pilot review.",
        "interpretation_notes": [
            "The corrected review supersedes classification fields in the parent events.",
            "Historical hard_gate_pass values record the original measurement workflow only; they do not approve a process condition.",
            "Historical numerical_state values do not qualify the 250-ray, 0.01-grid setting.",
        ],
        "superseded_source_versions": [
            {
                "manifest_path": "schemas/autoresearch-event.schema.json",
                "manifest_sha256": executed_schema_hash,
                "archive_path": str(EXECUTED_EVENT_SCHEMA.relative_to(ROOT)),
                "archive_sha256": _sha256(EXECUTED_EVENT_SCHEMA),
            },
            {
                "manifest_path": "pattern_bosch_factor_projection.json",
                "manifest_sha256": executed_projection_hash,
                "archive_path": str(EXECUTED_FACTOR_PROJECTION.relative_to(ROOT)),
                "archive_sha256": _sha256(EXECUTED_FACTOR_PROJECTION),
            },
            {
                "manifest_path": "factor_registry.json",
                "manifest_sha256": executed_registry_hash,
                "archive_path": str(EXECUTED_FACTOR_REGISTRY.relative_to(ROOT)),
                "archive_sha256": _sha256(EXECUTED_FACTOR_REGISTRY),
            },
            {
                "manifest_path": "build_knob_registry.py",
                "manifest_sha256": executed_registry_builder_hash,
                "archive_path": str(EXECUTED_REGISTRY_BUILDER.relative_to(ROOT)),
                "archive_sha256": _sha256(EXECUTED_REGISTRY_BUILDER),
            },
            {
                "manifest_path": "pattern_bosch_measurement_contract.json",
                "manifest_sha256": executed_measurement_hash,
                "archive_path": str(EXECUTED_MEASUREMENT_CONTRACT.relative_to(ROOT)),
                "archive_sha256": _sha256(EXECUTED_MEASUREMENT_CONTRACT),
            },
        ],
        "raw_sources": [
            {"path": str(PARENT_EVENTS.relative_to(ROOT)), "sha256": _sha256(PARENT_EVENTS), "committed": False},
            {"path": str(RECOVERY_EVENTS.relative_to(ROOT)), "sha256": _sha256(RECOVERY_EVENTS), "committed": False},
        ],
        "committed_sources": [
            {"path": str(PARENT_MANIFEST.relative_to(ROOT)), "sha256": _sha256(PARENT_MANIFEST)},
            {"path": str(RECOVERY_MANIFEST.relative_to(ROOT)), "sha256": _sha256(RECOVERY_MANIFEST)},
            {"path": str(EXECUTED_MEASUREMENT_CONTRACT.relative_to(ROOT)), "sha256": _sha256(EXECUTED_MEASUREMENT_CONTRACT)},
            {"path": str(EXECUTED_EVENT_SCHEMA.relative_to(ROOT)), "sha256": _sha256(EXECUTED_EVENT_SCHEMA)},
            {"path": str(EXECUTED_FACTOR_PROJECTION.relative_to(ROOT)), "sha256": _sha256(EXECUTED_FACTOR_PROJECTION)},
            {"path": str(EXECUTED_FACTOR_REGISTRY.relative_to(ROOT)), "sha256": _sha256(EXECUTED_FACTOR_REGISTRY)},
            {"path": str(EXECUTED_REGISTRY_BUILDER.relative_to(ROOT)), "sha256": _sha256(EXECUTED_REGISTRY_BUILDER)},
        ],
        "parent_events": parent_events,
        "recovery_events": recovery_events,
        "cases": cases,
        "integrity": {
            "parent_event_count": 25,
            "recovery_event_count": 7,
            "corrected_case_count": 25,
            "unique_corrected_cases": len({case["case_id"] for case in cases}),
            "bundle_payload_sha256": hashlib.sha256(_canonical(cases)).hexdigest(),
        },
    }


def main() -> None:
    document = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"range-pilot publication bundle: {len(document['cases'])} cases")


if __name__ == "__main__":
    main()

"""Classify the five saved Bosch profiles with incomplete measurements."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

import traveler_metrics as tm


ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "evidence/bosch/range_pilot/source_bundle.json"
MANIFEST = ROOT / "pattern_bosch_range_pilot_design.json"
CHECKPOINTS = ROOT / "evidence/bosch/unavailable_profile_checkpoints"
OUTPUT = ROOT / "evidence/bosch/pattern_bosch_unavailable_profile_review.json"
CASE_IDS = (
    "270ed2834457ec9c",
    "fed102f8549822b8",
    "b88f0c3e7a5e9bfb",
    "3ce6823a82555ae4",
    "031eff54b2d11a1a",
)
ETCH_METRICS = (
    "etch_depth",
    "etch_cd_top",
    "etch_cd_middle",
    "etch_cd_bottom",
    "etch_minimum_cd",
    "etch_maximum_cd_error",
    "etch_sidewall_angle",
    "etch_bow",
    "etch_scallop_rms",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def components(node_count: int, lines: np.ndarray) -> int:
    parent = list(range(node_count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for first, second in lines:
        first_root = find(int(first))
        second_root = find(int(second))
        if first_root != second_root:
            parent[second_root] = first_root
    return len({find(index) for index in range(node_count)})


def classification(case_id: str, legacy: dict) -> tuple[str, str, str]:
    if case_id in {"fed102f8549822b8", "b88f0c3e7a5e9bfb"}:
        assert legacy["state"] == "extractor_domain_failure"
        return (
            "extractor_out_of_domain",
            "configured_search_window_exceeded",
            "confirmed",
        )
    if case_id in {"270ed2834457ec9c", "031eff54b2d11a1a"}:
        assert legacy["state"] == "valid_categorical_modeled_state"
        return (
            "full_width_measurement_unavailable_one_sided",
            "modeled_surface_cause_unresolved",
            "unresolved",
        )
    assert case_id == "3ce6823a82555ae4"
    assert legacy["state"] == "out_of_scope_region"
    return (
        "via_reference_surface_absent",
        "modeled_surface_cause_unresolved",
        "unresolved",
    )


def build() -> dict:
    bundle = json.loads(BUNDLE.read_text())
    manifest = json.loads(MANIFEST.read_text())
    cases_by_id = {case["case_id"]: case for case in bundle["cases"]}
    groups = {
        "parent_events": bundle["parent_events"],
        "recovery_events": bundle["recovery_events"],
    }
    half_extent = 0.5 * manifest["geometry"]["x_extent"]
    opening_cd = manifest["comparison_context"]["opening_cd"]
    domain_bounds = (-half_extent, half_extent)
    legacy_search_bounds = (-opening_cd, opening_cd)
    reviewed = []

    for case_id in CASE_IDS:
        case = cases_by_id[case_id]
        selected = case["selected_event"]
        event = groups[selected["group"]][selected["index"]]
        source_name = Path(case["profile"]["native_path"]).name
        checkpoint = CHECKPOINTS / source_name
        if digest(checkpoint) != case["profile"]["native_sha256"]:
            raise ValueError(f"checkpoint hash differs for {case_id}")
        data = np.load(checkpoint, allow_pickle=False)
        nodes = data["silicon_nodes"]
        lines = data["silicon_lines"]
        grid_delta = float(data["grid_delta"])
        common = {
            "nodes": nodes,
            "lines": lines,
            "surface_y": 0.0,
            "target_cd": opening_cd,
            "domain_x_bounds": domain_bounds,
            "grid_delta": grid_delta,
        }
        legacy = tm.measure_full_via_profile_2d(
            **common,
            search_x_bounds=legacy_search_bounds,
        )
        full = tm.measure_full_via_profile_2d(**common)
        availability, cause, cause_status = classification(case_id, legacy)
        permitted = {
            "extractor_out_of_domain": (
                "Both signed wall intersections exist outside the old configured search window."
            ),
            "full_width_measurement_unavailable_one_sided": (
                "The saved full-domain surface provides only one wall at the declared sample heights, so full-width metrics are unavailable."
            ),
            "via_reference_surface_absent": (
                "The saved silicon surface does not intersect the declared wafer surface, so via measurements referenced to that surface are unavailable."
            ),
        }[availability]
        reviewed.append({
            "case_id": case_id,
            "event_source": {
                "path": str(BUNDLE.relative_to(ROOT)),
                "selector": f"/{selected['group']}/{selected['index']}",
                "event_hash": event["event_hash"],
            },
            "checkpoint": {
                "path": str(checkpoint.relative_to(ROOT)),
                "sha256": digest(checkpoint),
                "surface_sha256": case["profile"]["surface_sha256"],
            },
            "numerical_profile": {
                "grid_delta": grid_delta,
                "rays_per_point": int(data["rays_per_point"]),
                "completed_cycle": int(data["final_completed_cycle"]),
                "qualified": False,
            },
            "measurement_context": {
                "material": "silicon",
                "declared_hole_shape": manifest["geometry"]["hole_shape"],
                "domain_x_bounds": list(domain_bounds),
                "declared_surface_y": 0.0,
                "surface_source": {
                    "path": str(MANIFEST.relative_to(ROOT)),
                    "selector": "/geometry",
                    "sha256": digest(MANIFEST),
                },
                "legacy_extractor": {
                    "path": "traveler_metrics.py",
                    "symbol": "quarter_via_radius_at_y",
                    "geometry_assumption": "positive-x wall mirrored about x=0",
                    "search_x_bounds": [0.0, opening_cd],
                },
                "full_geometry_extractor": {
                    "path": "traveler_metrics.py",
                    "symbol": "measure_full_via_profile_2d",
                    "sha256": digest(ROOT / "traveler_metrics.py"),
                },
            },
            "topology_diagnostics": {
                "silicon_component_count": components(len(nodes), lines),
                "domain_boundary_contact": {
                    "left": bool(np.any(np.isclose(nodes[:, 0], domain_bounds[0]))),
                    "right": bool(np.any(np.isclose(nodes[:, 0], domain_bounds[1]))),
                },
            },
            "legacy_search_review": legacy,
            "full_geometry_review": full,
            "availability_class": availability,
            "cause_class": cause,
            "cause_status": cause_status,
            "affected_metric_ids": list(ETCH_METRICS),
            "unaffected_metric_ids": [],
            "physical_interpretation": "unresolved",
            "permitted_claim": permitted,
            "prohibited_claims": [
                "physical process failure",
                "failure-boundary location",
                "grid convergence",
                "product acceptance",
            ],
        })

    return {
        "schema_version": 1,
        "scope": "Derived review of five saved Bosch profiles; no simulation rerun.",
        "highest_supported_claim": (
            "Two missing results came from the old search window. Two saved surfaces provide only one wall at the requested heights. One saved surface does not intersect the declared wafer surface. Physical causes and numerical convergence remain unresolved."
        ),
        "sources": [
            {"path": str(BUNDLE.relative_to(ROOT)), "sha256": digest(BUNDLE)},
            {"path": str(MANIFEST.relative_to(ROOT)), "sha256": digest(MANIFEST)},
            {"path": "traveler_metrics.py", "sha256": digest(ROOT / "traveler_metrics.py")},
        ],
        "cases": reviewed,
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"unavailable Bosch profiles reviewed: {len(document['cases'])}")


if __name__ == "__main__":
    main()

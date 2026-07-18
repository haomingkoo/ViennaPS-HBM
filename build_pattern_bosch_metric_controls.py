"""Build synthetic controls for the mask and Bosch geometry measurements."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

import traveler_metrics as tm


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "evidence/bosch/pattern_bosch_metric_controls.json"


def digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def wall(radius_fn, *, depth: float = 1.0, count: int = 401):
    fractions = np.linspace(0.0, 1.0, count)
    nodes = np.column_stack(
        ([radius_fn(fraction) for fraction in fractions], -depth * fractions)
    )
    lines = np.column_stack((np.arange(count - 1), np.arange(1, count)))
    return nodes, lines


def full_via_surface(left_fn, right_fn, *, depth: float = 1.0, count: int = 401):
    fractions = np.linspace(0.0, 1.0, count)
    left = np.column_stack(
        ([left_fn(fraction) for fraction in fractions], -depth * fractions)
    )
    right = np.column_stack(
        ([right_fn(fraction) for fraction in fractions], -depth * fractions)
    )[::-1]
    nodes = np.vstack((left, right))
    lines = np.column_stack((np.arange(len(nodes) - 1), np.arange(1, len(nodes))))
    return nodes, lines


def full_profile_control(case_id: str, nodes, lines, *, search_bounds=None) -> dict:
    result = tm.measure_full_via_profile_2d(
        nodes,
        lines,
        surface_y=0.0,
        target_cd=0.30,
        domain_x_bounds=(-0.5, 0.5),
        search_x_bounds=search_bounds,
        grid_delta=0.01,
    )
    result["diagnostics"].pop("sample_records")
    return {"id": case_id, "result": result}


def etch_case(case_id: str, radius_fn, *, depth: float = 1.0) -> dict:
    nodes, lines = wall(radius_fn, depth=depth)
    raw = tm.etch_profile_metrics_2d(
        nodes,
        lines,
        surface_y=0.0,
        floor_y=-depth,
        target_cd=0.30,
    )
    keys = (
        "depth",
        "cd_top",
        "cd_middle",
        "cd_bottom",
        "cd_min",
        "cd_max",
        "max_cd_error",
        "sidewall_angle_deg",
        "max_bow",
        "scallop_rms",
    )
    return {
        "id": case_id,
        "step": "bosch_etch",
        "metrics": {key: raw[key] for key in keys},
    }


def mask_case(case_id: str, radius_fn, *, height: float = 0.30) -> dict:
    nodes, lines = wall(radius_fn, depth=-height)
    raw = tm.pattern_metrics_2d(
        nodes,
        lines,
        surface_y=0.0,
        target_cd=0.30,
        target_mask_height=0.30,
    )
    keys = (
        "opening_cd_bottom",
        "opening_cd_middle",
        "opening_cd_top",
        "mask_height",
        "mask_sidewall_angle_deg",
    )
    return {"id": case_id, "step": "mask", "metrics": {key: raw[key] for key in keys}}


def build() -> dict:
    cases = [
        mask_case("mask_straight", lambda _: 0.15),
        mask_case("mask_short", lambda _: 0.15, height=0.20),
        mask_case("mask_tapered", lambda fraction: 0.15 + 0.02 * fraction),
        etch_case("etch_straight", lambda _: 0.15),
        etch_case("etch_shallow", lambda _: 0.15, depth=0.80),
        etch_case("etch_tapered", lambda fraction: 0.16 - 0.04 * fraction),
        etch_case(
            "etch_bowed",
            lambda fraction: 0.15 + 0.02 * math.sin(math.pi * fraction),
        ),
        etch_case(
            "etch_narrow_neck",
            lambda fraction: 0.15 - 0.04 * math.exp(-(((fraction - 0.50) / 0.10) ** 2)),
        ),
        etch_case(
            "etch_scalloped",
            lambda fraction: 0.15 + 0.005 * math.sin(12 * math.pi * fraction),
        ),
    ]
    by_id = {case["id"]: case["metrics"] for case in cases}
    checks = {
        "mask_taper_changes_top_vs_bottom_width": (
            by_id["mask_tapered"]["opening_cd_top"]
            > by_id["mask_tapered"]["opening_cd_bottom"]
        ),
        "short_mask_changes_height": (
            by_id["mask_short"]["mask_height"] < by_id["mask_straight"]["mask_height"]
        ),
        "shallow_case_changes_depth": (
            by_id["etch_shallow"]["depth"] < by_id["etch_straight"]["depth"]
        ),
        "taper_changes_top_vs_bottom_width": (
            by_id["etch_tapered"]["cd_top"] > by_id["etch_tapered"]["cd_bottom"]
        ),
        "bow_exceeds_straight_bow": (
            by_id["etch_bowed"]["max_bow"] > by_id["etch_straight"]["max_bow"]
        ),
        "neck_reduces_minimum_width": (
            by_id["etch_narrow_neck"]["cd_min"] < by_id["etch_straight"]["cd_min"]
        ),
        "scallops_increase_residual": (
            by_id["etch_scalloped"]["scallop_rms"]
            > by_id["etch_straight"]["scallop_rms"]
        ),
    }
    assert all(checks.values())
    full_nodes, full_lines = full_via_surface(lambda _: -0.15, lambda _: 0.15)
    wide_nodes, wide_lines = full_via_surface(lambda _: -0.40, lambda _: 0.40)
    one_wall_nodes, one_wall_lines = wall(lambda _: -0.15)
    one_wall_nodes = np.vstack((one_wall_nodes, [0.0, -1.0]))
    one_wall_lines = np.vstack((
        one_wall_lines,
        [len(one_wall_nodes) - 2, len(one_wall_nodes) - 1],
    ))
    absent_nodes = full_nodes.copy()
    absent_nodes[:, 1] -= 2.0
    narrow_nodes, narrow_lines = full_via_surface(
        lambda _: -0.009, lambda _: 0.009
    )
    resolved_neck_nodes, resolved_neck_lines = full_via_surface(
        lambda _: -0.015, lambda _: 0.015
    )
    full_profile_controls = [
        full_profile_control("full_straight", full_nodes, full_lines),
        full_profile_control("full_wide", wide_nodes, wide_lines),
        full_profile_control(
            "full_wide_legacy_window",
            wide_nodes,
            wide_lines,
            search_bounds=(-0.30, 0.30),
        ),
        full_profile_control("full_one_wall", one_wall_nodes, one_wall_lines),
        full_profile_control("declared_surface_absent", absent_nodes, full_lines),
        full_profile_control("two_cell_neck", narrow_nodes, narrow_lines),
        full_profile_control(
            "three_cell_neck", resolved_neck_nodes, resolved_neck_lines
        ),
    ]
    expected_states = {
        "full_straight": "complete",
        "full_wide": "complete",
        "full_wide_legacy_window": "extractor_domain_failure",
        "full_one_wall": "valid_categorical_modeled_state",
        "declared_surface_absent": "out_of_scope_region",
        "two_cell_neck": "insufficient_grid_representation",
        "three_cell_neck": "complete",
    }
    for control in full_profile_controls:
        assert control["result"]["state"] == expected_states[control["id"]]
    return {
        "schema_version": 2,
        "scope": "Synthetic geometry controls for measurement code; not simulated process outcomes.",
        "sources": [
            {"path": path, "sha256": digest(path)}
            for path in (
                "build_pattern_bosch_metric_controls.py",
                "traveler_metrics.py",
            )
        ],
        "cases": cases,
        "full_profile_controls": full_profile_controls,
        "checks": checks,
        "claim": (
            "The legacy extractors respond to the large controlled contrasts. The full-via wrapper distinguishes complete, out-of-domain, one-wall, absent-surface, and under-resolved states, with availability bracketed between two and three grid cells."
        ),
        "does_not_prove": "Continuous-metric precision, numerical stability, physical calibration, or a process recipe.",
    }


def main() -> None:
    document = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"mask/Bosch metric controls: {len(document['cases'])} cases")


if __name__ == "__main__":
    main()

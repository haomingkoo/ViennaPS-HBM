"""Audit regional Cu-fill kinematics on the completed v2 coefficient screen."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import review_copper_fill_access_surface as access
import review_copper_fill_boundary_refinement as boundary
import traveler_metrics as tm


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_copper_fill_boundary_refinement_v2_manifest.json"
)
DEFAULT_ROWS = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_boundary_refinement_v2_rows.jsonl"
)
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_regional_kinematics_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_regional_kinematics_review.md"
)

COMMON_TIME = 0.75
X_ENVELOPE_PAD = 0.02
Y_ENVELOPE_PAD = 0.03
WIDTH_SAMPLE_COUNT = 31
REGION_NAMES = ("floor", "lower_wall", "mid_wall", "upper_wall", "field")
REQUIRED_SNAPSHOT_KEYS = {
    "elapsed",
    "nodes",
    "lines",
    "mesh_surface_stage",
    "diagnostic_surface_stage",
    "diagnostic_relative_balance_error",
    "diagnostic_coordinates",
    "diagnostic_material_ids",
    "diagnostic_suppressor_flux",
    "diagnostic_coverage",
    "diagnostic_velocity",
    "diagnostic_adsorption_term",
    "diagnostic_deactivation_term",
}


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _reference_geometry(reference):
    field_y = float(reference["field_y"])
    floor_y = float(reference["floor_y"])
    x_lo, x_hi = map(float, reference["via_x_bounds"])
    height = field_y - floor_y
    half_width = 0.5 * (x_hi - x_lo)
    if height <= 0.0 or half_width <= 0.0:
        raise ValueError("reference H and a must be positive")
    return {
        "field_y": field_y,
        "floor_y": floor_y,
        "x_lo": x_lo,
        "x_hi": x_hi,
        "center_x": 0.5 * (x_lo + x_hi),
        "H": height,
        "a": half_width,
        "nominal_threshold_H_over_a": height / half_width,
    }


def _mean(values, mask):
    return float(np.mean(values[mask])) if np.any(mask) else None


def region_statistics(coordinates, flux, coverage, velocity, reference):
    """Return means in the frozen, predeclared spatial regions."""
    coordinates = np.asarray(coordinates, dtype=float)
    arrays = {
        "suppressor_flux": np.asarray(flux, dtype=float),
        "coverage": np.asarray(coverage, dtype=float),
        "normal_velocity": np.asarray(velocity, dtype=float),
    }
    if coordinates.ndim != 2 or coordinates.shape[1] < 2:
        raise ValueError("diagnostic_coordinates must be an Nx2-or-greater array")
    count = len(coordinates)
    if any(values.shape != (count,) for values in arrays.values()):
        raise ValueError("diagnostic arrays do not align with coordinates")
    if not np.all(np.isfinite(coordinates)) or any(
        not np.all(np.isfinite(values)) for values in arrays.values()
    ):
        raise ValueError("diagnostic arrays contain nonfinite values")

    geometry = _reference_geometry(reference)
    x = coordinates[:, 0] - geometry["center_x"]
    y = coordinates[:, 1]
    absolute_x = np.abs(x)
    floor_y = geometry["floor_y"]
    field_y = geometry["field_y"]
    height = geometry["H"]
    half_width = geometry["a"]
    envelope = (
        (coordinates[:, 0] >= geometry["x_lo"] - X_ENVELOPE_PAD)
        & (coordinates[:, 0] <= geometry["x_hi"] + X_ENVELOPE_PAD)
        & (y >= floor_y - Y_ENVELOPE_PAD)
        & (y <= field_y + Y_ENVELOPE_PAD)
    )
    masks = {
        "floor": envelope & (y <= floor_y + 0.04) & (absolute_x <= 0.7 * half_width),
        "lower_wall": (
            envelope
            & (y >= floor_y + 0.15 * height)
            & (y < floor_y + 0.45 * height)
            & (absolute_x >= 0.65 * half_width)
        ),
        "mid_wall": (
            envelope
            & (y >= floor_y + 0.45 * height)
            & (y < floor_y + 0.70 * height)
            & (absolute_x >= 0.65 * half_width)
        ),
        "upper_wall": (
            envelope
            & (y >= floor_y + 0.70 * height)
            & (y < floor_y + 0.95 * height)
            & (absolute_x >= 0.65 * half_width)
        ),
        "field": (
            envelope
            & (y >= field_y - Y_ENVELOPE_PAD)
            & (absolute_x >= 0.65 * half_width)
        ),
    }
    return {
        name: {
            "point_count": int(np.count_nonzero(mask)),
            **{
                f"{quantity}_mean": _mean(values, mask)
                for quantity, values in arrays.items()
            },
        }
        for name, mask in masks.items()
    }


def floor_lower_ratios(regions):
    ratios = {}
    for quantity in ("suppressor_flux", "coverage", "normal_velocity"):
        floor = regions["floor"][f"{quantity}_mean"]
        lower = regions["lower_wall"][f"{quantity}_mean"]
        ratios[quantity] = (
            float(floor / lower)
            if floor is not None and lower not in (None, 0.0)
            else None
        )
    return ratios


def dynamic_width_threshold(nodes, lines, reference, grid_delta):
    """Measure the post-checkpoint cavity; never interpolate missing crossings."""
    geometry = _reference_geometry(reference)
    nodes = np.asarray(nodes, dtype=float)
    lines = np.asarray(lines, dtype=int)
    sample_ys = np.linspace(
        geometry["floor_y"] + 0.15 * geometry["H"],
        geometry["floor_y"] + 0.45 * geometry["H"],
        WIDTH_SAMPLE_COUNT,
    )
    x_bounds = (
        geometry["x_lo"] - X_ENVELOPE_PAD,
        geometry["x_hi"] + X_ENVELOPE_PAD,
    )
    left_widths = []
    right_widths = []
    missing = []
    for sample_y in sample_ys:
        intersections = tm.line_intersections_at_y(
            nodes, lines, float(sample_y), x_bounds=x_bounds
        )
        left = intersections[intersections < geometry["center_x"] - 1e-10]
        right = intersections[intersections > geometry["center_x"] + 1e-10]
        if not len(left) or not len(right):
            missing.append(float(sample_y))
            continue
        left_widths.append(float(geometry["center_x"] - np.max(left)))
        right_widths.append(float(np.min(right) - geometry["center_x"]))

    center_intersections = tm.line_intersections_at_x(
        nodes,
        lines,
        geometry["center_x"],
        y_bounds=(
            geometry["floor_y"] - Y_ENVELOPE_PAD,
            geometry["field_y"] + Y_ENVELOPE_PAD,
        ),
    )
    if missing or not len(center_intersections):
        return {
            "measurable": False,
            "method": "31 fixed lower-band horizontal intersections plus the lowest centerline intersection",
            "missing_horizontal_sample_ys": missing,
            "centerline_intersection_count": int(len(center_intersections)),
            "left_half_width": None,
            "right_half_width": None,
            "conservative_half_width": None,
            "remaining_axial_distance": None,
            "left_threshold": None,
            "right_threshold": None,
            "conservative_threshold": None,
            "linear_detection_limit": float(grid_delta),
            "at_or_below_detection_limit": None,
        }

    left_width = min(left_widths)
    right_width = min(right_widths)
    conservative_width = min(left_width, right_width)
    deepest_center_y = float(np.min(center_intersections))
    remaining = max(0.0, geometry["field_y"] - deepest_center_y)
    return {
        "measurable": True,
        "method": "31 fixed lower-band horizontal intersections; nearest left/right crossing at each y; side minima and their conservative minimum; lowest centerline crossing",
        "missing_horizontal_sample_ys": [],
        "centerline_intersection_count": int(len(center_intersections)),
        "left_half_width": left_width,
        "right_half_width": right_width,
        "conservative_half_width": conservative_width,
        "remaining_axial_distance": remaining,
        "left_threshold": remaining / left_width,
        "right_threshold": remaining / right_width,
        "conservative_threshold": remaining / conservative_width,
        "linear_detection_limit": float(grid_delta),
        "at_or_below_detection_limit": bool(
            conservative_width <= float(grid_delta) + 1e-12
        ),
    }


def _scalar_text(array):
    values = np.asarray(array).reshape(-1)
    return str(values[0]) if len(values) == 1 else None


def snapshot_profile(path, checkpoint, reference, grid_delta):
    path = Path(path)
    if not path.exists():
        return None, [f"saved diagnostic snapshot is missing: {path}"]
    try:
        with np.load(path, allow_pickle=False) as snapshot:
            missing = sorted(REQUIRED_SNAPSHOT_KEYS - set(snapshot.files))
            if missing:
                return None, [f"snapshot lacks required keys: {missing}"]
            elapsed = np.asarray(snapshot["elapsed"], dtype=float).reshape(-1)
            if len(elapsed) != 1 or not np.isfinite(elapsed[0]):
                return None, ["snapshot elapsed is not one finite scalar"]
            coordinates = np.asarray(snapshot["diagnostic_coordinates"], dtype=float)
            flux = np.asarray(snapshot["diagnostic_suppressor_flux"], dtype=float)
            coverage = np.asarray(snapshot["diagnostic_coverage"], dtype=float)
            velocity = np.asarray(snapshot["diagnostic_velocity"], dtype=float)
            nodes = np.asarray(snapshot["nodes"], dtype=float)
            lines = np.asarray(snapshot["lines"], dtype=int)
            diagnostic_stage = _scalar_text(snapshot["diagnostic_surface_stage"])
            mesh_stage = _scalar_text(snapshot["mesh_surface_stage"])
    except Exception as error:
        return None, [f"cannot read saved diagnostic snapshot: {error!r}"]

    errors = []
    if not math.isclose(
        float(elapsed[0]), float(checkpoint["elapsed"]), rel_tol=0.0, abs_tol=1e-12
    ):
        errors.append("snapshot elapsed differs from trajectory checkpoint")
    if diagnostic_stage != "pre-final-advection surface":
        errors.append("unexpected diagnostic surface stage")
    if mesh_stage != "post-checkpoint advection":
        errors.append("unexpected mesh surface stage")
    try:
        regions = region_statistics(coordinates, flux, coverage, velocity, reference)
        dynamic = dynamic_width_threshold(nodes, lines, reference, grid_delta)
    except Exception as error:
        return None, [*errors, f"invalid snapshot arrays: {error}"]
    return {
        "checkpoint": int(checkpoint["checkpoint"]),
        "elapsed": float(checkpoint["elapsed"]),
        "snapshot_path": str(path),
        "diagnostic_surface_stage": diagnostic_stage,
        "mesh_surface_stage": mesh_stage,
        "regions": regions,
        "floor_to_lower_ratios": floor_lower_ratios(regions),
        "dynamic_width_threshold": dynamic,
    }, errors


def common_time_metrics(row, common_time=COMMON_TIME):
    matches = [
        checkpoint
        for checkpoint in row.get("trajectory", [])
        if _number(checkpoint.get("elapsed"))
        and math.isclose(
            float(checkpoint["elapsed"]), common_time, rel_tol=0.0, abs_tol=1e-10
        )
    ]
    if len(matches) != 1:
        return None, [f"expected one trajectory checkpoint at t={common_time:g}"]
    checkpoint = matches[0]
    if boundary._hard_failures(checkpoint):
        return None, [f"common-time checkpoint t={common_time:g} is a hard failure"]
    topology = checkpoint.get("topology", {})
    initial = row.get("reference", {}).get("initial_topology", {})
    required = {
        "initial depth": initial.get("open_void_depth"),
        "initial area": initial.get("remaining_void_area"),
        "initial mouth": initial.get("mouth_aperture"),
        "depth": topology.get("open_void_depth"),
        "area": topology.get("remaining_void_area"),
        "mouth": topology.get("mouth_aperture"),
        "fill": topology.get("fill_fraction"),
    }
    missing = [name for name, value in required.items() if not _number(value)]
    if missing:
        return None, [f"common-time metrics are missing/nonfinite: {missing}"]
    elapsed = float(checkpoint["elapsed"])
    depth_advance = float(required["initial depth"] - required["depth"])
    area_reduction = float(required["initial area"] - required["area"])
    mouth_loss = float(required["initial mouth"] - required["mouth"])
    fill_fraction = float(required["fill"])
    return {
        "checkpoint": int(checkpoint["checkpoint"]),
        "elapsed": elapsed,
        "depth_advance": depth_advance,
        "area_reduction": area_reduction,
        "mouth_aperture": float(required["mouth"]),
        "mouth_loss": mouth_loss,
        "fill_fraction": fill_fraction,
        "depth_advance_rate": depth_advance / elapsed,
        "area_reduction_rate": area_reduction / elapsed,
        "mouth_loss_rate": mouth_loss / elapsed,
        "fill_fraction_rate": fill_fraction / elapsed,
    }, []


def classify_coefficient_screen(initial_velocity_ratios, threshold, va, vs):
    ratios = [float(value) for value in initial_velocity_ratios if _number(value)]
    all_at_most_one = bool(ratios and max(ratios) <= 1.0 + 1e-12)
    shortfall_factor = float(threshold) / max(ratios) if ratios and max(ratios) > 0 else None
    far_below = bool(shortfall_factor is not None and shortfall_factor >= 2.0)
    rejected = all_at_most_one and far_below
    coefficient_ceiling = float(va / vs) if vs > 0.0 else None
    return {
        "classification": (
            "coefficient_screen_rejected"
            if rejected
            else "coefficient_screen_not_rejected"
        ),
        "all_initial_floor_lower_velocity_ratios_at_most_one": all_at_most_one,
        "far_below_nominal_threshold": far_below,
        "observed_ratio_min": min(ratios) if ratios else None,
        "observed_ratio_max": max(ratios) if ratios else None,
        "nominal_threshold_H_over_a": float(threshold),
        "shortfall_factor": shortfall_factor,
        "active_deposition_rate_Va": float(va),
        "suppressed_deposition_rate_Vs": float(vs),
        "va_to_vs_ceiling": coefficient_ceiling,
        "ordering_constrained_velocity_ratio_ceiling": (
            1.0 if all_at_most_one else None
        ),
        "ordering_constrained_ceiling_below_nominal_threshold": bool(
            all_at_most_one and 1.0 < threshold
        ),
        "velocity_law": "V(theta)=Va*(1-theta)+Vs*theta, 0<=theta<=1",
        "ordering_no_go": bool(rejected),
        "coefficient_ceiling_below_nominal_threshold": bool(
            coefficient_ceiling is not None and coefficient_ceiling < threshold
        ),
        "reason": (
            "Every initial floor/lower normal-velocity ratio is <=1 and the "
            f"best ratio is {shortfall_factor:.4g}x below H/a; the observed "
            "coverage ordering cannot be reversed by active/suppressed-rate "
            "scaling."
            if rejected
            else "The predeclared direction-and-shortfall rejection rule is not met."
        ),
    }


def _select_current_rows(manifest, rows, fingerprint):
    selected = []
    for expected in access.expand_cases(manifest, fingerprint):
        matches = [
            row
            for row in rows
            if row.get("design") == expected["design"]
            and row.get("rng_seed") == expected["rng_seed"]
            and row.get("ok")
            and not access.validate_attempt(row, expected, fingerprint)
        ]
        if len(matches) == 1:
            selected.append(matches[0])
    return selected


def _event_record(row):
    event = next(
        (checkpoint for checkpoint in row["trajectory"] if boundary._hard_failures(checkpoint)),
        None,
    )
    if event is None:
        return {"hard_failure": False}
    topology = event.get("topology", {})
    transition = event.get("topology_transition", {})
    closed_count = int(topology.get("closed_void_count", 0) or 0)
    mouth_pinch = bool(topology.get("mouth_pinched_off", False))
    return {
        "hard_failure": True,
        "elapsed": float(event["elapsed"]),
        "classification": transition.get("classification"),
        "internal_closed_void": bool(closed_count and not mouth_pinch),
        "mouth_pinch": mouth_pinch,
        "main_mouth_open": bool(topology.get("mouth_open", False)),
        "closed_void_area": topology.get("closed_void_area"),
        "closed_void_width": topology.get("maximum_void_width"),
        "closed_void_height": topology.get("maximum_void_height"),
        "closed_void_aspect_ratio": topology.get("maximum_void_aspect_ratio"),
        "tail_width": transition.get("disappearing_tail_max_width"),
        "tail_height": transition.get("disappearing_tail_height"),
        "tail_aspect_ratio": transition.get("disappearing_tail_aspect_ratio"),
        "open_void_depth_drop": transition.get("observed_open_void_depth_drop"),
        "closure_width_bound": transition.get("closure_width_bound"),
    }


def _stats(values):
    return boundary.stats(value for value in values if _number(value))


def _event_summary(events, grid_delta):
    hard = [event for event in events if event["hard_failure"]]
    closed = [event for event in hard if event["internal_closed_void"]]
    tails = [
        event
        for event in hard
        if event["classification"] == "unresolved_narrow_tail_merger"
    ]
    return {
        "hard_failure_count": len(hard),
        "internal_closed_void_count": len(closed),
        "mouth_pinch_count": sum(event["mouth_pinch"] for event in hard),
        "main_mouth_open_count": sum(event["main_mouth_open"] for event in hard),
        "classification_counts": dict(sorted(Counter(
            event["classification"] for event in hard
        ).items())),
        "linear_detection_limit": float(grid_delta),
        "area_detection_limit": float(grid_delta) ** 2,
        "closed_void_area": _stats(event["closed_void_area"] for event in closed),
        "closed_void_width": _stats(event["closed_void_width"] for event in closed),
        "closed_void_height": _stats(event["closed_void_height"] for event in closed),
        "closed_void_aspect_ratio": _stats(
            event["closed_void_aspect_ratio"] for event in closed
        ),
        "closed_void_width_at_or_below_detection_count": sum(
            _number(event["closed_void_width"])
            and float(event["closed_void_width"]) <= grid_delta + 1e-12
            for event in closed
        ),
        "unresolved_tail_width": _stats(event["tail_width"] for event in tails),
        "unresolved_tail_height": _stats(event["tail_height"] for event in tails),
        "unresolved_tail_aspect_ratio": _stats(
            event["tail_aspect_ratio"] for event in tails
        ),
        "unresolved_tail_width_at_or_below_detection_count": sum(
            _number(event["tail_width"])
            and float(event["tail_width"]) <= grid_delta + 1e-12
            for event in tails
        ),
        "open_void_depth_drop": _stats(event["open_void_depth_drop"] for event in hard),
        "closure_width_bound": _stats(event["closure_width_bound"] for event in hard),
    }


def _design_summaries(case_records):
    grouped = defaultdict(list)
    for record in case_records:
        grouped[record["design"]].append(record)
    summaries = []
    for coverage_lambda in boundary.LAMBDA_LEVELS:
        for sticking in boundary.STICKING_LEVELS:
            design = boundary.expected_design_name(coverage_lambda, sticking)
            records = grouped[design]
            ratios = {
                quantity: _stats(
                    record["initial_snapshot"]["floor_to_lower_ratios"][quantity]
                    for record in records
                )
                for quantity in ("suppressor_flux", "coverage", "normal_velocity")
            }
            common = {
                metric: _stats(record["common_time"][metric] for record in records)
                for metric in (
                    "depth_advance",
                    "area_reduction",
                    "mouth_aperture",
                    "mouth_loss",
                    "fill_fraction",
                    "depth_advance_rate",
                    "area_reduction_rate",
                    "mouth_loss_rate",
                    "fill_fraction_rate",
                )
            }
            summaries.append({
                "design": design,
                "coverage_lambda": coverage_lambda,
                "sticking_probability": sticking,
                "n": len(records),
                "initial_floor_to_lower_ratios": ratios,
                "common_time": COMMON_TIME,
                "common_time_metrics": common,
            })
    return summaries


AUDIT_KEYS = (
    "expected_case_count",
    "attempt_count",
    "selected_current_case_count",
    "metric_valid_case_count",
    "expected_runtime_fingerprint",
    "manifest_validation_errors",
    "parse_errors",
    "current_fingerprint_error_attempt_rows",
    "invalid_attempts",
    "invalid_metric_rows",
    "unexpected_attempt_rows",
    "duplicate_success_case_ids",
    "missing_cases",
)


def build_summary(manifest, rows, parse_errors, rows_missing, fingerprint, project_root):
    upstream = boundary.build_summary(
        manifest, rows, parse_errors, rows_missing, fingerprint
    )
    summary = {
        "status": upstream["status"],
        "campaign": manifest.get("campaign"),
        **{key: upstream[key] for key in AUDIT_KEYS},
        "snapshot_count": 0,
        "snapshot_errors": [],
        "case_records": [],
        "designs": [],
        "ranking": [],
        "ranking_policy": "none; only common-exposure and predeclared regional kinematics are reported",
        "decision": {
            "classification": "insufficient_audited_evidence",
            "reason": "The exact current 72-case audit gate has not cleared.",
        },
    }
    if upstream["status"] != "complete":
        return summary

    selected = _select_current_rows(manifest, rows, fingerprint)
    project_root = Path(project_root)
    case_records = []
    snapshot_errors = []
    snapshot_paths = set()
    nominal_thresholds = []
    events = []
    for row in selected:
        try:
            geometry = _reference_geometry(row["reference"])
            nominal_thresholds.append(geometry["nominal_threshold_H_over_a"])
        except Exception as error:
            snapshot_errors.append({
                "case_id": row.get("case_id"),
                "reasons": [f"invalid reference geometry: {error}"],
            })
            continue
        profiles = []
        for checkpoint in row["trajectory"]:
            declared = checkpoint.get("snapshot_path")
            if not declared:
                continue
            path = Path(declared)
            if not path.is_absolute():
                path = project_root / path
            duplicate = str(path) in snapshot_paths
            snapshot_paths.add(str(path))
            profile, errors = snapshot_profile(
                path, checkpoint, row["reference"], row["numerics"]["grid_delta"]
            )
            if duplicate:
                errors.append("snapshot path is reused by more than one checkpoint")
            if errors:
                snapshot_errors.append({
                    "case_id": row["case_id"],
                    "checkpoint": checkpoint["checkpoint"],
                    "reasons": errors,
                })
            if profile is not None:
                profiles.append(profile)
        common, common_errors = common_time_metrics(row)
        if not profiles:
            snapshot_errors.append({
                "case_id": row["case_id"],
                "reasons": ["case has no readable saved diagnostic snapshot"],
            })
            continue
        initial = min(profiles, key=lambda profile: profile["elapsed"])
        empty_initial = [
            name
            for name in REGION_NAMES
            if initial["regions"][name]["point_count"] == 0
        ]
        if empty_initial:
            snapshot_errors.append({
                "case_id": row["case_id"],
                "checkpoint": initial["checkpoint"],
                "reasons": [f"initial snapshot has empty regions: {empty_initial}"],
            })
        if common_errors:
            snapshot_errors.append({
                "case_id": row["case_id"],
                "reasons": common_errors,
            })
            continue
        event = _event_record(row)
        events.append(event)
        case_records.append({
            "case_id": row["case_id"],
            "design": row["design"],
            "rng_seed": row["rng_seed"],
            "initial_snapshot": initial,
            "saved_snapshots": profiles,
            "common_time": common,
            "event": event,
        })

    summary["snapshot_count"] = len(snapshot_paths)
    summary["snapshot_errors"] = snapshot_errors
    summary["case_records"] = case_records
    if snapshot_errors or len(case_records) != 72:
        summary["status"] = "incomplete_or_invalid"
        summary["decision"] = {
            "classification": "insufficient_audited_evidence",
            "reason": "Saved-snapshot or common-time audit errors block a regional conclusion.",
        }
        return summary

    threshold = nominal_thresholds[0]
    if any(not math.isclose(value, threshold, rel_tol=0.0, abs_tol=1e-12) for value in nominal_thresholds):
        summary["status"] = "incomplete_or_invalid"
        summary["snapshot_errors"] = [{
            "reasons": ["nominal H/a differs across the exact matrix"]
        }]
        return summary
    initial_ratios = [
        record["initial_snapshot"]["floor_to_lower_ratios"]["normal_velocity"]
        for record in case_records
    ]
    va = float(manifest["model"]["active_deposition_rate"])
    vs = float(manifest["model"]["suppressed_deposition_rate"])
    decision = classify_coefficient_screen(initial_ratios, threshold, va, vs)
    dynamic = [
        profile["dynamic_width_threshold"]
        for record in case_records
        for profile in record["saved_snapshots"]
    ]
    measurable = [item for item in dynamic if item["measurable"]]
    decision["dynamic_coefficient_ceiling_below_threshold_count"] = sum(
        item["conservative_threshold"] > decision["va_to_vs_ceiling"]
        for item in measurable
    )
    summary.update({
        "status": "complete",
        "nominal_geometry": {
            "H": _reference_geometry(selected[0]["reference"])["H"],
            "a": _reference_geometry(selected[0]["reference"])["a"],
            "threshold_H_over_a": threshold,
        },
        "region_definitions": {
            "analysis_envelope": "via x bounds +/-0.02 and [floor-0.03, field+0.03] in y",
            "floor": "y<=floor+0.04 and |x-center|<=0.7a",
            "lower_wall": "floor+0.15H<=y<floor+0.45H and |x-center|>=0.65a",
            "mid_wall": "floor+0.45H<=y<floor+0.70H and |x-center|>=0.65a",
            "upper_wall": "floor+0.70H<=y<floor+0.95H and |x-center|>=0.65a",
            "field": "y>=field-0.03 and |x-center|>=0.65a",
        },
        "dynamic_width_method": (
            "On the post-checkpoint mesh, sample 31 fixed y values across the "
            "lower-wall band; select the nearest crossing on each side, retain "
            "each side's minimum half-width and their minimum, and divide the "
            "field-to-lowest-centerline distance by those widths. Any missing "
            "crossing makes that snapshot unmeasurable; widths <= grid delta are "
            "reported but flagged at/below the linear detection limit."
        ),
        "dynamic_width_summary": {
            "saved_snapshot_count": len(dynamic),
            "measurable_count": len(measurable),
            "unmeasurable_count": len(dynamic) - len(measurable),
            "at_or_below_detection_limit_count": sum(
                item["at_or_below_detection_limit"] is True for item in measurable
            ),
            "left_half_width": _stats(item["left_half_width"] for item in measurable),
            "right_half_width": _stats(item["right_half_width"] for item in measurable),
            "conservative_half_width": _stats(
                item["conservative_half_width"] for item in measurable
            ),
            "remaining_axial_distance": _stats(
                item["remaining_axial_distance"] for item in measurable
            ),
            "conservative_threshold": _stats(
                item["conservative_threshold"] for item in measurable
            ),
        },
        "designs": _design_summaries(case_records),
        "event_summary": _event_summary(events, float(manifest["numerics"]["grid_delta"])),
        "algebraic_no_go": decision,
        "decision": {
            "classification": decision["classification"],
            "reason": decision["reason"],
        },
    })
    return summary


def _fmt(value, digits=5):
    if value is None:
        return "—"
    return f"{value:.{digits}g}" if isinstance(value, (int, float)) else str(value)


def markdown(summary):
    lines = [
        "# Cu-fill regional kinematics audit",
        "",
        f"Status: **{summary['status']}**. Current cases: "
        f"{summary['selected_current_case_count']}/{summary['expected_case_count']}; "
        f"saved snapshots: {summary['snapshot_count']}; snapshot errors: "
        f"{len(summary['snapshot_errors'])}.",
        "",
        "No unequal-exposure ranking is produced by this reviewer.",
        "",
    ]
    if summary["status"] != "complete":
        lines += [
            f"Decision: **{summary['decision']['classification']}** — "
            f"{summary['decision']['reason']}",
            "",
        ]
        return "\n".join(lines)
    geometry = summary["nominal_geometry"]
    dynamic = summary["dynamic_width_summary"]
    no_go = summary["algebraic_no_go"]
    lines += [
        "## Predeclared geometry",
        "",
        f"H={_fmt(geometry['H'])}, a={_fmt(geometry['a'])}, nominal "
        f"H/a={_fmt(geometry['threshold_H_over_a'])}. "
        f"Dynamic widths were measurable in {dynamic['measurable_count']}/"
        f"{dynamic['saved_snapshot_count']} saved meshes; "
        f"{dynamic['at_or_below_detection_limit_count']} were at/below grid "
        "resolution.",
        "",
        summary["dynamic_width_method"],
        "",
        "## Initial regional direction and common-time progress",
        "",
        "| λ | Sticking | Initial floor/lower flux | Coverage | Velocity | t=.75 depth | Area | Mouth | Fill | Depth rate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for design in summary["designs"]:
        ratios = design["initial_floor_to_lower_ratios"]
        common = design["common_time_metrics"]
        lines.append(
            f"| {_fmt(design['coverage_lambda'])} | "
            f"{_fmt(design['sticking_probability'])} | "
            f"{_fmt(ratios['suppressor_flux']['mean'])} | "
            f"{_fmt(ratios['coverage']['mean'])} | "
            f"{_fmt(ratios['normal_velocity']['mean'])} | "
            f"{_fmt(common['depth_advance']['mean'])} | "
            f"{_fmt(common['area_reduction']['mean'])} | "
            f"{_fmt(common['mouth_aperture']['mean'])} | "
            f"{_fmt(common['fill_fraction']['mean'])} | "
            f"{_fmt(common['depth_advance_rate']['mean'])} |"
        )
    events = summary["event_summary"]
    lines += [
        "",
        "## Failure geometry and algebraic screen",
        "",
        f"Hard failures: {events['hard_failure_count']}; internal closed voids: "
        f"{events['internal_closed_void_count']}; true mouth pinches: "
        f"{events['mouth_pinch_count']}; main mouth still open: "
        f"{events['main_mouth_open_count']}.",
        "",
        f"Va/Vs={_fmt(no_go['va_to_vs_ceiling'])}. Initial floor/lower "
        f"velocity range={_fmt(no_go['observed_ratio_min'])}–"
        f"{_fmt(no_go['observed_ratio_max'])}; nominal threshold="
        f"{_fmt(no_go['nominal_threshold_H_over_a'])}.",
        "",
        f"Decision: **{summary['decision']['classification']}** — "
        f"{summary['decision']['reason']}",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    rows, parse_errors, rows_missing = access.load_jsonl(args.rows)
    fingerprint = access.runtime_fingerprint(manifest, args.project_root)
    summary = build_summary(
        manifest, rows, parse_errors, rows_missing, fingerprint, args.project_root
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    args.markdown.write_text(markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "selected": summary["selected_current_case_count"],
        "snapshots": summary["snapshot_count"],
        "decision": summary["decision"]["classification"],
    }))


if __name__ == "__main__":
    main()

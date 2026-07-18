"""Compare a saved via profile with a teaching target."""

from __future__ import annotations

import math

import numpy as np

import traveler_metrics as tm


def floor_profile_metrics_2d(
    nodes,
    lines,
    *,
    surface_y,
    target_cd,
    grid_delta,
    center_x=0.0,
    resolution_cells=2.0,
):
    """Measure the floor over the central half of the target width."""
    if not target_cd > 0 or not grid_delta > 0 or not resolution_cells > 0:
        raise ValueError("target_cd, grid_delta, and resolution_cells must be positive")

    half_span = 0.25 * float(target_cd)
    tolerance = max(1e-12, float(grid_delta) * 1e-9)
    first_index = math.ceil((-half_span - tolerance) / grid_delta)
    last_index = math.floor((half_span + tolerance) / grid_delta)
    sample_xs = center_x + grid_delta * np.arange(first_index, last_index + 1)
    diagnostics = {
        "requested_x_bounds": [center_x - half_span, center_x + half_span],
        "sample_xs": sample_xs.tolist(),
        "sample_ys": [],
        "sample_count": int(len(sample_xs)),
        "smoothing_window_cells": 3,
    }
    if len(sample_xs) < 3:
        return {
            "state": "floor_profile_unavailable",
            "reason_codes": ["insufficient_floor_sample_columns"],
            "metrics": None,
            "diagnostics": diagnostics,
        }

    sample_ys = []
    for x in sample_xs:
        intersections = tm.line_intersections_at_x(nodes, lines, float(x))
        below_surface = intersections[intersections < surface_y - tolerance]
        if len(below_surface) != 1:
            diagnostics.update({
                "sample_ys": sample_ys,
                "failed_x": float(x),
                "failed_intersections_y": intersections.tolist(),
            })
            return {
                "state": "floor_profile_unavailable",
                "reason_codes": [
                    "floor_intersection_missing"
                    if not len(below_surface)
                    else "floor_intersection_multiple"
                ],
                "metrics": None,
                "diagnostics": diagnostics,
            }
        sample_ys.append(float(below_surface[0]))

    sample_ys = np.asarray(sample_ys, dtype=float)
    filtered_ys = np.convolve(
        np.pad(sample_ys, (1, 1), mode="edge"), np.ones(3) / 3.0, mode="valid"
    )
    flatness_pv = float(np.ptp(filtered_ys))
    center_index = int(np.argmin(np.abs(sample_xs - center_x)))
    resolution_limit = float(resolution_cells * grid_delta)
    diagnostics.update({
        "sample_ys": sample_ys.tolist(),
        "filtered_sample_xs": sample_xs.tolist(),
        "filtered_sample_ys": filtered_ys.tolist(),
    })
    return {
        "state": "complete",
        "reason_codes": [],
        "metrics": {
            "floor_flatness_pv": flatness_pv,
            "floor_horizontal_rms": float(
                np.sqrt(np.mean((filtered_ys - np.mean(filtered_ys)) ** 2))
            ),
            "floor_center_relief": float(
                0.5 * (filtered_ys[0] + filtered_ys[-1])
                - filtered_ys[center_index]
            ),
            "floor_sample_count": int(len(sample_xs)),
            "floor_flatness_cells": float(flatness_pv / grid_delta),
            "floor_resolution_cells": float(resolution_cells),
            "floor_resolution_status": (
                "resolved_nonflatness"
                if flatness_pv > resolution_limit + tolerance
                else "flat_within_resolution"
            ),
        },
        "diagnostics": diagnostics,
    }


def measure_target_via_profile_2d(
    nodes,
    lines,
    *,
    surface_y,
    target_cd,
    target_depth,
    domain_x_bounds,
    grid_delta,
    allow_partial_floor=False,
    **wall_options,
):
    """Measure walls, floor, symmetry, and error from one target profile."""
    if not target_depth > 0:
        raise ValueError("target_depth must be positive")
    result = tm.measure_full_via_profile_2d(
        nodes,
        lines,
        surface_y=surface_y,
        target_cd=target_cd,
        domain_x_bounds=domain_x_bounds,
        grid_delta=grid_delta,
        **wall_options,
    )
    if result["state"] != "complete":
        return result

    metrics = dict(result["metrics"])
    diagnostics = dict(result["diagnostics"])
    floor = floor_profile_metrics_2d(
        nodes,
        lines,
        surface_y=surface_y,
        target_cd=target_cd,
        grid_delta=grid_delta,
        center_x=wall_options.get("center_x", 0.0),
    )
    diagnostics["floor_profile"] = floor["diagnostics"]
    records = diagnostics["sample_records"]
    center_x = wall_options.get("center_x", 0.0)
    left_xs = np.asarray([record["left_wall_x"] for record in records])
    right_xs = np.asarray([record["right_wall_x"] for record in records])
    wall_offsets = np.concatenate((
        left_xs - (center_x - 0.5 * target_cd),
        right_xs - (center_x + 0.5 * target_cd),
    ))
    metrics["profile_wall_rmse"] = float(np.sqrt(np.mean(wall_offsets**2)))

    if floor["state"] != "complete":
        if not allow_partial_floor:
            return {
                "state": "valid_categorical_modeled_state",
                "reason_codes": floor["reason_codes"],
                "metrics": None,
                "diagnostics": diagnostics,
            }
        metrics.update({
            "floor_flatness_pv": None,
            "floor_horizontal_rms": None,
            "floor_center_relief": None,
            "floor_sample_count": floor["diagnostics"]["sample_count"],
            "floor_flatness_cells": None,
            "floor_resolution_cells": 2.0,
            "floor_resolution_status": "unavailable",
            "profile_symmetry_rms": None,
            "profile_floor_rmse": None,
            "profile_shape_rmse": None,
            "profile_max_deviation": None,
        })
        return {
            "state": "partial",
            "reason_codes": floor["reason_codes"],
            "metrics": metrics,
            "diagnostics": diagnostics,
        }

    metrics.update(floor["metrics"])
    floor_ys = np.asarray(floor["diagnostics"]["filtered_sample_ys"])
    centers = 0.5 * (left_xs + right_xs)
    floor_pair_offsets = 0.5 * (floor_ys - floor_ys[::-1])
    metrics["profile_symmetry_rms"] = float(math.sqrt(0.5 * (
        np.mean((centers - center_x) ** 2) + np.mean(floor_pair_offsets**2)
    )))
    floor_offsets = floor_ys - (surface_y - target_depth)
    wall_mse = float(np.mean(wall_offsets**2))
    floor_mse = float(np.mean(floor_offsets**2))
    metrics.update({
        "profile_floor_rmse": float(math.sqrt(floor_mse)),
        "profile_shape_rmse": float(math.sqrt(0.5 * (wall_mse + floor_mse))),
        "profile_max_deviation": float(max(
            np.max(np.abs(wall_offsets)), np.max(np.abs(floor_offsets))
        )),
    })
    return {
        "state": "complete",
        "reason_codes": [],
        "metrics": metrics,
        "diagnostics": diagnostics,
    }

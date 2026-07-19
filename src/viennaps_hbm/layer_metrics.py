"""Local film metrics for asymmetric full-width 2D TSV sections."""

from __future__ import annotations

import numpy as np

from . import traveler_metrics as tm


def layer_thickness_metrics_full_2d(
    inner_nodes,
    inner_lines,
    outer_nodes,
    outer_lines,
    *,
    surface_y,
    floor_y,
    via_radius,
    center_x=0.0,
    field_xs=None,
    floor_x=None,
    top_fraction=0.15,
    middle_fraction=0.50,
    lower_fraction=0.80,
    sample_count=71,
    continuity_tolerance=1e-10,
):
    """Measure film thickness and aperture on a full-width section."""
    depth = float(surface_y - floor_y)
    via_radius = float(via_radius)
    center_x = float(center_x)
    if depth <= 0.0 or via_radius <= 0.0:
        raise ValueError("surface_y, floor_y, and via_radius define an invalid via")
    if not 0 < top_fraction < middle_fraction < lower_fraction < 1:
        raise ValueError("wall fractions must satisfy 0 < top < middle < lower < 1")
    if sample_count < 8:
        raise ValueError("sample_count must be at least 8")

    if field_xs is None:
        field_xs = (
            center_x - 2.5 * via_radius,
            center_x + 2.5 * via_radius,
        )
    if len(field_xs) != 2:
        raise ValueError("field_xs must contain left and right sample positions")
    left_field_x, right_field_x = sorted(float(value) for value in field_xs)
    if not left_field_x < center_x - via_radius:
        raise ValueError("left field sample must lie outside the nominal via")
    if not right_field_x > center_x + via_radius:
        raise ValueError("right field sample must lie outside the nominal via")
    floor_x = float(center_x if floor_x is None else floor_x)

    def interface_point_at_x(x, y_hint):
        values = tm.line_intersections_at_x(inner_nodes, inner_lines, x)
        if not len(values):
            raise ValueError("inner interface lacks a required field or floor sample")
        return x, float(values[np.argmin(np.abs(values - y_hint))])

    field_points = [
        interface_point_at_x(left_field_x, surface_y),
        interface_point_at_x(right_field_x, surface_y),
    ]
    floor_point = interface_point_at_x(floor_x, floor_y)

    fractions = np.linspace(top_fraction, lower_fraction, sample_count)
    x_bounds = (
        center_x - 2.0 * via_radius,
        center_x + 2.0 * via_radius,
    )
    left_wall_points = []
    right_wall_points = []
    apertures = []
    aperture_valid = []
    for fraction in fractions:
        y = surface_y - fraction * depth
        inner_xs = tm.line_intersections_at_y(
            inner_nodes, inner_lines, y, x_bounds=x_bounds
        )
        if len(inner_xs) < 2:
            raise ValueError("inner interface is not a resolved full-width via")
        left_wall_points.append((float(inner_xs.min()), y))
        right_wall_points.append((float(inner_xs.max()), y))

        outer_xs = tm.line_intersections_at_y(
            outer_nodes, outer_lines, y, x_bounds=x_bounds
        )
        valid = len(outer_xs) >= 2 and float(outer_xs.min()) < float(outer_xs.max())
        apertures.append(float(outer_xs.max() - outer_xs.min()) if valid else 0.0)
        aperture_valid.append(valid)

    left_wall = tm.point_to_polyline_distances(
        left_wall_points, outer_nodes, outer_lines
    )
    right_wall = tm.point_to_polyline_distances(
        right_wall_points, outer_nodes, outer_lines
    )
    left_field, right_field = tm.point_to_polyline_distances(
        field_points, outer_nodes, outer_lines
    )
    floor = float(
        tm.point_to_polyline_distances([floor_point], outer_nodes, outer_lines)[0]
    )
    field_reference = float(max(left_field, right_field))
    wall_minima = np.minimum(left_wall, right_wall)
    local = np.r_[left_wall, right_wall, left_field, right_field, floor]
    apertures = np.asarray(apertures)
    top_index = 0
    middle_index = int(np.argmin(np.abs(fractions - middle_fraction)))
    lower_index = len(fractions) - 1
    component_count = len(tm.component_summaries(outer_nodes, outer_lines))
    continuous = bool(
        np.all(np.isfinite(local))
        and np.min(local) > continuity_tolerance
        and component_count == 1
    )

    def ratio(value):
        return float(value / field_reference) if field_reference > 0.0 else None

    return {
        "field_thickness": field_reference,
        "field_thickness_reference": "maximum_of_left_and_right",
        "left_field_thickness": float(left_field),
        "right_field_thickness": float(right_field),
        "field_thickness_asymmetry": (
            float(abs(left_field - right_field) / field_reference)
            if field_reference > 0.0
            else None
        ),
        "upper_wall_thickness": float(wall_minima[top_index]),
        "middle_wall_thickness": float(wall_minima[middle_index]),
        "lower_wall_thickness": float(wall_minima[lower_index]),
        "left_lower_wall_thickness": float(left_wall[lower_index]),
        "right_lower_wall_thickness": float(right_wall[lower_index]),
        "floor_thickness": floor,
        "minimum_wall_thickness": float(np.min(wall_minima)),
        "minimum_local_thickness": float(np.min(local)),
        "maximum_local_thickness": float(np.max(local)),
        "thickness_nonuniformity": (
            float((np.max(local) - np.min(local)) / field_reference)
            if field_reference > 0.0
            else None
        ),
        "floor_to_field_conformality": ratio(floor),
        "lower_wall_to_field_conformality": ratio(wall_minima[lower_index]),
        "left_lower_wall_to_field_conformality": ratio(left_wall[lower_index]),
        "right_lower_wall_to_field_conformality": ratio(right_wall[lower_index]),
        "remaining_aperture_top": float(apertures[top_index]),
        "remaining_aperture_middle": float(apertures[middle_index]),
        "remaining_aperture_lower": float(apertures[lower_index]),
        "minimum_remaining_aperture": float(np.min(apertures)),
        "aperture_open": bool(all(aperture_valid) and np.min(apertures) > 0.0),
        "outer_boundary_component_count": component_count,
        "layer_continuous": continuous,
        "pinhole_detected": not continuous,
        "sample_fractions": fractions,
        "sample_left_wall_thicknesses": left_wall,
        "sample_right_wall_thicknesses": right_wall,
        "sample_apertures": apertures,
    }

"""Raw-mesh geometry metrics for the TSV traveler."""

from __future__ import annotations

import math
from typing import TypedDict

import numpy as np


class AnchorHits(TypedDict):
    floor: bool
    left_mouth: bool
    right_mouth: bool


class ComponentSummary(TypedDict):
    component_id: int
    grid_point_count: int
    bounds_min: tuple[float, float]
    bounds_max: tuple[float, float]
    anchor_hits: AnchorHits
    anchor_hit_count: int


def raw_level_set_meshes(geometry) -> list[dict]:
    """Return every ordered level-set mesh without merging duplicate materials."""
    import viennals as ls

    material_map = geometry.getMaterialMap()
    result = []
    for index, level_set in enumerate(geometry.getLevelSets()):
        mesh = ls.Mesh()
        ls.ToSurfaceMesh(level_set, mesh).apply()
        nodes = np.asarray(mesh.getNodes(), dtype=float)
        lines = np.asarray(mesh.getLines(), dtype=int)
        triangles = np.asarray(mesh.getTriangles(), dtype=int)
        result.append({
            "level_set_index": index,
            "material": material_map.getMaterialAtIdx(index),
            "nodes": nodes,
            "lines": lines.reshape((-1, 2)) if lines.size else np.empty((0, 2), dtype=int),
            "triangles": (
                triangles.reshape((-1, 3))
                if triangles.size else np.empty((0, 3), dtype=int)
            ),
        })
    return result


def material_region_mesh(geometry, material) -> dict:
    """Return the actual region occupied by one material, not its map entry."""
    import viennals as ls

    level_set = geometry.getMaterialLevelSet(material)
    mesh = ls.Mesh()
    ls.ToSurfaceMesh(level_set, mesh).apply()
    nodes = np.asarray(mesh.getNodes(), dtype=float)
    lines = np.asarray(mesh.getLines(), dtype=int)
    triangles = np.asarray(mesh.getTriangles(), dtype=int)
    return {
        "material": material,
        "nodes": nodes,
        "lines": lines.reshape((-1, 2)) if lines.size else np.empty((0, 2), dtype=int),
        "triangles": (
            triangles.reshape((-1, 3))
            if triangles.size else np.empty((0, 3), dtype=int)
        ),
    }


def material_region_connectivity_2d(
    geometry,
    material,
    *,
    floor_y,
    field_y,
    via_radius,
    grid_delta,
    local_minimum_thickness=None,
    resolution_cells=2.0,
):
    """Test floor-to-rim connectivity on the material region grid.

    Features at the declared grid resolution are reported as unresolved.
    """
    import viennals as ls

    floor_y = float(floor_y)
    field_y = float(field_y)
    via_radius = float(via_radius)
    grid_delta = float(grid_delta)
    resolution_cells = float(resolution_cells)
    if not floor_y < field_y:
        raise ValueError("floor_y must be below field_y")
    if via_radius <= 0.0:
        raise ValueError("via_radius must be positive")
    if grid_delta <= 0.0:
        raise ValueError("grid_delta must be positive")
    if resolution_cells <= 0.0:
        raise ValueError("resolution_cells must be positive")
    if local_minimum_thickness is not None:
        local_minimum_thickness = float(local_minimum_thickness)
        if (
            not np.isfinite(local_minimum_thickness)
            or local_minimum_thickness < 0.0
        ):
            raise ValueError(
                "local_minimum_thickness must be finite and nonnegative"
            )

    resolution_limit = resolution_cells * grid_delta
    comparison_tolerance = max(1e-12, resolution_limit * 1e-9)
    level_set = ls.Domain(geometry.getMaterialLevelSet(material))
    marker = ls.MarkVoidPoints(level_set)
    marker.setSaveComponentIds(True)
    marker.apply()
    mesh = ls.Mesh()
    ls.ToMesh(level_set, mesh).apply()
    points = np.asarray(mesh.getNodes(), dtype=float)
    cell_data = mesh.getCellData()
    values = np.asarray(cell_data.getScalarData("LSValues", False), dtype=float)
    component_ids = np.asarray(
        cell_data.getScalarData("ConnectedComponentId", False), dtype=float
    )
    if len(points) != len(values) or len(points) != len(component_ids):
        raise ValueError("material connectivity mesh data have inconsistent lengths")
    if np.any(~np.isfinite(component_ids)):
        raise ValueError("material connectivity component IDs must be finite")

    negative = values < 0.0
    negative_ids = np.unique(component_ids[negative].astype(int))
    anchor_tolerance = resolution_limit
    floor_x_limit = 0.5 * via_radius

    def anchor_hits(component_points) -> AnchorHits:
        x = component_points[:, 0]
        y = component_points[:, 1]
        near_floor = (
            np.abs(y - floor_y) <= anchor_tolerance + comparison_tolerance
        )
        near_field = (
            np.abs(y - field_y) <= anchor_tolerance + comparison_tolerance
        )
        inside_rim = np.abs(x) <= via_radius + anchor_tolerance
        return {
            "floor": bool(np.any(
                near_floor
                & (np.abs(x) <= floor_x_limit + comparison_tolerance)
            )),
            "left_mouth": bool(np.any(
                near_field
                & inside_rim
                & (x < -0.5 * via_radius + comparison_tolerance)
            )),
            "right_mouth": bool(np.any(
                near_field
                & inside_rim
                & (x > 0.5 * via_radius - comparison_tolerance)
            )),
        }

    components: list[ComponentSummary] = []
    integer_component_ids = component_ids.astype(int)
    for component_id in negative_ids:
        component_points = points[
            negative & (integer_component_ids == component_id)
        ]
        hits = anchor_hits(component_points)
        bounds_min = component_points.min(axis=0)
        bounds_max = component_points.max(axis=0)
        components.append({
            "component_id": int(component_id),
            "grid_point_count": int(len(component_points)),
            "bounds_min": (float(bounds_min[0]), float(bounds_min[1])),
            "bounds_max": (float(bounds_max[0]), float(bounds_max[1])),
            "anchor_hits": hits,
            "anchor_hit_count": int(sum(hits.values())),
        })

    spanning_ids = tuple(
        component["component_id"]
        for component in components
        if all(component["anchor_hits"].values())
    )
    detached_ids = tuple(
        component["component_id"]
        for component in components
        if not any(component["anchor_hits"].values())
    )
    anchors_present = {
        name: any(component["anchor_hits"][name] for component in components)
        for name in ("floor", "left_mouth", "right_mouth")
    }
    unresolved_reasons = []
    if local_minimum_thickness is not None and (
        local_minimum_thickness
        <= resolution_limit + comparison_tolerance
    ):
        unresolved_reasons.append("local_thickness_at_or_below_resolution_limit")
    for name, present in anchors_present.items():
        if not present:
            unresolved_reasons.append(f"anchor_not_resolved:{name}")
    if not components:
        unresolved_reasons.append("no_negative_material_component")
    resolved = not unresolved_reasons

    return {
        "resolved": resolved,
        "unresolved_reasons": tuple(unresolved_reasons),
        "grid_delta": grid_delta,
        "resolution_cells": resolution_cells,
        "resolution_limit": resolution_limit,
        "local_minimum_thickness": local_minimum_thickness,
        "anchor_tolerance": anchor_tolerance,
        "anchors_present": anchors_present,
        "negative_component_count": len(components),
        "component_summaries": tuple(components),
        "spanning_component_ids": spanning_ids,
        "floor_to_both_mouths_connected": bool(resolved and spanning_ids),
        "detached_fragment_ids": detached_ids,
        "detached_fragment_count": len(detached_ids),
    }


def line_intersections_at_y(nodes, lines, y, *, x_bounds=None, atol=1e-12):
    """Return unique x coordinates where a 2D polyline crosses horizontal y."""
    points = np.asarray(nodes, dtype=float)
    edges = np.asarray(lines, dtype=int)
    if points.ndim != 2 or points.shape[1] < 2:
        raise ValueError("nodes must be an Nx2-or-greater array")
    if edges.ndim != 2 or edges.shape[1] != 2:
        raise ValueError("lines must be an Mx2 array")

    xs = []
    for start, end in edges:
        x1, y1 = points[start, :2]
        x2, y2 = points[end, :2]
        dy = y2 - y1
        if abs(dy) <= atol:
            if abs(y - y1) <= atol:
                xs.extend((x1, x2))
            continue
        t = (y - y1) / dy
        if -atol <= t <= 1.0 + atol:
            x = x1 + t * (x2 - x1)
            if x_bounds is None or x_bounds[0] - atol <= x <= x_bounds[1] + atol:
                xs.append(float(x))

    if not xs:
        return np.empty(0, dtype=float)
    xs = np.sort(np.asarray(xs, dtype=float))
    keep = np.r_[True, np.diff(xs) > max(atol, 1e-10)]
    return xs[keep]


def line_intersections_at_x(nodes, lines, x, *, y_bounds=None, atol=1e-12):
    """Return unique y coordinates where a 2D polyline crosses vertical x."""
    points = np.asarray(nodes, dtype=float)
    swapped = points.copy()
    swapped[:, [0, 1]] = swapped[:, [1, 0]]
    bounds = None if y_bounds is None else (y_bounds[0], y_bounds[1])
    return line_intersections_at_y(
        swapped, lines, x, x_bounds=bounds, atol=atol
    )


def quarter_via_radius_at_y(nodes, lines, y, *, max_radius):
    """Measure the positive-x wall radius of a quarter/half 2D via at y."""
    xs = line_intersections_at_y(nodes, lines, y, x_bounds=(0.0, max_radius))
    positive = xs[xs > 0.0]
    if not len(positive):
        raise ValueError(f"no via-wall intersection at y={y}")
    return float(positive.max())


def opening_geometry_at_y(nodes, lines, y, *, max_radius):
    """Return opening CD and center for a full or symmetry-clipped 2D mask."""
    xs = line_intersections_at_y(
        nodes, lines, y, x_bounds=(-max_radius, max_radius)
    )
    negative = xs[xs < 0.0]
    positive = xs[xs > 0.0]
    if len(negative) and len(positive):
        left = float(negative.min())
        right = float(positive.max())
        geometry_kind = "full"
    elif len(positive):
        right = float(positive.max())
        left = -right
        geometry_kind = "symmetry_clipped"
    elif len(negative):
        left = float(negative.min())
        right = -left
        geometry_kind = "symmetry_clipped"
    else:
        raise ValueError(f"no mask-opening wall intersection at y={y}")
    cd = right - left
    if not cd > 0.0:
        raise ValueError(f"non-positive mask opening at y={y}")
    return {
        "left": left,
        "right": right,
        "cd": float(cd),
        "center": float(0.5 * (left + right)),
        "geometry_kind": geometry_kind,
    }


def pattern_metrics_2d(
    nodes,
    lines,
    *,
    surface_y,
    target_cd,
    target_mask_height,
    max_radius=None,
    lower_fraction=0.05,
    upper_fraction=0.85,
):
    """Measure the generated mask opening rather than echoing its inputs."""
    points = np.asarray(nodes, dtype=float)
    if points.ndim != 2 or points.shape[1] < 2 or not len(points):
        raise ValueError("mask nodes must be a non-empty Nx2-or-greater array")
    if not 0 < lower_fraction < upper_fraction < 1:
        raise ValueError("mask fractions must satisfy 0 < lower < upper < 1")
    if max_radius is None:
        max_radius = target_cd

    mask_top = float(points[:, 1].max())
    mask_bottom = float(points[:, 1].min())
    mask_height = mask_top - surface_y
    if not mask_height > 0:
        raise ValueError("mask top must be above the wafer surface")
    lower_y = surface_y + lower_fraction * mask_height
    upper_y = surface_y + upper_fraction * mask_height
    middle_y = surface_y + 0.50 * mask_height
    lower = opening_geometry_at_y(
        points, lines, lower_y, max_radius=max_radius
    )
    middle = opening_geometry_at_y(
        points, lines, middle_y, max_radius=max_radius
    )
    upper = opening_geometry_at_y(
        points, lines, upper_y, max_radius=max_radius
    )
    sidewall_angle = math.degrees(math.atan(
        0.5 * (upper["cd"] - lower["cd"]) / (upper_y - lower_y)
    ))
    right_angle = math.degrees(math.atan(
        (upper["right"] - lower["right"]) / (upper_y - lower_y)
    ))
    left_angle = math.degrees(math.atan(
        (lower["left"] - upper["left"]) / (upper_y - lower_y)
    ))
    opening_valid = all(
        measurement["cd"] > 0.0 for measurement in (lower, middle, upper)
    )
    return {
        "opening_cd_bottom": lower["cd"],
        "opening_cd_middle": middle["cd"],
        "opening_cd_top": upper["cd"],
        "opening_center_bottom": lower["center"],
        "opening_center_middle": middle["center"],
        "opening_center_top": upper["center"],
        "opening_center_shift": upper["center"] - lower["center"],
        "cd_bias": lower["cd"] - target_cd,
        "mask_height": mask_height,
        "mask_height_error": mask_height - target_mask_height,
        "mask_sidewall_angle_deg": float(sidewall_angle),
        "mask_left_sidewall_angle_deg": float(left_angle),
        "mask_right_sidewall_angle_deg": float(right_angle),
        "mask_mesh_bottom_y": mask_bottom,
        "opening_valid": bool(opening_valid),
        "geometry_kind": lower["geometry_kind"],
    }


def etch_profile_metrics_2d(
    nodes,
    lines,
    *,
    surface_y,
    floor_y,
    target_cd,
    max_radius=None,
    top_fraction=0.10,
    middle_fraction=0.50,
    bottom_fraction=0.85,
    sample_count=76,
):
    """Measure CD, taper, bow, and roughness on a 2D wall."""
    depth = float(surface_y - floor_y)
    if not depth > 0:
        raise ValueError("surface_y must be above floor_y")
    if not 0 < top_fraction < middle_fraction < bottom_fraction < 1:
        raise ValueError("CD fractions must satisfy 0 < top < middle < bottom < 1")
    if sample_count < 8:
        raise ValueError("sample_count must be at least 8")
    if max_radius is None:
        max_radius = target_cd

    fractions = np.linspace(top_fraction, bottom_fraction, sample_count)
    ys = surface_y - fractions * depth
    radii = np.asarray([
        quarter_via_radius_at_y(nodes, lines, y, max_radius=max_radius)
        for y in ys
    ])
    cds = 2.0 * radii
    depth_positions = fractions * depth

    def radius_at(fraction):
        y = surface_y - fraction * depth
        return quarter_via_radius_at_y(
            nodes, lines, y, max_radius=max_radius
        )

    radius_top = radius_at(top_fraction)
    radius_middle = radius_at(middle_fraction)
    radius_bottom = radius_at(bottom_fraction)
    chord_slope = (
        (radius_bottom - radius_top)
        / ((bottom_fraction - top_fraction) * depth)
    )
    straight_wall = radius_top + chord_slope * (
        depth_positions - top_fraction * depth
    )
    linear_residual = radii - straight_wall
    profile_degree = min(3, sample_count - 1)
    smooth_profile = np.polyval(
        np.polyfit(depth_positions, radii, profile_degree), depth_positions
    )

    return {
        "depth": depth,
        "cd_top": 2.0 * radius_top,
        "cd_middle": 2.0 * radius_middle,
        "cd_bottom": 2.0 * radius_bottom,
        "cd_min": float(cds.min()),
        "cd_max": float(cds.max()),
        "max_cd_error": float(np.max(np.abs(cds - target_cd))),
        "sidewall_angle_deg": float(math.degrees(math.atan(-chord_slope))),
        "max_bow": float(np.max(np.abs(linear_residual))),
        "scallop_rms": float(np.sqrt(np.mean((radii - smooth_profile) ** 2))),
        "sample_fractions": fractions,
        "sample_cds": cds,
    }


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
    """Measure the horizontal floor shape over the central half of target CD."""
    if not target_cd > 0:
        raise ValueError("target_cd must be positive")
    if not grid_delta > 0:
        raise ValueError("grid_delta must be positive")
    if not resolution_cells > 0:
        raise ValueError("resolution_cells must be positive")

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
        intersections = line_intersections_at_x(nodes, lines, float(x))
        below_surface = intersections[intersections < surface_y - tolerance]
        if len(below_surface) != 1:
            diagnostics["sample_ys"] = sample_ys
            diagnostics["failed_x"] = float(x)
            diagnostics["failed_intersections_y"] = intersections.tolist()
            reason = (
                "floor_intersection_missing"
                if not len(below_surface)
                else "floor_intersection_multiple"
            )
            return {
                "state": "floor_profile_unavailable",
                "reason_codes": [reason],
                "metrics": None,
                "diagnostics": diagnostics,
            }
        sample_ys.append(float(below_surface[0]))

    sample_ys = np.asarray(sample_ys, dtype=float)
    filtered_ys = np.convolve(
        np.pad(sample_ys, (1, 1), mode="edge"), np.ones(3) / 3.0, mode="valid"
    )
    filtered_xs = sample_xs
    mean_y = float(np.mean(filtered_ys))
    flatness_pv = float(np.ptp(filtered_ys))
    center_index = int(np.argmin(np.abs(filtered_xs - center_x)))
    center_relief = float(
        0.5 * (filtered_ys[0] + filtered_ys[-1])
        - filtered_ys[center_index]
    )
    resolution_limit = float(resolution_cells * grid_delta)
    diagnostics["sample_ys"] = sample_ys.tolist()
    diagnostics["filtered_sample_xs"] = filtered_xs.tolist()
    diagnostics["filtered_sample_ys"] = filtered_ys.tolist()
    return {
        "state": "complete",
        "reason_codes": [],
        "metrics": {
            "floor_flatness_pv": flatness_pv,
            "floor_horizontal_rms": float(
                np.sqrt(np.mean((filtered_ys - mean_y) ** 2))
            ),
            "floor_center_relief": center_relief,
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


def measure_full_via_profile_2d(
    nodes,
    lines,
    *,
    surface_y,
    target_cd,
    domain_x_bounds,
    grid_delta,
    target_depth=None,
    search_x_bounds=None,
    center_x=0.0,
    top_fraction=0.10,
    middle_fraction=0.50,
    bottom_fraction=0.85,
    sample_count=76,
    minimum_feature_cells=2.0,
    allow_partial_floor=False,
):
    """Measure a full 2D via or return why its profile is unavailable."""
    points = np.asarray(nodes, dtype=float)
    segments = np.asarray(lines, dtype=int)
    if points.ndim != 2 or points.shape[1] < 2 or not len(points):
        raise ValueError("silicon nodes must be a non-empty Nx2-or-greater array")
    if not len(segments):
        raise ValueError("silicon lines must be non-empty")
    if not grid_delta > 0:
        raise ValueError("grid_delta must be positive")
    if target_depth is not None and not target_depth > 0:
        raise ValueError("target_depth must be positive")
    if not domain_x_bounds[0] < center_x < domain_x_bounds[1]:
        raise ValueError("center_x must lie inside domain_x_bounds")
    if search_x_bounds is None:
        search_x_bounds = domain_x_bounds
    if not (
        domain_x_bounds[0] <= search_x_bounds[0] < center_x
        and center_x < search_x_bounds[1] <= domain_x_bounds[1]
    ):
        raise ValueError("search_x_bounds must straddle center_x inside the domain")
    if not 0 < top_fraction < middle_fraction < bottom_fraction < 1:
        raise ValueError("CD fractions must satisfy 0 < top < middle < bottom < 1")
    if sample_count < 8:
        raise ValueError("sample_count must be at least 8")

    mesh_bounds = {
        "x_min": float(points[:, 0].min()),
        "x_max": float(points[:, 0].max()),
        "y_min": float(points[:, 1].min()),
        "y_max": float(points[:, 1].max()),
    }
    surface_xs = line_intersections_at_y(
        points, segments, surface_y, x_bounds=domain_x_bounds
    )
    diagnostics = {
        "mesh_bounds": mesh_bounds,
        "surface_intersections": surface_xs.tolist(),
        "floor_candidates": [],
        "requested_y_range": None,
        "sample_count": sample_count,
        "samples_with_left_wall": 0,
        "samples_with_right_wall": 0,
        "samples_with_both_walls_in_domain": 0,
        "samples_with_both_walls_in_search": 0,
        "minimum_width_cells": None,
        "sample_records": [],
        "floor_profile": None,
    }

    if not len(surface_xs):
        return {
            "state": "out_of_scope_region",
            "reason_codes": ["declared_wafer_surface_absent"],
            "metrics": None,
            "diagnostics": diagnostics,
        }

    floor_candidates = line_intersections_at_x(
        points,
        segments,
        center_x,
        y_bounds=(mesh_bounds["y_min"], surface_y),
    )
    floor_candidates = floor_candidates[floor_candidates < surface_y]
    diagnostics["floor_candidates"] = floor_candidates.tolist()
    if not len(floor_candidates):
        return {
            "state": "valid_categorical_modeled_state",
            "reason_codes": ["via_floor_absent_at_declared_center"],
            "metrics": None,
            "diagnostics": diagnostics,
        }

    floor_y = float(floor_candidates.min())
    depth = float(surface_y - floor_y)
    fractions = np.linspace(top_fraction, bottom_fraction, sample_count)
    sample_ys = surface_y - fractions * depth
    diagnostics["requested_y_range"] = [
        float(sample_ys.min()),
        float(sample_ys.max()),
    ]

    widths = []
    centers = []
    search_missing = False
    domain_missing = False
    for y in sample_ys:
        domain_xs = line_intersections_at_y(
            points, segments, y, x_bounds=domain_x_bounds
        )
        left = domain_xs[domain_xs < center_x]
        right = domain_xs[domain_xs > center_x]
        diagnostics["samples_with_left_wall"] += int(bool(len(left)))
        diagnostics["samples_with_right_wall"] += int(bool(len(right)))
        if not len(left) or not len(right):
            domain_missing = True
            diagnostics["sample_records"].append({
                "y": float(y),
                "domain_intersections_x": domain_xs.tolist(),
                "accepted_intersections_x": [],
                "rejected_intersections_x": domain_xs.tolist(),
                "left_wall_x": float(left.max()) if len(left) else None,
                "right_wall_x": float(right.min()) if len(right) else None,
                "wall_pair_status": "missing_in_domain",
            })
            continue
        diagnostics["samples_with_both_walls_in_domain"] += 1
        left_x = float(left.max())
        right_x = float(right.min())
        widths.append(right_x - left_x)
        centers.append(0.5 * (left_x + right_x))

        search_xs = line_intersections_at_y(
            points, segments, y, x_bounds=search_x_bounds
        )
        search_left = search_xs[search_xs < center_x]
        search_right = search_xs[search_xs > center_x]
        if len(search_left) and len(search_right):
            diagnostics["samples_with_both_walls_in_search"] += 1
            accepted = [float(search_left.max()), float(search_right.min())]
            status = "complete"
        else:
            search_missing = True
            accepted = []
            status = "outside_search_bounds"
        diagnostics["sample_records"].append({
            "y": float(y),
            "domain_intersections_x": domain_xs.tolist(),
            "accepted_intersections_x": accepted,
            "rejected_intersections_x": [
                float(value)
                for value in domain_xs
                if value < search_x_bounds[0] or value > search_x_bounds[1]
            ],
            "left_wall_x": left_x,
            "right_wall_x": right_x,
            "wall_pair_status": status,
        })

    if domain_missing:
        reason = (
            "one_full_via_wall_absent"
            if not diagnostics["samples_with_left_wall"]
            or not diagnostics["samples_with_right_wall"]
            else "sampling_path_interrupted"
        )
        return {
            "state": "valid_categorical_modeled_state",
            "reason_codes": [reason],
            "metrics": None,
            "diagnostics": diagnostics,
        }
    if search_missing:
        return {
            "state": "extractor_domain_failure",
            "reason_codes": ["walls_outside_declared_search_bounds"],
            "metrics": None,
            "diagnostics": diagnostics,
        }

    widths = np.asarray(widths, dtype=float)
    half_widths = 0.5 * widths
    centers = np.asarray(centers, dtype=float)
    minimum_width_cells = float(widths.min() / grid_delta)
    diagnostics["minimum_width_cells"] = minimum_width_cells
    if minimum_width_cells <= minimum_feature_cells:
        return {
            "state": "insufficient_grid_representation",
            "reason_codes": ["minimum_width_at_or_below_cell_threshold"],
            "metrics": None,
            "diagnostics": diagnostics,
        }

    floor_profile = floor_profile_metrics_2d(
        points,
        segments,
        surface_y=surface_y,
        target_cd=target_cd,
        grid_delta=grid_delta,
        center_x=center_x,
    )
    diagnostics["floor_profile"] = floor_profile["diagnostics"]
    floor_complete = floor_profile["state"] == "complete"
    if not floor_complete and not allow_partial_floor:
        return {
            "state": "valid_categorical_modeled_state",
            "reason_codes": floor_profile["reason_codes"],
            "metrics": None,
            "diagnostics": diagnostics,
        }

    depth_positions = fractions * depth
    top_index = 0
    middle_index = int(np.argmin(np.abs(fractions - middle_fraction)))
    bottom_index = len(fractions) - 1
    chord_slope = (
        (half_widths[bottom_index] - half_widths[top_index])
        / ((bottom_fraction - top_fraction) * depth)
    )
    straight_wall = half_widths[top_index] + chord_slope * (
        depth_positions - top_fraction * depth
    )
    smooth_profile = np.polyval(
        np.polyfit(depth_positions, half_widths, min(3, sample_count - 1)),
        depth_positions,
    )
    metrics = {
        "depth": depth,
        "cd_top": float(widths[top_index]),
        "cd_middle": float(widths[middle_index]),
        "cd_bottom": float(widths[bottom_index]),
        "cd_min": float(widths.min()),
        "cd_max": float(widths.max()),
        "max_cd_error": float(np.max(np.abs(widths - target_cd))),
        "sidewall_angle_deg": float(math.degrees(math.atan(-chord_slope))),
        "max_bow": float(np.max(np.abs(half_widths - straight_wall))),
        "scallop_rms": float(
            np.sqrt(np.mean((half_widths - smooth_profile) ** 2))
        ),
        "maximum_center_shift": float(np.max(np.abs(centers - center_x))),
    }
    if not floor_complete:
        metrics.update({
            "floor_flatness_pv": None,
            "floor_horizontal_rms": None,
            "floor_center_relief": None,
            "floor_sample_count": floor_profile["diagnostics"]["sample_count"],
            "floor_flatness_cells": None,
            "floor_resolution_cells": 2.0,
            "floor_resolution_status": "unavailable",
            "profile_symmetry_rms": None,
            "profile_floor_rmse": None,
            "profile_shape_rmse": None,
            "profile_max_deviation": None,
        })
        if target_depth is not None:
            left_wall_xs = np.asarray(
                [record["left_wall_x"] for record in diagnostics["sample_records"]],
                dtype=float,
            )
            right_wall_xs = np.asarray(
                [record["right_wall_x"] for record in diagnostics["sample_records"]],
                dtype=float,
            )
            wall_offsets = np.concatenate(
                (left_wall_xs - (center_x - 0.5 * target_cd),
                 right_wall_xs - (center_x + 0.5 * target_cd))
            )
            metrics["profile_wall_rmse"] = float(
                np.sqrt(np.mean(wall_offsets**2))
            )
        return {
            "state": "partial",
            "reason_codes": floor_profile["reason_codes"],
            "metrics": metrics,
            "diagnostics": diagnostics,
        }

    metrics.update(floor_profile["metrics"])
    filtered_floor_ys = np.asarray(
        floor_profile["diagnostics"]["filtered_sample_ys"], dtype=float
    )
    floor_pair_offsets = 0.5 * (
        filtered_floor_ys - filtered_floor_ys[::-1]
    )
    wall_symmetry_mse = float(np.mean((centers - center_x) ** 2))
    floor_symmetry_mse = float(np.mean(floor_pair_offsets**2))
    metrics["profile_symmetry_rms"] = float(
        math.sqrt(0.5 * wall_symmetry_mse + 0.5 * floor_symmetry_mse)
    )
    if target_depth is not None:
        left_wall_xs = np.asarray(
            [record["left_wall_x"] for record in diagnostics["sample_records"]],
            dtype=float,
        )
        right_wall_xs = np.asarray(
            [record["right_wall_x"] for record in diagnostics["sample_records"]],
            dtype=float,
        )
        wall_offsets = np.concatenate(
            (left_wall_xs - (center_x - 0.5 * target_cd),
             right_wall_xs - (center_x + 0.5 * target_cd))
        )
        target_floor_y = surface_y - float(target_depth)
        floor_offsets = filtered_floor_ys - target_floor_y
        wall_mse = float(np.mean(wall_offsets**2))
        floor_mse = float(np.mean(floor_offsets**2))
        metrics.update({
            "profile_wall_rmse": float(math.sqrt(wall_mse)),
            "profile_floor_rmse": float(math.sqrt(floor_mse)),
            "profile_shape_rmse": float(math.sqrt(0.5 * wall_mse + 0.5 * floor_mse)),
            "profile_max_deviation": float(
                max(np.max(np.abs(wall_offsets)), np.max(np.abs(floor_offsets)))
            ),
        })
    return {
        "state": "complete",
        "reason_codes": [],
        "metrics": metrics,
        "diagnostics": diagnostics,
    }


def point_to_polyline_distances(points, boundary_nodes, boundary_lines):
    """Minimum Euclidean distance from each point to a 2D polyline."""
    query = np.asarray(points, dtype=float)[:, :2]
    nodes = np.asarray(boundary_nodes, dtype=float)[:, :2]
    lines = np.asarray(boundary_lines, dtype=int)
    if not len(query) or not len(lines):
        return np.full(len(query), np.nan)

    starts = nodes[lines[:, 0]]
    ends = nodes[lines[:, 1]]
    vectors = ends - starts
    lengths_sq = np.sum(vectors * vectors, axis=1)
    result = []
    for point in query:
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.sum((point - starts) * vectors, axis=1) / lengths_sq
        t = np.where(lengths_sq > 0, np.clip(t, 0.0, 1.0), 0.0)
        closest = starts + t[:, None] * vectors
        result.append(float(np.sqrt(np.sum((closest - point) ** 2, axis=1)).min()))
    return np.asarray(result)


def layer_thickness_metrics_2d(
    inner_nodes,
    inner_lines,
    outer_nodes,
    outer_lines,
    *,
    surface_y,
    floor_y,
    via_radius,
    field_x=None,
    floor_x=None,
    top_fraction=0.15,
    middle_fraction=0.50,
    lower_fraction=0.80,
    sample_count=71,
    continuity_tolerance=1e-10,
):
    """Measure local film thickness and remaining aperture."""
    depth = float(surface_y - floor_y)
    if depth <= 0 or via_radius <= 0:
        raise ValueError("surface_y, floor_y, and via_radius define an invalid via")
    if not 0 < top_fraction < middle_fraction < lower_fraction < 1:
        raise ValueError("wall fractions must satisfy 0 < top < middle < lower < 1")
    if sample_count < 8:
        raise ValueError("sample_count must be at least 8")
    field_x = float(field_x if field_x is not None else 2.5 * via_radius)
    floor_x = float(floor_x if floor_x is not None else 0.2 * via_radius)

    field_ys = line_intersections_at_x(inner_nodes, inner_lines, field_x)
    floor_ys = line_intersections_at_x(inner_nodes, inner_lines, floor_x)
    if not len(field_ys) or not len(floor_ys):
        raise ValueError("inner interface does not contain field and floor samples")
    field_y = float(field_ys[np.argmin(np.abs(field_ys - surface_y))])
    floor_sample_y = float(floor_ys[np.argmin(np.abs(floor_ys - floor_y))])

    fractions = np.linspace(top_fraction, lower_fraction, sample_count)
    wall_points = []
    apertures = []
    aperture_valid = []
    for fraction in fractions:
        y = surface_y - fraction * depth
        radius = quarter_via_radius_at_y(
            inner_nodes, inner_lines, y, max_radius=2.0 * via_radius
        )
        wall_points.append((radius, y))
        try:
            outer_radius = quarter_via_radius_at_y(
                outer_nodes, outer_lines, y, max_radius=2.0 * via_radius
            )
            apertures.append(2.0 * outer_radius)
            aperture_valid.append(True)
        except ValueError:
            apertures.append(0.0)
            aperture_valid.append(False)

    wall_thicknesses = point_to_polyline_distances(
        wall_points, outer_nodes, outer_lines
    )
    field_thickness, floor_thickness = point_to_polyline_distances(
        [(field_x, field_y), (floor_x, floor_sample_y)],
        outer_nodes,
        outer_lines,
    )
    top_index = 0
    middle_index = int(np.argmin(np.abs(fractions - middle_fraction)))
    lower_index = len(fractions) - 1
    local = np.r_[wall_thicknesses, field_thickness, floor_thickness]
    component_count = len(component_summaries(outer_nodes, outer_lines))
    continuous = bool(
        np.all(np.isfinite(local))
        and np.min(local) > continuity_tolerance
        and component_count == 1
    )

    def ratio(value):
        return float(value / field_thickness) if field_thickness > 0 else None

    return {
        "field_thickness": float(field_thickness),
        "upper_wall_thickness": float(wall_thicknesses[top_index]),
        "middle_wall_thickness": float(wall_thicknesses[middle_index]),
        "lower_wall_thickness": float(wall_thicknesses[lower_index]),
        "floor_thickness": float(floor_thickness),
        "minimum_wall_thickness": float(np.min(wall_thicknesses)),
        "minimum_local_thickness": float(np.min(local)),
        "maximum_local_thickness": float(np.max(local)),
        "thickness_nonuniformity": (
            float((np.max(local) - np.min(local)) / field_thickness)
            if field_thickness > 0 else None
        ),
        "floor_to_field_conformality": ratio(floor_thickness),
        "lower_wall_to_field_conformality": ratio(wall_thicknesses[lower_index]),
        "remaining_aperture_top": float(apertures[top_index]),
        "remaining_aperture_middle": float(apertures[middle_index]),
        "remaining_aperture_lower": float(apertures[lower_index]),
        "minimum_remaining_aperture": float(np.min(apertures)),
        "aperture_open": bool(all(aperture_valid) and np.min(apertures) > 0.0),
        "outer_boundary_component_count": component_count,
        "layer_continuous": continuous,
        "pinhole_detected": not continuous,
        "sample_fractions": fractions,
        "sample_wall_thicknesses": wall_thicknesses,
        "sample_apertures": np.asarray(apertures),
    }


def line_components(node_count, lines):
    """Return connected node-index arrays for a line mesh."""
    edges = np.asarray(lines, dtype=int)
    adjacency = [set() for _ in range(node_count)]
    for start, end in edges:
        adjacency[start].add(end)
        adjacency[end].add(start)

    unseen = {index for index, neighbors in enumerate(adjacency) if neighbors}
    components = []
    while unseen:
        root = unseen.pop()
        stack = [root]
        component = {root}
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor not in component:
                    component.add(neighbor)
                    unseen.discard(neighbor)
                    stack.append(neighbor)
        components.append(np.asarray(sorted(component), dtype=int))
    return components


def component_summaries(nodes, lines):
    """Summarize line-mesh components for topology qualification."""
    points = np.asarray(nodes, dtype=float)
    edges = np.asarray(lines, dtype=int)
    summaries = []
    for indices in line_components(len(points), edges):
        members = set(indices.tolist())
        component_edges = np.asarray([
            edge for edge in edges if edge[0] in members and edge[1] in members
        ], dtype=int)
        degree = {index: 0 for index in members}
        for start, end in component_edges:
            degree[int(start)] += 1
            degree[int(end)] += 1
        component_points = points[indices]
        summaries.append({
            "node_indices": indices,
            "node_count": len(indices),
            "edge_count": len(component_edges),
            "closed": bool(degree and all(value == 2 for value in degree.values())),
            "bounds_min": component_points.min(axis=0),
            "bounds_max": component_points.max(axis=0),
        })
    return summaries


def ordered_closed_component(nodes, lines, node_indices):
    """Return an ordered 2D polygon for a degree-two line component."""
    members = set(np.asarray(node_indices, dtype=int).tolist())
    adjacency = {index: [] for index in members}
    for start, end in np.asarray(lines, dtype=int):
        start, end = int(start), int(end)
        if start in members and end in members:
            adjacency[start].append(end)
            adjacency[end].append(start)
    if not adjacency or any(len(neighbors) != 2 for neighbors in adjacency.values()):
        raise ValueError("component is not a simple closed contour")

    first = min(members)
    ordered = [first]
    previous = None
    current = first
    while True:
        candidates = [node for node in adjacency[current] if node != previous]
        next_node = candidates[0]
        if next_node == first:
            break
        if next_node in ordered:
            raise ValueError("component repeats a node before closing")
        ordered.append(next_node)
        previous, current = current, next_node
    return np.asarray(nodes, dtype=float)[ordered, :2]


def polygon_area(points):
    """Unsigned area of an ordered 2D polygon."""
    polygon = np.asarray(points, dtype=float)
    if len(polygon) < 3:
        return 0.0
    x, y = polygon[:, 0], polygon[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0)


def fill_topology_metrics_2d(
    nodes,
    lines,
    *,
    field_y,
    floor_y,
    via_x_bounds,
    field_sample_xs,
    center_x=0.0,
    tolerance=1e-10,
    initial_cavity_area=None,
    grid_delta=None,
    area_sample_count=201,
    mouth_sample_y=None,
    overburden_sample_count=201,
):
    """Measure voids, fill progress, mouth opening, and overburden."""
    points = np.asarray(nodes, dtype=float)
    edges = np.asarray(lines, dtype=int)
    if not len(points) or not len(edges):
        raise ValueError("fill boundary must be a non-empty line mesh")
    x_lo, x_hi = via_x_bounds
    if x_lo >= x_hi or floor_y >= field_y:
        raise ValueError("invalid via bounds or reference levels")
    if area_sample_count < 8:
        raise ValueError("area_sample_count must be at least 8")
    if overburden_sample_count < 8:
        raise ValueError("overburden_sample_count must be at least 8")
    if initial_cavity_area is not None and initial_cavity_area <= 0.0:
        raise ValueError("initial_cavity_area must be positive")
    if grid_delta is not None and grid_delta <= 0.0:
        raise ValueError("grid_delta must be positive")

    summaries = component_summaries(points, edges)
    exterior_index = max(
        range(len(summaries)),
        key=lambda index: float(
            summaries[index]["bounds_max"][0]
            - summaries[index]["bounds_min"][0]
        ),
    )
    exterior = summaries[exterior_index]
    exterior_points = points[exterior["node_indices"], :2]
    in_via = (
        (exterior_points[:, 0] >= x_lo - tolerance)
        & (exterior_points[:, 0] <= x_hi + tolerance)
    )
    below_field = exterior_points[:, 1] < field_y - tolerance
    open_void = bool(np.any(in_via & below_field))
    open_void_depth = (
        float(field_y - np.min(exterior_points[in_via, 1]))
        if open_void and np.any(in_via) else 0.0
    )
    exterior_members = set(exterior["node_indices"].tolist())
    exterior_edges = np.asarray([
        edge
        for edge in edges
        if int(edge[0]) in exterior_members and int(edge[1]) in exterior_members
    ], dtype=int)

    open_void_area = 0.0
    if open_void:
        section_edges = np.linspace(x_lo, x_hi, area_sample_count + 1)
        section_xs = 0.5 * (section_edges[:-1] + section_edges[1:])
        section_depths = []
        for x in section_xs:
            intersections = line_intersections_at_x(
                points,
                exterior_edges,
                x,
            )
            below = intersections[intersections < field_y - tolerance]
            surface_y = float(np.max(below)) if len(below) else field_y
            section_depths.append(max(0.0, field_y - surface_y))
        open_void_area = float(
            np.mean(section_depths) * (x_hi - x_lo)
        )

    closed_voids = []
    unexpected_components = []
    for index, summary in enumerate(summaries):
        if index == exterior_index:
            continue
        center = 0.5 * (summary["bounds_min"] + summary["bounds_max"])
        recognized_void = bool(
            summary["closed"]
            and x_lo - tolerance <= center[0] <= x_hi + tolerance
            and summary["bounds_min"][1] < field_y - tolerance
        )
        if not recognized_void:
            unexpected_components.append(summary)
            continue
        polygon = ordered_closed_component(
            points, edges, summary["node_indices"]
        )
        width = float(summary["bounds_max"][0] - summary["bounds_min"][0])
        height = float(summary["bounds_max"][1] - summary["bounds_min"][1])
        closed_voids.append({
            "area": polygon_area(polygon),
            "width": width,
            "height": height,
            "major_dimension": max(width, height),
            "aspect_ratio": max(width, height) / max(min(width, height), tolerance),
        })

    center_intersections = line_intersections_at_x(points, edges, center_x)
    if not len(center_intersections):
        raise ValueError("fill boundary does not cross the via centerline")
    center_surface_y = float(np.max(center_intersections))
    field_surface_ys = []
    for x in field_sample_xs:
        intersections = line_intersections_at_x(points, edges, x)
        if not len(intersections):
            raise ValueError(f"fill boundary does not cross field sample x={x}")
        field_surface_ys.append(float(np.max(intersections)))
    field_overburden = np.asarray(field_surface_ys) - field_y
    center_overburden = center_surface_y - field_y
    profile_edges = np.linspace(
        min(field_sample_xs),
        max(field_sample_xs),
        overburden_sample_count + 1,
    )
    profile_xs = 0.5 * (profile_edges[:-1] + profile_edges[1:])
    profile_surface_ys = []
    for x in profile_xs:
        intersections = line_intersections_at_x(points, exterior_edges, x)
        if not len(intersections):
            raise ValueError(f"fill boundary does not cross profile sample x={x}")
        profile_surface_ys.append(float(np.max(intersections)))
    profile_overburden = np.asarray(profile_surface_ys) - field_y
    sampled_overburden = np.r_[field_overburden, center_overburden]
    open_internal_components = [
        summary
        for summary in unexpected_components
        if not summary["closed"]
        and summary["bounds_min"][1] < field_y - tolerance
        and summary["bounds_max"][0] >= x_lo - tolerance
        and summary["bounds_min"][0] <= x_hi + tolerance
    ]
    closed_void_area = float(sum(void["area"] for void in closed_voids))
    remaining_void_area = open_void_area + closed_void_area
    fill_fraction = (
        float(np.clip(1.0 - remaining_void_area / initial_cavity_area, 0.0, 1.0))
        if initial_cavity_area is not None
        else None
    )
    requested_mouth_sample_y = (
        field_y - 0.01 * (field_y - floor_y)
        if mouth_sample_y is None
        else float(mouth_sample_y)
    )
    requested_mouth_offset = max(
        tolerance,
        field_y - requested_mouth_sample_y,
    )
    effective_mouth_offset = (
        min(requested_mouth_offset, 0.5 * open_void_depth)
        if open_void
        else requested_mouth_offset
    )
    mouth_sample_y = field_y - effective_mouth_offset
    mouth_xs = line_intersections_at_y(
        points,
        exterior_edges,
        mouth_sample_y,
        x_bounds=(x_lo, x_hi),
    )
    left = mouth_xs[mouth_xs <= center_x + tolerance]
    right = mouth_xs[mouth_xs >= center_x - tolerance]
    mouth_aperture = (
        max(0.0, float(np.min(right) - np.max(left)))
        if open_void and len(left) and len(right)
        else 0.0
    )
    mouth_open = mouth_aperture > tolerance
    detection_area = (
        float(grid_delta * grid_delta)
        if grid_delta is not None
        else float(tolerance * tolerance)
    )
    topology_valid = not unexpected_components
    void_free = bool(topology_valid and not open_void and not closed_voids)

    return {
        "open_void": open_void,
        "open_void_depth": open_void_depth,
        "open_void_area": open_void_area,
        "closed_void_count": len(closed_voids),
        "closed_void_area": closed_void_area,
        "remaining_void_area": remaining_void_area,
        "initial_cavity_area": initial_cavity_area,
        "fill_fraction": fill_fraction,
        "maximum_void_width": max((void["width"] for void in closed_voids), default=0.0),
        "maximum_void_height": max((void["height"] for void in closed_voids), default=0.0),
        "maximum_void_dimension": max(
            (void["major_dimension"] for void in closed_voids), default=0.0
        ),
        "maximum_void_aspect_ratio": max(
            (void["aspect_ratio"] for void in closed_voids), default=0.0
        ),
        "open_internal_component_count": len(open_internal_components),
        "unexpected_component_count": len(unexpected_components),
        "seam_or_mesh_defect": bool(open_internal_components),
        "topology_valid": bool(topology_valid),
        "requested_mouth_sample_y": float(requested_mouth_sample_y),
        "mouth_sample_y": float(mouth_sample_y),
        "mouth_aperture": mouth_aperture,
        "mouth_open": bool(mouth_open),
        "pinch_off_failure": bool(closed_voids),
        "void_linear_detection_limit": (
            float(grid_delta) if grid_delta is not None else None
        ),
        "void_area_detection_limit": detection_area,
        "mouth_pinched_off": bool(closed_voids and not open_void),
        "void_free": void_free,
        "center_surface_y": center_surface_y,
        "center_fill_height": float(center_surface_y - floor_y),
        "center_overburden": float(center_overburden),
        "field_surface_mean_y": float(np.mean(field_surface_ys)),
        "field_overburden_min": float(np.min(field_overburden)),
        "field_overburden_mean": float(np.mean(field_overburden)),
        "sampled_overburden_min": float(np.min(sampled_overburden)),
        "sampled_overburden_mean": float(np.mean(sampled_overburden)),
        "overburden_profile_x_min": float(profile_xs[np.argmin(profile_overburden)]),
        "overburden_min": float(np.min(profile_overburden)),
        "overburden_mean": float(np.mean(profile_overburden)),
        "overburden_nonuniformity": float(
            np.max(profile_overburden) - np.min(profile_overburden)
        ),
        "positive_overburden": bool(np.min(profile_overburden) > tolerance),
        "pre_cmp_recess": max(0.0, float(np.mean(field_surface_ys) - center_surface_y)),
        "component_count": len(summaries),
    }


def surface_height_at_x(nodes, lines, x):
    """Highest boundary intersection at x, or None when material is absent."""
    if nodes is None or lines is None or not len(nodes) or not len(lines):
        return None
    intersections = line_intersections_at_x(nodes, lines, x)
    return float(np.max(intersections)) if len(intersections) else None


def cmp_profile_metrics_2d(
    *,
    post_cu_nodes,
    post_cu_lines,
    post_stop_nodes,
    post_stop_lines,
    field_sample_xs,
    center_x,
    target_field_y,
    pre_stop_field_y,
    stop_initial_thickness,
    pre_cu_center_y=None,
    post_seed_nodes=None,
    post_seed_lines=None,
    post_barrier_nodes=None,
    post_barrier_lines=None,
    pre_substrate_field_y=None,
    post_substrate_nodes=None,
    post_substrate_lines=None,
    tolerance=1e-10,
):
    """Measure endpoint, residual films, dish, erosion, and hard CMP failures."""
    stop_heights = [
        surface_height_at_x(post_stop_nodes, post_stop_lines, x)
        for x in field_sample_xs
    ]
    stop_available = bool(stop_heights and all(y is not None for y in stop_heights))
    if not stop_available:
        return {
            "valid": False,
            "invalid_reason": "CMP stop layer is absent at a field sample",
            "endpoint_reached": False,
            "copper_endpoint_reached": False,
            "plated_cu_endpoint_reached": False,
            "seed_endpoint_reached": False,
            "barrier_endpoint_reached": False,
            "stop_layer_survives": False,
            "stop_layer_consumed": True,
            "dish": None,
            "field_erosion": None,
            "residual_field_cu_max": None,
            "residual_field_plated_cu_max": None,
            "residual_field_seed_max": None,
            "residual_field_barrier_max": None,
            "plug_survives": False,
        }

    stop_heights = np.asarray(stop_heights, dtype=float)
    stop_mean = float(np.mean(stop_heights))

    def sampled_heights(nodes, lines, fallback):
        heights = []
        for x, fallback_y in zip(field_sample_xs, fallback):
            material_y = surface_height_at_x(nodes, lines, x)
            heights.append(fallback_y if material_y is None else material_y)
        return np.asarray(heights, dtype=float)

    barrier_heights = sampled_heights(
        post_barrier_nodes, post_barrier_lines, stop_heights
    )
    seed_heights = sampled_heights(
        post_seed_nodes, post_seed_lines, barrier_heights
    )
    cu_heights = sampled_heights(post_cu_nodes, post_cu_lines, seed_heights)
    residual_barrier = np.maximum(0.0, barrier_heights - stop_heights)
    residual_seed = np.maximum(0.0, seed_heights - barrier_heights)
    residual_plated_cu = np.maximum(0.0, cu_heights - seed_heights)
    residual_cu = residual_plated_cu + residual_seed
    center_cu_y = surface_height_at_x(post_cu_nodes, post_cu_lines, center_x)
    plug_survives = center_cu_y is not None
    dish = max(0.0, stop_mean - center_cu_y) if plug_survives else None
    protrusion = max(0.0, center_cu_y - stop_mean) if plug_survives else None
    stop_loss = max(0.0, float(pre_stop_field_y - stop_mean))
    stop_survives = bool(stop_loss < stop_initial_thickness - tolerance)

    substrate_loss = None
    if pre_substrate_field_y is not None:
        post_substrate = [
            surface_height_at_x(post_substrate_nodes, post_substrate_lines, x)
            for x in field_sample_xs
        ]
        if all(value is not None for value in post_substrate):
            substrate_loss = max(
                0.0,
                float(pre_substrate_field_y - np.mean(post_substrate)),
            )

    plated_cu_clear = bool(np.max(residual_plated_cu) <= tolerance)
    seed_clear = bool(np.max(residual_seed) <= tolerance)
    copper_clear = bool(plated_cu_clear and seed_clear)
    barrier_clear = bool(np.max(residual_barrier) <= tolerance)
    valid = bool(stop_survives and plug_survives)
    return {
        "valid": valid,
        "invalid_reason": None if valid else (
            "CMP stop layer consumed" if not stop_survives else "Cu plug consumed"
        ),
        "endpoint_reached": bool(copper_clear and barrier_clear),
        "copper_endpoint_reached": copper_clear,
        "plated_cu_endpoint_reached": plated_cu_clear,
        "seed_endpoint_reached": seed_clear,
        "barrier_endpoint_reached": barrier_clear,
        "residual_field_cu_max": float(np.max(residual_cu)),
        "residual_field_cu_mean": float(np.mean(residual_cu)),
        "residual_field_plated_cu_max": float(np.max(residual_plated_cu)),
        "residual_field_seed_max": float(np.max(residual_seed)),
        "residual_field_barrier_max": float(np.max(residual_barrier)),
        "residual_field_barrier_mean": float(np.mean(residual_barrier)),
        "stop_field_mean_y": stop_mean,
        "stop_field_nonuniformity": float(np.max(stop_heights) - np.min(stop_heights)),
        "field_erosion": stop_loss,
        "stop_layer_survives": stop_survives,
        "stop_layer_consumed": not stop_survives,
        "center_cu_y": center_cu_y,
        "plug_survives": plug_survives,
        "dish": dish,
        "protrusion": protrusion,
        "cu_removed_at_center": (
            max(0.0, float(pre_cu_center_y - center_cu_y))
            if pre_cu_center_y is not None and plug_survives else None
        ),
        "substrate_loss": substrate_loss,
        "target_plane_error": float(stop_mean - target_field_y),
    }

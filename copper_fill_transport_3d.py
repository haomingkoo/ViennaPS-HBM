"""Explicit 3D geometry and metrics for the copper transport bridge."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict, deque

import numpy as np
import viennals as ls
import viennaps as ps

from process_config import PROCESS_CONFIG


D3 = ps.d3
LS3 = ls.d3
TRANSPORT_CONFIG = PROCESS_CONFIG["transport_3d"]
SECTOR_COUNT = int(TRANSPORT_CONFIG["sector_count"])
SECTOR_OFFSETS_DEG = tuple(TRANSPORT_CONFIG["sector_offsets_degrees"])
SECTOR_REGION_NAMES = ("floor", "lower_wall", "middle_wall", "upper_wall")
QUANTITIES = ("suppressor_flux", "coverage", "normal_velocity")
EXPECTED_MATERIAL_NAMES = ("Si", "SiO2", "TaN", "CuSeed", "Cu")
PLANE_TOLERANCE = TRANSPORT_CONFIG["plane_tolerance"]
PROTECTED_STACK_TOLERANCE = TRANSPORT_CONFIG["protected_stack_tolerance"]
MOUTH_MIN_RADIUS_FACTOR = TRANSPORT_CONFIG["mouth_min_radius_factor"]
MOUTH_MAX_RADIUS_FACTOR = TRANSPORT_CONFIG["mouth_max_radius_factor"]
SURFACE_MOUTH_MAX_RADIUS_FACTOR = TRANSPORT_CONFIG["surface_mouth_max_radius_factor"]
WALL_HEIGHT_MIN_FRACTION = TRANSPORT_CONFIG["wall_height_min_fraction"]
WALL_HEIGHT_MAX_FRACTION = TRANSPORT_CONFIG["wall_height_max_fraction"]
DIAGNOSTIC_Z_MARGIN = TRANSPORT_CONFIG["diagnostic_z_margin"]
FLOOR_HEIGHT = TRANSPORT_CONFIG["floor_height"]
FLOOR_RADIUS_FRACTION = TRANSPORT_CONFIG["floor_radius_fraction"]
LOWER_WALL_END_FRACTION = TRANSPORT_CONFIG["lower_wall_end_fraction"]
MIDDLE_WALL_END_FRACTION = TRANSPORT_CONFIG["middle_wall_end_fraction"]
WALL_RADIUS_FRACTION = TRANSPORT_CONFIG["wall_radius_fraction"]
FLUX_RATIO_TARGET = TRANSPORT_CONFIG["flux_ratio_target"]
VELOCITY_RATIO_TARGET = TRANSPORT_CONFIG["velocity_ratio_target"]


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def cu_seed_material():
    """Return the stable, named Cu seed identity used by saved artifacts."""
    return ps.MaterialRegistry.instance().registerMaterial("CuSeed")


def material_name(material):
    text = str(material)
    return text.split("'", 2)[1] if "'" in text else text


def material_stack(geometry):
    material_map = geometry.getMaterialMap()
    return tuple(
        material_map.getMaterialAtIdx(index)
        for index in range(geometry.getNumberOfLevelSets())
    )


def material_stack_names(geometry):
    return tuple(material_name(material) for material in material_stack(geometry))


def validate_material_stack(geometry):
    observed = material_stack_names(geometry)
    if observed != EXPECTED_MATERIAL_NAMES:
        raise ValueError(f"unexpected 3D material stack: {observed}")
    if ps.Material.Mask in material_stack(geometry):
        raise ValueError("temporary pattern mask remains in the 3D stack")
    return observed


def level_set_surface_meshes(geometry):
    """Extract separate triangle meshes without touching 2D proxy helpers."""
    meshes = []
    for level_set, material in zip(geometry.getLevelSets(), material_stack(geometry)):
        mesh = ls.Mesh()
        LS3.ToSurfaceMesh(level_set, mesh).apply()
        nodes = np.asarray(mesh.getNodes(), dtype=float)
        triangles = np.asarray(mesh.getTriangles(), dtype=int)
        if nodes.ndim != 2 or nodes.shape[1] != 3:
            raise ValueError("3D level-set surface is not an Nx3 node array")
        if triangles.size == 0:
            triangles = np.empty((0, 3), dtype=int)
        elif triangles.ndim != 2 or triangles.shape[1] != 3:
            raise ValueError("3D level-set surface is not a triangle mesh")
        meshes.append(
            {
                "material": material,
                "material_name": material_name(material),
                "nodes": nodes,
                "triangles": triangles,
            }
        )
    return meshes


def _mesh_sha256(mesh):
    digest = hashlib.sha256()
    digest.update(np.asarray(mesh["nodes"], dtype=np.float64).tobytes())
    digest.update(np.asarray(mesh["triangles"], dtype=np.int64).tobytes())
    digest.update(mesh["material_name"].encode())
    return digest.hexdigest()


def build_seeded_stack(case):
    geometry_spec = case["geometry"]
    numerics = case["numerics"]
    geometry = D3.Domain(
        gridDelta=float(numerics["grid_delta"]),
        xExtent=float(geometry_spec["x_extent"]),
        yExtent=float(geometry_spec["lateral_y_extent"]),
        boundary=ps.BoundaryType.REFLECTIVE_BOUNDARY,
    )
    D3.MakeHole(
        domain=geometry,
        holeRadius=float(geometry_spec["radius"]),
        holeDepth=float(geometry_spec["depth"]),
        maskHeight=float(geometry_spec["mask_height"]),
        holeShape=ps.HoleShape.FULL,
    ).apply()
    geometry.removeMaterial(ps.Material.Mask)
    if ps.Material.Mask in material_stack(geometry):
        raise ValueError("removeMaterial did not strip the temporary mask")

    layers = case["layers"]
    for material, thickness in (
        (ps.Material.SiO2, layers["liner"]),
        (ps.Material.TaN, layers["barrier"]),
        (cu_seed_material(), layers["seed"]),
    ):
        geometry.duplicateTopLevelSet(material)
        D3.Process(
            geometry,
            D3.IsotropicProcess(rate=float(thickness)),
            1.0,
        ).apply()
    geometry.duplicateTopLevelSet(ps.Material.Cu)
    validate_material_stack(geometry)
    return geometry


def boundary_contract(geometry):
    conditions = tuple(geometry.getBoundaryConditions())
    expected = (
        ps.BoundaryType.REFLECTIVE_BOUNDARY,
        ps.BoundaryType.REFLECTIVE_BOUNDARY,
        ps.BoundaryType.INFINITE_BOUNDARY,
    )
    return {
        "observed": [str(value) for value in conditions],
        "expected": [str(value) for value in expected],
        "pass": conditions == expected,
    }


def triangle_component_count(triangles):
    triangles = np.asarray(triangles, dtype=int)
    if not len(triangles):
        return 0
    node_to_triangles = defaultdict(list)
    for index, triangle in enumerate(triangles):
        for node in triangle:
            node_to_triangles[int(node)].append(index)
    unseen = set(range(len(triangles)))
    components = 0
    while unseen:
        components += 1
        queue = deque([unseen.pop()])
        while queue:
            triangle_index = queue.popleft()
            for node in triangles[triangle_index]:
                for neighbor in node_to_triangles[int(node)]:
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        queue.append(neighbor)
    return components


def _plane_triangle_points(
    nodes,
    triangles,
    plane_z,
    tolerance=PLANE_TOLERANCE,
):
    """Return interpolated points where a triangle surface crosses z=plane_z."""
    points = []
    for triangle in np.asarray(triangles, dtype=int):
        vertices = nodes[triangle]
        if (
            plane_z < np.min(vertices[:, 2]) - tolerance
            or plane_z > np.max(vertices[:, 2]) + tolerance
        ):
            continue
        crossings = []
        for first, second in ((0, 1), (1, 2), (2, 0)):
            a = vertices[first]
            b = vertices[second]
            da = a[2] - plane_z
            db = b[2] - plane_z
            if abs(da) <= tolerance:
                crossings.append(a)
            if da * db < 0.0:
                fraction = (plane_z - a[2]) / (b[2] - a[2])
                crossings.append(a + fraction * (b - a))
        if len(crossings) >= 2:
            points.extend(crossings[:2])
    if not points:
        return np.empty((0, 3), dtype=float)
    values = np.asarray(points, dtype=float)
    rounded = np.round(values / max(tolerance, 1e-12)).astype(np.int64)
    _, indices = np.unique(rounded, axis=0, return_index=True)
    return values[np.sort(indices)]


def _sector_indices(x, y, offset_degrees=0.0):
    offset = math.radians(float(offset_degrees))
    angles = np.mod(np.arctan2(y, x) - offset, 2.0 * math.pi)
    width = 2.0 * math.pi / SECTOR_COUNT
    return np.minimum((angles / width).astype(int), SECTOR_COUNT - 1)


def reference_from_meshes(meshes, case):
    if tuple(mesh.get("material_name") for mesh in meshes) != EXPECTED_MATERIAL_NAMES:
        raise ValueError(
            "saved 3D mesh stack does not match the five-material contract"
        )
    seed_mesh = meshes[-2]
    nodes = seed_mesh["nodes"]
    triangles = seed_mesh["triangles"]
    radius = np.hypot(nodes[:, 0], nodes[:, 1])
    geometry_spec = case["geometry"]
    field_band = geometry_spec["field_radius_band"]
    field_mask = (radius >= field_band[0]) & (radius <= field_band[1])
    if np.count_nonzero(field_mask) < 16:
        raise ValueError("seed surface has too few far-field reference nodes")
    field_z = float(np.median(nodes[field_mask, 2]))
    center_mask = radius <= MOUTH_MIN_RADIUS_FACTOR * float(geometry_spec["radius"])
    if np.count_nonzero(center_mask) < 8:
        raise ValueError("seed surface has too few floor reference nodes")
    floor_z = float(np.min(nodes[center_mask, 2]))
    height = field_z - floor_z
    if height <= 0.0:
        raise ValueError("post-seed cavity height is not positive")
    if not math.isclose(
        height,
        float(geometry_spec["depth"]),
        rel_tol=0.0,
        abs_tol=2.0 * float(case["numerics"]["grid_delta"]),
    ):
        raise ValueError("measured post-seed H differs from the declared tier")

    mouth_z = field_z - float(geometry_spec["mouth_offset"])
    mouth_points = _plane_triangle_points(nodes, triangles, mouth_z)
    if not len(mouth_points):
        raise ValueError("seed surface has no mouth-plane intersection")
    mouth_radii = np.hypot(mouth_points[:, 0], mouth_points[:, 1])
    mouth_points = mouth_points[
        (mouth_radii > MOUTH_MIN_RADIUS_FACTOR * float(geometry_spec["radius"]))
        & (mouth_radii < MOUTH_MAX_RADIUS_FACTOR * float(geometry_spec["radius"]))
    ]
    mouth_radii = np.hypot(mouth_points[:, 0], mouth_points[:, 1])
    if not len(mouth_radii):
        raise ValueError("mouth-plane intersection does not resolve the aperture")
    mouth_sector = _sector_indices(mouth_points[:, 0], mouth_points[:, 1], 0.0)
    mouth_radius_by_sector = []
    for sector in range(SECTOR_COUNT):
        values = mouth_radii[mouth_sector == sector]
        if not len(values):
            raise ValueError(f"mouth aperture sector {sector} is empty")
        mouth_radius_by_sector.append(float(np.min(values)))

    wall_mask = (
        (nodes[:, 2] >= floor_z + WALL_HEIGHT_MIN_FRACTION * height)
        & (nodes[:, 2] <= floor_z + WALL_HEIGHT_MAX_FRACTION * height)
        & (radius < MOUTH_MAX_RADIUS_FACTOR * float(geometry_spec["radius"]))
    )
    wall_radii = radius[wall_mask]
    if not len(wall_radii):
        raise ValueError("post-seed cylindrical wall is unresolved")
    component_count = triangle_component_count(triangles)
    if component_count != 1:
        raise ValueError(
            f"CuSeed surface must be connected; found {component_count} components"
        )
    minimum_mouth_radius = min(mouth_radius_by_sector)
    reference = {
        "coordinate_convention": {
            "height_axis": "z=coordinate[:,2]",
            "radial_coordinate": "sqrt(x^2+y^2)",
        },
        "field_z": field_z,
        "floor_z": floor_z,
        "height_H": height,
        "mouth_z": mouth_z,
        "mouth_radius_minimum": minimum_mouth_radius,
        "mouth_radius_median": float(np.median(mouth_radii)),
        "mouth_radius_maximum": float(np.max(mouth_radii)),
        "mouth_radius_by_sector": mouth_radius_by_sector,
        "minimum_wall_radius": float(np.min(wall_radii)),
        "maximum_wall_radius": float(np.max(wall_radii)),
        "kinematic_threshold_H_over_a_mouth": height / minimum_mouth_radius,
        "kinematic_sensitivity_H_over_a_min_wall": height / float(np.min(wall_radii)),
        "seed_surface_triangle_component_count": component_count,
        "seed_surface_connected": True,
        "cavity_open_at_mouth": True,
        "seed_mesh_sha256": _mesh_sha256(seed_mesh),
        "field_radius_band": list(field_band),
    }
    return reference


def reference_from_geometry(geometry, case):
    meshes = level_set_surface_meshes(geometry)
    validate_material_stack(geometry)
    return reference_from_meshes(meshes, case), meshes


def surface_structure(mesh, reference):
    nodes = np.asarray(mesh["nodes"], dtype=float)
    triangles = np.asarray(mesh["triangles"], dtype=int)
    mouth = _plane_triangle_points(nodes, triangles, float(reference["mouth_z"]))
    radii = np.hypot(mouth[:, 0], mouth[:, 1]) if len(mouth) else np.asarray([])
    aperture = radii[
        (radii > MOUTH_MIN_RADIUS_FACTOR * float(reference["mouth_radius_median"]))
        & (
            radii
            < SURFACE_MOUTH_MAX_RADIUS_FACTOR * float(reference["mouth_radius_maximum"])
        )
    ]
    aperture_points = (
        mouth[
            (radii > MOUTH_MIN_RADIUS_FACTOR * float(reference["mouth_radius_median"]))
            & (
                radii
                < SURFACE_MOUTH_MAX_RADIUS_FACTOR
                * float(reference["mouth_radius_maximum"])
            )
        ]
        if len(mouth)
        else np.empty((0, 3), dtype=float)
    )
    sectors = (
        set(_sector_indices(aperture_points[:, 0], aperture_points[:, 1], 0.0).tolist())
        if len(aperture_points)
        else set()
    )
    components = triangle_component_count(triangles)
    return {
        "node_count": int(len(nodes)),
        "triangle_count": int(len(triangles)),
        "triangle_component_count": components,
        "mouth_intersection_point_count": int(len(aperture)),
        "mouth_sector_count": len(sectors),
        "cavity_open": bool(len(aperture) and len(sectors) == SECTOR_COUNT),
        "unexpected_sealed_component": bool(components != 1),
    }


def protected_stack_delta(before, after, tolerance=PROTECTED_STACK_TOLERANCE):
    if len(before) != len(after):
        return {"survives": False, "reason": "protected level-set count changed"}
    maximum_node_delta = 0.0
    for prior, current in zip(before, after):
        if prior["material_name"] != current["material_name"]:
            return {"survives": False, "reason": "protected material order changed"}
        if prior["nodes"].shape != current["nodes"].shape:
            return {"survives": False, "reason": "protected node shape changed"}
        if prior["triangles"].shape != current["triangles"].shape:
            return {"survives": False, "reason": "protected triangle shape changed"}
        if not np.array_equal(prior["triangles"], current["triangles"]):
            return {"survives": False, "reason": "protected triangles changed"}
        if prior["nodes"].size:
            maximum_node_delta = max(
                maximum_node_delta,
                float(np.max(np.abs(prior["nodes"] - current["nodes"]))),
            )
    return {
        "survives": bool(maximum_node_delta <= tolerance),
        "max_node_delta": maximum_node_delta,
        "tolerance": tolerance,
    }


def region_masks(coordinates, material_ids, plating_material_ids, reference, offset):
    coordinates = np.asarray(coordinates, dtype=float)
    material_ids = np.asarray(material_ids, dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        raise ValueError("3D diagnostic coordinates must have shape Nx3")
    if material_ids.shape != (len(coordinates),):
        raise ValueError("diagnostic material IDs do not align")
    if not np.all(np.isfinite(coordinates)) or not np.all(np.isfinite(material_ids)):
        raise ValueError("diagnostic coordinates/material IDs contain nonfinite values")
    plating = np.isin(material_ids, np.asarray(plating_material_ids, dtype=float))
    x, y, z = coordinates[:, 0], coordinates[:, 1], coordinates[:, 2]
    radius = np.hypot(x, y)
    sector = _sector_indices(x, y, offset)
    floor_z = float(reference["floor_z"])
    field_z = float(reference["field_z"])
    height = float(reference["height_H"])
    a = float(reference["mouth_radius_minimum"])
    wall_minimum = float(reference["minimum_wall_radius"])
    envelope = (
        plating
        & (z >= floor_z - DIAGNOSTIC_Z_MARGIN)
        & (z <= field_z + DIAGNOSTIC_Z_MARGIN)
        & (radius <= MOUTH_MAX_RADIUS_FACTOR * float(reference["mouth_radius_maximum"]))
    )
    bases = {
        "floor": envelope
        & (z <= floor_z + FLOOR_HEIGHT)
        & (radius <= FLOOR_RADIUS_FRACTION * a),
        "lower_wall": (
            envelope
            & (z >= floor_z + WALL_HEIGHT_MIN_FRACTION * height)
            & (z < floor_z + LOWER_WALL_END_FRACTION * height)
            & (radius >= WALL_RADIUS_FRACTION * wall_minimum)
        ),
        "middle_wall": (
            envelope
            & (z >= floor_z + LOWER_WALL_END_FRACTION * height)
            & (z < floor_z + MIDDLE_WALL_END_FRACTION * height)
            & (radius >= WALL_RADIUS_FRACTION * wall_minimum)
        ),
        "upper_wall": (
            envelope
            & (z >= floor_z + MIDDLE_WALL_END_FRACTION * height)
            & (z < floor_z + WALL_HEIGHT_MAX_FRACTION * height)
            & (radius >= WALL_RADIUS_FRACTION * wall_minimum)
        ),
    }
    masks = {}
    for name, base in bases.items():
        masks[name] = base
        for sector_index in range(SECTOR_COUNT):
            masks[f"{name}_sector_{sector_index}"] = base & (sector == sector_index)
    field_band = reference["field_radius_band"]
    masks["field"] = (
        plating
        & (z >= field_z - DIAGNOSTIC_Z_MARGIN)
        & (radius >= float(field_band[0]))
        & (radius <= float(field_band[1]))
    )
    masks["mouth_shoulder"] = (
        plating
        & (z >= field_z - DIAGNOSTIC_Z_MARGIN)
        & (radius >= WALL_RADIUS_FRACTION * wall_minimum)
        & (radius < float(field_band[0]))
    )
    return masks


def _statistics(values, mask):
    selected = np.asarray(values, dtype=float)[mask]
    if not len(selected):
        return {"mean": None, "q10": None, "q50": None, "q90": None}
    quantiles = np.quantile(selected, (0.1, 0.5, 0.9))
    return {
        "mean": float(np.mean(selected)),
        "q10": float(quantiles[0]),
        "q50": float(quantiles[1]),
        "q90": float(quantiles[2]),
    }


def region_statistics(
    coordinates,
    material_ids,
    suppressor_flux,
    coverage,
    velocity,
    plating_material_ids,
    reference,
    offset,
):
    arrays = {
        "suppressor_flux": np.asarray(suppressor_flux, dtype=float),
        "coverage": np.asarray(coverage, dtype=float),
        "normal_velocity": np.asarray(velocity, dtype=float),
    }
    if any(values.shape != (len(coordinates),) for values in arrays.values()):
        raise ValueError("diagnostic response arrays do not align")
    if any(not np.all(np.isfinite(values)) for values in arrays.values()):
        raise ValueError("diagnostic response arrays contain nonfinite values")
    masks = region_masks(
        coordinates, material_ids, plating_material_ids, reference, offset
    )
    regions = {
        name: {
            "point_count": int(np.count_nonzero(mask)),
            "plating_only": True,
            **{
                quantity: _statistics(values, mask)
                for quantity, values in arrays.items()
            },
        }
        for name, mask in masks.items()
    }
    return regions, masks


def transport_decision(regions, reference, minimum_sector_points, guards):
    required_valid = True
    for region in SECTOR_REGION_NAMES:
        for sector in range(SECTOR_COUNT):
            item = regions.get(f"{region}_sector_{sector}", {})
            if item.get("point_count", 0) < minimum_sector_points:
                required_valid = False
            if item.get("plating_only") is not True:
                required_valid = False
            for quantity in QUANTITIES:
                stats = item.get(quantity, {})
                if any(
                    not _number(stats.get(key)) for key in ("mean", "q10", "q50", "q90")
                ):
                    required_valid = False

    flux_ratios = []
    coverage_margins = []
    lower_velocity_ratios = []
    floor_velocities = []
    middle_upper_velocities = []
    if required_valid:
        for sector in range(SECTOR_COUNT):
            floor = regions[f"floor_sector_{sector}"]
            lower = regions[f"lower_wall_sector_{sector}"]
            floor_flux = floor["suppressor_flux"]["mean"]
            lower_flux = lower["suppressor_flux"]["mean"]
            floor_velocity = floor["normal_velocity"]["mean"]
            lower_velocity = lower["normal_velocity"]["mean"]
            flux_ratios.append(floor_flux / lower_flux if lower_flux > 0.0 else None)
            coverage_margins.append(
                lower["coverage"]["mean"] - floor["coverage"]["mean"]
            )
            lower_velocity_ratios.append(
                floor_velocity / lower_velocity if lower_velocity > 0.0 else None
            )
            floor_velocities.append(floor_velocity)
            middle_upper_velocities.extend(
                [
                    regions[f"middle_wall_sector_{sector}"]["normal_velocity"]["mean"],
                    regions[f"upper_wall_sector_{sector}"]["normal_velocity"]["mean"],
                ]
            )
    minimum_floor_velocity: float | None = (
        float(min(floor_velocities)) if required_valid else None
    )
    fastest_middle_upper: float | None = (
        float(max(middle_upper_velocities)) if required_valid else None
    )
    wall_velocities = (
        [
            regions[f"{region}_sector_{sector}"]["normal_velocity"]["mean"]
            for region in ("lower_wall", "middle_wall", "upper_wall")
            for sector in range(SECTOR_COUNT)
        ]
        if required_valid
        else []
    )
    fastest_wall: float | None = (
        float(max(wall_velocities)) if wall_velocities else None
    )
    realized_h_over_a_ratio = (
        minimum_floor_velocity / fastest_wall
        if minimum_floor_velocity is not None
        and fastest_wall is not None
        and fastest_wall > 0.0
        else None
    )
    conditions = {
        "all_required_sectors_finite_and_populated": required_valid,
        "diagnostic_balance_valid": guards.get("diagnostic_balance_valid") is True,
        "analytic_parity_valid": guards.get("analytic_parity_valid") is True,
        "full_cylinder_and_stack_valid": guards.get("full_cylinder_and_stack_valid")
        is True,
        "protected_stack_survives": guards.get("protected_stack_survives") is True,
        "cavity_remains_open_without_sealed_component": guards.get(
            "cavity_remains_open_without_sealed_component"
        )
        is True,
        "floor_to_each_lower_flux_ratio_strictly_below_0p95": bool(
            flux_ratios
            and all(
                _number(value) and value < FLUX_RATIO_TARGET for value in flux_ratios
            )
        ),
        "floor_coverage_strictly_below_each_lower_wall": bool(
            coverage_margins and all(value > 0.0 for value in coverage_margins)
        ),
        "floor_to_each_lower_velocity_ratio_strictly_above_1p05": bool(
            lower_velocity_ratios
            and all(
                _number(value) and value > VELOCITY_RATIO_TARGET
                for value in lower_velocity_ratios
            )
        ),
        "minimum_floor_velocity_above_every_middle_upper_sector": bool(
            minimum_floor_velocity is not None
            and fastest_middle_upper is not None
            and minimum_floor_velocity > fastest_middle_upper
        ),
        "floor_outruns_fastest_wall_by_H_over_a": bool(
            realized_h_over_a_ratio is not None
            and realized_h_over_a_ratio
            > float(reference["kinematic_threshold_H_over_a_mouth"])
        ),
    }
    return {
        "pass": all(conditions.values()),
        "conditions": conditions,
        "floor_to_lower_flux_ratios": flux_ratios,
        "lower_minus_floor_coverage": coverage_margins,
        "floor_to_lower_velocity_ratios": lower_velocity_ratios,
        "minimum_floor_minus_fastest_middle_upper_velocity": (
            minimum_floor_velocity - fastest_middle_upper
            if minimum_floor_velocity is not None and fastest_middle_upper is not None
            else None
        ),
        "realized_min_floor_to_fastest_wall_velocity_ratio": realized_h_over_a_ratio,
        "required_H_over_a_mouth": reference["kinematic_threshold_H_over_a_mouth"],
        "minimum_sector_point_count_required": minimum_sector_points,
    }


def equilibrium_coverage(adsorption, deactivation_rate, active_rate, suppressed_rate):
    adsorption = float(adsorption)
    active_rate = float(active_rate)
    suppressed_rate = float(suppressed_rate)
    deactivation_rate = float(deactivation_rate)
    if adsorption <= 0.0:
        return 0.0
    deactivation_active = deactivation_rate * active_rate
    quadratic = deactivation_rate * (active_rate - suppressed_rate)
    scale = max(adsorption, deactivation_active)
    if scale <= 0.0:
        return 1.0
    linear = adsorption / scale + deactivation_active / scale
    constant = adsorption / scale
    normalized_quadratic = quadratic / scale
    if normalized_quadratic <= np.finfo(float).eps * linear:
        return float(np.clip(constant / linear, 0.0, 1.0))
    discriminant = max(0.0, linear * linear - 4.0 * normalized_quadratic * constant)
    denominator = linear + math.sqrt(discriminant)
    return (
        1.0
        if denominator <= 0.0
        else float(np.clip(2.0 * constant / denominator, 0.0, 1.0))
    )


def analytic_diagnostics(
    flux,
    material_ids,
    plating_material_ids,
    *,
    pi_a,
    deactivation_rate,
    active_rate,
    suppressed_rate,
):
    flux = np.asarray(flux, dtype=float)
    material_ids = np.asarray(material_ids, dtype=float)
    if flux.shape != material_ids.shape:
        raise ValueError("flux and material IDs do not align")
    plating = np.isin(material_ids, np.asarray(plating_material_ids, dtype=float))
    adsorption = float(pi_a) * float(deactivation_rate) * float(active_rate) * flux
    local_active = np.where(plating, float(active_rate), 0.0)
    local_suppressed = np.where(plating, float(suppressed_rate), 0.0)
    coverage = np.asarray(
        [
            equilibrium_coverage(a, deactivation_rate, va, vs)
            for a, va, vs in zip(adsorption, local_active, local_suppressed)
        ]
    )
    velocity = local_active * (1.0 - coverage) + local_suppressed * coverage
    adsorption_term = adsorption * (1.0 - coverage)
    deactivation_term = float(deactivation_rate) * velocity * coverage
    scale = np.maximum.reduce(
        [
            np.abs(adsorption_term),
            np.abs(deactivation_term),
            np.full_like(adsorption_term, np.finfo(float).eps),
        ]
    )
    return {
        "coverage": coverage,
        "velocity": velocity,
        "adsorption_term": adsorption_term,
        "deactivation_term": deactivation_term,
        "relative_balance_error": float(
            np.max(np.abs(adsorption_term - deactivation_term) / scale)
        ),
    }


def analytic_parity(raw, model, plating_material_ids):
    pi_a = (
        float(model["adsorption_strength"])
        * float(model["suppressor_sticking_probability"])
        / (float(model["deactivation_rate"]) * float(model["active_deposition_rate"]))
    )
    predicted = analytic_diagnostics(
        raw["suppressor_flux"],
        raw["material_ids"],
        plating_material_ids,
        pi_a=pi_a,
        deactivation_rate=model["deactivation_rate"],
        active_rate=model["active_deposition_rate"],
        suppressed_rate=model["suppressed_deposition_rate"],
    )
    return {
        "coverage_max_abs_error": float(
            np.max(np.abs(predicted["coverage"] - raw["coverage"]))
        ),
        "velocity_max_abs_error": float(
            np.max(np.abs(predicted["velocity"] - raw["velocity"]))
        ),
        "adsorption_term_max_abs_error": float(
            np.max(np.abs(predicted["adsorption_term"] - raw["adsorption_term"]))
        ),
        "deactivation_term_max_abs_error": float(
            np.max(np.abs(predicted["deactivation_term"] - raw["deactivation_term"]))
        ),
        "analytic_relative_balance_error": predicted["relative_balance_error"],
    }

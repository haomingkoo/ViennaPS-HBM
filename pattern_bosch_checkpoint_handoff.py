"""Verified surface-mesh handoff from Gate-0 into a process domain."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import viennals as ls
import viennaps as ps

import foundation_pattern_bosch_gate0 as gate0
import traveler_metrics as tm


SCALAR_CTQS = (
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


def load_verified_checkpoint(path, *, expected_sha256=None):
    """Load a Gate-0 checkpoint after validating its self-bound case payload."""
    path = Path(path)
    if expected_sha256 is not None and gate0.file_sha256(path) != expected_sha256:
        raise ValueError("checkpoint file hash differs from the successful row")
    with np.load(path, allow_pickle=False) as snapshot:
        payload = gate0.strict_json_loads(str(gate0._scalar(
            snapshot, "case_payload_json"
        )))
        case = {
            **payload,
            "case_id": gate0.case_id(payload),
            "case_payload_sha256": gate0.canonical_sha256(payload),
        }
        arrays = {key: np.asarray(snapshot[key]).copy() for key in snapshot.files}
    errors = gate0.validate_checkpoint(path, case)
    if errors:
        raise ValueError("invalid Gate-0 checkpoint: " + "; ".join(errors))
    return case, arrays


def surface_mesh(nodes, lines):
    mesh = ls.Mesh()
    for node in np.asarray(nodes, dtype=float):
        point = np.zeros(3, dtype=float)
        point[: min(3, len(node))] = node[:3]
        mesh.insertNextNode(point)
    for line in np.asarray(lines, dtype=int):
        mesh.insertNextLine(line)
    return mesh


def reconstruct_silicon_domain(case, silicon_nodes, silicon_lines):
    """Rebuild the saved silicon boundary on the original Gate-0 grid."""
    geometry_spec = case["geometry"]
    grid_delta = float(case["numerics"]["grid_delta"])
    template = ps.Domain(
        gridDelta=grid_delta,
        xExtent=float(geometry_spec["x_extent"]),
        yExtent=float(geometry_spec["y_extent"]),
    )
    silicon = ls.Domain(template.getGrid())
    ls.FromSurfaceMesh(
        silicon,
        surface_mesh(silicon_nodes, silicon_lines),
    ).apply()
    geometry = ps.Domain()
    geometry.insertNextLevelSetAsMaterial(silicon, ps.Material.Si)
    if geometry.getNumberOfLevelSets() != 1:
        raise ValueError("reconstructed domain does not contain exactly one silicon level set")
    return geometry


def etch_metrics(nodes, lines, case):
    floor_y = float(np.min(np.asarray(nodes, dtype=float)[:, 1]))
    return tm.etch_profile_metrics_2d(
        nodes,
        lines,
        surface_y=0.0,
        floor_y=floor_y,
        target_cd=float(case["target"]["opening_cd"]),
        max_radius=float(case["target"]["opening_cd"]),
    )


def etch_gate(metrics, case):
    target = case["target"]
    return bool(
        abs(metrics["depth"] - target["etch_depth"])
        <= target["depth_tolerance"]
        and metrics["max_cd_error"] <= target["max_width_error"]
        and metrics["max_bow"] <= target["max_wall_bulge"]
    )


def compare_checkpoint_handoff(path, *, expected_sha256=None):
    """Reconstruct and independently compare the Gate-0 silicon boundary."""
    case, checkpoint = load_verified_checkpoint(
        path, expected_sha256=expected_sha256
    )
    original_nodes = checkpoint["silicon_nodes"]
    original_lines = checkpoint["silicon_lines"]
    geometry = reconstruct_silicon_domain(
        case, original_nodes, original_lines
    )
    rebuilt = tm.material_region_mesh(geometry, ps.Material.Si)
    original_metrics = etch_metrics(original_nodes, original_lines, case)
    rebuilt_metrics = etch_metrics(rebuilt["nodes"], rebuilt["lines"], case)
    ctq_absolute_deltas = {
        name: abs(float(rebuilt_metrics[name]) - float(original_metrics[name]))
        for name in SCALAR_CTQS
    }
    original_to_rebuilt = tm.point_to_polyline_distances(
        original_nodes, rebuilt["nodes"], rebuilt["lines"]
    )
    rebuilt_to_original = tm.point_to_polyline_distances(
        rebuilt["nodes"], original_nodes, original_lines
    )
    maximum_surface_distance = float(max(
        np.max(original_to_rebuilt),
        np.max(rebuilt_to_original),
    ))
    grid_delta = float(case["numerics"]["grid_delta"])
    surface_tolerance = 0.25 * grid_delta
    ctq_tolerances = {
        "depth": 0.25 * grid_delta,
        "cd_top": 0.50 * grid_delta,
        "cd_middle": 0.50 * grid_delta,
        "cd_bottom": 0.50 * grid_delta,
        "cd_min": 0.50 * grid_delta,
        "cd_max": 0.50 * grid_delta,
        "max_cd_error": 0.50 * grid_delta,
        "sidewall_angle_deg": 0.10,
        "max_bow": 0.50 * grid_delta,
        "scallop_rms": 0.50 * grid_delta,
    }
    ctq_tolerance_pass = {
        name: ctq_absolute_deltas[name] <= tolerance
        for name, tolerance in ctq_tolerances.items()
    }
    maximum_normalized_ctq_delta = max(
        ctq_absolute_deltas[name] / tolerance
        for name, tolerance in ctq_tolerances.items()
    )
    original_pass = etch_gate(original_metrics, case)
    rebuilt_pass = etch_gate(rebuilt_metrics, case)
    return {
        "case_id": case["case_id"],
        "rng_seed": case["rng_seed"],
        "checkpoint_path": str(Path(path)),
        "checkpoint_sha256": gate0.file_sha256(path),
        "grid_delta": grid_delta,
        "surface_distance_tolerance": surface_tolerance,
        "maximum_surface_distance": maximum_surface_distance,
        "ctq_absolute_deltas": ctq_absolute_deltas,
        "ctq_tolerances": ctq_tolerances,
        "ctq_tolerance_pass": ctq_tolerance_pass,
        "maximum_normalized_ctq_delta": maximum_normalized_ctq_delta,
        "original_etch_pass": original_pass,
        "reconstructed_etch_pass": rebuilt_pass,
        "gate_flip": original_pass != rebuilt_pass,
        "accepted": bool(
            maximum_surface_distance <= surface_tolerance
            and all(ctq_tolerance_pass.values())
            and original_pass == rebuilt_pass
        ),
        "original_metrics": original_metrics,
        "reconstructed_metrics": rebuilt_metrics,
        "geometry": geometry,
    }

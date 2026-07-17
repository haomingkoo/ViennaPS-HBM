"""Frozen full-2D pattern/Bosch Gate-0 campaign.

This campaign qualifies geometry representation, selected-cycle metrics, mask
erosion response, and numerical bridges.  It can authorize only a later broad
pattern/Bosch screen; it cannot authorize a recipe or process window.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import math
import os
from pathlib import Path
import time
import traceback

import numpy as np
import viennals._core as ls_core
import viennaps as ps
import viennaps._core as ps_core

import foundation_metric_audit as foundation
import traveler_metrics as tm
import tsv_process as tp


ps.Logger.setLogLevel(ps.LogLevel.ERROR)

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_pattern_bosch_gate0_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/pattern_bosch_gate0_rows.jsonl"
)
MAX_WORKERS = 2
EXPECTED_LABELS = ("full-traveler", "critical-review")
EXPECTED_SEEDS = (61000, 62000, 63000, 64000)
EXPECTED_DESIGNS = {
    "quarter_reference_fine": {
        "role": "quarter_reference",
        "hole_shape": "QUARTER",
        "grid_delta": 0.00125,
        "rays_per_point": 2000,
        "mask_ion_rate": 0.0,
    },
    "full_reference_fine": {
        "role": "full_reference",
        "hole_shape": "FULL",
        "grid_delta": 0.00125,
        "rays_per_point": 2000,
        "mask_ion_rate": 0.0,
    },
    "full_grid_bridge": {
        "role": "grid_bridge",
        "hole_shape": "FULL",
        "grid_delta": 0.0025,
        "rays_per_point": 2000,
        "mask_ion_rate": 0.0,
    },
    "full_erosion_m0p01": {
        "role": "erosion_challenge",
        "hole_shape": "FULL",
        "grid_delta": 0.00125,
        "rays_per_point": 2000,
        "mask_ion_rate": -0.01,
    },
    "full_erosion_m0p02": {
        "role": "erosion_challenge",
        "hole_shape": "FULL",
        "grid_delta": 0.00125,
        "rays_per_point": 2000,
        "mask_ion_rate": -0.02,
    },
    "full_erosion_m0p04": {
        "role": "erosion_challenge",
        "hole_shape": "FULL",
        "grid_delta": 0.00125,
        "rays_per_point": 2000,
        "mask_ion_rate": -0.04,
    },
}
EXPECTED_TOLERANCES = {
    "depth": 0.02,
    "cd_top": 0.01,
    "cd_middle": 0.01,
    "cd_bottom": 0.01,
    "max_cd_error": 0.01,
    "max_bow": 0.005,
    "scallop_rms": 0.0025,
    "mask_remaining_height": 0.01,
}
EXPECTED_TARGET = {
    "opening_cd": 0.3,
    "mask_height": 0.3,
    "etch_depth": 1.25,
    "depth_tolerance": 0.1,
    "max_width_error": 0.06,
    "max_wall_bulge": 0.03,
    "resolved_mask_cells_strict": 2.0,
}
EXPECTED_REFERENCE_RECIPE = {
    "source_path": (
        ".scratch/full-traveler-autoresearch/"
        "foundation_bosch_high_fidelity_manifest.json"
    ),
    "recipe_canonical_sha256": (
        "0c94e62d79254d3d6a018be8f386f985662260ff01305936b0ff30e506b6c1a8"
    ),
}
CASE_FIELDS = (
    "manifest_version",
    "campaign",
    "labels",
    "arm",
    "role",
    "geometry",
    "recipe",
    "selected_cycle",
    "numerics",
    "target",
    "rng_seed",
    "rng_stream",
    "rng_policy",
    "runtime_fingerprint",
    "reference_recipe",
    "authority",
    "provenance",
)
CHECKPOINT_KEYS = {
    "schema_version",
    "case_id",
    "case_payload_json",
    "case_payload_sha256",
    "runtime_fingerprint_json",
    "selected_cycle",
    "simulation_dimension",
    "arm",
    "hole_shape",
    "grid_delta",
    "rays_per_point",
    "rng_seed",
    "initial_mask_nodes",
    "initial_mask_lines",
    "silicon_nodes",
    "silicon_lines",
    "mask_nodes",
    "mask_lines",
}


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def strict_json_loads(value: str):
    def reject_constant(constant):
        raise ValueError(f"non-standard JSON constant: {constant}")

    return json.loads(value, parse_constant=reject_constant)


def file_sha256(path) -> str:
    return foundation.file_sha256(path)


def runtime_fingerprint(project_root=ROOT) -> dict:
    root = Path(project_root)
    return {
        "runner_sha256": file_sha256(root / Path(__file__).name),
        "foundation_sha256": file_sha256(root / "foundation_metric_audit.py"),
        "traveler_metrics_sha256": file_sha256(root / "traveler_metrics.py"),
        "tsv_process_sha256": file_sha256(root / "tsv_process.py"),
        "viennaps_binary_sha256": file_sha256(ps_core.__file__),
        "viennals_binary_sha256": file_sha256(ls_core.__file__),
    }


def case_payload(row) -> dict:
    return {field: row.get(field) for field in CASE_FIELDS}


def case_id(payload) -> str:
    return canonical_sha256(payload)[:16]


def evidence_origin() -> dict:
    return {
        "mode": "executed_pattern_bosch_gate0",
        "selected_cycle_checkpoint": True,
        "shared_base_seed_labels_across_arms": True,
        "pointwise_common_random_numbers_across_arms": False,
        "full_vs_quarter_common_random_numbers": False,
        "recipe_authority": False,
    }


def checkpoint_directory(output=DEFAULT_OUTPUT) -> Path:
    output = Path(output)
    return output.parent / f"{output.stem}_checkpoints"


def checkpoint_path(output, current_case_id, selected_cycle) -> Path:
    return checkpoint_directory(output) / (
        f"{current_case_id}_cycle{int(selected_cycle):03d}.npz"
    )


def expand_cases(manifest, fingerprint=None) -> list[dict]:
    fingerprint = runtime_fingerprint() if fingerprint is None else dict(fingerprint)
    process_seed_count = foundation.bosch_process_seed_count(
        manifest["recipe"]["num_cycles"]
    )
    cases = []
    for design in manifest["designs"]:
        for base_seed in manifest["rng_base_seeds"]:
            recipe = {**manifest["recipe"], "mask_ion_rate": design["mask_ion_rate"]}
            current = {
                "manifest_version": manifest["manifest_version"],
                "campaign": manifest["campaign"],
                "labels": list(manifest["labels"]),
                "arm": design["name"],
                "role": design["role"],
                "geometry": {
                    **manifest["geometry"],
                    "hole_shape": design["hole_shape"],
                },
                "recipe": recipe,
                "selected_cycle": manifest["selected_cycle"],
                "numerics": {
                    "grid_delta": design["grid_delta"],
                    "rays_per_point": design["rays_per_point"],
                    "threads_per_worker": manifest["numerics"]["threads_per_worker"],
                    "simulation_dimension": manifest["numerics"]["dimension"],
                },
                "target": manifest["target"],
                "rng_seed": base_seed,
                "rng_stream": {
                    "base_seed": base_seed,
                    "process_seed_count": process_seed_count,
                    "first_process_seed": base_seed,
                    "last_process_seed": base_seed + process_seed_count - 1,
                    "disjoint_within_arm": True,
                    "shared_base_seed_label_across_arms": True,
                    "pointwise_common_random_numbers_across_arms": False,
                },
                "rng_policy": manifest["rng_policy"],
                "runtime_fingerprint": fingerprint,
                "reference_recipe": manifest["reference_recipe"],
                "authority": manifest["authority"],
                "provenance": manifest["provenance"],
            }
            payload = case_payload(current)
            current["case_id"] = case_id(payload)
            current["case_payload_sha256"] = canonical_sha256(payload)
            cases.append(current)
    return cases


def _close(first, second, tolerance=1e-15) -> bool:
    try:
        return math.isclose(
            float(first), float(second), rel_tol=0.0, abs_tol=tolerance
        )
    except (TypeError, ValueError):
        return False


def _reference_recipe_errors(manifest, project_root=ROOT) -> list[str]:
    errors = []
    source = Path(manifest.get("reference_recipe", {}).get("source_path", ""))
    source = source if source.is_absolute() else Path(project_root) / source
    if not source.is_file():
        return [f"reference recipe source is missing: {source}"]
    try:
        reference = strict_json_loads(source.read_text())
    except Exception as error:
        return [f"reference recipe source does not parse: {error}"]
    recipe = reference.get("recipe")
    expected_hash = manifest["reference_recipe"].get("recipe_canonical_sha256")
    if recipe != manifest.get("recipe"):
        errors.append("manifest recipe differs from the high-fidelity reference")
    if canonical_sha256(recipe) != expected_hash:
        errors.append("reference recipe canonical hash differs")
    return errors


def validate_manifest(
    manifest, cases=None, *, check_runtime=True, project_root=ROOT
) -> list[str]:
    errors = []
    if tuple(manifest.get("labels", ())) != EXPECTED_LABELS:
        errors.append("labels must be full-traveler and critical-review")
    if manifest.get("campaign") != "foundation-pattern-bosch-gate0":
        errors.append("campaign name differs")
    if manifest.get("selected_cycle") != 13:
        errors.append("selected cycle must be 13")
    if manifest.get("recipe", {}).get("num_cycles") != 14:
        errors.append("num_cycles must be 14")
    if tuple(manifest.get("rng_base_seeds", ())) != EXPECTED_SEEDS:
        errors.append("RNG bases differ from the frozen four-stream design")
    if manifest.get("rng_policy") != {
        "shared_base_seed_labels_across_arms": True,
        "streams_disjoint_within_each_arm": True,
        "pointwise_common_random_numbers_across_arms": False,
        "full_vs_quarter_common_random_numbers": False,
        "interpretation": (
            "Base labels pair comparisons, but changed geometry, surface nodes, "
            "and process evolution do not guarantee identical pointwise random draws."
        ),
    }:
        errors.append("RNG pairing interpretation differs")
    geometry = manifest.get("geometry", {})
    if geometry != {
        "radius": 0.15,
        "mask_height": 0.3,
        "x_extent": 1.0,
        "y_extent": 2.0,
    }:
        errors.append("geometry differs from the frozen Gate-0 geometry")
    numerics = manifest.get("numerics", {})
    if numerics != {
        "threads_per_worker": 7,
        "maximum_workers": 2,
        "dimension": 2,
    }:
        errors.append("worker, thread, or dimension contract differs")
    if manifest.get("target") != EXPECTED_TARGET:
        errors.append("product gates differ from the frozen Gate-0 targets")
    if manifest.get("reference_recipe") != EXPECTED_REFERENCE_RECIPE:
        errors.append("high-fidelity reference recipe declaration differs")
    observed_designs = {
        item.get("name"): {
            key: item.get(key)
            for key in (
                "role",
                "hole_shape",
                "grid_delta",
                "rays_per_point",
                "mask_ion_rate",
            )
        }
        for item in manifest.get("designs", ())
    }
    if observed_designs != EXPECTED_DESIGNS or len(manifest.get("designs", ())) != 6:
        errors.append("six-arm design differs from the frozen matrix")
    review = manifest.get("review", {})
    if review.get("paired_max_absolute_deltas") != EXPECTED_TOLERANCES:
        errors.append("paired CTQ tolerances differ")
    if review.get("erosion_arm_order") != [
        "full_reference_fine",
        "full_erosion_m0p01",
        "full_erosion_m0p02",
        "full_erosion_m0p04",
    ]:
        errors.append("erosion arm order differs")
    if not (
        review.get("row_recompute_abs_tolerance") == 1e-12
        and review.get("erosion_monotonic_abs_tolerance") == 1e-12
        and review.get("full_vs_quarter") == {
            "reference_arm": "quarter_reference_fine",
            "candidate_arm": "full_reference_fine",
            "require_all_four_pairs": True,
            "require_no_gate_flips": True,
        }
        and review.get("grid_bridge") == {
            "reference_arm": "full_reference_fine",
            "candidate_arm": "full_grid_bridge",
            "require_all_four_pairs": True,
            "require_no_gate_flips": True,
        }
        and review.get("require_one_all_seed_surviving_arm") is True
        and review.get("require_one_all_seed_failed_arm") is True
    ):
        errors.append("review hard gates were relaxed")
    authority = manifest.get("authority", {})
    if authority != {
        "gate": "pattern_bosch_gate0",
        "may_authorize": "broad_pattern_bosch_screen_only",
        "recipe_authorized": False,
        "process_window_authorized": False,
        "full_traveler_authorized": False,
        "automatic_downstream_launch_authorized": False,
    }:
        errors.append("Gate-0 authority differs")
    errors.extend(_reference_recipe_errors(manifest, project_root))
    if check_runtime:
        actual = runtime_fingerprint(project_root)
        runtime = manifest.get("runtime", {})
        for key in ("viennaps_binary_sha256", "viennals_binary_sha256"):
            if actual.get(key) != runtime.get(key):
                errors.append(f"runtime {key} differs")
    if cases is not None:
        if len(cases) != 24 or len({case["case_id"] for case in cases}) != 24:
            errors.append("expanded matrix is not 24 unique cases")
        expected_cells = {
            (arm, seed) for arm in EXPECTED_DESIGNS for seed in EXPECTED_SEEDS
        }
        if {(case.get("arm"), case.get("rng_seed")) for case in cases} != expected_cells:
            errors.append("expanded arm/seed matrix differs")
        for case in cases:
            payload = case_payload(case)
            if case.get("case_id") != case_id(payload):
                errors.append(f"case ID differs: {case.get('case_id')}")
            if case.get("case_payload_sha256") != canonical_sha256(payload):
                errors.append(f"case payload hash differs: {case.get('case_id')}")
            stream = case.get("rng_stream", {})
            if stream.get("process_seed_count") != 43:
                errors.append(f"Bosch stream horizon differs: {case.get('case_id')}")
        for arm in EXPECTED_DESIGNS:
            streams = [
                set(range(
                    case["rng_stream"]["first_process_seed"],
                    case["rng_stream"]["last_process_seed"] + 1,
                ))
                for case in cases if case["arm"] == arm
            ]
            if any(first & second for index, first in enumerate(streams)
                   for second in streams[index + 1:]):
                errors.append(f"Bosch streams overlap within {arm}")
    return errors


def _mesh_for_material(meshes, material, *, required=True):
    matches = [mesh for mesh in meshes if mesh["material"] == material]
    matches = [mesh for mesh in matches if len(mesh["nodes"])]
    if not matches:
        if required:
            raise ValueError(f"required material mesh is absent: {material}")
        return None
    if len(matches) != 1:
        raise ValueError(f"material mesh is ambiguous: {material}")
    return matches[0]


def measure_pattern(mask_mesh, case) -> dict:
    return tm.pattern_metrics_2d(
        mask_mesh["nodes"],
        mask_mesh["lines"],
        surface_y=0.0,
        target_cd=case["target"]["opening_cd"],
        target_mask_height=case["target"]["mask_height"],
        max_radius=case["target"]["opening_cd"],
    )


def measure_selected_cycle(silicon_mesh, mask_mesh, case) -> dict:
    floor_y = float(np.min(silicon_mesh["nodes"][:, 1]))
    etch = tm.etch_profile_metrics_2d(
        silicon_mesh["nodes"],
        silicon_mesh["lines"],
        surface_y=0.0,
        floor_y=floor_y,
        target_cd=case["target"]["opening_cd"],
        max_radius=case["target"]["opening_cd"],
    )
    remaining = 0.0
    post_mask = None
    if mask_mesh is not None and len(mask_mesh["nodes"]):
        remaining = float(np.max(mask_mesh["nodes"][:, 1]))
        try:
            post_mask = measure_pattern(mask_mesh, case)
        except ValueError:
            post_mask = None
    return {
        "etch": etch,
        "mask_remaining_height": remaining,
        "post_etch_mask": post_mask,
    }


def save_cycle_checkpoint(
    path, case, initial_mask, silicon_mesh, mask_mesh
) -> str:
    empty_nodes = np.empty((0, 3), dtype=float)
    empty_lines = np.empty((0, 2), dtype=int)
    return foundation.save_npz_atomic(
        path,
        schema_version=np.asarray(1, dtype=int),
        case_id=np.asarray(case["case_id"]),
        case_payload_json=np.asarray(canonical_json(case_payload(case))),
        case_payload_sha256=np.asarray(case["case_payload_sha256"]),
        runtime_fingerprint_json=np.asarray(
            canonical_json(case["runtime_fingerprint"])
        ),
        selected_cycle=np.asarray(case["selected_cycle"], dtype=int),
        simulation_dimension=np.asarray(2, dtype=int),
        arm=np.asarray(case["arm"]),
        hole_shape=np.asarray(case["geometry"]["hole_shape"]),
        grid_delta=np.asarray(case["numerics"]["grid_delta"], dtype=float),
        rays_per_point=np.asarray(case["numerics"]["rays_per_point"], dtype=int),
        rng_seed=np.asarray(case["rng_seed"], dtype=int),
        initial_mask_nodes=np.asarray(initial_mask["nodes"], dtype=float),
        initial_mask_lines=np.asarray(initial_mask["lines"], dtype=int),
        silicon_nodes=np.asarray(silicon_mesh["nodes"], dtype=float),
        silicon_lines=np.asarray(silicon_mesh["lines"], dtype=int),
        mask_nodes=(
            np.asarray(mask_mesh["nodes"], dtype=float)
            if mask_mesh is not None else empty_nodes
        ),
        mask_lines=(
            np.asarray(mask_mesh["lines"], dtype=int)
            if mask_mesh is not None else empty_lines
        ),
    )


def run_case(task):
    case, output = task
    started = time.time()
    try:
        ps.setNumThreads(int(case["numerics"]["threads_per_worker"]))
        hole_shape = (
            ps.HoleShape.FULL
            if case["geometry"]["hole_shape"] == "FULL"
            else ps.HoleShape.QUARTER
        )
        geometry = tp.make_initial_geometry(
            radius=case["geometry"]["radius"],
            mask_height=case["geometry"]["mask_height"],
            grid_delta=case["numerics"]["grid_delta"],
            x_extent=case["geometry"]["x_extent"],
            y_extent=case["geometry"]["y_extent"],
            taper=case["recipe"]["mask_taper"],
            hole_shape=hole_shape,
        )
        initial_mask = _mesh_for_material(
            tm.raw_level_set_meshes(geometry), ps.Material.Mask
        )
        initial_pattern = measure_pattern(initial_mask, case)
        captured = []

        def capture_cycle(current, cycle):
            if int(cycle) != int(case["selected_cycle"]):
                return
            if captured:
                raise ValueError("selected cycle was captured more than once")
            meshes = tm.raw_level_set_meshes(current)
            silicon = _mesh_for_material(meshes, ps.Material.Si)
            mask = _mesh_for_material(meshes, ps.Material.Mask, required=False)
            metrics = measure_selected_cycle(silicon, mask, case)
            path = checkpoint_path(output, case["case_id"], case["selected_cycle"])
            digest = save_cycle_checkpoint(
                path, case, initial_mask, silicon, mask
            )
            captured.append((metrics, path, digest))

        tp.bosch_etch(
            geometry,
            num_cycles=case["recipe"]["num_cycles"],
            etch_time=case["recipe"]["etch_time"],
            initial_etch_time=case["recipe"]["initial_etch_time"],
            ion_source_exponent=case["recipe"]["ion_source_exponent"],
            neutral_sticking_probability=case["recipe"][
                "neutral_sticking_probability"
            ],
            deposition_thickness=case["recipe"]["deposition_thickness"],
            deposition_sticking_probability=case["recipe"][
                "deposition_sticking_probability"
            ],
            neutral_rate=case["recipe"]["neutral_rate"],
            ion_rate=case["recipe"]["ion_rate"],
            radius=case["geometry"]["radius"],
            theta_r_min=case["recipe"]["theta_r_min"],
            rays_per_point=case["numerics"]["rays_per_point"],
            rng_seed=case["rng_seed"],
            mask_ion_rate=case["recipe"]["mask_ion_rate"],
            on_cycle=capture_cycle,
        )
        if len(captured) != 1:
            raise ValueError("selected cycle checkpoint was not captured exactly once")
        selected_metrics, path, digest = captured[0]
        success = foundation.jsonable({
            **case,
            "ok": True,
            "evidence_origin": evidence_origin(),
            "initial_pattern": initial_pattern,
            "selected_cycle_metrics": selected_metrics,
            "checkpoint_cycle": case["selected_cycle"],
            "checkpoint_path": str(path),
            "checkpoint_sha256": digest,
            "elapsed_s": time.time() - started,
        })
        # Validate while still inside the guarded execution path.  In particular,
        # a non-finite metric must become a durable failed attempt instead of
        # escaping later from append_row() and leaving no result record.
        canonical_json(success)
        return success
    except Exception as error:
        return foundation.jsonable({
            **case,
            "ok": False,
            "evidence_origin": evidence_origin(),
            "error": repr(error),
            "traceback": traceback.format_exc(),
            "elapsed_s": time.time() - started,
        })


def _scalar(snapshot, key):
    value = snapshot[key]
    if np.asarray(value).shape != ():
        raise ValueError(f"checkpoint metadata is not scalar: {key}")
    return np.asarray(value).item()


def _mesh_errors(nodes, lines, name, *, required) -> list[str]:
    errors = []
    nodes = np.asarray(nodes)
    lines = np.asarray(lines)
    if nodes.ndim != 2 or nodes.shape[1] < 2:
        return [f"{name} nodes are not Nx2-or-greater"]
    if lines.ndim != 2 or lines.shape[1] != 2:
        return [f"{name} lines are not Mx2"]
    if required and not len(nodes):
        errors.append(f"{name} mesh is empty")
    if np.any(~np.isfinite(nodes)):
        errors.append(f"{name} nodes are nonfinite")
    if not np.issubdtype(lines.dtype, np.integer):
        errors.append(f"{name} lines are not integer")
    if len(lines) and (
        np.min(lines) < 0 or np.max(lines) >= len(nodes)
    ):
        errors.append(f"{name} line indices are out of range")
    if not len(nodes) and len(lines):
        errors.append(f"{name} has lines without nodes")
    return errors


def validate_checkpoint(path, case) -> list[str]:
    path = Path(path)
    if not path.is_file():
        return ["checkpoint is missing"]
    errors = []
    try:
        with np.load(path, allow_pickle=False) as snapshot:
            if set(snapshot.files) != CHECKPOINT_KEYS:
                errors.append("checkpoint schema keys differ")
                return errors
            expected_metadata = {
                "schema_version": 1,
                "case_id": case["case_id"],
                "case_payload_sha256": case["case_payload_sha256"],
                "runtime_fingerprint_json": canonical_json(
                    case["runtime_fingerprint"]
                ),
                "selected_cycle": case["selected_cycle"],
                "simulation_dimension": 2,
                "arm": case["arm"],
                "hole_shape": case["geometry"]["hole_shape"],
                "grid_delta": case["numerics"]["grid_delta"],
                "rays_per_point": case["numerics"]["rays_per_point"],
                "rng_seed": case["rng_seed"],
            }
            for key, expected in expected_metadata.items():
                observed = _scalar(snapshot, key)
                if isinstance(expected, float):
                    matches = _close(observed, expected)
                else:
                    matches = observed == expected
                if not matches:
                    errors.append(f"checkpoint metadata differs: {key}")
            try:
                payload = strict_json_loads(str(_scalar(snapshot, "case_payload_json")))
            except Exception as error:
                errors.append(f"checkpoint case payload does not parse: {error}")
            else:
                if payload != case_payload(case):
                    errors.append("checkpoint case payload differs")
                if canonical_sha256(payload) != case["case_payload_sha256"]:
                    errors.append("checkpoint case payload hash differs")
            errors.extend(_mesh_errors(
                snapshot["initial_mask_nodes"],
                snapshot["initial_mask_lines"],
                "initial mask",
                required=True,
            ))
            errors.extend(_mesh_errors(
                snapshot["silicon_nodes"],
                snapshot["silicon_lines"],
                "silicon",
                required=True,
            ))
            errors.extend(_mesh_errors(
                snapshot["mask_nodes"],
                snapshot["mask_lines"],
                "post-etch mask",
                required=False,
            ))
    except Exception as error:
        errors.append(f"checkpoint cannot be loaded: {error}")
    return errors


def row_matches_case(row, case) -> bool:
    return bool(
        isinstance(row, dict)
        and row.get("case_id") == case["case_id"]
        and row.get("case_payload_sha256") == case["case_payload_sha256"]
        and all(row.get(field) == case.get(field) for field in CASE_FIELDS)
        and case_id(case_payload(row)) == case["case_id"]
        and canonical_sha256(case_payload(row)) == case["case_payload_sha256"]
    )


def audit_existing_rows(output, cases) -> set[str]:
    output = Path(output)
    if not output.exists():
        return set()
    expected = {case["case_id"]: case for case in cases}
    attempts = {current: [] for current in expected}
    for line_number, line in enumerate(output.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = strict_json_loads(line)
        except Exception as error:
            raise ValueError(
                f"existing Gate-0 row line {line_number} is malformed: {error}"
            ) from error
        if not isinstance(row, dict):
            raise ValueError(f"existing Gate-0 row line {line_number} is not an object")
        case = expected.get(row.get("case_id"))
        if case is None:
            raise ValueError(f"existing Gate-0 row line {line_number} is unexpected")
        if not row_matches_case(row, case):
            raise ValueError(
                f"existing Gate-0 row line {line_number} has stale payload"
            )
        if row.get("ok") not in (True, False):
            raise ValueError(
                f"existing Gate-0 row line {line_number} lacks boolean status"
            )
        if row.get("evidence_origin") != evidence_origin():
            raise ValueError(
                f"existing Gate-0 row line {line_number} has invalid origin"
            )
        attempts[case["case_id"]].append((line_number, row))
    completed = set()
    for current_case_id, case_attempts in attempts.items():
        successes = [
            (index, row)
            for index, (_, row) in enumerate(case_attempts)
            if row["ok"] is True
        ]
        if len(successes) > 1:
            raise ValueError(f"duplicate successful Gate-0 case: {current_case_id}")
        if not successes:
            continue
        success_index, row = successes[0]
        if success_index != len(case_attempts) - 1:
            raise ValueError(
                f"successful Gate-0 case has a later attempt: {current_case_id}"
            )
        expected_path = checkpoint_path(
            output, current_case_id, expected[current_case_id]["selected_cycle"]
        )
        declaration = row.get("checkpoint_path")
        if not isinstance(declaration, str) or (
            Path(declaration).resolve() != expected_path.resolve()
        ):
            raise ValueError(
                f"successful Gate-0 checkpoint path differs: {current_case_id}"
            )
        if row.get("checkpoint_cycle") != expected[current_case_id]["selected_cycle"]:
            raise ValueError(
                f"successful Gate-0 checkpoint cycle differs: {current_case_id}"
            )
        if not expected_path.is_file() or row.get("checkpoint_sha256") != file_sha256(
            expected_path
        ):
            raise ValueError(
                f"successful Gate-0 checkpoint hash differs: {current_case_id}"
            )
        checkpoint_errors = validate_checkpoint(
            expected_path, expected[current_case_id]
        )
        if checkpoint_errors:
            raise ValueError(
                f"successful Gate-0 checkpoint invalid {current_case_id}: "
                + "; ".join(checkpoint_errors)
            )
        completed.add(current_case_id)
    return completed


def append_row(path, row):
    serialized = json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")
    manifest = strict_json_loads(args.manifest.read_text())
    cases = expand_cases(manifest)
    errors = validate_manifest(manifest, cases)
    if errors:
        raise ValueError("invalid Gate-0 manifest: " + "; ".join(errors))
    done = audit_existing_rows(args.output, cases)
    pending = [case for case in cases if case["case_id"] not in done]
    print(
        f"logical=24 complete={len(done)} pending={len(pending)} "
        "authority=broad_pattern_bosch_screen_only",
        flush=True,
    )
    if not pending:
        return
    tasks = [(case, args.output) for case in pending]
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, row in enumerate(executor.map(run_case, tasks), start=1):
            append_row(args.output, row)
            print(
                f"[{completed}/{len(tasks)}] {row['case_id']} "
                f"ok={row['ok']} elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

"""Checkpointed pattern/DRIE metric and numerical-convergence audit."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import os
import time
import zipfile  # np.savez imports this lazily; preload before long simulations.
from pathlib import Path

import numpy as np
import viennaps as ps

import traveler_metrics as tm
import tsv_process as tp


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/foundation_metric_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/metric_convergence_rows.jsonl"
)


def case_id(case):
    payload = json.dumps(case, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_npz_atomic(path, **arrays):
    """Write a reusable simulation checkpoint without exposing a partial file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}.npz")
    np.savez_compressed(temporary, **arrays)
    with temporary.open("rb+") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return file_sha256(path)


def bosch_process_seed_count(num_cycles):
    """Number of sequential ray-tracing seeds consumed by one Bosch run."""
    cycles = int(num_cycles)
    if cycles < 0 or cycles != num_cycles:
        raise ValueError("num_cycles must be a non-negative integer")
    return 1 + 3 * cycles


def bosch_replicate_base_seeds(design, num_cycles):
    """Return disjoint base streams for stochastic Bosch replicates.

    ``bosch_etch`` consumes one seed for the initial etch and three for every
    Bosch cycle.  Adjacent base seeds therefore create almost identical
    streams and are paired checkpoints, not independent replicates.
    """
    seed_count = int(design["seed_count"])
    if seed_count < 1 or seed_count != design["seed_count"]:
        raise ValueError("seed_count must be a positive integer")
    process_seed_count = bosch_process_seed_count(num_cycles)
    seed_stride = int(design.get("seed_stride", 1))
    if seed_stride < 1 or seed_stride != design.get("seed_stride", 1):
        raise ValueError("seed_stride must be a positive integer")
    if seed_count > 1 and seed_stride < process_seed_count:
        raise ValueError(
            f"Bosch replicate RNG streams overlap: seed_stride={seed_stride}, "
            f"required>={process_seed_count} for num_cycles={int(num_cycles)}"
        )
    seed_start = int(design["seed_start"])
    return [seed_start + replicate * seed_stride for replicate in range(seed_count)]


def expand_cases(manifest):
    base = {
        "manifest_version": manifest["manifest_version"],
        "geometry": manifest["geometry"],
        "recipe": manifest["recipe"],
        "target": manifest["target"],
        "provenance": manifest["provenance"],
    }
    if "threads_per_worker" in manifest:
        base["threads_per_worker"] = manifest["threads_per_worker"]
    if "record_cycle_history" in manifest:
        base["record_cycle_history"] = manifest["record_cycle_history"]
    if "save_checkpoint_cycles" in manifest:
        base["save_checkpoint_cycles"] = manifest["save_checkpoint_cycles"]
    cases = []
    for design in manifest["designs"]:
        replicate_seeds = bosch_replicate_base_seeds(
            design, manifest["recipe"]["num_cycles"]
        )
        process_seed_count = bosch_process_seed_count(
            manifest["recipe"]["num_cycles"]
        )
        for grid_delta in design["grid_deltas"]:
            for rays_per_point in design["rays_per_point"]:
                for replicate, rng_seed in enumerate(replicate_seeds):
                    case = {
                        **base,
                        "geometry": {
                            **manifest["geometry"],
                            **design.get("geometry", {}),
                        },
                        "design": design["name"],
                        "grid_delta": grid_delta,
                        "rays_per_point": rays_per_point,
                        "replicate": replicate,
                        "rng_seed": rng_seed,
                        "rng_process_seed_count": process_seed_count,
                        "rng_seed_stride": int(design.get("seed_stride", 1)),
                    }
                    case["case_id"] = case_id(case)
                    case["save_mesh"] = replicate == 0
                    cases.append(case)
    return cases


def jsonable(value):
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def run_case(task):
    case, mesh_dir = task
    started = time.time()
    geometry_spec = case["geometry"]
    recipe = case["recipe"]
    cycle_history = []
    cycle_checkpoints = []
    try:
        if case.get("threads_per_worker") is not None:
            ps.setNumThreads(int(case["threads_per_worker"]))
        geometry = tp.make_initial_geometry(
            radius=geometry_spec["radius"],
            mask_height=geometry_spec["mask_height"],
            grid_delta=case["grid_delta"],
            x_extent=geometry_spec["x_extent"],
            y_extent=geometry_spec["y_extent"],
            taper=recipe["mask_taper"],
            hole_shape=(
                ps.HoleShape.FULL
                if geometry_spec.get("hole_shape") == "FULL"
                else ps.HoleShape.QUARTER
            ),
        )
        initial_meshes = tm.raw_level_set_meshes(geometry)
        initial_mask = next(
            mesh for mesh in initial_meshes if mesh["material"] == ps.Material.Mask
        )
        pattern = tm.pattern_metrics_2d(
            initial_mask["nodes"],
            initial_mask["lines"],
            surface_y=0.0,
            target_cd=case["target"]["opening_cd"],
            target_mask_height=case["target"]["mask_height"],
            max_radius=case["target"]["opening_cd"],
        )

        def record_cycle(current, cycle):
            should_record_metrics = bool(case.get("record_cycle_history"))
            should_save_checkpoint = cycle in set(
                case.get("save_checkpoint_cycles", ())
            )
            if not should_record_metrics and not should_save_checkpoint:
                return
            meshes = tm.raw_level_set_meshes(current)
            silicon_mesh = next(
                mesh for mesh in meshes if mesh["material"] == ps.Material.Si
            )
            if should_save_checkpoint:
                masks = [
                    mesh for mesh in meshes
                    if mesh["material"] == ps.Material.Mask and len(mesh["nodes"])
                ]
                mask_mesh = masks[0] if masks else None
                checkpoint_path = (
                    mesh_dir / f"{case['case_id']}_cycle{int(cycle):03d}.npz"
                )
                checkpoint_sha256 = save_npz_atomic(
                    checkpoint_path,
                    case_id=np.asarray(case["case_id"]),
                    cycle=np.asarray(int(cycle)),
                    silicon_nodes=silicon_mesh["nodes"],
                    silicon_lines=silicon_mesh["lines"],
                    mask_nodes=(
                        mask_mesh["nodes"]
                        if mask_mesh is not None else np.empty((0, 3))
                    ),
                    mask_lines=(
                        mask_mesh["lines"]
                        if mask_mesh is not None
                        else np.empty((0, 2), dtype=int)
                    ),
                )
                cycle_checkpoints.append({
                    "cycle": int(cycle),
                    "path": str(checkpoint_path),
                    "sha256": checkpoint_sha256,
                })
            if not should_record_metrics:
                return
            cycle_floor = float(np.min(silicon_mesh["nodes"][:, 1]))
            if cycle_floor >= -0.01:
                return
            measured = tm.etch_profile_metrics_2d(
                silicon_mesh["nodes"],
                silicon_mesh["lines"],
                surface_y=0.0,
                floor_y=cycle_floor,
                target_cd=case["target"]["opening_cd"],
                max_radius=case["target"]["opening_cd"],
            )
            cycle_history.append({
                "cycle": cycle,
                **{key: measured[key] for key in (
                    "depth",
                    "cd_top",
                    "cd_middle",
                    "cd_bottom",
                    "max_cd_error",
                    "sidewall_angle_deg",
                    "max_bow",
                    "scallop_rms",
                )},
            })

        geometry, floor_y = tp.bosch_etch(
            geometry,
            num_cycles=recipe["num_cycles"],
            etch_time=recipe["etch_time"],
            initial_etch_time=recipe["initial_etch_time"],
            ion_source_exponent=recipe["ion_source_exponent"],
            neutral_sticking_probability=recipe["neutral_sticking_probability"],
            deposition_thickness=recipe["deposition_thickness"],
            deposition_sticking_probability=recipe[
                "deposition_sticking_probability"
            ],
            neutral_rate=recipe["neutral_rate"],
            ion_rate=recipe["ion_rate"],
            radius=geometry_spec["radius"],
            theta_r_min=recipe["theta_r_min"],
            rays_per_point=case["rays_per_point"],
            rng_seed=case["rng_seed"],
            mask_ion_rate=recipe.get("mask_ion_rate", 0.0),
            on_cycle=(
                record_cycle
                if case.get("record_cycle_history")
                or case.get("save_checkpoint_cycles")
                else None
            ),
        )
        final_meshes = tm.raw_level_set_meshes(geometry)
        silicon = next(
            mesh for mesh in final_meshes if mesh["material"] == ps.Material.Si
        )
        masks = [
            mesh for mesh in final_meshes if mesh["material"] == ps.Material.Mask
        ]
        etch = tm.etch_profile_metrics_2d(
            silicon["nodes"],
            silicon["lines"],
            surface_y=0.0,
            floor_y=floor_y,
            target_cd=case["target"]["opening_cd"],
            max_radius=case["target"]["opening_cd"],
        )
        legacy_points = tp.profile_points(geometry)
        legacy = {
            "depth": floor_y,
            "wall_bulge": tp.wall_bulge(
                legacy_points, floor_y, geometry_spec["radius"]
            ),
            "width_error": tp.width_error(
                legacy_points, floor_y, geometry_spec["radius"]
            ),
        }
        mask = masks[0] if masks else None
        mask_remaining_height = (
            float(mask["nodes"][:, 1].max())
            if mask is not None and len(mask["nodes"])
            else 0.0
        )
        post_etch_mask = None
        if mask is not None and len(mask["nodes"]):
            post_etch_mask = tm.pattern_metrics_2d(
                mask["nodes"],
                mask["lines"],
                surface_y=0.0,
                target_cd=case["target"]["opening_cd"],
                target_mask_height=case["target"]["mask_height"],
                max_radius=case["target"]["opening_cd"],
            )

        if case["save_mesh"]:
            mesh_dir.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                mesh_dir / f"{case['case_id']}.npz",
                silicon_nodes=silicon["nodes"],
                silicon_lines=silicon["lines"],
                mask_nodes=(
                    mask["nodes"] if mask is not None else np.empty((0, 3))
                ),
                mask_lines=(
                    mask["lines"] if mask is not None else np.empty((0, 2), dtype=int)
                ),
            )

        return jsonable({
            **case,
            "ok": True,
            "pattern": pattern,
            "etch": etch,
            "legacy": legacy,
            "mask_remaining_height": mask_remaining_height,
            "post_etch_mask": post_etch_mask,
            "cycle_history": cycle_history,
            "cycle_checkpoints": cycle_checkpoints,
            "elapsed_s": time.time() - started,
        })
    except Exception as error:
        return jsonable({
            **case,
            "ok": False,
            "error": repr(error),
            "elapsed_s": time.time() - started,
        })


def completed_case_ids(path):
    if not path.exists():
        return set()
    completed = set()
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("ok") is True:
                completed.add(row["case_id"])
    return completed


def append_row(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    cases = expand_cases(manifest)
    done = completed_case_ids(args.output)
    pending = [case for case in cases if case["case_id"] not in done]
    if args.limit is not None:
        pending = pending[:args.limit]
    print(
        f"manifest cases={len(cases)} complete={len(done)} pending={len(pending)}",
        flush=True,
    )
    if not pending:
        return

    mesh_dir = args.output.parent / "metric_convergence_meshes"
    tasks = [(case, mesh_dir) for case in pending]
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

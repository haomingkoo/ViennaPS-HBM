"""Checkpointed liner, barrier, and seed metric/model qualification."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import viennaps as ps
import viennaps._core as ps_core

import foundation_metric_audit as foundation
import traveler_metrics as tm
import tsv_process as tp


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/foundation_layer_manifest.json"
)
DEFAULT_OUTPUT = Path("autoresearch-results/restart_audit/layer_rows.jsonl")


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_fingerprint():
    project_root = Path(__file__).resolve().parent
    return {
        "runner_sha256": _file_sha256(project_root / Path(__file__).name),
        "metric_sha256": _file_sha256(project_root / "traveler_metrics.py"),
        "tsv_process_sha256": _file_sha256(project_root / "tsv_process.py"),
        "runtime_binary_sha256": _file_sha256(ps_core.__file__),
    }


def expand_cases(manifest):
    cases = []
    runtime_fingerprint = _runtime_fingerprint()
    for design in manifest["designs"]:
        for replicate in range(design["seed_count"]):
            case = {
                "manifest_version": manifest["manifest_version"],
                "design": design["name"],
                "comparison_family": design["comparison_family"],
                "geometry": manifest["geometry"],
                "specs": manifest["specs"],
                "grid_delta": design["grid_delta"],
                "rays_per_point": design.get(
                    "rays_per_point", manifest["rays_per_point"]
                ),
                "threads_per_worker": manifest["threads_per_worker"],
                "replicate": replicate,
                "rng_seed": design["seed_start"] + replicate,
                "liner": {**manifest["baseline"]["liner"], **design.get("liner", {})},
                "barrier": {
                    **manifest["baseline"]["barrier"],
                    **design.get("barrier", {}),
                },
                "seed": {**manifest["baseline"]["seed"], **design.get("seed", {})},
                "provenance": manifest["provenance"],
                "runtime_fingerprint": runtime_fingerprint,
            }
            case["case_id"] = foundation.case_id(case)
            case["save_mesh"] = replicate == 0
            cases.append(case)
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("manifest contains duplicate layer cases")
    return cases


def interface_levels(mesh, *, surface_hint, floor_hint, via_radius):
    field_ys = tm.line_intersections_at_x(
        mesh["nodes"], mesh["lines"], 2.5 * via_radius
    )
    floor_ys = tm.line_intersections_at_x(
        mesh["nodes"], mesh["lines"], 0.2 * via_radius
    )
    if not len(field_ys) or not len(floor_ys):
        raise ValueError("layer interface lacks a measurable field or floor")
    surface_y = float(field_ys[np.argmin(np.abs(field_ys - surface_hint))])
    floor_y = float(floor_ys[np.argmin(np.abs(floor_ys - floor_hint))])
    return surface_y, floor_y


def measure_layer(inner, outer, *, surface_y, floor_y, via_radius):
    return tm.layer_thickness_metrics_2d(
        inner["nodes"],
        inner["lines"],
        outer["nodes"],
        outer["lines"],
        surface_y=surface_y,
        floor_y=floor_y,
        via_radius=via_radius,
    )


def step_passes(case, liner, barrier, seed):
    liner_spec = case["specs"]["liner"]
    stack_spec = case["specs"]["barrier_seed"]
    combined_minimum = (
        barrier["minimum_local_thickness"] + seed["minimum_local_thickness"]
    )
    combined_conformality = min(
        barrier["floor_to_field_conformality"],
        seed["floor_to_field_conformality"],
    )
    return {
        "liner": bool(
            liner["minimum_local_thickness"] >= liner_spec["min_thickness"]
            and liner["floor_to_field_conformality"] >= liner_spec["min_coverage"]
            and liner["lower_wall_to_field_conformality"]
            >= liner_spec["min_coverage"]
            and liner["layer_continuous"]
            and liner["aperture_open"]
        ),
        "barrier_seed": bool(
            combined_minimum >= stack_spec["min_thickness"]
            and combined_conformality >= stack_spec["min_coverage"]
            and barrier["layer_continuous"]
            and seed["layer_continuous"]
            and seed["aperture_open"]
        ),
        "barrier_seed_combined_minimum": combined_minimum,
        "barrier_seed_conformality": combined_conformality,
    }


def run_case(task):
    case, mesh_dir = task
    started = time.time()
    try:
        ps.setNumThreads(int(case["threads_per_worker"]))
        geometry_spec = case["geometry"]
        radius = geometry_spec["radius"]
        depth = geometry_spec["depth"]
        geometry = ps.Domain(
            gridDelta=case["grid_delta"],
            xExtent=geometry_spec["x_extent"],
            yExtent=geometry_spec["y_extent"],
        )
        ps.MakeHole(
            domain=geometry,
            holeRadius=radius,
            holeDepth=depth,
            maskHeight=geometry_spec["mask_height"],
            maskTaperAngle=0.0,
            holeShape=ps.HoleShape.QUARTER,
        ).apply()
        tp.strip_pattern_mask(geometry)
        substrate = tm.raw_level_set_meshes(geometry)[-1]
        substrate_surface, substrate_floor = interface_levels(
            substrate, surface_hint=0.0, floor_hint=-depth, via_radius=radius
        )

        tp.deposit_conformal(
            geometry,
            ps.Material.SiO2,
            case["liner"]["thickness"],
            sticking=case["liner"]["sticking"],
            rays_per_point=case["rays_per_point"],
            rng_seed=case["rng_seed"],
        )
        liner_outer = tm.raw_level_set_meshes(geometry)[-1]
        liner = measure_layer(
            substrate,
            liner_outer,
            surface_y=substrate_surface,
            floor_y=substrate_floor,
            via_radius=radius,
        )
        liner_surface, liner_floor = interface_levels(
            liner_outer,
            surface_hint=substrate_surface + case["liner"]["thickness"],
            floor_hint=substrate_floor + case["liner"]["thickness"],
            via_radius=radius,
        )

        tp.deposit_conformal(
            geometry,
            ps.Material.TaN,
            case["barrier"]["thickness"],
            directional=True,
            iso_ratio=case["barrier"]["iso_ratio"],
            rays_per_point=case["rays_per_point"],
            rng_seed=case["rng_seed"] + 100000,
        )
        barrier_outer = tm.raw_level_set_meshes(geometry)[-1]
        barrier = measure_layer(
            liner_outer,
            barrier_outer,
            surface_y=liner_surface,
            floor_y=liner_floor,
            via_radius=radius,
        )
        barrier_surface, barrier_floor = interface_levels(
            barrier_outer,
            surface_hint=liner_surface + case["barrier"]["thickness"],
            floor_hint=liner_floor + case["barrier"]["thickness"],
            via_radius=radius,
        )

        tp.deposit_conformal(
            geometry,
            tp.CU_SEED_MATERIAL,
            case["seed"]["thickness"],
            directional=True,
            iso_ratio=case["seed"]["iso_ratio"],
            rays_per_point=case["rays_per_point"],
            rng_seed=case["rng_seed"] + 200000,
        )
        seed_outer = tm.raw_level_set_meshes(geometry)[-1]
        seed = measure_layer(
            barrier_outer,
            seed_outer,
            surface_y=barrier_surface,
            floor_y=barrier_floor,
            via_radius=radius,
        )
        passes = step_passes(case, liner, barrier, seed)

        if case["save_mesh"]:
            mesh_dir.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                mesh_dir / f"{case['case_id']}.npz",
                substrate_nodes=substrate["nodes"],
                substrate_lines=substrate["lines"],
                liner_nodes=liner_outer["nodes"],
                liner_lines=liner_outer["lines"],
                barrier_nodes=barrier_outer["nodes"],
                barrier_lines=barrier_outer["lines"],
                seed_nodes=seed_outer["nodes"],
                seed_lines=seed_outer["lines"],
            )

        return foundation.jsonable({
            **case,
            "ok": True,
            "liner_metrics": liner,
            "barrier_metrics": barrier,
            "seed_metrics": seed,
            "passes": passes,
            "elapsed_s": time.time() - started,
        })
    except Exception as error:
        return foundation.jsonable({
            **case,
            "ok": False,
            "error": repr(error),
            "elapsed_s": time.time() - started,
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    cases = expand_cases(manifest)
    done = foundation.completed_case_ids(args.output)
    pending = [case for case in cases if case["case_id"] not in done]
    if args.limit is not None:
        pending = pending[:args.limit]
    print(
        f"manifest cases={len(cases)} complete={len(done)} pending={len(pending)}",
        flush=True,
    )
    if not pending:
        return

    mesh_dir = args.output.parent / "layer_meshes"
    tasks = [(case, mesh_dir) for case in pending]
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, row in enumerate(executor.map(run_case, tasks), start=1):
            foundation.append_row(args.output, row)
            print(
                f"[{completed}/{len(tasks)}] {row['case_id']} "
                f"ok={row['ok']} elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

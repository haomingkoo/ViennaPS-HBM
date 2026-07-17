"""Resolve the thin Bosch passivation layer before further DRIE optimization."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import time
from pathlib import Path

import numpy as np
import viennaps as ps

import foundation_metric_audit as foundation
import traveler_metrics as tm
import tsv_process as tp


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/foundation_bosch_resolution_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/bosch_resolution_rows.jsonl"
)


def expand_cases(manifest):
    cases = []
    for grid_delta in manifest["grid_deltas"]:
        for replicate in range(manifest["seed_count"]):
            case = {
                "manifest_version": manifest["manifest_version"],
                "design": "single_bosch_cycle_resolution",
                "grid_delta": grid_delta,
                "rays_per_point": manifest["rays_per_point"],
                "threads_per_worker": manifest["threads_per_worker"],
                "replicate": replicate,
                "rng_seed": manifest["seed_start"] + replicate,
                "geometry": manifest["geometry"],
                "recipe": manifest["recipe"],
                "provenance": manifest["provenance"],
            }
            case["case_id"] = foundation.case_id(case)
            case["save_mesh"] = replicate == 0
            cases.append(case)
    return cases


def run_case(task):
    case, mesh_dir = task
    started = time.time()
    passivation = []
    try:
        ps.setNumThreads(int(case["threads_per_worker"]))
        geometry_spec = case["geometry"]
        recipe = case["recipe"]
        geometry = tp.make_initial_geometry(
            radius=geometry_spec["radius"],
            mask_height=geometry_spec["mask_height"],
            grid_delta=case["grid_delta"],
            x_extent=geometry_spec["x_extent"],
            y_extent=geometry_spec["y_extent"],
            taper=recipe["mask_taper"],
        )

        def measure_polymer(current, cycle):
            meshes = tm.raw_level_set_meshes(current)
            inner, outer = meshes[-2], meshes[-1]
            silicon = next(
                mesh for mesh in meshes if mesh["material"] == ps.Material.Si
            )
            floor_y = float(np.min(silicon["nodes"][:, 1]))
            metrics = tm.layer_thickness_metrics_2d(
                inner["nodes"],
                inner["lines"],
                outer["nodes"],
                outer["lines"],
                surface_y=0.0,
                floor_y=floor_y,
                via_radius=geometry_spec["radius"],
            )
            passivation.append({"cycle": cycle, **metrics})

        geometry, floor_y = tp.bosch_etch(
            geometry,
            num_cycles=1,
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
            on_polymer=measure_polymer,
        )
        meshes = tm.raw_level_set_meshes(geometry)
        silicon = next(
            mesh for mesh in meshes if mesh["material"] == ps.Material.Si
        )
        etch = tm.etch_profile_metrics_2d(
            silicon["nodes"],
            silicon["lines"],
            surface_y=0.0,
            floor_y=floor_y,
            target_cd=2.0 * geometry_spec["radius"],
            max_radius=2.0 * geometry_spec["radius"],
        )
        if len(passivation) != 1:
            raise ValueError(f"expected one passivation snapshot, got {len(passivation)}")

        if case["save_mesh"]:
            mesh_dir.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                mesh_dir / f"{case['case_id']}.npz",
                silicon_nodes=silicon["nodes"],
                silicon_lines=silicon["lines"],
            )
        return foundation.jsonable({
            **case,
            "ok": True,
            "passivation_metrics": passivation[0],
            "etch_metrics": etch,
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
    mesh_dir = args.output.parent / "bosch_resolution_meshes"
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        tasks = [(case, mesh_dir) for case in pending]
        for completed, row in enumerate(executor.map(run_case, tasks), start=1):
            foundation.append_row(args.output, row)
            print(
                f"[{completed}/{len(tasks)}] {row['case_id']} "
                f"ok={row['ok']} elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

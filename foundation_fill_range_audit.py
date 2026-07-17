"""Controlled wide-range audit of the legacy geometric fill models."""

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
    ".scratch/full-traveler-autoresearch/foundation_fill_range_manifest.json"
)
DEFAULT_OUTPUT = Path("autoresearch-results/restart_audit/fill_range_rows.jsonl")


def expand_cases(manifest):
    cases = []
    for design in manifest["designs"]:
        for dose in design["doses"]:
            for iso_ratio in design["iso_ratios"]:
                case = {
                    "manifest_version": manifest["manifest_version"],
                    "design": design["name"],
                    "model": design["model"],
                    "dose": dose,
                    "iso_ratio": iso_ratio,
                    "geometry": manifest["geometry"],
                    "grid_delta": manifest["grid_delta"],
                    "threads_per_worker": manifest["threads_per_worker"],
                    "target": manifest["target"],
                    "provenance": manifest["provenance"],
                }
                case["case_id"] = foundation.case_id(case)
                case["save_mesh"] = dose in design.get("save_doses", [])
                cases.append(case)
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("manifest contains duplicate fill cases")
    return cases


def run_case(task):
    case, mesh_dir = task
    started = time.time()
    try:
        ps.setNumThreads(int(case["threads_per_worker"]))
        spec = case["geometry"]
        geometry = ps.Domain(
            gridDelta=case["grid_delta"],
            xExtent=spec["x_extent"],
            yExtent=spec["y_extent"],
        )
        ps.MakeHole(
            domain=geometry,
            holeRadius=spec["radius"],
            holeDepth=spec["depth"],
            maskHeight=spec["mask_height"],
            # A half-domain trench clips centerline voids at the reflective
            # boundary, so its open mesh can be misclassified as void-free.
            holeShape=ps.HoleShape.FULL,
        ).apply()
        tp.strip_pattern_mask(geometry)
        tp.cu_fill(
            geometry,
            case["dose"],
            directional=case["model"] == "directional",
            iso_ratio=case["iso_ratio"],
        )
        fill_mesh = tm.raw_level_set_meshes(geometry)[-1]
        metrics = tm.fill_topology_metrics_2d(
            fill_mesh["nodes"],
            fill_mesh["lines"],
            field_y=-1e-4,
            floor_y=-spec["depth"],
            via_x_bounds=(-spec["radius"], spec["radius"]),
            field_sample_xs=(-2.5 * spec["radius"], 2.5 * spec["radius"]),
            center_x=0.0,
            tolerance=0.1 * case["grid_delta"],
        )
        target_pass = bool(
            metrics["void_free"]
            and metrics["overburden_min"] >= case["target"]["min_overburden"]
        )

        if case["save_mesh"]:
            mesh_dir.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                mesh_dir / f"{case['case_id']}.npz",
                nodes=fill_mesh["nodes"],
                lines=fill_mesh["lines"],
            )

        return foundation.jsonable({
            **case,
            "ok": True,
            "metrics": metrics,
            "target_pass": target_pass,
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
    parser.add_argument("--workers", type=int, default=8)
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

    mesh_dir = args.output.parent / "fill_range_meshes"
    tasks = [(case, mesh_dir) for case in pending]
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, row in enumerate(executor.map(run_case, tasks), start=1):
            foundation.append_row(args.output, row)
            print(
                f"[{completed}/{len(tasks)}] {row['case_id']} "
                f"ok={row['ok']} elapsed={row['elapsed_s']:.2f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

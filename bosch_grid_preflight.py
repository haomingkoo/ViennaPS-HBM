"""Check whether a finer fast grid retains a usable Bosch reference shape."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import viennals._core as ls_core
import viennaps as ps
import viennaps._core as ps_core

import foundation_metric_audit as foundation
import traveler_metrics as tm
import tsv_process as tp


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "evidence/numerical/bosch_grid_preflight_manifest.json"
OUTPUT = ROOT / "evidence/numerical/bosch_grid_preflight.json"
CHECKPOINT = ROOT / "evidence/numerical/bosch_grid_preflight_checkpoint.npz"
SOURCE_ROWS = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_rows.jsonl"
SOURCE_CASE_ID = "7405eb159356c564"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)


def source_row() -> tuple[dict, int]:
    for line_number, line in enumerate(SOURCE_ROWS.read_text().splitlines(), 1):
        row = json.loads(line)
        if row["case_id"] == SOURCE_CASE_ID:
            return row, line_number
    raise ValueError(f"source case not found: {SOURCE_CASE_ID}")


def build_manifest() -> dict:
    row, line_number = source_row()
    grid_delta = 0.005
    return {
        "schema_version": 1,
        "campaign": "bosch-grid-preflight-v1",
        "question": (
            "Does grid spacing 0.005 at 500 rays reproduce at least one complete "
            "profile inside the assumed Bosch comparison bands?"
        ),
        "authority": "grid viability check only; no numerical or recipe qualification",
        "source_case": {
            "case_id": SOURCE_CASE_ID,
            "path": str(SOURCE_ROWS.relative_to(ROOT)),
            "line_number": line_number,
            "sha256": digest(SOURCE_ROWS),
            "historical_grid_delta": row["numerics"]["grid_delta"],
            "historical_rays_per_point": row["numerics"]["rays_per_point"],
            "historical_assumed_band_result": row["hard_gate_pass"],
        },
        "geometry": row["geometry"],
        "recipe": row["recipe"],
        "maximum_cycles": row["trajectory"]["maximum_cycles"],
        "selection_rule": (
            "Complete full-width profiles inside all assumed bands rank first; "
            "then minimize absolute depth error; then choose the earlier cycle."
        ),
        "numerics": {
            "grid_delta": grid_delta,
            "rays_per_point": 500,
            "threads_per_worker": 4,
            "rng_seed": 1_600_000,
            "simulation_dimension": 2,
            "representation_context": {
                "two_cell_width": 2 * grid_delta,
                "three_cell_width": 3 * grid_delta,
                "source": "pattern_bosch_measurement_contract.json",
            },
        },
        "assumed_comparison_bands": row["target"],
        "sources": [
            {"path": "boschi_grid_preflight.py", "sha256": None},
            {"path": "traveler_metrics.py", "sha256": digest(ROOT / "traveler_metrics.py")},
            {"path": "tsv_process.py", "sha256": digest(ROOT / "tsv_process.py")},
            {
                "path": "pattern_bosch_measurement_contract.json",
                "sha256": digest(ROOT / "pattern_bosch_measurement_contract.json"),
            },
        ],
        "limits": {
            "one_process_run": True,
            "does_not_compare_ray_counts": True,
            "does_not_establish_grid_convergence": True,
        },
    }


def freeze_manifest() -> None:
    document = build_manifest()
    document["sources"][0] = {
        "path": Path(__file__).name,
        "sha256": digest(Path(__file__)),
    }
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if MANIFEST.exists() and MANIFEST.read_text() != text:
        raise ValueError(f"refusing to overwrite different manifest: {MANIFEST}")
    MANIFEST.write_text(text)
    print(MANIFEST.relative_to(ROOT))


def mesh_for(meshes: list[dict], material, *, required: bool = True):
    matches = [
        mesh for mesh in meshes if mesh["material"] == material and len(mesh["nodes"])
    ]
    if not matches and not required:
        return None
    if len(matches) != 1:
        raise ValueError(f"expected one mesh for material {material}")
    return matches[0]


def band_result(metrics: dict, target: dict) -> dict:
    checks = {
        "depth": abs(metrics["depth"] - target["etch_depth"])
        <= target["depth_tolerance"],
        "width": metrics["max_cd_error"] <= target["max_width_error"],
        "bow": metrics["max_bow"] <= target["max_wall_bulge"],
    }
    return {"checks": checks, "inside_all": all(checks.values())}


def run() -> None:
    expected = build_manifest()
    expected["sources"][0] = {
        "path": Path(__file__).name,
        "sha256": digest(Path(__file__)),
    }
    manifest = json.loads(MANIFEST.read_text())
    if manifest != expected:
        raise ValueError("manifest differs from the current builder or source hashes")

    ps.Logger.setLogLevel(ps.LogLevel.ERROR)
    ps.setDimension(2)
    ps.setNumThreads(manifest["numerics"]["threads_per_worker"])
    geometry_spec = manifest["geometry"]
    recipe = manifest["recipe"]
    target = manifest["assumed_comparison_bands"]
    started = time.monotonic()
    geometry = tp.make_initial_geometry(
        radius=geometry_spec["radius"],
        mask_height=geometry_spec["mask_height"],
        grid_delta=manifest["numerics"]["grid_delta"],
        x_extent=geometry_spec["x_extent"],
        y_extent=geometry_spec["y_extent"],
        taper=geometry_spec["mask_taper"],
        hole_shape=ps.HoleShape.FULL,
    )
    initial_mask = mesh_for(tm.raw_level_set_meshes(geometry), ps.Material.Mask)
    pattern = tm.pattern_metrics_2d(
        initial_mask["nodes"],
        initial_mask["lines"],
        surface_y=0.0,
        target_cd=target["opening_cd"],
        target_mask_height=target["mask_height"],
        max_radius=target["opening_cd"],
    )
    cycles = []
    selected = None

    def capture(current, cycle):
        nonlocal selected
        meshes = tm.raw_level_set_meshes(current)
        silicon = mesh_for(meshes, ps.Material.Si)
        mask = mesh_for(meshes, ps.Material.Mask, required=False)
        measured = tm.measure_full_via_profile_2d(
            silicon["nodes"],
            silicon["lines"],
            surface_y=0.0,
            target_cd=target["opening_cd"],
            domain_x_bounds=(-0.5 * geometry_spec["x_extent"], 0.5 * geometry_spec["x_extent"]),
            grid_delta=manifest["numerics"]["grid_delta"],
        )
        comparison = (
            band_result(measured["metrics"], target)
            if measured["metrics"] is not None
            else None
        )
        record = {
            "cycle": int(cycle),
            "availability": measured["state"],
            "reason_codes": measured["reason_codes"],
            "metrics": measured["metrics"],
            "minimum_width_cells": measured["diagnostics"].get("minimum_width_cells"),
            "mask_remaining_height": (
                float(np.max(mask["nodes"][:, 1])) if mask is not None else 0.0
            ),
            "assumed_band_result": comparison,
        }
        cycles.append(record)
        if measured["metrics"] is None:
            return
        assert comparison is not None
        rank = (
            0 if comparison["inside_all"] else 1,
            abs(measured["metrics"]["depth"] - target["etch_depth"]),
            int(cycle),
        )
        if selected is None or rank < selected["rank"]:
            selected = {
                "rank": rank,
                "record": record,
                "silicon_nodes": np.asarray(silicon["nodes"]),
                "silicon_lines": np.asarray(silicon["lines"]),
                "mask_nodes": (
                    np.asarray(mask["nodes"])
                    if mask is not None
                    else np.empty((0, 3), dtype=float)
                ),
                "mask_lines": (
                    np.asarray(mask["lines"])
                    if mask is not None
                    else np.empty((0, 2), dtype=int)
                ),
            }

    tp.bosch_etch(
        geometry,
        num_cycles=manifest["maximum_cycles"],
        etch_time=recipe["etch_time"],
        initial_etch_time=recipe["initial_etch_time"],
        ion_source_exponent=recipe["ion_source_exponent"],
        neutral_sticking_probability=recipe["neutral_sticking_probability"],
        deposition_thickness=recipe["deposition_thickness"],
        deposition_sticking_probability=recipe["deposition_sticking_probability"],
        neutral_rate=recipe["neutral_rate"],
        ion_rate=recipe["ion_rate"],
        radius=geometry_spec["radius"],
        theta_r_min=recipe["theta_r_min"],
        rays_per_point=manifest["numerics"]["rays_per_point"],
        rng_seed=manifest["numerics"]["rng_seed"],
        mask_ion_rate=recipe["mask_ion_rate"],
        on_cycle=capture,
    )
    if selected is None:
        raise ValueError("no complete full-width cycle was measured")
    checkpoint_sha = foundation.save_npz_atomic(
        CHECKPOINT,
        manifest_sha256=np.asarray(digest(MANIFEST)),
        selected_cycle=np.asarray(selected["record"]["cycle"]),
        silicon_nodes=selected["silicon_nodes"],
        silicon_lines=selected["silicon_lines"],
        mask_nodes=selected["mask_nodes"],
        mask_lines=selected["mask_lines"],
    )
    result = {
        "schema_version": 1,
        "campaign": manifest["campaign"],
        "status": "complete",
        "highest_supported_claim": (
            "The selected 0.005-grid, 500-ray run contains a complete profile inside "
            "the assumed bands."
            if selected["record"]["assumed_band_result"]["inside_all"]
            else "The selected 0.005-grid, 500-ray run did not reproduce a profile inside all assumed bands."
        ),
        "manifest": {"path": str(MANIFEST.relative_to(ROOT)), "sha256": digest(MANIFEST)},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "viennaps_binary_sha256": digest(Path(ps_core.__file__)),
            "viennals_binary_sha256": digest(Path(ls_core.__file__)),
        },
        "elapsed_s": time.monotonic() - started,
        "initial_pattern": pattern,
        "cycles": cycles,
        "selected": selected["record"],
        "checkpoint": {"path": str(CHECKPOINT.relative_to(ROOT)), "sha256": checkpoint_sha},
        "decision": (
            "eligible_as_clear_assumed-band case for the paired ray panel"
            if selected["record"]["assumed_band_result"]["inside_all"]
            else "do not freeze the paired ray panel; find a valid current-grid reference case"
        ),
        "limits": manifest["limits"],
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"selected_cycle": selected["record"]["cycle"], "inside_all": selected["record"]["assumed_band_result"]["inside_all"], "elapsed_s": result["elapsed_s"]}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "run", "status"))
    args = parser.parse_args()
    if args.action == "build":
        freeze_manifest()
    elif args.action == "run":
        run()
    else:
        if not OUTPUT.exists():
            print(json.dumps({"status": "not_run"}))
        else:
            result = json.loads(OUTPUT.read_text())
            print(json.dumps({"status": result["status"], "selected": result["selected"]}, sort_keys=True))


if __name__ == "__main__":
    main()

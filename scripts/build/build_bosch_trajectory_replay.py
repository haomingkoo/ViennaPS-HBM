"""Replay the focused Bosch center case and export seven checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import viennaps as ps

from scripts.build import build_bosch_tutorial_data as tutorial
import native_domain_checkpoint as checkpoint
import traveler_metrics as tm
import tsv_process as tp


ROOT = Path(__file__).resolve().parents[2]
ROWS = ROOT / "evidence/numerical/v3_bosch_focused_ion_map_rows.jsonl"
OUTPUT = ROOT / "bosch_trajectory_replay.json"
PUBLIC_SOURCE = ROOT / "evidence/bosch/bosch_trajectory_replay_source.json"
CASE_ID = "1cf4ff64c506b271"
CHECKPOINT_CYCLES = {1, 4, 7, 10, 13, 16, 20}
PROGRAM_SECTION = "Assumed study comparison bands"


def source_row() -> tuple[dict, int]:
    for line_number, line in enumerate(ROWS.read_text().splitlines(), 1):
        row = json.loads(line)
        if row["case_id"] == CASE_ID:
            return row, line_number
    raise ValueError(f"missing source case {CASE_ID}")


def silicon_mesh(domain) -> dict:
    return next(
        mesh
        for mesh in tm.raw_level_set_meshes(domain)
        if mesh["material"] == ps.Material.Si
    )


def silicon_path(domain) -> str:
    mesh = silicon_mesh(domain)
    return tutorial.surface_path(mesh)


def _refresh_provenance() -> None:
    document = json.loads(OUTPUT.read_text())
    document["target"]["basis"]["source"].update(
        sha256=checkpoint.file_sha256(ROOT / "program.md"),
        section=PROGRAM_SECTION,
    )
    for citation in document["citations"]:
        if citation["path"] == str(PUBLIC_SOURCE.relative_to(ROOT)):
            citation["sha256"] = hashlib.sha256(PUBLIC_SOURCE.read_bytes()).hexdigest()
    OUTPUT.write_text(
        json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(OUTPUT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provenance-only", action="store_true")
    args = parser.parse_args()
    if args.provenance_only:
        _refresh_provenance()
        return

    row, line_number = source_row()
    ps.setDimension(2)
    ps.setNumThreads(int(row["numerics"]["threads_per_worker"]))
    recipe = row["recipe"]
    geometry = row["geometry"]
    domain = tp.make_initial_geometry(
        radius=geometry["radius"],
        mask_height=geometry["mask_height"],
        grid_delta=row["numerics"]["grid_delta"],
        x_extent=geometry["x_extent"],
        y_extent=geometry["y_extent"],
        taper=recipe["mask_taper"],
        hole_shape=ps.HoleShape.FULL,
    )
    frames = []

    def capture(current, cycle):
        if cycle not in CHECKPOINT_CYCLES:
            return
        mesh = silicon_mesh(current)
        review = tm.measure_full_via_profile_2d(
            mesh["nodes"],
            mesh["lines"],
            surface_y=0.0,
            target_cd=row["target"]["opening_cd"],
            domain_x_bounds=(-geometry["x_extent"] / 2, geometry["x_extent"] / 2),
            grid_delta=row["numerics"]["grid_delta"],
        )
        if review["state"] != "complete":
            raise ValueError(f"trajectory measurement unavailable at cycle {cycle}")
        measured = review["metrics"]
        frames.append(
            {
                "cycle": cycle,
                "progress": cycle / max(CHECKPOINT_CYCLES),
                "surface_path": tutorial.surface_path(mesh),
                "metrics": {
                    "depth": measured["depth"],
                    "cd_top": measured["cd_top"],
                    "cd_middle": measured["cd_middle"],
                    "cd_bottom": measured["cd_bottom"],
                    "maximum_cd_error": measured["max_cd_error"],
                    "bow": measured["max_bow"],
                    "scallop_rms": measured["scallop_rms"],
                    "measurement_method": "full_width_two_wall_remeasurement",
                    "numerically_qualified": False,
                },
            }
        )

    tp.bosch_etch(
        domain,
        num_cycles=max(CHECKPOINT_CYCLES),
        etch_time=recipe["etch_time"],
        initial_etch_time=recipe["initial_etch_time"],
        ion_source_exponent=recipe["ion_source_exponent"],
        neutral_sticking_probability=recipe["neutral_sticking_probability"],
        deposition_thickness=recipe["deposition_thickness"],
        deposition_sticking_probability=recipe["deposition_sticking_probability"],
        neutral_rate=recipe["neutral_rate"],
        ion_rate=recipe["ion_rate"],
        mask_ion_rate=recipe["mask_ion_rate"],
        radius=geometry["radius"],
        theta_r_min=recipe["theta_r_min"],
        rays_per_point=row["numerics"]["rays_per_point"],
        rng_seed=row["rng_seed"],
        on_cycle=capture,
    )
    if [frame["cycle"] for frame in frames] != sorted(CHECKPOINT_CYCLES):
        raise ValueError("trajectory replay is incomplete")
    saved_checkpoint = (
        ROWS.parent
        / "v3_bosch_focused_ion_map_rows_checkpoints"
        / Path(row["checkpoint_path"]).name
    )
    saved = checkpoint.load_domain_checkpoint(
        saved_checkpoint, expected_sha256=row["checkpoint_sha256"]
    )
    native_surface = silicon_path(saved)
    if frames[-1]["surface_path"] != native_surface:
        raise ValueError(
            "replayed final surface differs from the saved native checkpoint"
        )

    PUBLIC_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    public_row = {
        **row,
        "checkpoint_path": str(saved_checkpoint.relative_to(ROOT)),
    }
    source_bundle = {
        "schema_version": 2,
        "case_id": CASE_ID,
        "source_row": public_row,
        "origin": {
            "rows_file": str(ROWS.relative_to(ROOT)),
            "rows_line_number": line_number,
            "rows_sha256": hashlib.sha256(ROWS.read_bytes()).hexdigest(),
            "native_checkpoint_file": str(saved_checkpoint.relative_to(ROOT)),
            "native_checkpoint_sha256": row["checkpoint_sha256"],
        },
        "native_checkpoint_verification": {
            "exact_surface_match": True,
            "replayed_surface_sha256": hashlib.sha256(
                frames[-1]["surface_path"].encode()
            ).hexdigest(),
            "native_surface_sha256": hashlib.sha256(
                native_surface.encode()
            ).hexdigest(),
        },
    }
    PUBLIC_SOURCE.write_text(
        json.dumps(source_bundle, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )

    document = {
        "schema_version": 2,
        "case_id": CASE_ID,
        "scope": "Seven replayed checkpoints remeasured from both via walls; the final frame exactly matches the saved native checkpoint.",
        "geometry": geometry,
        "recipe": recipe,
        "numerics": row["numerics"],
        "target": {
            "depth": row["target"]["etch_depth"],
            "depth_tolerance": row["target"]["depth_tolerance"],
            "maximum_cd_error": row["target"]["max_width_error"],
            "maximum_bow": row["target"]["max_wall_bulge"],
            "basis": {
                "classification": "assumed_study_target",
                "physical_qualification": False,
                "source": {
                    "path": "program.md",
                    "sha256": checkpoint.file_sha256(ROOT / "program.md"),
                    "section": PROGRAM_SECTION,
                },
            },
        },
        "view_box": [
            -geometry["x_extent"] / 2,
            -0.25,
            geometry["x_extent"],
            geometry["y_extent"] + 0.25,
        ],
        "frames": frames,
        "citations": [
            {
                "path": str(PUBLIC_SOURCE.relative_to(ROOT)),
                "sha256": hashlib.sha256(PUBLIC_SOURCE.read_bytes()).hexdigest(),
                "selector": selector,
            }
            for selector in ("/source_row", "/native_checkpoint_verification")
        ],
    }
    OUTPUT.write_text(
        json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()

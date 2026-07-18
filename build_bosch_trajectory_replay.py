"""Rerun one saved Bosch case and export seven actual profile checkpoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import viennaps as ps

import build_bosch_tutorial_data as tutorial
import native_domain_checkpoint as checkpoint
import traveler_metrics as tm
import tsv_process as tp


ROOT = Path(__file__).resolve().parent
ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_interior_refinement_rows.jsonl"
OUTPUT = ROOT / "bosch_trajectory_replay.json"
CASE_ID = "aac0e99de49584cc"
CHECKPOINT_CYCLES = {1, 4, 7, 10, 13, 16, 18}


def source_row() -> tuple[dict, int]:
    for line_number, line in enumerate(ROWS.read_text().splitlines(), 1):
        row = json.loads(line)
        if row["case_id"] == CASE_ID:
            return row, line_number
    raise ValueError(f"missing source case {CASE_ID}")


def silicon_path(domain) -> str:
    mesh = next(
        mesh
        for mesh in tm.raw_level_set_meshes(domain)
        if mesh["material"] == ps.Material.Si
    )
    return tutorial.surface_path(mesh)


def main() -> None:
    row, line_number = source_row()
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
    history = {record["cycle"]: record for record in row["cycle_history"]}
    frames = []

    def capture(current, cycle):
        if cycle not in CHECKPOINT_CYCLES:
            return
        record = history[cycle]
        frames.append(
            {
                "cycle": cycle,
                "progress": cycle / max(CHECKPOINT_CYCLES),
                "surface_path": silicon_path(current),
                "metrics": {
                    "depth": record["depth"],
                    "cd_top": record["cd_top"],
                    "cd_middle": record["cd_middle"],
                    "cd_bottom": record["cd_bottom"],
                    "maximum_cd_error": record["max_cd_error"],
                    "bow": record["max_bow"],
                    "scallop_rms": record["scallop_rms"],
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
    saved = checkpoint.load_domain_checkpoint(
        Path(row["checkpoint_path"]), expected_sha256=row["checkpoint_sha256"]
    )
    if frames[-1]["surface_path"] != silicon_path(saved):
        raise ValueError("replayed final surface differs from the saved native checkpoint")

    document = {
        "schema_version": 1,
        "case_id": CASE_ID,
        "scope": "Seven actual checkpoints from one reproducible 500-ray Bosch trajectory.",
        "recipe": recipe,
        "numerics": row["numerics"],
        "frames": frames,
        "source": {
            "path": str(ROWS.relative_to(ROOT)),
            "line_number": line_number,
            "sha256": hashlib.sha256(ROWS.read_bytes()).hexdigest(),
            "native_checkpoint_sha256": row["checkpoint_sha256"],
        },
    }
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()

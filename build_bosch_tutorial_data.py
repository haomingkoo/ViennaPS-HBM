"""Export reviewed Bosch factor-pair profiles for the tutorial."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import viennaps as ps

import native_domain_checkpoint as checkpoint
from process_config import PROCESS_CONFIG
import profile_shape_metrics as psm
import traveler_metrics as tm


ROOT = Path(__file__).resolve().parent
INTERACTION_ROWS = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_rows.jsonl"
INTERACTION_REVIEW = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_review.json"
INTERIOR_ROWS = ROOT / "evidence/numerical/v3_bosch_interior_refinement_rows.jsonl"
OUTPUT = ROOT / "bosch_tutorial_data.json"
PUBLIC_EVIDENCE = Path("evidence/numerical")
TUTORIAL_CHECKPOINTS = ROOT / "evidence/bosch/tutorial_checkpoints"
ETCH_TARGETS = PROCESS_CONFIG["targets"]["etch"]

FACTOR_COPY = {
    "etch_time": {
        "label": "Etch phase time per cycle",
        "kind": "model control",
        "equipment_influences": ["etch-step duration", "reactive-gas delivery"],
        "meaning": "Changes the etch dose applied during every cycle.",
        "direction": "Higher means a longer simulated etch phase.",
        "calibration_status": "Recipe-linked",
        "calibration_note": "Etch-step time is a direct equipment analogue. The simulated time scale still needs a measured etch-rate match.",
    },
    "deposition_thickness": {
        "label": "Passivation added per cycle",
        "kind": "model control",
        "equipment_influences": ["passivation-step duration", "passivation-gas delivery"],
        "meaning": "Changes the protective layer added before the next etch phase.",
        "direction": "Higher means more passivation is added per cycle.",
        "calibration_status": "Fit from data",
        "calibration_note": "Passivation time and gas delivery influence this value, but film added per cycle must be fitted from measured profiles.",
    },
    "neutral_rate": {
        "label": "Neutral removal strength",
        "kind": "model coefficient",
        "equipment_influences": ["etch chemistry", "reactive-species flux"],
        "meaning": "Scales removal driven by simulated neutral particles.",
        "direction": "More negative means stronger neutral removal.",
        "calibration_status": "Fit from data",
        "calibration_note": "Fit this effective rate from measured etch depth and wall motion across recipe splits.",
    },
    "neutral_sticking_probability": {
        "label": "Neutral surface-reaction probability",
        "kind": "model coefficient",
        "equipment_influences": ["chemistry", "pressure", "temperature", "surface condition"],
        "meaning": "Changes whether a neutral particle reacts or reflects.",
        "direction": "Higher means more reactions on first contact and fewer reflections.",
        "calibration_status": "Fit from data",
        "calibration_note": "Infer this effective probability from profile response. It is not one machine setting.",
    },
    "ion_rate": {
        "label": "Directional removal strength",
        "kind": "model coefficient",
        "equipment_influences": ["platen bias", "ion energy", "plasma state"],
        "meaning": "Scales removal driven by simulated ions.",
        "direction": "More negative means stronger directional removal.",
        "calibration_status": "Fit from data",
        "calibration_note": "Fit this effective rate from depth and profile response across bias and plasma splits.",
    },
    "ion_source_exponent": {
        "label": "Ion arrival directionality",
        "kind": "model coefficient",
        "equipment_influences": ["pressure", "source and bias conditions", "reactor geometry"],
        "meaning": "Higher values concentrate simulated ion arrival toward the surface normal.",
        "direction": "Higher means a narrower arrival-angle distribution.",
        "calibration_status": "Fit from data",
        "calibration_note": "Fit the angular distribution from profile response or plasma diagnostics. It is not a pressure or bias value.",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def surface_path(mesh: dict) -> str:
    segments = np.asarray(mesh["nodes"])[np.asarray(mesh["lines"], dtype=int)][:, :, :2]
    return "".join(
        f"M{start[0]:.5f} {start[1]:.5f}L{end[0]:.5f} {end[1]:.5f}"
        for start, end in segments
    )


def material_id(material) -> str:
    if material == ps.Material.Mask:
        return "mask"
    if material == ps.Material.Si:
        return "silicon"
    return str(material)


def silicon_mesh(row: dict) -> dict:
    checkpoint_path = TUTORIAL_CHECKPOINTS / Path(row["checkpoint_path"]).name
    domain = checkpoint.load_domain_checkpoint(
        checkpoint_path, expected_sha256=row["checkpoint_sha256"]
    )
    mesh = next(
        mesh
        for mesh in tm.raw_level_set_meshes(domain)
        if mesh["material"] == ps.Material.Si
    )
    del domain
    gc.collect()
    return mesh


def materials(mesh: dict) -> list[dict]:
    return [
        {"id": material_id(mesh["material"]), "surface_path": surface_path(mesh)}
    ]


def public_metrics(row: dict, mesh: dict) -> dict:
    review = psm.measure_target_via_profile_2d(
        mesh["nodes"],
        mesh["lines"],
        surface_y=0.0,
        target_cd=ETCH_TARGETS["target_width"],
        target_depth=ETCH_TARGETS["target_depth"],
        domain_x_bounds=(-0.5, 0.5),
        grid_delta=row["numerics"]["grid_delta"],
        allow_partial_floor=True,
    )
    if review["state"] not in {"complete", "partial"}:
        raise ValueError(f"full-width measurement unavailable for {row['case_id']}")
    etch = review["metrics"]
    records = review["diagnostics"]["sample_records"]
    fractions = np.asarray([-record["y"] / etch["depth"] for record in records])
    cds = np.asarray(
        [record["right_wall_x"] - record["left_wall_x"] for record in records]
    )
    radii = 0.5 * cds
    straight = np.linspace(radii[0], radii[-1], len(radii))
    cd_index = int(np.argmax(np.abs(cds - ETCH_TARGETS["target_width"])))
    bow_index = int(np.argmax(np.abs(radii - straight)))
    hard_gate_pass = (
        abs(etch["depth"] - ETCH_TARGETS["target_depth"])
        <= ETCH_TARGETS["depth_tolerance"]
        and etch["max_cd_error"] <= ETCH_TARGETS["max_width_error"]
        and etch["max_bow"] <= ETCH_TARGETS["max_wall_bulge"]
    )
    return {
        "depth": etch["depth"],
        "cd_top": etch["cd_top"],
        "cd_middle": etch["cd_middle"],
        "cd_bottom": etch["cd_bottom"],
        "maximum_cd_error": etch["max_cd_error"],
        "bow": etch["max_bow"],
        "scallop_rms": etch["scallop_rms"],
        "sidewall_angle_deg": etch["sidewall_angle_deg"],
        "profile_shape_rmse": etch["profile_shape_rmse"],
        "profile_max_deviation": etch["profile_max_deviation"],
        "profile_symmetry_rms": etch["profile_symmetry_rms"],
        "profile_wall_rmse": etch["profile_wall_rmse"],
        "profile_floor_rmse": etch["profile_floor_rmse"],
        "floor_flatness_pv": etch["floor_flatness_pv"],
        "floor_center_relief": etch["floor_center_relief"],
        "floor_resolution_status": etch["floor_resolution_status"],
        "profile_measurement_status": review["state"],
        "selected_cycle": row["selected_cycle"],
        "hard_gate_pass": bool(hard_gate_pass),
        "trajectory_class": row["trajectory_classification"],
        "measurement_method": "full_width_two_wall_remeasurement",
        "numerically_qualified": False,
        "maximum_cd_error_fraction": float(fractions[cd_index]),
        "maximum_cd_error_cd": float(cds[cd_index]),
        "maximum_bow_fraction": float(fractions[bow_index]),
        "maximum_bow_actual_radius": float(radii[bow_index]),
        "maximum_bow_reference_radius": float(straight[bow_index]),
    }


def interaction_case(row: dict, line_number: int) -> dict:
    anchor = row["anchor_reasons"][0]
    _, first, second, first_level, second_level = anchor.split(":")
    mesh = silicon_mesh(row)
    return {
        "case_id": row["case_id"],
        "interaction": [first, second],
        "levels": {first: first_level, second: second_level},
        "values": {first: row["recipe"][first], second: row["recipe"][second]},
        "recipe": row["recipe"],
        "metrics": public_metrics(row, mesh),
        "materials": materials(mesh),
        "elapsed_s": row["elapsed_s"],
        "rays_per_point": row["numerics"]["rays_per_point"],
        "checkpoint_sha256": row["checkpoint_sha256"],
        "citation": {
            "path": str(PUBLIC_EVIDENCE / INTERACTION_ROWS.name),
            "line_number": line_number,
            "sha256": sha256(INTERACTION_ROWS),
        },
    }


def interior_case(row: dict, line_number: int) -> dict:
    mesh = silicon_mesh(row)
    return {
        "case_id": row["case_id"],
        "normalized_coordinates": row["normalized_coordinates"],
        "recipe": row["recipe"],
        "metrics": public_metrics(row, mesh),
        "materials": materials(mesh),
        "elapsed_s": row["elapsed_s"],
        "rays_per_point": row["numerics"]["rays_per_point"],
        "checkpoint_sha256": row["checkpoint_sha256"],
        "citation": {
            "path": str(PUBLIC_EVIDENCE / INTERIOR_ROWS.name),
            "line_number": line_number,
            "sha256": sha256(INTERIOR_ROWS),
        },
    }


def build_case_group(kind: str) -> list[dict]:
    """Build one checkpoint group in a fresh process."""
    if kind == "interaction":
        rows = load_rows(INTERACTION_ROWS)
        return [interaction_case(row, index) for index, row in enumerate(rows, 1)]
    if kind == "interior":
        rows = load_rows(INTERIOR_ROWS)
        return [interior_case(row, index) for index, row in enumerate(rows, 1)]
    raise ValueError(f"unknown case group: {kind}")


def main() -> None:
    interaction_rows = load_rows(INTERACTION_ROWS)
    interior_rows = load_rows(INTERIOR_ROWS)
    review = json.loads(INTERACTION_REVIEW.read_text())
    if len(interaction_rows) != 28 or review["valid_case_count"] != 28:
        raise ValueError("expected 28 reviewed interaction cases")
    if len(interior_rows) != 18:
        raise ValueError("expected 18 completed interior cases")

    with tempfile.TemporaryDirectory() as directory:
        paths = {
            kind: Path(directory) / f"{kind}.json"
            for kind in ("interaction", "interior")
        }
        for kind, path in paths.items():
            subprocess.run(
                [sys.executable, __file__, "--group", kind, "--output", str(path)],
                check=True,
            )
        interactions = json.loads(paths["interaction"].read_text())
        interior = json.loads(paths["interior"].read_text())
    remeasured_passes = sum(
        case["metrics"]["hard_gate_pass"] for case in interactions
    )
    document = {
        "schema_version": 3,
        "title": "Dry-etch multi-factor study",
        "scope": (
            "Exact 500-ray discovery cases, remeasured from both saved via walls. "
            "They compare factor pairs against "
            "assumed study bands; they do not estimate interaction uncertainty, "
            "define a machine recipe, or confirm a process window."
        ),
        "equipment_mapping": {
            "relationship": "many-to-many and uncalibrated",
            "chain": [
                "equipment controls",
                "plasma and surface state not modeled here",
                "effective ViennaPS controls",
                "simulated profile",
                "geometry measurements",
            ],
        },
        "measurement_implementation": {
            "path": "profile_shape_metrics.py",
            "sha256": checkpoint.file_sha256(ROOT / "profile_shape_metrics.py"),
            "symbol": "measure_target_via_profile_2d",
        },
        "factors": FACTOR_COPY,
        "targets": {
            "basis": {
                "classification": "assumed_study_target",
                "physical_qualification": False,
                "source": {
                    "path": "program.md",
                    "sha256": checkpoint.file_sha256(ROOT / "program.md"),
                    "section": "Assumed study comparison bands",
                },
            },
            "depth": ETCH_TARGETS["target_depth"],
            "depth_tolerance": ETCH_TARGETS["depth_tolerance"],
            "target_cd": ETCH_TARGETS["target_width"],
            "maximum_cd_error": ETCH_TARGETS["max_width_error"],
            "maximum_bow": ETCH_TARGETS["max_wall_bulge"],
        },
        "interactions": interactions,
        "interior_cases": interior,
        "interior_study": {
            "case_count": len(interior),
            "factor_order": [
                "etch_time",
                "deposition_thickness",
                "ion_source_exponent",
                "ion_rate",
                "neutral_rate",
                "neutral_sticking_probability",
            ],
            "coordinate_levels": [-0.5, 0.0, 0.5],
            "method": "18-case D-optimal interior refinement",
            "interpretation": (
                "Each profile is one saved six-control combination. The browser "
                "does not interpolate or rerun ViennaPS."
            ),
        },
        "default_interaction": ["ion_source_exponent", "ion_rate"],
        "default_interior_case": "aac0e99de49584cc",
        "measurement_example_case_id": "7405eb159356c564",
        "review": {
            "valid_cases": review["valid_case_count"],
            "hard_gate_passes": remeasured_passes,
            "decision": (
                "All 28 saved profiles were remeasured from both walls. Counts use assumed study bands; no factor effect or interaction is qualified."
            ),
            "derivation": "Count /interactions/*/metrics/hard_gate_pass; each interaction carries its source-row citation.",
        },
    }
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=("interaction", "interior"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.group:
        if args.output is None:
            parser.error("--output is required with --group")
        args.output.write_text(
            json.dumps(build_case_group(args.group), allow_nan=False)
        )
    else:
        main()

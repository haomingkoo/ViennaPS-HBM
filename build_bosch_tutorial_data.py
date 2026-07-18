"""Export reviewed Bosch factor-pair profiles for the tutorial."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import viennaps as ps

import native_domain_checkpoint as checkpoint
from process_config import PROCESS_CONFIG
import traveler_metrics as tm


ROOT = Path(__file__).resolve().parent
INTERACTION_ROWS = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_rows.jsonl"
INTERACTION_REVIEW = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_review.json"
INTERIOR_ROWS = ROOT / "evidence/numerical/v3_bosch_interior_refinement_rows.jsonl"
OUTPUT = ROOT / "bosch_tutorial_data.json"
PUBLIC_EVIDENCE = Path("evidence/numerical")
TUTORIAL_CHECKPOINTS = ROOT / "evidence/bosch/tutorial_checkpoints"
ETCH_TARGETS = PROCESS_CONFIG["targets"]["etch"]
INTERIOR_PUBLIC_CASES = {
    "aac0e99de49584cc",
    "5e3a68ad9b65a792",
    "39f57e028c34770e",
}

FACTOR_COPY = {
    "etch_time": {
        "label": "Etch phase time per cycle",
        "kind": "model control",
        "equipment_influences": ["etch-step duration", "reactive-gas delivery"],
        "meaning": "Changes the etch dose applied during every cycle.",
        "direction": "Higher means a longer simulated etch phase.",
    },
    "deposition_thickness": {
        "label": "Passivation added per cycle",
        "kind": "model control",
        "equipment_influences": ["passivation-step duration", "passivation-gas delivery"],
        "meaning": "Changes the protective layer added before the next etch phase.",
        "direction": "Higher means more passivation is added per cycle.",
    },
    "neutral_rate": {
        "label": "Neutral removal strength",
        "kind": "model coefficient",
        "equipment_influences": ["etch chemistry", "reactive-species flux"],
        "meaning": "Scales removal driven by simulated neutral particles.",
        "direction": "More negative means stronger neutral removal.",
    },
    "neutral_sticking_probability": {
        "label": "Neutral surface-reaction probability",
        "kind": "model coefficient",
        "equipment_influences": ["chemistry", "pressure", "temperature", "surface condition"],
        "meaning": "Changes whether a neutral particle reacts or reflects.",
        "direction": "Higher means more reactions on first contact and fewer reflections.",
    },
    "ion_rate": {
        "label": "Directional removal strength",
        "kind": "model coefficient",
        "equipment_influences": ["platen bias", "ion energy", "plasma state"],
        "meaning": "Scales removal driven by simulated ions.",
        "direction": "More negative means stronger directional removal.",
    },
    "ion_source_exponent": {
        "label": "Ion arrival directionality",
        "kind": "model coefficient",
        "equipment_influences": ["pressure", "source and bias conditions", "reactor geometry"],
        "meaning": "Higher values concentrate simulated ion arrival toward the surface normal.",
        "direction": "Higher means a narrower arrival-angle distribution.",
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
    return next(
        mesh
        for mesh in tm.raw_level_set_meshes(domain)
        if mesh["material"] == ps.Material.Si
    )


def materials(mesh: dict) -> list[dict]:
    return [
        {"id": material_id(mesh["material"]), "surface_path": surface_path(mesh)}
    ]


def public_metrics(row: dict, mesh: dict) -> dict:
    review = tm.measure_full_via_profile_2d(
        mesh["nodes"],
        mesh["lines"],
        surface_y=0.0,
        target_cd=ETCH_TARGETS["target_width"],
        domain_x_bounds=(-0.5, 0.5),
        grid_delta=row["numerics"]["grid_delta"],
    )
    if review["state"] != "complete":
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


def main() -> None:
    interaction_rows = load_rows(INTERACTION_ROWS)
    interior_rows = load_rows(INTERIOR_ROWS)
    review = json.loads(INTERACTION_REVIEW.read_text())
    if len(interaction_rows) != 28 or review["valid_case_count"] != 28:
        raise ValueError("expected 28 reviewed interaction cases")
    if len(interior_rows) != 18:
        raise ValueError("expected 18 completed interior cases")

    interactions = [
        interaction_case(row, index)
        for index, row in enumerate(interaction_rows, 1)
    ]
    interior = [
        interior_case(row, index)
        for index, row in enumerate(interior_rows, 1)
        if row["case_id"] in INTERIOR_PUBLIC_CASES
    ]
    remeasured_passes = sum(
        case["metrics"]["hard_gate_pass"] for case in interactions
    )
    document = {
        "schema_version": 2,
        "title": "Dry-etch factor pairs",
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
        "default_interaction": ["neutral_rate", "neutral_sticking_probability"],
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
    main()

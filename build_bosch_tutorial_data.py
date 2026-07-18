"""Export reviewed Bosch interaction profiles for the tutorial."""

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
INTERACTION_ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_interactions_rows.jsonl"
INTERACTION_REVIEW = ROOT / "autoresearch-results/restart_audit/v3_bosch_cheap_interactions_review.json"
INTERIOR_ROWS = ROOT / "autoresearch-results/restart_audit/v3_bosch_interior_refinement_rows.jsonl"
OUTPUT = ROOT / "bosch_tutorial_data.json"
PUBLIC_EVIDENCE = Path("evidence/numerical")
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


def materials(row: dict) -> list[dict]:
    domain = checkpoint.load_domain_checkpoint(
        Path(row["checkpoint_path"]), expected_sha256=row["checkpoint_sha256"]
    )
    return [
        {"id": material_id(mesh["material"]), "surface_path": surface_path(mesh)}
        for mesh in tm.raw_level_set_meshes(domain)
        if mesh["material"] == ps.Material.Si
    ]


def public_metrics(row: dict) -> dict:
    etch = row["selected_cycle_metrics"]["etch"]
    fractions = np.asarray(etch["sample_fractions"], dtype=float)
    cds = np.asarray(etch["sample_cds"], dtype=float)
    radii = cds / 2.0
    straight = np.linspace(radii[0], radii[-1], len(radii))
    cd_index = int(np.argmax(np.abs(cds - ETCH_TARGETS["target_width"])))
    bow_index = int(np.argmax(np.abs(radii - straight)))
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
        "hard_gate_pass": row["hard_gate_pass"],
        "trajectory_class": row["trajectory_classification"],
        "maximum_cd_error_fraction": float(fractions[cd_index]),
        "maximum_cd_error_cd": float(cds[cd_index]),
        "maximum_bow_fraction": float(fractions[bow_index]),
        "maximum_bow_actual_radius": float(radii[bow_index]),
        "maximum_bow_reference_radius": float(straight[bow_index]),
    }


def interaction_case(row: dict, line_number: int) -> dict:
    anchor = row["anchor_reasons"][0]
    _, first, second, first_level, second_level = anchor.split(":")
    return {
        "case_id": row["case_id"],
        "interaction": [first, second],
        "levels": {first: first_level, second: second_level},
        "values": {first: row["recipe"][first], second: row["recipe"][second]},
        "recipe": row["recipe"],
        "metrics": public_metrics(row),
        "materials": materials(row),
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
    return {
        "case_id": row["case_id"],
        "normalized_coordinates": row["normalized_coordinates"],
        "recipe": row["recipe"],
        "metrics": public_metrics(row),
        "materials": materials(row),
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
    document = {
        "schema_version": 1,
        "title": "Dry-etch interactions",
        "scope": (
            "Exact 500-ray discovery cases. They identify coupled failure regions; "
            "they do not define a machine recipe or confirmed process window."
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
        "review": {
            "valid_cases": review["valid_case_count"],
            "hard_gate_passes": review["hard_gate_pass_count"],
            "decision": review["decision"],
            "citation": {
                "path": str(PUBLIC_EVIDENCE / INTERACTION_REVIEW.name),
                "sha256": sha256(INTERACTION_REVIEW),
                "selector": "/decision",
            },
        },
    }
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()

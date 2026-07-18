"""Project the complete registry into the first mask/Bosch research block."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "pattern_bosch_factor_projection.json"
REGISTRY_PATH = ROOT / "factor_registry.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


MAIN_RANGE_FINDING = {
    "pattern_radius_input",
    "phase_factor_mask_taper",
    "phase_factor_num_cycles",
    "phase_factor_etch_time",
    "phase_factor_neutral_rate",
    "phase_factor_neutral_sticking_probability",
    "phase_factor_initial_etch_time",
    "phase_factor_deposition_thickness",
    "phase_factor_deposition_sticking_probability",
    "phase_factor_ion_source_exponent",
    "phase_factor_theta_r_min",
    "bosch_ion_rate",
}

MASK_EROSION_BLOCK = {
    "pattern_mask_height_input",
    "bosch_mask_ion_rate",
}

OBSERVATION_ONLY = {"bosch_on_cycle", "bosch_on_polymer"}

LIVE_LOCATORS = {
    "pattern_radius_input": ("defaults.geometry.radius", "make_initial_geometry", "radius"),
    "pattern_mask_height_input": ("defaults.geometry.mask_height", "make_initial_geometry", "mask_height"),
    "phase_factor_mask_taper": ("defaults.geometry.mask_taper", "make_initial_geometry", "taper"),
    "phase_factor_num_cycles": ("defaults.bosch.num_cycles", "bosch_etch", "num_cycles"),
    "phase_factor_etch_time": ("defaults.bosch.etch_time", "bosch_etch", "etch_time"),
    "phase_factor_neutral_rate": ("defaults.bosch.neutral_rate", "bosch_etch", "neutral_rate"),
    "phase_factor_neutral_sticking_probability": ("defaults.bosch.neutral_sticking_probability", "bosch_etch", "neutral_sticking_probability"),
    "phase_factor_initial_etch_time": ("defaults.bosch.initial_etch_time", "bosch_etch", "initial_etch_time"),
    "phase_factor_deposition_thickness": ("defaults.bosch.deposition_thickness", "bosch_etch", "deposition_thickness"),
    "phase_factor_deposition_sticking_probability": ("defaults.bosch.deposition_sticking_probability", "bosch_etch", "deposition_sticking_probability"),
    "phase_factor_ion_source_exponent": ("defaults.bosch.ion_source_exponent", "bosch_etch", "ion_source_exponent"),
    "phase_factor_theta_r_min": ("defaults.bosch.theta_r_min", "bosch_etch", "theta_r_min"),
    "bosch_ion_rate": ("defaults.bosch.ion_rate", "bosch_etch", "ion_rate"),
    "bosch_mask_ion_rate": ("defaults.bosch.mask_ion_rate", "bosch_etch", "mask_ion_rate"),
}

COUPLING_NOTES = {
    "phase_factor_num_cycles": "Cycle count changes cumulative etch, polymer deposition, polymer removal, and random-stream length. Use a matched-total-dose block or predeclare its cumulative-dose interactions before screening.",
    "phase_factor_deposition_thickness": "The wrapper uses this value for polymer deposition and an equal-magnitude directional polymer-removal rate.",
    "phase_factor_ion_source_exponent": "The wrapper uses this directionality value for silicon-ion transport and directional polymer removal.",
    "pattern_mask_height_input": "Mask survival also depends on cumulative ion exposure. Bridge the erosion block to low and high main-screen exposure.",
    "bosch_mask_ion_rate": "Mask survival also depends on cumulative ion exposure. Bridge the erosion block to low and high main-screen exposure.",
}

SPECIAL_FIXED_REASONS = {
    "pattern_hole_shape": "Use FULL 2D geometry for this mask/Bosch block so both sidewalls and the floor remain visible. Treat dimensionality as a separate challenge.",
    "single_particle_mask_materials": "Keep the polymer-removal mask material fixed to the declared pattern mask.",
    "bosch_polymer_deposition_duration": "Fix duration to 1.0 as the deposition-rate scale convention. In this single phase, rate and duration enter as one commanded dose.",
    "bosch_polymer_removal_duration": "Fix duration to 1.0 as the removal-rate scale convention. Varying both rate and duration would duplicate one commanded dose.",
    "bosch_polymer_removal_rate": "The wrapper ties removal magnitude to deposition_thickness. It cannot be estimated independently until an explicit removal-to-deposition ratio is wired.",
    "bosch_polymer_removal_sticking": "The wrapper fixes first-contact removal. Treat a different transport law as a separate model-family challenge.",
}


def is_relevant_record(record: dict) -> bool:
    return bool({"pattern", "bosch_etch"} & set(record["step"].split("/")))


def tutorial_role(record: dict, status: str) -> str:
    """Return the plain-language role shown to tutorial readers."""
    factor_id = record["id"]
    if status == "response_or_derived_input":
        return "assumed_study_target"
    if status == "separate_accuracy_study":
        return "numerical_setting"
    if status == "observation_only":
        return "observation_callback"
    if status == "blocked_requires_model_and_calibration":
        return "equipment_control_unmapped"
    if status == "blocked_not_wired":
        return "available_model_input_unwired"
    if status == "model_limitation":
        return "model_limitation"
    if status == "fixed_structural_choice":
        return "fixed_choice"
    if factor_id in {
        "pattern_radius_input",
        "pattern_mask_height_input",
        "phase_factor_mask_taper",
    }:
        return "geometry_input"
    return "effective_model_control"


def disposition(record: dict) -> tuple[str, str]:
    factor_id = record["id"]
    if factor_id in MAIN_RANGE_FINDING:
        return (
            "include_range_finding",
            "Implemented control; qualify its model-space range before screening.",
        )
    if factor_id in MASK_EROSION_BLOCK:
        return (
            "separate_mask_erosion_block",
            "Study mask height and erosion together before crossing them into the main etch screen.",
        )
    if factor_id in OBSERVATION_ONLY:
        return (
            "observation_only",
            "Checkpoint callback; records intermediate geometry but is not a process factor.",
        )
    if record["classification"] == "numerical_control":
        return (
            "separate_accuracy_study",
            "Computational setting; qualify speed and measurement agreement separately.",
        )
    if record["doe_eligibility"] == "requires_model_and_calibration":
        return (
            "blocked_requires_model_and_calibration",
            "Real equipment control has no calibrated mapping into the current model.",
        )
    if record["doe_eligibility"] == "not_wired":
        return (
            "blocked_not_wired",
            "Available concept or API input is not implemented in the active wrapper.",
        )
    if record["classification"] == "product_specification":
        return (
            "response_or_derived_input",
            "Comparison target or value derived from another input; do not count it as an independent factor.",
        )
    if record["classification"] == "model_limitation":
        return (
            "model_limitation",
            "Missing physics is recorded as a limitation, not converted into a numeric factor.",
        )
    if record["doe_eligibility"] == "range_requalification_required":
        return (
            "include_range_finding",
            "Implemented control; qualify its model-space range before screening.",
        )
    if factor_id in SPECIAL_FIXED_REASONS:
        return "fixed_structural_choice", SPECIAL_FIXED_REASONS[factor_id]
    return (
        "fixed_structural_choice",
        "Keep fixed in the first block; changing it would define a different geometry or process path.",
    )


def build() -> dict:
    registry = json.loads(REGISTRY_PATH.read_text())
    relevant = [
        record
        for record in registry["records"]
        if is_relevant_record(record)
    ]
    factors = []
    for record in relevant:
        status, reason = disposition(record)
        locator = LIVE_LOCATORS.get(record["id"])
        factors.append(
            {
                "registry_id": record["id"],
                "name": record["name"],
                "owner_api": record["owner_api"],
                "classification": record["classification"],
                "implementation_status": record["implementation_status"],
                "registry_doe_eligibility": record["doe_eligibility"],
                "disposition": status,
                "tutorial_role": tutorial_role(record, status),
                "reason": reason,
                "implementation_locator": (
                    {
                        "config_key": locator[0],
                        "code_path": "tsv_process.py",
                        "callable": locator[1],
                        "argument": locator[2],
                    }
                    if locator
                    else None
                ),
                "coupling_note": COUPLING_NOTES.get(record["id"]),
                "range_provenance": record["range_provenance"],
                "responses_expected_to_change": record["metrics_affected"],
                "known_interactions": record["known_interactions"],
            }
        )
    counts = Counter(item["disposition"] for item in factors)
    return {
        "schema_version": 1,
        "scope": "Complete mask/Bosch registry projection before range finding; not a design matrix.",
        "launch_status": "blocked_pending_ranges_measurements_and_numerics",
        "sources": [
            {"path": "factor_registry.json", "sha256": digest(REGISTRY_PATH)},
            {
                "path": "build_pattern_bosch_factor_projection.py",
                "sha256": digest(ROOT / "build_pattern_bosch_factor_projection.py"),
            },
        ],
        "factor_count": len(factors),
        "counts_by_disposition": dict(sorted(counts.items())),
        "factors": factors,
        "screening_rule": (
            "The pair viewer may display two factors at once. The experiment may not "
            "drop an eligible factor because it was absent from an earlier campaign."
        ),
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(
        f"mask/Bosch projection: {document['factor_count']} records, "
        f"{document['counts_by_disposition']['include_range_finding']} in main range finding"
    )


if __name__ == "__main__":
    main()

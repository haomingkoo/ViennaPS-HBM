"""Build the measurement contract required before mask/Bosch screening."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "pattern_bosch_measurement_contract.json"


def digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def metric(
    metric_id: str,
    step: str,
    output_key: str,
    definition: str,
    region: str,
    *,
    units: str = "model length",
) -> dict:
    return {
        "id": metric_id,
        "step": step,
        "extractor": {
            "path": "traveler_metrics.py",
            "symbol": (
                "pattern_metrics_2d" if step == "mask" else "etch_profile_metrics_2d"
            ),
            "output_key": output_key,
        },
        "definition": definition,
        "region": region,
        "units": units,
        "required_for": ["range_finding", "screening"],
        "missing_value_rule": "block the affected decision; never replace with zero",
        "detection_limit": None,
        "known_failure_evidence": None,
        "prescribed_control_evidence": None,
        "save_reload_parity": None,
        "numerical_allowance": None,
        "repeat_allowance": None,
        "useful_change_threshold": None,
        "qualification_status": "pending",
    }


def build() -> dict:
    metrics = [
        metric(
            "mask_opening_cd_bottom",
            "mask",
            "opening_cd_bottom",
            "Opening width near the wafer surface.",
            "Horizontal intersection at 5% of the measured mask height.",
        ),
        metric(
            "mask_opening_cd_middle",
            "mask",
            "opening_cd_middle",
            "Opening width at the middle of the mask.",
            "Horizontal intersection at 50% of the measured mask height.",
        ),
        metric(
            "mask_opening_cd_top",
            "mask",
            "opening_cd_top",
            "Opening width near the top of the mask.",
            "Horizontal intersection at 85% of the measured mask height.",
        ),
        metric(
            "mask_height",
            "mask",
            "mask_height",
            "Distance from the wafer surface to the highest mask point.",
            "Complete extracted mask boundary.",
        ),
        metric(
            "mask_sidewall_angle",
            "mask",
            "mask_sidewall_angle_deg",
            "Angle implied by the change in opening width through the mask.",
            "Opening widths at 5% and 85% of the measured mask height.",
            units="degrees",
        ),
        metric(
            "etch_depth",
            "bosch_etch",
            "depth",
            "Vertical distance from the wafer surface to the via floor.",
            "Silicon boundary from the declared surface to extracted floor.",
        ),
        metric(
            "etch_cd_top",
            "bosch_etch",
            "cd_top",
            "Via width near the top of the etched depth.",
            "Horizontal intersection at 10% of the extracted depth.",
        ),
        metric(
            "etch_cd_middle",
            "bosch_etch",
            "cd_middle",
            "Via width at the middle of the etched depth.",
            "Horizontal intersection at 50% of the extracted depth.",
        ),
        metric(
            "etch_cd_bottom",
            "bosch_etch",
            "cd_bottom",
            "Via width near the bottom of the etched depth.",
            "Horizontal intersection at 85% of the extracted depth.",
        ),
        metric(
            "etch_minimum_cd",
            "bosch_etch",
            "cd_min",
            "Smallest sampled via width; used to detect a narrow neck.",
            "76 horizontal samples from 10% to 85% of the extracted depth.",
        ),
        metric(
            "etch_maximum_cd_error",
            "bosch_etch",
            "max_cd_error",
            "Largest absolute sampled difference from the declared comparison width.",
            "76 horizontal samples from 10% to 85% of the extracted depth.",
        ),
        metric(
            "etch_sidewall_angle",
            "bosch_etch",
            "sidewall_angle_deg",
            "Angle of the straight chord between the top and bottom sample widths.",
            "Widths at 10% and 85% of the extracted depth.",
            units="degrees",
        ),
        metric(
            "etch_bow",
            "bosch_etch",
            "max_bow",
            "Largest radial departure from the top-to-bottom straight chord.",
            "76 wall-radius samples from 10% to 85% of the extracted depth.",
        ),
        metric(
            "etch_scallop_rms",
            "bosch_etch",
            "scallop_rms",
            "Root-mean-square wall residual after a cubic smooth profile is removed.",
            "76 wall-radius samples from 10% to 85% of the extracted depth.",
        ),
    ]
    contrast_cases = {
        "mask_opening_cd_bottom": "mask_tapered",
        "mask_opening_cd_middle": "mask_tapered",
        "mask_opening_cd_top": "mask_tapered",
        "mask_height": "mask_short",
        "mask_sidewall_angle": "mask_tapered",
        "etch_depth": "etch_shallow",
        "etch_cd_top": "etch_tapered",
        "etch_cd_middle": "etch_narrow_neck",
        "etch_cd_bottom": "etch_tapered",
        "etch_minimum_cd": "etch_narrow_neck",
        "etch_maximum_cd_error": "etch_narrow_neck",
        "etch_sidewall_angle": "etch_tapered",
        "etch_bow": "etch_bowed",
        "etch_scallop_rms": "etch_scalloped",
    }
    evidence_path = "evidence/bosch/pattern_bosch_metric_controls.json"
    evidence_sha = digest(evidence_path)
    evidence_document = json.loads((ROOT / evidence_path).read_text())
    case_index = {
        case["id"]: index for index, case in enumerate(evidence_document["cases"])
    }
    for item in metrics:
        control_case = "mask_straight" if item["step"] == "mask" else "etch_straight"
        item["prescribed_control_evidence"] = {
            "path": evidence_path,
            "sha256": evidence_sha,
            "selector": f"/cases/{case_index[control_case]}",
        }
        item["known_failure_evidence"] = {
            "path": evidence_path,
            "sha256": evidence_sha,
            "selector": f"/cases/{case_index[contrast_cases[item['id']]]}",
        }
        roundtrip_path = "evidence/numerical/v3_pattern_bosch_stage2a_rows.jsonl"
        item["save_reload_parity"] = {
            "maximum_absolute_difference": 0.0,
            "path": roundtrip_path,
            "sha256": digest(roundtrip_path),
            "line_numbers": [1],
        }

    return {
        "schema_version": 1,
        "scope": "Mask-plus-Bosch measurement qualification; not process acceptance.",
        "launch_status": "blocked_pending_measurement_qualification",
        "sources": [
            {"path": path, "sha256": digest(path)}
            for path in (
                "build_pattern_bosch_measurement_contract.py",
                "traveler_metrics.py",
                "build_step_experiments.py",
                evidence_path,
                "evidence/numerical/v3_pattern_bosch_stage2a_rows.jsonl",
            )
        ],
        "metrics": metrics,
        "qualification_rule": (
            "Every required metric needs a detection limit, known-failure evidence, "
            "prescribed-control evidence, save/reload parity, numerical allowance, "
            "repeat allowance, and useful-change threshold before screening."
        ),
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"mask/Bosch measurement contract: {len(document['metrics'])} metrics")


if __name__ == "__main__":
    main()

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
    extractor = {
        "path": "traveler_metrics.py",
        "symbol": (
            "pattern_metrics_2d"
            if step == "mask"
            else "measure_full_via_profile_2d"
        ),
        "output_key": output_key,
        "sha256": digest("traveler_metrics.py"),
    }
    definition_payload = json.dumps(
        {
            "definition": definition,
            "region": region,
            "units": units,
            "extractor": extractor,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "id": metric_id,
        "step": step,
        "extractor": extractor,
        "definition": definition,
        "definition_sha256": hashlib.sha256(definition_payload.encode()).hexdigest(),
        "region": region,
        "units": units,
        "required_for": ["range_finding", "screening"],
        "missing_value_rule": "block the affected decision; never replace with zero",
        "representation_domain": (
            "full or explicitly symmetry-clipped 2D mask opening"
            if step == "mask"
            else "full 2D via with two walls and a centerline floor below the declared wafer surface"
        ),
        "analytic_reference_evidence": None,
        "feature_present_evidence": None,
        "missingness_evidence": None,
        "resolution_bracket": None,
        "save_reload_parity": None,
        "numerical_envelope": None,
        "repeat_envelope": None,
        "useful_change_threshold": None,
        "useful_change_evidence_class": None,
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
            "Mask taper angle; zero means vertical walls and positive means a wider opening near the top.",
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
            "Overall via taper angle; zero means the average wall is vertical.",
            "Straight reference between widths at 10% and 85% of the extracted depth.",
            units="degrees",
        ),
        metric(
            "etch_bow",
            "bosch_etch",
            "max_bow",
            "Largest horizontal gap between the average wall and its straight taper reference.",
            "76 half-width samples from 10% to 85% of the extracted depth.",
        ),
        metric(
            "etch_scallop_rms",
            "bosch_etch",
            "scallop_rms",
            "Typical small wall ripple after the smooth overall profile is removed.",
            "RMS residual from 76 half-width samples after a cubic fit.",
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
        item["analytic_reference_evidence"] = {
            "path": evidence_path,
            "sha256": evidence_sha,
            "selector": f"/cases/{case_index[control_case]}",
        }
        item["feature_present_evidence"] = {
            "path": evidence_path,
            "sha256": evidence_sha,
            "selector": f"/cases/{case_index[contrast_cases[item['id']]]}",
        }
        if item["step"] == "bosch_etch":
            missingness_path = "evidence/bosch/pattern_bosch_unavailable_profile_review.json"
            item["missingness_evidence"] = {
                "path": missingness_path,
                "sha256": digest(missingness_path),
                "selector": "/cases",
            }
            item["resolution_bracket"] = {
                "resolved_at_or_above": 3.0,
                "unresolved_at_or_below": 2.0,
                "units": "grid cells across the minimum via width",
                "scope": (
                    "Full-width measurement availability only; continuous-metric "
                    "precision remains unresolved."
                ),
                "source": {"path": evidence_path, "sha256": evidence_sha},
            }
        roundtrip_path = "evidence/numerical/v3_pattern_bosch_stage2a_rows.jsonl"
        item["save_reload_parity"] = {
            "maximum_absolute_difference": 0.0,
            "path": roundtrip_path,
            "sha256": digest(roundtrip_path),
            "line_numbers": [1],
        }

    return {
        "schema_version": 2,
        "scope": "Mask-plus-Bosch measurement qualification; not process acceptance.",
        "launch_status": "blocked_pending_measurement_qualification",
        "sources": [
            {"path": path, "sha256": digest(path)}
            for path in (
                "build_pattern_bosch_measurement_contract.py",
                "traveler_metrics.py",
                "build_step_experiments.py",
                evidence_path,
                "evidence/bosch/pattern_bosch_unavailable_profile_review.json",
                "evidence/numerical/v3_pattern_bosch_stage2a_rows.jsonl",
            )
        ],
        "metrics": metrics,
        "qualification_rule": (
            "Every response retained for screening needs an independently checked control, "
            "a declared representation domain, a resolution bracket, classified missingness, "
            "observed numerical and repeat envelopes, and a sourced or explicitly assumed "
            "useful-change threshold."
        ),
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"mask/Bosch measurement contract: {len(document['metrics'])} metrics")


if __name__ == "__main__":
    main()

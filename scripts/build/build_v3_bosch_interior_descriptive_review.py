"""Build a descriptive main-effect review of the 18 saved Bosch profiles."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "evidence/numerical/executed_sources/"
    "bb66a70_bosch_tutorial_data.json"
)
OUTPUT = ROOT / "evidence/numerical/v3_bosch_interior_descriptive_review.json"
FACTORS = (
    "etch_time",
    "deposition_thickness",
    "ion_source_exponent",
    "ion_rate",
    "neutral_rate",
    "neutral_sticking_probability",
)
METRICS = (
    "depth",
    "cd_top",
    "cd_middle",
    "cd_bottom",
    "bow",
    "sidewall_angle_deg",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject_constant(value: str):
    raise ValueError(f"invalid JSON constant {value}")


def load_cases() -> tuple[dict, list[dict]]:
    source = json.loads(SOURCE.read_text(), parse_constant=reject_constant)
    cases = source.get("interior_cases", [])
    if len(cases) != 18 or len({case.get("case_id") for case in cases}) != 18:
        raise ValueError("expected 18 unique interior cases")
    if source.get("interior_study", {}).get("factor_order") != list(FACTORS):
        raise ValueError("interior factor order differs")
    expected_lines = list(range(1, 19))
    if [case.get("citation", {}).get("line_number") for case in cases] != expected_lines:
        raise ValueError("interior source-line citations are incomplete or out of order")
    for case in cases:
        if case.get("rays_per_point") != 500:
            raise ValueError("interior ray count differs")
        if set(case.get("normalized_coordinates", {})) != set(FACTORS):
            raise ValueError("interior coordinates differ")
        if any(case["normalized_coordinates"][factor] not in (-0.5, 0.5) for factor in FACTORS):
            raise ValueError("interior coordinates must be half-step endpoints")
        if any(not math.isfinite(float(case["metrics"][metric])) for metric in METRICS):
            raise ValueError("interior metric is missing or nonfinite")
    for factor in FACTORS:
        for coordinate in (-0.5, 0.5):
            values = {
                case["recipe"][factor] for case in cases
                if case["normalized_coordinates"][factor] == coordinate
            }
            if len(values) != 1:
                raise ValueError(f"{factor} does not map to one value per coded level")
    return source, cases


def fit_effects(matrix: np.ndarray, values: np.ndarray) -> np.ndarray:
    design = np.column_stack((np.ones(len(matrix)), matrix))
    return np.linalg.lstsq(design, values, rcond=None)[0][1:]


def build() -> dict:
    source, cases = load_cases()
    matrix = np.asarray([
        [case["normalized_coordinates"][factor] for factor in FACTORS]
        for case in cases
    ], dtype=float)
    effects = {}
    for metric in METRICS:
        values = np.asarray([case["metrics"][metric] for case in cases], dtype=float)
        fitted = fit_effects(matrix, values)
        leave_one_out = [
            fit_effects(matrix[np.arange(len(cases)) != omitted], values[np.arange(len(cases)) != omitted])
            for omitted in range(len(cases))
        ]
        ranked = []
        for index, factor in enumerate(FACTORS):
            omitted_values = [float(row[index]) for row in leave_one_out]
            effect = float(fitted[index])
            ranked.append({
                "factor": factor,
                "adjusted_high_minus_low": effect,
                "leave_one_out_minimum": min(omitted_values),
                "leave_one_out_maximum": max(omitted_values),
                "leave_one_out_sign_stable": bool(
                    all(value > 0 for value in omitted_values)
                    if effect > 0
                    else all(value < 0 for value in omitted_values)
                ),
            })
        ranked.sort(key=lambda row: (-abs(row["adjusted_high_minus_low"]), row["factor"]))
        for rank, row in enumerate(ranked, 1):
            row["absolute_effect_rank"] = rank
        effects[metric] = {
            "observed_minimum": float(values.min()),
            "observed_maximum": float(values.max()),
            "ranked_factors": ranked,
        }

    cited_rows = ROOT / cases[0]["citation"]["path"]
    if any(
        case["citation"]["path"] != cases[0]["citation"]["path"]
        or case["citation"]["sha256"] != cases[0]["citation"]["sha256"]
        for case in cases
    ):
        raise ValueError("interior cases do not share one cited source")
    if digest(cited_rows) != cases[0]["citation"]["sha256"]:
        raise ValueError("cited interior source hash differs")

    return {
        "schema_version": 1,
        "campaign": "v3-bosch-interior-descriptive-review",
        "status": "complete_descriptive_review",
        "completeness": {
            "expected_cases": 18,
            "observed_cases": len(cases),
            "unique_case_ids": len({case["case_id"] for case in cases}),
            "all_metrics_finite": True,
            "rays_per_point": 500,
            "level_counts": {
                factor: {
                    "low": int(np.sum(matrix[:, index] == -0.5)),
                    "high": int(np.sum(matrix[:, index] == 0.5)),
                }
                for index, factor in enumerate(FACTORS)
            },
        },
        "provenance": {
            "analysis_input": {
                "path": str(SOURCE.relative_to(ROOT)),
                "sha256": digest(SOURCE),
                "selector": "/interior_cases",
            },
            "simulation_rows": {
                "path": str(cited_rows.relative_to(ROOT)),
                "sha256": digest(cited_rows),
                "line_numbers": list(range(1, 19)),
            },
            "case_citations": [
                {"case_id": case["case_id"], "source_line": case["citation"]["line_number"]}
                for case in cases
            ],
            "measurement_method": cases[0]["metrics"]["measurement_method"],
        },
        "design": {
            "method": source["interior_study"]["method"],
            "coded_low": -0.5,
            "coded_high": 0.5,
            "factor_order": list(FACTORS),
            "control_levels": {
                factor: {
                    "low": min(
                        case["recipe"][factor] for case in cases
                        if case["normalized_coordinates"][factor] == -0.5
                    ),
                    "high": max(
                        case["recipe"][factor] for case in cases
                        if case["normalized_coordinates"][factor] == 0.5
                    ),
                }
                for factor in FACTORS
            },
            "estimator": (
                "ordinary least squares with intercept and six coded main effects; "
                "adjusted_high_minus_low is the fitted +0.5 minus -0.5 contrast"
            ),
        },
        "effects": effects,
        "limitations": {
            "repeats_per_combination": 1,
            "within_combination_noise_estimated": False,
            "statistical_significance_estimated": False,
            "interpretation": (
                "Effects and leave-one-out sign stability are descriptive for these "
                "18 saved combinations. With no repeated combinations, residual variation "
                "cannot separate stochastic noise from curvature or interactions."
            ),
            "prohibited_claims": [
                "statistically significant effect",
                "confirmed causal main effect",
                "qualified recipe or process window",
            ],
        },
    }


def main() -> None:
    review = build()
    OUTPUT.write_text(json.dumps(review, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({
        "status": review["status"],
        "cases": review["completeness"]["observed_cases"],
        "metrics": len(review["effects"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

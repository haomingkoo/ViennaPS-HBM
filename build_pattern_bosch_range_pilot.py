"""Build the coarse 12-control Bosch range-pilot design."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from process_config import PROCESS_CONFIG


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "pattern_bosch_range_pilot_design.json"
CONFIG_PATH = ROOT / "config/process.toml"

FACTOR_ORDER = (
    "radius",
    "mask_taper",
    "num_cycles",
    "etch_time",
    "initial_etch_time",
    "neutral_rate",
    "neutral_sticking_probability",
    "deposition_thickness",
    "deposition_sticking_probability",
    "ion_source_exponent",
    "theta_r_min",
    "ion_rate",
)

REGISTRY_IDS = {
    "radius": "pattern_radius_input",
    "mask_taper": "phase_factor_mask_taper",
    "num_cycles": "phase_factor_num_cycles",
    "etch_time": "phase_factor_etch_time",
    "initial_etch_time": "phase_factor_initial_etch_time",
    "neutral_rate": "phase_factor_neutral_rate",
    "neutral_sticking_probability": "phase_factor_neutral_sticking_probability",
    "deposition_thickness": "phase_factor_deposition_thickness",
    "deposition_sticking_probability": "phase_factor_deposition_sticking_probability",
    "ion_source_exponent": "phase_factor_ion_source_exponent",
    "theta_r_min": "phase_factor_theta_r_min",
    "ion_rate": "bosch_ion_rate",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _conference_matrix() -> np.ndarray:
    """Return the order-12 Paley conference matrix."""
    q = 11
    residues = {pow(value, 2, q) for value in range(1, q)}
    matrix = np.zeros((q + 1, q + 1), dtype=int)
    matrix[0, 1:] = 1
    matrix[1:, 0] = -1
    for left in range(q):
        for right in range(q):
            if left != right:
                matrix[left + 1, right + 1] = (
                    1 if (right - left) % q in residues else -1
                )
    if not np.array_equal(matrix @ matrix.T, q * np.eye(q + 1, dtype=int)):
        raise ValueError("conference matrix construction failed")
    return matrix


def coded_design() -> np.ndarray:
    conference = _conference_matrix()
    return np.vstack((conference, -conference, np.zeros((1, 12), dtype=int)))


def _diagnostics(matrix: np.ndarray) -> dict:
    linear = matrix.astype(float)
    quadratic = linear**2
    interactions = np.column_stack(
        [linear[:, i] * linear[:, j] for i in range(12) for j in range(i + 1, 12)]
    )
    linear_correlation = np.corrcoef(linear, rowvar=False)
    off_diagonal = linear_correlation - np.eye(12)
    return {
        "run_count": int(len(matrix)),
        "linear_model_rank": int(
            np.linalg.matrix_rank(np.column_stack((np.ones(len(matrix)), linear)))
        ),
        "maximum_absolute_linear_correlation": float(np.max(np.abs(off_diagonal))),
        "maximum_absolute_main_to_quadratic_cross_product": float(
            np.max(np.abs(linear.T @ quadratic))
        ),
        "maximum_absolute_main_to_interaction_cross_product": float(
            np.max(np.abs(linear.T @ interactions))
        ),
    }


def build() -> dict:
    config = PROCESS_CONFIG["pattern_bosch_range_pilot"]
    levels = config["levels"]
    matrix = coded_design()
    factors = []
    for name in FACTOR_ORDER:
        values = levels[name]
        if len(values) != 3 or not values[0] < values[1] < values[2]:
            raise ValueError(f"{name} needs ordered low/reference/high levels")
        factors.append(
            {
                "name": name,
                "registry_id": REGISTRY_IDS[name],
                "levels": values,
                "range_status": "candidate_model_space_bracket",
                "range_source": "docs/range-research.md#candidate-bracket-for-the-first-bosch-range-study",
            }
        )

    cases = []
    for row_index, coded_row in enumerate(matrix):
        recipe = {
            name: levels[name][int(code) + 1]
            for name, code in zip(FACTOR_ORDER, coded_row, strict=True)
        }
        recipe["num_cycles"] = int(recipe["num_cycles"])
        cycles = recipe["num_cycles"]
        derived_exposures = {
            "total_cycle_etch_duration": cycles * recipe["etch_time"],
            "total_etch_duration_including_open": (
                recipe["initial_etch_time"] + cycles * recipe["etch_time"]
            ),
            "total_polymer_deposition_amount": (
                cycles * recipe["deposition_thickness"]
            ),
            "total_polymer_directional_removal_amount": (
                -cycles * recipe["deposition_thickness"]
            ),
        }
        payload = {
            "campaign": "pattern-bosch-range-pilot-v1",
            "design_row": row_index,
            "coded_levels": coded_row.tolist(),
            "recipe": recipe,
            "derived_exposures": derived_exposures,
            "rng_seed": int(config["rng_seed"]),
            "numerics": {
                "grid_delta": config["grid_delta"],
                "rays_per_point": config["rays_per_point"],
            },
        }
        cases.append(
            {
                **payload,
                "case_id": hashlib.sha256(_canonical(payload).encode()).hexdigest()[:16],
            }
        )

    return {
        "schema_version": 1,
        "campaign": "pattern-bosch-range-pilot-v1",
        "authority": config["authority"],
        "status": "frozen_design",
        "purpose": (
            "Record raw response spans, invalid regions, runtime, and contrasting "
            "states that may justify confirmation before a repeated screening study."
        ),
        "method": {
            "name": "25-case three-level range pilot (DSD matrix)",
            "construction": "order-12 Paley conference matrix, its negative, and one center row",
            "interpretation": "range pilot only; no interaction or process-window claim",
        },
        "inference_policy": {
            "allowed": [
                "execution and completion state",
                "raw measured values",
                "observed minimum, maximum, and span at the named coarse setting",
                "runtime and invalidity classes",
                "rows nominated for confirmation",
            ],
            "prohibited": [
                "factor effect or ranking",
                "uncertainty or curvature",
                "interaction",
                "failure-boundary location",
                "process qualification, optimum, or process window",
            ],
        },
        "sources": [
            {"path": "config/process.toml", "sha256": _sha256(CONFIG_PATH)},
            {
                "path": "build_pattern_bosch_range_pilot.py",
                "sha256": _sha256(ROOT / "build_pattern_bosch_range_pilot.py"),
            },
            {
                "path": "run_pattern_bosch_range_pilot.py",
                "sha256": _sha256(ROOT / "run_pattern_bosch_range_pilot.py"),
            },
            {
                "path": "scripts/autoresearch_event_log.py",
                "sha256": _sha256(ROOT / "scripts/autoresearch_event_log.py"),
            },
            {
                "path": "schemas/autoresearch-event.schema.json",
                "sha256": _sha256(ROOT / "schemas/autoresearch-event.schema.json"),
            },
            {
                "path": "pattern_bosch_factor_projection.json",
                "sha256": _sha256(ROOT / "pattern_bosch_factor_projection.json"),
            },
            {
                "path": "pattern_bosch_measurement_contract.json",
                "sha256": _sha256(ROOT / "pattern_bosch_measurement_contract.json"),
            },
            {
                "path": "docs/range-research.md",
                "sha256": _sha256(ROOT / "docs/range-research.md"),
            },
        ],
        "endpoint": {
            "mode": "final_completed_cycle",
            "depth_matched_selection": False,
            "reason": "cycle count is an input and etch depth is a measured response",
        },
        "numerics": {
            "grid_delta": config["grid_delta"],
            "rays_per_point": config["rays_per_point"],
            "threads_per_worker": config["threads_per_worker"],
            "simulation_dimension": 2,
            "status": "coarse_pilot_not_numerically_qualified",
        },
        "execution": {
            "case_cap": 25,
            "executor": "sequential_resumable",
            "maximum_workers": 1,
            "retry_policy": "one identical retry for explicit transient infrastructure errors only",
            "checkpoint_policy": "save final completed cycle and last valid state",
            "early_stop_policy": "no scientific early stop; retain numerical or domain invalidity",
        },
        "rng_policy": {
            "shared_base_seed_label_across_rows": True,
            "pointwise_common_random_numbers_not_claimed": True,
            "independent_repeats_present": False,
        },
        "comparison_context": {
            "evidence_class": "assumed_study_band",
            "opening_cd": PROCESS_CONFIG["targets"]["pattern"]["width"],
            "mask_height": PROCESS_CONFIG["targets"]["pattern"]["mask_height"],
            "etch_depth": PROCESS_CONFIG["targets"]["etch"]["target_depth"],
            "depth_tolerance": PROCESS_CONFIG["targets"]["etch"]["depth_tolerance"],
            "max_width_error": PROCESS_CONFIG["targets"]["etch"]["max_width_error"],
            "max_wall_bulge": PROCESS_CONFIG["targets"]["etch"]["max_wall_bulge"],
            "interpretation": "visible comparison only; no process acceptance decision",
        },
        "geometry": {
            "hole_shape": "FULL",
            "mask_height": PROCESS_CONFIG["defaults"]["geometry"]["mask_height"],
            "x_extent": config["x_extent"],
            "y_extent": config["y_extent"],
        },
        "held_controls": {
            "mask_ion_rate": 0.0,
            "polymer_deposition_duration": 1.0,
            "polymer_removal_duration": 1.0,
            "polymer_removal_rate": "negative of deposition_thickness",
            "polymer_removal_sticking": 1.0,
        },
        "required_measurements": [
            "mask_opening_cd_bottom",
            "mask_opening_cd_middle",
            "mask_opening_cd_top",
            "mask_height",
            "mask_sidewall_angle",
            "etch_depth",
            "etch_cd_top",
            "etch_cd_middle",
            "etch_cd_bottom",
            "etch_minimum_cd",
            "etch_maximum_cd_error",
            "etch_sidewall_angle",
            "etch_bow",
            "etch_scallop_rms",
        ],
        "invalidity_rule": "retain the row, error, elapsed time, and completed checkpoint status",
        "factors": factors,
        "diagnostics": _diagnostics(matrix),
        "cases": cases,
        "output": config["output"],
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"{OUTPUT.name}: {len(document['cases'])} cases")


if __name__ == "__main__":
    main()

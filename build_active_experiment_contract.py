"""Build the small contract used by the public teaching studies."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from process_config import PROCESS_CONFIG


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "active_experiment_contract.json"


def digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def teaching_factor(
    factor_id: str,
    registry_id: str,
    step: str,
    label: str,
    config_key: str,
    model_input: str,
    code_symbol: str,
    units: str,
    measurements: list[str],
    equipment_influences: list[str],
) -> dict:
    key = config_key.rsplit(".", 1)[1]
    values = PROCESS_CONFIG["teaching_experiments"][key]
    return {
        "id": factor_id,
        "registry_id": registry_id,
        "step": step,
        "label": label,
        "role": "saved_sensitivity_example",
        "config_key": config_key,
        "code": {"path": "build_step_experiments.py", "symbol": code_symbol},
        "model_input": model_input,
        "explored_values": values,
        "units": units,
        "range_evidence_class": "exploratory_internal_history",
        "equipment_influences": equipment_influences,
        "equipment_to_model_mapping": None,
        "measurements": measurements,
        "doe_status": "range_finding_required",
        "constraints": None,
        "runtime_cost": None,
        "restart_from": {
            "mask": "ideal mask constructor",
            "bosch_etch": "fresh configured mask",
            "liner": "focused saved etch profile resampled on the teaching grid",
            "barrier": "resampled focused etch profile with fixed liner",
            "seed": "resampled focused etch profile with fixed liner and barrier",
            "cmp": "analytic raised-plug stack",
        }[step],
    }


def build() -> dict:
    factors = [
        teaching_factor(
            "mask_radius",
            "pattern_radius_input",
            "mask",
            "Opening radius",
            "teaching_experiments.mask_radii",
            "make_initial_geometry.radius",
            "_mask_study",
            "model length",
            ["opening_cd_bottom", "opening_cd_top", "mask_height"],
            ["focus", "exposure dose", "develop"],
        ),
        teaching_factor(
            "mask_taper",
            "phase_factor_mask_taper",
            "mask",
            "Mask taper",
            "teaching_experiments.mask_tapers",
            "make_initial_geometry.taper",
            "_mask_study",
            "degrees",
            ["opening_cd_bottom", "opening_cd_top", "mask_height"],
            ["focus", "exposure dose", "develop"],
        ),
        teaching_factor(
            "bosch_cycles",
            "phase_factor_num_cycles",
            "bosch_etch",
            "Completed etch cycles",
            "teaching_experiments.bosch_cycles",
            "bosch_etch.num_cycles checkpoint",
            "_bosch_study",
            "cycles",
            ["depth", "maximum_cd_error", "bow"],
            ["etch/passivation step timing"],
        ),
        teaching_factor(
            "bosch_passivation",
            "phase_factor_deposition_thickness",
            "bosch_etch",
            "Passivation per cycle",
            "teaching_experiments.bosch_passivation_thickness",
            "bosch_etch.deposition_thickness",
            "_bosch_study",
            "model length per cycle",
            ["depth", "maximum_cd_error", "bow"],
            ["passivation gas time", "passivation precursor flux"],
        ),
        teaching_factor(
            "liner_sticking",
            "phase_factor_liner_sticking",
            "liner",
            "Liner sticking",
            "teaching_experiments.liner_sticking",
            "deposit_conformal.sticking",
            "_liner_study",
            "probability",
            [
                "minimum_thickness",
                "lower_wall_coverage",
                "floor_coverage",
                "remaining_aperture",
                "continuous",
                "aperture_open",
            ],
            ["precursor chemistry", "temperature", "surface state"],
        ),
        teaching_factor(
            "liner_dose",
            "phase_factor_liner_thick",
            "liner",
            "Liner deposition amount",
            "teaching_experiments.liner_doses",
            "deposit_conformal.thickness",
            "_liner_study",
            "model length",
            [
                "minimum_thickness",
                "lower_wall_coverage",
                "floor_coverage",
                "remaining_aperture",
                "continuous",
                "aperture_open",
            ],
            ["precursor exposure", "deposition time"],
        ),
        teaching_factor(
            "barrier_direction",
            "candidate_barrier_seed_isotropic_fraction",
            "barrier",
            "Barrier all-angle fraction",
            "teaching_experiments.barrier_isotropic_fraction",
            "deposit_directional_fraction.isotropic_fraction",
            "_barrier_study",
            "fraction",
            [
                "minimum_thickness",
                "lower_wall_coverage",
                "remaining_aperture",
                "continuous",
                "aperture_open",
            ],
            ["pressure", "target power", "collimation", "substrate bias"],
        ),
        teaching_factor(
            "barrier_dose",
            "candidate_barrier_seed_field_dose",
            "barrier",
            "Barrier deposition amount",
            "teaching_experiments.barrier_doses",
            "deposit_directional_fraction.field_dose",
            "_barrier_study",
            "model length",
            [
                "minimum_thickness",
                "lower_wall_coverage",
                "remaining_aperture",
                "continuous",
            ],
            ["deposition time", "target power"],
        ),
        teaching_factor(
            "seed_direction",
            "candidate_barrier_seed_isotropic_fraction",
            "seed",
            "Seed all-angle fraction",
            "teaching_experiments.seed_isotropic_fraction",
            "deposit_directional_fraction.isotropic_fraction",
            "_seed_study",
            "fraction",
            [
                "minimum_thickness",
                "lower_wall_coverage",
                "remaining_aperture",
                "continuous",
            ],
            ["pressure", "target power", "collimation", "substrate bias"],
        ),
        teaching_factor(
            "seed_dose",
            "candidate_barrier_seed_field_dose",
            "seed",
            "Seed deposition amount",
            "teaching_experiments.seed_doses",
            "deposit_directional_fraction.field_dose",
            "_seed_study",
            "model length",
            [
                "minimum_thickness",
                "lower_wall_coverage",
                "remaining_aperture",
                "continuous",
            ],
            ["deposition time", "target power"],
        ),
        teaching_factor(
            "cmp_removal",
            "candidate_cmp_overpolish_dose",
            "cmp",
            "Removal amount",
            "teaching_experiments.cmp_removal_durations",
            "apply_native_control.duration",
            "_cmp_study",
            "model time",
            [
                "field_relative_to_target",
                "plug_relative_to_target",
                "stop_retained_thickness",
            ],
            ["polish time", "endpoint", "overpolish"],
        ),
        teaching_factor(
            "cmp_oxide_rate",
            "candidate_cmp_sio2_rate",
            "cmp",
            "Oxide/Cu removal-rate ratio",
            "teaching_experiments.cmp_oxide_rate_ratios",
            "HeightMaterialRemovalLaw.material_rate_ratios[SiO2]",
            "_cmp_study",
            "ratio",
            [
                "field_relative_to_target",
                "plug_relative_to_target",
                "stop_retained_thickness",
            ],
            ["slurry chemistry", "pad", "pressure", "speed"],
        ),
    ]
    targets = PROCESS_CONFIG["targets"]
    teaching = PROCESS_CONFIG["teaching_experiments"]

    def criterion(
        criterion_id: str,
        metric: str,
        operator: str,
        value: object,
        config_key: str,
        tolerance: float | None = None,
    ) -> dict:
        return {
            "id": criterion_id,
            "metric": metric,
            "operator": operator,
            "value": value,
            "tolerance": tolerance,
            "config_key": config_key,
            "evidence_class": "assumed_comparison_band",
            "detection_limit": None,
            "calibrated_pass": None,
            "permitted_claim": "study comparison only",
        }

    criteria = [
        criterion(
            "pattern_opening_width",
            "opening_cd_bottom",
            "equal_within",
            targets["pattern"]["width"],
            "targets.pattern.width",
            teaching["measurement_tolerance"],
        ),
        criterion(
            "pattern_mask_height",
            "mask_height",
            "equal_within",
            targets["pattern"]["mask_height"],
            "targets.pattern.mask_height",
            teaching["mask_height_tolerance"],
        ),
        criterion(
            "etch_depth",
            "depth",
            "equal_within",
            targets["etch"]["target_depth"],
            "targets.etch.target_depth",
            targets["etch"]["depth_tolerance"],
        ),
        criterion(
            "etch_width_error",
            "maximum_cd_error",
            "maximum",
            targets["etch"]["max_width_error"],
            "targets.etch.max_width_error",
        ),
        criterion(
            "etch_wall_bulge",
            "bow",
            "maximum",
            targets["etch"]["max_wall_bulge"],
            "targets.etch.max_wall_bulge",
        ),
        criterion(
            "liner_thickness",
            "minimum_thickness",
            "minimum",
            targets["liner"]["min_thickness"],
            "targets.liner.min_thickness",
        ),
        criterion(
            "liner_coverage",
            "lower_wall_coverage",
            "minimum",
            targets["liner"]["min_floor_coverage"],
            "targets.liner.min_floor_coverage",
        ),
        criterion(
            "barrier_thickness",
            "minimum_thickness",
            "minimum",
            targets["barrier"]["min_thickness"],
            "targets.barrier.min_thickness",
        ),
        criterion(
            "barrier_coverage",
            "lower_wall_coverage",
            "minimum",
            targets["barrier"]["min_floor_coverage"],
            "targets.barrier.min_floor_coverage",
        ),
    ]
    return {
        "schema_version": 1,
        "scope": "Active public teaching studies; not the complete ViennaPS API inventory or a fab DOE.",
        "sources": [
            {"path": path, "sha256": digest(path)}
            for path in (
                "build_active_experiment_contract.py",
                "config/process.toml",
                "build_step_experiments.py",
                "factor_registry.json",
                "process_config.py",
            )
        ],
        "factors": factors,
        "acceptance_criteria": criteria,
        "known_gaps": [
            "The public copper transport map still reads factor levels from saved publication data rather than config/process.toml.",
            "The active copper replay and CMP teaching panel have no declared acceptance criteria.",
            "These explored values are saved sensitivity examples; ranges must be requalified before screening DOE.",
            "No equipment-to-model coefficient mapping is calibrated.",
        ],
    }


def main() -> None:
    document = build()
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    OUTPUT.write_text(text)
    print(
        f"active experiment contract: {len(document['factors'])} factors, {len(document['acceptance_criteria'])} assumed criteria"
    )


if __name__ == "__main__":
    main()

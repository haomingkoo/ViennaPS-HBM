"""Build the deterministic 27-point V3 pattern-geometry screen."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import foundation_metric_audit as foundation
import foundation_pattern_bosch_gate0 as gate0


DEFAULT_SPEC = Path(
    ".scratch/full-traveler-autoresearch/v3_pattern_skew_stage1_spec.json"
)
LEVEL_NAMES = ("low", "nominal", "high")
FACTOR_NAMES = ("opening_cd", "mask_height", "mask_taper")


def strict_load(path):
    return gate0.strict_json_loads(Path(path).read_text())


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _expected_horizon(spec):
    return 1 + 3 * int(spec["trajectory"]["maximum_cycles"])


def validate_spec(spec):
    errors = []
    if spec.get("schema_version") != 1:
        errors.append("schema version differs")
    if spec.get("methodology_epoch") != "full-traveler-doe-v3":
        errors.append("methodology epoch differs")
    if spec.get("campaign") != "v3-pattern-skew-stage1":
        errors.append("campaign differs")
    if spec.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("required labels differ")
    factors = spec.get("factors", [])
    if tuple(factor.get("name") for factor in factors) != FACTOR_NAMES:
        errors.append("exact three-factor registry differs")
    for factor in factors:
        name = factor.get("name")
        levels = [factor.get(level) for level in LEVEL_NAMES]
        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in levels
        ) or not levels[0] < levels[1] < levels[2]:
            errors.append(f"{name}: levels must be finite and ordered")
        for required in ("owning_api", "classification", "units", "range_basis"):
            if not isinstance(factor.get(required), str) or not factor[required].strip():
                errors.append(f"{name}: {required} is missing")
    expected_recipe = {
        "source_path": (
            ".scratch/full-traveler-autoresearch/"
            "foundation_bosch_high_fidelity_manifest.json"
        ),
        "etch_time": 0.5,
        "initial_etch_time": 0.3,
        "neutral_rate": -0.08,
        "neutral_sticking_probability": 0.08,
        "deposition_thickness": 0.005,
        "deposition_sticking_probability": 0.01,
        "ion_source_exponent": 400,
        "theta_r_min": 45.0,
        "ion_rate": -0.1,
        "mask_ion_rate": 0.0,
    }
    if spec.get("fixed_bosch_recipe") != expected_recipe:
        errors.append("fixed Bosch reference differs")
    if spec.get("geometry") != {
        "hole_shape": "FULL",
        "x_extent": 1.0,
        "y_extent": 2.0,
    }:
        errors.append("full-width geometry contract differs")
    if spec.get("numerics") != {
        "grid_delta": 0.00125,
        "rays_per_point": 2000,
        "threads_per_worker": 7,
        "maximum_workers": 2,
        "dimension": 2,
    }:
        errors.append("qualified numerical contract differs")
    if spec.get("trajectory") != {
        "maximum_cycles": 14,
        "first_scored_cycle": 1,
        "early_stop_depth": 1.45,
        "selection": (
            "minimum absolute depth error among valid checkpoints; an "
            "in-window checkpoint outranks every miss"
        ),
        "record_all_scored_cycles": True,
    }:
        errors.append("depth-matched trajectory contract differs")
    if spec.get("target") != gate0.EXPECTED_TARGET:
        errors.append("product target differs")
    if spec.get("pattern_gate_policy") != {
        "opening_cd_measurement": "raw mask intersection at surface y=0",
        "opening_cd_target": 0.3,
        "opening_cd_numerical_allowance_grid_cells": 1.0,
        "bottom_middle_top_cd_role": (
            "profile diagnostics sampled above the surface; not the "
            "surface-opening gate"
        ),
        "interpretation": (
            "the product target remains exactly 0.30; one grid cell is a "
            "numerical construction allowance, not a product tolerance"
        ),
    }:
        errors.append("surface-opening pattern gate policy differs")
    horizon = _expected_horizon(spec)
    expected_rng = {
        "block_id": "v3_pattern_shared_81000_81042",
        "base_seed": 81000,
        "process_seed_horizon": horizon,
        "first_process_seed": 81000,
        "last_process_seed": 81000 + horizon - 1,
        "assignment": (
            "reuse this exact stochastic block across all 27 pattern "
            "geometries while holding the Bosch recipe fixed"
        ),
        "interpretation": (
            "controlled nuisance block for screening; the geometries share "
            "seed labels but pointwise common random draws are not claimed"
        ),
        "independence_limit": (
            "this stage cannot estimate stochastic variance or confirm an "
            "effect; promoted effects require disjoint-block confirmation"
        ),
    }
    if spec.get("rng_policy") != expected_rng:
        errors.append("shared RNG block contract differs")
    authority = spec.get("authority", {})
    if authority.get("pattern_geometry_screening_only") is not True or any(
        authority.get(name) is not False
        for name in (
            "confirmed_factor_authorized",
            "recipe_authorized",
            "process_window_authorized",
            "downstream_recipe_authorized",
            "traveler_relevance_authorized",
            "full_traveler_authorized",
            "automatic_launch_authorized",
        )
    ):
        errors.append("screening-only authority differs")
    practical_changes = spec.get("practical_screen_changes", {})
    if not practical_changes or any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or value <= 0
        for value in practical_changes.values()
    ):
        errors.append("practical screen changes must be positive finite values")
    if spec.get("threshold_policy") != {
        "formula": (
            "max(practical engineering change, released numerical-fidelity "
            "shift when available, three times paired stochastic SD when "
            "available, two grid cells for dimensional geometry outputs)"
        ),
        "geometry_resolution_cells": 2.0,
        "paired_stochastic_sd_status": (
            "unavailable in this single-block stage; no zero-noise "
            "substitution is allowed"
        ),
        "numerical_fidelity_source": (
            "source_artifacts.numerical_release.ray_bridge.metric_results"
        ),
        "authority": "effective thresholds screen confirmation hypotheses only",
    }:
        errors.append("effective-threshold policy differs")
    prohibited = " ".join(spec.get("unsupported_claims", [])).lower()
    if "dose" not in prohibited or "focus" not in prohibited:
        errors.append("dose and focus claims are not explicitly prohibited")
    if errors:
        raise ValueError("invalid V3 pattern-skew spec: " + "; ".join(errors))


def build_design(spec):
    validate_spec(spec)
    factors = spec["factors"]
    points = []
    for index, names in enumerate(itertools.product(LEVEL_NAMES, repeat=3), start=1):
        levels = dict(zip(FACTOR_NAMES, names))
        values = {
            factor["name"]: factor[levels[factor["name"]]]
            for factor in factors
        }
        points.append({
            "pattern_id": f"pattern_{index:02d}",
            "levels": levels,
            "values": values,
        })
    if len(points) != 27 or len({canonical_json(row["values"]) for row in points}) != 27:
        raise ValueError("pattern design is not 27 unique combinations")
    return {
        "design_type": "complete_three_level_factorial",
        "factor_count": 3,
        "logical_case_count": 27,
        "factors": factors,
        "points": points,
        "fixed_bosch_recipe": spec["fixed_bosch_recipe"],
        "geometry": spec["geometry"],
        "numerics": spec["numerics"],
        "trajectory": spec["trajectory"],
        "rng_policy": spec["rng_policy"],
        "target": spec["target"],
        "pattern_gate_policy": spec["pattern_gate_policy"],
        "practical_screen_changes": spec["practical_screen_changes"],
        "threshold_policy": spec["threshold_policy"],
        "decision_rules": spec["decision_rules"],
        "unsupported_claims": spec["unsupported_claims"],
        "authority": spec["authority"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    args = parser.parse_args()
    spec = strict_load(args.spec)
    design = build_design(spec)
    print(json.dumps({
        "campaign": spec["campaign"],
        "cases": design["logical_case_count"],
        "design_sha256": foundation.file_sha256(args.spec),
        "screening_only": design["authority"]["pattern_geometry_screening_only"],
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

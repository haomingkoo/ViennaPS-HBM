"""Build a compact public checkpoint from reviewed foundation evidence.

The research summaries stay verbose and retain every diagnostic.  This file
selects only the fields used by the public explainer and records the source
hashes so a published claim can be traced back to the reviewed artifact.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parent
AUDIT = ROOT / "autoresearch-results" / "restart_audit"
OUTPUT = ROOT / "publication_interim_data.json"
SOURCES = {
    "bosch_resolution": AUDIT / "bosch_resolution_summary.json",
    "bosch_cycle_history": AUDIT / "bosch_cycle_history_summary.json",
    "layers": AUDIT / "layer_qualification_v2_summary.json",
    "cu_structural": AUDIT / "copper_fill_structural_challenge_summary.json",
    "cu_transport": AUDIT / "copper_fill_transport_sign_summary.json",
    "cu_effects": AUDIT / "copper_fill_transport_effects_summary.json",
    "cu_confirmation": AUDIT / "copper_fill_transport_confirmation_summary.json",
    "cu_boundary": AUDIT / "copper_fill_transport_boundary_confirmation_summary.json",
    "pattern_bosch_gate0": AUDIT / "pattern_bosch_gate0_summary.json",
    "pattern_bosch_handoff": AUDIT / "pattern_bosch_handoff_summary.json",
    "pattern_bosch_gate0_manifest": ROOT / ".scratch" /
        "full-traveler-autoresearch" /
        "foundation_pattern_bosch_gate0_manifest.json",
    "pattern_bosch_gate0_r1_manifest": ROOT / ".scratch" /
        "full-traveler-autoresearch" /
        "foundation_pattern_bosch_gate0_r1_manifest.json",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


source = {name: load(path) for name, path in SOURCES.items()}

assert source["bosch_resolution"]["status"] == "complete"
assert source["bosch_resolution"]["ok_count"] == 20
assert source["bosch_cycle_history"]["ok_count"] == 4
assert source["bosch_cycle_history"]["common_passing_cycles"] == [13]
cycle_13 = next(row for row in source["bosch_cycle_history"]["cycles"] if row["cycle"] == 13)
assert cycle_13["common_pass"] and cycle_13["all_gate_passes"] == 4

layers = source["layers"]
assert layers["status"] == "complete"
assert layers["qualification_status"] == "established"
assert layers["valid_metric_count"] == 12
assert layers["production_doe_authorization_scope"] == "exploratory_layer_factor_screening_only"
fine_layers = layers["groups"]["grid_fine_r2000"]
assert fine_layers["liner_passes"] == 0
assert fine_layers["barrier_seed_passes"] == 0

structural = source["cu_structural"]
assert structural["status"] == "complete"
assert structural["valid_attempt_count"] == 4
candidate_cases = [row for row in structural["cases"] if row["arm"] == "candidate_rank1_quasi_steady"]
control_cases = [row for row in structural["cases"] if row["arm"] == "morphology_only_bottom_up_positive_control"]
assert len(candidate_cases) == len(control_cases) == 2
assert not any(row["target_pass"] for row in candidate_cases)
assert all(row["target_pass"] for row in control_cases)

transport = source["cu_transport"]
assert transport["status"] == "complete"
assert transport["selected_current_case_count"] == 168
assert transport["metric_valid_case_count"] == 168
assert transport["expected_case_count"] == 168
assert transport["transport_pass_design_count"] == 0
assert len(transport["cross_tier_designs"]) == 21
assert len(transport["tier_designs"]) == 42
assert not transport["manifest_validation_errors"]

effects = source["cu_effects"]
assert effects["status"] == "complete"
assert effects["case_count"] == 168
assert not effects["validation_errors"]

confirmation = source["cu_confirmation"]
assert confirmation["status"] == "complete"
assert confirmation["selected_current_case_count"] == 128
assert confirmation["metric_valid_case_count"] == 128
assert confirmation["verified_parent_reuse_count"] == 8
assert confirmation["reviewed_new_execution_count"] == 120
assert confirmation["decision"]["classification"] == "lower_sticking_boundary_expansion_required"
assert not confirmation["decision"]["automatic_launch_authorized"]
assert not confirmation["decision"]["morphology_authorized"]
assert not confirmation["decision"]["model_family_pivot_authorized"]

boundary = source["cu_boundary"]
assert boundary["status"] == "complete"
assert boundary["selected_current_case_count"] == 24
assert boundary["metric_valid_case_count"] == 24
assert boundary["reviewed_new_execution_count"] == 24
assert boundary["verified_parent_comparison_count"] == 8
assert boundary["reflection_convergence"]["converged"]
assert boundary["reflection_convergence"]["eligible"]
assert not boundary["boundary_trend"]["continued_boundary_improvement"]
assert boundary["boundary_trend"]["improves_every_stream_in_both_tiers"]
assert boundary["multiresponse_paired_directions"]["eligible"]
assert boundary["reflection_arms"]["3200"]["realized_kinematic_ratio_by_tier"][
    "continuity"
]["stream_pass_count"] == 0
assert boundary["reflection_arms"]["3200"]["realized_kinematic_ratio_by_tier"][
    "nominal_hbm"
]["stream_pass_count"] == 0
assert boundary["reflection_arms"]["3200"]["broad_analytic_envelope"][
    "evaluation_status"
] == "not_evaluated_preliminary_flux_gate_failed"
assert boundary["decision"]["classification"] == (
    "two_dimensional_transport_no_go_requires_matched_3d_before_pivot"
)
assert not boundary["decision"]["automatic_further_boundary_launch_authorized"]
assert not boundary["decision"]["morphology_authorized"]
assert not boundary["decision"]["model_family_pivot_authorized"]
assert boundary["decision"]["matched_3d_required"]

gate0 = source["pattern_bosch_gate0"]
gate0_manifest = source["pattern_bosch_gate0_manifest"]
assert gate0["status"] == "complete_gate0_blocked"
assert gate0["attempt_count"] == 24
assert gate0["expected_case_count"] == 24
assert gate0["independently_valid_case_count"] == 24
assert gate0["decision"]["classification"] == "gate0_blocked"
assert not gate0["decision"]["full_traveler_authorized"]
assert not gate0["decision"]["automatic_downstream_launch_authorized"]
assert not gate0["comparisons"]["full_vs_quarter"]["pass"]
assert not gate0["comparisons"]["grid_bridge"]["pass"]
assert gate0["erosion_response"]["all_seeds_monotonic"]
assert not gate0["erosion_response"]["all_seed_failed_arms"]
assert gate0_manifest["campaign"] == "foundation-pattern-bosch-gate0"

handoff = source["pattern_bosch_handoff"]
assert handoff["attempt_count"] == 4
assert handoff["reviewed_checkpoint_count"] == 3
assert handoff["decision"]["classification"] == (
    "full_reference_checkpoint_handoff_blocked"
)
assert not handoff["decision"]["reusable_upstream_geometry_authorized"]
assert not any(row["accepted"] for row in handoff["handoff_results"])

r1_manifest = source["pattern_bosch_gate0_r1_manifest"]
assert r1_manifest["campaign"] == "foundation-pattern-bosch-gate0-r1"
assert r1_manifest["labels"] == ["full-traveler", "critical-review"]
assert r1_manifest["numerics"]["screen_rays_per_point"] == 1000
assert r1_manifest["numerics"]["anchor_rays_per_point"] == 2000
assert r1_manifest["mask_bracket"]["maximum_executed_cases"] == 14
assert all(
    len(digest) == 64
    for digest in r1_manifest["runtime_fingerprint"].values()
)

full_reference_rows = [
    row for row in gate0["reviewed_cases"]
    if row["arm"] == "full_reference_fine"
]
assert len(full_reference_rows) == 4
full_reference_passes = [
    row for row in full_reference_rows
    if all(row["gates"].values())
]
full_reference_misses = [
    row for row in full_reference_rows
    if not all(row["gates"].values())
]
assert len(full_reference_passes) == 3
assert len(full_reference_misses) == 1
full_reference_miss = full_reference_misses[0]
depth_upper_limit = gate0_manifest["target"]["etch_depth"] + gate0_manifest["target"][
    "depth_tolerance"
]


def compact_bridge(comparison):
    return {
        "paired_cases": len(comparison["pairs"]),
        "gate_flip_pairs": sum(row["gate_flip"] for row in comparison["pairs"]),
        "failed_metrics": [{
            "name": name,
            "maximum_absolute_delta": result["maximum_absolute_delta"],
            "tolerance": result["tolerance"],
        } for name, result in comparison["metric_results"].items()
          if not result["pass"]],
    }


erosion_ranges = []
for arm in (
    "full_reference_fine",
    "full_erosion_m0p01",
    "full_erosion_m0p02",
    "full_erosion_m0p04",
):
    rows = [row for row in gate0["reviewed_cases"] if row["arm"] == arm]
    assert len(rows) == 4
    remaining_heights = [row["metrics"]["mask_remaining_height"] for row in rows]
    erosion_ranges.append({
        "mask_ion_rate": rows[0]["mask_ion_rate"],
        "minimum_remaining_height": min(remaining_heights),
        "maximum_remaining_height": max(remaining_heights),
        "all_four_seeds_survive": arm in gate0["erosion_response"][
            "all_seed_surviving_arms"
        ],
    })

compact_structural = []
for row in structural["cases"]:
    topology = row["terminal_topology"]
    compact_structural.append({
        "arm": row["arm"],
        "grid_delta": row["grid_delta"],
        "target_pass": row["target_pass"],
        "outcome": row["outcome"],
        "mechanism": row["mechanism_classification"],
        "protected_stack_survives": row["protected_stack_survives"],
        "void_free": topology["void_free"],
        "remaining_void_area": topology["remaining_void_area"],
        "minimum_overburden": topology["overburden_min"],
        "initial_floor_to_lower_wall_velocity_ratio": row["initial_region_rates"]["floor_to_lower_wall_velocity_ratio"],
        "required_floor_to_lower_wall_velocity_ratio": row["required_floor_to_lower_wall_velocity_ratio"],
    })

compact_surface = [{
    "tier": row["geometry_tier"],
    "sticking": row["sticking_probability"],
    "source_power": row["source_power"],
    "streams_passing": row["stream_pass_count"],
    "streams": row["stream_count"],
    "worst_flux_ratio": row["worst_floor_to_lower_flux_ratio"],
    "worst_velocity_ratio": row["worst_floor_to_lower_velocity_ratio"],
    "worst_coverage_margin": row["worst_lower_minus_floor_coverage"],
} for row in transport["tier_designs"]]

data = {
    "checkpoint": "foundation-audit-2026-07-13",
    "status": "interim",
    "selected_foundation_cases": 376,
    "reviewed_logical_cells": 384,
    "selected_case_accounting": {
        "bosch_resolution": 20,
        "bosch_full_depth": 4,
        "layer_qualification": 12,
        "cu_structural_challenge": 4,
        "cu_transport_screen": 168,
        "cu_transport_confirmation_new": 120,
        "cu_transport_boundary_new": 24,
        "pattern_bosch_gate0": 24,
    },
    "source_artifacts": [{
        "name": name,
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
    } for name, path in SOURCES.items()],
    "pattern_bosch_gate0": {
        "status": gate0["status"],
        "attempts": gate0["attempt_count"],
        "expected_cases": gate0["expected_case_count"],
        "independently_valid_cases": gate0["independently_valid_case_count"],
        "gate_pass_counts": gate0["gate_pass_counts"],
        "full_reference_pass": gate0["decision"]["full_reference_pass"],
        "full_reference": {
            "passes": len(full_reference_passes),
            "seeds": len(full_reference_rows),
            "miss_seed": full_reference_miss["rng_seed"],
            "miss_depth": full_reference_miss["metrics"]["depth"],
            "depth_upper_limit": depth_upper_limit,
            "depth_excess": (
                full_reference_miss["metrics"]["depth"] - depth_upper_limit
            ),
        },
        "full_vs_quarter": compact_bridge(
            gate0["comparisons"]["full_vs_quarter"]
        ),
        "grid_bridge": compact_bridge(gate0["comparisons"]["grid_bridge"]),
        "mask_erosion": {
            "all_seeds_monotonic": gate0["erosion_response"][
                "all_seeds_monotonic"
            ],
            "failure_bracket_established": bool(
                gate0["erosion_response"]["all_seed_failed_arms"]
            ),
            "ranges": erosion_ranges,
        },
        "handoff": {
            "source_checkpoints": handoff["attempt_count"],
            "reviewed": handoff["reviewed_checkpoint_count"],
            "excluded": (
                handoff["attempt_count"] - handoff["reviewed_checkpoint_count"]
            ),
            "accepted": sum(row["accepted"] for row in handoff["handoff_results"]),
            "classification": handoff["decision"]["classification"],
            "reusable_upstream_geometry_authorized": handoff["decision"][
                "reusable_upstream_geometry_authorized"
            ],
        },
        "full_traveler_authorized": gate0["decision"][
            "full_traveler_authorized"
        ],
        "automatic_downstream_launch_authorized": gate0["decision"][
            "automatic_downstream_launch_authorized"
        ],
        "next_action": (
            "Use the full-width fine grid, compare 1,000 versus 2,000 rays, "
            "extend mask erosion until survival and failure are both observed, "
            "and save each selected shape with the native ViennaPS format."
        ),
        "next_action_status": "frozen corrective R1 design",
        "corrective_r1": {
            "manifest_path": str(
                SOURCES["pattern_bosch_gate0_r1_manifest"].relative_to(ROOT)
            ),
            "manifest_sha256": sha256(
                SOURCES["pattern_bosch_gate0_r1_manifest"]
            ),
            "initial_cases": 9,
            "maximum_executed_cases": r1_manifest["mask_bracket"][
                "maximum_executed_cases"
            ],
            "screen_rays_per_point": r1_manifest["numerics"][
                "screen_rays_per_point"
            ],
            "anchor_rays_per_point": r1_manifest["numerics"][
                "anchor_rays_per_point"
            ],
        },
    },
    "bosch": {
        "qualified_grid_delta": 0.00125,
        "saved_shape_count": cycle_13["rows"],
        "passing_cycle": 13,
        "depth_mean": cycle_13["depth"]["mean"],
        "depth_min": cycle_13["depth"]["min"],
        "depth_max": cycle_13["depth"]["max"],
        "top_cd_mean": cycle_13["cd_top"]["mean"],
        "middle_cd_mean": cycle_13["cd_middle"]["mean"],
        "bottom_cd_mean": cycle_13["cd_bottom"]["mean"],
        "max_cd_error_mean": cycle_13["max_cd_error"]["mean"],
        "max_bow_mean": cycle_13["max_bow"]["mean"],
    },
    "layers": {
        "qualification_rows": layers["valid_metric_count"],
        "exploratory_screening_authorized": layers["production_doe_authorized"],
        "final_recipe_acceptance_authorized": layers["final_recipe_acceptance_authorized"],
        "baseline_liner_passes": fine_layers["liner_passes"],
        "baseline_barrier_seed_passes": fine_layers["barrier_seed_passes"],
        "replicates": fine_layers["rows"],
        "liner_min_mean": fine_layers["metrics"]["liner_min"]["mean"],
        "liner_floor_field_mean": fine_layers["metrics"]["liner_floor_field"]["mean"],
        "liner_lower_wall_field_mean": fine_layers["metrics"]["liner_lower_wall_field"]["mean"],
        "stack_min_mean": fine_layers["metrics"]["stack_min"]["mean"],
        "barrier_lower_wall_field_mean": fine_layers["metrics"]["barrier_lower_wall_field"]["mean"],
        "seed_lower_wall_field_mean": fine_layers["metrics"]["seed_lower_wall_field"]["mean"],
    },
    "cu_structural": {
        "cases": compact_structural,
        "candidate_passes": sum(row["target_pass"] for row in candidate_cases),
        "candidate_cases": len(candidate_cases),
        "prescribed_bottom_up_passes": sum(row["target_pass"] for row in control_cases),
        "prescribed_bottom_up_cases": len(control_cases),
        "conclusion": structural["structural_conclusion"]["classification"],
    },
    "cu_transport": {
        "raw_cases": transport["selected_current_case_count"],
        "valid_cases": transport["metric_valid_case_count"],
        "logical_designs": len(transport["cross_tier_designs"]),
        "tier_designs": compact_surface,
        "passing_cross_tier_designs": sum(row["all_eight_streams_pass"] for row in transport["cross_tier_designs"]),
        "flux_pass_threshold": 0.95,
        "velocity_pass_threshold": 1.05,
        "closest_tested_miss": effects["closest_tested_miss"],
        "factor_effects": effects["factor_effects"],
        "monotonicity": effects["monotonicity"],
        "paired_geometry_effect": effects["paired_geometry_effect"],
        "scope": effects["scope"],
        "coarse_decision": {
            "classification": transport["decision"]["classification"],
            "reason": transport["decision"]["reason"],
        },
    },
    "cu_confirmation": {
        "logical_cells": confirmation["selected_current_case_count"],
        "metric_valid_cells": confirmation["metric_valid_case_count"],
        "parent_reuses": confirmation["verified_parent_reuse_count"],
        "new_executions": confirmation["reviewed_new_execution_count"],
        "high_fidelity_results": confirmation["high_fidelity_results"],
        "class_changing_numerical_interactions": len(confirmation["class_changing_interactions"]),
        "numerical_artifacts": len(confirmation["numerical_artifacts"]),
        "decision": confirmation["decision"],
    },
    "cu_boundary": {
        "logical_cells": boundary["selected_current_case_count"],
        "metric_valid_cells": boundary["metric_valid_case_count"],
        "new_executions": boundary["reviewed_new_execution_count"],
        "matched_control_cells": boundary["verified_parent_comparison_count"],
        "control": boundary["parent_B_comparison"],
        "candidate": boundary["reflection_arms"]["3200"],
        "reflection_convergence": boundary["reflection_convergence"],
        "boundary_trend": boundary["boundary_trend"],
        "multiresponse_paired_directions": boundary[
            "multiresponse_paired_directions"
        ],
        "realized_kinematic_ratio_by_tier": boundary["reflection_arms"][
            "3200"
        ]["realized_kinematic_ratio_by_tier"],
        "analytic_envelope": boundary["reflection_arms"]["3200"][
            "broad_analytic_envelope"
        ],
        "decision": boundary["decision"],
    },
    "cmp": {
        "status": "measurement_and_control_harness_ready",
        "qualification_grids": [0.0025, 0.00125],
        "material_regions_checked": ["SiO2 stop", "TaN barrier", "Cu seed", "Cu plug"],
        "connectivity_rule": "one resolved signed region must connect the via floor to both mouth sides",
        "feature_resolution_rule": "features at or below two grid cells remain unresolved",
        "recipe_doe_authorized": False,
        "reason_doe_blocked": "allowable stop-layer and Cu-plug loss thresholds are not yet declared",
        "model_limit": "height and material dependent removal without pad pressure",
    },
}

OUTPUT.write_text(json.dumps(data, separators=(",", ":")))
print(f"wrote {OUTPUT.name}: {data['selected_foundation_cases']} selected foundation cases")

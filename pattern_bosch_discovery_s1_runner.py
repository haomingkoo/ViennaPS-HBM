"""Resumable executor for broad-first Bosch factor discovery."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import math
from pathlib import Path

import viennals._core as ls_core
import viennaps._core as ps_core

import build_pattern_bosch_discovery_s1 as builder
import foundation_metric_audit as foundation
import foundation_pattern_bosch_gate0 as gate0
import foundation_pattern_bosch_gate0_r1 as r1


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "pattern_bosch_discovery_s1_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/"
    "pattern_bosch_discovery_s1_rows.jsonl"
)
CASE_FIELDS = (
    "manifest_version",
    "campaign",
    "labels",
    "recipe_id",
    "case_role",
    "design_class",
    "anchor_reasons",
    "normalized_coordinates",
    "geometry",
    "recipe",
    "numerics",
    "trajectory",
    "target",
    "rng_seed",
    "rng_stream",
    "runtime_fingerprint",
    "source_artifacts",
    "authority",
    "provenance",
)


def file_sha256(path):
    return foundation.file_sha256(path)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def runtime_fingerprint(project_root=ROOT):
    root = Path(project_root)
    return {
        "runner_sha256": file_sha256(root / Path(__file__).name),
        "reviewer_sha256": file_sha256(root / "review_pattern_bosch_discovery_s1.py"),
        "builder_sha256": file_sha256(root / "build_pattern_bosch_discovery_s1.py"),
        "design_spec_sha256": file_sha256(root / builder.DEFAULT_SPEC),
        "r1_runner_sha256": file_sha256(root / "foundation_pattern_bosch_gate0_r1.py"),
        "screen_kernel_sha256": file_sha256(root / "pattern_bosch_screen_runner.py"),
        "native_checkpoint_sha256": file_sha256(root / "native_domain_checkpoint.py"),
        "gate0_metric_sha256": file_sha256(root / "foundation_pattern_bosch_gate0.py"),
        "traveler_metrics_sha256": file_sha256(root / "traveler_metrics.py"),
        "tsv_process_sha256": file_sha256(root / "tsv_process.py"),
        "viennaps_binary_sha256": file_sha256(ps_core.__file__),
        "viennals_binary_sha256": file_sha256(ls_core.__file__),
    }


def evidence_origin():
    return {
        "mode": "executed_pattern_bosch_discovery_s1",
        "per_seed_depth_matched": True,
        "native_vpsd_checkpoint": True,
        "nominal_pattern_geometry": True,
        "two_seed_factor_discovery": True,
        "recipe_authority": False,
    }


def case_payload(case):
    return {field: case.get(field) for field in CASE_FIELDS}


def case_id(payload):
    return canonical_sha256(payload)[:16]


def validate_r1_prerequisite(summary):
    errors = []
    bridge = summary.get("ray_bridge", {})
    expected_seeds = set(r1.EXPECTED_SEEDS)
    bridge_pairs = bridge.get("pairs", [])
    if (
        bridge.get("pass") is not True
        or len(bridge_pairs) != len(expected_seeds)
        or {row.get("rng_seed") for row in bridge_pairs} != expected_seeds
    ):
        errors.append("R1 did not qualify 1000 rays against 2000 rays")
    references = [
        row for row in summary.get("reviewed_cases", [])
        if row.get("arm") == r1.REFERENCE_ARM
    ]
    if not (
        len(references) == 4
        and {row.get("rng_seed") for row in references} == expected_seeds
        and all(
            row.get("valid") is True
            and row.get("hard_gate_pass") is True
            and row.get("native_roundtrip_exact") is True
            and row.get("rays_per_point") == 1000
            for row in references
        )
    ):
        errors.append("R1 does not contain four valid passing 1000-ray references")
    handoffs = summary.get("native_handoffs", {}).get("handoff_results", [])
    if (
        len(handoffs) != 4
        or {row.get("rng_seed") for row in handoffs} != expected_seeds
        or not all(row.get("accepted") is True for row in handoffs)
    ):
        errors.append("R1 native checkpoint evidence is incomplete")
    return errors


def validate_manifest(
    manifest, *, check_runtime=True, check_prerequisite=True, project_root=ROOT
):
    errors = []
    root = Path(project_root)
    spec = builder.common.strict_load(root / builder.DEFAULT_SPEC)
    expected_design = builder.build_design(spec)
    if str(spec.get("status", "")).startswith("superseded"):
        errors.append(
            "superseded Bosch-only S1 methodology; follow RESEARCH_PLAN_V3.md"
        )
    if manifest.get("manifest_version") != 1:
        errors.append("manifest version differs")
    if manifest.get("campaign") != "pattern-bosch-discovery-s1":
        errors.append("campaign name differs")
    if manifest.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("required labels differ")
    if manifest.get("design") != expected_design:
        errors.append("embedded deterministic design differs")
    if manifest.get("execution") != {
        "output": str(DEFAULT_OUTPUT),
        "maximum_workers": 2,
        "threads_per_worker": 7,
        "executor": "direct_checkpointed_batch_no_llm",
    }:
        errors.append("execution contract differs")
    if manifest.get("authority") != expected_design["authority"]:
        errors.append("authority differs")
    if check_runtime and manifest.get("runtime_fingerprint") != runtime_fingerprint(root):
        errors.append("runtime or source fingerprint differs")
    declaration = manifest.get("source_artifacts", {}).get("gate0_r1_summary", {})
    source = Path(declaration.get("path", ""))
    source = source if source.is_absolute() else root / source
    if check_prerequisite:
        if not source.is_file():
            errors.append("R1 summary is missing")
        elif declaration.get("sha256") != file_sha256(source):
            errors.append("R1 summary hash differs")
        else:
            try:
                summary = gate0.strict_json_loads(source.read_text())
                errors.extend(validate_r1_prerequisite(summary))
            except Exception as error:
                errors.append(f"R1 summary does not parse: {error}")
    return errors


def expand_cases(manifest):
    design = manifest["design"]
    horizon = design["rng_process_seed_horizon"]
    policy = design["rng_policy"]
    cases = []
    replicated = set(design["sentinels"]["replicated_recipe_ids"])
    fidelity = set(design["sentinels"]["fidelity_recipe_ids"])
    allocation_index = 0
    for row in design["recipes"]:
        schedule = []
        base_allocations = []
        for replicate in range(policy["base_replicates_per_recipe"]):
            seed = policy["seed_start"] + allocation_index * policy[
                "interval_stride"
            ]
            allocation = {
                "rng_seed": seed,
                "allocation_id": f"pbds1_rng_{allocation_index:04d}",
                "replicate_index": replicate,
                "interval_reused_for_fidelity": row["recipe_id"] in fidelity,
            }
            base_allocations.append(allocation)
            schedule.append((allocation, design["numerics"]["rays_per_point"], "base_discovery"))
            allocation_index += 1
        if row["recipe_id"] in replicated:
            for replicate in range(
                policy["sentinel_extra_replicates_per_recipe"]
            ):
                seed = policy["seed_start"] + allocation_index * policy[
                    "interval_stride"
                ]
                allocation = {
                    "rng_seed": seed,
                    "allocation_id": f"pbds1_rng_{allocation_index:04d}",
                    "replicate_index": (
                        policy["base_replicates_per_recipe"] + replicate
                    ),
                    "interval_reused_for_fidelity": False,
                }
                schedule.append((
                    allocation,
                    design["numerics"]["rays_per_point"],
                    "sentinel_noise",
                ))
                allocation_index += 1
        if row["recipe_id"] in fidelity:
            schedule.extend(
                (
                    allocation,
                    design["numerics"]["fidelity_anchor_rays_per_point"],
                    "sentinel_fidelity",
                )
                for allocation in base_allocations
            )
        for allocation, rays, role in schedule:
            seed = allocation["rng_seed"]
            recipe = {
                **row["recipe"],
                "mask_taper": design["geometry"]["mask_taper"],
                "mask_ion_rate": design["fixed_recipe"]["mask_ion_rate"],
            }
            current = {
                "manifest_version": manifest["manifest_version"],
                "campaign": manifest["campaign"],
                "labels": list(manifest["labels"]),
                "recipe_id": row["recipe_id"],
                "case_role": role,
                "design_class": row["design_class"],
                "anchor_reasons": list(row["anchor_reasons"]),
                "normalized_coordinates": dict(row["normalized_coordinates"]),
                "geometry": dict(design["geometry"]),
                "recipe": recipe,
                "numerics": {
                    "grid_delta": design["numerics"]["grid_delta"],
                    "rays_per_point": rays,
                    "threads_per_worker": design["numerics"]["threads_per_worker"],
                    "simulation_dimension": design["numerics"]["dimension"],
                },
                "trajectory": dict(design["trajectory"]),
                "target": dict(design["target"]),
                "rng_seed": int(seed),
                "rng_stream": {
                    "allocation_id": allocation["allocation_id"],
                    "replicate_index": allocation["replicate_index"],
                    "base_seed": int(seed),
                    "first_process_seed": int(seed),
                    "last_process_seed": int(seed) + horizon - 1,
                    "process_seed_horizon": horizon,
                    "streams_disjoint_within_recipe": True,
                    "globally_disjoint_except_same_recipe_fidelity": True,
                    "same_base_labels_reused_across_recipes": False,
                    "interval_reused_for_fidelity": allocation[
                        "interval_reused_for_fidelity"
                    ],
                    "pointwise_common_random_numbers_not_claimed": True,
                },
                "runtime_fingerprint": dict(manifest["runtime_fingerprint"]),
                "source_artifacts": dict(manifest["source_artifacts"]),
                "authority": dict(manifest["authority"]),
                "provenance": dict(manifest["provenance"]),
            }
            payload = case_payload(current)
            current["case_id"] = case_id(payload)
            current["case_payload_sha256"] = canonical_sha256(payload)
            cases.append(current)
    return cases


def rng_interval_errors(cases):
    """Reject RNG overlap except an intentional same-recipe fidelity pair."""
    errors = []
    ordered = sorted(
        cases,
        key=lambda case: (
            case["rng_stream"]["first_process_seed"],
            case["rng_stream"]["last_process_seed"],
            case["case_id"],
        ),
    )
    for index, first in enumerate(ordered):
        first_stream = first["rng_stream"]
        if first_stream["first_process_seed"] != first["rng_seed"]:
            errors.append(f"{first['case_id']}: first process seed differs")
        if first_stream["last_process_seed"] != (
            first["rng_seed"] + first_stream["process_seed_horizon"] - 1
        ):
            errors.append(f"{first['case_id']}: process-seed interval differs")
        for second in ordered[index + 1:]:
            second_stream = second["rng_stream"]
            if second_stream["first_process_seed"] > first_stream[
                "last_process_seed"
            ]:
                break
            allowed_fidelity_pair = bool(
                first["recipe_id"] == second["recipe_id"]
                and first["rng_seed"] == second["rng_seed"]
                and first_stream["allocation_id"]
                == second_stream["allocation_id"]
                and {first["case_role"], second["case_role"]}
                == {"base_discovery", "sentinel_fidelity"}
                and {
                    first["numerics"]["rays_per_point"],
                    second["numerics"]["rays_per_point"],
                }
                == {1000, 2000}
            )
            if not allowed_fidelity_pair:
                errors.append(
                    f"{first['case_id']} overlaps RNG interval with "
                    f"{second['case_id']}"
                )
    return errors


def row_matches_case(row, case):
    return bool(
        row.get("case_id") == case["case_id"]
        and row.get("case_payload_sha256") == case["case_payload_sha256"]
        and case_payload(row) == case_payload(case)
        and case_id(case_payload(row)) == case["case_id"]
        and canonical_sha256(case_payload(row)) == case["case_payload_sha256"]
    )


def run_case(task):
    row = r1.run_case(task)
    row["evidence_origin"] = evidence_origin()
    history = row.get("cycle_history") or []
    last = history[-1] if history else {}
    lower_depth = row["target"]["etch_depth"] - row["target"]["depth_tolerance"]
    shallow_censored = bool(
        row.get("ok") is True
        and row.get("early_stopped") is False
        and row.get("last_recorded_cycle") == row["trajectory"]["maximum_cycles"]
        and isinstance(last.get("depth"), (int, float))
        and math.isfinite(float(last["depth"]))
        and last["depth"] < lower_depth
    )
    row["trajectory_classification"] = (
        "shallow_at_cycle_horizon_boundary_limited"
        if shallow_censored
        else "depth_selected"
    )
    row["depth_horizon_censored"] = shallow_censored
    return row


def validate_success_row(row, case, output):
    errors = []
    if not row_matches_case(row, case):
        errors.append("case payload differs")
    if row.get("evidence_origin") != evidence_origin():
        errors.append("evidence origin differs")
    history = row.get("cycle_history") or []
    last = history[-1] if history else {}
    lower_depth = case["target"]["etch_depth"] - case["target"]["depth_tolerance"]
    expected_censored = bool(
        row.get("early_stopped") is False
        and row.get("last_recorded_cycle") == case["trajectory"]["maximum_cycles"]
        and isinstance(last.get("depth"), (int, float))
        and math.isfinite(float(last["depth"]))
        and last["depth"] < lower_depth
    )
    if row.get("depth_horizon_censored") is not expected_censored:
        errors.append("depth-horizon censoring differs")
    expected_classification = (
        "shallow_at_cycle_horizon_boundary_limited"
        if expected_censored else "depth_selected"
    )
    if row.get("trajectory_classification") != expected_classification:
        errors.append("trajectory classification differs")
    bridge = dict(row)
    bridge["evidence_origin"] = r1.evidence_origin()
    errors.extend(r1.validate_success_row(bridge, case, output))
    return errors


def audit_existing_rows(output, cases):
    output = Path(output)
    if not output.is_file():
        return {}
    expected = {case["case_id"]: case for case in cases}
    successes = {}
    terminal_success = set()
    for line_number, line in enumerate(output.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = gate0.strict_json_loads(line)
        except Exception as error:
            raise ValueError(f"malformed row {line_number}: {error}") from error
        current_id = row.get("case_id")
        case = expected.get(current_id)
        if case is None:
            raise ValueError(f"unexpected case ID at row {line_number}")
        if current_id in terminal_success:
            raise ValueError(f"attempt follows success at row {line_number}")
        if not row_matches_case(row, case):
            raise ValueError(f"stale case payload at row {line_number}")
        if row.get("ok") is True:
            errors = validate_success_row(row, case, output)
            if errors:
                raise ValueError(
                    f"invalid success at row {line_number}: " + "; ".join(errors)
                )
            successes[current_id] = row
            terminal_success.add(current_id)
        elif row.get("ok") is not False:
            raise ValueError(f"row {line_number} lacks a boolean execution status")
    return successes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    manifest = gate0.strict_json_loads(args.manifest.read_text())
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid Bosch discovery manifest: " + "; ".join(errors))
    if args.output != Path(manifest["execution"]["output"]):
        raise ValueError("output differs from the frozen execution contract")
    if args.workers != manifest["execution"]["maximum_workers"]:
        raise ValueError("worker count differs from the frozen execution contract")
    cases = expand_cases(manifest)
    if len(cases) != 232 or len({case["case_id"] for case in cases}) != 232:
        raise ValueError("expanded discovery matrix is not 232 unique cases")
    interval_errors = rng_interval_errors(cases)
    if interval_errors:
        raise ValueError("invalid discovery RNG allocation: " + "; ".join(
            interval_errors
        ))
    successes = audit_existing_rows(args.output, cases)
    pending = [case for case in cases if case["case_id"] not in successes]
    if args.limit is not None:
        pending = pending[:args.limit]
    print(
        f"logical=232 complete={len(successes)} pending={len(pending)} "
        "authority=factor_discovery_only",
        flush=True,
    )
    if not pending:
        return
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for index, row in enumerate(
            executor.map(run_case, [(case, args.output) for case in pending]),
            start=1,
        ):
            gate0.append_row(args.output, row)
            print(
                f"[{index}/{len(pending)}] {row['case_id']} ok={row['ok']} "
                f"elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )
            if row.get("ok") is not True:
                raise RuntimeError(f"Bosch discovery case failed: {row['case_id']}")


if __name__ == "__main__":
    main()

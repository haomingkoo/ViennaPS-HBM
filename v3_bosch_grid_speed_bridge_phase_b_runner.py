"""Run the four-case Bosch speed-bridge Phase B."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import copy
from pathlib import Path

import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as stage2a


DEFAULT_MANIFEST = Path("evidence/numerical/v3_bosch_grid_speed_bridge_phase_b_manifest.json")
DEFAULT_OUTPUT = Path("autoresearch-results/restart_audit/v3_bosch_grid_speed_bridge_phase_b_rows.jsonl")
CAMPAIGN = "v3-bosch-grid-speed-bridge-phase-b"


def evidence_origin():
    return {
        "mode": "executed_v3_bosch_grid_speed_bridge_phase_b",
        "per_recipe_depth_matched": True,
        "native_vpsd_checkpoint": True,
        "simulation_dimension": 2,
        "paired_base_seed_reuse": True,
        "pointwise_common_random_numbers_claimed": False,
        "numerical_setting_authority": False,
    }


def expand_cases(manifest):
    root = Path(__file__).resolve().parent
    focused = gate0.strict_json_loads((root / manifest["source_artifacts"]["focused_manifest"]["path"]).read_text())
    sources = {case["case_id"]: case for case in stage2a.expand_cases(focused)}
    cases = []
    for run in manifest["design"]["runs"]:
        case = copy.deepcopy(sources[run["source_fine_case_id"]])
        if case["rng_seed"] != run["rng_seed"]:
            raise ValueError(f"{run['run_id']}: declared seed differs")
        case.update({
            "campaign": manifest["campaign"],
            "labels": list(manifest["labels"]),
            "recipe_id": "v3gridbridgeb_" + run["run_id"].replace(".", "p"),
            "design_class": run["role"],
            "anchor_reasons": [f"phase_b:{run['cell_id']}:{run['role']}"],
            "runtime_fingerprint": dict(manifest["runtime_fingerprint"]),
            "source_artifacts": dict(manifest["source_artifacts"]),
            "authority": dict(manifest["authority"]),
            "provenance": dict(manifest["provenance"]),
        })
        case["numerics"].update(grid_delta=run["grid_delta"], rays_per_point=run["rays_per_point"])
        case["rng_stream"].update({
            "allocation_id": f"grid_bridge_b_{run['run_id']}",
            "phase_b_run_id": run["run_id"],
            "intentional_evidence_pair_reuse": True,
            "paired_fine_case_id": run["source_fine_case_id"],
            "paired_phase_a_case_id": run["paired_phase_a_case_id"],
        })
        payload = stage2a.case_payload(case)
        case["case_id"] = stage2a.case_id(payload)
        case["case_payload_sha256"] = stage2a.canonical_sha256(payload)
        cases.append(case)
    return cases


def paired_rng_errors(cases, manifest):
    errors = []
    runs = {run["run_id"]: run for run in manifest["design"]["runs"]}
    intervals = []
    for case in cases:
        run_id = case["rng_stream"].get("phase_b_run_id")
        run = runs.get(run_id)
        if run is None or case["rng_seed"] != run["rng_seed"]:
            errors.append(f"{case['case_id']}: pairing declaration differs")
        if case["rng_stream"].get("intentional_evidence_pair_reuse") is not True:
            errors.append(f"{case['case_id']}: reuse is undeclared")
        stream = case["rng_stream"]
        intervals.append((case["case_id"], stream["first_process_seed"], stream["last_process_seed"]))
        for reserved in stream["reserved_prior_v3_intervals"]:
            if not (stream["last_process_seed"] < reserved["first"] or stream["first_process_seed"] > reserved["last"]):
                errors.append(f"{case['case_id']} overlaps undeclared prior interval {reserved['campaign']}")
    for index, first in enumerate(intervals):
        for second in intervals[index + 1:]:
            if not (first[2] < second[1] or second[2] < first[1]):
                errors.append(f"{first[0]} overlaps Phase B run {second[0]}")
    return errors


def validate_manifest(manifest):
    errors = []
    if manifest.get("campaign") != CAMPAIGN:
        errors.append("campaign differs")
    if len(manifest.get("design", {}).get("runs", [])) != 4:
        errors.append("run count differs")
    plan = manifest.get("design", {}).get("analysis_plan", {})
    if plan.get("accuracy_limit", "missing") is not None or plan.get("weighted_score", "missing") is not None:
        errors.append("an accuracy limit or score was introduced")
    root = Path(__file__).resolve().parent
    for declaration in manifest.get("source_artifacts", {}).values():
        path = root / declaration.get("path", "")
        if not path.is_file() or stage2a.file_sha256(path) != declaration.get("sha256"):
            errors.append(f"source artifact differs: {path}")
    cases = expand_cases(manifest)
    errors.extend(paired_rng_errors(cases, manifest))
    if len({case["case_id"] for case in cases}) != 4:
        errors.append("case IDs are not unique")
    return errors


def run_case(task):
    stage2a.evidence_origin = evidence_origin
    return stage2a.run_case(task)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest = gate0.strict_json_loads(stage2a.project_path(args.manifest).read_text())
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid Phase B bridge: " + "; ".join(errors))
    output = stage2a.project_path(args.output)
    if output != stage2a.project_path(manifest["execution"]["output"]):
        raise ValueError("output differs from frozen contract")
    if args.workers != manifest["execution"]["maximum_workers"]:
        raise ValueError("workers differ from frozen contract")
    cases = expand_cases(manifest)
    stage2a.evidence_origin = evidence_origin
    if args.dry_run:
        complete = stage2a.audit_existing_rows(output, cases)
        print(f"logical=4 complete={len(complete)} pending={4-len(complete)}")
        return
    lock, _ = stage2a.acquire_campaign_lock(output, manifest["campaign"])
    try:
        complete = stage2a.audit_existing_rows(output, cases)
        pending = [case for case in cases if case["case_id"] not in complete]
        with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            submitted = {executor.submit(run_case, (case, output)): case for case in pending}
            for future in futures.as_completed(submitted):
                case = submitted[future]
                row = future.result()
                errors = stage2a.worker_row_errors(row, case, output)
                if errors:
                    raise RuntimeError(f"{case['case_id']}: {'; '.join(errors)}")
                gate0.append_row(output, row)
    finally:
        stage2a.release_campaign_lock(lock)


if __name__ == "__main__":
    main()

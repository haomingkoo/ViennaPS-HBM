"""Run the frozen focused Bosch ion-direction map."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
from pathlib import Path

import foundation_pattern_bosch_gate0 as gate0
import v3_pattern_bosch_stage2a_runner as stage2a


DEFAULT_MANIFEST = Path("evidence/numerical/v3_bosch_focused_ion_map_manifest.json")
DEFAULT_OUTPUT = Path("autoresearch-results/restart_audit/v3_bosch_focused_ion_map_rows.jsonl")
CAMPAIGN = "v3-bosch-focused-ion-map"


def evidence_origin():
    return {
        "mode": "executed_v3_bosch_focused_ion_map",
        "per_recipe_depth_matched": True,
        "native_vpsd_checkpoint": True,
        "nominal_pattern_geometry": True,
        "simulation_dimension": 2,
        "independent_rng_interval_per_run": True,
        "within_recipe_repeats_present": True,
        "recipe_authority": False,
    }


def run_case(task):
    stage2a.evidence_origin = evidence_origin
    return stage2a.run_case(task)


def validate_manifest(manifest):
    errors = []
    if manifest.get("campaign") != CAMPAIGN:
        errors.append("campaign differs")
    if manifest.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("labels differ")
    design = manifest.get("design", {})
    if design.get("numerics", {}).get("rays_per_point") != 500:
        errors.append("ray count differs")
    if len(design.get("recipes", [])) != 12:
        errors.append("run count differs")
    if design.get("analysis_plan", {}).get("weighted_score_authorized") is not False:
        errors.append("weighted-score policy differs")
    if manifest.get("execution", {}).get("output") != str(DEFAULT_OUTPUT):
        errors.append("output contract differs")
    root = Path(__file__).resolve().parent
    for declaration in manifest.get("source_artifacts", {}).values():
        path = root / declaration.get("path", "")
        if not path.is_file() or stage2a.file_sha256(path) != declaration.get("sha256"):
            errors.append(f"source artifact differs: {path}")
    cases = stage2a.expand_cases(manifest)
    errors.extend(stage2a.rng_interval_errors(cases))
    if len({case["case_id"] for case in cases}) != len(cases):
        errors.append("case IDs are not unique")
    return errors


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
        raise ValueError("invalid focused ion map: " + "; ".join(errors))
    output = stage2a.project_path(args.output)
    if output != stage2a.project_path(manifest["execution"]["output"]):
        raise ValueError("output differs from frozen contract")
    if args.workers != manifest["execution"]["maximum_workers"]:
        raise ValueError("workers differ from frozen contract")
    stage2a.evidence_origin = evidence_origin
    cases = stage2a.expand_cases(manifest)
    if args.dry_run:
        completed = stage2a.audit_existing_rows(output, cases)
        print(
            f"logical={len(cases)} complete={len(completed)} "
            f"pending={len(cases) - len(completed)}",
            flush=True,
        )
        return
    lock, lock_path = stage2a.acquire_campaign_lock(output, manifest["campaign"])
    try:
        completed = stage2a.audit_existing_rows(output, cases)
        pending = [case for case in cases if case["case_id"] not in completed]
        print(
            f"logical={len(cases)} complete={len(completed)} "
            f"pending={len(pending)} lock={lock_path}",
            flush=True,
        )
        if not pending:
            return
        with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            submitted = {executor.submit(run_case, (case, output)): case for case in pending}
            for index, future in enumerate(futures.as_completed(submitted), 1):
                case = submitted[future]
                row = future.result()
                errors = stage2a.worker_row_errors(row, case, output)
                if errors:
                    raise RuntimeError(f"focused case failed: {case['case_id']}: {'; '.join(errors)}")
                gate0.append_row(output, row)
                print(f"[{index}/{len(pending)}] {row['case_id']} elapsed={row['elapsed_s']:.1f}s", flush=True)
    finally:
        stage2a.release_campaign_lock(lock)


if __name__ == "__main__":
    main()

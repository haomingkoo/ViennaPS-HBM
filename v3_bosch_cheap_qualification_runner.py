"""Checkpointed executor for the cheap Bosch screening-mode qualification."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
from pathlib import Path

import foundation_pattern_bosch_gate0 as gate0
import native_domain_checkpoint as native_checkpoint
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/v3_bosch_cheap_qualification_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/v3_bosch_cheap_qualification_rows.jsonl"
)


def evidence_origin():
    return {
        "mode": "executed_v3_bosch_cheap_qualification",
        "per_recipe_depth_matched": True,
        "native_vpsd_checkpoint": True,
        "nominal_pattern_geometry": True,
        "simulation_dimension": 2,
        "independent_rng_interval_per_recipe": True,
        "within_recipe_noise_estimated": True,
        "confirmed_factor_authority": False,
        "recipe_authority": False,
    }


def run_case(task):
    stage2a.evidence_origin = evidence_origin
    return stage2a.run_case(task)


def validate_manifest(manifest):
    errors = []
    if manifest.get("campaign") != "v3-bosch-cheap-qualification":
        errors.append("campaign differs")
    if manifest.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("labels differ")
    design = manifest.get("design", {})
    if design.get("numerics", {}).get("rays_per_point") != 500:
        errors.append("candidate ray count differs")
    if design.get("trajectory", {}).get("early_stop_depth") != 1.36:
        errors.append("early-stop depth differs")
    if len(design.get("recipes", [])) != 16:
        errors.append("qualification case count differs")
    execution = manifest.get("execution", {})
    if execution.get("output") != str(DEFAULT_OUTPUT):
        errors.append("output contract differs")
    if execution.get("maximum_workers") != 2:
        errors.append("worker contract differs")
    for declaration in manifest.get("source_artifacts", {}).values():
        path = ROOT / declaration.get("path", "")
        if not path.is_file() or stage2a.file_sha256(path) != declaration.get("sha256"):
            errors.append(f"source artifact differs: {path}")
    return errors


def completed_rows(output, cases):
    expected = {case["case_id"]: case for case in cases}
    completed = {}
    if not output.is_file():
        return completed
    for number, line in enumerate(output.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = gate0.strict_json_loads(line)
        case = expected.get(row.get("case_id"))
        if case is None or not stage2a.row_matches_case(row, case):
            raise ValueError(f"unexpected or stale row {number}")
        if row.get("ok") is not True or row.get("evidence_origin") != evidence_origin():
            raise ValueError(f"invalid qualification row {number}")
        checkpoint = Path(row.get("checkpoint_path", ""))
        native_checkpoint.load_domain_checkpoint(
            checkpoint, expected_sha256=row.get("checkpoint_sha256")
        )
        completed[row["case_id"]] = row
    return completed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest_path = stage2a.project_path(args.manifest)
    output = stage2a.project_path(args.output)
    manifest = gate0.strict_json_loads(manifest_path.read_text())
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid cheap qualification manifest: " + "; ".join(errors))
    if output != stage2a.project_path(manifest["execution"]["output"]):
        raise ValueError("output differs from frozen contract")
    if args.workers != manifest["execution"]["maximum_workers"]:
        raise ValueError("workers differ from frozen contract")

    lock, lock_path = stage2a.acquire_campaign_lock(output, manifest["campaign"])
    try:
        cases = stage2a.expand_cases(manifest)
        completed = completed_rows(output, cases)
        pending = [case for case in cases if case["case_id"] not in completed]
        print(f"logical={len(cases)} complete={len(completed)} pending={len(pending)} lock={lock_path}", flush=True)
        if args.dry_run or not pending:
            return
        with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_case = {
                executor.submit(run_case, (case, output)): case for case in pending
            }
            for index, future in enumerate(futures.as_completed(future_to_case), 1):
                case = future_to_case[future]
                row = future.result()
                if (
                    not stage2a.row_matches_case(row, case)
                    or row.get("evidence_origin") != evidence_origin()
                    or row.get("ok") is not True
                ):
                    raise RuntimeError(f"qualification case failed: {case['case_id']}")
                gate0.append_row(output, row)
                print(
                    f"[{index}/{len(pending)}] {row['case_id']} elapsed={row['elapsed_s']:.1f}s",
                    flush=True,
                )
    finally:
        stage2a.release_campaign_lock(lock)


if __name__ == "__main__":
    main()

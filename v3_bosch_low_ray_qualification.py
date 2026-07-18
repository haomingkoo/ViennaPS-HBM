"""Build and run the 125/250-ray Bosch discovery qualification."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import copy
import json
import os
from pathlib import Path

import foundation_pattern_bosch_gate0 as gate0
import native_domain_checkpoint as native_checkpoint
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / ".scratch/full-traveler-autoresearch/v3_bosch_cheap_qualification_manifest.json"
RAY_COUNTS = (125, 250)
SEED_START = {125: 1_120_000, 250: 1_140_000}


def manifest_path(rays):
    return ROOT / f".scratch/full-traveler-autoresearch/v3_bosch_r{rays}_qualification_manifest.json"


def rows_path(rays):
    return Path(f"autoresearch-results/restart_audit/v3_bosch_r{rays}_qualification_rows.jsonl")


def evidence_origin(rays):
    return {
        "mode": f"executed_v3_bosch_r{rays}_qualification",
        "per_recipe_depth_matched": True,
        "native_vpsd_checkpoint": True,
        "nominal_pattern_geometry": True,
        "simulation_dimension": 2,
        "independent_rng_interval_per_recipe": True,
        "within_recipe_noise_estimated": True,
        "confirmed_factor_authority": False,
        "recipe_authority": False,
    }


def freeze(path, value):
    serialized = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text() != serialized:
            raise ValueError(f"refusing to overwrite different manifest: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized)
    os.replace(temporary, path)


def build_manifest(rays):
    if rays not in RAY_COUNTS:
        raise ValueError(f"unsupported ray count: {rays}")
    source = gate0.strict_json_loads(SOURCE.read_text())
    design = copy.deepcopy(source["design"])
    campaign = f"v3-bosch-r{rays}-qualification"
    design["campaign"] = campaign
    design["question"] = (
        f"Does a {rays}-ray discovery mode preserve the decisions and factor "
        "ranking observed at 2,000 rays?"
    )
    design["numerics"]["rays_per_point"] = rays
    design["rng_policy"].update({
        "seed_start": SEED_START[rays],
        "interval_count": len(design["recipes"]),
        "assignment": "one disjoint low-ray interval per logical simulation",
        "interpretation": "discovery-only; compare with preserved 500- and 2,000-ray evidence",
    })
    design["authority"]["cheap_screen_qualification_only"] = True
    output = rows_path(rays)
    return {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": campaign,
        "labels": ["full-traveler", "critical-review"],
        "design": design,
        "execution": {
            "output": str(output),
            "maximum_workers": 2,
            "threads_per_worker": 7,
            "executor": "direct_checkpointed_batch_no_llm",
        },
        "runtime_fingerprint": stage2a.runtime_fingerprint(ROOT),
        "source_artifacts": {
            **source["source_artifacts"],
            "r500_manifest": {
                "path": str(SOURCE.relative_to(ROOT)),
                "sha256": stage2a.file_sha256(SOURCE),
            },
        },
        "authority": design["authority"],
        "provenance": {
            "purpose": "find the cheapest broad-discovery ray count",
            "reference_rays_per_point": 2000,
            "qualified_discovery_rays_per_point": 500,
            "candidate_rays_per_point": rays,
            "existing_high_ray_artifacts_preserved": True,
        },
    }


def validate_manifest(manifest, rays):
    errors = []
    if manifest.get("campaign") != f"v3-bosch-r{rays}-qualification":
        errors.append("campaign differs")
    design = manifest.get("design", {})
    if design.get("numerics", {}).get("rays_per_point") != rays:
        errors.append("candidate ray count differs")
    if len(design.get("recipes", [])) != 16:
        errors.append("qualification case count differs")
    if manifest.get("execution", {}).get("output") != str(rows_path(rays)):
        errors.append("output contract differs")
    if manifest.get("execution", {}).get("maximum_workers") != 2:
        errors.append("worker contract differs")
    for declaration in manifest.get("source_artifacts", {}).values():
        path = ROOT / declaration.get("path", "")
        if not path.is_file() or stage2a.file_sha256(path) != declaration.get("sha256"):
            errors.append(f"source artifact differs: {path}")
    return errors


def run_case(task):
    case, _output = task
    rays = case["numerics"]["rays_per_point"]
    stage2a.evidence_origin = lambda: evidence_origin(rays)
    return stage2a.run_case(task)


def completed_rows(output, cases, rays):
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
        if row.get("ok") is not True or row.get("evidence_origin") != evidence_origin(rays):
            raise ValueError(f"invalid qualification row {number}")
        native_checkpoint.load_domain_checkpoint(
            Path(row["checkpoint_path"]), expected_sha256=row["checkpoint_sha256"]
        )
        completed[row["case_id"]] = row
    return completed


def run_manifest(rays, workers, dry_run):
    path = manifest_path(rays)
    manifest = gate0.strict_json_loads(path.read_text())
    errors = validate_manifest(manifest, rays)
    if errors:
        raise ValueError("invalid low-ray manifest: " + "; ".join(errors))
    if workers != manifest["execution"]["maximum_workers"]:
        raise ValueError("workers differ from frozen contract")
    output = ROOT / rows_path(rays)
    lock, lock_path = stage2a.acquire_campaign_lock(output, manifest["campaign"])
    try:
        cases = stage2a.expand_cases(manifest)
        completed = completed_rows(output, cases, rays)
        pending = [case for case in cases if case["case_id"] not in completed]
        print(
            f"rays={rays} logical={len(cases)} complete={len(completed)} "
            f"pending={len(pending)} lock={lock_path}",
            flush=True,
        )
        if dry_run or not pending:
            return
        with futures.ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_case = {
                executor.submit(run_case, (case, output)): case for case in pending
            }
            for index, future in enumerate(futures.as_completed(future_to_case), 1):
                case = future_to_case[future]
                row = future.result()
                if (
                    not stage2a.row_matches_case(row, case)
                    or row.get("evidence_origin") != evidence_origin(rays)
                    or row.get("ok") is not True
                ):
                    raise RuntimeError(f"low-ray case failed: {case['case_id']}")
                gate0.append_row(output, row)
                print(
                    f"rays={rays} [{index}/{len(pending)}] {row['case_id']} "
                    f"elapsed={row['elapsed_s']:.1f}s",
                    flush=True,
                )
    finally:
        stage2a.release_campaign_lock(lock)


def selected_rays(value):
    return RAY_COUNTS if value == "all" else (int(value),)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "run", "status"))
    parser.add_argument("--rays", choices=("all", "125", "250"), default="all")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    for rays in selected_rays(args.rays):
        if args.action == "build":
            manifest = build_manifest(rays)
            freeze(manifest_path(rays), manifest)
            print(
                json.dumps({
                    "campaign": manifest["campaign"],
                    "logical_simulations": len(manifest["design"]["recipes"]),
                    "rays_per_point": rays,
                    "canonical_sha256": stage2a.canonical_sha256(manifest),
                }, sort_keys=True)
            )
        else:
            run_manifest(rays, args.workers, args.action == "status")


if __name__ == "__main__":
    main()

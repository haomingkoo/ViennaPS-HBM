"""Run the frozen Bosch ray-count ladder."""

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
SOURCE = ROOT / ".scratch/full-traveler-autoresearch/v3_pattern_bosch_stage2a_manifest.json"
RAY_COUNTS = (250, 375, 500, 750, 1000, 2000)
ANCHORS = (
    "nominal",
    "ofat:etch_time:low",
    "ofat:etch_time:high",
    "ofat:neutral_sticking_probability:low",
    "ofat:theta_r_min:low",
    "ofat:ion_rate:low",
    "ofat:ion_rate:high",
)
SEED_START = 1_220_000


def manifest_path(rays: int) -> Path:
    return ROOT / f".scratch/full-traveler-autoresearch/v3_bosch_clean_r{rays}_manifest.json"


def rows_path(rays: int) -> Path:
    return Path(f"autoresearch-results/restart_audit/v3_bosch_clean_r{rays}_rows.jsonl")


def evidence_origin(rays: int) -> dict:
    return {
        "mode": "executed_v3_bosch_clean_ray_ladder",
        "candidate_rays_per_point": rays,
        "paired_base_seed_labels": True,
        "pointwise_common_random_numbers_claimed": False,
        "per_recipe_depth_matched": True,
        "native_vpsd_checkpoint": True,
        "simulation_dimension": 2,
        "confirmed_factor_authority": False,
        "recipe_authority": False,
    }


def freeze(path: Path, value: dict) -> None:
    serialized = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text() != serialized:
            raise ValueError(f"refusing to overwrite different manifest: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized)
    os.replace(temporary, path)


def build_manifest(rays: int) -> dict:
    if rays not in RAY_COUNTS:
        raise ValueError(f"unsupported ray count: {rays}")
    source = gate0.strict_json_loads(SOURCE.read_text())
    selected = []
    for anchor in ANCHORS:
        matches = [
            copy.deepcopy(row)
            for row in source["design"]["recipes"]
            if anchor in row["anchor_reasons"]
        ]
        if len(matches) != 1:
            raise ValueError(f"expected one source recipe for {anchor}, found {len(matches)}")
        selected.extend(matches)

    campaign = f"v3-bosch-clean-ray-{rays}"
    design = copy.deepcopy(source["design"])
    design["campaign"] = campaign
    design["question"] = (
        "What is the cheapest ray count that preserves Bosch measurements, "
        "shape classes, hard gates, and the ion-rate tuning direction?"
    )
    design["evidence_class"] = "clean paired ray-count accuracy screen"
    design["numerics"]["rays_per_point"] = rays
    design["trajectory"]["early_stop_depth"] = 1.45
    design["rng_policy"].update(
        {
            "seed_start": SEED_START,
            "interval_count": len(selected),
            "assignment": "same base-seed labels reused across ray arms",
            "interpretation": (
                "paired by base seed; different ray counts consume different paths, "
                "so pointwise common random numbers are not claimed"
            ),
        }
    )
    design["recipes"] = selected
    design["design"] = {
        "method": "seven frozen morphology and interaction sentinels",
        "logical_simulation_count": len(selected),
        "ray_ladder": list(RAY_COUNTS),
        "anchors": list(ANCHORS),
    }
    design["decision_rules"] = [
        "Change ray count only; hold geometry, recipe, grid, cycle horizon, stop depth, measurements, threads, and base-seed labels fixed.",
        "Reject a candidate after any trajectory-class or hard-gate mismatch is confirmed on two sentinels.",
        "Do not infer numerical truth from the 2,000-ray arm.",
        "This study may approve a discovery setting only; boundaries and finalists remain at 2,000 rays.",
    ]
    authority = {
        "numerical_accuracy_screen_only": True,
        "discovery_profile_authorized": False,
        "recipe_authorized": False,
        "process_window_authorized": False,
    }
    design["authority"] = authority
    output = rows_path(rays)
    return {
        "manifest_version": 1,
        "methodology_epoch": "full-traveler-doe-v3",
        "campaign": campaign,
        "labels": ["numerical-accuracy", "critical-review"],
        "design": design,
        "execution": {
            "output": str(output),
            "maximum_workers": 2,
            "threads_per_worker": 7,
            "executor": "direct_checkpointed_batch_no_llm",
        },
        "runtime_fingerprint": stage2a.runtime_fingerprint(ROOT),
        "source_artifacts": {
            "stage2a_manifest": {
                "path": str(SOURCE.relative_to(ROOT)),
                "sha256": stage2a.file_sha256(SOURCE),
            }
        },
        "authority": authority,
        "provenance": {
            "purpose": "select a fast geometry-scoped Bosch discovery profile",
            "candidate_rays_per_point": rays,
            "tested_reference_rays_per_point": 2000,
            "paired_base_seed_start": SEED_START,
            "existing_artifacts_preserved": True,
        },
    }


def expand_cases(manifest: dict) -> list[dict]:
    cases = stage2a.expand_cases(manifest)
    rays = manifest["design"]["numerics"]["rays_per_point"]
    for index, case in enumerate(cases):
        case["rng_stream"].update(
            {
                "allocation_id": f"clean_ray_r{rays}_{index:02d}",
                "interval_reused": True,
                "pointwise_common_random_numbers_claimed": False,
            }
        )
        payload = stage2a.case_payload(case)
        case["case_id"] = stage2a.case_id(payload)
        case["case_payload_sha256"] = stage2a.canonical_sha256(payload)
    return cases


def validate_manifest(manifest: dict, rays: int) -> list[str]:
    errors = []
    if manifest.get("campaign") != f"v3-bosch-clean-ray-{rays}":
        errors.append("campaign differs")
    design = manifest.get("design", {})
    if design.get("numerics", {}).get("rays_per_point") != rays:
        errors.append("ray count differs")
    if design.get("trajectory", {}).get("early_stop_depth") != 1.45:
        errors.append("stop depth differs")
    if len(design.get("recipes", [])) != len(ANCHORS):
        errors.append("sentinel count differs")
    if manifest.get("execution", {}).get("output") != str(rows_path(rays)):
        errors.append("output differs")
    for declaration in manifest.get("source_artifacts", {}).values():
        path = ROOT / declaration.get("path", "")
        if not path.is_file() or stage2a.file_sha256(path) != declaration.get("sha256"):
            errors.append(f"source artifact differs: {path}")
    return errors


def run_case(task):
    case, _output = task
    rays = case["numerics"]["rays_per_point"]
    setattr(stage2a, "evidence_origin", lambda: evidence_origin(rays))
    return stage2a.run_case(task)


def completed_rows(output: Path, cases: list[dict], rays: int) -> dict:
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
            raise ValueError(f"invalid ray-ladder row {number}")
        native_checkpoint.load_domain_checkpoint(
            Path(row["checkpoint_path"]), expected_sha256=row["checkpoint_sha256"]
        )
        completed[row["case_id"]] = row
    return completed


def run_manifest(rays: int, workers: int, dry_run: bool) -> None:
    manifest = gate0.strict_json_loads(manifest_path(rays).read_text())
    errors = validate_manifest(manifest, rays)
    if errors:
        raise ValueError("invalid ray-ladder manifest: " + "; ".join(errors))
    if workers != manifest["execution"]["maximum_workers"]:
        raise ValueError("workers differ from frozen contract")
    output = ROOT / rows_path(rays)
    lock, lock_path = stage2a.acquire_campaign_lock(output, manifest["campaign"])
    try:
        cases = expand_cases(manifest)
        completed = completed_rows(output, cases, rays)
        pending = [case for case in cases if case["case_id"] not in completed]
        print(f"rays={rays} complete={len(completed)} pending={len(pending)} lock={lock_path}", flush=True)
        if dry_run or not pending:
            return
        with futures.ProcessPoolExecutor(max_workers=workers) as executor:
            jobs = {executor.submit(run_case, (case, output)): case for case in pending}
            for index, future in enumerate(futures.as_completed(jobs), 1):
                case = jobs[future]
                row = future.result()
                if not stage2a.row_matches_case(row, case) or row.get("ok") is not True:
                    raise RuntimeError(f"ray-ladder case failed: {case['case_id']}")
                gate0.append_row(output, row)
                print(f"rays={rays} [{index}/{len(pending)}] {row['case_id']} elapsed={row['elapsed_s']:.1f}s", flush=True)
    finally:
        stage2a.release_campaign_lock(lock)


def selected_rays(value: str) -> tuple[int, ...]:
    return RAY_COUNTS if value == "all" else (int(value),)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "run", "status"))
    parser.add_argument("--rays", choices=("all", *(str(value) for value in RAY_COUNTS)), default="all")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    for rays in selected_rays(args.rays):
        if args.action == "build":
            manifest = build_manifest(rays)
            freeze(manifest_path(rays), manifest)
            print(json.dumps({"campaign": manifest["campaign"], "rays": rays, "cases": len(ANCHORS)}, sort_keys=True))
        else:
            run_manifest(rays, args.workers, args.action == "status")


if __name__ == "__main__":
    main()

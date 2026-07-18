"""Run fresh paired 250/500-ray Bosch triage cases."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import time
import traceback

import numpy as np
import viennals._core as ls_core
import viennaps as ps
import viennaps._core as ps_core

import foundation_metric_audit as foundation
from scripts.autoresearch_event_log import append_event, validate_log
import traveler_metrics as tm
import tsv_process as tp


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "evidence/numerical/bosch_ray_phase_a_manifest.json"
OUTPUT = ROOT / "autoresearch-results/restart_audit/bosch_ray_phase_a_events.jsonl"
REVIEW = ROOT / "evidence/numerical/bosch_ray_phase_a_review.json"
CHECKPOINTS = OUTPUT.parent / "bosch_ray_phase_a_checkpoints"
PILOT = ROOT / "pattern_bosch_range_pilot_design.json"
INTERACTIONS = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_rows.jsonl"
CONTRACT = ROOT / "pattern_bosch_measurement_contract.json"
PREFLIGHT = ROOT / "evidence/numerical/bosch_grid_preflight.json"
RAY_ARMS = (250, 500)
SEED_START = 1_610_000
SEED_STRIDE = 91


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)


def case_id(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()[:16]


def interaction_row(source_case_id: str) -> tuple[dict, int]:
    for line_number, line in enumerate(INTERACTIONS.read_text().splitlines(), 1):
        row = json.loads(line)
        if row["case_id"] == source_case_id:
            return row, line_number
    raise ValueError(f"interaction row not found: {source_case_id}")


def panel_recipes() -> list[dict]:
    pilot = json.loads(PILOT.read_text())
    pilot_by_id = {case["case_id"]: case for case in pilot["cases"]}
    clear, clear_line = interaction_row("7405eb159356c564")
    definitions = [
        {
            "id": "current_grid_reference",
            "roles": ["clear_assumed_band_reference", "interaction_sensitive"],
            "source": {
                "path": str(INTERACTIONS.relative_to(ROOT)),
                "line_number": clear_line,
                "case_id": clear["case_id"],
                "sha256": digest(INTERACTIONS),
            },
            "geometry": clear["geometry"],
            "recipe": clear["recipe"],
            "maximum_cycles": clear["trajectory"]["maximum_cycles"],
            "repeat_count": 1,
        },
        ("design_center", "48083e578a008900", ["design_center"], 3),
        ("narrow_profile", "bd5b486f6fb67256", ["narrow_valid_profile"], 3),
        ("low_movement_wide", "4405fc56d8e10409", ["low_movement"], 3),
        ("low_movement_narrow", "f56ee9f0c5703348", ["low_movement"], 3),
        ("near_depth_adverse", "1cb56644ad10ff06", ["near_depth_adverse"], 1),
        ("near_bow_adverse", "7d8102bf6ea2fd39", ["near_bow_adverse"], 1),
        (
            "availability_challenge",
            "270ed2834457ec9c",
            ["one_sided_availability_challenge"],
            1,
        ),
    ]
    result = []
    for item in definitions:
        if isinstance(item, dict):
            result.append(item)
            continue
        panel_id, source_case_id, roles, repeat_count = item
        source = pilot_by_id[source_case_id]
        result.append({
            "id": panel_id,
            "roles": roles,
            "source": {
                "path": str(PILOT.relative_to(ROOT)),
                "selector": f"/cases/{source['design_row']}",
                "case_id": source_case_id,
                "sha256": digest(PILOT),
            },
            "geometry": {
                **pilot["geometry"],
                "radius": source["recipe"]["radius"],
                "mask_taper": source["recipe"]["mask_taper"],
            },
            "recipe": {
                **source["recipe"],
                "mask_ion_rate": pilot["held_controls"]["mask_ion_rate"],
            },
            "maximum_cycles": source["recipe"]["num_cycles"],
            "repeat_count": repeat_count,
        })
    return result


def build_manifest() -> dict:
    preflight = json.loads(PREFLIGHT.read_text())
    if preflight["selected"]["assumed_band_result"]["inside_all"] is not True:
        raise ValueError("current-grid reference preflight did not pass")
    panel = panel_recipes()
    pair_count = sum(item["repeat_count"] for item in panel)
    return {
        "schema_version": 1,
        "campaign": "bosch-ray-phase-a-v1",
        "question": (
            "Where do fresh 250- and 500-ray runs disagree when every paired run "
            "uses the same physical inputs, grid, endpoint rule, and seed label?"
        ),
        "authority": (
            "Triage 250 rays and select Phase B cases only. Phase A cannot qualify "
            "500 rays or establish engineering equivalence."
        ),
        "panel": panel,
        "numerics": {
            "grid_delta": 0.005,
            "ray_arms": list(RAY_ARMS),
            "threads_per_worker": 4,
            "maximum_workers": 2,
            "simulation_dimension": 2,
        },
        "rng_policy": {
            "seed_start": SEED_START,
            "seed_stride": SEED_STRIDE,
            "paired_by_seed_label": True,
            "pointwise_common_random_numbers_claimed": False,
            "independent_pair_count": pair_count,
        },
        "selection_rule": (
            "Complete full-width profiles inside all assumed bands rank first; "
            "then minimize absolute depth error; then choose the earlier cycle."
        ),
        "comparison_rules": {
            "availability_and_assumed_band_checks_must_match": True,
            "continuous_differences_are_reported_not_qualified": True,
            "250_rays_may_be_rejected_but_not_approved": True,
            "500_rays_requires_fresh_2000_ray_phase_b": True,
        },
        "execution": {
            "case_cap": 2 * pair_count,
            "checkpoint_policy": "save one selected-cycle checkpoint per run",
            "retry_policy": "one identical retry for a first transient infrastructure error only",
        },
        "assumed_comparison_bands": {
            "opening_cd": 0.3,
            "mask_height": 0.3,
            "etch_depth": 1.25,
            "depth_tolerance": 0.1,
            "max_width_error": 0.06,
            "max_wall_bulge": 0.03,
            "evidence_class": "assumed_model_study",
        },
        "sources": [
            {"path": Path(__file__).name, "sha256": digest(Path(__file__))},
            {"path": str(PILOT.relative_to(ROOT)), "sha256": digest(PILOT)},
            {"path": str(INTERACTIONS.relative_to(ROOT)), "sha256": digest(INTERACTIONS)},
            {"path": str(CONTRACT.relative_to(ROOT)), "sha256": digest(CONTRACT)},
            {"path": str(PREFLIGHT.relative_to(ROOT)), "sha256": digest(PREFLIGHT)},
            {"path": "traveler_metrics.py", "sha256": digest(ROOT / "traveler_metrics.py")},
            {"path": "tsv_process.py", "sha256": digest(ROOT / "tsv_process.py")},
        ],
    }


def freeze_manifest() -> None:
    document = build_manifest()
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if MANIFEST.exists() and MANIFEST.read_text() != text:
        raise ValueError(f"refusing to overwrite different manifest: {MANIFEST}")
    MANIFEST.write_text(text)
    print(json.dumps({"manifest": str(MANIFEST.relative_to(ROOT)), "runs": document["execution"]["case_cap"]}, sort_keys=True))


def expand_cases(manifest: dict) -> list[dict]:
    cases = []
    pair_index = 0
    for panel in manifest["panel"]:
        for repeat_index in range(panel["repeat_count"]):
            seed = manifest["rng_policy"]["seed_start"] + pair_index * manifest["rng_policy"]["seed_stride"]
            pair_id = f"{panel['id']}:stream_{repeat_index + 1}"
            arm_order = RAY_ARMS if pair_index % 2 == 0 else tuple(reversed(RAY_ARMS))
            for rays in arm_order:
                payload = {
                    "campaign": manifest["campaign"],
                    "panel_id": panel["id"],
                    "roles": panel["roles"],
                    "pair_id": pair_id,
                    "repeat_index": repeat_index,
                    "geometry": panel["geometry"],
                    "recipe": panel["recipe"],
                    "maximum_cycles": panel["maximum_cycles"],
                    "grid_delta": manifest["numerics"]["grid_delta"],
                    "rays_per_point": rays,
                    "rng_seed": seed,
                }
                cases.append({**payload, "case_id": case_id(payload)})
            pair_index += 1
    return cases


def mesh_for(meshes: list[dict], material, *, required: bool = True):
    matches = [mesh for mesh in meshes if mesh["material"] == material and len(mesh["nodes"])]
    if not matches and not required:
        return None
    if len(matches) != 1:
        raise ValueError(f"expected one mesh for material {material}")
    return matches[0]


def band_result(metrics: dict, target: dict) -> dict:
    checks = {
        "depth": abs(metrics["depth"] - target["etch_depth"]) <= target["depth_tolerance"],
        "width": metrics["max_cd_error"] <= target["max_width_error"],
        "bow": metrics["max_bow"] <= target["max_wall_bulge"],
    }
    return {"checks": checks, "inside_all": all(checks.values())}


def environment() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "runner_sha256": digest(Path(__file__)),
        "traveler_metrics_sha256": digest(ROOT / "traveler_metrics.py"),
        "tsv_process_sha256": digest(ROOT / "tsv_process.py"),
        "viennaps_binary_sha256": digest(Path(ps_core.__file__)),
        "viennals_binary_sha256": digest(Path(ls_core.__file__)),
    }


def event_base(
    case: dict, manifest: dict, manifest_hash: str, env: dict, attempt: int
) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest_id": manifest["campaign"],
        "manifest_version": manifest["schema_version"],
        "manifest_hash": manifest_hash,
        "case_key": case["case_id"],
        "case_payload_hash": hashlib.sha256(canonical(case).encode()).hexdigest(),
        "stage": "bosch_ray_phase_a",
        "attempt": attempt,
        "retry_count": attempt - 1,
        "inputs": {key: value for key, value in case.items() if key != "case_id"},
        "environment": env,
        "numerical_profile": {
            "grid_delta": case["grid_delta"],
            "rays_per_point": case["rays_per_point"],
            "threads_per_worker": manifest["numerics"]["threads_per_worker"],
            "status": "under_comparison",
        },
    }


def measure_pattern(mask: dict, target: dict) -> dict:
    return tm.pattern_metrics_2d(
        mask["nodes"], mask["lines"], surface_y=0.0,
        target_cd=target["opening_cd"], target_mask_height=target["mask_height"],
        max_radius=target["opening_cd"],
    )


def measurement_payload(pattern: dict, selected: dict) -> dict:
    return {
        "availability": selected["availability"],
        "reason_codes": selected["reason_codes"],
        "selected_cycle": selected["cycle"],
        "assumed_band_result": selected["assumed_band_result"],
        "minimum_width_cells": selected["minimum_width_cells"],
        "maximum_center_shift": (
            selected["metrics"].get("maximum_center_shift") if selected["metrics"] else None
        ),
        "mask": pattern,
        "etch": selected["metrics"],
    }


def run_case(task: tuple[dict, dict, str, dict, int]) -> dict:
    case, manifest, manifest_hash, env, attempt = task
    base = event_base(case, manifest, manifest_hash, env, attempt)
    started = time.monotonic()
    try:
        ps.Logger.setLogLevel(ps.LogLevel.ERROR)
        ps.setDimension(2)
        ps.setNumThreads(manifest["numerics"]["threads_per_worker"])
        geometry_spec = case["geometry"]
        recipe = case["recipe"]
        target = manifest["assumed_comparison_bands"]
        geometry = tp.make_initial_geometry(
            radius=geometry_spec["radius"], mask_height=geometry_spec["mask_height"],
            grid_delta=case["grid_delta"], x_extent=geometry_spec["x_extent"],
            y_extent=geometry_spec["y_extent"], taper=geometry_spec["mask_taper"],
            hole_shape=ps.HoleShape.FULL,
        )
        initial_mask = mesh_for(tm.raw_level_set_meshes(geometry), ps.Material.Mask)
        pattern = measure_pattern(initial_mask, target)
        selected = None

        def capture(current, cycle):
            nonlocal selected
            meshes = tm.raw_level_set_meshes(current)
            silicon = mesh_for(meshes, ps.Material.Si)
            mask = mesh_for(meshes, ps.Material.Mask, required=False)
            measured = tm.measure_full_via_profile_2d(
                silicon["nodes"], silicon["lines"], surface_y=0.0,
                target_cd=target["opening_cd"],
                domain_x_bounds=(-0.5 * geometry_spec["x_extent"], 0.5 * geometry_spec["x_extent"]),
                grid_delta=case["grid_delta"],
            )
            comparison = band_result(measured["metrics"], target) if measured["metrics"] else None
            record = {
                "cycle": int(cycle), "availability": measured["state"],
                "reason_codes": measured["reason_codes"], "metrics": measured["metrics"],
                "minimum_width_cells": measured["diagnostics"].get("minimum_width_cells"),
                "mask_remaining_height": float(np.max(mask["nodes"][:, 1])) if mask is not None else 0.0,
                "assumed_band_result": comparison,
            }
            rank = (
                0 if comparison and comparison["inside_all"] else 1,
                abs(measured["metrics"]["depth"] - target["etch_depth"])
                if measured["metrics"] else math.inf,
                int(cycle),
            )
            if selected is None or rank < selected["rank"]:
                selected = {
                    "rank": rank, "record": record,
                    "silicon_nodes": np.asarray(silicon["nodes"]),
                    "silicon_lines": np.asarray(silicon["lines"]),
                    "mask_nodes": np.asarray(mask["nodes"]) if mask is not None else np.empty((0, 3)),
                    "mask_lines": np.asarray(mask["lines"]) if mask is not None else np.empty((0, 2), dtype=int),
                }

        tp.bosch_etch(
            geometry, num_cycles=case["maximum_cycles"], etch_time=recipe["etch_time"],
            initial_etch_time=recipe["initial_etch_time"],
            ion_source_exponent=recipe["ion_source_exponent"],
            neutral_sticking_probability=recipe["neutral_sticking_probability"],
            deposition_thickness=recipe["deposition_thickness"],
            deposition_sticking_probability=recipe["deposition_sticking_probability"],
            neutral_rate=recipe["neutral_rate"], ion_rate=recipe["ion_rate"],
            radius=geometry_spec["radius"], theta_r_min=recipe["theta_r_min"],
            rays_per_point=case["rays_per_point"], rng_seed=case["rng_seed"],
            mask_ion_rate=recipe["mask_ion_rate"], on_cycle=capture,
        )
        if selected is None:
            raise ValueError("no cycle was captured")
        CHECKPOINTS.mkdir(parents=True, exist_ok=True)
        checkpoint = CHECKPOINTS / f"{case['case_id']}_cycle{selected['record']['cycle']:03d}.npz"
        checkpoint_sha = foundation.save_npz_atomic(
            checkpoint, manifest_sha256=np.asarray(manifest_hash),
            case_payload_sha256=np.asarray(base["case_payload_hash"]),
            selected_cycle=np.asarray(selected["record"]["cycle"]),
            silicon_nodes=selected["silicon_nodes"], silicon_lines=selected["silicon_lines"],
            mask_nodes=selected["mask_nodes"], mask_lines=selected["mask_lines"],
        )
        return {
            **base, "state": "complete_measured", "retryable": False,
            "elapsed_s": time.monotonic() - started,
            "measurements": measurement_payload(pattern, selected["record"]),
            "metrics_valid": True,
            "hard_gate_pass": None, "numerical_state": "not_checked",
            "failure_scope": None, "unresolved_reasons": [], "error": None,
            "checkpoint": {"path": str(checkpoint.relative_to(ROOT)), "sha256": checkpoint_sha},
            "decision": "continue_search", "next_action": "Complete both ray arms and review paired differences.",
            "stop_reason": None,
        }
    except (TimeoutError, OSError) as error:
        retryable = attempt == 1
        return {
            **base, "state": "failed_transient", "retryable": retryable,
            "elapsed_s": time.monotonic() - started, "measurements": None,
            "metrics_valid": None, "hard_gate_pass": None, "numerical_state": "not_checked",
            "failure_scope": "infrastructure", "unresolved_reasons": [],
            "error": {"type": type(error).__name__, "message": str(error)}, "checkpoint": None,
            "decision": "retry_same_case" if retryable else "investigate",
            "next_action": (
                "Retry once with the identical payload."
                if retryable
                else "Inspect the repeated infrastructure failure."
            ),
            "stop_reason": None,
        }
    except Exception as error:
        return {
            **base, "state": "failed_deterministic", "retryable": False,
            "elapsed_s": time.monotonic() - started, "measurements": None,
            "metrics_valid": None, "hard_gate_pass": None, "numerical_state": "failed",
            "failure_scope": "geometry", "unresolved_reasons": [traceback.format_exc(limit=8)],
            "error": {"type": type(error).__name__, "message": str(error)}, "checkpoint": None,
            "decision": "reproduce_minimal", "next_action": "Preserve the row and inspect the smallest reproducer.",
            "stop_reason": None,
        }


def latest_events(manifest: dict, manifest_hash: str) -> dict[str, dict]:
    if not OUTPUT.exists():
        return {}
    errors, rows = validate_log(OUTPUT)
    if errors:
        raise ValueError("invalid event log: " + "; ".join(errors))
    expected = {case["case_id"]: case for case in expand_cases(manifest)}
    latest = {}
    for line_number, row in rows:
        case = expected.get(row["case_key"])
        if case is None or row["manifest_hash"] != manifest_hash:
            raise ValueError(f"stale or unexpected event at line {line_number}")
        if row["case_payload_hash"] != hashlib.sha256(canonical(case).encode()).hexdigest():
            raise ValueError(f"case payload differs at line {line_number}")
        latest[row["case_key"]] = row
    return latest


def run(max_cases: int | None) -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest != build_manifest():
        raise ValueError("manifest differs from builder or cited sources")
    manifest_hash = digest(MANIFEST)
    cases = expand_cases(manifest)
    latest = latest_events(manifest, manifest_hash)
    pending_all = [
        (
            case,
            2
            if case["case_id"] in latest and latest[case["case_id"]]["retryable"]
            else 1,
        )
        for case in cases
        if case["case_id"] not in latest or latest[case["case_id"]]["retryable"]
    ]
    pending = pending_all
    if max_cases is not None:
        pending = pending[:max_cases]
    print(
        f"planned={len(cases)} complete={len(cases)-len(pending_all)} "
        f"pending={len(pending_all)} selected={len(pending)}",
        flush=True,
    )
    env = environment()
    with futures.ProcessPoolExecutor(max_workers=manifest["numerics"]["maximum_workers"]) as executor:
        jobs = {
            executor.submit(run_case, (case, manifest, manifest_hash, env, attempt)): case
            for case, attempt in pending
        }
        for index, future in enumerate(futures.as_completed(jobs), 1):
            event = future.result()
            append_event(OUTPUT, event)
            print(f"[{index}/{len(pending)}] {event['case_key']} rays={event['numerical_profile']['rays_per_point']} state={event['state']} elapsed={event['elapsed_s']:.1f}s", flush=True)
    errors, rows = validate_log(OUTPUT)
    if errors:
        raise ValueError("event log failed validation: " + "; ".join(errors))
    print(f"validated_events={len(rows)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "run", "status"))
    parser.add_argument("--max-cases", type=int)
    args = parser.parse_args()
    if args.action == "build":
        freeze_manifest()
        return
    manifest = json.loads(MANIFEST.read_text())
    if args.action == "run":
        run(args.max_cases)
    else:
        cases = expand_cases(manifest)
        latest = latest_events(manifest, digest(MANIFEST))
        print(json.dumps({"planned": len(cases), "terminal": len(latest), "pending": len(cases) - len(latest)}, sort_keys=True))


if __name__ == "__main__":
    main()

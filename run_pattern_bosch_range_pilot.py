"""Run the frozen 25-case mask/Bosch range pilot."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import time
import traceback

from jsonschema import Draft202012Validator
import numpy as np
import viennals._core as ls_core
import viennaps as ps
import viennaps._core as ps_core

import build_pattern_bosch_range_pilot as design_builder
import foundation_metric_audit as foundation
import foundation_pattern_bosch_gate0 as gate0
from scripts.autoresearch_event_log import append_event, validate_log
import traveler_metrics as tm
import tsv_process as tp


ps.Logger.setLogLevel(ps.LogLevel.ERROR)

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "pattern_bosch_range_pilot_design.json"
SCHEMA = ROOT / "schemas/pattern-bosch-range-pilot.schema.json"
MEASUREMENT_CONTRACT = ROOT / "pattern_bosch_measurement_contract.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode()


def _strict_load(path: Path) -> dict:
    return json.loads(
        path.read_text(),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant {value}")
        ),
    )


def _environment() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "runner_sha256": _sha256(Path(__file__)),
        "tsv_process_sha256": _sha256(ROOT / "tsv_process.py"),
        "traveler_metrics_sha256": _sha256(ROOT / "traveler_metrics.py"),
        "viennaps_binary_sha256": _sha256(Path(ps_core.__file__)),
        "viennals_binary_sha256": _sha256(Path(ls_core.__file__)),
    }


def _mesh(meshes: list[dict], material, *, required: bool = True):
    matches = [
        item
        for item in meshes
        if item["material"] == material and len(item["nodes"])
    ]
    if not matches and not required:
        return None
    if len(matches) != 1:
        raise ValueError(f"expected one resolved mesh for material {material}")
    return matches[0]


def _checkpoint_path(output: Path, case: dict) -> Path:
    return output.parent / f"{output.stem}_checkpoints" / (
        f"{case['case_id']}_cycle{case['recipe']['num_cycles']:03d}.npz"
    )


def _save_checkpoint(
    path: Path,
    *,
    manifest_hash: str,
    case: dict,
    initial_mask: dict,
    silicon: dict,
    mask: dict | None,
) -> str:
    empty_nodes = np.empty((0, 3), dtype=float)
    empty_lines = np.empty((0, 2), dtype=int)
    return foundation.save_npz_atomic(
        path,
        schema_version=np.asarray(1, dtype=int),
        manifest_sha256=np.asarray(manifest_hash),
        case_id=np.asarray(case["case_id"]),
        case_payload_sha256=np.asarray(hashlib.sha256(_canonical(case)).hexdigest()),
        final_completed_cycle=np.asarray(case["recipe"]["num_cycles"], dtype=int),
        grid_delta=np.asarray(case["numerics"]["grid_delta"], dtype=float),
        rays_per_point=np.asarray(case["numerics"]["rays_per_point"], dtype=int),
        rng_seed=np.asarray(case["rng_seed"], dtype=int),
        initial_mask_nodes=np.asarray(initial_mask["nodes"], dtype=float),
        initial_mask_lines=np.asarray(initial_mask["lines"], dtype=int),
        silicon_nodes=np.asarray(silicon["nodes"], dtype=float),
        silicon_lines=np.asarray(silicon["lines"], dtype=int),
        mask_nodes=(
            np.asarray(mask["nodes"], dtype=float) if mask is not None else empty_nodes
        ),
        mask_lines=(
            np.asarray(mask["lines"], dtype=int) if mask is not None else empty_lines
        ),
    )


def _measurements(
    initial_pattern: dict,
    final_metrics: dict,
    measurement_contract: dict,
) -> tuple[dict, list[str]]:
    sources = {
        "mask": initial_pattern,
        "bosch_etch": final_metrics["etch"],
    }
    measured = {}
    missing = []
    for metric in measurement_contract["metrics"]:
        metric_id = metric["id"]
        output_key = metric["extractor"]["output_key"]
        value = sources[metric["step"]].get(output_key)
        if isinstance(value, (np.integer, np.floating)):
            value = value.item()
        if isinstance(value, float) and not math.isfinite(value):
            value = None
        if value is None:
            missing.append(metric_id)
        measured[metric_id] = {
            "value": value,
            "units": metric["units"],
            "region": metric["region"],
            "output_key": output_key,
            "qualification_status": metric["qualification_status"],
        }
    measured["post_etch_mask_remaining_height"] = {
        "value": final_metrics["mask_remaining_height"],
        "units": "model length",
        "qualification_status": "observation_only",
    }
    return measured, missing


def _event_base(
    manifest: dict,
    manifest_hash: str,
    case: dict,
    environment: dict,
    *,
    attempt: int,
) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest_id": manifest["campaign"],
        "manifest_version": manifest["schema_version"],
        "manifest_hash": manifest_hash,
        "case_key": case["case_id"],
        "case_payload_hash": hashlib.sha256(_canonical(case)).hexdigest(),
        "stage": "mask_and_bosch_range_pilot",
        "attempt": attempt,
        "retry_count": attempt - 1,
        "inputs": {
            "design_row": case["design_row"],
            "coded_levels": case["coded_levels"],
            "recipe": case["recipe"],
            "derived_exposures": case["derived_exposures"],
            "rng_policy": manifest["rng_policy"],
            "inference_policy": manifest["inference_policy"],
        },
        "environment": environment,
        "numerical_profile": {
            **case["numerics"],
            "status": manifest["numerics"]["status"],
            "threads_per_worker": manifest["numerics"]["threads_per_worker"],
        },
    }


def run_case(
    manifest: dict,
    manifest_hash: str,
    case: dict,
    output: Path,
    measurement_contract: dict,
    environment: dict,
    *,
    attempt: int,
) -> dict:
    base = _event_base(
        manifest, manifest_hash, case, environment, attempt=attempt
    )
    started = time.monotonic()
    checkpoint = None
    try:
        ps.setNumThreads(int(manifest["numerics"]["threads_per_worker"]))
        recipe = case["recipe"]
        geometry = tp.make_initial_geometry(
            radius=recipe["radius"],
            mask_height=manifest["geometry"]["mask_height"],
            grid_delta=case["numerics"]["grid_delta"],
            x_extent=manifest["geometry"]["x_extent"],
            y_extent=manifest["geometry"]["y_extent"],
            taper=recipe["mask_taper"],
            hole_shape=ps.HoleShape.FULL,
        )
        initial_mask = _mesh(tm.raw_level_set_meshes(geometry), ps.Material.Mask)
        measurement_case = {"target": manifest["comparison_context"]}
        initial_pattern = gate0.measure_pattern(initial_mask, measurement_case)
        captured = []

        def capture_final(current, cycle):
            if int(cycle) != int(recipe["num_cycles"]):
                return
            if captured:
                raise ValueError("final completed cycle captured more than once")
            meshes = tm.raw_level_set_meshes(current)
            silicon = _mesh(meshes, ps.Material.Si)
            mask = _mesh(meshes, ps.Material.Mask, required=False)
            final_metrics = gate0.measure_selected_cycle(
                silicon, mask, measurement_case
            )
            path = _checkpoint_path(output, case)
            digest = _save_checkpoint(
                path,
                manifest_hash=manifest_hash,
                case=case,
                initial_mask=initial_mask,
                silicon=silicon,
                mask=mask,
            )
            captured.append((final_metrics, path, digest))

        tp.bosch_etch(
            geometry,
            num_cycles=recipe["num_cycles"],
            etch_time=recipe["etch_time"],
            initial_etch_time=recipe["initial_etch_time"],
            ion_source_exponent=recipe["ion_source_exponent"],
            neutral_sticking_probability=recipe["neutral_sticking_probability"],
            deposition_thickness=recipe["deposition_thickness"],
            deposition_sticking_probability=recipe[
                "deposition_sticking_probability"
            ],
            neutral_rate=recipe["neutral_rate"],
            ion_rate=recipe["ion_rate"],
            radius=recipe["radius"],
            theta_r_min=recipe["theta_r_min"],
            rays_per_point=case["numerics"]["rays_per_point"],
            rng_seed=case["rng_seed"],
            mask_ion_rate=0.0,
            on_cycle=capture_final,
        )
        if len(captured) != 1:
            raise ValueError("final completed cycle was not captured exactly once")
        final_metrics, path, digest = captured[0]
        checkpoint = {
            "path": str(path.relative_to(ROOT)),
            "sha256": digest,
            "final_completed_cycle": recipe["num_cycles"],
        }
        measurements, missing = _measurements(
            initial_pattern, final_metrics, measurement_contract
        )
        elapsed = time.monotonic() - started
        if missing:
            return {
                **base,
                "state": "missing_measurement",
                "retryable": False,
                "elapsed_s": elapsed,
                "measurements": measurements,
                "metrics_valid": False,
                "hard_gate_pass": None,
                "numerical_state": "not_checked",
                "failure_scope": "metric",
                "unresolved_reasons": [
                    "missing required metrics: " + ", ".join(missing)
                ],
                "error": None,
                "checkpoint": checkpoint,
                "decision": "repair_measurement",
                "next_action": "Inspect the checkpoint and extractor before interpretation.",
                "stop_reason": None,
            }
        return {
            **base,
            "state": "complete_measured",
            "retryable": False,
            "elapsed_s": elapsed,
            "measurements": measurements,
            "metrics_valid": True,
            "hard_gate_pass": True,
            "numerical_state": "screening_only",
            "failure_scope": None,
            "unresolved_reasons": [
                "single shared seed label; no repeat uncertainty",
                "0.01 grid and 250 rays are not numerically qualified",
            ],
            "error": None,
            "checkpoint": checkpoint,
            "decision": "continue_search",
            "next_action": "Retain the raw observation and finish the bounded pilot.",
            "stop_reason": None,
        }
    except (TimeoutError, OSError) as error:
        retryable = attempt == 1
        return {
            **base,
            "state": "failed_transient",
            "retryable": retryable,
            "elapsed_s": time.monotonic() - started,
            "measurements": None,
            "metrics_valid": None,
            "hard_gate_pass": None,
            "numerical_state": "not_checked",
            "failure_scope": "infrastructure",
            "unresolved_reasons": [],
            "error": {"type": type(error).__name__, "message": str(error)},
            "checkpoint": checkpoint,
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
            **base,
            "state": "failed_deterministic",
            "retryable": False,
            "elapsed_s": time.monotonic() - started,
            "measurements": None,
            "metrics_valid": None,
            "hard_gate_pass": None,
            "numerical_state": "failed",
            "failure_scope": "geometry",
            "unresolved_reasons": [
                "deterministic execution or geometry failure",
                traceback.format_exc(limit=8),
            ],
            "error": {"type": type(error).__name__, "message": str(error)},
            "checkpoint": checkpoint,
            "decision": "reproduce_minimal",
            "next_action": "Preserve the row and inspect the smallest reproducer.",
            "stop_reason": None,
        }


def validate_manifest(manifest: dict) -> list[str]:
    errors = [
        error.message
        for error in Draft202012Validator(_strict_load(SCHEMA)).iter_errors(manifest)
    ]
    if manifest != design_builder.build():
        errors.append("manifest differs from the current deterministic builder")
    measurement_ids = {
        metric["id"] for metric in _strict_load(MEASUREMENT_CONTRACT)["metrics"]
    }
    if set(manifest.get("required_measurements", [])) != measurement_ids:
        errors.append("required measurements differ from the canonical contract")
    return errors


def _latest_events(
    output: Path,
    manifest: dict,
    manifest_hash: str,
) -> dict[str, dict]:
    if not output.exists():
        return {}
    errors, rows = validate_log(output)
    if errors:
        raise ValueError("invalid existing event log: " + "; ".join(errors))
    cases = {case["case_id"]: case for case in manifest["cases"]}
    latest = {}
    for line_number, row in rows:
        case = cases.get(row.get("case_key"))
        if case is None:
            raise ValueError(f"unexpected case at event line {line_number}")
        expected_case_hash = hashlib.sha256(_canonical(case)).hexdigest()
        if row.get("manifest_hash") != manifest_hash:
            raise ValueError(f"stale manifest hash at event line {line_number}")
        if row.get("case_payload_hash") != expected_case_hash:
            raise ValueError(f"stale case payload at event line {line_number}")
        latest[row["case_key"]] = row
    return latest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-cases", type=int, default=25)
    args = parser.parse_args()

    manifest = _strict_load(args.manifest)
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid range-pilot manifest: " + "; ".join(errors))
    output = ROOT / manifest["output"] if args.output is None else args.output
    if args.max_cases < 1 or args.max_cases > manifest["execution"]["case_cap"]:
        raise ValueError("max-cases must be between 1 and the frozen case cap")

    manifest_hash = _sha256(args.manifest)
    environment = _environment()
    measurement_contract = _strict_load(MEASUREMENT_CONTRACT)
    latest = _latest_events(output, manifest, manifest_hash)
    pending_all = []
    for case in manifest["cases"]:
        previous = latest.get(case["case_id"])
        if previous is None or previous.get("retryable") is True:
            pending_all.append(case)
    pending = pending_all[: args.max_cases]
    print(
        f"planned=25 completed={25 - len(pending_all)} "
        f"pending={len(pending_all)} selected={len(pending)} "
        "authority=raw_observations_only",
        flush=True,
    )

    for index, case in enumerate(pending, 1):
        previous = latest.get(case["case_id"])
        attempt = 2 if previous and previous.get("retryable") else 1
        event = run_case(
            manifest,
            manifest_hash,
            case,
            output,
            measurement_contract,
            environment,
            attempt=attempt,
        )
        append_event(output, event)
        print(
            f"[{index}/{len(pending)}] {case['case_id']} "
            f"state={event['state']} elapsed={event['elapsed_s']:.1f}s",
            flush=True,
        )

    errors, rows = validate_log(output)
    if errors:
        raise ValueError("event log failed final validation: " + "; ".join(errors))
    print(f"validated_events={len(rows)} output={output}", flush=True)


if __name__ == "__main__":
    main()

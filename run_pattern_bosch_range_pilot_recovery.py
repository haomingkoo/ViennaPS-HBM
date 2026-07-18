"""Recover final geometry and measurement state for seven pilot cases."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time
import traceback

import numpy as np
import viennaps as ps

import foundation_pattern_bosch_gate0 as gate0
import run_pattern_bosch_range_pilot as base
from scripts.autoresearch_event_log import append_event, validate_log
import traveler_metrics as tm
import tsv_process as tp


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "pattern_bosch_range_pilot_recovery_design.json"


def _measurement_values(
    initial_pattern: dict,
    final_metrics: dict,
    contract: dict,
) -> tuple[dict, list[str]]:
    values, missing = base._measurements(initial_pattern, final_metrics, contract)
    return values, missing


def run_case(
    manifest: dict,
    manifest_hash: str,
    case: dict,
    output: Path,
    contract: dict,
    environment: dict,
) -> dict:
    event = base._event_base(
        manifest, manifest_hash, case, environment, attempt=1
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
        initial_mask = base._mesh(
            tm.raw_level_set_meshes(geometry), ps.Material.Mask
        )
        measurement_case = {"target": manifest["comparison_context"]}
        initial_pattern = gate0.measure_pattern(initial_mask, measurement_case)
        captured = []

        def capture_final(current, cycle):
            if int(cycle) != int(recipe["num_cycles"]):
                return
            if captured:
                raise ValueError("final completed cycle captured more than once")
            meshes = tm.raw_level_set_meshes(current)
            silicon = base._mesh(meshes, ps.Material.Si)
            mask = base._mesh(meshes, ps.Material.Mask, required=False)
            path = base._checkpoint_path(output, case)
            digest = base._save_checkpoint(
                path,
                manifest_hash=manifest_hash,
                case=case,
                initial_mask=initial_mask,
                silicon=silicon,
                mask=mask,
            )
            final_metrics = None
            measurement_error = None
            try:
                final_metrics = gate0.measure_selected_cycle(
                    silicon, mask, measurement_case
                )
            except Exception as error:
                measurement_error = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            captured.append({
                "metrics": final_metrics,
                "measurement_error": measurement_error,
                "path": path,
                "sha256": digest,
            })

        movement_guard = None
        try:
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
        except RuntimeError as error:
            if captured and str(error).startswith("etch barely moved"):
                movement_guard = str(error)
            else:
                raise
        if len(captured) != 1:
            raise ValueError("final completed cycle was not captured exactly once")

        captured_state = captured[0]
        checkpoint = {
            "path": str(captured_state["path"].relative_to(ROOT)),
            "sha256": captured_state["sha256"],
            "final_completed_cycle": recipe["num_cycles"],
        }
        elapsed = time.monotonic() - started
        if captured_state["measurement_error"] is not None:
            error = captured_state["measurement_error"]
            return {
                **event,
                "state": "missing_measurement",
                "retryable": False,
                "elapsed_s": elapsed,
                "measurements": None,
                "metrics_valid": False,
                "hard_gate_pass": None,
                "numerical_state": "not_checked",
                "failure_scope": "metric",
                "unresolved_reasons": [
                    "final geometry saved before the wall-intersection extractor failed",
                    "geometry, sampling region, grid resolution, and extractor assumptions remain unresolved",
                ],
                "error": error,
                "checkpoint": checkpoint,
                "decision": "repair_measurement",
                "next_action": "Inspect the saved final geometry before changing the factor range.",
                "stop_reason": None,
            }

        measurements, missing = _measurement_values(
            initial_pattern, captured_state["metrics"], contract
        )
        if missing:
            raise ValueError("unexpected missing metrics: " + ", ".join(missing))
        measurements["pilot_observation"] = {
            "value": "low_movement_guard" if movement_guard else "measured",
            "guard_message": movement_guard,
        }
        return {
            **event,
            "state": "complete_measured",
            "retryable": False,
            "elapsed_s": elapsed,
            "measurements": measurements,
            "metrics_valid": True,
            "hard_gate_pass": None,
            "numerical_state": "not_checked",
            "failure_scope": None,
            "unresolved_reasons": [
                "measurement returned but the coarse numerical profile remains unqualified"
            ],
            "error": None,
            "checkpoint": checkpoint,
            "decision": "investigate" if movement_guard else "continue_search",
            "next_action": (
                "Retain the measurable low-movement state for paired confirmation."
                if movement_guard
                else "Retain the raw observation for confirmation selection."
            ),
            "stop_reason": None,
        }
    except Exception as error:
        return {
            **event,
            "state": "failed_deterministic",
            "retryable": False,
            "elapsed_s": time.monotonic() - started,
            "measurements": None,
            "metrics_valid": None,
            "hard_gate_pass": None,
            "numerical_state": "failed",
            "failure_scope": "numerical",
            "unresolved_reasons": [traceback.format_exc(limit=8)],
            "error": {"type": type(error).__name__, "message": str(error)},
            "checkpoint": checkpoint,
            "decision": "reproduce_minimal",
            "next_action": "Inspect the recovery-run failure without changing the parent ledger.",
            "stop_reason": None,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    manifest = base._strict_load(args.manifest)
    output = ROOT / manifest["output"]
    if output.exists():
        errors, rows = validate_log(output)
        if errors:
            raise ValueError("invalid recovery log: " + "; ".join(errors))
        if rows:
            raise ValueError("recovery log already contains events")
    manifest_hash = base._sha256(args.manifest)
    contract = base._strict_load(base.MEASUREMENT_CONTRACT)
    environment = {
        **base._environment(),
        "recovery_runner_sha256": base._sha256(Path(__file__)),
    }
    for index, case in enumerate(manifest["cases"], 1):
        event = run_case(
            manifest, manifest_hash, case, output, contract, environment
        )
        append_event(output, event)
        print(
            f"[{index}/{len(manifest['cases'])}] {case['case_id']} "
            f"state={event['state']} elapsed={event['elapsed_s']:.1f}s",
            flush=True,
        )
    errors, rows = validate_log(output)
    if errors:
        raise ValueError("recovery log failed validation: " + "; ".join(errors))
    print(f"validated_events={len(rows)} output={output}")


if __name__ == "__main__":
    main()

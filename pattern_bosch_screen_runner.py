"""Checkpointed executor for the frozen broad pattern/Bosch screen."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import math
from pathlib import Path
import time
import traceback

import numpy as np
import viennals._core as ls_core
import viennaps as ps
import viennaps._core as ps_core

import build_pattern_bosch_screen_design as design_builder
import foundation_metric_audit as foundation
import foundation_pattern_bosch_gate0 as gate0
import traveler_metrics as tm
import tsv_process as tp


ps.Logger.setLogLevel(ps.LogLevel.ERROR)

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/pattern_bosch_broad_screen_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/pattern_bosch_broad_screen_rows.jsonl"
)
CASE_FIELDS = (
    "manifest_version",
    "campaign",
    "labels",
    "recipe_id",
    "design_class",
    "anchor_reasons",
    "normalized_coordinates",
    "recipe",
    "geometry",
    "numerics",
    "trajectory",
    "target",
    "rng_seed",
    "rng_stream",
    "runtime_fingerprint",
    "source_artifacts",
    "authority",
)
CHECKPOINT_KEYS = {
    "schema_version",
    "case_id",
    "case_payload_json",
    "case_payload_sha256",
    "selected_cycle",
    "selection_eligible",
    "rng_seed",
    "grid_delta",
    "initial_mask_nodes",
    "initial_mask_lines",
    "silicon_nodes",
    "silicon_lines",
    "mask_nodes",
    "mask_lines",
}
SLIM_ETCH_KEYS = (
    "depth",
    "cd_top",
    "cd_middle",
    "cd_bottom",
    "cd_min",
    "cd_max",
    "max_cd_error",
    "sidewall_angle_deg",
    "max_bow",
    "scallop_rms",
)


class TrajectoryStop(Exception):
    """Internal control flow after the safe depth ceiling is recorded."""


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_fingerprint(project_root=ROOT):
    root = Path(project_root)
    return {
        "runner_sha256": file_sha256(root / Path(__file__).name),
        "design_builder_sha256": file_sha256(
            root / "build_pattern_bosch_screen_design.py"
        ),
        "design_spec_sha256": file_sha256(root / design_builder.DEFAULT_SPEC),
        "foundation_sha256": file_sha256(root / "foundation_metric_audit.py"),
        "gate0_runner_sha256": file_sha256(
            root / "foundation_pattern_bosch_gate0.py"
        ),
        "traveler_metrics_sha256": file_sha256(root / "traveler_metrics.py"),
        "tsv_process_sha256": file_sha256(root / "tsv_process.py"),
        "viennaps_binary_sha256": file_sha256(ps_core.__file__),
        "viennals_binary_sha256": file_sha256(ls_core.__file__),
    }


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def case_payload(case):
    return {field: case.get(field) for field in CASE_FIELDS}


def case_id(payload):
    return canonical_sha256(payload)[:16]


def sanitize(value, path="metrics", invalid=None):
    """Convert arrays and replace nonfinite numbers with visible nulls."""
    invalid = [] if invalid is None else invalid
    if isinstance(value, dict):
        return {
            key: sanitize(item, f"{path}.{key}", invalid)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, np.ndarray)):
        return [
            sanitize(item, f"{path}[{index}]", invalid)
            for index, item in enumerate(np.asarray(value, dtype=object).tolist())
        ]
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.floating, float)):
        result = float(value)
        if not math.isfinite(result):
            invalid.append(f"{path}: nonfinite")
            return None
        return result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if value is None or isinstance(value, str):
        return value
    invalid.append(f"{path}: unsupported {type(value).__name__}")
    return None


def validate_manifest(
    manifest, *, check_runtime=True, check_prerequisites=True, project_root=ROOT
):
    errors = [
        "superseded repeat-heavy screen methodology; follow RESEARCH_PLAN_V3.md"
    ]
    spec = design_builder.strict_load(Path(project_root) / design_builder.DEFAULT_SPEC)
    expected_design = design_builder.build_design(spec)
    if manifest.get("manifest_version") != 1:
        errors.append("manifest version differs")
    if manifest.get("campaign") != "pattern-bosch-broad-screen":
        errors.append("campaign name differs")
    if manifest.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("required labels differ")
    if manifest.get("design") != expected_design:
        errors.append("embedded design differs from the accepted deterministic design")
    if manifest.get("execution") != {
        "output": str(DEFAULT_OUTPUT),
        "maximum_workers": 2,
        "threads_per_worker": 7,
        "executor": "direct_checkpointed_batch_no_llm",
    }:
        errors.append("execution contract differs")
    if manifest.get("authority") != expected_design["authority"]:
        errors.append("authority differs from the design")
    fingerprint = manifest.get("runtime_fingerprint", {})
    if check_runtime and fingerprint != runtime_fingerprint(project_root):
        errors.append("runtime or source fingerprint differs")
    source_artifacts = manifest.get("source_artifacts", {})
    if set(source_artifacts) != {"gate0_summary", "handoff_summary"}:
        errors.append("prerequisite artifact declarations differ")
    elif check_prerequisites:
        for name, declaration in source_artifacts.items():
            path = Path(declaration.get("path", ""))
            path = path if path.is_absolute() else Path(project_root) / path
            if not path.is_file():
                errors.append(f"{name}: prerequisite artifact is missing")
                continue
            if declaration.get("sha256") != file_sha256(path):
                errors.append(f"{name}: prerequisite artifact hash differs")
                continue
            try:
                payload = gate0.strict_json_loads(path.read_text())
            except Exception as error:
                errors.append(f"{name}: prerequisite does not parse: {error}")
                continue
            if name == "gate0_summary" and payload.get("decision", {}).get(
                "broad_pattern_bosch_screen_authorized"
            ) is not True:
                errors.append("Gate-0 did not authorize the broad screen")
            if name == "handoff_summary" and payload.get("decision", {}).get(
                "reusable_upstream_geometry_authorized"
            ) is not True:
                errors.append("full-reference geometry handoff is not authorized")
    return errors


def expand_cases(manifest):
    design = manifest["design"]
    horizon = design["rng_process_seed_horizon"]
    cases = []
    for row in design["recipes"]:
        for seed in design["rng_base_seeds"]:
            current = {
                "manifest_version": manifest["manifest_version"],
                "campaign": manifest["campaign"],
                "labels": list(manifest["labels"]),
                "recipe_id": row["recipe_id"],
                "design_class": row["design_class"],
                "anchor_reasons": list(row["anchor_reasons"]),
                "normalized_coordinates": dict(row["normalized_coordinates"]),
                "recipe": dict(row["recipe"]),
                "geometry": dict(design["geometry"]),
                "numerics": dict(design["numerics"]),
                "trajectory": dict(design["trajectory"]),
                "target": dict(design["target"]),
                "rng_seed": seed,
                "rng_stream": {
                    "base_seed": seed,
                    "first_process_seed": seed,
                    "last_process_seed": seed + horizon - 1,
                    "process_seed_horizon": horizon,
                    "replicate_streams_disjoint": True,
                    "same_base_labels_reused_across_recipes": True,
                    "pointwise_common_random_numbers_not_claimed": True,
                },
                "runtime_fingerprint": dict(manifest["runtime_fingerprint"]),
                "source_artifacts": dict(manifest["source_artifacts"]),
                "authority": dict(manifest["authority"]),
            }
            payload = case_payload(current)
            current["case_id"] = case_id(payload)
            current["case_payload_sha256"] = canonical_sha256(payload)
            cases.append(current)
    return cases


def depth_rank(record, case):
    depth = record.get("depth")
    cycle = record.get("cycle")
    if (
        record.get("metrics_valid") is not True
        or not isinstance(depth, (int, float))
        or cycle < case["trajectory"]["first_scored_cycle"]
    ):
        return None
    target = case["target"]
    error = abs(depth - target["etch_depth"])
    in_window = error <= target["depth_tolerance"]
    return (0 if in_window else 1, error, cycle)


def select_depth_matched(history, case):
    eligible = [
        (depth_rank(record, case), record)
        for record in history
        if depth_rank(record, case) is not None
    ]
    if eligible:
        rank, record = min(eligible, key=lambda item: item[0])
        return record, True, rank
    valid = [record for record in history if record.get("metrics_valid") is True]
    if valid:
        record = min(
            valid,
            key=lambda item: (
                abs(item["depth"] - case["target"]["etch_depth"]),
                item["cycle"],
            ),
        )
        return record, False, None
    return None, False, None


def slim_cycle(cycle, measured, invalid_reasons):
    etch = measured.get("etch", {})
    return {
        "cycle": int(cycle),
        **{key: etch.get(key) for key in SLIM_ETCH_KEYS},
        "mask_remaining_height": measured.get("mask_remaining_height"),
        "post_mask_opening_valid": (
            (measured.get("post_etch_mask") or {}).get("opening_valid")
        ),
        "metrics_valid": not invalid_reasons,
        "invalid_reasons": list(invalid_reasons),
    }


def classify_gates(initial_pattern, measured, case):
    target = case["target"]
    grid_delta = case["numerics"]["grid_delta"]
    etch = measured.get("etch") or {}
    post_mask = measured.get("post_etch_mask") or {}

    def finite(name):
        value = etch.get(name)
        return isinstance(value, (int, float)) and math.isfinite(float(value))

    gates = {
        "pattern_width": bool(
            isinstance(initial_pattern.get("opening_cd_bottom"), (int, float))
            and abs(initial_pattern["opening_cd_bottom"] - target["opening_cd"])
            <= target["max_width_error"]
        ),
        "pattern_height": bool(
            isinstance(initial_pattern.get("mask_height"), (int, float))
            and abs(initial_pattern["mask_height"] - target["mask_height"])
            <= grid_delta
        ),
        "pattern_opening": initial_pattern.get("opening_valid") is True,
        "etch_depth": bool(
            finite("depth")
            and abs(etch["depth"] - target["etch_depth"])
            <= target["depth_tolerance"]
        ),
        "etch_cd_profile": bool(
            finite("max_cd_error")
            and etch["max_cd_error"] <= target["max_width_error"]
        ),
        "etch_bow": bool(
            finite("max_bow")
            and etch["max_bow"] <= target["max_wall_bulge"]
        ),
        "etch_mask_resolved": bool(
            isinstance(measured.get("mask_remaining_height"), (int, float))
            and measured["mask_remaining_height"]
            > target["resolved_mask_cells_strict"] * grid_delta
            and post_mask.get("opening_valid") is True
        ),
    }
    gates["pattern_pass"] = all(
        gates[name] for name in ("pattern_width", "pattern_height", "pattern_opening")
    )
    gates["etch_pass"] = all(
        gates[name] for name in (
            "etch_depth", "etch_cd_profile", "etch_bow", "etch_mask_resolved"
        )
    )
    return gates


def combined_hard_gate_pass(selection_eligible, gates):
    return bool(
        selection_eligible
        and gates.get("pattern_pass") is True
        and gates.get("etch_pass") is True
    )


def _mesh_for_material(geometry, material, *, required):
    meshes = [
        mesh for mesh in tm.raw_level_set_meshes(geometry)
        if mesh["material"] == material and len(mesh["nodes"])
    ]
    if not meshes:
        if required:
            raise ValueError(f"required material mesh is absent: {material}")
        return None
    if len(meshes) != 1:
        raise ValueError(f"material mesh is ambiguous: {material}")
    return meshes[0]


def checkpoint_directory(output=DEFAULT_OUTPUT):
    output = Path(output)
    return output.parent / f"{output.stem}_checkpoints"


def checkpoint_path(output, current_case_id):
    return checkpoint_directory(output) / f"{current_case_id}.npz"


def save_checkpoint(path, case, initial_mask, snapshot, selection_eligible):
    mask = snapshot.get("mask")
    empty_nodes = np.empty((0, 3), dtype=float)
    empty_lines = np.empty((0, 2), dtype=int)
    return foundation.save_npz_atomic(
        path,
        schema_version=np.asarray(1, dtype=int),
        case_id=np.asarray(case["case_id"]),
        case_payload_json=np.asarray(canonical_json(case_payload(case))),
        case_payload_sha256=np.asarray(case["case_payload_sha256"]),
        selected_cycle=np.asarray(snapshot["cycle"], dtype=int),
        selection_eligible=np.asarray(bool(selection_eligible)),
        rng_seed=np.asarray(case["rng_seed"], dtype=int),
        grid_delta=np.asarray(case["numerics"]["grid_delta"], dtype=float),
        initial_mask_nodes=np.asarray(initial_mask["nodes"], dtype=float),
        initial_mask_lines=np.asarray(initial_mask["lines"], dtype=int),
        silicon_nodes=np.asarray(snapshot["silicon"]["nodes"], dtype=float),
        silicon_lines=np.asarray(snapshot["silicon"]["lines"], dtype=int),
        mask_nodes=(np.asarray(mask["nodes"], dtype=float) if mask else empty_nodes),
        mask_lines=(np.asarray(mask["lines"], dtype=int) if mask else empty_lines),
    )


def validate_checkpoint(
    path,
    case,
    expected_sha256=None,
    *,
    expected_selected_cycle=None,
    expected_selection_eligible=None,
):
    path = Path(path)
    errors = []
    if not path.is_file():
        return ["checkpoint is missing"]
    if expected_sha256 is not None and file_sha256(path) != expected_sha256:
        errors.append("checkpoint file hash differs")
    try:
        with np.load(path, allow_pickle=False) as checkpoint:
            if set(checkpoint.files) != CHECKPOINT_KEYS:
                return errors + ["checkpoint schema keys differ"]
            if checkpoint["case_id"].item() != case["case_id"]:
                errors.append("checkpoint case ID differs")
            if checkpoint["case_payload_sha256"].item() != case[
                "case_payload_sha256"
            ]:
                errors.append("checkpoint payload hash differs")
            if checkpoint["rng_seed"].item() != case["rng_seed"]:
                errors.append("checkpoint RNG seed differs")
            if not math.isclose(
                float(checkpoint["grid_delta"].item()),
                float(case["numerics"]["grid_delta"]),
                rel_tol=0.0,
                abs_tol=1e-15,
            ):
                errors.append("checkpoint grid delta differs")
            if (
                expected_selected_cycle is not None
                and checkpoint["selected_cycle"].item()
                != expected_selected_cycle
            ):
                errors.append("checkpoint selected cycle differs from row")
            if (
                expected_selection_eligible is not None
                and bool(checkpoint["selection_eligible"].item())
                != expected_selection_eligible
            ):
                errors.append("checkpoint selection eligibility differs from row")
            payload = gate0.strict_json_loads(
                str(checkpoint["case_payload_json"].item())
            )
            if payload != case_payload(case):
                errors.append("checkpoint case payload differs")
            for prefix, required in (("initial_mask", True), ("silicon", True), ("mask", False)):
                errors.extend(gate0._mesh_errors(
                    checkpoint[f"{prefix}_nodes"],
                    checkpoint[f"{prefix}_lines"],
                    prefix.replace("_", " "),
                    required=required,
                ))
    except Exception as error:
        errors.append(f"checkpoint cannot be loaded: {error}")
    return errors


def run_case(task):
    case, output = task
    started = time.time()
    try:
        ps.setNumThreads(int(case["numerics"]["threads_per_worker"]))
        recipe = case["recipe"]
        geometry = tp.make_initial_geometry(
            radius=recipe["radius"],
            mask_height=recipe["mask_height"],
            grid_delta=case["numerics"]["grid_delta"],
            x_extent=case["geometry"]["x_extent"],
            y_extent=case["geometry"]["y_extent"],
            taper=recipe["mask_taper"],
            hole_shape=ps.HoleShape.FULL,
        )
        initial_mask = _mesh_for_material(geometry, ps.Material.Mask, required=True)
        initial_invalid = []
        initial_pattern = sanitize(
            gate0.measure_pattern(initial_mask, case),
            "initial_pattern",
            initial_invalid,
        )
        history = []
        best_snapshot = None
        best_rank = None
        fallback_snapshot = None
        fallback_rank = None

        def on_cycle(current_geometry, cycle):
            nonlocal best_snapshot, best_rank, fallback_snapshot, fallback_rank
            silicon = _mesh_for_material(
                current_geometry, ps.Material.Si, required=True
            )
            mask = _mesh_for_material(
                current_geometry, ps.Material.Mask, required=False
            )
            invalid = []
            measured = sanitize(
                gate0.measure_selected_cycle(silicon, mask, case),
                f"cycle[{cycle}]",
                invalid,
            )
            record = slim_cycle(cycle, measured, invalid)
            history.append(record)
            current_snapshot = {
                "cycle": int(cycle),
                "silicon": {
                    "nodes": np.asarray(silicon["nodes"]).copy(),
                    "lines": np.asarray(silicon["lines"]).copy(),
                },
                "mask": (
                    {
                        "nodes": np.asarray(mask["nodes"]).copy(),
                        "lines": np.asarray(mask["lines"]).copy(),
                    } if mask is not None else None
                ),
                "measured": measured,
                "invalid_reasons": invalid,
            }
            current_rank = depth_rank(record, case)
            if current_rank is not None and (
                best_rank is None or current_rank < best_rank
            ):
                best_rank = current_rank
                best_snapshot = current_snapshot
            if record["metrics_valid"] is True:
                current_fallback_rank = (
                    abs(record["depth"] - case["target"]["etch_depth"]),
                    record["cycle"],
                )
                if (
                    fallback_rank is None
                    or current_fallback_rank < fallback_rank
                ):
                    fallback_rank = current_fallback_rank
                    fallback_snapshot = current_snapshot
            if (
                isinstance(record.get("depth"), (int, float))
                and record["depth"] >= case["trajectory"]["early_stop_depth"]
            ):
                raise TrajectoryStop

        try:
            tp.bosch_etch(
                geometry,
                num_cycles=case["trajectory"]["maximum_cycles"],
                etch_time=recipe["etch_time"],
                initial_etch_time=recipe["initial_etch_time"],
                ion_source_exponent=recipe["ion_source_exponent"],
                neutral_sticking_probability=recipe[
                    "neutral_sticking_probability"
                ],
                deposition_thickness=recipe["deposition_thickness"],
                deposition_sticking_probability=recipe[
                    "deposition_sticking_probability"
                ],
                neutral_rate=recipe["neutral_rate"],
                ion_rate=recipe["ion_rate"],
                mask_ion_rate=recipe["mask_ion_rate"],
                radius=recipe["radius"],
                theta_r_min=recipe["theta_r_min"],
                rays_per_point=case["numerics"]["rays_per_point"],
                rng_seed=case["rng_seed"],
                on_cycle=on_cycle,
            )
        except TrajectoryStop:
            pass
        selected, eligible, rank = select_depth_matched(history, case)
        if selected is None:
            raise ValueError("trajectory produced no valid metric checkpoint")
        snapshot = best_snapshot if eligible else fallback_snapshot
        if snapshot is None or snapshot["cycle"] != selected["cycle"]:
            raise ValueError("retained mesh does not match depth-selected cycle")
        gates = classify_gates(initial_pattern, snapshot["measured"], case)
        path = checkpoint_path(output, case["case_id"])
        digest = save_checkpoint(
            path, case, initial_mask, snapshot, eligible
        )
        row = {
            **case,
            "ok": True,
            "initial_pattern": initial_pattern,
            "initial_pattern_invalid_reasons": initial_invalid,
            "cycle_history": history,
            "selected_cycle": selected["cycle"],
            "selection_eligible": eligible,
            "selection_rank": list(rank) if rank is not None else None,
            "selected_cycle_metrics": snapshot["measured"],
            "selected_metric_invalid_reasons": snapshot["invalid_reasons"],
            "gates": gates,
            "hard_gate_pass": combined_hard_gate_pass(eligible, gates),
            "early_stopped": bool(
                history[-1]["depth"] is not None
                and history[-1]["depth"] >= case["trajectory"]["early_stop_depth"]
            ),
            "last_recorded_cycle": history[-1]["cycle"],
            "checkpoint_path": str(path),
            "checkpoint_sha256": digest,
            "elapsed_s": time.time() - started,
        }
        canonical_json(row)
        return row
    except Exception as error:
        return {
            **case,
            "ok": False,
            "error": repr(error),
            "traceback": traceback.format_exc(),
            "elapsed_s": time.time() - started,
        }


def audit_existing_rows(output, cases):
    output = Path(output)
    if not output.is_file():
        return set()
    expected = {case["case_id"]: case for case in cases}
    success = set()
    terminal_success = set()
    for line_number, line in enumerate(output.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = gate0.strict_json_loads(line)
        except Exception as error:
            raise ValueError(f"malformed row {line_number}: {error}") from error
        current_case_id = row.get("case_id")
        if current_case_id not in expected:
            raise ValueError(f"unexpected case ID at row {line_number}")
        case = expected[current_case_id]
        if case_payload(row) != case_payload(case):
            raise ValueError(f"stale case payload at row {line_number}")
        if current_case_id in terminal_success:
            raise ValueError(f"attempt follows success at row {line_number}")
        if row.get("ok") is True:
            if row.get("case_payload_sha256") != case["case_payload_sha256"]:
                raise ValueError(f"success payload hash differs at row {line_number}")
            errors = validate_checkpoint(
                row.get("checkpoint_path", ""),
                case,
                row.get("checkpoint_sha256"),
                expected_selected_cycle=row.get("selected_cycle"),
                expected_selection_eligible=row.get("selection_eligible"),
            )
            if errors:
                raise ValueError(
                    f"invalid success checkpoint at row {line_number}: "
                    + "; ".join(errors)
                )
            success.add(current_case_id)
            terminal_success.add(current_case_id)
        elif row.get("ok") is not False:
            raise ValueError(f"row {line_number} lacks a boolean execution status")
    return success


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    manifest = gate0.strict_json_loads(args.manifest.read_text())
    manifest_errors = validate_manifest(manifest)
    if manifest_errors:
        raise ValueError("invalid frozen manifest: " + "; ".join(manifest_errors))
    if args.output != Path(manifest["execution"]["output"]):
        raise ValueError("output differs from the frozen execution contract")
    if args.workers != manifest["execution"]["maximum_workers"]:
        raise ValueError("worker count differs from the frozen execution contract")
    cases = expand_cases(manifest)
    if len(cases) != 640 or len({case["case_id"] for case in cases}) != 640:
        raise ValueError("expanded broad screen is not 640 unique cases")
    done = audit_existing_rows(args.output, cases)
    pending = [case for case in cases if case["case_id"] not in done]
    if args.limit is not None:
        pending = pending[:args.limit]
    print(
        f"logical={len(cases)} complete={len(done)} pending={len(pending)} "
        "authority=screen_only",
        flush=True,
    )
    if not pending:
        return
    tasks = [(case, args.output) for case in pending]
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for index, row in enumerate(executor.map(run_case, tasks), start=1):
            foundation.append_row(args.output, row)
            print(
                f"[{index}/{len(tasks)}] {row['case_id']} ok={row['ok']} "
                f"elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

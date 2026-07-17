"""Resumable executor for the V3 Stage 2a broad Bosch hypothesis screen."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback


os.environ["OMP_NUM_THREADS"] = "7"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import numpy as np
import viennals as ls
import viennals._core as ls_core
import viennaps as ps
import viennaps._core as ps_core

import build_v3_pattern_bosch_stage2a as builder
import foundation_metric_audit as foundation
import foundation_pattern_bosch_gate0 as gate0
import foundation_pattern_bosch_gate0_r1 as r1
import native_domain_checkpoint as native_checkpoint
import pattern_bosch_screen_runner as screen
import tsv_process as tp


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/v3_pattern_bosch_stage2a_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/v3_pattern_bosch_stage2a_rows.jsonl"
)
DEFAULT_NUMERICAL_RELEASE = Path(
    "autoresearch-results/restart_audit/v3_numerical_release.json"
)
CASE_FIELDS = (
    "manifest_version",
    "methodology_epoch",
    "campaign",
    "labels",
    "recipe_id",
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


def project_path(path, *, project_root=ROOT):
    path = Path(path)
    return path.resolve() if path.is_absolute() else (Path(project_root) / path).resolve()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def runtime_fingerprint(project_root=ROOT):
    root = Path(project_root)
    return {
        "runner_sha256": file_sha256(root / Path(__file__).name),
        "reviewer_sha256": file_sha256(root / "review_v3_pattern_bosch_stage2a.py"),
        "builder_sha256": file_sha256(root / "build_v3_pattern_bosch_stage2a.py"),
        "freezer_sha256": file_sha256(root / "freeze_v3_pattern_bosch_stage2a_manifest.py"),
        "design_spec_sha256": file_sha256(root / builder.DEFAULT_SPEC),
        "program_sha256": file_sha256(root / "program.md"),
        "research_plan_v3_sha256": file_sha256(root / "RESEARCH_PLAN_V3.md"),
        "r1_execution_kernel_sha256": file_sha256(root / "foundation_pattern_bosch_gate0_r1.py"),
        "screen_kernel_sha256": file_sha256(root / "pattern_bosch_screen_runner.py"),
        "native_checkpoint_sha256": file_sha256(root / "native_domain_checkpoint.py"),
        "gate0_metric_sha256": file_sha256(root / "foundation_pattern_bosch_gate0.py"),
        "traveler_metrics_sha256": file_sha256(root / "traveler_metrics.py"),
        "tsv_process_sha256": file_sha256(root / "tsv_process.py"),
        "python_version": sys.version,
        "python_executable": str(Path(sys.executable).resolve()),
        "python_executable_sha256": file_sha256(Path(sys.executable).resolve()),
        "numpy_version": np.__version__,
        "numpy_proxy_sha256": file_sha256(np.__file__),
        "viennaps_version": ps.__version__,
        "viennaps_proxy_sha256": file_sha256(ps.__file__),
        "viennals_proxy_sha256": file_sha256(ls.__file__),
        "viennaps_binary_sha256": file_sha256(ps_core.__file__),
        "viennals_binary_sha256": file_sha256(ls_core.__file__),
        "simulation_dimension": 2,
    }


def evidence_origin():
    return {
        "mode": "executed_v3_pattern_bosch_stage2a",
        "per_recipe_depth_matched": True,
        "native_vpsd_checkpoint": True,
        "nominal_pattern_geometry": True,
        "simulation_dimension": 2,
        "independent_rng_interval_per_recipe": True,
        "within_recipe_noise_estimated": False,
        "confirmed_factor_authority": False,
        "recipe_authority": False,
    }


def case_payload(case):
    return {field: case.get(field) for field in CASE_FIELDS}


def case_id(payload):
    return canonical_sha256(payload)[:16]


def validate_numerical_release(release, *, project_root=ROOT):
    errors = []
    if release.get("artifact") != "v3_stage0_numerical_release":
        errors.append("numerical release artifact identity differs")
    if release.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("numerical release labels differ")
    decision = release.get("decision", {})
    expected = {
        "classification": "approved_for_v3_exploratory_screening",
        "grid_delta": 0.00125,
        "rays_per_point": 2000,
        "dimension": 2,
        "rays_1000_rejected": True,
        "native_baseline_authorized": True,
        "pass": True,
        "scope": "V3 Stage 1/2 2D exploratory pattern/Bosch screening only",
    }
    for key, value in expected.items():
        if decision.get(key) != value:
            errors.append(f"numerical release {key} differs")
    expected_authority = {
        "exploratory_screening": True,
        "automatic_launch": False,
        "mask_claims": False,
        "recipe": False,
        "process_window": False,
        "full_traveler": False,
        "fab_recipe": False,
    }
    if decision.get("authority") != expected_authority:
        errors.append("numerical release authority differs")
    bridge = release.get("ray_bridge", {})
    if bridge.get("all_rows_independently_valid") is not True:
        errors.append("numerical release rows are not independently valid")
    if bridge.get("no_hard_gate_flips") is not True:
        errors.append("numerical release contains hard-gate flips")
    if bridge.get("pair_count") != 4 or len(bridge.get("pairs", [])) != 4:
        errors.append("numerical release does not contain four ray pairs")
    if bridge.get("rays_1000_passes_frozen_bridge") is not False:
        errors.append("numerical release does not reject 1,000 rays")
    expected_metrics = {
        "depth", "cd_top", "cd_middle", "cd_bottom", "max_cd_error",
        "max_bow", "scallop_rms", "mask_remaining_height",
    }
    for name in expected_metrics:
        value = (bridge.get("metric_results", {}).get(name) or {}).get(
            "observed_max_absolute_delta"
        )
        if not finite_nonnegative(value):
            errors.append(f"numerical release metric delta is invalid: {name}")
    pair_seeds = set()
    for pair in bridge.get("pairs", []):
        pair_seeds.add(pair.get("rng_seed"))
        deltas = pair.get("deltas_2000_minus_1000", {})
        if set(deltas) != expected_metrics or any(
            not finite_number(value) for value in deltas.values()
        ):
            errors.append("numerical release pair metric deltas are invalid")
        if pair.get("hard_gate_flip") is not False:
            errors.append("numerical release pair contains a hard-gate flip")
    if pair_seeds != {61000, 62000, 63000, 64000}:
        errors.append("numerical release pair seeds differ")
    native = release.get("native_baselines", {})
    shapes = native.get("shapes", [])
    if not (
        native.get("authorized") is True
        and native.get("rays_per_point") == 2000
        and native.get("shape_count") == 4
        and len(shapes) == 4
        and {row.get("rng_seed") for row in shapes} == pair_seeds
        and all(row.get("accepted") is True for row in shapes)
    ):
        errors.append("numerical release native baseline set differs")
    source_evidence = release.get("source_evidence", {})
    if set(source_evidence) != {"r1_manifest", "r1_rows", "r1_summary"}:
        errors.append("numerical release source-evidence registry differs")
    root = Path(project_root)
    for name in ("r1_manifest", "r1_rows", "r1_summary"):
        declaration = source_evidence.get(name, {})
        relative = declaration.get("path")
        digest = declaration.get("sha256")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            errors.append(f"numerical release {name} path is invalid")
            continue
        source = root / relative
        if not source.is_file():
            errors.append(f"numerical release {name} file is missing")
        elif not isinstance(digest, str) or len(digest) != 64 or digest.lower() != digest:
            errors.append(f"numerical release {name} hash is invalid")
        elif file_sha256(source) != digest:
            errors.append(f"numerical release {name} hash differs")
    return errors


def finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def finite_nonnegative(value):
    return finite_number(value) and value >= 0.0


def stochastic_baseline(release, design, *, project_root=ROOT):
    declaration = release["source_evidence"]["r1_rows"]
    path = project_path(declaration["path"], project_root=project_root)
    rows = [
        gate0.strict_json_loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    expected = {
        row["case_id"] for row in release["native_baselines"]["shapes"]
    }
    rows = [
        row for row in rows
        if row.get("case_id") in expected
        and row.get("ok") is True
        and row.get("numerics", {}).get("rays_per_point") == 2000
    ]
    if len(rows) != 4 or {row["case_id"] for row in rows} != expected:
        raise ValueError("four released 2,000-ray stochastic baselines are required")
    if len({canonical_json(row["geometry"]) for row in rows}) != 1 or len({
        canonical_json(row["recipe"]) for row in rows
    }) != 1:
        raise ValueError("stochastic baselines do not share one recipe and geometry")

    values = {name: [] for name in design["practical_screen_thresholds"]}
    for row in rows:
        measured = row["selected_cycle_metrics"]
        etch = measured["etch"]
        current = {
            "etch_depth": etch["depth"],
            "selected_cycle": row["selected_cycle"],
            "etch_cd_top": etch["cd_top"],
            "etch_cd_middle": etch["cd_middle"],
            "etch_cd_bottom": etch["cd_bottom"],
            "etch_cd_taper_top_minus_bottom": etch["cd_top"] - etch["cd_bottom"],
            "etch_cd_span": etch["cd_max"] - etch["cd_min"],
            "etch_max_cd_error": etch["max_cd_error"],
            "etch_max_bow": etch["max_bow"],
            "etch_scallop_rms": etch["scallop_rms"],
            "etch_sidewall_angle_deg": etch["sidewall_angle_deg"],
            "mask_remaining_height": measured["mask_remaining_height"],
        }
        for name, value in current.items():
            if not finite_number(value):
                raise ValueError(f"invalid stochastic baseline metric: {name}")
            values[name].append(float(value))

    return {
        name: {
            "replicate_count": 4,
            "sample_standard_deviation": float(np.std(metric_values, ddof=1)),
            "independent_contrast_3sqrt2_sd": float(
                3.0 * math.sqrt(2.0) * np.std(metric_values, ddof=1)
            ),
        }
        for name, metric_values in values.items()
    }


def effective_screen_thresholds(release, design, *, project_root=ROOT):
    metric_results = release["ray_bridge"]["metric_results"]
    pairs = release["ray_bridge"]["pairs"]
    numerical = {
        "etch_depth": metric_results["depth"]["observed_max_absolute_delta"],
        "selected_cycle": None,
        "etch_cd_top": metric_results["cd_top"]["observed_max_absolute_delta"],
        "etch_cd_middle": metric_results["cd_middle"]["observed_max_absolute_delta"],
        "etch_cd_bottom": metric_results["cd_bottom"]["observed_max_absolute_delta"],
        "etch_cd_taper_top_minus_bottom": max(
            abs(
                pair["deltas_2000_minus_1000"]["cd_top"]
                - pair["deltas_2000_minus_1000"]["cd_bottom"]
            )
            for pair in pairs
        ),
        "etch_cd_span": 2.0 * max(
            metric_results[name]["observed_max_absolute_delta"]
            for name in ("cd_top", "cd_middle", "cd_bottom")
        ),
        "etch_max_cd_error": metric_results["max_cd_error"]["observed_max_absolute_delta"],
        "etch_max_bow": metric_results["max_bow"]["observed_max_absolute_delta"],
        "etch_scallop_rms": metric_results["scallop_rms"]["observed_max_absolute_delta"],
        "etch_sidewall_angle_deg": None,
        "mask_remaining_height": metric_results["mask_remaining_height"]["observed_max_absolute_delta"],
    }
    geometry_outputs = set(numerical) - {"selected_cycle", "etch_sidewall_angle_deg"}
    two_grid_cells = 2.0 * design["numerics"]["grid_delta"]
    stochastic = stochastic_baseline(release, design, project_root=project_root)
    thresholds = {}
    for metric, practical in design["practical_screen_thresholds"].items():
        components = {
            "practical_engineering_change": practical,
            "released_r1_numerical_shift": numerical[metric],
            "two_grid_cells": two_grid_cells if metric in geometry_outputs else None,
            "paired_stochastic_term": None,
            "independent_stochastic_contrast_term": stochastic[metric][
                "independent_contrast_3sqrt2_sd"
            ],
        }
        available = [
            float(value) for value in components.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        thresholds[metric] = {
            **components,
            "effective_threshold": max(available),
            "stochastic_baseline_replicates": 4,
            "stochastic_sample_standard_deviation": stochastic[metric][
                "sample_standard_deviation"
            ],
            "paired_stochastic_status": "unavailable_for_independent_recipe_streams",
            "stochastic_contrast_status": (
                "conservative_3sqrt2_sample_sd_from_four_disjoint_released_"
                "nominal_baselines"
            ),
            "authority": "hypothesis_screening_only",
        }
    return thresholds


def validate_manifest(
    manifest, *, check_runtime=True, check_prerequisite=True, project_root=ROOT
):
    errors = []
    root = Path(project_root)
    try:
        spec = builder.common.strict_load(root / builder.DEFAULT_SPEC)
        expected_design = builder.build_design(spec)
    except Exception as error:
        return [f"deterministic design could not be rebuilt: {error}"]
    if manifest.get("manifest_version") != 1:
        errors.append("manifest version differs")
    if manifest.get("methodology_epoch") != "full-traveler-doe-v3":
        errors.append("methodology epoch differs")
    if manifest.get("campaign") != "v3-pattern-bosch-stage2a":
        errors.append("campaign differs")
    if manifest.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("required labels differ")
    if manifest.get("design") != expected_design:
        errors.append("embedded deterministic design differs")
    if manifest.get("execution") != {
        "output": str(DEFAULT_OUTPUT),
        "maximum_workers": 2,
        "threads_per_worker": 7,
        "executor": "direct_checkpointed_batch_no_llm",
        "launch_order": "after_v3_pattern_stage1_review_resource_scheduling_only",
    }:
        errors.append("execution contract differs")
    if manifest.get("authority") != expected_design["authority"]:
        errors.append("authority differs")
    if check_runtime and manifest.get("runtime_fingerprint") != runtime_fingerprint(root):
        errors.append("runtime or source fingerprint differs")
    declaration = manifest.get("source_artifacts", {}).get("v3_numerical_release", {})
    source = Path(declaration.get("path", ""))
    source = source if source.is_absolute() else root / source
    if check_prerequisite:
        if not source.is_file():
            errors.append("V3 numerical release is missing")
        elif declaration.get("sha256") != file_sha256(source):
            errors.append("V3 numerical release hash differs")
        else:
            try:
                release = gate0.strict_json_loads(source.read_text())
                errors.extend(validate_numerical_release(release, project_root=root))
                if manifest.get("effective_screen_thresholds") != effective_screen_thresholds(
                    release, expected_design, project_root=root
                ):
                    errors.append("effective screen thresholds differ from the released numerical evidence")
            except Exception as error:
                errors.append(f"V3 numerical release does not parse: {error}")
    if "v3_pattern_stage1" in manifest.get("source_artifacts", {}):
        errors.append("Stage 1 was encoded as a false Stage 2a data prerequisite")
    cases = expand_cases(manifest) if manifest.get("design") == expected_design else []
    if cases:
        if len(cases) != 96 or len({case["case_id"] for case in cases}) != 96:
            errors.append("expanded Stage 2a matrix is not 96 unique cases")
        errors.extend(rng_interval_errors(cases))
        for case in cases:
            if case["numerics"].get("simulation_dimension") != 2:
                errors.append(f"{case['case_id']}: simulation dimension differs")
            if case["case_id"] != case_id(case_payload(case)):
                errors.append(f"{case['case_id']}: case ID differs")
            if case["case_payload_sha256"] != canonical_sha256(case_payload(case)):
                errors.append(f"{case['case_id']}: case payload hash differs")
    return errors


def expand_cases(manifest):
    design = manifest["design"]
    policy = design["rng_policy"]
    horizon = policy["process_seed_horizon"]
    cases = []
    for index, row in enumerate(design["recipes"]):
        seed = policy["seed_start"] + index * policy["interval_stride"]
        recipe = {
            **row["recipe"],
            "mask_taper": design["geometry"]["mask_taper"],
            "mask_ion_rate": design["fixed_recipe"]["mask_ion_rate"],
        }
        current = {
            "manifest_version": manifest["manifest_version"],
            "methodology_epoch": manifest["methodology_epoch"],
            "campaign": manifest["campaign"],
            "labels": list(manifest["labels"]),
            "recipe_id": row["recipe_id"],
            "design_class": row["design_class"],
            "anchor_reasons": list(row["anchor_reasons"]),
            "normalized_coordinates": dict(row["normalized_coordinates"]),
            "geometry": dict(design["geometry"]),
            "recipe": recipe,
            "numerics": {
                "grid_delta": design["numerics"]["grid_delta"],
                "rays_per_point": design["numerics"]["rays_per_point"],
                "threads_per_worker": design["numerics"]["threads_per_worker"],
                "simulation_dimension": design["numerics"]["dimension"],
            },
            "trajectory": dict(design["trajectory"]),
            "target": dict(design["target"]),
            "rng_seed": int(seed),
            "rng_stream": {
                "allocation_id": f"v3pb2a_rng_{index:03d}",
                "base_seed": int(seed),
                "first_process_seed": int(seed),
                "last_process_seed": int(seed) + horizon - 1,
                "process_seed_horizon": horizon,
                "globally_disjoint_within_stage": True,
                "interval_reused": False,
                "same_seed_labels_reused_across_recipes": False,
                "pointwise_common_random_numbers_claimed": False,
                "reserved_prior_v3_intervals": list(
                    policy["reserved_prior_v3_intervals"]
                ),
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
    errors = []
    ordered = sorted(cases, key=lambda case: case["rng_stream"]["first_process_seed"])
    for index, case in enumerate(ordered):
        stream = case["rng_stream"]
        if stream["first_process_seed"] != case["rng_seed"]:
            errors.append(f"{case['case_id']}: first process seed differs")
        if stream["last_process_seed"] != (
            case["rng_seed"] + stream["process_seed_horizon"] - 1
        ):
            errors.append(f"{case['case_id']}: process-seed interval differs")
        if index and ordered[index - 1]["rng_stream"]["last_process_seed"] >= stream[
            "first_process_seed"
        ]:
            errors.append(
                f"{ordered[index - 1]['case_id']} overlaps RNG interval with {case['case_id']}"
            )
        for reserved in stream["reserved_prior_v3_intervals"]:
            if not (
                stream["last_process_seed"] < reserved["first"]
                or stream["first_process_seed"] > reserved["last"]
            ):
                errors.append(
                    f"{case['case_id']} overlaps prior V3 interval "
                    f"{reserved['campaign']}"
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


def acquire_campaign_lock(output, campaign):
    path = Path(output).with_suffix(Path(output).suffix + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(descriptor)
        raise RuntimeError(f"another Stage 2a runner holds {path}") from error
    lock_record = {
        "campaign": campaign,
        "output": str(Path(output).resolve()),
        "pid": os.getpid(),
    }
    os.ftruncate(descriptor, 0)
    os.write(descriptor, (canonical_json(lock_record) + "\n").encode())
    os.fsync(descriptor)
    return descriptor, path


def release_campaign_lock(descriptor):
    fcntl.flock(descriptor, fcntl.LOCK_UN)
    os.close(descriptor)


def _trajectory_classification(row):
    history = row.get("cycle_history") or []
    last = history[-1] if history else {}
    target = row["target"]
    lower = target["etch_depth"] - target["depth_tolerance"]
    upper = target["etch_depth"] + target["depth_tolerance"]
    selected = (row.get("selected_cycle_metrics") or {}).get("etch", {}).get("depth")
    if (
        row.get("early_stopped") is False
        and row.get("last_recorded_cycle") == row["trajectory"]["maximum_cycles"]
        and isinstance(last.get("depth"), (int, float))
        and math.isfinite(float(last["depth"]))
        and last["depth"] < lower
    ):
        return "shallow_at_cycle_horizon_boundary_limited"
    if (
        row.get("selection_eligible") is False
        and isinstance(selected, (int, float))
        and math.isfinite(float(selected))
        and selected > upper
    ):
        return "target_depth_skipped_between_cycle_checkpoints"
    return "depth_selected"


def _copy_domain(domain):
    copied = ps.Domain()
    copied.deepCopy(domain)
    return copied


def _invalid_measurement(error):
    reason = f"selected_cycle_metrics: measurement failed: {error}"
    return {
        "etch": {name: None for name in screen.SLIM_ETCH_KEYS},
        "mask_remaining_height": None,
        "post_etch_mask": {},
    }, [reason]


def run_case(task):
    """Run one case while retaining measurable under-etch boundary evidence."""
    case, output = task
    started = time.time()
    try:
        if case["numerics"].get("simulation_dimension") != 2:
            raise ValueError("Stage 2a requires an explicit 2D simulation")
        ps.setNumThreads(int(case["numerics"]["threads_per_worker"]))
        recipe = case["recipe"]
        geometry = tp.make_initial_geometry(
            radius=case["geometry"]["radius"],
            mask_height=case["geometry"]["mask_height"],
            grid_delta=case["numerics"]["grid_delta"],
            x_extent=case["geometry"]["x_extent"],
            y_extent=case["geometry"]["y_extent"],
            taper=recipe["mask_taper"],
            hole_shape=ps.HoleShape.FULL,
        )
        initial_mask = screen._mesh_for_material(
            geometry, ps.Material.Mask, required=True
        )
        initial_invalid = []
        initial_pattern = screen.sanitize(
            gate0.measure_pattern(initial_mask, case),
            "initial_pattern",
            initial_invalid,
        )
        history = []
        best = fallback = last_snapshot = None
        best_rank = fallback_rank = None

        def on_cycle(current_geometry, cycle):
            nonlocal best, fallback, last_snapshot, best_rank, fallback_rank
            try:
                measured, invalid = r1._measure_domain(current_geometry, case)
            except Exception as error:
                measured, invalid = _invalid_measurement(error)
            record = screen.slim_cycle(cycle, measured, invalid)
            history.append(record)
            snapshot = {
                "cycle": int(cycle),
                "domain": _copy_domain(current_geometry),
                "measured": measured,
                "invalid_reasons": invalid,
            }
            last_snapshot = snapshot
            rank = screen.depth_rank(record, case)
            if rank is not None and (best_rank is None or rank < best_rank):
                best_rank = rank
                best = snapshot
            if record["metrics_valid"] is True:
                current_fallback_rank = (
                    abs(record["depth"] - case["target"]["etch_depth"]),
                    int(cycle),
                )
                if fallback_rank is None or current_fallback_rank < fallback_rank:
                    fallback_rank = current_fallback_rank
                    fallback = snapshot
            depth = record.get("depth")
            if finite_number(depth) and depth >= case["trajectory"]["early_stop_depth"]:
                raise screen.TrajectoryStop

        underetch_assertion = None
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
                radius=case["geometry"]["radius"],
                theta_r_min=recipe["theta_r_min"],
                rays_per_point=case["numerics"]["rays_per_point"],
                rng_seed=case["rng_seed"],
                on_cycle=on_cycle,
            )
        except screen.TrajectoryStop:
            pass
        except AssertionError as error:
            if str(error).startswith("etch barely moved:"):
                underetch_assertion = str(error)
            else:
                raise
        if not history or last_snapshot is None:
            raise ValueError("trajectory produced no checkpoint")

        selected, eligible, rank = screen.select_depth_matched(history, case)
        scientific_invalid = selected is None
        if scientific_invalid:
            snapshot = last_snapshot
            selected_cycle = snapshot["cycle"]
            selected_measured = snapshot["measured"]
            selected_invalid = list(snapshot["invalid_reasons"])
            scientific_invalid_reasons = [
                "no_valid_depth_matched_metric_checkpoint",
                *selected_invalid,
            ]
            eligible = False
            rank = None
        else:
            snapshot = best if eligible else fallback
            if snapshot is None or snapshot["cycle"] != selected["cycle"]:
                raise ValueError("retained native domain differs from depth selection")
            selected_cycle = selected["cycle"]
            selected_measured = snapshot["measured"]
            selected_invalid = list(snapshot["invalid_reasons"])
            scientific_invalid_reasons = []

        path = r1.checkpoint_path(output, case["case_id"], selected_cycle)
        before_digest = r1.domain_mesh_sha256(snapshot["domain"])
        digest = native_checkpoint.save_domain_atomic(path, snapshot["domain"])
        restored = native_checkpoint.load_domain_checkpoint(path, expected_sha256=digest)
        after_digest = r1.domain_mesh_sha256(restored)
        if before_digest != after_digest:
            raise ValueError("native checkpoint changed the selected level sets")
        if scientific_invalid:
            restored_measured = selected_measured
            restored_invalid = selected_invalid
        else:
            restored_measured, restored_invalid = r1._measure_domain(restored, case)
            comparison_errors = r1._compare_values(
                selected_measured,
                restored_measured,
                path="selected_cycle_metrics",
            )
            if restored_invalid != selected_invalid:
                comparison_errors.append(
                    "selected metric invalid reasons differ after native reload"
                )
            if comparison_errors:
                raise ValueError(
                    "native checkpoint metric drift: "
                    + "; ".join(comparison_errors)
                )
        gates = screen.classify_gates(initial_pattern, restored_measured, case)
        if scientific_invalid:
            for name in (
                "etch_depth", "etch_cd_profile", "etch_bow", "etch_mask_resolved"
            ):
                gates[name] = False
            gates["etch_pass"] = False
        last_depth = history[-1].get("depth")
        row = {
            **case,
            "ok": True,
            "simulation_completed": True,
            "metrics_valid": not scientific_invalid,
            "scientific_invalid_reasons": scientific_invalid_reasons,
            "underetch_assertion_intercepted": underetch_assertion,
            "evidence_origin": evidence_origin(),
            "initial_pattern": initial_pattern,
            "initial_pattern_invalid_reasons": initial_invalid,
            "cycle_history": history,
            "selected_cycle": selected_cycle,
            "selection_eligible": bool(eligible),
            "selection_rank": list(rank) if rank is not None else None,
            "selected_cycle_metrics": restored_measured,
            "selected_metric_invalid_reasons": restored_invalid,
            "gates": gates,
            "hard_gate_pass": bool(
                not scientific_invalid
                and screen.combined_hard_gate_pass(eligible, gates)
            ),
            "early_stopped": bool(
                finite_number(last_depth)
                and last_depth >= case["trajectory"]["early_stop_depth"]
            ),
            "last_recorded_cycle": history[-1]["cycle"],
            "checkpoint_format": "ViennaPS .vpsd",
            "checkpoint_path": str(path),
            "checkpoint_sha256": digest,
            "native_mesh_sha256": after_digest,
            "native_roundtrip_exact": True,
            "elapsed_s": time.time() - started,
        }
        if scientific_invalid:
            row["trajectory_classification"] = "invalid_metrics_failure_boundary"
            row["depth_horizon_censored"] = False
        else:
            classification = _trajectory_classification(row)
            row["trajectory_classification"] = classification
            row["depth_horizon_censored"] = (
                classification == "shallow_at_cycle_horizon_boundary_limited"
            )
        consumed = 1 + 3 * int(row["last_recorded_cycle"])
        row["rng_consumption"] = {
            "reserved_first_process_seed": row["rng_stream"]["first_process_seed"],
            "reserved_last_process_seed": row["rng_stream"]["last_process_seed"],
            "reserved_process_seed_horizon": row["rng_stream"][
                "process_seed_horizon"
            ],
            "actual_process_seed_count": consumed,
            "actual_last_process_seed": row["rng_seed"] + consumed - 1,
            "early_stop_shortened_stream": consumed < row["rng_stream"][
                "process_seed_horizon"
            ],
        }
        canonical_json(row)
        return row
    except Exception as error:
        return {
            **case,
            "ok": False,
            "simulation_completed": False,
            "evidence_origin": evidence_origin(),
            "error": repr(error),
            "traceback": traceback.format_exc(),
            "elapsed_s": time.time() - started,
        }


def validate_success_row(row, case, output):
    errors = []
    if not row_matches_case(row, case):
        errors.append("case payload differs")
    if row.get("evidence_origin") != evidence_origin():
        errors.append("evidence origin differs")
    if row.get("simulation_completed") is not True:
        errors.append("simulation is not marked complete")
    metrics_valid = row.get("metrics_valid")
    if metrics_valid not in (True, False):
        errors.append("scientific metric-valid status is missing")
    if isinstance(row.get("last_recorded_cycle"), int):
        consumed = 1 + 3 * row["last_recorded_cycle"]
        expected_consumption = {
            "reserved_first_process_seed": case["rng_stream"][
                "first_process_seed"
            ],
            "reserved_last_process_seed": case["rng_stream"][
                "last_process_seed"
            ],
            "reserved_process_seed_horizon": case["rng_stream"][
                "process_seed_horizon"
            ],
            "actual_process_seed_count": consumed,
            "actual_last_process_seed": case["rng_seed"] + consumed - 1,
            "early_stop_shortened_stream": consumed < case["rng_stream"][
                "process_seed_horizon"
            ],
        }
        errors.extend(r1._compare_values(
            expected_consumption,
            row.get("rng_consumption"),
            path="rng_consumption",
        ))
    else:
        errors.append("last recorded cycle is invalid")
    if metrics_valid is False:
        if row.get("trajectory_classification") != "invalid_metrics_failure_boundary":
            errors.append("invalid-metric trajectory classification differs")
        if row.get("depth_horizon_censored") is not False:
            errors.append("invalid metrics were mislabeled as a depth censor")
        if row.get("selection_eligible") is not False:
            errors.append("invalid metrics were selection eligible")
        if row.get("selection_rank") is not None:
            errors.append("invalid metrics have a selection rank")
        reasons = row.get("scientific_invalid_reasons")
        if not isinstance(reasons, list) or "no_valid_depth_matched_metric_checkpoint" not in reasons:
            errors.append("scientific invalid reasons are incomplete")
        if row.get("hard_gate_pass") is not False:
            errors.append("invalid metrics passed the hard gate")
        gates = row.get("gates") or {}
        if any(
            gates.get(name) is not False
            for name in ("etch_depth", "etch_cd_profile", "etch_bow", "etch_mask_resolved", "etch_pass")
        ):
            errors.append("invalid metrics retain an etch gate")
        selected_cycle = row.get("selected_cycle")
        expected_path = r1.checkpoint_path(output, case["case_id"], selected_cycle)
        if Path(row.get("checkpoint_path", "")).resolve() != expected_path.resolve():
            errors.append("invalid-metric checkpoint path differs")
        else:
            try:
                restored = native_checkpoint.load_domain_checkpoint(
                    expected_path,
                    expected_sha256=row.get("checkpoint_sha256"),
                )
                if r1.domain_mesh_sha256(restored) != row.get("native_mesh_sha256"):
                    errors.append("invalid-metric native mesh hash differs")
                if not math.isclose(
                    float(restored.getGridDelta()),
                    float(case["numerics"]["grid_delta"]),
                    rel_tol=0.0,
                    abs_tol=1e-15,
                ):
                    errors.append("invalid-metric checkpoint grid differs")
            except Exception as error:
                errors.append(f"invalid-metric native checkpoint failed: {error}")
        history = row.get("cycle_history")
        if not isinstance(history, list) or not history:
            errors.append("invalid-metric cycle history is missing")
        else:
            cycles = [record.get("cycle") for record in history]
            if cycles != list(range(len(cycles))):
                errors.append("invalid-metric cycle history is not contiguous")
            if selected_cycle != cycles[-1]:
                errors.append("invalid-metric checkpoint is not the final measurable state")
    elif metrics_valid is True:
        if row.get("scientific_invalid_reasons") != []:
            errors.append("valid metrics retain scientific invalid reasons")
        expected_classification = _trajectory_classification(row)
        if row.get("trajectory_classification") != expected_classification:
            errors.append("trajectory classification differs")
        expected_censored = expected_classification == "shallow_at_cycle_horizon_boundary_limited"
        if row.get("depth_horizon_censored") is not expected_censored:
            errors.append("depth-horizon censoring differs")
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


def worker_row_errors(row, case, output):
    if not isinstance(row, dict):
        return ["worker result is not an object"]
    if not row_matches_case(row, case):
        return ["worker returned a stale or wrong case payload"]
    if row.get("evidence_origin") != evidence_origin():
        return ["worker evidence origin differs"]
    if row.get("ok") is True:
        return validate_success_row(row, case, output)
    if row.get("ok") is False:
        return []
    return ["worker result lacks a boolean execution status"]


def drain_in_flight(in_flight, output):
    """Preserve any already-running valid attempt after scheduling stops."""
    drain_errors = []
    for future, case in list(in_flight.items()):
        if future.cancel():
            continue
        try:
            row = future.result()
        except Exception as error:
            drain_errors.append(f"{case['case_id']}: drain failed: {error}")
            continue
        errors = worker_row_errors(row, case, output)
        if errors:
            drain_errors.append(f"{case['case_id']}: " + "; ".join(errors))
            continue
        gate0.append_row(output, row)
    return drain_errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest_path = project_path(args.manifest)
    output = project_path(args.output)
    manifest = gate0.strict_json_loads(manifest_path.read_text())
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid V3 Stage 2a manifest: " + "; ".join(errors))
    if output != project_path(manifest["execution"]["output"]):
        raise ValueError("output differs from the frozen execution contract")
    if args.workers != manifest["execution"]["maximum_workers"]:
        raise ValueError("worker count differs from the frozen execution contract")
    lock_descriptor, lock_path = acquire_campaign_lock(
        output, manifest["campaign"]
    )
    try:
        cases = expand_cases(manifest)
        successes = audit_existing_rows(output, cases)
        pending = [case for case in cases if case["case_id"] not in successes]
        print(
            f"logical=96 complete={len(successes)} pending={len(pending)} "
            f"lock={lock_path} authority=bosch_hypothesis_screening_only",
            flush=True,
        )
        if not pending:
            return
        if args.dry_run:
            print("dry-run: validated manifest and resume ledger; no simulation launched")
            return
        executor = futures.ProcessPoolExecutor(max_workers=args.workers)
        in_flight = {}
        iterator = iter(pending)
        try:
            for _ in range(min(args.workers, len(pending))):
                case = next(iterator)
                in_flight[executor.submit(run_case, (case, output))] = case
            completed = 0
            while in_flight:
                finished = next(futures.as_completed(tuple(in_flight)))
                case = in_flight.pop(finished)
                try:
                    row = finished.result()
                except Exception as error:
                    drain_errors = drain_in_flight(in_flight, output)
                    raise RuntimeError(
                        f"Stage 2a worker crashed for {case['case_id']}: {error}; "
                        f"drain_errors={drain_errors}"
                    ) from error
                row_errors = worker_row_errors(row, case, output)
                if row_errors:
                    drain_errors = drain_in_flight(in_flight, output)
                    raise RuntimeError(
                        f"invalid Stage 2a worker row for {case['case_id']}: "
                        + "; ".join(row_errors)
                        + f"; drain_errors={drain_errors}"
                    )
                gate0.append_row(output, row)
                completed += 1
                print(
                    f"[{completed}/{len(pending)}] {row['case_id']} ok={row['ok']} "
                    f"elapsed={row['elapsed_s']:.1f}s",
                    flush=True,
                )
                if row.get("ok") is not True:
                    drain_errors = drain_in_flight(in_flight, output)
                    raise RuntimeError(
                        f"V3 Stage 2a case failed: {row['case_id']}; "
                        f"drain_errors={drain_errors}"
                    )
                next_case = next(iterator, None)
                if next_case is not None:
                    in_flight[executor.submit(
                        run_case, (next_case, output)
                    )] = next_case
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
    finally:
        release_campaign_lock(lock_descriptor)


if __name__ == "__main__":
    main()

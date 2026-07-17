"""Resumable executor for the V3 27-point pattern-geometry screen."""

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

import build_v3_pattern_skew_stage1 as builder
import foundation_metric_audit as foundation
import foundation_pattern_bosch_gate0 as gate0
import foundation_pattern_bosch_gate0_r1 as r1
import native_domain_checkpoint as native_checkpoint
import pattern_bosch_screen_runner as screen
import traveler_metrics as tm
import tsv_process as tp


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/v3_pattern_skew_stage1_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/v3_pattern_skew_stage1_rows.jsonl"
)
DEFAULT_NUMERICAL_RELEASE = Path(
    "autoresearch-results/restart_audit/v3_numerical_release.json"
)
CASE_FIELDS = (
    "manifest_version",
    "methodology_epoch",
    "campaign",
    "labels",
    "pattern",
    "geometry",
    "recipe",
    "numerics",
    "trajectory",
    "target",
    "pattern_gate_policy",
    "rng_seed",
    "rng_stream",
    "runtime_fingerprint",
    "source_artifacts",
    "authority",
    "provenance",
)


def file_sha256(path):
    return foundation.file_sha256(path)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def project_path(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _exact_json_value(observed, expected):
    if isinstance(expected, bool):
        return observed is expected
    if isinstance(expected, int):
        return type(observed) is int and observed == expected
    if isinstance(expected, float):
        return type(observed) is float and observed == expected
    return type(observed) is type(expected) and observed == expected


def runtime_fingerprint(project_root=ROOT):
    root = Path(project_root)
    return {
        "runner_sha256": file_sha256(root / Path(__file__).name),
        "reviewer_sha256": file_sha256(root / "review_v3_pattern_skew_stage1.py"),
        "builder_sha256": file_sha256(root / "build_v3_pattern_skew_stage1.py"),
        "design_spec_sha256": file_sha256(root / builder.DEFAULT_SPEC),
        "program_sha256": file_sha256(root / "program.md"),
        "research_plan_v3_sha256": file_sha256(root / "RESEARCH_PLAN_V3.md"),
        "r1_kernel_sha256": file_sha256(root / "foundation_pattern_bosch_gate0_r1.py"),
        "screen_kernel_sha256": file_sha256(root / "pattern_bosch_screen_runner.py"),
        "native_checkpoint_sha256": file_sha256(root / "native_domain_checkpoint.py"),
        "gate0_metric_sha256": file_sha256(root / "foundation_pattern_bosch_gate0.py"),
        "traveler_metrics_sha256": file_sha256(root / "traveler_metrics.py"),
        "tsv_process_sha256": file_sha256(root / "tsv_process.py"),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "numpy_proxy_sha256": file_sha256(np.__file__),
        "viennaps_proxy_sha256": file_sha256(ps.__file__),
        "viennals_proxy_sha256": file_sha256(ls.__file__),
        "viennaps_binary_sha256": file_sha256(ps_core.__file__),
        "viennals_binary_sha256": file_sha256(ls_core.__file__),
    }


def evidence_origin():
    return {
        "mode": "executed_v3_pattern_skew_stage1",
        "geometry_constructed_directly": True,
        "physical_dose_or_focus_claim": False,
        "per_case_depth_matched": True,
        "native_vpsd_checkpoint": True,
        "nonselected_cycle_native_checkpoints": False,
        "explicit_simulation_dimension": 2,
        "single_shared_rng_block": True,
        "pointwise_common_random_numbers_claimed": False,
        "stochastic_variance_estimated": False,
        "screening_only": True,
    }


def case_payload(case):
    return {field: case.get(field) for field in CASE_FIELDS}


def case_id(payload):
    return canonical_sha256(payload)[:16]


def validate_numerical_release(release):
    errors = []
    if release.get("artifact") != "v3_stage0_numerical_release":
        errors.append("numerical release artifact identity differs")
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
    for name, value in expected.items():
        if not _exact_json_value(decision.get(name), value):
            errors.append(f"numerical release {name} differs")
    expected_authority = {
        "exploratory_screening": True,
        "automatic_launch": False,
        "mask_claims": False,
        "recipe": False,
        "process_window": False,
        "full_traveler": False,
        "fab_recipe": False,
    }
    observed_authority = decision.get("authority")
    if not isinstance(observed_authority, dict) or (
        set(observed_authority) != set(expected_authority)
        or any(
            observed_authority.get(name) is not value
            for name, value in expected_authority.items()
        )
    ):
        errors.append("numerical release authority differs")
    bridge = release.get("ray_bridge", {})
    if bridge.get("all_rows_independently_valid") is not True:
        errors.append("numerical release rows are not independently valid")
    if bridge.get("no_hard_gate_flips") is not True:
        errors.append("numerical release contains hard-gate flips")
    if bridge.get("pair_count") != 4:
        errors.append("numerical release does not contain four ray pairs")
    if bridge.get("rays_1000_passes_frozen_bridge") is not False:
        errors.append("numerical release does not reject 1,000 rays")
    native = release.get("native_baselines", {})
    if not (
        native.get("authorized") is True
        and native.get("rays_per_point") == 2000
        and native.get("shape_count") == 4
        and len(native.get("shapes", [])) == 4
        and all(row.get("accepted") is True for row in native["shapes"])
    ):
        errors.append("numerical release native baseline set differs")
    metric_results = bridge.get("metric_results", {})
    required_metrics = (
        "depth",
        "cd_top",
        "cd_middle",
        "cd_bottom",
        "max_cd_error",
        "max_bow",
        "scallop_rms",
        "mask_remaining_height",
    )
    for name in required_metrics:
        value = (metric_results.get(name) or {}).get("observed_max_absolute_delta")
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or value < 0.0
        ):
            errors.append(f"numerical release metric delta is invalid: {name}")
    return errors


def _resolve(root, declaration):
    path = Path(declaration)
    return path if path.is_absolute() else Path(root) / path


def _source_errors(manifest, project_root):
    errors = []
    root = Path(project_root)
    release_decl = manifest.get("source_artifacts", {}).get("numerical_release", {})
    release_path = _resolve(root, release_decl.get("path", ""))
    if not release_path.is_file():
        errors.append("V3 numerical release is missing")
    elif release_decl.get("sha256") != file_sha256(release_path):
        errors.append("V3 numerical release hash differs")
    else:
        try:
            release = gate0.strict_json_loads(release_path.read_text())
            errors.extend(validate_numerical_release(release))
        except Exception as error:
            errors.append(f"V3 numerical release does not parse: {error}")

    recipe_decl = manifest.get("source_artifacts", {}).get("reference_recipe", {})
    recipe_path = _resolve(root, recipe_decl.get("path", ""))
    if not recipe_path.is_file():
        errors.append("reference Bosch recipe source is missing")
    elif recipe_decl.get("sha256") != file_sha256(recipe_path):
        errors.append("reference Bosch recipe source hash differs")
    else:
        try:
            source = gate0.strict_json_loads(recipe_path.read_text())
            source_recipe = dict(source.get("recipe", {}))
            fixed = dict(manifest["design"]["fixed_bosch_recipe"])
            fixed.pop("source_path", None)
            for name, value in fixed.items():
                if name == "mask_ion_rate":
                    if value != 0.0:
                        errors.append("Stage 1 mask erosion hold differs")
                    continue
                if source_recipe.get(name) != value:
                    errors.append(f"reference Bosch control differs: {name}")
            if source_recipe.get("num_cycles") != manifest["design"]["trajectory"]["maximum_cycles"]:
                errors.append("reference Bosch cycle horizon differs")
        except Exception as error:
            errors.append(f"reference Bosch recipe does not parse: {error}")
    return errors


def expand_cases(manifest):
    design = manifest["design"]
    fixed = dict(design["fixed_bosch_recipe"])
    fixed.pop("source_path")
    policy = design["rng_policy"]
    cases = []
    for point in design["points"]:
        values = point["values"]
        recipe = {
            **fixed,
            "num_cycles": design["trajectory"]["maximum_cycles"],
            "mask_taper": values["mask_taper"],
        }
        current = {
            "manifest_version": manifest["manifest_version"],
            "methodology_epoch": manifest["methodology_epoch"],
            "campaign": manifest["campaign"],
            "labels": list(manifest["labels"]),
            "pattern": {
                "pattern_id": point["pattern_id"],
                "levels": dict(point["levels"]),
                "input_geometry": dict(values),
                "interpretation": "measured geometry skew; not dose or focus",
            },
            "geometry": {
                **design["geometry"],
                "radius": values["opening_cd"] / 2.0,
                "mask_height": values["mask_height"],
            },
            "recipe": recipe,
            "numerics": {
                "grid_delta": design["numerics"]["grid_delta"],
                "rays_per_point": design["numerics"]["rays_per_point"],
                "threads_per_worker": design["numerics"]["threads_per_worker"],
                "simulation_dimension": design["numerics"]["dimension"],
            },
            "trajectory": dict(design["trajectory"]),
            "target": dict(design["target"]),
            "pattern_gate_policy": dict(design["pattern_gate_policy"]),
            "rng_seed": policy["base_seed"],
            "rng_stream": {
                "block_id": policy["block_id"],
                "base_seed": policy["base_seed"],
                "first_process_seed": policy["first_process_seed"],
                "last_process_seed": policy["last_process_seed"],
                "process_seed_horizon": policy["process_seed_horizon"],
                "same_interval_reused_across_all_pattern_cases": True,
                "pointwise_common_random_numbers_claimed": False,
                "independent_replicate": False,
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


def validate_manifest(manifest, *, check_runtime=True, check_sources=True, project_root=ROOT):
    errors = []
    root = Path(project_root)
    spec = builder.strict_load(root / builder.DEFAULT_SPEC)
    expected_design = builder.build_design(spec)
    if manifest.get("manifest_version") != 1:
        errors.append("manifest version differs")
    if manifest.get("methodology_epoch") != "full-traveler-doe-v3":
        errors.append("methodology epoch differs")
    if manifest.get("campaign") != "v3-pattern-skew-stage1":
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
    }:
        errors.append("execution contract differs")
    if manifest.get("authority") != expected_design["authority"]:
        errors.append("authority differs")
    if check_runtime and manifest.get("runtime_fingerprint") != runtime_fingerprint(root):
        errors.append("runtime or source fingerprint differs")
    if check_sources:
        errors.extend(_source_errors(manifest, root))
    cases = expand_cases(manifest) if not errors or manifest.get("design") == expected_design else []
    if cases:
        if len(cases) != 27 or len({case["case_id"] for case in cases}) != 27:
            errors.append("expanded matrix is not 27 unique cases")
        expected_interval = (
            expected_design["rng_policy"]["first_process_seed"],
            expected_design["rng_policy"]["last_process_seed"],
        )
        if any(
            (
                case["rng_stream"]["first_process_seed"],
                case["rng_stream"]["last_process_seed"],
            ) != expected_interval
            or case["rng_stream"]["same_interval_reused_across_all_pattern_cases"] is not True
            or case["rng_stream"]["independent_replicate"] is not False
            for case in cases
        ):
            errors.append("shared RNG block allocation differs")
        for case in cases:
            if case["case_id"] != case_id(case_payload(case)):
                errors.append(f"case ID differs: {case['case_id']}")
            if case["case_payload_sha256"] != canonical_sha256(case_payload(case)):
                errors.append(f"case payload hash differs: {case['case_id']}")
    return errors


def row_matches_case(row, case):
    return bool(
        row.get("case_id") == case["case_id"]
        and row.get("case_payload_sha256") == case["case_payload_sha256"]
        and case_payload(row) == case_payload(case)
        and case_id(case_payload(row)) == case["case_id"]
        and canonical_sha256(case_payload(row)) == case["case_payload_sha256"]
    )


def checkpoint_path(output, current_case_id, selected_cycle):
    return r1.checkpoint_path(output, current_case_id, selected_cycle)


def acquire_campaign_lock(output):
    rooted_output = project_path(output)
    path = rooted_output.with_suffix(rooted_output.suffix + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(descriptor)
        raise RuntimeError(f"another Stage 1 runner holds {path}") from error
    os.ftruncate(descriptor, 0)
    os.write(descriptor, f"pid={os.getpid()}\n".encode())
    os.fsync(descriptor)
    return descriptor, path


def release_campaign_lock(descriptor):
    fcntl.flock(descriptor, fcntl.LOCK_UN)
    os.close(descriptor)


def target_depth_crossing(history, target_depth):
    valid = []
    for record in history or []:
        depth = record.get("depth")
        cycle = record.get("cycle")
        if (
            record.get("metrics_valid") is True
            and isinstance(cycle, int)
            and not isinstance(cycle, bool)
            and isinstance(depth, (int, float))
            and not isinstance(depth, bool)
            and math.isfinite(float(depth))
        ):
            valid.append((int(cycle), float(depth)))
    for cycle, depth in valid:
        if depth == target_depth:
            return {
                "status": "bracketed",
                "interpolated_cycle": float(cycle),
                "lower_cycle": cycle,
                "upper_cycle": cycle,
                "lower_depth": depth,
                "upper_depth": depth,
                "authority": "descriptive_depth_rate_hypothesis_only",
            }
    for (lower_cycle, lower_depth), (upper_cycle, upper_depth) in zip(valid, valid[1:]):
        if lower_depth <= target_depth <= upper_depth and upper_depth > lower_depth:
            fraction = (target_depth - lower_depth) / (upper_depth - lower_depth)
            return {
                "status": "bracketed",
                "interpolated_cycle": lower_cycle + fraction * (upper_cycle - lower_cycle),
                "lower_cycle": lower_cycle,
                "upper_cycle": upper_cycle,
                "lower_depth": lower_depth,
                "upper_depth": upper_depth,
                "authority": "descriptive_depth_rate_hypothesis_only",
            }
    if not valid:
        status = "no_valid_depth_history"
    elif max(depth for _, depth in valid) < target_depth:
        status = "right_censored_shallow_at_cycle_horizon"
    elif min(depth for _, depth in valid) > target_depth:
        status = "left_censored_target_exceeded_before_first_valid_checkpoint"
    else:
        status = "unbracketed_nonmonotonic_history"
    return {
        "status": status,
        "interpolated_cycle": None,
        "lower_cycle": None,
        "upper_cycle": None,
        "lower_depth": None,
        "upper_depth": None,
        "authority": "descriptive_depth_rate_hypothesis_only",
    }


def classify_gates(initial_pattern, measured, case):
    gates = screen.classify_gates(initial_pattern, measured, case)
    surface_cd = initial_pattern.get("opening_cd_surface")
    policy = case["pattern_gate_policy"]
    gates["pattern_width"] = bool(
        isinstance(surface_cd, (int, float))
        and not isinstance(surface_cd, bool)
        and math.isfinite(float(surface_cd))
        and abs(float(surface_cd) - policy["opening_cd_target"])
        <= (
            policy["opening_cd_numerical_allowance_grid_cells"]
            * case["numerics"]["grid_delta"]
        )
    )
    gates["pattern_pass"] = all(
        gates[name]
        for name in ("pattern_width", "pattern_height", "pattern_opening")
    )
    return gates


def measure_initial_pattern(case):
    geometry = tp.make_initial_geometry(
        radius=case["geometry"]["radius"],
        mask_height=case["geometry"]["mask_height"],
        grid_delta=case["numerics"]["grid_delta"],
        x_extent=case["geometry"]["x_extent"],
        y_extent=case["geometry"]["y_extent"],
        taper=case["recipe"]["mask_taper"],
        hole_shape=ps.HoleShape.FULL,
    )
    mask = screen._mesh_for_material(geometry, ps.Material.Mask, required=True)
    invalid = []
    measured = screen.sanitize(
        gate0.measure_pattern(mask, case),
        "initial_pattern",
        invalid,
    )
    surface = tm.opening_geometry_at_y(
        mask["nodes"],
        mask["lines"],
        0.0,
        max_radius=case["target"]["opening_cd"],
    )
    measured.update({
        "opening_cd_surface": float(surface["cd"]),
        "opening_center_surface": float(surface["center"]),
        "opening_surface_geometry_kind": surface["geometry_kind"],
    })
    return measured, invalid


def run_case(task):
    case, _output = task
    if case["numerics"]["simulation_dimension"] != 2:
        raise ValueError("Stage 1 execution requires explicit dimension 2")
    ps.setDimension(2)
    row = r1.run_case(task)
    row["evidence_origin"] = evidence_origin()
    if row.get("ok") is True:
        initial_pattern, initial_invalid = measure_initial_pattern(row)
        row["initial_pattern"] = initial_pattern
        row["initial_pattern_invalid_reasons"] = initial_invalid
        row["gates"] = classify_gates(
            row["initial_pattern"], row["selected_cycle_metrics"], row
        )
        row["hard_gate_pass"] = screen.combined_hard_gate_pass(
            row["selection_eligible"], row["gates"]
        )
        row["target_depth_crossing"] = target_depth_crossing(
            row.get("cycle_history"), row["target"]["etch_depth"]
        )
        row["cycle_history_canonical_sha256"] = canonical_sha256(
            row["cycle_history"]
        )
        consumed = 1 + 3 * int(row["last_recorded_cycle"])
        row["rng_consumption"] = {
            "actual_process_seed_count": consumed,
            "actual_last_process_seed": row["rng_seed"] + consumed - 1,
            "declared_maximum_process_seed_count": row["rng_stream"][
                "process_seed_horizon"
            ],
            "declared_maximum_last_process_seed": row["rng_stream"][
                "last_process_seed"
            ],
            "early_stop_shortened_stream": consumed < row["rng_stream"][
                "process_seed_horizon"
            ],
        }
    return row


def validate_success_row(row, case, output):
    errors = []
    if not row_matches_case(row, case):
        errors.append("case payload differs")
    if row.get("evidence_origin") != evidence_origin():
        errors.append("evidence origin differs")
    selected_cycle = row.get("selected_cycle")
    if not isinstance(selected_cycle, int) or isinstance(selected_cycle, bool):
        return errors + ["selected cycle is not an integer"]
    expected_path = checkpoint_path(output, case["case_id"], selected_cycle)
    declaration = row.get("checkpoint_path")
    if not isinstance(declaration, str) or Path(declaration).resolve() != expected_path.resolve():
        return errors + ["checkpoint path differs"]
    digest = row.get("checkpoint_sha256")
    if not isinstance(digest, str):
        return errors + ["checkpoint hash is missing"]
    try:
        restored = native_checkpoint.load_domain_checkpoint(expected_path, expected_sha256=digest)
    except Exception as error:
        return errors + [f"native checkpoint invalid: {error}"]
    if not math.isclose(
        float(restored.getGridDelta()),
        float(case["numerics"]["grid_delta"]),
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        errors.append("checkpoint grid delta differs")
    if row.get("native_mesh_sha256") != r1.domain_mesh_sha256(restored):
        errors.append("native mesh hash differs")
    if row.get("native_roundtrip_exact") is not True:
        errors.append("native roundtrip was not exact")
    if row.get("checkpoint_format") != "ViennaPS .vpsd":
        errors.append("checkpoint format differs")
    measured, invalid = r1._measure_domain(restored, case)
    errors.extend(r1._compare_values(
        measured,
        row.get("selected_cycle_metrics"),
        path="selected_cycle_metrics",
    ))
    if invalid != row.get("selected_metric_invalid_reasons"):
        errors.append("selected metric invalid reasons differ")
    history = row.get("cycle_history")
    if not isinstance(history, list) or not history:
        errors.append("cycle history is missing")
    else:
        cycles = [record.get("cycle") for record in history]
        if cycles != list(range(len(cycles))):
            errors.append("cycle history is not contiguous from cycle zero")
        selected, eligible, rank = screen.select_depth_matched(history, case)
        if selected is None or selected.get("cycle") != selected_cycle:
            errors.append("reported cycle is not the depth-matched selection")
        if eligible is not row.get("selection_eligible"):
            errors.append("selection eligibility differs")
        if row.get("selection_rank") != (list(rank) if rank is not None else None):
            errors.append("selection rank differs")
        last_depth = history[-1].get("depth")
        early = bool(
            isinstance(last_depth, (int, float))
            and last_depth >= case["trajectory"]["early_stop_depth"]
        )
        if row.get("early_stopped") is not early:
            errors.append("early-stop state differs")
        if row.get("last_recorded_cycle") != cycles[-1]:
            errors.append("last recorded cycle differs from history")
        if not early and cycles[-1] != case["trajectory"]["maximum_cycles"]:
            errors.append("trajectory ended before its frozen maximum")
        expected_crossing = target_depth_crossing(history, case["target"]["etch_depth"])
        errors.extend(r1._compare_values(
            expected_crossing,
            row.get("target_depth_crossing"),
            path="target_depth_crossing",
        ))
        if row.get("cycle_history_canonical_sha256") != canonical_sha256(history):
            errors.append("cycle-history canonical hash differs")
        expected_history_record = screen.slim_cycle(
            selected_cycle, measured, invalid
        )
        errors.extend(r1._compare_values(
            expected_history_record,
            history[selected_cycle] if selected_cycle < len(history) else None,
            path="selected_cycle_history_record",
        ))
        consumed = 1 + 3 * int(row.get("last_recorded_cycle", -1))
        expected_consumption = {
            "actual_process_seed_count": consumed,
            "actual_last_process_seed": case["rng_seed"] + consumed - 1,
            "declared_maximum_process_seed_count": case["rng_stream"][
                "process_seed_horizon"
            ],
            "declared_maximum_last_process_seed": case["rng_stream"][
                "last_process_seed"
            ],
            "early_stop_shortened_stream": consumed < case["rng_stream"][
                "process_seed_horizon"
            ],
        }
        errors.extend(r1._compare_values(
            expected_consumption,
            row.get("rng_consumption"),
            path="rng_consumption",
        ))
    try:
        initial_pattern, initial_invalid = measure_initial_pattern(case)
        errors.extend(r1._compare_values(
            initial_pattern,
            row.get("initial_pattern"),
            path="initial_pattern",
        ))
        if initial_invalid != row.get("initial_pattern_invalid_reasons"):
            errors.append("initial pattern invalid reasons differ")
        gates = classify_gates(initial_pattern, measured, case)
        if gates != row.get("gates"):
            errors.append("gate vector differs")
        expected_hard_pass = screen.combined_hard_gate_pass(
            row.get("selection_eligible"), gates
        )
        if row.get("hard_gate_pass") is not expected_hard_pass:
            errors.append("hard-gate pass differs")
    except Exception as error:
        errors.append(f"initial pattern recomputation failed: {error}")
    return errors


def audit_existing_rows(output, cases):
    output = Path(output)
    if not output.is_file():
        return {}, 0, []
    expected = {case["case_id"]: case for case in cases}
    successes = {}
    terminal_success = set()
    failures = []
    attempt_count = 0
    for line_number, line in enumerate(output.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        attempt_count += 1
        try:
            row = gate0.strict_json_loads(line)
        except Exception as error:
            raise ValueError(f"malformed row {line_number}: {error}") from error
        if not isinstance(row, dict):
            raise ValueError(f"row {line_number} is not an object")
        current_id = row.get("case_id")
        case = expected.get(current_id)
        if case is None:
            raise ValueError(f"unexpected case ID at row {line_number}")
        if current_id in terminal_success:
            raise ValueError(f"attempt follows success at row {line_number}")
        if not row_matches_case(row, case):
            raise ValueError(f"stale case payload at row {line_number}")
        if row.get("evidence_origin") != evidence_origin():
            raise ValueError(f"evidence origin differs at row {line_number}")
        if row.get("ok") is True:
            row_errors = validate_success_row(row, case, output)
            if row_errors:
                raise ValueError(
                    f"invalid success at row {line_number}: " + "; ".join(row_errors)
                )
            successes[current_id] = row
            terminal_success.add(current_id)
        elif row.get("ok") is False:
            failures.append({
                "line_number": line_number,
                "case_id": current_id,
                "pattern_id": case["pattern"]["pattern_id"],
                "error": row.get("error"),
            })
        else:
            raise ValueError(f"row {line_number} lacks a boolean execution status")
    return successes, attempt_count, failures


def validate_execution_options(*, limit, dry_run):
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative")
    if limit is not None and not dry_run:
        raise ValueError("--limit is allowed only with --dry-run")


def _failure_row(case, error, elapsed_s=0.0):
    return {
        **case,
        "ok": False,
        "evidence_origin": evidence_origin(),
        "error": str(error),
        "elapsed_s": float(elapsed_s),
    }


def execute_manifest(manifest, args):
    cases = expand_cases(manifest)
    successes, attempts, failures = audit_existing_rows(args.output, cases)
    pending = [case for case in cases if case["case_id"] not in successes]
    preview = pending if args.limit is None else pending[:args.limit]
    print(
        f"logical=27 complete={len(successes)} attempts={attempts} "
        f"failed_attempts={len(failures)} pending={len(pending)} "
        "authority=single_block_pattern_screen_only",
        flush=True,
    )
    if not pending:
        return
    if args.dry_run:
        print(
            f"dry-run: validated manifest and resume ledger; "
            f"preview_cases={len(preview)}; no simulation launched"
        )
        return
    fatal_errors = []
    with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        iterator = iter(pending)
        in_flight = {}
        for _ in range(min(args.workers, len(pending))):
            case = next(iterator)
            in_flight[executor.submit(run_case, (case, args.output))] = case
        completed = 0
        stop_scheduling = False
        while in_flight:
            finished = next(futures.as_completed(tuple(in_flight)))
            case = in_flight.pop(finished)
            try:
                row = finished.result()
            except Exception as error:
                row = _failure_row(case, f"worker exception: {error}")
            completed += 1
            if row.get("case_id") != case["case_id"]:
                row = _failure_row(case, "worker returned the wrong Stage 1 case")
            if row.get("ok") is True:
                row_errors = validate_success_row(row, case, args.output)
                if row_errors:
                    row = _failure_row(
                        case,
                        "post-run validation failed: " + "; ".join(row_errors),
                        row.get("elapsed_s", 0.0),
                    )
            gate0.append_row(args.output, row)
            print(
                f"[{completed}/{len(pending)}] {row['case_id']} ok={row['ok']} "
                f"elapsed={row['elapsed_s']:.1f}s",
                flush=True,
            )
            if row.get("ok") is not True:
                fatal_errors.append(f"{row['case_id']}: {row.get('error')}")
                stop_scheduling = True
            if not stop_scheduling:
                next_case = next(iterator, None)
                if next_case is not None:
                    in_flight[executor.submit(
                        run_case, (next_case, args.output)
                    )] = next_case
    if fatal_errors:
        raise RuntimeError(
            "V3 pattern-skew execution stopped after recording all in-flight "
            "attempts: " + "; ".join(fatal_errors)
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    validate_execution_options(limit=args.limit, dry_run=args.dry_run)
    manifest_path = project_path(args.manifest)
    manifest = gate0.strict_json_loads(manifest_path.read_text())
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid V3 pattern-skew manifest: " + "; ".join(errors))
    expected_output = project_path(manifest["execution"]["output"])
    requested_output = project_path(args.output)
    if requested_output.resolve() != expected_output.resolve():
        raise ValueError("output differs from the frozen execution contract")
    if args.workers != manifest["execution"]["maximum_workers"]:
        raise ValueError("worker count differs from the frozen execution contract")
    os.chdir(ROOT)
    args.output = Path(manifest["execution"]["output"])
    descriptor, _lock_path = acquire_campaign_lock(args.output)
    try:
        execute_manifest(manifest, args)
    finally:
        release_campaign_lock(descriptor)


if __name__ == "__main__":
    main()

"""Fast, depth-matched full-2D pattern/Bosch Gate-0 R1 campaign."""

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

import foundation_metric_audit as foundation
import foundation_pattern_bosch_gate0 as gate0
import native_domain_checkpoint as native_checkpoint
import pattern_bosch_screen_runner as screen
import traveler_metrics as tm
import tsv_process as tp


ps.Logger.setLogLevel(ps.LogLevel.ERROR)

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_pattern_bosch_gate0_r1_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/pattern_bosch_gate0_r1_rows.jsonl"
)
EXPECTED_SEEDS = (61000, 62000, 63000, 64000)
REFERENCE_ARM = "full_reference_r1000"
RAY_ANCHOR_ARM = "full_ray_anchor_r2000"
CASE_FIELDS = (
    "manifest_version",
    "campaign",
    "labels",
    "arm",
    "role",
    "geometry",
    "recipe",
    "numerics",
    "trajectory",
    "target",
    "rng_seed",
    "rng_stream",
    "rng_policy",
    "runtime_fingerprint",
    "authority",
    "provenance",
    "adaptive",
)


def file_sha256(path) -> str:
    return foundation.file_sha256(path)


def runtime_fingerprint(project_root=ROOT) -> dict:
    root = Path(project_root)
    return {
        "runner_sha256": file_sha256(root / Path(__file__).name),
        "reviewer_sha256": file_sha256(root / "review_pattern_bosch_gate0_r1.py"),
        "native_checkpoint_sha256": file_sha256(
            root / "native_domain_checkpoint.py"
        ),
        "screen_runner_sha256": file_sha256(
            root / "pattern_bosch_screen_runner.py"
        ),
        "gate0_metric_sha256": file_sha256(
            root / "foundation_pattern_bosch_gate0.py"
        ),
        "traveler_metrics_sha256": file_sha256(root / "traveler_metrics.py"),
        "tsv_process_sha256": file_sha256(root / "tsv_process.py"),
        "viennaps_binary_sha256": file_sha256(ps_core.__file__),
        "viennals_binary_sha256": file_sha256(ls_core.__file__),
    }


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def case_payload(row) -> dict:
    return {field: row.get(field) for field in CASE_FIELDS}


def case_id(payload) -> str:
    return canonical_sha256(payload)[:16]


def evidence_origin() -> dict:
    return {
        "mode": "executed_pattern_bosch_gate0_r1",
        "per_seed_depth_matched": True,
        "native_vpsd_checkpoint": True,
        "shared_base_seed_labels_across_arms": True,
        "pointwise_common_random_numbers_across_arms": False,
        "recipe_authority": False,
    }


def mask_arm(rate) -> str:
    return f"full_mask_challenge_m{abs(float(rate)):.2f}".replace(".", "p")


def _make_case(manifest, *, arm, role, rays, rate, seed, adaptive) -> dict:
    horizon = foundation.bosch_process_seed_count(
        manifest["trajectory"]["maximum_cycles"]
    )
    current = {
        "manifest_version": manifest["manifest_version"],
        "campaign": manifest["campaign"],
        "labels": list(manifest["labels"]),
        "arm": arm,
        "role": role,
        "geometry": dict(manifest["geometry"]),
        "recipe": {**manifest["recipe"], "mask_ion_rate": float(rate)},
        "numerics": {
            "grid_delta": manifest["numerics"]["grid_delta"],
            "rays_per_point": int(rays),
            "threads_per_worker": manifest["numerics"]["threads_per_worker"],
            "simulation_dimension": manifest["numerics"]["dimension"],
        },
        "trajectory": dict(manifest["trajectory"]),
        "target": dict(manifest["target"]),
        "rng_seed": int(seed),
        "rng_stream": {
            "base_seed": int(seed),
            "process_seed_count": horizon,
            "first_process_seed": int(seed),
            "last_process_seed": int(seed) + horizon - 1,
            "disjoint_within_arm": True,
            "shared_base_seed_label_across_arms": True,
            "pointwise_common_random_numbers_across_arms": False,
        },
        "rng_policy": dict(manifest["rng_policy"]),
        "runtime_fingerprint": dict(manifest["runtime_fingerprint"]),
        "authority": dict(manifest["authority"]),
        "provenance": dict(manifest["provenance"]),
        "adaptive": dict(adaptive),
    }
    payload = case_payload(current)
    current["case_id"] = case_id(payload)
    current["case_payload_sha256"] = canonical_sha256(payload)
    return current


def expand_cases(manifest) -> list[dict]:
    cases = []
    screen_rays = manifest["numerics"]["screen_rays_per_point"]
    anchor_rays = manifest["numerics"]["anchor_rays_per_point"]
    for arm, role, rays in (
        (REFERENCE_ARM, "screen_reference", screen_rays),
        (RAY_ANCHOR_ARM, "ray_anchor", anchor_rays),
    ):
        for seed in manifest["rng_base_seeds"]:
            cases.append(_make_case(
                manifest,
                arm=arm,
                role=role,
                rays=rays,
                rate=0.0,
                seed=seed,
                adaptive={"stage": "fixed", "rate_index": None},
            ))
    search_seed = manifest["mask_bracket"]["search_seed"]
    confirmation_seeds = manifest["mask_bracket"]["confirmation_seeds"]
    for index, rate in enumerate(manifest["mask_bracket"]["search_rates"]):
        cases.append(_make_case(
            manifest,
            arm=mask_arm(rate),
            role="mask_challenge",
            rays=screen_rays,
            rate=rate,
            seed=search_seed,
            adaptive={"stage": "search", "rate_index": index},
        ))
        for seed in confirmation_seeds:
            cases.append(_make_case(
                manifest,
                arm=mask_arm(rate),
                role="mask_challenge",
                rays=screen_rays,
                rate=rate,
                seed=seed,
                adaptive={"stage": "confirmation", "rate_index": index},
            ))
    return cases


def _reference_recipe_errors(manifest, project_root=ROOT) -> list[str]:
    declaration = manifest.get("reference_recipe", {})
    source = Path(declaration.get("source_path", ""))
    source = source if source.is_absolute() else Path(project_root) / source
    if not source.is_file():
        return ["reference recipe source is missing"]
    try:
        reference = gate0.strict_json_loads(source.read_text())
    except Exception as error:
        return [f"reference recipe source does not parse: {error}"]
    errors = []
    recipe = reference.get("recipe")
    if recipe != manifest.get("recipe"):
        errors.append("manifest recipe differs from the high-fidelity reference")
    if canonical_sha256(recipe) != declaration.get("recipe_canonical_sha256"):
        errors.append("reference recipe canonical hash differs")
    return errors


def validate_manifest(
    manifest, cases=None, *, check_runtime=True, project_root=ROOT
) -> list[str]:
    errors = []
    if manifest.get("manifest_version") != 1:
        errors.append("manifest version differs")
    if manifest.get("campaign") != "foundation-pattern-bosch-gate0-r1":
        errors.append("campaign name differs")
    if manifest.get("labels") != ["full-traveler", "critical-review"]:
        errors.append("required labels differ")
    if manifest.get("geometry") != {
        "hole_shape": "FULL",
        "radius": 0.15,
        "mask_height": 0.3,
        "x_extent": 1.0,
        "y_extent": 2.0,
    }:
        errors.append("full-width geometry contract differs")
    if manifest.get("trajectory") != {
        "maximum_cycles": 14,
        "first_scored_cycle": 1,
        "early_stop_depth": 1.45,
        "selection": (
            "minimum absolute depth error among valid checkpoints; an in-window "
            "checkpoint outranks every miss"
        ),
        "record_all_scored_cycles": True,
    }:
        errors.append("depth-matched trajectory contract differs")
    if manifest.get("rng_base_seeds") != list(EXPECTED_SEEDS):
        errors.append("RNG base seeds differ")
    if manifest.get("rng_policy") != {
        "shared_base_seed_labels_across_arms": True,
        "streams_disjoint_within_each_arm": True,
        "pointwise_common_random_numbers_across_arms": False,
        "interpretation": (
            "Base labels pair comparisons, but changed ray counts and evolving "
            "surfaces do not guarantee identical pointwise random draws."
        ),
    }:
        errors.append("RNG interpretation differs")
    if manifest.get("numerics") != {
        "grid_delta": 0.00125,
        "screen_rays_per_point": 1000,
        "anchor_rays_per_point": 2000,
        "threads_per_worker": 7,
        "maximum_workers": 2,
        "dimension": 2,
    }:
        errors.append("numerical contract differs")
    if manifest.get("mask_bracket") != {
        "search_seed": 61000,
        "search_rates": [-0.05, -0.06, -0.08],
        "confirmation_seeds": [62000, 63000, 64000],
        "selection": (
            "first valid search rate whose depth-matched checkpoint fails "
            "etch_mask_resolved"
        ),
        "maximum_executed_cases": 14,
    }:
        errors.append("adaptive mask-bracket contract differs")
    if manifest.get("target") != gate0.EXPECTED_TARGET:
        errors.append("target contract differs")
    if manifest.get("reference_recipe") != gate0.EXPECTED_REFERENCE_RECIPE:
        errors.append("reference recipe declaration differs")
    if manifest.get("review") != {
        "row_recompute_abs_tolerance": 1e-12,
        "paired_max_absolute_deltas": gate0.EXPECTED_TOLERANCES,
        "ray_bridge": {
            "reference_arm": REFERENCE_ARM,
            "candidate_arm": RAY_ANCHOR_ARM,
            "require_all_four_pairs": True,
            "require_no_gate_flips": True,
        },
        "require_all_reference_hard_pass": True,
        "require_all_seed_mask_bracket": True,
        "require_native_roundtrip_exact": True,
    }:
        errors.append("review gates or tolerances differ")
    if manifest.get("authority") != {
        "gate": "pattern_bosch_gate0_r1",
        "may_authorize": "broad_pattern_bosch_screen_only",
        "recipe_authorized": False,
        "process_window_authorized": False,
        "full_traveler_authorized": False,
        "automatic_downstream_launch_authorized": False,
    }:
        errors.append("authority differs")
    if check_runtime and manifest.get("runtime_fingerprint") != runtime_fingerprint(
        project_root
    ):
        errors.append("runtime or source fingerprint differs")
    errors.extend(_reference_recipe_errors(manifest, project_root))
    if cases is not None:
        if len(cases) != 20 or len({case["case_id"] for case in cases}) != 20:
            errors.append("potential adaptive matrix is not 20 unique cases")
        initial = initial_cases(cases)
        if len(initial) != 9:
            errors.append("initial adaptive matrix is not nine cases")
        for case in cases:
            if case["rng_stream"]["process_seed_count"] != 43:
                errors.append(f"RNG horizon differs: {case['case_id']}")
            if case["case_id"] != case_id(case_payload(case)):
                errors.append(f"case ID differs: {case['case_id']}")
            if case["case_payload_sha256"] != canonical_sha256(case_payload(case)):
                errors.append(f"case payload hash differs: {case['case_id']}")
    return errors


def initial_cases(cases) -> list[dict]:
    return [
        case for case in cases
        if case["adaptive"]["stage"] == "fixed"
        or (
            case["adaptive"]["stage"] == "search"
            and case["adaptive"]["rate_index"] == 0
        )
    ]


def _by_stage(cases, stage, rate_index=None) -> list[dict]:
    return [
        case for case in cases
        if case["adaptive"]["stage"] == stage
        and (
            rate_index is None
            or case["adaptive"]["rate_index"] == rate_index
        )
    ]


def _mask_survives(row) -> bool:
    value = (row.get("gates") or {}).get("etch_mask_resolved")
    if value not in (True, False):
        raise ValueError("successful mask-search row lacks a resolved-mask result")
    return value


def selected_failure_index(cases, successes) -> tuple[int | None, bool]:
    searches = sorted(
        _by_stage(cases, "search"),
        key=lambda case: case["adaptive"]["rate_index"],
    )
    for case in searches:
        row = successes.get(case["case_id"])
        if row is None:
            return None, False
        if not _mask_survives(row):
            return case["adaptive"]["rate_index"], False
    return None, True


def active_case_ids(cases, successes) -> set[str]:
    active = {
        case["case_id"]
        for case in cases if case["adaptive"]["stage"] == "fixed"
    }
    searches = sorted(
        _by_stage(cases, "search"),
        key=lambda case: case["adaptive"]["rate_index"],
    )
    for case in searches:
        active.add(case["case_id"])
        row = successes.get(case["case_id"])
        if row is None:
            return active
        if not _mask_survives(row):
            index = case["adaptive"]["rate_index"]
            active.update(
                item["case_id"] for item in _by_stage(cases, "confirmation", index)
            )
            return active
    return active


def campaign_terminal(cases, successes) -> bool:
    fixed = _by_stage(cases, "fixed")
    if any(case["case_id"] not in successes for case in fixed):
        return False
    failure_index, exhausted = selected_failure_index(cases, successes)
    if exhausted:
        return True
    if failure_index is None:
        return False
    confirmations = _by_stage(cases, "confirmation", failure_index)
    return all(case["case_id"] in successes for case in confirmations)


def checkpoint_directory(output=DEFAULT_OUTPUT) -> Path:
    output = Path(output)
    return output.parent / f"{output.stem}_checkpoints"


def checkpoint_path(output, current_case_id, selected_cycle) -> Path:
    return checkpoint_directory(output) / (
        f"{current_case_id}_cycle{int(selected_cycle):03d}.vpsd"
    )


def domain_mesh_sha256(domain) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(float(domain.getGridDelta()), dtype="<f8").tobytes())
    for mesh in tm.raw_level_set_meshes(domain):
        digest.update(str(mesh["material"]).encode())
        for name, dtype in (("nodes", "<f8"), ("lines", "<i8")):
            array = np.ascontiguousarray(mesh[name], dtype=dtype)
            digest.update(name.encode())
            digest.update(np.asarray(array.shape, dtype="<i8").tobytes())
            digest.update(array.tobytes())
    return digest.hexdigest()


def _copy_domain(domain):
    copied = ps.Domain()
    copied.deepCopy(domain)
    return copied


def _measure_domain(domain, case):
    silicon = screen._mesh_for_material(domain, ps.Material.Si, required=True)
    mask = screen._mesh_for_material(domain, ps.Material.Mask, required=False)
    invalid = []
    measured = screen.sanitize(
        gate0.measure_selected_cycle(silicon, mask, case),
        "selected_cycle_metrics",
        invalid,
    )
    return measured, invalid


def _compare_values(expected, observed, tolerance=1e-12, path="value") -> list[str]:
    errors = []
    if isinstance(expected, dict):
        if not isinstance(observed, dict):
            return [f"{path} is not a mapping"]
        if set(expected) != set(observed):
            errors.append(f"{path} keys differ")
        for key in sorted(set(expected) & set(observed)):
            errors.extend(_compare_values(
                expected[key], observed[key], tolerance, f"{path}.{key}"
            ))
        return errors
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            return [f"{path} sequence differs"]
        for index, (first, second) in enumerate(zip(expected, observed)):
            errors.extend(_compare_values(
                first, second, tolerance, f"{path}[{index}]"
            ))
        return errors
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(observed, (int, float)) or isinstance(observed, bool):
            return [f"{path} is not numeric"]
        if not math.isclose(
            float(expected), float(observed), rel_tol=0.0, abs_tol=tolerance
        ):
            errors.append(f"{path} differs")
        return errors
    if expected != observed:
        errors.append(f"{path} differs")
    return errors


def run_case(task):
    case, output = task
    started = time.time()
    try:
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
        best = None
        best_rank = None
        fallback = None
        fallback_rank = None

        def on_cycle(current_geometry, cycle):
            nonlocal best, best_rank, fallback, fallback_rank
            measured, invalid = _measure_domain(current_geometry, case)
            record = screen.slim_cycle(cycle, measured, invalid)
            history.append(record)
            rank = screen.depth_rank(record, case)
            if rank is not None and (best_rank is None or rank < best_rank):
                best_rank = rank
                best = {
                    "cycle": int(cycle),
                    "domain": _copy_domain(current_geometry),
                    "measured": measured,
                    "invalid_reasons": invalid,
                }
            if record["metrics_valid"] is True:
                current_fallback_rank = (
                    abs(record["depth"] - case["target"]["etch_depth"]),
                    int(cycle),
                )
                if fallback_rank is None or current_fallback_rank < fallback_rank:
                    fallback_rank = current_fallback_rank
                    fallback = {
                        "cycle": int(cycle),
                        "domain": _copy_domain(current_geometry),
                        "measured": measured,
                        "invalid_reasons": invalid,
                    }
            depth = record.get("depth")
            if (
                isinstance(depth, (int, float))
                and depth >= case["trajectory"]["early_stop_depth"]
            ):
                raise screen.TrajectoryStop

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
        selected, eligible, rank = screen.select_depth_matched(history, case)
        if selected is None:
            raise ValueError("trajectory produced no valid metric checkpoint")
        snapshot = best if eligible else fallback
        if snapshot is None or snapshot["cycle"] != selected["cycle"]:
            raise ValueError("retained native domain differs from depth selection")
        path = checkpoint_path(output, case["case_id"], snapshot["cycle"])
        before_digest = domain_mesh_sha256(snapshot["domain"])
        digest = native_checkpoint.save_domain_atomic(path, snapshot["domain"])
        restored = native_checkpoint.load_domain_checkpoint(
            path, expected_sha256=digest
        )
        after_digest = domain_mesh_sha256(restored)
        if before_digest != after_digest:
            raise ValueError("native checkpoint changed the selected level sets")
        restored_measured, restored_invalid = _measure_domain(restored, case)
        errors = _compare_values(
            snapshot["measured"], restored_measured, path="selected_cycle_metrics"
        )
        if restored_invalid != snapshot["invalid_reasons"]:
            errors.append("selected metric invalid reasons differ after native reload")
        if errors:
            raise ValueError("native checkpoint metric drift: " + "; ".join(errors))
        gates = screen.classify_gates(initial_pattern, restored_measured, case)
        last_depth = history[-1].get("depth")
        row = {
            **case,
            "ok": True,
            "evidence_origin": evidence_origin(),
            "initial_pattern": initial_pattern,
            "initial_pattern_invalid_reasons": initial_invalid,
            "cycle_history": history,
            "selected_cycle": selected["cycle"],
            "selection_eligible": eligible,
            "selection_rank": list(rank) if rank is not None else None,
            "selected_cycle_metrics": restored_measured,
            "selected_metric_invalid_reasons": restored_invalid,
            "gates": gates,
            "hard_gate_pass": screen.combined_hard_gate_pass(eligible, gates),
            "early_stopped": bool(
                isinstance(last_depth, (int, float))
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
        canonical_json(row)
        return row
    except Exception as error:
        return {
            **case,
            "ok": False,
            "evidence_origin": evidence_origin(),
            "error": repr(error),
            "traceback": traceback.format_exc(),
            "elapsed_s": time.time() - started,
        }


def row_matches_case(row, case) -> bool:
    return bool(
        isinstance(row, dict)
        and row.get("case_id") == case["case_id"]
        and row.get("case_payload_sha256") == case["case_payload_sha256"]
        and case_payload(row) == case_payload(case)
        and case_id(case_payload(row)) == case["case_id"]
        and canonical_sha256(case_payload(row)) == case["case_payload_sha256"]
    )


def validate_success_row(row, case, output) -> list[str]:
    errors = []
    if row.get("evidence_origin") != evidence_origin():
        errors.append("evidence origin differs")
    selected_cycle = row.get("selected_cycle")
    if not isinstance(selected_cycle, int) or isinstance(selected_cycle, bool):
        return errors + ["selected cycle is not an integer"]
    expected_path = checkpoint_path(output, case["case_id"], selected_cycle)
    declaration = row.get("checkpoint_path")
    if not isinstance(declaration, str) or (
        Path(declaration).resolve() != expected_path.resolve()
    ):
        errors.append("checkpoint path differs")
        return errors
    digest = row.get("checkpoint_sha256")
    if not isinstance(digest, str):
        errors.append("checkpoint hash is missing")
        return errors
    try:
        restored = native_checkpoint.load_domain_checkpoint(
            expected_path, expected_sha256=digest
        )
    except Exception as error:
        return errors + [f"native checkpoint invalid: {error}"]
    if not math.isclose(
        float(restored.getGridDelta()),
        float(case["numerics"]["grid_delta"]),
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        errors.append("checkpoint grid delta differs")
    observed_mesh_hash = domain_mesh_sha256(restored)
    if row.get("native_mesh_sha256") != observed_mesh_hash:
        errors.append("native mesh hash differs")
    if row.get("native_roundtrip_exact") is not True:
        errors.append("native roundtrip was not exact")
    if row.get("checkpoint_format") != "ViennaPS .vpsd":
        errors.append("checkpoint format differs")
    measured, invalid = _measure_domain(restored, case)
    errors.extend(_compare_values(
        measured,
        row.get("selected_cycle_metrics"),
        path="selected_cycle_metrics",
    ))
    if invalid != row.get("selected_metric_invalid_reasons"):
        errors.append("selected metric invalid reasons differ")
    history = row.get("cycle_history")
    selected = eligible = rank = None
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
        if row.get("selection_rank") != (
            list(rank) if rank is not None else None
        ):
            errors.append("selection rank differs")
        last_depth = history[-1].get("depth")
        early = bool(
            isinstance(last_depth, (int, float))
            and last_depth >= case["trajectory"]["early_stop_depth"]
        )
        if row.get("early_stopped") is not early:
            errors.append("early-stop state differs")
        if not early and cycles[-1] != case["trajectory"]["maximum_cycles"]:
            errors.append("trajectory ended before its frozen maximum")
    try:
        initial_geometry = tp.make_initial_geometry(
            radius=case["geometry"]["radius"],
            mask_height=case["geometry"]["mask_height"],
            grid_delta=case["numerics"]["grid_delta"],
            x_extent=case["geometry"]["x_extent"],
            y_extent=case["geometry"]["y_extent"],
            taper=case["recipe"]["mask_taper"],
            hole_shape=ps.HoleShape.FULL,
        )
        initial_mask = screen._mesh_for_material(
            initial_geometry, ps.Material.Mask, required=True
        )
        initial_invalid = []
        initial_pattern = screen.sanitize(
            gate0.measure_pattern(initial_mask, case),
            "initial_pattern",
            initial_invalid,
        )
        errors.extend(_compare_values(
            initial_pattern, row.get("initial_pattern"), path="initial_pattern"
        ))
        if initial_invalid != row.get("initial_pattern_invalid_reasons"):
            errors.append("initial pattern invalid reasons differ")
        gates = screen.classify_gates(initial_pattern, measured, case)
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


def audit_existing_rows(output, cases) -> tuple[dict[str, dict], int]:
    output = Path(output)
    if not output.exists():
        return {}, 0
    expected = {case["case_id"]: case for case in cases}
    successes = {}
    terminal_success = set()
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
        current_case_id = row.get("case_id")
        case = expected.get(current_case_id)
        if case is None:
            raise ValueError(f"unexpected case ID at row {line_number}")
        if current_case_id not in active_case_ids(cases, successes):
            raise ValueError(f"inactive adaptive case at row {line_number}")
        if not row_matches_case(row, case):
            raise ValueError(f"stale case payload at row {line_number}")
        if row.get("evidence_origin") != evidence_origin():
            raise ValueError(f"evidence origin differs at row {line_number}")
        if current_case_id in terminal_success:
            raise ValueError(f"attempt follows success at row {line_number}")
        if row.get("ok") is True:
            errors = validate_success_row(row, case, output)
            if errors:
                raise ValueError(
                    f"invalid success at row {line_number}: " + "; ".join(errors)
                )
            successes[current_case_id] = row
            terminal_success.add(current_case_id)
        elif row.get("ok") is not False:
            raise ValueError(f"row {line_number} lacks a boolean execution status")
    if attempt_count > 14:
        raise ValueError("adaptive execution exceeded fourteen attempted cases")
    return successes, attempt_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    manifest = gate0.strict_json_loads(args.manifest.read_text())
    cases = expand_cases(manifest)
    errors = validate_manifest(manifest, cases)
    if errors:
        raise ValueError("invalid Gate-0 R1 manifest: " + "; ".join(errors))
    if args.output != DEFAULT_OUTPUT:
        raise ValueError("output differs from the frozen execution contract")
    if args.workers != manifest["numerics"]["maximum_workers"]:
        raise ValueError("worker count differs from the frozen execution contract")

    while True:
        successes, attempt_count = audit_existing_rows(args.output, cases)
        active_ids = active_case_ids(cases, successes)
        pending = [
            case for case in cases
            if case["case_id"] in active_ids and case["case_id"] not in successes
        ]
        print(
            f"potential=20 active={len(active_ids)} complete={len(successes)} "
            f"pending={len(pending)} attempts={attempt_count} authority=screen_only",
            flush=True,
        )
        if not pending:
            if not campaign_terminal(cases, successes):
                raise RuntimeError("adaptive campaign has no runnable case")
            return
        if attempt_count + len(pending) > manifest["mask_bracket"][
            "maximum_executed_cases"
        ]:
            raise RuntimeError("Gate-0 R1 fourteen-attempt budget is exhausted")
        tasks = [(case, args.output) for case in pending]
        failed = []
        with futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            submitted = {
                executor.submit(run_case, task): task[0]["case_id"]
                for task in tasks
            }
            for index, completed in enumerate(
                futures.as_completed(submitted), start=1
            ):
                row = completed.result()
                gate0.append_row(args.output, row)
                print(
                    f"[{index}/{len(tasks)}] {row['case_id']} ok={row['ok']} "
                    f"elapsed={row['elapsed_s']:.1f}s",
                    flush=True,
                )
                if row["ok"] is not True:
                    failed.append(row["case_id"])
        if failed:
            raise RuntimeError("Gate-0 R1 cases failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()

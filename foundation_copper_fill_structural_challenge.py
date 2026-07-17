"""Compare copper-fill models on the same material stack."""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import os
import time
import traceback
from pathlib import Path

import numpy as np
import viennals as ls
import viennals.d2 as ls2
import viennaps as ps
import viennaps._core as ps_core

import foundation_copper_fill_trajectory as fill
import foundation_metric_audit as foundation


CANDIDATE_ARM = "candidate_rank1_quasi_steady"
POSITIVE_CONTROL_ARM = "morphology_only_bottom_up_positive_control"
ARMS = (CANDIDATE_ARM, POSITIVE_CONTROL_ARM)
GRID_DELTAS = (0.01, 0.005)
FIXED_RNG_SEED = 94000

ACTIVE_RATE = 0.20
SUPPRESSED_RATE = 0.01
DEACTIVATION_RATE = 0.25
COVERAGE_LAMBDA = 1.25
STICKING_PROBABILITY = 0.025
ADSORPTION_STRENGTH = (
    COVERAGE_LAMBDA * DEACTIVATION_RATE / STICKING_PROBABILITY
)
MAX_DURATION = 8.0

DEFAULT_OUTPUT = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_structural_challenge_rows.jsonl"
)
DEFAULT_SUMMARY_JSON = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_structural_challenge_summary.json"
)
DEFAULT_REVIEW_MD = Path(
    "autoresearch-results/restart_audit/"
    "copper_fill_structural_challenge_review.md"
)

MORPHOLOGY_ONLY_SCOPE = (
    "prescribed exact-stack morphology control; not electrochemistry or a recipe"
)


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@functools.lru_cache(maxsize=1)
def _runtime_fingerprint():
    return {
        "structural_runner_sha256": _file_sha256(Path(__file__).resolve()),
        "foundation_fill_runner_sha256": _file_sha256(
            Path(fill.__file__).resolve()
        ),
        "traveler_metrics_sha256": _file_sha256(Path(fill.tm.__file__).resolve()),
        "tsv_process_sha256": _file_sha256(Path(fill.tp.__file__).resolve()),
        "viennaps_binary_sha256": _file_sha256(Path(ps_core.__file__).resolve()),
    }


def _case(arm, grid_delta):
    if arm not in ARMS:
        raise ValueError(f"unknown structural-challenge arm: {arm}")
    if grid_delta not in GRID_DELTAS:
        raise ValueError(f"unsupported structural-challenge grid: {grid_delta}")
    checkpoint_interval = 2.5 * grid_delta
    case = {
        "arm": arm,
        "geometry": {
            "radius": 0.15,
            "depth": 1.25,
            "mask_height": 0.30,
            "x_extent": 1.0,
            "y_extent": 1.6,
            "field_sample_xs": (-0.40, -0.35, 0.35, 0.40),
            "mouth_offset": 0.02,
        },
        "layers": {"liner": 0.03, "barrier": 0.01, "seed": 0.01},
        "model": {
            "suppressor_sticking_probability": STICKING_PROBABILITY,
            "suppressor_source_power": 1.0,
            "gas_mean_free_path": -1.0,
            "adsorption_strength": ADSORPTION_STRENGTH,
            "deactivation_rate": DEACTIVATION_RATE,
            "active_deposition_rate": ACTIVE_RATE,
            "suppressed_deposition_rate": SUPPRESSED_RATE,
        },
        "numerics": {
            "grid_delta": grid_delta,
            "checkpoint_interval": checkpoint_interval,
            "max_duration": MAX_DURATION,
            "rays_per_point": 1000,
            "max_reflections": 100,
            "max_boundary_hits": 1000,
            "smoothing_neighbors": 1,
            "min_node_distance_factor": 0.05,
            "disk_radius": 0.0,
            "time_step_ratio": 0.4999,
            "threads_per_worker": 1,
        },
        "target": {
            "min_overburden": 0.15,
            "max_balance_error": 1e-10,
            "liner_min_thickness": 0.02,
            "liner_min_conformality": 0.995,
            "barrier_seed_min_thickness": 0.012,
            "barrier_seed_min_conformality": 0.985,
        },
        "rng_seed": FIXED_RNG_SEED,
        "runtime_fingerprint": _runtime_fingerprint(),
    }
    max_front_cells = (
        ACTIVE_RATE * checkpoint_interval / grid_delta
    )
    if max_front_cells > 0.5 + 1e-12:
        raise ValueError("structural challenge permits more than 0.5 cell per checkpoint")
    case["numerical_contract"] = {
        "maximum_front_cells_per_checkpoint": max_front_cells,
        "fixed_rng_seed": FIXED_RNG_SEED,
        "full_exact_material_stack": True,
    }
    case["case_id"] = foundation.case_id(case)
    return case


def case_matrix():
    """Return the frozen four-case structural-challenge matrix."""
    return [_case(arm, grid) for arm in ARMS for grid in GRID_DELTAS]


def _kinematic_geometry(reference):
    x_lo, x_hi = reference["via_x_bounds"]
    height = reference["field_y"] - reference["floor_y"]
    half_width = 0.5 * (x_hi - x_lo)
    return {
        "cavity_height": height,
        "conservative_half_width": half_width,
        "required_floor_to_lower_wall_velocity_ratio": height / half_width,
        "region_definition": {
            "analysis_x_padding": 0.02,
            "analysis_y_padding": 0.03,
            "floor_max_y_above_floor": 0.04,
            "floor_max_abs_x_fraction_of_half_width": 0.70,
            "lower_wall_height_fraction": (0.15, 0.45),
            "lower_wall_min_abs_x_fraction_of_half_width": 0.65,
        },
    }


def _region_masks(coordinates, reference):
    coordinates = np.asarray(coordinates, dtype=float)
    x = coordinates[:, 0]
    y = coordinates[:, 1]
    x_lo, x_hi = reference["via_x_bounds"]
    floor_y = reference["floor_y"]
    field_y = reference["field_y"]
    height = field_y - floor_y
    half_width = 0.5 * (x_hi - x_lo)
    in_analysis = (
        (x >= x_lo - 0.02)
        & (x <= x_hi + 0.02)
        & (y >= floor_y - 0.03)
        & (y <= field_y + 0.03)
    )
    floor = (
        in_analysis
        & (y <= floor_y + 0.04)
        & (np.abs(x) <= 0.70 * half_width)
    )
    lower_wall = (
        in_analysis
        & (y >= floor_y + 0.15 * height)
        & (y <= floor_y + 0.45 * height)
        & (np.abs(x) >= 0.65 * half_width)
    )
    return floor, lower_wall


def _candidate_region_rates(raw, reference):
    floor_mask, lower_mask = _region_masks(raw["coordinates"], reference)

    def mean(name, mask):
        return (
            float(np.mean(np.asarray(raw[name], dtype=float)[mask]))
            if np.any(mask)
            else None
        )

    floor_velocity = mean("velocity", floor_mask)
    lower_velocity = mean("velocity", lower_mask)
    return {
        "source": "candidate diagnostic surface",
        "floor_point_count": int(np.count_nonzero(floor_mask)),
        "lower_wall_point_count": int(np.count_nonzero(lower_mask)),
        "floor_flux_mean": mean("suppressor_flux", floor_mask),
        "lower_wall_flux_mean": mean("suppressor_flux", lower_mask),
        "floor_coverage_mean": mean("coverage", floor_mask),
        "lower_wall_coverage_mean": mean("coverage", lower_mask),
        "floor_velocity_mean": floor_velocity,
        "lower_wall_velocity_mean": lower_velocity,
        "floor_to_lower_wall_velocity_ratio": (
            floor_velocity / lower_velocity
            if floor_velocity is not None and lower_velocity
            else None
        ),
    }


class PrescribedBottomUpVelocity(ls.VelocityField):
    """Morphology-only rate field on the exact material stack."""

    def __init__(self, reference, grid_delta, stage):
        super().__init__()
        if stage not in {"bottom_up_fill", "uniform_overburden"}:
            raise ValueError(f"unknown positive-control stage: {stage}")
        self.reference = reference
        self.grid_delta = grid_delta
        self.stage = stage
        self.floor_samples = []
        self.lower_wall_samples = []

    def _region(self, coordinate):
        x, y = float(coordinate[0]), float(coordinate[1])
        x_lo, x_hi = self.reference["via_x_bounds"]
        floor_y = self.reference["floor_y"]
        field_y = self.reference["field_y"]
        height = field_y - floor_y
        half_width = 0.5 * (x_hi - x_lo)
        in_analysis = (
            x_lo - 0.02 <= x <= x_hi + 0.02
            and floor_y - 0.03 <= y <= field_y + 0.03
        )
        if (
            in_analysis
            and y <= floor_y + 0.04
            and abs(x) <= 0.70 * half_width
        ):
            return "floor"
        if (
            in_analysis
            and floor_y + 0.15 * height <= y <= floor_y + 0.45 * height
            and abs(x) >= 0.65 * half_width
        ):
            return "lower_wall"
        return None

    def getScalarVelocity(self, coordinate, material, normal, point_id):
        if material not in {3, 4}:
            speed = 0.0
        elif self.stage == "uniform_overburden":
            speed = ACTIVE_RATE
        else:
            x_lo, x_hi = self.reference["via_x_bounds"]
            in_via = x_lo < coordinate[0] < x_hi
            below_field = (
                coordinate[1]
                < self.reference["field_y"] + 1.5 * self.grid_delta
            )
            upward_facing = normal[1] > 0.45
            speed = (
                ACTIVE_RATE
                if in_via and below_field and upward_facing
                else SUPPRESSED_RATE
            )
        region = self._region(coordinate)
        if region == "floor":
            self.floor_samples.append(speed)
        elif region == "lower_wall":
            self.lower_wall_samples.append(speed)
        return speed

    def getVectorVelocity(self, coordinate, material, normal, point_id):
        return (0.0, 0.0, 0.0)

    def region_rates(self):
        floor_velocity = (
            float(np.mean(self.floor_samples)) if self.floor_samples else None
        )
        lower_velocity = (
            float(np.mean(self.lower_wall_samples))
            if self.lower_wall_samples
            else None
        )
        return {
            "source": MORPHOLOGY_ONLY_SCOPE,
            "floor_point_count": len(self.floor_samples),
            "lower_wall_point_count": len(self.lower_wall_samples),
            "floor_velocity_mean": floor_velocity,
            "lower_wall_velocity_mean": lower_velocity,
            "floor_to_lower_wall_velocity_ratio": (
                floor_velocity / lower_velocity
                if floor_velocity is not None and lower_velocity
                else None
            ),
        }


def _advect_positive_control(geometry, velocity, duration, case):
    advection = ls2.Advect()
    for level_set in geometry.getLevelSets():
        advection.insertNextLevelSet(level_set)
    advection.setVelocityField(velocity)
    advection.setCalculateNormalVectors(True)
    advection.setIgnoreVoids(True)
    advection.setTimeStepRatio(case["numerics"]["time_step_ratio"])
    advection.setSpatialScheme(ls.SpatialSchemeEnum.ENGQUIST_OSHER_1ST_ORDER)
    advection.setTemporalScheme(ls.TemporalSchemeEnum.RUNGE_KUTTA_2ND_ORDER)
    advection.setAdvectionTime(duration)
    advection.apply()


def _topology(geometry, reference, case):
    mesh = fill.tm.raw_level_set_meshes(geometry)[-1]
    return fill._fill_topology_metrics_2d(
        mesh,
        field_y=reference["field_y"],
        floor_y=reference["floor_y"],
        via_x_bounds=reference["via_x_bounds"],
        field_sample_xs=reference["field_sample_xs"],
        center_x=0.0,
        tolerance=0.1 * case["numerics"]["grid_delta"],
        initial_cavity_area=reference["initial_cavity_area"],
        grid_delta=case["numerics"]["grid_delta"],
        mouth_sample_y=reference["mouth_sample_y"],
        area_sample_count=reference["metric_sampling"]["area_sample_count"],
        overburden_sample_count=reference["metric_sampling"][
            "overburden_sample_count"
        ],
    )


def _failure_types(topology, transition, protected, diagnostics_valid):
    failures = []
    if topology.get("degenerate_closed_component_count", 0):
        failures.append("degenerate_closed_fragment")
    if not topology["topology_valid"]:
        failures.append("invalid_topology")
    if topology["pinch_off_failure"] or topology["closed_void_count"]:
        failures.append("pinch_off_or_closed_void")
    if not transition["valid"]:
        failures.append(transition["classification"])
    if not protected["survives"]:
        failures.append("protected_stack_changed")
    if not diagnostics_valid:
        failures.append("invalid_model_diagnostic")
    return sorted(set(failures))


def _mechanism_classification(outcome, failure_types):
    if outcome == "target_pass":
        return "resolved_bottom_up_target"
    lateral_failures = {
        "pinch_off_or_closed_void",
        "unresolved_narrow_tail_merger",
        "nonconservative_or_unmeasurable_cavity_loss",
    }
    if lateral_failures.intersection(failure_types):
        return "lateral_closure_failure"
    return "other_failure_or_censor"


@functools.lru_cache(maxsize=4)
def run_structural_case(arm, grid_delta):
    """Run one of the four frozen structural-challenge cases in memory."""
    case = _case(arm, grid_delta)
    started = time.time()
    if arm == CANDIDATE_ARM and not hasattr(ps, "CopperSuppressionFill"):
        raise RuntimeError("qualified CopperSuppressionFill binding is unavailable")
    ps.setNumThreads(1)
    ls.setNumThreads(1)

    geometry = fill._build_seeded_stack(case)
    reference = fill._reference_geometry(geometry, case)
    fill._validate_material_stack(geometry)
    kinematics = _kinematic_geometry(reference)
    numerical_invariants = {
        "max_front_displacement": ACTIVE_RATE
        * case["numerics"]["checkpoint_interval"],
        "max_front_cells_per_checkpoint": case["numerical_contract"][
            "maximum_front_cells_per_checkpoint"
        ],
    }
    trajectory = []
    elapsed = 0.0
    stage = "candidate" if arm == CANDIDATE_ARM else "bottom_up_fill"
    void_free_event_seen = False
    overburden_stage_seen = False
    all_failure_types = set()
    first_failure_types = []
    target_pass = False
    checkpoint_count = int(
        math.ceil(MAX_DURATION / case["numerics"]["checkpoint_interval"])
    )

    for checkpoint in range(1, checkpoint_count + 1):
        duration = min(
            case["numerics"]["checkpoint_interval"], MAX_DURATION - elapsed
        )
        previous_mesh = fill.tm.raw_level_set_meshes(geometry)[-1]
        previous_topology = (
            trajectory[-1]["topology"]
            if trajectory
            else reference["initial_topology"]
        )
        if arm == CANDIDATE_ARM:
            model = ps.CopperSuppressionFill(fill._model_parameters(case))
            process = ps.Process(geometry, model, duration)
            fill._set_process_parameters(process, case, checkpoint)
            process.apply()
            diagnostics, raw = fill._model_diagnostics(model, reference, case)
            region_rates = _candidate_region_rates(raw, reference)
            diagnostics_valid = diagnostics["valid"]
        else:
            velocity = PrescribedBottomUpVelocity(
                reference, grid_delta, stage
            )
            _advect_positive_control(geometry, velocity, duration, case)
            region_rates = velocity.region_rates()
            diagnostics_valid = True

        elapsed += duration
        meshes = fill.tm.raw_level_set_meshes(geometry)
        topology = _topology(geometry, reference, case)
        transition = fill._topology_transition_check(
            previous_topology,
            topology,
            numerical_invariants,
            grid_delta,
            previous_mesh=previous_mesh,
            reference=reference,
        )
        protected = fill._protected_stack_delta(
            reference["protected_meshes"], meshes[:-1]
        )
        failures = _failure_types(
            topology, transition, protected, diagnostics_valid
        )
        all_failure_types.update(failures)
        if failures and not first_failure_types:
            first_failure_types = failures

        if (
            arm == POSITIVE_CONTROL_ARM
            and stage == "bottom_up_fill"
            and topology["void_free"]
            and not all_failure_types
        ):
            void_free_event_seen = True
            stage = "uniform_overburden"
        if stage == "uniform_overburden":
            overburden_stage_seen = True

        target_pass = bool(
            topology["topology_valid"]
            and topology["void_free"]
            and topology["overburden_min"] >= case["target"]["min_overburden"]
            and not all_failure_types
            and protected["survives"]
            and diagnostics_valid
        )
        trajectory.append(
            foundation.jsonable(
                {
                    "checkpoint": checkpoint,
                    "elapsed": elapsed,
                    "stage": stage,
                    "topology": topology,
                    "topology_transition": transition,
                    "protected_stack": protected,
                    "region_rates": region_rates,
                    "kinematic_threshold": kinematics[
                        "required_floor_to_lower_wall_velocity_ratio"
                    ],
                    "failure_types": failures,
                    "target_pass": target_pass,
                }
            )
        )
        if target_pass or failures or duration <= 0.0:
            break

    outcome = (
        "target_pass"
        if target_pass
        else "hard_failure"
        if all_failure_types
        else "censored"
    )
    classification = _mechanism_classification(outcome, all_failure_types)
    return foundation.jsonable(
        {
            "ok": True,
            "case_id": case["case_id"],
            "runtime_fingerprint": case["runtime_fingerprint"],
            "arm": arm,
            "scope": (
                "uncalibrated candidate structural challenge"
                if arm == CANDIDATE_ARM
                else MORPHOLOGY_ONLY_SCOPE
            ),
            "grid_delta": grid_delta,
            "checkpoint_interval": case["numerics"]["checkpoint_interval"],
            "rng_seed": FIXED_RNG_SEED,
            "case": case,
            "reference": {
                key: value
                for key, value in reference.items()
                if key != "protected_meshes"
            },
            "kinematics": kinematics,
            "trajectory": trajectory,
            "outcome": outcome,
            "mechanism_classification": classification,
            "target_pass": target_pass,
            "void_free_event_seen": void_free_event_seen,
            "overburden_stage_seen": overburden_stage_seen,
            "first_failure_types": first_failure_types,
            "all_failure_types": sorted(all_failure_types),
            "protected_stack_survives": bool(
                trajectory
                and all(row["protected_stack"]["survives"] for row in trajectory)
            ),
            "elapsed_s": time.time() - started,
        }
    )


def run_structural_challenge():
    """Run the frozen four cases and report grid-level classification agreement."""
    results = [
        run_structural_case(arm, grid)
        for arm in ARMS
        for grid in GRID_DELTAS
    ]
    agreement = {}
    for arm in ARMS:
        classifications = {
            result["mechanism_classification"]
            for result in results
            if result["arm"] == arm
        }
        agreement[arm] = {
            "agrees": len(classifications) == 1,
            "classifications": sorted(classifications),
        }
    return {"cases": results, "grid_classification_agreement": agreement}


def _row_validation_errors(row, case):
    errors = []
    expected_case = foundation.jsonable(case)
    if not isinstance(row, dict):
        return ["attempt is not a JSON object"]
    if row.get("ok") is not True:
        errors.append("attempt is not successful")
    if row.get("case_id") != case["case_id"]:
        errors.append("case_id does not match the current matrix")
    if row.get("runtime_fingerprint") != case["runtime_fingerprint"]:
        errors.append("runtime fingerprint does not match the current matrix")
    if row.get("case") != expected_case:
        errors.append("embedded case payload does not match the current matrix")
    if row.get("arm") != case["arm"]:
        errors.append("arm does not match the current matrix")
    if row.get("grid_delta") != case["numerics"]["grid_delta"]:
        errors.append("grid does not match the current matrix")
    if row.get("rng_seed") != case["rng_seed"]:
        errors.append("fixed seed does not match the current matrix")
    if row.get("outcome") not in {"target_pass", "hard_failure", "censored"}:
        errors.append("outcome is missing or invalid")
    if not isinstance(row.get("mechanism_classification"), str):
        errors.append("mechanism classification is missing")
    if row.get("target_pass") != (row.get("outcome") == "target_pass"):
        errors.append("target_pass disagrees with outcome")
    if not isinstance(row.get("protected_stack_survives"), bool):
        errors.append("protected-stack result is missing")
    trajectory = row.get("trajectory")
    if not isinstance(trajectory, list) or not trajectory:
        errors.append("trajectory is missing")
    else:
        terminal = trajectory[-1]
        if not isinstance(terminal.get("topology"), dict):
            errors.append("terminal topology is missing")
        if not isinstance(terminal.get("topology_transition"), dict):
            errors.append("terminal topology transition is missing")
        if not isinstance(trajectory[0].get("region_rates"), dict):
            errors.append("initial region-rate diagnostic is missing")
    return errors


def _read_attempts(path):
    attempts = []
    parse_errors = []
    if not path.exists():
        return attempts, parse_errors
    for line_number, text in enumerate(path.read_text().splitlines(), start=1):
        if not text.strip():
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as error:
            parse_errors.append({
                "line_number": line_number,
                "error": str(error),
            })
            continue
        attempts.append({"line_number": line_number, "row": row})
    return attempts, parse_errors


def _selected_valid_rows(path, cases=None):
    cases = case_matrix() if cases is None else cases
    expected = {case["case_id"]: case for case in cases}
    attempts, parse_errors = _read_attempts(path)
    valid_by_case = {case_id: [] for case_id in expected}
    invalid_attempts = []
    for attempt in attempts:
        row = attempt["row"]
        case_id = row.get("case_id") if isinstance(row, dict) else None
        case = expected.get(case_id)
        errors = (
            ["case_id is not in the current fingerprint-bound matrix"]
            if case is None
            else _row_validation_errors(row, case)
        )
        if errors:
            invalid_attempts.append({
                "line_number": attempt["line_number"],
                "case_id": case_id,
                "errors": errors,
            })
        else:
            valid_by_case[case_id].append(attempt)
    selected = {
        case_id: rows[-1]["row"]
        for case_id, rows in valid_by_case.items()
        if rows
    }
    duplicate_valid = sorted(
        case_id for case_id, rows in valid_by_case.items() if len(rows) > 1
    )
    return {
        "attempt_count": len(attempts),
        "parse_errors": parse_errors,
        "invalid_attempts": invalid_attempts,
        "valid_attempt_count": sum(len(rows) for rows in valid_by_case.values()),
        "selected": selected,
        "duplicate_valid_case_ids": duplicate_valid,
    }


def valid_completed_case_ids(path, cases=None):
    """Return only successful, current-fingerprint, payload-valid case IDs."""
    return set(_selected_valid_rows(path, cases)["selected"])


def _compact_case_review(row):
    initial = row["trajectory"][0]
    terminal = row["trajectory"][-1]
    topology = terminal["topology"]
    exact_topology_keys = (
        "topology_valid",
        "open_void",
        "open_void_depth",
        "remaining_void_area",
        "fill_fraction",
        "closed_void_count",
        "maximum_void_width",
        "maximum_void_height",
        "mouth_aperture",
        "void_free",
        "center_overburden",
        "field_overburden_min",
        "overburden_min",
        "overburden_mean",
        "overburden_nonuniformity",
    )
    return {
        "case_id": row["case_id"],
        "arm": row["arm"],
        "grid_delta": row["grid_delta"],
        "rng_seed": row["rng_seed"],
        "outcome": row["outcome"],
        "mechanism_classification": row["mechanism_classification"],
        "target_pass": row["target_pass"],
        "first_failure_types": row["first_failure_types"],
        "all_failure_types": row["all_failure_types"],
        "protected_stack_survives": row["protected_stack_survives"],
        "terminal_checkpoint": terminal["checkpoint"],
        "terminal_elapsed": terminal["elapsed"],
        "terminal_stage": terminal["stage"],
        "terminal_transition_classification": terminal[
            "topology_transition"
        ]["classification"],
        "terminal_topology": {
            key: topology.get(key) for key in exact_topology_keys
        },
        "initial_region_rates": initial["region_rates"],
        "required_floor_to_lower_wall_velocity_ratio": row["kinematics"][
            "required_floor_to_lower_wall_velocity_ratio"
        ],
        "elapsed_s": row.get("elapsed_s"),
    }


def review_output(path, cases=None):
    """Critically select current valid attempts and summarize exact outcomes."""
    cases = case_matrix() if cases is None else cases
    selected_attempts = _selected_valid_rows(path, cases)
    selected = selected_attempts["selected"]
    case_reviews = [
        _compact_case_review(selected[case["case_id"]])
        for case in cases
        if case["case_id"] in selected
    ]
    grid_agreement = {}
    for arm in ARMS:
        rows = [row for row in case_reviews if row["arm"] == arm]
        classifications = sorted({
            row["mechanism_classification"] for row in rows
        })
        outcomes = sorted({row["outcome"] for row in rows})
        grid_agreement[arm] = {
            "complete": len(rows) == len(GRID_DELTAS),
            "agrees": (
                len(rows) == len(GRID_DELTAS)
                and len(classifications) == 1
                and len(outcomes) == 1
            ),
            "classifications": classifications,
            "outcomes": outcomes,
        }
    complete = len(case_reviews) == len(cases)
    conclusion_accepted = bool(
        complete
        and grid_agreement[CANDIDATE_ARM]["agrees"]
        and grid_agreement[POSITIVE_CONTROL_ARM]["agrees"]
        and grid_agreement[CANDIDATE_ARM]["classifications"]
        == ["lateral_closure_failure"]
        and grid_agreement[POSITIVE_CONTROL_ARM]["classifications"]
        == ["resolved_bottom_up_target"]
    )
    return {
        "status": "complete" if complete else "incomplete",
        "review_scope": (
            "exact-stack structural model/representation challenge; not a recipe DOE"
        ),
        "output_path": str(path),
        "expected_case_count": len(cases),
        "selected_valid_case_count": len(case_reviews),
        "missing_case_ids": [
            case["case_id"] for case in cases if case["case_id"] not in selected
        ],
        "runtime_fingerprint": _runtime_fingerprint(),
        "attempt_count": selected_attempts["attempt_count"],
        "valid_attempt_count": selected_attempts["valid_attempt_count"],
        "invalid_attempts": selected_attempts["invalid_attempts"],
        "parse_errors": selected_attempts["parse_errors"],
        "duplicate_valid_case_ids": selected_attempts[
            "duplicate_valid_case_ids"
        ],
        "grid_classification_agreement": grid_agreement,
        "structural_conclusion": {
            "accepted": conclusion_accepted,
            "classification": (
                "candidate_rate_law_rejected_representation_control_passed"
                if conclusion_accepted
                else "await_complete_grid_agreement"
            ),
            "reason": (
                "The candidate fails by lateral closure on both grids while "
                "the prescribed bottom-up control reaches void-free positive "
                "overburden on the same protected material stack."
                if conclusion_accepted
                else "All four current-fingerprint cases are required."
            ),
        },
        "cases": case_reviews,
    }


def _fmt(value):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.8g}"
    return str(value)


def review_markdown(summary):
    lines = [
        "# Cu-fill exact-stack structural challenge",
        "",
        f"Status: **{summary['status']}**. Valid current cases: "
        f"{summary['selected_valid_case_count']}/{summary['expected_case_count']}.",
        "",
        "This is a model/representation challenge, not an electroplating recipe DOE.",
        "",
        "| Arm | Grid | Outcome | Mechanism | Time | Void free | Closed voids | Remaining void | Open depth | Mouth | Min overburden | Initial floor/wall | Required | Protected |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["cases"]:
        topology = row["terminal_topology"]
        initial_ratio = row["initial_region_rates"].get(
            "floor_to_lower_wall_velocity_ratio"
        )
        lines.append(
            f"| {row['arm']} | {_fmt(row['grid_delta'])} | "
            f"{row['outcome']} | {row['mechanism_classification']} | "
            f"{_fmt(row['terminal_elapsed'])} | {_fmt(topology['void_free'])} | "
            f"{_fmt(topology['closed_void_count'])} | "
            f"{_fmt(topology['remaining_void_area'])} | "
            f"{_fmt(topology['open_void_depth'])} | "
            f"{_fmt(topology['mouth_aperture'])} | "
            f"{_fmt(topology['overburden_min'])} | {_fmt(initial_ratio)} | "
            f"{_fmt(row['required_floor_to_lower_wall_velocity_ratio'])} | "
            f"{_fmt(row['protected_stack_survives'])} |"
        )
    lines.extend(["", "## Grid agreement", ""])
    for arm, agreement in summary["grid_classification_agreement"].items():
        lines.append(
            f"- `{arm}`: {'agree' if agreement['agrees'] else 'not established'}; "
            f"classification={', '.join(agreement['classifications']) or 'missing'}; "
            f"outcome={', '.join(agreement['outcomes']) or 'missing'}."
        )
    conclusion = summary["structural_conclusion"]
    lines.extend([
        "",
        "## Reviewed conclusion",
        "",
        f"**{conclusion['classification']}** — {conclusion['reason']}",
        "",
        f"Attempts retained: {summary['attempt_count']}; valid attempts: "
        f"{summary['valid_attempt_count']}; invalid attempts: "
        f"{len(summary['invalid_attempts'])}; parse errors: "
        f"{len(summary['parse_errors'])}.",
        "",
    ])
    return "\n".join(lines)


def _atomic_write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_review_artifacts(summary, summary_json, review_md):
    _atomic_write_text(
        summary_json, json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    _atomic_write_text(review_md, review_markdown(summary))


def execute_case(case):
    """Run one case and retain a fingerprinted error attempt if it fails."""
    started = time.time()
    try:
        row = run_structural_case(
            case["arm"], case["numerics"]["grid_delta"]
        )
        errors = _row_validation_errors(row, case)
        if errors:
            raise ValueError(f"completed row failed validation: {errors}")
        return row
    except Exception as error:
        return foundation.jsonable({
            "ok": False,
            "case_id": case["case_id"],
            "runtime_fingerprint": case["runtime_fingerprint"],
            "case": case,
            "arm": case["arm"],
            "grid_delta": case["numerics"]["grid_delta"],
            "rng_seed": case["rng_seed"],
            "error": repr(error),
            "traceback": traceback.format_exc(),
            "elapsed_s": time.time() - started,
        })


def run_resumable(output, summary_json, review_md):
    """Append each pending case immediately and refresh reviewed artifacts."""
    cases = case_matrix()
    completed = valid_completed_case_ids(output, cases)
    pending = [case for case in cases if case["case_id"] not in completed]
    print(
        f"structural cases={len(cases)} valid={len(completed)} "
        f"pending={len(pending)}",
        flush=True,
    )
    for index, case in enumerate(pending, start=1):
        row = execute_case(case)
        foundation.append_row(output, row)
        summary = review_output(output, cases)
        write_review_artifacts(summary, summary_json, review_md)
        print(
            f"[{index}/{len(pending)}] {case['case_id']} "
            f"arm={case['arm']} grid={case['numerics']['grid_delta']} "
            f"ok={row['ok']} outcome={row.get('outcome')}",
            flush=True,
        )
    summary = review_output(output, cases)
    write_review_artifacts(summary, summary_json, review_md)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON
    )
    parser.add_argument("--review-md", type=Path, default=DEFAULT_REVIEW_MD)
    args = parser.parse_args()
    summary = run_resumable(args.output, args.summary_json, args.review_md)
    if summary["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

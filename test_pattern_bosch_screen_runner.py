"""Synthetic guards for the broad pattern/Bosch executor."""

import copy
from pathlib import Path
import tempfile

import numpy as np

import build_pattern_bosch_screen_design as builder
import pattern_bosch_screen_runner as runner


def manifest():
    spec = builder.strict_load(builder.DEFAULT_SPEC)
    design = builder.build_design(spec)
    return {
        "manifest_version": 1,
        "campaign": "pattern-bosch-broad-screen",
        "labels": ["full-traveler", "critical-review"],
        "design": design,
        "execution": {
            "output": str(runner.DEFAULT_OUTPUT),
            "maximum_workers": 2,
            "threads_per_worker": 7,
            "executor": "direct_checkpointed_batch_no_llm",
        },
        "runtime_fingerprint": runner.runtime_fingerprint(),
        "source_artifacts": {
            "gate0_summary": {"path": "gate0.json", "sha256": "a" * 64},
            "handoff_summary": {"path": "handoff.json", "sha256": "b" * 64},
        },
        "authority": design["authority"],
    }


def test_exact_640_case_matrix_and_rng_horizon():
    frozen = manifest()
    errors = runner.validate_manifest(
        frozen, check_runtime=True, check_prerequisites=False
    )
    assert errors == [
        "superseded repeat-heavy screen methodology; follow RESEARCH_PLAN_V3.md"
    ]
    cases = runner.expand_cases(frozen)
    assert len(cases) == 640
    assert len({case["case_id"] for case in cases}) == 640
    assert len({case["recipe_id"] for case in cases}) == 160
    for case in cases:
        assert case["rng_stream"]["process_seed_horizon"] == 151
        assert case["rng_stream"]["last_process_seed"] == case["rng_seed"] + 150
        assert case["labels"] == ["full-traveler", "critical-review"]
        assert not case["authority"]["recipe_authorized"]


def test_depth_selection_ignores_shape_and_includes_fast_cycles():
    case = runner.expand_cases(manifest())[0]
    history = [
        {"cycle": 0, "depth": 1.249, "metrics_valid": True, "max_bow": 0.0},
        {"cycle": 1, "depth": 1.18, "metrics_valid": True, "max_bow": 9.0},
        {"cycle": 2, "depth": 1.249, "metrics_valid": True, "max_bow": 8.0},
        {"cycle": 3, "depth": 1.251, "metrics_valid": True, "max_bow": 0.0},
    ]
    selected, eligible, rank = runner.select_depth_matched(history, case)
    assert eligible
    assert selected["cycle"] == 2
    assert rank[0] == 0

    invalid = copy.deepcopy(history)
    invalid[2]["metrics_valid"] = False
    selected, eligible, _ = runner.select_depth_matched(invalid, case)
    assert selected["cycle"] == 3
    assert eligible


def test_invalid_metrics_become_visible_nulls_and_fail_gates():
    reasons = []
    sanitized = runner.sanitize(
        {"depth": float("nan"), "bow": np.asarray([0.1, np.inf])},
        invalid=reasons,
    )
    assert sanitized == {"depth": None, "bow": [0.1, None]}
    assert len(reasons) == 2
    case = runner.expand_cases(manifest())[0]
    gates = runner.classify_gates(
        {"opening_cd_bottom": 0.3, "mask_height": 0.3, "opening_valid": True},
        {"etch": {"depth": None, "max_cd_error": None, "max_bow": None}},
        case,
    )
    assert gates["pattern_pass"]
    assert not gates["etch_pass"]
    assert not runner.combined_hard_gate_pass(False, {
        "pattern_pass": True, "etch_pass": True
    })
    assert runner.combined_hard_gate_pass(True, {
        "pattern_pass": True, "etch_pass": True
    })


def synthetic_mesh():
    nodes = np.asarray([
        [-0.5, 0.0, 0.0],
        [-0.15, 0.0, 0.0],
        [-0.15, -1.25, 0.0],
        [0.15, -1.25, 0.0],
        [0.15, 0.0, 0.0],
        [0.5, 0.0, 0.0],
    ])
    lines = np.column_stack((np.arange(5), np.arange(1, 6)))
    return {"nodes": nodes, "lines": lines}


def test_checkpoint_and_resume_are_hash_bound_and_fail_closed():
    case = runner.expand_cases(manifest())[0]
    mesh = synthetic_mesh()
    snapshot = {"cycle": 12, "silicon": mesh, "mask": mesh}
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        checkpoint = runner.checkpoint_path(output, case["case_id"])
        digest = runner.save_checkpoint(
            checkpoint, case, mesh, snapshot, True
        )
        assert runner.validate_checkpoint(checkpoint, case, digest) == []
        row = {
            **case,
            "ok": True,
            "selected_cycle": 12,
            "selection_eligible": True,
            "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": digest,
        }
        runner.foundation.append_row(output, row)
        assert runner.audit_existing_rows(output, [case]) == {case["case_id"]}

        runner.foundation.append_row(output, row)
        try:
            runner.audit_existing_rows(output, [case])
        except ValueError as error:
            assert "attempt follows success" in str(error)
        else:
            raise AssertionError("duplicate success was accepted")


def test_manifest_target_design_and_authority_mutations_fail():
    frozen = manifest()
    changed = copy.deepcopy(frozen)
    changed["design"]["target"]["opening_cd"] = 0.31
    assert runner.validate_manifest(
        changed, check_runtime=False, check_prerequisites=False
    )
    changed = copy.deepcopy(frozen)
    changed["authority"]["recipe_authorized"] = True
    assert runner.validate_manifest(
        changed, check_runtime=False, check_prerequisites=False
    )


def test_run_case_depth_selects_and_early_stops_without_retaining_last_shape():
    case = runner.expand_cases(manifest())[0]
    mesh = synthetic_mesh()
    depths = {0: 0.5, 1: 1.1, 2: 1.24, 3: 1.5}

    class Geometry:
        cycle = 0

    geometry = Geometry()
    original_make = runner.tp.make_initial_geometry
    original_etch = runner.tp.bosch_etch
    original_mesh = runner._mesh_for_material
    original_pattern = runner.gate0.measure_pattern
    original_measure = runner.gate0.measure_selected_cycle

    def fake_etch(current, *, on_cycle, **_kwargs):
        for cycle in range(4):
            current.cycle = cycle
            on_cycle(current, cycle)

    def fake_mesh(current, material, *, required):
        if material == runner.ps.Material.Mask:
            return mesh
        return {**mesh, "cycle": current.cycle}

    def fake_measure(silicon, _mask, _case):
        depth = depths[silicon["cycle"]]
        etch = {
            "depth": depth,
            "cd_top": 0.3,
            "cd_middle": 0.3,
            "cd_bottom": 0.3,
            "cd_min": 0.3,
            "cd_max": 0.3,
            "max_cd_error": 0.0,
            "sidewall_angle_deg": 0.0,
            "max_bow": 0.0,
            "scallop_rms": 0.0,
            "sample_fractions": [],
            "sample_cds": [],
        }
        return {
            "etch": etch,
            "mask_remaining_height": 0.3,
            "post_etch_mask": {"opening_valid": True},
        }

    try:
        runner.tp.make_initial_geometry = lambda **_kwargs: geometry
        runner.tp.bosch_etch = fake_etch
        runner._mesh_for_material = fake_mesh
        runner.gate0.measure_pattern = lambda _mask, _case: {
            "opening_cd_bottom": 0.3,
            "mask_height": 0.3,
            "opening_valid": True,
        }
        runner.gate0.measure_selected_cycle = fake_measure
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rows.jsonl"
            row = runner.run_case((case, output))
            assert row["ok"]
            assert row["early_stopped"]
            assert row["last_recorded_cycle"] == 3
            assert row["selected_cycle"] == 2
            assert row["selection_eligible"]
            assert row["hard_gate_pass"]
            assert runner.validate_checkpoint(
                row["checkpoint_path"],
                case,
                row["checkpoint_sha256"],
                expected_selected_cycle=2,
                expected_selection_eligible=True,
            ) == []
    finally:
        runner.tp.make_initial_geometry = original_make
        runner.tp.bosch_etch = original_etch
        runner._mesh_for_material = original_mesh
        runner.gate0.measure_pattern = original_pattern
        runner.gate0.measure_selected_cycle = original_measure


if __name__ == "__main__":
    test_exact_640_case_matrix_and_rng_horizon()
    test_depth_selection_ignores_shape_and_includes_fast_cycles()
    test_invalid_metrics_become_visible_nulls_and_fail_gates()
    test_checkpoint_and_resume_are_hash_bound_and_fail_closed()
    test_manifest_target_design_and_authority_mutations_fail()
    test_run_case_depth_selects_and_early_stops_without_retaining_last_shape()
    print("pattern/Bosch broad-screen runner checks: PASS")

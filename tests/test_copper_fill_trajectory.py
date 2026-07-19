"""Resume and artifact guards for the candidate Cu-fill trajectory runner."""

import copy
import json
import tempfile
from pathlib import Path

import numpy as np
import viennaps as ps

import foundation_copper_fill_trajectory as trajectory


def test_one_checkpoint_resumes_without_reexecution_and_saves_diagnostics():
    manifest = json.loads(
        trajectory.DEFAULT_MANIFEST.read_text()
    )
    manifest["numerics"]["max_duration"] = 0.10
    case = trajectory.expand_cases(manifest)[1]
    root = Path(tempfile.mkdtemp(prefix="copper-fill-trajectory-test-"))
    task = (case, root / "snapshots", root / "progress")

    first_chunk = copy.deepcopy(case)
    first_chunk["numerics"]["max_duration"] = 0.05
    first = trajectory.run_case(
        (first_chunk, root / "snapshots", root / "progress")
    )
    second = trajectory.run_case(task)
    assert first["ok"] and second["ok"]
    assert first["last_checkpoint"] == 1
    assert first["resumed_from_checkpoint"] is None
    assert second["resumed_from_checkpoint"] == 1
    assert second["last_checkpoint"] == 2
    assert len(second["trajectory"]) == 2
    assert second["trajectory"][0] == first["trajectory"][0]
    assert second["trajectory"][-1]["elapsed"] == 0.10

    snapshot_path = Path(second["trajectory"][-1]["snapshot_path"])
    with np.load(snapshot_path) as snapshot:
        assert {
            "nodes",
            "lines",
            "diagnostic_coordinates",
            "diagnostic_material_ids",
            "diagnostic_suppressor_flux",
            "diagnostic_coverage",
            "diagnostic_velocity",
            "diagnostic_adsorption_term",
            "diagnostic_deactivation_term",
        } <= set(snapshot.files)


def test_named_seed_material_survives_domain_roundtrip():
    manifest = json.loads(trajectory.DEFAULT_MANIFEST.read_text())
    case = trajectory.expand_cases(manifest)[0]
    original = trajectory._build_seeded_stack(case)
    root = Path(tempfile.mkdtemp(prefix="copper-fill-domain-test-"))
    path = root / "stack.vpsd"
    ps.Writer(original, str(path)).apply()
    restored = ps.Domain()
    ps.Reader(restored, str(path)).apply()

    assert trajectory._validate_material_stack(original) == (
        trajectory._validate_material_stack(restored)
    )
    original_meshes = trajectory.tm.raw_level_set_meshes(original)
    restored_meshes = trajectory.tm.raw_level_set_meshes(restored)
    for before, after in zip(original_meshes, restored_meshes):
        assert np.array_equal(before["lines"], after["lines"])
        assert np.array_equal(before["nodes"], after["nodes"])


def test_only_valid_rows_are_considered_complete():
    root = Path(tempfile.mkdtemp(prefix="copper-fill-row-test-"))
    rows = root / "rows.jsonl"
    rows.write_text(
        json.dumps({"case_id": "failed", "ok": False}) + "\n"
        + json.dumps({"case_id": "valid", "ok": True}) + "\n"
    )
    assert trajectory._successful_case_ids(rows) == {"valid"}


def test_case_ids_bind_runtime_and_limit_checkpoint_motion():
    manifest = json.loads(trajectory.DEFAULT_MANIFEST.read_text())
    case = trajectory.expand_cases(manifest)[0]
    fingerprint = case["runtime_fingerprint"]
    assert set(fingerprint) == {
        "runner_sha256",
        "traveler_metrics_sha256",
        "tsv_process_sha256",
        "viennaps_binary_sha256",
    }
    assert all(len(value) == 64 for value in fingerprint.values())
    invariants = trajectory._validate_case_invariants(case)
    assert abs(invariants["max_front_cells_per_checkpoint"] - 1.0) < 1e-12

    invalid = copy.deepcopy(case)
    invalid["numerics"]["checkpoint_interval"] = 0.051
    try:
        trajectory._validate_case_invariants(invalid)
    except ValueError as error:
        assert "more than one grid cell" in str(error)
    else:
        raise AssertionError("multi-cell checkpoint motion was not rejected")


def test_topology_transition_rejects_nonconservative_cavity_loss():
    previous = {
        "open_void": True,
        "open_void_depth": 1.10,
        "closed_void_count": 0,
    }
    impossible = {
        "open_void": True,
        "open_void_depth": 0.20,
        "closed_void_count": 0,
    }
    check = trajectory._topology_transition_check(
        previous,
        impossible,
        {"max_front_displacement": 0.01},
        0.01,
    )
    assert not check["valid"]
    assert abs(check["observed_open_void_depth_drop"] - 0.9) < 1e-12
    assert check["classification"] == (
        "nonconservative_or_unmeasurable_cavity_loss"
    )

    narrow_tail_mesh = {
        "nodes": np.asarray([
            [-0.0025, -1.10],
            [-0.0025, -0.20],
            [0.0025, -1.10],
            [0.0025, -0.20],
        ]),
        "lines": np.asarray([[0, 1], [2, 3]]),
    }
    narrow = trajectory._topology_transition_check(
        previous,
        impossible,
        {"max_front_displacement": 0.0025},
        0.005,
        previous_mesh=narrow_tail_mesh,
        reference={"field_y": 0.0, "via_x_bounds": (-0.15, 0.15)},
    )
    assert not narrow["valid"]
    assert narrow["classification"] == "unresolved_narrow_tail_merger"
    assert narrow["unresolved_seam_risk"]
    assert abs(narrow["disappearing_tail_max_width"] - 0.005) < 1e-12

    resolved_closure = {
        "open_void": False,
        "open_void_depth": 0.0,
        "closed_void_count": 0,
    }
    previous["open_void_depth"] = 0.02
    assert trajectory._topology_transition_check(
        previous,
        resolved_closure,
        {"max_front_displacement": 0.01},
        0.01,
    )["valid"]


def test_access_surface_holds_identifiable_lambda_by_design():
    path = Path(
        ".scratch/full-traveler-autoresearch/"
        "foundation_copper_fill_access_surface_manifest.json"
    )
    manifest = json.loads(path.read_text())
    cases = trajectory.expand_cases(manifest)
    assert len(cases) == 32
    assert len({case["case_id"] for case in cases}) == 32
    assert {case["rng_seed"] for case in cases} == {93000, 93001}
    observed = set()
    for case in cases:
        model = case["model"]
        coverage_scale = (
            model["adsorption_strength"]
            * model["suppressor_sticking_probability"]
            / model["deactivation_rate"]
        )
        observed.add((coverage_scale, model["suppressor_sticking_probability"]))
    assert observed == {
        (coverage_scale, sticking)
        for coverage_scale in (0.2, 0.5, 1.0, 2.0)
        for sticking in (0.05, 0.2, 0.5, 0.8)
    }


def test_boundary_refinement_expands_low_sticking_with_unseen_seeds():
    path = Path(
        ".scratch/full-traveler-autoresearch/"
        "foundation_copper_fill_boundary_refinement_v2_manifest.json"
    )
    manifest = json.loads(path.read_text())
    stream_policy = trajectory._validate_replicate_rng_streams(manifest)
    cases = trajectory.expand_cases(manifest)
    assert len(cases) == 72
    assert len({case["case_id"] for case in cases}) == 72
    assert {case["rng_seed"] for case in cases} == {
        94000,
        95000,
        96000,
        97000,
    }
    assert stream_policy["max_checkpoint_count"] == 320
    assert stream_policy["minimum_base_seed_separation"] == 1000
    assert stream_policy["checkpoint_seed_ranges_disjoint"]

    observed = set()
    for case in cases:
        model = case["model"]
        coverage_scale = (
            model["adsorption_strength"]
            * model["suppressor_sticking_probability"]
            / model["deactivation_rate"]
        )
        observed.add((coverage_scale, model["suppressor_sticking_probability"]))
        invariants = trajectory._validate_case_invariants(case)
        assert invariants["max_front_cells_per_checkpoint"] <= 0.5 + 1e-12

    assert observed == {
        (coverage_scale, sticking)
        for coverage_scale in (0.5, 0.625, 0.75, 0.875, 1.0, 1.25)
        for sticking in (0.025, 0.05, 0.1)
    }

    flawed = copy.deepcopy(manifest)
    for design in flawed["designs"]:
        design["rng_seeds"] = [94000, 94001, 94002, 94003]
    try:
        trajectory._validate_replicate_rng_streams(flawed)
    except ValueError as error:
        assert "RNG streams overlap" in str(error)
    else:
        raise AssertionError("overlapping replicate RNG streams were accepted")


def test_degenerate_two_node_closed_fragment_is_invalid_not_an_error():
    manifest = json.loads(trajectory.DEFAULT_MANIFEST.read_text())
    case = trajectory.expand_cases(manifest)[0]
    geometry = trajectory._build_seeded_stack(case)
    reference = trajectory._reference_geometry(geometry, case)
    fill_mesh = trajectory.tm.raw_level_set_meshes(geometry)[-1]
    node_count = len(fill_mesh["nodes"])
    mesh = {
        "nodes": np.vstack([
            fill_mesh["nodes"],
            [[-0.001, -0.5, 0.0], [0.001, -0.495, 0.0]],
        ]),
        "lines": np.vstack([
            fill_mesh["lines"],
            [[node_count, node_count + 1], [node_count, node_count + 1]],
        ]),
    }
    metrics = trajectory._fill_topology_metrics_2d(
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
        overburden_sample_count=(
            reference["metric_sampling"]["overburden_sample_count"]
        ),
    )
    assert metrics["degenerate_closed_component_count"] == 1
    assert not metrics["topology_valid"]
    assert not metrics["void_free"]
    assert metrics["seam_or_mesh_defect"]


if __name__ == "__main__":
    test_one_checkpoint_resumes_without_reexecution_and_saves_diagnostics()
    test_named_seed_material_survives_domain_roundtrip()
    test_only_valid_rows_are_considered_complete()
    test_case_ids_bind_runtime_and_limit_checkpoint_motion()
    test_topology_transition_rejects_nonconservative_cavity_loss()
    test_access_surface_holds_identifiable_lambda_by_design()
    test_boundary_refinement_expands_low_sticking_with_unseen_seeds()
    test_degenerate_two_node_closed_fragment_is_invalid_not_an_error()
    print("Cu-fill trajectory checks: PASS")

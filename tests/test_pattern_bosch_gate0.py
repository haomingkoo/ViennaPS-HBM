"""Synthetic, no-campaign guards for the frozen pattern/Bosch Gate 0."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile

import numpy as np

import foundation_pattern_bosch_gate0 as campaign
import review_pattern_bosch_gate0 as review


FINGERPRINT_KEYS = {
    "runner_sha256",
    "foundation_sha256",
    "traveler_metrics_sha256",
    "tsv_process_sha256",
    "viennaps_binary_sha256",
    "viennals_binary_sha256",
}


def manifest():
    return campaign.strict_json_loads(campaign.DEFAULT_MANIFEST.read_text())


def fingerprint(character="a"):
    return {key: character * 64 for key in FINGERPRINT_KEYS}


def cases(character=None):
    runtime = campaign.runtime_fingerprint() if character is None else fingerprint(character)
    return campaign.expand_cases(manifest(), runtime)


def mask_mesh(case, height):
    if height <= 0.0:
        return None
    right = np.asarray([[0.15, 0.0, 0.0], [0.15, height, 0.0]])
    if case["geometry"]["hole_shape"] == "QUARTER":
        nodes = right
        lines = np.asarray([[0, 1]], dtype=int)
    else:
        left = np.asarray([[-0.15, 0.0, 0.0], [-0.15, height, 0.0]])
        nodes = np.vstack((left, right))
        lines = np.asarray([[0, 1], [2, 3]], dtype=int)
    return {"nodes": nodes, "lines": lines}


def silicon_mesh(radius=0.15):
    y = np.linspace(0.0, -1.25, 101)
    nodes = np.column_stack((np.full_like(y, radius), y, np.zeros_like(y)))
    lines = np.column_stack((np.arange(100), np.arange(1, 101))).astype(int)
    return {"nodes": nodes, "lines": lines}


def success_row(output, case, *, remaining_height=0.30, radius=0.15):
    initial = mask_mesh(case, 0.30)
    silicon = silicon_mesh(radius)
    post_mask = mask_mesh(case, remaining_height)
    initial_pattern = campaign.measure_pattern(initial, case)
    selected = campaign.measure_selected_cycle(silicon, post_mask, case)
    path = campaign.checkpoint_path(
        output, case["case_id"], case["selected_cycle"]
    )
    digest = campaign.save_cycle_checkpoint(
        path, case, initial, silicon, post_mask
    )
    return {
        **case,
        "ok": True,
        "evidence_origin": campaign.evidence_origin(),
        "initial_pattern": campaign.foundation.jsonable(initial_pattern),
        "selected_cycle_metrics": campaign.foundation.jsonable(selected),
        "checkpoint_cycle": case["selected_cycle"],
        "checkpoint_path": str(path),
        "checkpoint_sha256": digest,
        "elapsed_s": 0.01,
    }


def failure_row(case, error="synthetic failure"):
    return {
        **case,
        "ok": False,
        "evidence_origin": campaign.evidence_origin(),
        "error": error,
        "traceback": error,
        "elapsed_s": 0.01,
    }


def append(path, *rows):
    for row in rows:
        campaign.append_row(path, row)


def assert_raises(fragment, function, *args):
    try:
        function(*args)
    except ValueError as error:
        assert fragment in str(error), error
    else:
        raise AssertionError(f"expected ValueError containing {fragment!r}")


def build_complete_fixture(directory):
    output = Path(directory) / "rows.jsonl"
    height_by_arm = {
        "quarter_reference_fine": 0.30,
        "full_reference_fine": 0.30,
        "full_grid_bridge": 0.30,
        "full_erosion_m0p01": 0.20,
        "full_erosion_m0p02": 0.05,
        "full_erosion_m0p04": 0.0,
    }
    for case in cases():
        append(
            output,
            success_row(
                output,
                case,
                remaining_height=height_by_arm[case["arm"]],
            ),
        )
    return output


def test_manifest_matrix_streams_authority_and_case_hashes_are_frozen():
    data = manifest()
    expanded = cases()
    assert campaign.validate_manifest(
        data, expanded, check_runtime=False
    ) == []
    assert len(expanded) == 24
    assert len({case["case_id"] for case in expanded}) == 24
    assert {(case["arm"], case["rng_seed"]) for case in expanded} == {
        (arm, seed)
        for arm in campaign.EXPECTED_DESIGNS
        for seed in campaign.EXPECTED_SEEDS
    }
    for case in expanded:
        assert set(case["runtime_fingerprint"]) == FINGERPRINT_KEYS
        assert case["rng_stream"]["process_seed_count"] == 43
        assert case["rng_stream"]["shared_base_seed_label_across_arms"]
        assert not case["rng_stream"][
            "pointwise_common_random_numbers_across_arms"
        ]
        assert not case["rng_policy"]["full_vs_quarter_common_random_numbers"]
        assert case["selected_cycle"] == 13
        assert case["recipe"]["num_cycles"] == 14
        assert not case["authority"]["recipe_authorized"]
        assert campaign.case_id(campaign.case_payload(case)) == case["case_id"]
        assert campaign.canonical_sha256(
            campaign.case_payload(case)
        ) == case["case_payload_sha256"]
    for arm in campaign.EXPECTED_DESIGNS:
        arm_cases = [case for case in expanded if case["arm"] == arm]
        streams = [
            set(range(
                case["rng_stream"]["first_process_seed"],
                case["rng_stream"]["last_process_seed"] + 1,
            ))
            for case in arm_cases
        ]
        assert not any(
            first & second
            for index, first in enumerate(streams)
            for second in streams[index + 1:]
        )
    changed = cases("b")
    assert {case["case_id"] for case in changed}.isdisjoint(
        {case["case_id"] for case in expanded}
    )


def test_manifest_mutations_fail_closed():
    mutations = []
    changed = manifest()
    changed["labels"] = ["full-traveler"]
    mutations.append(changed)
    changed = manifest()
    changed["rng_base_seeds"] = [61000, 61001, 61002, 61003]
    mutations.append(changed)
    changed = manifest()
    changed["numerics"]["maximum_workers"] = 3
    mutations.append(changed)
    changed = manifest()
    changed["designs"][1]["hole_shape"] = "QUARTER"
    mutations.append(changed)
    changed = manifest()
    changed["designs"][4]["mask_ion_rate"] = -0.03
    mutations.append(changed)
    changed = manifest()
    changed["review"]["paired_max_absolute_deltas"]["depth"] = 0.03
    mutations.append(changed)
    changed = manifest()
    changed["review"]["full_vs_quarter"]["candidate_arm"] = (
        "quarter_reference_fine"
    )
    mutations.append(changed)
    changed = manifest()
    changed["review"]["row_recompute_abs_tolerance"] = 1.0
    mutations.append(changed)
    changed = manifest()
    changed["target"]["etch_depth"] = 1.0
    mutations.append(changed)
    changed = manifest()
    changed["reference_recipe"]["source_path"] = "program.md"
    mutations.append(changed)
    changed = manifest()
    changed["authority"]["recipe_authorized"] = True
    mutations.append(changed)
    changed = manifest()
    changed["recipe"]["etch_time"] = 0.6
    mutations.append(changed)
    assert all(
        campaign.validate_manifest(item, check_runtime=False)
        for item in mutations
    )


def test_checkpoint_is_hash_bound_and_reviewer_recomputes_row_metrics():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        case = cases()[0]
        row = success_row(output, case)
        append(output, row)
        assert campaign.audit_existing_rows(output, cases()) == {case["case_id"]}
        with np.load(row["checkpoint_path"], allow_pickle=False) as checkpoint:
            assert set(checkpoint.files) == campaign.CHECKPOINT_KEYS
            assert checkpoint["selected_cycle"].item() == 13
            assert checkpoint["case_payload_sha256"].item() == case[
                "case_payload_sha256"
            ]
        reviewed = review.review_case(row, case, output, manifest())
        assert reviewed["valid"]
        assert all(reviewed["gates"].values())

        tampered = copy.deepcopy(row)
        tampered["selected_cycle_metrics"]["etch"]["depth"] = 1.20
        reviewed = review.review_case(tampered, case, output, manifest())
        assert not reviewed["valid"]
        assert any("selected_cycle_metrics.etch.depth differs" in error
                   for error in reviewed["errors"])


def test_resume_allows_failure_then_success_only():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        case = cases()[0]
        success = success_row(output, case)
        append(output, failure_row(case), success)
        assert campaign.audit_existing_rows(output, cases()) == {case["case_id"]}

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        case = cases()[0]
        success = success_row(output, case)
        append(output, success, failure_row(case))
        assert_raises("later attempt", campaign.audit_existing_rows, output, cases())

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        case = cases()[0]
        success = success_row(output, case)
        append(output, success, success)
        assert_raises("duplicate successful", campaign.audit_existing_rows, output, cases())


def test_resume_rejects_malformed_unexpected_and_stale_rows():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        output.write_text("{\n")
        assert_raises("malformed", campaign.audit_existing_rows, output, cases())

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        row = failure_row(cases()[0])
        row["case_id"] = "unexpected"
        output.write_text(json.dumps(row) + "\n")
        assert_raises("unexpected", campaign.audit_existing_rows, output, cases())

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        row = failure_row(cases()[0])
        row["runtime_fingerprint"]["runner_sha256"] = "0" * 64
        output.write_text(json.dumps(row) + "\n")
        assert_raises("stale payload", campaign.audit_existing_rows, output, cases())


def test_resume_rejects_wrong_checkpoint_path_hash_and_payload():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        case = cases()[0]
        row = success_row(output, case)
        row["checkpoint_path"] = str(Path(directory) / "wrong.npz")
        append(output, row)
        assert_raises("path differs", campaign.audit_existing_rows, output, cases())

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        case = cases()[0]
        row = success_row(output, case)
        row["checkpoint_sha256"] = "0" * 64
        append(output, row)
        assert_raises("hash differs", campaign.audit_existing_rows, output, cases())

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        case = cases()[0]
        row = success_row(output, case)
        checkpoint_path = Path(row["checkpoint_path"])
        with np.load(checkpoint_path, allow_pickle=False) as checkpoint:
            arrays = {name: checkpoint[name] for name in checkpoint.files}
        arrays["case_payload_sha256"] = np.asarray("0" * 64)
        campaign.foundation.save_npz_atomic(checkpoint_path, **arrays)
        row["checkpoint_sha256"] = campaign.file_sha256(checkpoint_path)
        append(output, row)
        assert_raises("checkpoint invalid", campaign.audit_existing_rows, output, cases())


def test_strict_json_rejects_nonfinite_values_before_writing():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        try:
            campaign.append_row(output, {"value": float("nan")})
        except ValueError:
            pass
        else:
            raise AssertionError("nonfinite row was serialized")
        assert not output.exists()
        summary = Path(directory) / "summary.json"
        try:
            review.write_json(summary, {"value": float("nan")})
        except ValueError:
            pass
        else:
            raise AssertionError("nonfinite summary was serialized")
        assert not summary.exists()


def test_run_case_records_nonfinite_metrics_as_a_failed_attempt():
    case = cases()[0]
    original_make = campaign.tp.make_initial_geometry
    original_etch = campaign.tp.bosch_etch
    original_meshes = campaign.tm.raw_level_set_meshes
    original_pattern = campaign.measure_pattern
    original_selected = campaign.measure_selected_cycle
    original_save = campaign.save_cycle_checkpoint
    mask = {
        "material": campaign.ps.Material.Mask,
        "nodes": np.asarray([[-0.3, 0.0, 0.0], [-0.3, 0.3, 0.0]]),
        "lines": np.asarray([[0, 1]]),
    }
    silicon = {
        "material": campaign.ps.Material.Si,
        "nodes": np.asarray([[-0.15, 0.0, 0.0], [-0.15, -1.25, 0.0]]),
        "lines": np.asarray([[0, 1]]),
    }

    def fake_etch(geometry, *, on_cycle, **_kwargs):
        on_cycle(geometry, case["selected_cycle"])

    try:
        campaign.tp.make_initial_geometry = lambda **_kwargs: object()
        campaign.tp.bosch_etch = fake_etch
        campaign.tm.raw_level_set_meshes = lambda _geometry: [mask, silicon]
        campaign.measure_pattern = lambda _mesh, _case: {"opening_cd": 0.3}
        campaign.measure_selected_cycle = lambda *_args: {
            "etch": {"depth": float("nan")},
            "mask_remaining_height": 0.3,
            "post_etch_mask": {"opening_cd": 0.3},
        }
        campaign.save_cycle_checkpoint = lambda *_args: "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            row = campaign.run_case((case, Path(directory) / "rows.jsonl"))
            assert row["ok"] is False
            assert "Out of range float values" in row["error"]
            output = Path(directory) / "rows.jsonl"
            campaign.append_row(output, row)
            saved = campaign.strict_json_loads(output.read_text())
            assert saved["ok"] is False
    finally:
        campaign.tp.make_initial_geometry = original_make
        campaign.tp.bosch_etch = original_etch
        campaign.tm.raw_level_set_meshes = original_meshes
        campaign.measure_pattern = original_pattern
        campaign.measure_selected_cycle = original_selected
        campaign.save_cycle_checkpoint = original_save


def test_complete_synthetic_matrix_authorizes_only_the_broad_screen():
    with tempfile.TemporaryDirectory() as directory:
        output = build_complete_fixture(directory)
        summary = review.build_summary(manifest(), output)
        assert summary["status"] == "complete_gate0_pass"
        assert summary["selected_success_count"] == 24
        assert summary["independently_valid_case_count"] == 24
        assert summary["comparisons"]["full_vs_quarter"]["pass"]
        assert summary["comparisons"]["grid_bridge"]["pass"]
        assert summary["erosion_response"]["pass"]
        assert summary["erosion_response"]["all_seeds_monotonic"]
        assert "full_reference_fine" in summary["erosion_response"][
            "all_seed_surviving_arms"
        ]
        assert "full_erosion_m0p04" in summary["erosion_response"][
            "all_seed_failed_arms"
        ]
        decision = summary["decision"]
        assert decision["broad_pattern_bosch_screen_authorized"]
        assert not decision["recipe_authorized"]
        assert not decision["process_window_authorized"]
        assert not decision["full_traveler_authorized"]
        assert not decision["automatic_downstream_launch_authorized"]
        review.write_json(Path(directory) / "summary.json", summary)


def test_paired_tolerance_gate_flip_monotonicity_and_bracket_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        output = build_complete_fixture(directory)
        summary = review.build_summary(manifest(), output)
        reviewed = summary["reviewed_cases"]

        delta_failure = copy.deepcopy(reviewed)
        candidate = next(
            row for row in delta_failure
            if row["arm"] == "full_grid_bridge" and row["rng_seed"] == 61000
        )
        candidate["metrics"]["depth"] += 0.021
        assert not review.paired_comparison(
            delta_failure, manifest(), "grid_bridge"
        )["pass"]

        flip_failure = copy.deepcopy(reviewed)
        candidate = next(
            row for row in flip_failure
            if row["arm"] == "full_reference_fine" and row["rng_seed"] == 61000
        )
        candidate["gates"]["etch_bow"] = False
        comparison = review.paired_comparison(
            flip_failure, manifest(), "full_vs_quarter"
        )
        assert not comparison["no_gate_flips"]
        assert not comparison["pass"]

        monotonic_failure = copy.deepcopy(reviewed)
        first = next(
            row for row in monotonic_failure
            if row["arm"] == "full_erosion_m0p01" and row["rng_seed"] == 61000
        )
        second = next(
            row for row in monotonic_failure
            if row["arm"] == "full_erosion_m0p02" and row["rng_seed"] == 61000
        )
        second["metrics"]["mask_remaining_height"] = (
            first["metrics"]["mask_remaining_height"] + 0.01
        )
        assert not review.erosion_response(
            monotonic_failure, manifest()
        )["pass"]

        no_failure_bracket = copy.deepcopy(reviewed)
        for row in no_failure_bracket:
            row["gates"]["etch_mask_resolved"] = True
        erosion = review.erosion_response(no_failure_bracket, manifest())
        assert erosion["all_seed_failed_arms"] == []
        assert not erosion["pass"]


def test_incomplete_matrix_never_authorizes_work():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        case = cases()[0]
        append(output, success_row(output, case))
        summary = review.build_summary(manifest(), output)
        assert summary["status"] == "incomplete_or_invalid"
        assert not summary["decision"]["broad_pattern_bosch_screen_authorized"]
        assert not summary["decision"]["automatic_downstream_launch_authorized"]


def test_checkpoint_mesh_validation_rejects_nonfinite_and_bad_indices():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        case = cases()[0]
        row = success_row(output, case)
        path = Path(row["checkpoint_path"])
        with np.load(path, allow_pickle=False) as checkpoint:
            arrays = {name: checkpoint[name] for name in checkpoint.files}
        arrays["silicon_nodes"] = arrays["silicon_nodes"].copy()
        arrays["silicon_nodes"][0, 0] = np.nan
        arrays["silicon_lines"] = arrays["silicon_lines"].copy()
        arrays["silicon_lines"][0, 0] = len(arrays["silicon_nodes"]) + 1
        campaign.foundation.save_npz_atomic(path, **arrays)
        errors = campaign.validate_checkpoint(path, case)
        assert "silicon nodes are nonfinite" in errors
        assert "silicon line indices are out of range" in errors


if __name__ == "__main__":
    test_manifest_matrix_streams_authority_and_case_hashes_are_frozen()
    test_manifest_mutations_fail_closed()
    test_checkpoint_is_hash_bound_and_reviewer_recomputes_row_metrics()
    test_resume_allows_failure_then_success_only()
    test_resume_rejects_malformed_unexpected_and_stale_rows()
    test_resume_rejects_wrong_checkpoint_path_hash_and_payload()
    test_strict_json_rejects_nonfinite_values_before_writing()
    test_run_case_records_nonfinite_metrics_as_a_failed_attempt()
    test_complete_synthetic_matrix_authorizes_only_the_broad_screen()
    test_paired_tolerance_gate_flip_monotonicity_and_bracket_fail_closed()
    test_incomplete_matrix_never_authorizes_work()
    test_checkpoint_mesh_validation_rejects_nonfinite_and_bad_indices()
    print("pattern/Bosch Gate-0 checks: PASS")

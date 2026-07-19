import copy
import tempfile
from pathlib import Path

import numpy as np

import review_copper_fill_transition as review


FINGERPRINT = {
    "runner_sha256": "runner",
    "traveler_metrics_sha256": "metrics",
    "tsv_process_sha256": "process",
    "viennaps_binary_sha256": "binary",
}


def make_manifest(study):
    fine = study == "fine_grid"
    manifest = {
        "manifest_version": 3 if fine else 2,
        "campaign": (
            "foundation-copper-fill-topology-transition-grid-study"
            if fine
            else "foundation-copper-fill-topology-transition-step-study"
        ),
        "geometry": {"radius": 0.15},
        "layers": {"liner": 0.03, "barrier": 0.01, "seed": 0.01},
        "model": {
            "active_deposition_rate": 0.2,
            "adsorption_strength": 0.0,
        },
        "numerics": {
            "grid_delta": review.FINE_GRID if fine else review.COARSE_GRID,
            "checkpoint_interval": review.SELECTED_INTERVAL if fine else 0.05,
            "max_duration": 0.8,
        },
        "target": {"min_overburden": 0.15},
        "provenance": {"viennaps_binary_sha256": "binary"},
        "designs": [],
    }
    intervals = (
        (review.SELECTED_INTERVAL,)
        if fine
        else review.CHECKPOINT_INTERVALS
    )
    suffix = "grid_005_dt_0125" if fine else None
    for adsorption, regime in review.REGIMES.items():
        for interval in intervals:
            name = (
                f"{regime}_{suffix}"
                if fine
                else f"{regime}_dt_{int(interval * 10000):04d}"
            )
            manifest["designs"].append({
                "name": name,
                "model": {"adsorption_strength": adsorption},
                "numerics": (
                    {} if fine else {"checkpoint_interval": interval}
                ),
                "rng_seeds": list(review.SEEDS),
            })
    return manifest


def checkpoint(
    index,
    allowed,
    jump,
    *,
    closure_width_bound=None,
    topology_valid=True,
):
    prior = 1.1
    closure_width_bound = (
        allowed if closure_width_bound is None else closure_width_bound
    )
    tail_width = 0.5 * closure_width_bound if jump > allowed else None
    return {
        "checkpoint": index,
        "elapsed": index * 0.0125,
        "topology_transition": {
            "valid": jump <= allowed,
            "previous_open_void_depth": prior,
            "current_open_void_depth": prior - jump,
            "observed_open_void_depth_drop": jump,
            "allowed_open_void_depth_drop": allowed,
            "closed_void_created": False,
            "classification": (
                "unresolved_narrow_tail_merger"
                if jump > allowed
                else "resolved_front_motion"
            ),
            "disappearing_tail_max_width": tail_width,
            "closure_width_bound": closure_width_bound,
            "unresolved_seam_risk": jump > allowed,
        },
        "topology_transition_failure_seen": jump > allowed,
        "topology": {
            "topology_valid": topology_valid,
            "mouth_aperture": 0.1,
            "remaining_void_area": 0.02,
            "pinch_off_failure": False,
        },
        "invalid_topology_seen": not topology_valid,
        "pinch_off_seen": False,
        "protected_stack": {"survives": True},
        "protected_failure_seen": False,
        "model_diagnostics": {"valid": True},
        "model_failure_seen": False,
        "target_pass": False,
    }


def result_row(case, fail):
    grid = case["numerics"]["grid_delta"]
    interval = case["numerics"]["checkpoint_interval"]
    front = case["model"]["active_deposition_rate"] * interval
    allowed = front + 2.0 * grid
    jump = allowed * (2.0 if fail else 0.5)
    item = checkpoint(
        1,
        allowed,
        jump,
        closure_width_bound=2.0 * front + grid,
    )
    return {
        **case,
        "ok": True,
        "production_doe_eligible": False,
        "numerical_invariants": {"max_front_displacement": front},
        "trajectory": [item],
        "last_checkpoint": 1,
        "topology_transition_failure_seen": fail,
        "invalid_topology_seen": False,
        "pinch_off_seen": False,
        "protected_failure_seen": False,
        "model_failure_seen": False,
        "target_pass": False,
        "screen_pass": False,
    }


def rows_for(manifest, fail_by_regime):
    rows = []
    for case in review.expand_cases(manifest, FINGERPRINT):
        rows.append(result_row(case, fail_by_regime[review.regime_for(case)]))
    return rows


def build(checkpoint_rows, fine_rows, *, fine_missing=False):
    checkpoint_manifest = make_manifest("checkpoint")
    fine_manifest = make_manifest("fine_grid")
    return review.build_summary(
        checkpoint_manifest,
        checkpoint_rows,
        [],
        False,
        fine_manifest,
        fine_rows,
        [],
        fine_missing,
        FINGERPRINT,
        FINGERPRINT,
    )


def test_exact_matrices_classify_width_audited_unresolved_seam():
    checkpoint_manifest = make_manifest("checkpoint")
    fine_manifest = make_manifest("fine_grid")
    checkpoint_rows = rows_for(
        checkpoint_manifest,
        {regime: True for regime in review.REGIMES.values()},
    )
    fine_rows = rows_for(
        fine_manifest,
        {regime: True for regime in review.REGIMES.values()},
    )

    summary = build(checkpoint_rows, fine_rows)

    assert summary["status"] == "complete"
    assert summary["decision"]["classification"] == (
        "unresolved_seam_limitation"
    )
    assert summary["decision"]["provisional_depth_guard_classification"] == (
        "structural_morphology_limitation"
    )
    assert summary["decision"]["guard_validation_status"] == (
        "width_audited_from_saved_pre_event_meshes"
    )
    assert "narrow pointed tail" in summary["decision"][
        "per_regime_reason"
    ]["no_suppression"]
    assert len(summary["groups"]) == 8
    group = next(
        item
        for item in summary["groups"]
        if item["regime"] == "no_suppression"
        and item["grid_delta"] == review.COARSE_GRID
        and item["checkpoint_interval"] == review.SELECTED_INTERVAL
    )
    assert group["n"] == 4
    assert group["physical_failure_count"] == 4
    assert group["metrics"]["jump_bound_ratio"]["mean"] == 2.0
    assert group["seed_spread"]["observed_depth_jump"] == 0.0
    assert summary["grid_comparisons"][0]["status"] == "complete"
    incomplete_cases = review.expand_cases(checkpoint_manifest, FINGERPRINT)[:-1]
    assert review.validate_manifest_matrix(
        checkpoint_manifest, incomplete_cases, "checkpoint"
    )


def test_checkpoint_and_grid_resolution_are_distinguished():
    checkpoint_manifest = make_manifest("checkpoint")
    fine_manifest = make_manifest("fine_grid")
    checkpoint_pass = rows_for(
        checkpoint_manifest,
        {regime: False for regime in review.REGIMES.values()},
    )
    fine_pass = rows_for(
        fine_manifest,
        {regime: False for regime in review.REGIMES.values()},
    )
    checkpoint_summary = build(checkpoint_pass, fine_pass)
    assert checkpoint_summary["decision"]["classification"] == (
        "checkpoint_resolved"
    )

    checkpoint_fail = rows_for(
        checkpoint_manifest,
        {regime: True for regime in review.REGIMES.values()},
    )
    grid_summary = build(checkpoint_fail, fine_pass)
    assert grid_summary["decision"]["classification"] == "grid_resolved"


def test_partial_fine_grid_stays_incomplete_and_keeps_failures_visible():
    checkpoint_manifest = make_manifest("checkpoint")
    fine_manifest = make_manifest("fine_grid")
    checkpoint_rows = rows_for(
        checkpoint_manifest,
        {regime: True for regime in review.REGIMES.values()},
    )
    fine_rows = rows_for(
        fine_manifest,
        {regime: True for regime in review.REGIMES.values()},
    )[:4]

    summary = build(checkpoint_rows, fine_rows)

    assert summary["status"] == "incomplete_or_invalid"
    assert summary["decision"]["classification"] == "incomplete"
    assert summary["fine_grid_study"]["selected_case_count"] == 4
    assert len(summary["fine_grid_study"]["missing_cases"]) == 4
    fine_group = next(
        item for item in summary["groups"] if item["grid_delta"] == 0.005
    )
    assert fine_group["hard_failure_counts"]["topology_transition"] == 4
    assert "No checkpoint, grid, or structural conclusion" in review.markdown(
        summary
    )


def test_fingerprint_errors_and_invalid_metrics_are_preserved():
    checkpoint_manifest = make_manifest("checkpoint")
    fine_manifest = make_manifest("fine_grid")
    checkpoint_rows = rows_for(
        checkpoint_manifest,
        {regime: True for regime in review.REGIMES.values()},
    )
    fine_rows = rows_for(
        fine_manifest,
        {regime: True for regime in review.REGIMES.values()},
    )
    wrong = copy.deepcopy(checkpoint_rows[0])
    wrong["runtime_fingerprint"]["runner_sha256"] = "wrong"
    checkpoint_rows[0] = wrong
    fine_rows[0]["trajectory"][0]["topology"]["mouth_aperture"] = None

    summary = build(checkpoint_rows, fine_rows)

    assert summary["status"] == "incomplete_or_invalid"
    assert summary["checkpoint_study"]["invalid_attempts"]
    assert summary["fine_grid_study"]["invalid_metric_rows"]
    assert summary["checkpoint_study"]["invalid_attempts"][0]["row"] == wrong
    assert summary["fine_grid_study"]["invalid_metric_rows"][0]["row"] == fine_rows[0]


def test_error_attempt_is_preserved_when_a_valid_retry_exists():
    checkpoint_manifest = make_manifest("checkpoint")
    fine_manifest = make_manifest("fine_grid")
    checkpoint_rows = rows_for(
        checkpoint_manifest,
        {regime: True for regime in review.REGIMES.values()},
    )
    fine_rows = rows_for(
        fine_manifest,
        {regime: False for regime in review.REGIMES.values()},
    )
    failed = {
        **review.expand_cases(checkpoint_manifest, FINGERPRINT)[0],
        "ok": False,
        "production_doe_eligible": False,
        "error": "synthetic worker failure",
    }

    summary = build([failed, *checkpoint_rows], fine_rows)

    assert summary["checkpoint_study"]["complete"]
    assert summary["checkpoint_study"]["error_attempt_rows"] == [failed]
    assert summary["checkpoint_study"]["selected_case_count"] == 24


def test_missing_or_live_partial_jsonl_does_not_crash(tmp_path):
    rows, errors, missing = review.load_jsonl(tmp_path / "absent.jsonl")
    assert (rows, errors, missing) == ([], [], True)

    path = tmp_path / "live.jsonl"
    path.write_text('{"ok": false}\n{"unfinished":')
    rows, errors, missing = review.load_jsonl(path)
    assert rows == [{"ok": False}]
    assert len(errors) == 1
    assert errors[0]["raw_line"] == '{"unfinished":'
    assert not missing


def test_old_depth_only_row_is_width_reaudited_from_saved_mesh(tmp_path):
    snapshot = tmp_path / "pre_event.npz"
    nodes = np.asarray([
        [-0.0025, -1.0, 0.0],
        [0.0025, -1.0, 0.0],
        [0.0025, 0.0, 0.0],
        [-0.0025, 0.0, 0.0],
    ])
    lines = np.asarray([[0, 1], [1, 2], [2, 3], [3, 0]])
    np.savez(snapshot, nodes=nodes, lines=lines)

    resolved = checkpoint(
        1,
        0.03,
        0.01,
        closure_width_bound=0.03,
    )
    resolved["snapshot_path"] = str(snapshot)
    failure = checkpoint(
        2,
        0.03,
        0.9,
        closure_width_bound=0.03,
    )
    for key in (
        "classification",
        "disappearing_tail_max_width",
        "closure_width_bound",
        "unresolved_seam_risk",
    ):
        failure["topology_transition"].pop(key)
    failure["topology_transition"]["previous_open_void_depth"] = 1.0
    failure["topology_transition"]["current_open_void_depth"] = 0.1
    failure["topology_transition"]["observed_open_void_depth_drop"] = 0.9
    failure["elapsed"] = 0.025

    row = {
        "case_id": "old",
        "design": "old",
        "model": {"active_deposition_rate": 0.2, "adsorption_strength": 0.0},
        "numerics": {"grid_delta": 0.01, "checkpoint_interval": 0.05},
        "rng_seed": 91000,
        "reference": {
            "field_y": 0.0,
            "via_x_bounds": [-0.1, 0.1],
            "initial_topology": {
                "remaining_void_area": 0.2,
                "mouth_aperture": 0.1,
            },
        },
        "numerical_invariants": {"max_front_displacement": 0.01},
        "trajectory": [resolved, failure],
        "last_checkpoint": 2,
        "topology_transition_failure_seen": True,
        "invalid_topology_seen": False,
        "pinch_off_seen": False,
        "protected_failure_seen": False,
        "model_failure_seen": False,
        "target_pass": False,
        "screen_pass": False,
    }

    diagnostic, errors = review.diagnose_row(row, tmp_path)

    assert errors == []
    assert diagnostic["width_audit_source"] == (
        "offline_saved_pre_event_mesh"
    )
    assert diagnostic["transition_classification"] == (
        "unresolved_narrow_tail_merger"
    )
    assert diagnostic["disappearing_tail_max_width"] == 0.005
    assert diagnostic["closure_width_bound"] == 0.03
    assert diagnostic["unresolved_seam_risk"]


if __name__ == "__main__":
    test_exact_matrices_classify_width_audited_unresolved_seam()
    test_checkpoint_and_grid_resolution_are_distinguished()
    test_partial_fine_grid_stays_incomplete_and_keeps_failures_visible()
    test_fingerprint_errors_and_invalid_metrics_are_preserved()
    test_error_attempt_is_preserved_when_a_valid_retry_exists()
    with tempfile.TemporaryDirectory() as directory:
        test_missing_or_live_partial_jsonl_does_not_crash(Path(directory))
        test_old_depth_only_row_is_width_reaudited_from_saved_mesh(
            Path(directory)
        )
    print("Cu-fill transition reviewer checks: PASS")

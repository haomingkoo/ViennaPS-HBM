"""Focused checks for the four-case exact-stack Cu-fill structural challenge."""

import functools
import json
import tempfile
from pathlib import Path

import foundation_copper_fill_structural_challenge as challenge


@functools.lru_cache(maxsize=1)
def _result():
    return challenge.run_structural_challenge()


def _arm_rows(arm):
    return [row for row in _result()["cases"] if row["arm"] == arm]


def _synthetic_row(case):
    candidate = case["arm"] == challenge.CANDIDATE_ARM
    topology = {
        "topology_valid": True,
        "open_void": candidate,
        "open_void_depth": 1.04 if candidate else 0.0,
        "remaining_void_area": 0.05 if candidate else 0.0,
        "fill_fraction": 0.80 if candidate else 1.0,
        "closed_void_count": 1 if candidate else 0,
        "maximum_void_width": 0.005 if candidate else 0.0,
        "maximum_void_height": 0.04 if candidate else 0.0,
        "mouth_aperture": 0.10 if candidate else 0.0,
        "void_free": not candidate,
        "center_overburden": -1.04 if candidate else 0.151,
        "field_overburden_min": 0.06 if candidate else 0.151,
        "overburden_min": -1.04 if candidate else 0.151,
        "overburden_mean": -0.01 if candidate else 0.151,
        "overburden_nonuniformity": 1.10 if candidate else 0.0,
    }
    failures = ["pinch_off_or_closed_void"] if candidate else []
    outcome = "hard_failure" if candidate else "target_pass"
    mechanism = (
        "lateral_closure_failure"
        if candidate
        else "resolved_bottom_up_target"
    )
    ratio = 0.995 if candidate else 20.0
    trajectory = [{
        "checkpoint": 10,
        "elapsed": 5.35,
        "stage": "candidate" if candidate else "uniform_overburden",
        "topology": topology,
        "topology_transition": {
            "classification": (
                "resolved_closed_void_creation"
                if candidate
                else "resolved_front_motion"
            ),
            "valid": True,
        },
        "protected_stack": {"survives": True, "max_node_delta": 0.0},
        "region_rates": {
            "floor_velocity_mean": 0.013 if candidate else 0.20,
            "lower_wall_velocity_mean": 0.0131 if candidate else 0.01,
            "floor_to_lower_wall_velocity_ratio": ratio,
        },
        "failure_types": failures,
        "target_pass": not candidate,
    }]
    return {
        "ok": True,
        "case_id": case["case_id"],
        "runtime_fingerprint": case["runtime_fingerprint"],
        "case": challenge.foundation.jsonable(case),
        "arm": case["arm"],
        "scope": "synthetic test row",
        "grid_delta": case["numerics"]["grid_delta"],
        "checkpoint_interval": case["numerics"]["checkpoint_interval"],
        "rng_seed": case["rng_seed"],
        "kinematics": {
            "required_floor_to_lower_wall_velocity_ratio": 10.0
        },
        "trajectory": trajectory,
        "outcome": outcome,
        "mechanism_classification": mechanism,
        "target_pass": not candidate,
        "void_free_event_seen": not candidate,
        "overburden_stage_seen": not candidate,
        "first_failure_types": failures,
        "all_failure_types": failures,
        "protected_stack_survives": True,
        "elapsed_s": 0.01,
    }


def test_frozen_four_case_matrix_and_checkpoint_contract():
    cases = challenge.case_matrix()
    assert len(cases) == 4
    assert {
        (case["arm"], case["numerics"]["grid_delta"])
        for case in cases
    } == {
        (arm, grid)
        for arm in challenge.ARMS
        for grid in challenge.GRID_DELTAS
    }
    for case in cases:
        assert case["rng_seed"] == challenge.FIXED_RNG_SEED
        assert case["numerical_contract"][
            "maximum_front_cells_per_checkpoint"
        ] <= 0.5 + 1e-12
        assert case["numerics"]["checkpoint_interval"] == 2.5 * case[
            "numerics"
        ]["grid_delta"]


def test_runtime_fingerprint_binds_unique_case_ids():
    cases = challenge.case_matrix()
    expected_keys = {
        "structural_runner_sha256",
        "foundation_fill_runner_sha256",
        "traveler_metrics_sha256",
        "tsv_process_sha256",
        "viennaps_binary_sha256",
    }
    assert len({case["case_id"] for case in cases}) == 4
    for case in cases:
        assert set(case["runtime_fingerprint"]) == expected_keys
        assert all(
            len(value) == 64
            for value in case["runtime_fingerprint"].values()
        )
        payload = {key: value for key, value in case.items() if key != "case_id"}
        assert case["case_id"] == challenge.foundation.case_id(payload)


def test_valid_row_only_resume_preserves_synthetic_prior_attempts():
    cases = challenge.case_matrix()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "attempts.jsonl"
        invalid = _synthetic_row(cases[0])
        invalid["runtime_fingerprint"] = {
            **invalid["runtime_fingerprint"],
            "viennaps_binary_sha256": "0" * 64,
        }
        challenge.foundation.append_row(output, invalid)
        challenge.foundation.append_row(output, _synthetic_row(cases[0]))
        challenge.foundation.append_row(output, {
            "ok": False,
            "case_id": cases[1]["case_id"],
            "runtime_fingerprint": cases[1]["runtime_fingerprint"],
            "case": challenge.foundation.jsonable(cases[1]),
            "error": "synthetic interruption",
        })
        with output.open("a") as handle:
            handle.write("not-json\n")

        before = output.read_text()
        completed = challenge.valid_completed_case_ids(output, cases)
        selection = challenge._selected_valid_rows(output, cases)
        assert completed == {cases[0]["case_id"]}
        assert selection["attempt_count"] == 3
        assert selection["valid_attempt_count"] == 1
        assert len(selection["invalid_attempts"]) == 2
        assert len(selection["parse_errors"]) == 1
        assert output.read_text() == before


def test_synthetic_review_writes_compact_complete_artifacts():
    cases = challenge.case_matrix()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "rows.jsonl"
        summary_path = root / "summary.json"
        review_path = root / "review.md"
        for case in cases:
            challenge.foundation.append_row(output, _synthetic_row(case))

        summary = challenge.review_output(output, cases)
        challenge.write_review_artifacts(summary, summary_path, review_path)
        persisted = json.loads(summary_path.read_text())
        assert summary["status"] == "complete"
        assert summary["selected_valid_case_count"] == 4
        assert summary["structural_conclusion"]["accepted"]
        assert all(
            result["agrees"]
            for result in summary["grid_classification_agreement"].values()
        )
        assert persisted["cases"][0]["terminal_topology"]
        assert "Reviewed conclusion" in review_path.read_text()


def test_exact_protected_stack_stays_fixed_in_every_case():
    for row in _result()["cases"]:
        assert row["protected_stack_survives"]
        assert all(
            checkpoint["protected_stack"]["survives"]
            and checkpoint["protected_stack"]["max_node_delta"] == 0.0
            for checkpoint in row["trajectory"]
        )


def test_positive_control_follows_bottom_up_then_overburden_path():
    for row in _arm_rows(challenge.POSITIVE_CONTROL_ARM):
        assert row["scope"] == challenge.MORPHOLOGY_ONLY_SCOPE
        assert row["outcome"] == "target_pass"
        assert row["mechanism_classification"] == "resolved_bottom_up_target"
        assert row["target_pass"]
        assert row["void_free_event_seen"]
        assert row["overburden_stage_seen"]
        assert not row["all_failure_types"]

        stages = [checkpoint["stage"] for checkpoint in row["trajectory"]]
        assert stages[0] == "bottom_up_fill"
        assert "uniform_overburden" in stages
        first_overburden = stages.index("uniform_overburden")
        assert row["trajectory"][first_overburden]["topology"]["void_free"]

        initial_rates = row["trajectory"][0]["region_rates"]
        assert abs(
            initial_rates["floor_velocity_mean"] - challenge.ACTIVE_RATE
        ) < 1e-12
        assert abs(
            initial_rates["lower_wall_velocity_mean"]
            - challenge.SUPPRESSED_RATE
        ) < 1e-12
        assert abs(
            initial_rates["floor_to_lower_wall_velocity_ratio"] - 20.0
        ) < 1e-12
        assert initial_rates["floor_to_lower_wall_velocity_ratio"] > row[
            "kinematics"
        ]["required_floor_to_lower_wall_velocity_ratio"]

        terminal = row["trajectory"][-1]["topology"]
        assert terminal["void_free"]
        assert terminal["closed_void_count"] == 0
        assert terminal["overburden_min"] >= row["case"]["target"][
            "min_overburden"
        ]


def test_candidate_reproduces_lateral_closure_failure_on_both_grids():
    accepted_failure_types = {
        "pinch_off_or_closed_void",
        "unresolved_narrow_tail_merger",
    }
    for row in _arm_rows(challenge.CANDIDATE_ARM):
        assert row["outcome"] == "hard_failure"
        assert row["mechanism_classification"] == "lateral_closure_failure"
        assert not row["target_pass"]
        assert accepted_failure_types.intersection(row["all_failure_types"])

        initial_rates = row["trajectory"][0]["region_rates"]
        ratio = initial_rates["floor_to_lower_wall_velocity_ratio"]
        threshold = row["kinematics"][
            "required_floor_to_lower_wall_velocity_ratio"
        ]
        assert ratio < 1.1
        assert ratio < threshold


def test_grid_level_mechanism_classification_agrees():
    result = _result()
    for arm in challenge.ARMS:
        agreement = result["grid_classification_agreement"][arm]
        assert agreement["agrees"]
        assert len(agreement["classifications"]) == 1

    positive_times = [
        row["trajectory"][-1]["elapsed"]
        for row in _arm_rows(challenge.POSITIVE_CONTROL_ARM)
    ]
    assert max(positive_times) - min(positive_times) <= 0.05


if __name__ == "__main__":
    test_frozen_four_case_matrix_and_checkpoint_contract()
    test_runtime_fingerprint_binds_unique_case_ids()
    test_valid_row_only_resume_preserves_synthetic_prior_attempts()
    test_synthetic_review_writes_compact_complete_artifacts()
    test_exact_protected_stack_stays_fixed_in_every_case()
    test_positive_control_follows_bottom_up_then_overburden_path()
    test_candidate_reproduces_lateral_closure_failure_on_both_grids()
    test_grid_level_mechanism_classification_agrees()
    print("Cu-fill exact-stack structural challenge: PASS")

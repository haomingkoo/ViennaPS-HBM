import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import build_v3_bosch_focused_ion_map as builder
import v3_bosch_focused_ion_map_runner as runner
import v3_pattern_bosch_stage2a_runner as stage2a


ROOT = Path(__file__).resolve().parent


def test_focused_map_is_exact_and_disjoint():
    manifest = builder.build_manifest()
    recipes = manifest["design"]["recipes"]
    assert len(recipes) == 12
    assert manifest["design"]["design"]["factor_levels"] == {
        "ion_source_exponent": [50, 141, 400],
        "ion_rate": [-0.04, -0.06324555, -0.1],
    }
    coordinates = Counter(
        (row["recipe"]["ion_source_exponent"], row["recipe"]["ion_rate"])
        for row in recipes
    )
    assert len(coordinates) == 9
    assert coordinates[(50, -0.04)] == 2
    assert coordinates[(141, -0.06324555)] == 3
    assert all(count == 1 for point, count in coordinates.items() if point not in {
        (50, -0.04), (141, -0.06324555)
    })

    fixed = {
        "etch_time": 0.5,
        "initial_etch_time": 0.3,
        "neutral_rate": -0.08,
        "neutral_sticking_probability": 0.08,
        "deposition_thickness": 0.005,
        "deposition_sticking_probability": 0.01,
        "theta_r_min": 45.0,
    }
    for row in recipes:
        assert all(row["recipe"][name] == value for name, value in fixed.items())

    cases = stage2a.expand_cases(manifest)
    assert len(cases) == len({case["case_id"] for case in cases}) == 12
    assert not stage2a.rng_interval_errors(cases)
    assert [case["rng_seed"] for case in cases] == [950000 + 91 * index for index in range(12)]
    assert cases[-1]["rng_stream"]["last_process_seed"] == 951091
    assert all(case["numerics"] == {
        "grid_delta": 0.00125,
        "rays_per_point": 500,
        "threads_per_worker": 7,
        "simulation_dimension": 2,
    } for case in cases)


def test_manifest_has_raw_measurement_policy_and_valid_sources():
    manifest = builder.build_manifest()
    plan = manifest["design"]["analysis_plan"]
    assert plan["selection_method"] == "pareto_raw_measurements"
    assert plan["weighted_score_authorized"] is False
    assert plan["candidate_rank_from_assumed_target_flags"] is False
    assert "floor_shape" in plan
    assert not runner.validate_manifest(manifest)
    for declaration in manifest["source_artifacts"].values():
        path = ROOT / declaration["path"]
        assert stage2a.file_sha256(path) == declaration["sha256"]


def test_frozen_manifest_and_dry_run():
    frozen = json.loads(builder.DEFAULT_OUTPUT.read_text())
    rebuilt = builder.build_manifest()
    rebuilt["runtime_fingerprint"] = frozen["runtime_fingerprint"]
    assert frozen == rebuilt
    result = subprocess.run(
        [sys.executable, str(ROOT / "v3_bosch_focused_ion_map_runner.py"), "--dry-run"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "logical=12 complete=12 pending=0" in result.stdout


if __name__ == "__main__":
    test_focused_map_is_exact_and_disjoint()
    test_manifest_has_raw_measurement_policy_and_valid_sources()
    test_frozen_manifest_and_dry_run()

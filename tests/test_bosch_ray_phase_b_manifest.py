"""Check the frozen 500/2,000-ray comparison design."""

import hashlib
import json
from pathlib import Path

from bosch_ray_phase_b import (
    MANIFEST,
    PANEL_REPEATS,
    SEED_STRIDE,
    build_manifest,
    expand_cases,
)


ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads(MANIFEST.read_text())
rebuilt = build_manifest()
frozen_contract = next(
    source
    for source in manifest["sources"]
    if source["path"] == "pattern_bosch_measurement_contract.json"
)
next(
    source
    for source in rebuilt["sources"]
    if source["path"] == frozen_contract["path"]
)["sha256"] = frozen_contract["sha256"]
assert manifest == rebuilt
assert manifest["numerics"]["ray_arms"] == [500, 2_000]
assert manifest["execution"]["case_cap"] == 26
assert manifest["rng_policy"]["independent_pair_count"] == 13
assert manifest["authority"].startswith(
    "Categorical confirmation only"
)
assert manifest["comparison_rules"]["continuous_differences_are_reported_not_qualified"]
assert manifest["comparison_rules"]["this_campaign_cannot_approve_500_rays"]
assert manifest["comparison_rules"]["selected_cycle_must_match"]
assert manifest["comparison_rules"]["scope_is_exact_seed_labelled_pairs_only"]
assert manifest["comparison_rules"]["minimum_width_cells_must_be_at_least"] == 3.0
assert manifest["execution"]["wall_time_limit_s"] is None

expected_repeats = dict(PANEL_REPEATS)
assert {panel["id"]: panel["repeat_count"] for panel in manifest["panel"]} == expected_repeats
assert all(panel["teaching_purpose"] for panel in manifest["panel"])
assert all(panel["repeat_rationale"] for panel in manifest["panel"])
assert SEED_STRIDE > 1 + 3 * max(
    panel["maximum_cycles"] for panel in manifest["panel"]
)

cases = expand_cases(manifest)
assert len(cases) == 26
assert len({case["case_id"] for case in cases}) == 26
assert len({(case["pair_id"], case["rng_seed"]) for case in cases}) == 13

phase_a = json.loads(
    (ROOT / "evidence/numerical/bosch_ray_phase_a_manifest.json").read_text()
)
phase_a_seeds = {
    phase_a["rng_policy"]["seed_start"]
    + index * phase_a["rng_policy"]["seed_stride"]
    for index in range(phase_a["rng_policy"]["independent_pair_count"])
}
assert not phase_a_seeds.intersection(case["rng_seed"] for case in cases)

phase_a_panels = {panel["id"]: panel for panel in phase_a["panel"]}
phase_b_panels = {panel["id"]: panel for panel in manifest["panel"]}
for panel_id in ("current_grid_reference", "design_center", "narrow_profile"):
    for key in ("geometry", "recipe", "maximum_cycles"):
        assert phase_b_panels[panel_id][key] == phase_a_panels[panel_id][key]
for key in ("geometry", "recipe", "maximum_cycles"):
    assert phase_b_panels["depth_boundary"][key] == phase_a_panels[
        "availability_challenge"
    ][key]

for pair_id in {case["pair_id"] for case in cases}:
    pair = [case for case in cases if case["pair_id"] == pair_id]
    assert {case["rays_per_point"] for case in pair} == {500, 2_000}
    assert len({case["rng_seed"] for case in pair}) == 1
    comparable = []
    for case in pair:
        comparable.append(
            {
                key: value
                for key, value in case.items()
                if key not in {"case_id", "rays_per_point"}
            }
        )
    assert comparable[0] == comparable[1]

for source in manifest["sources"]:
    path = ROOT / source["path"]
    if source["path"] == "pattern_bosch_measurement_contract.json":
        path = (
            ROOT
            / "evidence/numerical/executed_sources/"
            "29110c3_pattern_bosch_measurement_contract.json"
        )
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

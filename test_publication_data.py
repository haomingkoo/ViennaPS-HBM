"""Small publication guard: the public report must match final campaign evidence."""

import base64
import hashlib
import json
from html.parser import HTMLParser
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "publication_campaign_data.json").read_text())
interim = json.loads((ROOT / "publication_interim_data.json").read_text())
assert data["total_travelers"] == 1948
assert data["wired_factor_count"] == 17
assert "score_history" not in data
assert len(data["window"]) == 81
assert sum(not row["mask_consumed_runs"] for row in data["window"]) == 48
assert all(row["full_pass_runs"] == 0 for row in data["window"])
assert len(data["finalist_seeds"]) == 32
assert all(row["step_passes"] == 4 for row in data["finalist_seeds"])
assert all(row["tip_gap"] > 0 and row["dish"] > 0 for row in data["finalist_seeds"])
assert all(
    value.startswith("data:image/png;base64,") for value in data["visuals"].values()
)
assert interim["status"] == "complete_screening_traveler"
traveler = interim["screening_traveler"]
assert traveler["status"] == "complete_screening_traveler"
assert traveler["scope"]["two_thousand_ray_confirmation"] == "deferred"
assert traveler["etch"]["rays_per_point"] == 500
assert traveler["layers"] == {"liner": True, "barrier_seed": True}
assert traveler["fill"]["void_free"]
assert traveler["fill"]["closed_void_count"] == 0
assert traveler["fill"]["remaining_void_area"] == 0.0
assert traveler["fill"]["overburden_min"] >= 0.15
assert traveler["cmp"]["all_field_metals_clear"]
assert traveler["cmp"]["plug_connected"]
assert traveler["cmp"]["stop_continuous"]
assert traveler["cmp"]["dish"] == 0.0
assert traveler["render"].startswith("data:image/png;base64,")
assert len(traveler["render_sha256"]) == 64
render_bytes = base64.b64decode(traveler["render"].split(",", 1)[1])
assert hashlib.sha256(render_bytes).hexdigest() == traveler["render_sha256"]
assert interim["selected_foundation_cases"] == 376
assert interim["reviewed_logical_cells"] == 384
assert sum(interim["selected_case_accounting"].values()) == 376
assert interim["bosch"]["passing_cycle"] == 13
assert interim["bosch"]["saved_shape_count"] == 4
assert 1.15 <= interim["bosch"]["depth_min"] <= interim["bosch"]["depth_max"] <= 1.35
assert interim["layers"]["qualification_rows"] == 12
assert interim["layers"]["baseline_liner_passes"] == 0
assert interim["layers"]["baseline_barrier_seed_passes"] == 0
assert interim["layers"]["exploratory_screening_authorized"]
assert not interim["layers"]["final_recipe_acceptance_authorized"]
assert interim["cu_structural"]["candidate_passes"] == 0
assert interim["cu_structural"]["prescribed_bottom_up_passes"] == 2
assert interim["cu_transport"]["raw_cases"] == 168
assert interim["cu_transport"]["valid_cases"] == 168
assert interim["cu_transport"]["logical_designs"] == 21
assert interim["cu_transport"]["passing_cross_tier_designs"] == 0
assert len(interim["cu_transport"]["tier_designs"]) == 42
assert interim["cu_confirmation"]["logical_cells"] == 128
assert interim["cu_confirmation"]["metric_valid_cells"] == 128
assert interim["cu_confirmation"]["parent_reuses"] == 8
assert interim["cu_confirmation"]["new_executions"] == 120
assert interim["cu_confirmation"]["class_changing_numerical_interactions"] == 0
assert interim["cu_confirmation"]["numerical_artifacts"] == 0
assert (
    interim["cu_confirmation"]["decision"]["classification"]
    == "lower_sticking_boundary_expansion_required"
)
assert interim["cu_boundary"]["logical_cells"] == 24
assert interim["cu_boundary"]["metric_valid_cells"] == 24
assert interim["cu_boundary"]["new_executions"] == 24
assert interim["cu_boundary"]["matched_control_cells"] == 8
assert interim["cu_boundary"]["reflection_convergence"]["converged"]
assert not interim["cu_boundary"]["boundary_trend"]["continued_boundary_improvement"]
assert interim["cu_boundary"]["boundary_trend"]["improves_every_stream_in_both_tiers"]
assert (
    interim["cu_boundary"]["multiresponse_paired_directions"]["responses"][
        "worst_floor_to_each_lower_flux_ratio"
    ]["improved_count"]
    == 8
)
assert (
    interim["cu_boundary"]["realized_kinematic_ratio_by_tier"]["continuity"][
        "stream_pass_count"
    ]
    == 0
)
assert (
    interim["cu_boundary"]["realized_kinematic_ratio_by_tier"]["nominal_hbm"][
        "stream_pass_count"
    ]
    == 0
)
assert interim["cu_boundary"]["analytic_envelope"]["evaluation_status"] == (
    "not_evaluated_preliminary_flux_gate_failed"
)
assert interim["cu_boundary"]["decision"]["classification"] == (
    "two_dimensional_transport_no_go_requires_matched_3d_before_pivot"
)
assert interim["cu_boundary"]["decision"]["matched_3d_required"]
assert not interim["cu_boundary"]["decision"]["morphology_authorized"]
assert not interim["cmp"]["recipe_doe_authorized"]
assert len(interim["source_artifacts"]) == 13
assert all(len(source["sha256"]) == 64 for source in interim["source_artifacts"])
assert interim["source_artifact_distribution"] == (
    "hashes_only; raw research artifacts are not committed"
)
missing_sources = []
for source in interim["source_artifacts"]:
    path = ROOT / source["path"]
    if path.is_file():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    else:
        missing_sources.append(source["path"])
assert not missing_sources or interim["source_artifact_distribution"].startswith(
    "hashes_only"
)

template = (ROOT / "explainer_template.html").read_text()
html = (ROOT / "explainer.html").read_text()
for required in (
    'id="screening-result"',
    'id="screening-traveler-visual"',
    'id="current"',
    'id="boundary-atlas"',
    'id="actions"',
    'id="why-order"',
    'id="cu-screen"',
    'id="transport-surface"',
    'id="tutorial"',
    'id="raw-output"',
    'id="autoresearch"',
    'id="stage-tabs"',
    'id="window-plot"',
    'id="seed-plot"',
    'id="visual-reads"',
    'id="references"',
):
    assert required in template
assert "A simplified TSV traveler" in html
assert '"total_travelers":1948' in html
assert '"selected_foundation_cases":376' in html
assert "How the measurement code checks a known geometry" in html
assert "Creates the vertical electrical path." in html
assert "What the new experiments indicate" in html
assert "Equipment controls, model controls, and feedback" in html
assert "Copper-fill results" in html
assert "The browser does not invent intermediate shapes." in html
assert 'href="cu_fill_replay.json"' in html
assert 'id="step-output-list"' in html
step_experiments = json.loads((ROOT / "step_experiments.json").read_text())
assert [study["id"] for study in step_experiments["studies"]] == [
    "mask",
    "bosch",
    "liner",
    "barrier",
    "seed",
    "cmp",
]
assert [frame["step"] for frame in step_experiments["failure_chain"]["frames"]] == [
    "Mask",
    "Dry etch",
    "Liner",
    "Barrier",
    "Seed",
    "Copper fill",
]
assert (
    step_experiments["failure_chain"]["frames"][-1]["metrics"]["closed_void_count"] == 1
)
assert step_experiments["studies"][0]["frames"][
    step_experiments["studies"][0]["target_frame"]
]["metrics"]["meets_screen"]
parameter_counts = {
    study["id"]: len(study["parameters"])
    for study in step_experiments["studies"]
}
assert parameter_counts == {
    "mask": 3,
    "bosch": 2,
    "liner": 2,
    "barrier": 2,
    "seed": 2,
    "cmp": 2,
}
frame_counts = {study["id"]: len(study["frames"]) for study in step_experiments["studies"]}
assert frame_counts == {
    "mask": 27,
    "bosch": 9,
    "liner": 9,
    "barrier": 9,
    "seed": 9,
    "cmp": 9,
}
for study in step_experiments["studies"]:
    parameter_keys = [parameter["key"] for parameter in study["parameters"]]
    expected_settings = set(
        product(*(parameter["values"] for parameter in study["parameters"]))
    )
    actual_settings = {
        tuple(frame["setting"][key] for key in parameter_keys)
        for frame in study["frames"]
    }
    assert actual_settings == expected_settings
    if study["acceptance"]["status"] == "not_declared":
        assert study["claim_level"] == "no_gate_declared"
        assert study["acceptance"]["basis"]["classification"] == "no_limit_declared"
        assert all(frame["metrics"]["meets_screen"] is None for frame in study["frames"])
        continue
    assert study["acceptance"]["basis"] == {
        "classification": "assumed_study_target",
        "physical_qualification": False,
        "source": study["acceptance"]["basis"]["source"],
    }
    assert study["acceptance"]["basis"]["source"]["path"] == "program.md"
    for frame in study["frames"]:
        outcomes = []
        for rule in study["acceptance"]["rules"]:
            measured = frame["metrics"][rule["metric"]]
            if rule["operator"] == "must_be_true":
                outcomes.append(measured is True)
            elif rule["operator"] == "minimum":
                outcomes.append(measured >= rule["value"])
            elif rule["operator"] == "maximum":
                outcomes.append(measured <= rule["value"])
            else:
                outcomes.append(abs(measured - rule["value"]) <= rule["tolerance"])
        assert frame["metrics"]["meets_screen"] == all(outcomes)
seed_study = next(
    study for study in step_experiments["studies"] if study["id"] == "seed"
)
assert all(frame["metrics"]["meets_screen"] is None for frame in seed_study["frames"])
cmp_study = next(study for study in step_experiments["studies"] if study["id"] == "cmp")
assert all(frame["metrics"]["meets_screen"] is None for frame in cmp_study["frames"])
chain_frames = step_experiments["failure_chain"]["frames"]
assert chain_frames[0]["parent_frame_hash"] is None
recomputed_chain_hashes = []
for frame in chain_frames:
    payload = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "parent_frame_hash"}
    }
    recomputed_chain_hashes.append(
        hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
assert [frame["frame_hash"] for frame in chain_frames] == recomputed_chain_hashes
assert all(
    chain_frames[index]["parent_frame_hash"] == chain_frames[index - 1]["frame_hash"]
    for index in range(1, len(chain_frames))
)
assert step_experiments["failure_chain"]["run_id"] == recomputed_chain_hashes[-1][:12]
assert all(
    "continuous" in frame["metrics"]
    for frame in chain_frames
    if frame["step"] in {"Liner", "Barrier", "Seed"}
)
assert step_experiments["provenance"]["rng_seed"] == 42000
assert "Clear field copper without" not in html
replay = json.loads((ROOT / "cu_fill_replay.json").read_text())
assert replay["frame_count"] == 24
assert len(replay["runs"]) == 2
assert replay["runs"][0]["frames"][-1]["metrics"]["closed_void_count"] == 1
assert replay["runs"][1]["frames"][-1]["metrics"]["void_free"]

bosch_replay = json.loads((ROOT / "bosch_trajectory_replay.json").read_text())
assert bosch_replay["target"]["basis"]["classification"] == "assumed_study_target"
assert bosch_replay["target"]["basis"]["physical_qualification"] is False
assert [frame["cycle"] for frame in bosch_replay["frames"]] == [1, 4, 7, 10, 13, 16, 18]
assert bosch_replay["frames"][-1]["progress"] == 1
assert {item["selector"] for item in bosch_replay["citations"]} == {
    "/source_row",
    "/native_checkpoint_verification",
}

candidate_replay = json.loads((ROOT / "candidate_cu_replay.json").read_text())
assert all(
    basis["physical_qualification"] is False
    for basis in candidate_replay["target_basis"].values()
)
assert candidate_replay["target_basis"]["max_balance_error"]["classification"] == (
    "implementation_assumption"
)
assert [frame["checkpoint"] for frame in candidate_replay["frames"]] == list(
    range(1, 12)
)
assert all(
    not frame["metrics"]["unresolved_seam_risk"]
    for frame in candidate_replay["frames"][:-1]
)
assert candidate_replay["frames"][-1]["metrics"]["unresolved_seam_risk"]
assert "cannot be classified reliably" in candidate_replay["decision"]
assert {item["selector"] for item in candidate_replay["citations"]} == {
    "/source_row",
    "/review_decision",
}
bosch_tutorial = json.loads((ROOT / "bosch_tutorial_data.json").read_text())
assert bosch_tutorial["targets"]["basis"]["classification"] == (
    "assumed_study_target"
)
assert bosch_tutorial["targets"]["basis"]["physical_qualification"] is False
assert "Copper response map" in html
assert "SELECTED HANDOFF PASSES 4/4" not in html
assert "What to tune next" in html
assert "Target only." in html
assert "https://www.nist.gov/publications/metrology-needs-tsv-fabrication" in html
assert "https://viennatools.github.io/ViennaPS/process/" in html
assert "Adopted as production" not in html
assert "All 4 real knobs" not in html
assert "only 2 real continuous knobs" not in html
assert "18 wired recipe factors" not in html
assert "aria-valuetext" in template
assert "model length" in template
for banned in (
    "audited wired model space",
    "one canonical traveler",
    "No compliant full traveler",
    "model-limited misses",
    "fab-calibrated DOE",
):
    assert banned not in template


class MarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.range_ids, self.label_fors = [], [], set()
        self.images, self.buttons, self.links = [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "input" and attrs.get("type") == "range":
            self.range_ids.append(attrs.get("id"))
        if tag == "label" and attrs.get("for"):
            self.label_fors.add(attrs["for"])
        if tag == "img":
            self.images.append(attrs)
        if tag == "button":
            self.buttons.append(attrs)
        if tag == "a":
            self.links.append(attrs)


audit = MarkupAudit()
audit.feed(template)
assert len(audit.ids) == len(set(audit.ids)), "duplicate HTML id"
assert all(input_id in audit.label_fors for input_id in audit.range_ids)
assert all(image.get("src") and image.get("alt") for image in audit.images)
assert all(button.get("type") == "button" for button in audit.buttons)
assert all(link.get("href") for link in audit.links)
assert (
    'rel="canonical" href="https://kooexperience.com/ViennaPS-HBM/explainer.html"'
    in template
)
print("publication campaign data checks: PASS")

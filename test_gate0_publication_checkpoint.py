"""Publication guard for the completed, blocked pattern/Bosch Gate-0."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parent
AUDIT = ROOT / "autoresearch-results" / "restart_audit"


def load(path):
    return json.loads(path.read_text())


def test_gate0_checkpoint_matches_review_artifacts():
    public = load(ROOT / "publication_interim_data.json")["pattern_bosch_gate0"]
    gate0_path = AUDIT / "pattern_bosch_gate0_summary.json"
    handoff_path = AUDIT / "pattern_bosch_handoff_summary.json"
    gate0 = load(gate0_path)
    handoff = load(handoff_path)

    assert public["status"] == gate0["status"] == "complete_gate0_blocked"
    assert public["attempts"] == gate0["attempt_count"] == 24
    assert public["independently_valid_cases"] == 24
    assert public["gate_pass_counts"] == gate0["gate_pass_counts"]
    assert not public["full_reference_pass"]
    assert not public["full_traveler_authorized"]
    assert not public["automatic_downstream_launch_authorized"]

    for public_key, review_key in (
        ("full_vs_quarter", "full_vs_quarter"),
        ("grid_bridge", "grid_bridge"),
    ):
        review = gate0["comparisons"][review_key]
        expected_failures = {
            name: (result["maximum_absolute_delta"], result["tolerance"])
            for name, result in review["metric_results"].items()
            if not result["pass"]
        }
        actual_failures = {
            row["name"]: (row["maximum_absolute_delta"], row["tolerance"])
            for row in public[public_key]["failed_metrics"]
        }
        assert actual_failures == expected_failures
        assert public[public_key]["gate_flip_pairs"] == sum(
            row["gate_flip"] for row in review["pairs"]
        )

    for published_range in public["mask_erosion"]["ranges"]:
        rows = [
            row for row in gate0["reviewed_cases"]
            if row["arm"] in gate0["erosion_response"]["all_seed_surviving_arms"]
            and row["mask_ion_rate"] == published_range["mask_ion_rate"]
        ]
        heights = [row["metrics"]["mask_remaining_height"] for row in rows]
        assert len(rows) == 4
        assert published_range["minimum_remaining_height"] == min(heights)
        assert published_range["maximum_remaining_height"] == max(heights)
        assert published_range["all_four_seeds_survive"]
    assert public["mask_erosion"]["all_seeds_monotonic"]
    assert not public["mask_erosion"]["failure_bracket_established"]

    assert public["handoff"]["source_checkpoints"] == handoff["attempt_count"] == 4
    assert public["handoff"]["reviewed"] == handoff["reviewed_checkpoint_count"] == 3
    assert public["handoff"]["excluded"] == 1
    assert public["handoff"]["accepted"] == 0
    assert not public["handoff"]["reusable_upstream_geometry_authorized"]

    interim = load(ROOT / "publication_interim_data.json")
    artifact_hashes = {
        row["name"]: row["sha256"] for row in interim["source_artifacts"]
    }
    assert artifact_hashes["pattern_bosch_gate0"] == hashlib.sha256(
        gate0_path.read_bytes()
    ).hexdigest()
    assert artifact_hashes["pattern_bosch_handoff"] == hashlib.sha256(
        handoff_path.read_bytes()
    ).hexdigest()
    r1_manifest_path = ROOT / public["corrective_r1"]["manifest_path"]
    assert public["corrective_r1"]["manifest_sha256"] == hashlib.sha256(
        r1_manifest_path.read_bytes()
    ).hexdigest()
    assert public["corrective_r1"]["initial_cases"] == 9
    assert public["corrective_r1"]["maximum_executed_cases"] == 14

    template = (ROOT / "explainer_template.html").read_text()
    assert 'id="latest-checkpoint"' in template
    assert "What the first 24 reruns changed" in template
    assert "they do not solve the full traveler" in template
    assert "INTERIM.pattern_bosch_gate0" in template
    assert "writes ViennaPS domains directly" in template

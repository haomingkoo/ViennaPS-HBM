"""Fail-closed guards for the active full-traveler DOE methodology."""

import json
from pathlib import Path
import tempfile

import freeze_pattern_bosch_discovery_s1_manifest as s1_freezer
import freeze_pattern_bosch_screen_manifest as old_freezer
import pattern_bosch_discovery_s1_runner as s1_runner
import pattern_bosch_screen_runner as old_runner


ROOT = Path(__file__).resolve().parent


def test_old_state_ledgers_cannot_resume():
    old = json.loads((ROOT / "autoresearch-results/state.json").read_text())
    audit = json.loads(
        (ROOT / "autoresearch-results/restart_audit/state.json").read_text()
    )
    assert old["mode"] == "superseded"
    assert old["methodology"]["resume_authorized"] is False
    assert audit["resume_authorized"] is False
    assert audit["methodology_epoch"] == "full-traveler-doe-v3"
    assert audit["resume_files"][0] == "RESEARCH_PLAN_V3.md"


def test_superseded_screen_freezers_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        missing = Path(directory) / "missing.json"
        for freezer, arguments in (
            (old_freezer, (missing, missing)),
            (s1_freezer, (missing,)),
        ):
            try:
                freezer.build_manifest(*arguments)
            except ValueError as error:
                assert "superseded" in str(error)
            else:
                raise AssertionError("superseded DOE freezer remained executable")


def test_superseded_s1_runner_rejects_constructed_manifest():
    from test_pattern_bosch_discovery_s1 import manifest

    errors = s1_runner.validate_manifest(
        manifest(), check_runtime=True, check_prerequisite=False
    )
    assert any("superseded Bosch-only S1" in error for error in errors)


def test_superseded_640_case_runner_rejects_constructed_manifest():
    from test_pattern_bosch_screen_runner import manifest

    errors = old_runner.validate_manifest(
        manifest(), check_runtime=True, check_prerequisites=False
    )
    assert any("superseded repeat-heavy screen" in error for error in errors)


def test_v3_requires_screen_propagate_focus_sequence():
    plan = (ROOT / "RESEARCH_PLAN_V3.md").read_text()
    for required in (
        "Broad skew screening",
        "Rank effects",
        "Prove propagation",
        "Focus",
        "Step-sensitive",
        "Traveler-relevant",
        "Shared-geometry blocking",
    ):
        assert required in plan


def test_wired_mask_erosion_is_separately_challenged_not_silently_omitted():
    plan = (ROOT / "RESEARCH_PLAN_V3.md").read_text()
    registry = (
        ROOT / "docs/factor-registry.md"
    ).read_text()
    assert "2f. Mask-erosion model challenge" in plan
    assert "intentionally not mixed into Stage 2a's nine recipe-factor" in plan
    assert "`bosch_mask_ion_rate`" in registry
    assert "V3 Stage 2f" in registry
    assert "wired_model_sensitivity" in registry


if __name__ == "__main__":
    test_old_state_ledgers_cannot_resume()
    test_superseded_screen_freezers_fail_closed()
    test_superseded_s1_runner_rejects_constructed_manifest()
    test_superseded_640_case_runner_rejects_constructed_manifest()
    test_v3_requires_screen_propagate_focus_sequence()
    test_wired_mask_erosion_is_separately_challenged_not_silently_omitted()
    print("V3 methodology guards: PASS")

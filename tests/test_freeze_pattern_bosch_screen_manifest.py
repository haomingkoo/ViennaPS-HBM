"""Guards for prerequisite-bound broad-screen manifest freezing."""

import json
from pathlib import Path
import tempfile

import freeze_pattern_bosch_screen_manifest as freezer


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False))


def prerequisite_files(directory):
    gate0 = Path(directory) / "gate0.json"
    handoff = Path(directory) / "handoff.json"
    write(gate0, {
        "status": "complete_gate0_pass",
        "selected_success_count": 24,
        "independently_valid_case_count": 24,
        "decision": {"broad_pattern_bosch_screen_authorized": True},
    })
    write(handoff, {
        "reviewed_checkpoint_count": 4,
        "handoff_results": [{"accepted": True} for _ in range(4)],
        "decision": {"reusable_upstream_geometry_authorized": True},
    })
    return gate0, handoff


def test_superseded_640_case_screen_cannot_freeze():
    with tempfile.TemporaryDirectory() as directory:
        gate0, handoff = prerequisite_files(directory)
        try:
            freezer.build_manifest(gate0, handoff)
        except ValueError as error:
            assert "superseded by RESEARCH_PLAN_V3.md" in str(error)
        else:
            raise AssertionError("superseded 640-case screen was frozen")


if __name__ == "__main__":
    test_superseded_640_case_screen_cannot_freeze()
    print("pattern/Bosch manifest-freeze checks: PASS")

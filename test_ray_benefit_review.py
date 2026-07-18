"""Validate the ray-cost review and its evidence links."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
BUILDER = ROOT / "build_ray_benefit_review.py"
DOCUMENT = ROOT / "evidence/numerical/ray_benefit_review.json"
SCHEMA = ROOT / "schemas/ray-benefit-review.schema.json"
VALIDATOR = ROOT / "scripts/validate_evidence.py"


def validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path), str(SCHEMA)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def main() -> None:
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    result = validate(DOCUMENT)
    assert result.returncode == 0, result.stdout
    document = json.loads(DOCUMENT.read_text())
    levels = document["datasets"][0]["levels"]
    assert [row["rays_per_point"] for row in levels] == [250, 1000, 2000, 4000]
    for previous, current in zip(levels, levels[1:]):
        change = current["change_from_previous_level"]
        assert change["from_rays"] == previous["rays_per_point"]
        assert change["to_rays"] == current["rays_per_point"]
    factor_check = document["datasets"][2]
    assert factor_check["broad_outcome_matches"] <= factor_check["anchor_count"]
    assert factor_check["trajectory_matches"] <= factor_check["anchor_count"]

    broken = json.loads(DOCUMENT.read_text())
    broken["datasets"][0]["levels"][0]["latency_s"].pop("median")
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        path = Path(directory) / "broken.json"
        path.write_text(json.dumps(broken))
        result = validate(path)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "schema_failed"


if __name__ == "__main__":
    main()
    print("ray benefit review: PASS")

"""Verify the committed 18-case Bosch descriptive review."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

from scripts.build.build_v3_bosch_interior_descriptive_review import build


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "evidence/numerical/v3_bosch_interior_descriptive_review.json"
SCHEMA = ROOT / "schemas/v3-bosch-interior-descriptive-review.schema.json"
VALIDATOR = ROOT / "scripts/validate_evidence.py"


def main() -> None:
    document = json.loads(DOCUMENT.read_text())
    rebuilt = build()
    assert document == rebuilt
    assert document["completeness"]["observed_cases"] == 18
    assert document["limitations"]["statistical_significance_estimated"] is False
    assert document["effects"]["cd_bottom"]["ranked_factors"][0]["factor"] == "deposition_thickness"
    assert document["effects"]["sidewall_angle_deg"]["ranked_factors"][0]["factor"] == "deposition_thickness"
    assert document["effects"]["depth"]["ranked_factors"][0]["factor"] == "ion_rate"
    assert math.isclose(
        document["effects"]["cd_bottom"]["ranked_factors"][0]["adjusted_high_minus_low"],
        -0.1405783252591525,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(DOCUMENT), str(SCHEMA)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout


if __name__ == "__main__":
    main()
    print("V3 Bosch interior descriptive review: PASS")

"""The retired phase-one scorer must require an explicit historical override."""

import os
import subprocess
import sys
from pathlib import Path


LEGACY_SCRIPTS = (
    "archive/phase-one-campaign/joint_process_doe.py",
    "archive/phase-one-campaign/autoresearch_joint_process.py",
    "archive/phase-one-campaign/review_joint_process_results.py",
    "archive/phase-one-campaign/dry_etch_doe.py",
    "archive/phase-one-campaign/flow_doe.py",
    "archive/phase-one-sweeps/sweep_big.py",
    "archive/phase-one-sweeps/sweep_downstream.py",
    "archive/phase-one-sweeps/sweep_downstream_comprehensive.py",
    "archive/phase-one-sweeps/sweep_joint_5steps.py",
    "archive/phase-one-sweeps/sweep_top4.py",
)
ROOT = Path(__file__).parents[1]

for script in LEGACY_SCRIPTS:
    environment = dict(os.environ)
    environment.pop("VIENNAPS_HBM_ALLOW_LEGACY_METRICS", None)
    root = str(ROOT)
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (root, environment.get("PYTHONPATH")) if part
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / script)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        env=environment,
    )
    assert result.returncode != 0, script
    assert "under foundation re-audit" in result.stderr, (script, result.stderr)

print("legacy metric guard: PASS")

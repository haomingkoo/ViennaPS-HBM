"""The retired phase-one scorer must require an explicit historical override."""

import os
import subprocess
import sys


LEGACY_SCRIPTS = (
    "joint_process_doe.py",
    "autoresearch_joint_process.py",
    "review_joint_process_results.py",
    "dry_etch_doe.py",
    "flow_doe.py",
    "sweep_big.py",
    "sweep_downstream.py",
    "sweep_downstream_comprehensive.py",
    "sweep_joint_5steps.py",
    "sweep_top4.py",
)

for script in LEGACY_SCRIPTS:
    environment = dict(os.environ)
    environment.pop("VIENNAPS_HBM_ALLOW_LEGACY_METRICS", None)
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert result.returncode != 0, script
    assert "under foundation re-audit" in result.stderr, (script, result.stderr)

print("legacy metric guard: PASS")

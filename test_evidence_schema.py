"""Check that evidence validation fails closed without inventing values."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
VALIDATOR = ROOT / "scripts" / "validate_evidence.py"
SCHEMA = ROOT / "schemas" / "numerical-performance.schema.json"
DOCUMENT = ROOT / "numerical_performance_data.json"


def run(document: Path):
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(document), str(SCHEMA)],
        check=False,
        capture_output=True,
        text=True,
    )


def main():
    valid = run(DOCUMENT)
    assert valid.returncode == 0
    assert json.loads(valid.stdout)["status"] == "valid"

    broken = json.loads(DOCUMENT.read_text())
    del broken["v3_ray_qualification"]["points"][0]["status"]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "broken.json"
        path.write_text(json.dumps(broken))
        invalid = run(path)
    result = json.loads(invalid.stdout)
    assert invalid.returncode == 1
    assert result["status"] == "schema_failed"
    assert result["retryable"] is False
    assert any(item["pointer"].endswith("/0") for item in result["details"])

    bad_hash = json.loads(DOCUMENT.read_text())
    bad_hash["provenance"]["builder"]["sha256"] = "0" * 64
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        path = Path(directory) / "bad-hash.json"
        path.write_text(json.dumps(bad_hash))
        invalid = run(path)
    result = json.loads(invalid.stdout)
    assert invalid.returncode == 1
    assert result["status"] == "provenance_failed"
    assert any("hash mismatch" in item["message"] for item in result["details"])

    bad_selector = json.loads(DOCUMENT.read_text())
    bad_selector["foundation"]["grid"]["points"][0]["citations"][0]["selector"] = "/does/not/exist"
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        path = Path(directory) / "bad-selector.json"
        path.write_text(json.dumps(bad_selector))
        invalid = run(path)
    result = json.loads(invalid.stdout)
    assert invalid.returncode == 1
    assert result["status"] == "provenance_failed"
    assert any("JSON pointer" in item["message"] for item in result["details"])

    bad_status = json.loads(DOCUMENT.read_text())
    bad_status["v3_ray_qualification"]["points"][0]["status"] = "qualified"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "bad-status.json"
        path.write_text(json.dumps(bad_status))
        invalid = run(path)
    assert invalid.returncode == 1
    assert json.loads(invalid.stdout)["status"] == "schema_failed"


if __name__ == "__main__":
    main()
    print("evidence schema checks: PASS")

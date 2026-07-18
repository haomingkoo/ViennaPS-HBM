"""Verify the committed mask/Bosch measurement-control evidence."""

import hashlib
import json
from pathlib import Path

from build_pattern_bosch_metric_controls import build


ROOT = Path(__file__).resolve().parent
evidence = json.loads(
    (ROOT / "evidence/bosch/pattern_bosch_metric_controls.json").read_text()
)
assert evidence == build()
assert all(evidence["checks"].values())

for source in evidence["sources"]:
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

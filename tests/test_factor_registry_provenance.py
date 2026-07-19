"""Verify the committed factor registry without importing ViennaPS."""

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
registry = json.loads((ROOT / "factor_registry.json").read_text())
records = registry["records"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


sources = [registry["provenance"]["builder"], *registry["provenance"]["code_sources"]]
assert len({source["path"] for source in sources}) == len(sources)
for source in sources:
    path = ROOT / source["path"]
    assert path.is_file(), source
    assert sha256(path) == source["sha256"], source

ids = [record["id"] for record in records]
assert len(ids) == len(set(ids))
assert registry["counts"]["total"] == len(records)
assert registry["counts"]["by_step"] == dict(
    sorted(Counter(record["step"] for record in records).items())
)
assert registry["counts"]["by_classification"] == dict(
    sorted(Counter(record["classification"] for record in records).items())
)
assert registry["counts"]["by_implementation_status"] == dict(
    sorted(Counter(record["implementation_status"] for record in records).items())
)
assert registry["counts"]["by_evidence_status"] == dict(
    sorted(Counter(record["evidence_status"] for record in records).items())
)
assert registry["counts"]["by_doe_eligibility"] == dict(
    sorted(Counter(record["doe_eligibility"] for record in records).items())
)
assert registry["counts"]["by_criterion_evidence_class"] == dict(
    sorted(Counter(record["criterion_evidence_class"] for record in records).items())
)
assert all(
    record["classification"] in registry["classification_vocabulary"]
    and record["evidence_status"] in registry["evidence_status_vocabulary"]
    and record["range_provenance"]
    and record["doe_eligibility"]
    and record["criterion_evidence_class"]
    for record in records
)

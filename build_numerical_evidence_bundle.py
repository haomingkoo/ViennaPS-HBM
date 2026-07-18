"""Publish the exact JSON evidence used by the numerical charts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "autoresearch-results" / "restart_audit"
OUTPUT = ROOT / "evidence" / "numerical"
MANIFEST = OUTPUT / "manifest.json"
FILES = (
    "metric_convergence_rows.jsonl",
    "grid_extension_rows.jsonl",
    "metric_convergence_summary.json",
    "v3_pattern_bosch_stage2a_rows.jsonl",
    "v3_pattern_bosch_stage2a_summary.json",
    "v3_bosch_cheap_qualification_rows.jsonl",
    "v3_bosch_cheap_qualification_review.json",
    "v3_bosch_r125_qualification_rows.jsonl",
    "v3_bosch_r250_qualification_rows.jsonl",
    "v3_bosch_low_ray_qualification_review.json",
    "v3_bosch_cheap_interactions_rows.jsonl",
    "v3_bosch_cheap_interactions_review.json",
    "v3_bosch_interior_refinement_rows.jsonl",
)
SOURCES = {name: SOURCE / name for name in FILES}
SOURCES.update(
    {
        "v3_bosch_r125_qualification_manifest.json": ROOT
        / ".scratch/full-traveler-autoresearch/v3_bosch_r125_qualification_manifest.json",
        "v3_bosch_r250_qualification_manifest.json": ROOT
        / ".scratch/full-traveler-autoresearch/v3_bosch_r250_qualification_manifest.json",
        "v3_bosch_cheap_qualification_manifest.json": ROOT
        / ".scratch/full-traveler-autoresearch/v3_bosch_cheap_qualification_manifest.json",
        "v3_pattern_bosch_stage2a_manifest.json": ROOT
        / ".scratch/full-traveler-autoresearch/v3_pattern_bosch_stage2a_manifest.json",
    }
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record(path: Path, data: bytes):
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(data),
        "bytes": len(data),
        "lines": len(data.splitlines()),
    }


def export():
    missing = [
        str(path.relative_to(ROOT)) for path in SOURCES.values() if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(f"source evidence missing: {missing}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = []
    for name, source in SOURCES.items():
        target = OUTPUT / name
        data = source.read_bytes()
        target.write_bytes(data)
        files.append(
            {
                "original_workspace_source": record(source, data),
                "published": record(target, data),
            }
        )
    manifest = {
        "schema_version": 1,
        "purpose": "exact source rows for the published numerical charts and Bosch tutorial",
        "generator": record(Path(__file__).resolve(), Path(__file__).read_bytes()),
        "files": files,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def check():
    manifest = json.loads(MANIFEST.read_text())
    errors = []
    generator = manifest["generator"]
    generator_path = ROOT / generator["path"]
    if (
        not generator_path.is_file()
        or sha256(generator_path.read_bytes()) != generator["sha256"]
    ):
        errors.append("evidence-bundle generator changed")
    for item in manifest["files"]:
        expected = item["published"]
        path = ROOT / expected["path"]
        if not path.is_file():
            errors.append(f"missing {expected['path']}")
            continue
        data = path.read_bytes()
        if sha256(data) != expected["sha256"]:
            errors.append(f"hash mismatch {expected['path']}")
        if (
            len(data) != expected["bytes"]
            or len(data.splitlines()) != expected["lines"]
        ):
            errors.append(f"size mismatch {expected['path']}")
    if errors:
        raise ValueError("; ".join(errors))
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = check() if args.check else export()
    print(
        json.dumps(
            {
                "status": "valid" if args.check else "exported",
                "files": len(manifest["files"]),
                "manifest": str(MANIFEST.relative_to(ROOT)),
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()

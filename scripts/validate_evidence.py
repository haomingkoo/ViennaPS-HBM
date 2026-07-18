#!/usr/bin/env python3
"""Validate one evidence document and return an actionable result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def pointer(parts) -> str:
    escaped = (str(part).replace("~", "~0").replace("/", "~1") for part in parts)
    return "/" + "/".join(escaped)


def reject_constant(value: str):
    raise ValueError(f"invalid JSON constant {value}")


def evidence_references(value, trail=()):
    if isinstance(value, dict):
        if {"path", "sha256"} <= value.keys():
            yield trail, value
        for key, item in value.items():
            yield from evidence_references(item, (*trail, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from evidence_references(item, (*trail, index))


def resolve_json_pointer(document, value: str):
    current = document
    for token in value.removeprefix("/").split("/") if value else []:
        key = token.replace("~1", "/").replace("~0", "~")
        current = current[int(key)] if isinstance(current, list) else current[key]
    return current


def reference_errors(document: object, root: Path):
    errors = []
    for trail, reference in evidence_references(document):
        path = (root / reference["path"]).resolve()
        location = pointer(trail)
        if not path.is_relative_to(root):
            errors.append({"pointer": location, "message": "path leaves the evidence root"})
            continue
        if not path.is_file():
            errors.append({"pointer": location, "message": f"missing cited file {reference['path']}"})
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != reference["sha256"]:
            errors.append({"pointer": location, "message": f"hash mismatch for {reference['path']}"})
        lines = reference.get("line_numbers")
        if lines is not None:
            if not lines or any(line < 1 or line > len(data.splitlines()) for line in lines):
                errors.append({"pointer": location, "message": f"invalid line citation for {reference['path']}"})
        selector = reference.get("selector")
        if isinstance(selector, str) and selector.startswith("/"):
            try:
                resolve_json_pointer(json.loads(data), selector)
            except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
                errors.append({"pointer": location, "message": f"JSON pointer does not resolve in {reference['path']}"})
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path)
    parser.add_argument("schema", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    missing = [str(path) for path in (args.document, args.schema) if not path.is_file()]
    if missing:
        print(json.dumps({
            "status": "missing_file",
            "missing": missing,
            "retryable": False,
            "next_action": "Restore or generate the named file before validation.",
        }, separators=(",", ":")))
        return 1

    try:
        document = json.loads(args.document.read_text(), parse_constant=reject_constant)
        schema = json.loads(args.schema.read_text(), parse_constant=reject_constant)
    except (json.JSONDecodeError, ValueError) as error:
        print(json.dumps({
            "status": "invalid_json",
            "path": str(args.document),
            "line": getattr(error, "lineno", None),
            "column": getattr(error, "colno", None),
            "message": getattr(error, "msg", str(error)),
            "retryable": False,
            "next_action": "Repair the JSON; do not retry unchanged input.",
        }, separators=(",", ":")))
        return 1

    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
        key=lambda item: list(item.path),
    )
    if errors:
        print(json.dumps({
            "status": "schema_failed",
            "errors": len(errors),
            "details": [
                {"pointer": pointer(error.path), "message": error.message}
                for error in errors[:20]
            ],
            "truncated": len(errors) > 20,
            "retryable": False,
            "next_action": "Repair missing or contradictory evidence fields before review or publication.",
        }, separators=(",", ":")))
        return 1

    provenance_errors = reference_errors(document, args.root.resolve())
    if provenance_errors:
        print(json.dumps({
            "status": "provenance_failed",
            "errors": len(provenance_errors),
            "details": provenance_errors[:20],
            "truncated": len(provenance_errors) > 20,
            "retryable": False,
            "next_action": "Restore the cited file or regenerate evidence from the declared source.",
        }, separators=(",", ":")))
        return 1

    print(json.dumps({
        "status": "valid",
        "document": str(args.document),
        "schema": str(args.schema),
        "retryable": False,
        "next_action": None,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Load and validate the checked-in process settings."""

from __future__ import annotations

from pathlib import Path
import tomllib
from typing import Any, cast


CONFIG_PATH = Path(__file__).resolve().parent / "config" / "process.toml"


def _table(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"config section {name!r} must be a table")
    return cast(dict[str, Any], value)


def _number(table: dict[str, Any], key: str) -> float:
    value = table.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"config value {key!r} must be numeric")
    return float(value)


def _positive(table: dict[str, Any], key: str) -> float:
    value = _number(table, key)
    if value <= 0.0:
        raise ValueError(f"config value {key!r} must be positive")
    return value


def load_process_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("rb") as handle:
        config = tomllib.load(handle)
    if config.get("schema_version") != 1:
        raise ValueError("unsupported process config schema")

    core = _table(config.get("core"), "core")
    targets = _table(config.get("targets"), "targets")
    defaults = _table(config.get("defaults"), "defaults")
    morphology = _table(config.get("morphology"), "morphology")
    traveler = _table(config.get("traveler"), "traveler")
    transport = _table(config.get("transport_3d"), "transport_3d")

    for key in ("numeric_epsilon", "min_resolved_etch_depth"):
        _positive(core, key)
    for name in ("pattern", "etch", "liner", "barrier", "fill", "cmp"):
        _table(targets.get(name), f"targets.{name}")
    for name in ("geometry", "bosch", "deposition", "fill"):
        _table(defaults.get(name), f"defaults.{name}")
    for table, key in (
        (morphology, "grid_delta"),
        (morphology, "via_radius"),
        (traveler, "grid_delta"),
        (traveler, "thread_count"),
        (transport, "sector_count"),
    ):
        _positive(table, key)
    source_hash = traveler.get("source_sha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("traveler.source_sha256 must be a SHA-256 digest")
    return config


PROCESS_CONFIG = load_process_config()

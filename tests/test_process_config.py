"""Checks for the public process configuration."""

from pathlib import Path
import tempfile

from process_config import CONFIG_PATH, load_process_config


config = load_process_config()
assert config["schema_version"] == 1
assert config["targets"]["fill"]["min_overburden"] > 0
assert config["traveler"]["source_sha256"]

with tempfile.TemporaryDirectory() as directory:
    invalid = Path(directory) / "process.toml"
    invalid.write_text("schema_version = 2\n")
    try:
        load_process_config(invalid)
    except ValueError as error:
        assert "schema" in str(error)
    else:
        raise AssertionError("invalid schema was accepted")

print(f"process config checks: PASS ({CONFIG_PATH.name})")

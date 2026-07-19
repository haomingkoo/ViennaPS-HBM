"""Load the tutorial configuration."""

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config/tutorial.toml"


def load_config(path=DEFAULT_CONFIG):
    return tomllib.loads(Path(path).read_text())

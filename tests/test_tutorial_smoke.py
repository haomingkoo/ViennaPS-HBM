"""Run the public tutorial once with its fixed teaching configuration."""

from pathlib import Path
import math
import tempfile

from viennaps_hbm import run_tutorial


with tempfile.TemporaryDirectory() as directory:
    result = run_tutorial(output_dir=directory)
    assert result["stages"] == [
        "mask",
        "etch",
        "liner",
        "barrier",
        "seed",
        "copper",
        "cmp",
    ]
    assert all(math.isfinite(result["etch"][name]) for name in result["etch"])
    assert isinstance(result["liner"]["aperture_open"], bool)
    assert result["copper"]["topology_valid"] is True
    assert result["cmp"]["copper_surface_nodes"] > 0
    assert (Path(directory) / "summary.json").is_file()

"""Export simulated copper surfaces for the interactive teaching replay."""

from __future__ import annotations

import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import viennals as ls

import morphology_fill_control as control


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "cu_fill_replay.json"
FRAME_COUNT = 24


def _source(path: Path) -> dict:
    resolved = path.resolve()
    return {
        "path": str(resolved.relative_to(ROOT)),
        "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
    }


def _surface_path(domain) -> str:
    mesh = ls.Mesh()
    control.ls2.ToSurfaceMesh(domain, mesh).apply()
    nodes = np.asarray(mesh.getNodes(), dtype=float)
    lines = np.asarray(mesh.getLines(), dtype=int)
    segments = nodes[lines][:, :, :2]
    return "".join(
        f"M{start[0]:.5f} {start[1]:.5f}L{end[0]:.5f} {end[1]:.5f}"
        for start, end in segments
    )


def _metrics(fill, initial_area):
    measured = control._measure_morphology_only(
        fill, initial_cavity_area=initial_area
    )
    return {
        key: measured[key]
        for key in (
            "mouth_open",
            "mouth_aperture",
            "mouth_pinched_off",
            "closed_void_count",
            "closed_void_area",
            "remaining_void_area",
            "open_void_depth",
            "void_free",
            "fill_fraction",
            "overburden_min",
        )
    }


def _frame(fill, initial_area, progress):
    return {
        "progress": progress,
        "surface_path": _surface_path(fill),
        "metrics": _metrics(fill, initial_area),
    }


def _wall_dominated_run():
    substrate, fill = control._build_morphology_only_via()
    initial_area = control._measure_morphology_only(fill)["remaining_void_area"]
    velocity = control.MorphologyOnlyVelocity("top_heavy")
    frames = [_frame(fill, initial_area, 0.0)]
    for index in range(1, FRAME_COUNT):
        control._advect_morphology_only(
            substrate,
            fill,
            velocity,
            control.FAILED_FILL_DURATION / (FRAME_COUNT - 1),
            ignore_voids=True,
        )
        frames.append(_frame(fill, initial_area, index / (FRAME_COUNT - 1)))
    return substrate, frames


def _floor_dominated_run():
    substrate, fill = control._build_morphology_only_via()
    initial_area = control._measure_morphology_only(fill)["remaining_void_area"]
    frames = [_frame(fill, initial_area, 0.0)]
    bottom_up_frames = FRAME_COUNT - 3
    velocity = control.MorphologyOnlyVelocity("bottom_up")
    duration = (
        control.INCOMPLETE_FILL_DURATION + control.CLOSURE_DURATION
    ) / bottom_up_frames
    for index in range(1, bottom_up_frames + 1):
        control._advect_morphology_only(substrate, fill, velocity, duration)
        frames.append(_frame(fill, initial_area, index / (FRAME_COUNT - 1)))
    velocity = control.MorphologyOnlyVelocity("uniform")
    for index in range(bottom_up_frames + 1, FRAME_COUNT):
        control._advect_morphology_only(
            substrate, fill, velocity, control.OVERBURDEN_DURATION / 2
        )
        frames.append(_frame(fill, initial_area, index / (FRAME_COUNT - 1)))
    return substrate, frames


def main():
    control.ls.setNumThreads(1)
    substrate, wall_frames = _wall_dominated_run()
    _, floor_frames = _floor_dominated_run()
    if wall_frames[-1]["metrics"]["closed_void_count"] != 1:
        raise RuntimeError("wall-dominated control did not retain one void")
    if not floor_frames[-1]["metrics"]["void_free"]:
        raise RuntimeError("floor-dominated control did not finish void-free")

    data = {
        "schema_version": 1,
        "scope": control.MORPHOLOGY_ONLY_SCOPE,
        "frame_count": FRAME_COUNT,
        "provenance": {
            "sources": [
                _source(Path(__file__)),
                _source(Path(control.__file__)),
            ],
            "viennals_version": version("viennals"),
            "stochastic": False,
        },
        "substrate_path": _surface_path(substrate),
        "runs": [
            {
                "id": "wall_dominated",
                "label": "Wall growth faster",
                "input": "Prescribed top-heavy surface velocity",
                "frames": wall_frames,
            },
            {
                "id": "floor_dominated",
                "label": "Floor growth faster",
                "input": "Prescribed bottom-up surface velocity",
                "frames": floor_frames,
            },
        ],
    }
    OUTPUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()

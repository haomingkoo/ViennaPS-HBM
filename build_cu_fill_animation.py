"""Render the tested morphology controls as a teaching animation."""

from __future__ import annotations

from pathlib import Path

import matplotlib.animation as animation
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
import viennals as ls

import morphology_fill_control as control


OUTPUT = Path("cu_fill_void_vs_control.gif")
FRAME_COUNT = 24
FPS = 6


def _surface(domain):
    mesh = ls.Mesh()
    control.ls2.ToSurfaceMesh(domain, mesh).apply()
    nodes = np.asarray(mesh.getNodes(), dtype=float)
    lines = np.asarray(mesh.getLines(), dtype=int)
    return nodes[lines][:, :, :2]


def _run(profile, duration, *, ignore_voids):
    substrate, fill = control._build_morphology_only_via()
    initial_area = control._measure_morphology_only(fill)["remaining_void_area"]
    velocity = control.MorphologyOnlyVelocity(profile)
    frames = [(_surface(fill), control._measure_morphology_only(fill))]
    for _ in range(FRAME_COUNT - 1):
        control._advect_morphology_only(
            substrate,
            fill,
            velocity,
            duration / (FRAME_COUNT - 1),
            ignore_voids=ignore_voids,
        )
        frames.append(
            (
                _surface(fill),
                control._measure_morphology_only(
                    fill, initial_cavity_area=initial_area
                ),
            )
        )
    return _surface(substrate), frames


def _run_bottom_up():
    substrate, fill = control._build_morphology_only_via()
    initial_area = control._measure_morphology_only(fill)["remaining_void_area"]
    frames = [(_surface(fill), control._measure_morphology_only(fill))]
    bottom_up_frames = FRAME_COUNT - 3
    bottom_up = control.MorphologyOnlyVelocity("bottom_up")
    for _ in range(bottom_up_frames):
        control._advect_morphology_only(
            substrate,
            fill,
            bottom_up,
            (control.INCOMPLETE_FILL_DURATION + control.CLOSURE_DURATION)
            / bottom_up_frames,
        )
        frames.append(
            (
                _surface(fill),
                control._measure_morphology_only(
                    fill, initial_cavity_area=initial_area
                ),
            )
        )
    uniform = control.MorphologyOnlyVelocity("uniform")
    for _ in range(2):
        control._advect_morphology_only(
            substrate,
            fill,
            uniform,
            control.OVERBURDEN_DURATION / 2,
        )
        frames.append(
            (
                _surface(fill),
                control._measure_morphology_only(
                    fill, initial_cavity_area=initial_area
                ),
            )
        )
    return _surface(substrate), frames


def _status(metrics):
    if metrics["closed_void_count"]:
        return "Mouth closed first — void trapped"
    if metrics["void_free"]:
        return "Cavity filled — no void detected"
    return "Copper front advancing"


def main():
    control.ls.setNumThreads(1)
    substrate, failed = _run(
        "top_heavy", control.FAILED_FILL_DURATION, ignore_voids=True
    )
    _, passed = _run_bottom_up()
    if failed[-1][1]["closed_void_count"] != 1:
        raise RuntimeError("failed-fill control did not retain one void")
    if not passed[-1][1]["void_free"]:
        raise RuntimeError("bottom-up control did not finish void-free")

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 6.2), sharex=True, sharey=True)
    fig.patch.set_facecolor("#eef3f5")
    titles = ("Wall growth dominates", "Floor growth dominates")
    collections = []
    status_text = []
    for ax, title in zip(axes, titles):
        ax.add_collection(
            LineCollection(substrate, colors="#66717d", linewidths=2.2)
        )
        moving = LineCollection([], colors="#b8652a", linewidths=4.0)
        ax.add_collection(moving)
        collections.append(moving)
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        status_text.append(
            ax.text(
                0.5,
                0.02,
                "",
                transform=ax.transAxes,
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )
        )
        ax.set_xlim(-0.24, 0.24)
        ax.set_ylim(-1.08, 0.16)
        ax.set_aspect("equal")
        ax.set_facecolor("#ffffff")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("#c9d1d7")

    progress = fig.text(0.5, 0.94, "", ha="center", fontsize=11, color="#53606c")
    fig.text(
        0.5,
        0.035,
        "Gray: silicon boundary   Brown: moving copper surface",
        ha="center",
        fontsize=10,
        color="#53606c",
    )
    fig.subplots_adjust(left=0.06, right=0.94, bottom=0.09, top=0.88, wspace=0.16)

    def draw(index):
        for collection, text, frames in zip(
            collections, status_text, (failed, passed)
        ):
            collection.set_segments(frames[index][0])
            metrics = frames[index][1]
            text.set_text(_status(metrics))
            text.set_color("#b33a24" if metrics["closed_void_count"] else "#176b5b")
        progress.set_text(f"Fill progress  {round(100 * index / (FRAME_COUNT - 1))}%")
        return (*collections, *status_text, progress)

    movie = animation.FuncAnimation(
        fig, draw, frames=FRAME_COUNT, interval=1000 / FPS, blit=False
    )
    movie.save(OUTPUT, writer=animation.PillowWriter(fps=FPS), dpi=120)
    plt.close(fig)
    print(OUTPUT)


if __name__ == "__main__":
    main()

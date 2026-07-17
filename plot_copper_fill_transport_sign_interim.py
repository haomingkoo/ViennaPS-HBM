"""Plot the provisional Cu-fill transport-sign screen from saved row means.

This intentionally does not import the independent reviewer.  It visualizes
only the regional means already saved in each raw successful row; the coarse
screen is audited, while numerical and 3D confirmation remain pending.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm


ROOT = Path(__file__).resolve().parent
DEFAULT_ROWS = ROOT / (
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_sign_rows.jsonl"
)
DEFAULT_OUTPUT = ROOT / (
    "autoresearch-results/restart_audit/"
    "copper_fill_transport_sign_interim.png"
)
TIERS = ("continuity", "nominal_hbm")
TIER_LABELS = {"continuity": "Continuity", "nominal_hbm": "Nominal HBM"}
STICKINGS = (0.025, 0.05, 0.1, 0.2, 0.5, 0.8, 1.0)
SOURCE_POWERS = (0.0, 1.0, 4.0)
SEEDS = (102000, 103000, 104000, 105000)
LOWER_WALLS = ("left_lower_wall", "right_lower_wall")
LABELS = ("full-traveler", "critical-review")


def load_and_validate(path: Path) -> list[dict]:
    rows = []
    with path.open() as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON on line {line_number}: {error}") from error

    if len(rows) != 168 or not all(row.get("ok") is True for row in rows):
        raise ValueError("expected exactly 168 successful raw rows")
    case_ids = [row.get("case_id") for row in rows]
    if None in case_ids or len(set(case_ids)) != 168:
        raise ValueError("expected exactly 168 unique nonempty case IDs")
    if not all(tuple(row.get("labels", ())) == LABELS for row in rows):
        raise ValueError(f"every row must carry labels {LABELS!r}")

    cells: dict[tuple, list[dict]] = defaultdict(list)
    logical_keys = set()
    for row in rows:
        model = row.get("model", {})
        key = (
            row.get("geometry_tier"),
            float(model.get("suppressor_sticking_probability", math.nan)),
            float(model.get("suppressor_source_power", math.nan)),
        )
        logical = (*key, row.get("rng_seed"))
        if logical in logical_keys:
            raise ValueError(f"duplicate tier/design/seed row: {logical!r}")
        logical_keys.add(logical)
        cells[key].append(row)

    expected = {
        (tier, sticking, power)
        for tier in TIERS
        for sticking in STICKINGS
        for power in SOURCE_POWERS
    }
    if set(cells) != expected:
        raise ValueError("raw rows do not match the frozen 2 x 7 x 3 design")
    for key, cell in cells.items():
        if len(cell) != 4 or {row["rng_seed"] for row in cell} != set(SEEDS):
            raise ValueError(f"cell {key!r} does not contain the four paired streams")
        if any(len(row.get("trajectory", ())) != 1 for row in cell):
            raise ValueError(f"cell {key!r} contains a non-one-checkpoint row")
    return rows


def saved_mean(row: dict, region: str, quantity: str) -> float:
    try:
        value = float(
            row["trajectory"][0]["analysis_regions"][region][quantity]["mean"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"missing saved {region}/{quantity} mean in {row['case_id']}"
        ) from error
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(
            f"nonpositive/nonfinite {region}/{quantity} mean in {row['case_id']}"
        )
    return value


def aggregate(rows: list[dict]) -> dict[str, dict[str, np.ndarray]]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        model = row["model"]
        grouped[
            (
                row["geometry_tier"],
                float(model["suppressor_sticking_probability"]),
                float(model["suppressor_source_power"]),
            )
        ].append(row)

    result = {
        metric: {tier: np.empty((len(STICKINGS), len(SOURCE_POWERS))) for tier in TIERS}
        for metric in ("flux", "velocity")
    }
    for tier in TIERS:
        for i, sticking in enumerate(STICKINGS):
            for j, power in enumerate(SOURCE_POWERS):
                flux_ratios = []
                velocity_ratios = []
                for row in grouped[tier, sticking, power]:
                    floor_flux = saved_mean(row, "floor", "suppressor_flux")
                    floor_velocity = saved_mean(row, "floor", "normal_velocity")
                    for wall in LOWER_WALLS:
                        flux_ratios.append(
                            floor_flux / saved_mean(row, wall, "suppressor_flux")
                        )
                        velocity_ratios.append(
                            floor_velocity / saved_mean(row, wall, "normal_velocity")
                        )
                # Strict conditions must survive both lower walls and all four streams.
                result["flux"][tier][i, j] = max(flux_ratios)
                result["velocity"][tier][i, j] = min(velocity_ratios)
    return result


def plot(data: dict[str, dict[str, np.ndarray]], output: Path) -> None:
    targets = {"flux": 0.95, "velocity": 1.05}
    margins = {
        "flux": {
            tier: np.log10(targets["flux"] / data["flux"][tier])
            for tier in TIERS
        },
        "velocity": {
            tier: np.log10(data["velocity"][tier] / targets["velocity"])
            for tier in TIERS
        },
    }
    norms = {}
    for metric in ("flux", "velocity"):
        limit = max(
            0.05,
            max(float(np.max(np.abs(margins[metric][tier]))) for tier in TIERS),
        )
        norms[metric] = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.titlesize": 11,
            "axes.labelsize": 10,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 10.0))
    fig.patch.set_facecolor("#f7f4ee")
    fig.subplots_adjust(
        left=0.075,
        right=0.975,
        top=0.82,
        bottom=0.19,
        wspace=0.14,
        hspace=0.38,
    )
    fig.suptitle(
        "PROVISIONAL — Cu suppressor transport-sign screen",
        y=0.975,
        fontsize=18,
        fontweight="bold",
        color="#8a1c1c",
    )
    fig.text(
        0.5,
        0.925,
        "168/168 raw rows · four paired streams per cell · saved regional means",
        ha="center",
        fontsize=10.5,
        color="#332f2b",
    )

    images = {"flux": [], "velocity": []}
    for row_index, tier in enumerate(TIERS):
        for col_index, metric in enumerate(("flux", "velocity")):
            ax = axes[row_index, col_index]
            ax.set_facecolor("#f7f4ee")
            values = data[metric][tier]
            image = ax.imshow(
                margins[metric][tier],
                cmap="RdYlGn",
                norm=norms[metric],
                origin="lower",
                aspect="auto",
                interpolation="none",
            )
            images[metric].append(image)
            target_text = "< 0.95" if metric == "flux" else "> 1.05"
            quantity = (
                "floor / lower-wall suppressor flux"
                if metric == "flux"
                else "floor / lower-wall growth velocity"
            )
            worst = "maximum" if metric == "flux" else "minimum"
            ax.set_title(
                f"{TIER_LABELS[tier]} · {quantity}\n"
                f"worst ({worst}) of 4 streams · pass {target_text}"
            )
            ax.set_xticks(range(len(SOURCE_POWERS)), [f"{x:g}" for x in SOURCE_POWERS])
            ax.set_yticks(range(len(STICKINGS)), [f"{x:g}" for x in STICKINGS])
            ax.set_xlabel("Suppressor source power")
            ax.set_ylabel("Suppressor sticking probability")
            for i in range(values.shape[0]):
                for j in range(values.shape[1]):
                    score = margins[metric][tier][i, j]
                    text_color = "white" if abs(score) > norms[metric].vmax * 0.52 else "#251f1b"
                    value = values[i, j]
                    label = f"{value:.2f}" if value >= 10 else f"{value:.3f}"
                    ax.text(j, i, label, ha="center", va="center", fontsize=8.5, color=text_color)
            for spine in ax.spines.values():
                spine.set_visible(False)

    for col_index, metric in enumerate(("flux", "velocity")):
        colorbar_axis = fig.add_axes(
            [0.13 + 0.50 * col_index, 0.085, 0.30, 0.016]
        )
        colorbar = fig.colorbar(
            images[metric][0], cax=colorbar_axis, orientation="horizontal"
        )
        colorbar.set_label("Signed log₁₀ pass margin · 0 is the strict boundary")

    fig.text(
        0.5,
        0.018,
        "AUDITED COARSE SCREEN · NUMERICAL AND 3D CONFIRMATION PENDING · "
        "NO INTERPOLATION · NOT QUALIFICATION EVIDENCE",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#8a1c1c",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output,
        dpi=180,
        facecolor=fig.get_facecolor(),
        metadata={
            "Title": "PROVISIONAL Cu suppressor transport-sign screen",
            "Description": "Audited coarse screen; numerical and 3D confirmation pending; not qualification evidence.",
        },
    )
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = load_and_validate(args.rows)
    plot(aggregate(rows), args.output)
    print(f"validated_rows={len(rows)} unique_case_ids={len({row['case_id'] for row in rows})}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()

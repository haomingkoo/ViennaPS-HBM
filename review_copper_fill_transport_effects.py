"""Review factor effects in the coarse copper-transport screen."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


DEFAULT_ROWS = Path(
    "autoresearch-results/restart_audit/copper_fill_transport_sign_rows.jsonl"
)
DEFAULT_REVIEWED_SUMMARY = Path(
    "autoresearch-results/restart_audit/copper_fill_transport_sign_summary.json"
)
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/copper_fill_transport_effects_summary.json"
)
DEFAULT_MD = Path(
    "autoresearch-results/restart_audit/copper_fill_transport_effects_review.md"
)

TIERS = ("continuity", "nominal_hbm")
STICKING_LEVELS = (0.025, 0.05, 0.1, 0.2, 0.5, 0.8, 1.0)
SOURCE_POWER_LEVELS = (0.0, 1.0, 4.0)
SEEDS = (102000, 103000, 104000, 105000)
LOWER_WALLS = ("left_lower_wall", "right_lower_wall")
MIDDLE_UPPER_WALLS = (
    "left_middle_wall",
    "right_middle_wall",
    "left_upper_wall",
    "right_upper_wall",
)


def _mean(regions, name, quantity):
    return float(regions[name][quantity]["mean"])


def row_responses(row):
    regions = row["trajectory"][0]["analysis_regions"]
    floor_flux = _mean(regions, "floor", "suppressor_flux")
    floor_coverage = _mean(regions, "floor", "coverage")
    floor_velocity = _mean(regions, "floor", "normal_velocity")
    flux_ratios = []
    coverage_margins = []
    velocity_ratios = []
    for name in LOWER_WALLS:
        wall_flux = _mean(regions, name, "suppressor_flux")
        wall_coverage = _mean(regions, name, "coverage")
        wall_velocity = _mean(regions, name, "normal_velocity")
        flux_ratios.append(floor_flux / wall_flux)
        coverage_margins.append(wall_coverage - floor_coverage)
        velocity_ratios.append(floor_velocity / wall_velocity)
    upper_velocity_margins = [
        floor_velocity - _mean(regions, name, "normal_velocity")
        for name in MIDDLE_UPPER_WALLS
    ]
    return {
        "worst_floor_to_lower_flux_ratio": max(flux_ratios),
        "worst_lower_minus_floor_coverage": min(coverage_margins),
        "worst_floor_to_lower_velocity_ratio": min(velocity_ratios),
        "worst_floor_minus_middle_upper_velocity": min(
            upper_velocity_margins
        ),
    }


def _case_key(row):
    model = row["model"]
    return (
        row["geometry_tier"],
        float(model["suppressor_sticking_probability"]),
        float(model["suppressor_source_power"]),
        int(row["rng_seed"]),
    )


def validate_rows(rows, reviewed_summary):
    errors = []
    if reviewed_summary.get("status") != "complete":
        errors.append("independent transport review is not complete")
    if reviewed_summary.get("metric_valid_case_count") != 168:
        errors.append("independent transport review does not have 168 valid cases")
    if len(rows) != 168:
        errors.append(f"expected 168 rows, found {len(rows)}")
    if len({row.get("case_id") for row in rows}) != len(rows):
        errors.append("case IDs are not unique")
    if any(row.get("ok") is not True for row in rows):
        errors.append("not every row is successful")
    if any(
        row.get("labels") != ["full-traveler", "critical-review"]
        for row in rows
    ):
        errors.append("required labels are missing or reordered")
    expected = {
        (tier, sticking, power, seed)
        for tier in TIERS
        for sticking in STICKING_LEVELS
        for power in SOURCE_POWER_LEVELS
        for seed in SEEDS
    }
    observed = {_case_key(row) for row in rows}
    if observed != expected:
        errors.append("logical design matrix differs from the frozen 168 cells")
    return errors


def range_variance_decomposition(values):
    """Return balanced sampled-range SS shares for a 7 x 3 x 4 array."""
    array = np.asarray(values, dtype=float)
    if array.shape != (7, 3, 4):
        raise ValueError("factor array must have shape 7 x 3 x 4")
    if not np.all(np.isfinite(array)):
        raise ValueError("factor array contains nonfinite values")
    grand = float(np.mean(array))
    sticking_means = np.mean(array, axis=(1, 2))
    power_means = np.mean(array, axis=(0, 2))
    cell_means = np.mean(array, axis=2)
    ss_total = float(np.sum((array - grand) ** 2))
    ss_sticking = float(3 * 4 * np.sum((sticking_means - grand) ** 2))
    ss_power = float(7 * 4 * np.sum((power_means - grand) ** 2))
    ss_interaction = float(4 * np.sum(
        (
            cell_means
            - sticking_means[:, None]
            - power_means[None, :]
            + grand
        ) ** 2
    ))
    ss_stream = max(
        0.0, ss_total - ss_sticking - ss_power - ss_interaction
    )
    components = {
        "sticking": ss_sticking,
        "source_power": ss_power,
        "sticking_x_source_power": ss_interaction,
        "paired_stream_residual": ss_stream,
    }
    shares = {
        name: (value / ss_total if ss_total > 0.0 else 0.0)
        for name, value in components.items()
    }
    return {
        "scale": "natural log of the regional ratio",
        "sum_squares_total": ss_total,
        "sum_squares": components,
        "sampled_range_variance_share": shares,
    }


def _sample_standard_deviation(values):
    array = np.asarray(values, dtype=float)
    return float(np.std(array, ddof=1)) if len(array) > 1 else 0.0


def build_summary(rows, reviewed_summary):
    errors = validate_rows(rows, reviewed_summary)
    summary = {
        "status": "invalid" if errors else "complete",
        "validation_errors": errors,
        "scope": (
            "descriptive balanced factor/interaction audit of the audited "
            "coarse 2D screen; not calibration or qualification"
        ),
        "case_count": len(rows),
        "factor_effects": {},
        "monotonicity": {},
        "paired_geometry_effect": {},
        "closest_tested_miss": {},
    }
    if errors:
        return summary

    indexed = {_case_key(row): row_responses(row) for row in rows}
    for tier in TIERS:
        flux = np.empty((7, 3, 4), dtype=float)
        velocity = np.empty((7, 3, 4), dtype=float)
        for i, sticking in enumerate(STICKING_LEVELS):
            for j, power in enumerate(SOURCE_POWER_LEVELS):
                for k, seed in enumerate(SEEDS):
                    response = indexed[(tier, sticking, power, seed)]
                    flux[i, j, k] = math.log(
                        response["worst_floor_to_lower_flux_ratio"]
                    )
                    velocity[i, j, k] = math.log(
                        response["worst_floor_to_lower_velocity_ratio"]
                    )
        summary["factor_effects"][tier] = {
            "floor_to_lower_flux_ratio": range_variance_decomposition(flux),
            "floor_to_lower_velocity_ratio": range_variance_decomposition(
                velocity
            ),
        }

    sticking_sequences = 0
    sticking_monotone = 0
    for tier in TIERS:
        for power in SOURCE_POWER_LEVELS:
            for seed in SEEDS:
                values = [
                    indexed[(tier, sticking, power, seed)][
                        "worst_floor_to_lower_flux_ratio"
                    ]
                    for sticking in STICKING_LEVELS
                ]
                sticking_sequences += 1
                sticking_monotone += int(all(
                    first <= second
                    for first, second in zip(values, values[1:])
                ))
    power_sequences = 0
    power_monotone = 0
    for tier in TIERS:
        for sticking in STICKING_LEVELS:
            for seed in SEEDS:
                values = [
                    indexed[(tier, sticking, power, seed)][
                        "worst_floor_to_lower_flux_ratio"
                    ]
                    for power in SOURCE_POWER_LEVELS
                ]
                power_sequences += 1
                power_monotone += int(all(
                    first <= second
                    for first, second in zip(values, values[1:])
                ))
    summary["monotonicity"] = {
        "flux_ratio_non_decreasing_with_sticking": {
            "passing_sequences": sticking_monotone,
            "total_sequences": sticking_sequences,
        },
        "flux_ratio_non_decreasing_with_source_power": {
            "passing_sequences": power_monotone,
            "total_sequences": power_sequences,
        },
    }

    geometry_deltas = []
    for sticking in STICKING_LEVELS:
        for power in SOURCE_POWER_LEVELS:
            for seed in SEEDS:
                geometry_deltas.append(
                    indexed[("nominal_hbm", sticking, power, seed)][
                        "worst_floor_to_lower_flux_ratio"
                    ]
                    - indexed[("continuity", sticking, power, seed)][
                        "worst_floor_to_lower_flux_ratio"
                    ]
                )
    summary["paired_geometry_effect"] = {
        "nominal_minus_continuity_flux_ratio_positive_pairs": sum(
            delta > 0.0 for delta in geometry_deltas
        ),
        "pair_count": len(geometry_deltas),
        "median_difference": float(np.median(geometry_deltas)),
        "minimum_difference": min(geometry_deltas),
        "maximum_difference": max(geometry_deltas),
    }

    design = (0.025, 0.0)
    closest = {
        "design": "stick_0p025_power_0p0",
        "selection_scope": (
            "closest tested corner on the two headline sign ratios; it is a "
            "boundary miss, not a recipe ranking"
        ),
        "tiers": {},
    }
    for tier in TIERS:
        flux_values = [
            indexed[(tier, *design, seed)][
                "worst_floor_to_lower_flux_ratio"
            ]
            for seed in SEEDS
        ]
        velocity_values = [
            indexed[(tier, *design, seed)][
                "worst_floor_to_lower_velocity_ratio"
            ]
            for seed in SEEDS
        ]
        closest["tiers"][tier] = {
            "flux_ratio_values": flux_values,
            "flux_ratio_mean": float(np.mean(flux_values)),
            "flux_ratio_sample_sd": _sample_standard_deviation(flux_values),
            "flux_ratio_worst": max(flux_values),
            "velocity_ratio_values": velocity_values,
            "velocity_ratio_mean": float(np.mean(velocity_values)),
            "velocity_ratio_sample_sd": _sample_standard_deviation(
                velocity_values
            ),
            "velocity_ratio_worst": min(velocity_values),
        }
    summary["closest_tested_miss"] = closest
    return summary


def markdown(summary):
    lines = [
        "# Cu-fill transport factor and interaction audit",
        "",
        f"Status: **{summary['status']}**. Cases: {summary['case_count']}.",
        "",
        "This is a descriptive decomposition over the sampled coarse range. "
        "The percentages depend on the chosen levels and log-ratio scale; they "
        "are not universal physical importance or fab calibration.",
        "",
    ]
    if summary["status"] != "complete":
        lines += [
            "Validation errors:",
            "",
            *[f"- {error}" for error in summary["validation_errors"]],
            "",
        ]
        return "\n".join(lines)
    lines += [
        "| Tier | Response | Sticking | Source power | Interaction | Paired-stream residual |",
        "|---|---|---:|---:|---:|---:|",
    ]
    labels = {
        "floor_to_lower_flux_ratio": "floor/lower flux ratio",
        "floor_to_lower_velocity_ratio": "floor/lower velocity ratio",
    }
    for tier in TIERS:
        for response, label in labels.items():
            shares = summary["factor_effects"][tier][response][
                "sampled_range_variance_share"
            ]
            lines.append(
                f"| {tier} | {label} | {100 * shares['sticking']:.2f}% | "
                f"{100 * shares['source_power']:.2f}% | "
                f"{100 * shares['sticking_x_source_power']:.2f}% | "
                f"{100 * shares['paired_stream_residual']:.2f}% |"
            )
    monotonicity = summary["monotonicity"]
    geometry = summary["paired_geometry_effect"]
    lines += [
        "",
        "## Direction checks",
        "",
        "- Flux ratio is non-decreasing with sticking in "
        f"{monotonicity['flux_ratio_non_decreasing_with_sticking']['passing_sequences']}/"
        f"{monotonicity['flux_ratio_non_decreasing_with_sticking']['total_sequences']} "
        "paired tier/power/stream sequences.",
        "- Flux ratio is non-decreasing with source power in "
        f"{monotonicity['flux_ratio_non_decreasing_with_source_power']['passing_sequences']}/"
        f"{monotonicity['flux_ratio_non_decreasing_with_source_power']['total_sequences']} "
        "paired tier/sticking/stream sequences.",
        "- Nominal HBM has a larger wrong-sign flux ratio than continuity in "
        f"{geometry['nominal_minus_continuity_flux_ratio_positive_pairs']}/"
        f"{geometry['pair_count']} paired cells.",
        "",
        "## Interpretation",
        "",
        "Sticking controls nearly all sampled variation in the raw transport "
        "flux ratio. The velocity response contains a material source-power "
        "effect and interaction because the nonlinear coverage law transforms "
        "that flux. The very small paired-stream residual shows the coarse "
        "surface is reproducible, but four streams are not robustness proof. "
        "Numerical, boundary, and 3D confirmation remain mandatory.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument(
        "--reviewed-summary", type=Path, default=DEFAULT_REVIEWED_SUMMARY
    )
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.rows.read_text().splitlines()
        if line.strip()
    ]
    reviewed_summary = json.loads(args.reviewed_summary.read_text())
    summary = build_summary(rows, reviewed_summary)
    args.json.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    args.markdown.write_text(markdown(summary))
    print(json.dumps({
        "status": summary["status"],
        "cases": summary["case_count"],
    }))
    if summary["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

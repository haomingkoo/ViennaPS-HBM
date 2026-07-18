"""Review the matched current-grid Bosch ray ladder."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
from typing import Any

import numpy as np

from scripts.autoresearch_event_log import validate_log
import traveler_metrics as tm


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "evidence/numerical/bosch_ray_current_grid_ladder_manifest.json"
NEW_EVENTS = ROOT / "autoresearch-results/restart_audit/bosch_ray_current_grid_ladder_events.jsonl"
PHASE_B_EVENTS = ROOT / "evidence/numerical/bosch_ray_phase_b_events.jsonl"
OUTPUT = ROOT / "evidence/numerical/bosch_ray_current_grid_ladder_review.json"
PUBLIC_EVENTS = ROOT / "evidence/numerical/bosch_ray_current_grid_ladder_events.jsonl"
PUBLIC_CHECKPOINTS = ROOT / "evidence/numerical/bosch_ray_current_grid_ladder_checkpoints"
RAYS = (250, 500, 750, 1_000, 2_000)
METRICS = (
    "depth",
    "cd_top",
    "cd_middle",
    "cd_bottom",
    "cd_min",
    "cd_max",
    "max_bow",
    "scallop_rms",
    "maximum_center_shift",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def stats(values: list[float]) -> dict[str, float | int]:
    result: dict[str, float | int] = {
        "count": len(values),
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
        "p10": percentile(values, 0.1),
        "p90": percentile(values, 0.9),
    }
    result["sample_sd"] = statistics.stdev(values) if len(values) > 1 else 0.0
    return result


def rows(path: Path) -> list[dict[str, Any]]:
    errors, validated = validate_log(path)
    if errors:
        raise ValueError(f"invalid event log {path}: {'; '.join(errors)}")
    return [row for _, row in validated]


def load_events(manifest: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    required_pairs = {row["pair_id"] for row in manifest["pairs"]}
    selected = [
        row
        for row in (*rows(PHASE_B_EVENTS), *rows(NEW_EVENTS))
        if row["inputs"].get("pair_id") in required_pairs
        and row["numerical_profile"]["rays_per_point"] in RAYS
    ]
    latest = {
        (row["inputs"]["pair_id"], row["numerical_profile"]["rays_per_point"]): row
        for row in selected
    }
    expected = {(pair_id, rays) for pair_id in required_pairs for rays in RAYS}
    if set(latest) != expected:
        missing = sorted(expected - set(latest))
        raise ValueError(f"ray ladder incomplete: {missing}")
    if any(row["state"] != "complete_measured" for row in latest.values()):
        raise ValueError("ray ladder contains a non-complete event")
    return latest


def checkpoint_profile(row: dict[str, Any]) -> dict[str, Any]:
    public_path = PUBLIC_CHECKPOINTS / Path(row["checkpoint"]["path"]).name
    path = public_path if public_path.is_file() else ROOT / row["checkpoint"]["path"]
    if digest(path) != row["checkpoint"]["sha256"]:
        raise ValueError(f"checkpoint hash differs: {path}")
    with np.load(path, allow_pickle=False) as saved:
        review = tm.measure_full_via_profile_2d(
            saved["silicon_nodes"],
            saved["silicon_lines"],
            surface_y=0.0,
            target_cd=0.3,
            domain_x_bounds=(-0.5, 0.5),
            grid_delta=float(row["numerical_profile"]["grid_delta"]),
        )
    if review["state"] != "complete":
        raise ValueError(f"profile measurement unavailable: {path}")
    depth = float(review["metrics"]["depth"])
    samples = []
    for record in review["diagnostics"]["sample_records"]:
        left = float(record["left_wall_x"])
        right = float(record["right_wall_x"])
        samples.append({
            "depth_fraction": float(-record["y"] / depth),
            "left_wall_x": left,
            "right_wall_x": right,
            "center_x": 0.5 * (left + right),
            "cd": right - left,
        })
    return {
        "checkpoint": {
            "path": str(path.relative_to(ROOT)),
            "sha256": row["checkpoint"]["sha256"],
        },
        "samples": samples,
    }


def profile_delta(first: dict[str, Any], second: dict[str, Any]) -> dict[str, float]:
    a = first["samples"]
    b = second["samples"]
    if len(a) != len(b) or any(
        not math.isclose(x["depth_fraction"], y["depth_fraction"], abs_tol=1e-9)
        for x, y in zip(a, b, strict=True)
    ):
        raise ValueError("wall sample locations differ")
    left = [abs(x["left_wall_x"] - y["left_wall_x"]) for x, y in zip(a, b, strict=True)]
    right = [abs(x["right_wall_x"] - y["right_wall_x"]) for x, y in zip(a, b, strict=True)]
    cd = [abs(x["cd"] - y["cd"]) for x, y in zip(a, b, strict=True)]
    center = [abs(x["center_x"] - y["center_x"]) for x, y in zip(a, b, strict=True)]
    wall = left + right
    return {
        "maximum_wall_shift": max(wall),
        "rms_wall_shift": math.sqrt(statistics.fmean(value * value for value in wall)),
        "maximum_cd_shift": max(cd),
        "rms_cd_shift": math.sqrt(statistics.fmean(value * value for value in cd)),
        "maximum_center_shift": max(center),
    }


def build() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text())
    events = load_events(manifest)
    profiles = {key: checkpoint_profile(row) for key, row in events.items()}
    panels = []
    adjacent_deltas: dict[tuple[int, int], list[dict[str, float]]] = {
        pair: [] for pair in zip(RAYS, RAYS[1:])
    }

    for pair in manifest["pairs"]:
        pair_id = pair["pair_id"]
        arms = []
        for rays in RAYS:
            row = events[(pair_id, rays)]
            arms.append({
                "rays_per_point": rays,
                "event_hash": row["event_hash"],
                "elapsed_s": row["elapsed_s"],
                "selected_cycle": row["measurements"]["selected_cycle"],
                "measurements": {
                    name: row["measurements"]["etch"][name] for name in METRICS
                },
                "profile": profiles[(pair_id, rays)],
            })
        movements = []
        for lower, higher in zip(RAYS, RAYS[1:]):
            delta = profile_delta(profiles[(pair_id, lower)], profiles[(pair_id, higher)])
            metric_delta = {
                name: abs(
                    events[(pair_id, higher)]["measurements"]["etch"][name]
                    - events[(pair_id, lower)]["measurements"]["etch"][name]
                )
                for name in METRICS
            }
            adjacent_deltas[(lower, higher)].append({**delta, **metric_delta})
            movements.append({
                "from_rays": lower,
                "to_rays": higher,
                "profile_delta": delta,
                "measurement_delta": metric_delta,
            })
        panels.append({
            "pair_id": pair_id,
            "panel_id": pair["panel_id"],
            "repeat_index": pair["repeat_index"],
            "rng_seed": pair["rng_seed"],
            "arms": arms,
            "adjacent_movements": movements,
        })

    levels = []
    for rays in RAYS:
        current = [events[(pair["pair_id"], rays)] for pair in manifest["pairs"]]
        levels.append({
            "rays_per_point": rays,
            "run_count": len(current),
            "runtime_s": stats([float(row["elapsed_s"]) for row in current]),
            "measurements": {
                metric: stats([
                    float(row["measurements"]["etch"][metric]) for row in current
                ])
                for metric in METRICS
            },
        })

    repeat_spread = []
    panel_ids = list(dict.fromkeys(pair["panel_id"] for pair in manifest["pairs"]))
    for panel_id in panel_ids:
        pair_ids = [
            pair["pair_id"] for pair in manifest["pairs"] if pair["panel_id"] == panel_id
        ]
        for rays in RAYS:
            comparisons = [
                profile_delta(profiles[(first, rays)], profiles[(second, rays)])
                for first, second in itertools.combinations(pair_ids, 2)
            ]
            repeat_spread.append({
                "panel_id": panel_id,
                "rays_per_point": rays,
                "stream_count": len(pair_ids),
                "pairwise_comparison_count": len(comparisons),
                "profile_spread": {
                    key: stats([row[key] for row in comparisons]) for key in comparisons[0]
                },
                "measurement_spread": {
                    metric: stats([
                        float(events[(pair_id, rays)]["measurements"]["etch"][metric])
                        for pair_id in pair_ids
                    ])
                    for metric in METRICS
                },
            })

    adjacent = []
    for (lower, higher), deltas in adjacent_deltas.items():
        keys = deltas[0]
        adjacent.append({
            "from_rays": lower,
            "to_rays": higher,
            "runtime_ratio_of_medians": (
                next(row for row in levels if row["rays_per_point"] == higher)["runtime_s"]["median"]
                / next(row for row in levels if row["rays_per_point"] == lower)["runtime_s"]["median"]
            ),
            "movement": {key: stats([row[key] for row in deltas]) for key in keys},
        })

    return {
        "schema_version": 1,
        "study": "bosch-ray-current-grid-ladder-v1",
        "question": manifest["question"],
        "result_scope": (
            "Observed runtime, repeat spread, measurement movement, and full-wall movement "
            "for nine 2D Bosch cases at grid 0.005. No ray count is treated as truth."
        ),
        "execution": {
            "planned_runs": len(manifest["pairs"]) * len(RAYS),
            "complete_runs": len(events),
            "pair_count": len(manifest["pairs"]),
            "profile_samples_per_wall": 76,
            "grid_delta": manifest["numerics"]["grid_delta"],
            "rays_per_point": list(RAYS),
        },
        "levels": levels,
        "adjacent_levels": adjacent,
        "repeat_spread_by_panel": repeat_spread,
        "pairs": panels,
        "interpretation_rules": manifest["interpretation_rules"],
        "limits": [
            "The same seed labels do not imply identical particle paths across ray counts.",
            "The three streams estimate stochastic repeat spread for each fixed panel, not wafer variation.",
            "Wall curves are compared at the same normalized depth locations; depth movement is reported separately.",
            "This numerical study does not validate the Bosch process model against fabrication data.",
        ],
        "sources": [
            {"path": str(MANIFEST.relative_to(ROOT)), "sha256": digest(MANIFEST)},
            {"path": str(PHASE_B_EVENTS.relative_to(ROOT)), "sha256": digest(PHASE_B_EVENTS)},
            {"path": str(PUBLIC_EVENTS.relative_to(ROOT)), "sha256": digest(PUBLIC_EVENTS)},
            {"path": Path(__file__).name, "sha256": digest(Path(__file__))},
            {"path": "traveler_metrics.py", "sha256": digest(ROOT / "traveler_metrics.py")},
        ],
    }


def main() -> None:
    PUBLIC_EVENTS.write_bytes(NEW_EVENTS.read_bytes())
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "runs": document["execution"]["complete_runs"],
        "pairs": document["execution"]["pair_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

"""Publish the scoped 500/2,000-ray Bosch comparison review."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
from typing import Any

from scripts.autoresearch_event_log import validate_log


ROOT = Path(__file__).resolve().parent
RUNTIME_EVENTS = ROOT / "autoresearch-results/restart_audit/bosch_ray_phase_b_events.jsonl"
PUBLIC_EVENTS = ROOT / "evidence/numerical/bosch_ray_phase_b_events.jsonl"
MANIFEST = ROOT / "evidence/numerical/bosch_ray_phase_b_manifest.json"
OUTPUT = ROOT / "evidence/numerical/bosch_ray_phase_b_review.json"
ARCHIVE = ROOT / "evidence/numerical/bosch_ray_phase_b_checkpoints"
RAY_ARMS = (500, 2_000)
METRICS = (
    "depth",
    "cd_top",
    "cd_middle",
    "cd_bottom",
    "cd_min",
    "cd_max",
    "max_cd_error",
    "sidewall_angle_deg",
    "max_bow",
    "scallop_rms",
    "maximum_center_shift",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event_source() -> Path:
    return RUNTIME_EVENTS if RUNTIME_EVENTS.exists() else PUBLIC_EVENTS


def load_events() -> list[dict[str, Any]]:
    errors, rows = validate_log(event_source())
    if errors:
        raise ValueError("invalid Phase B event log: " + "; ".join(errors))
    return [row for _, row in rows]


def margins(metrics: dict[str, float], bands: dict[str, float]) -> dict[str, float]:
    depth_low = bands["etch_depth"] - bands["depth_tolerance"]
    depth_high = bands["etch_depth"] + bands["depth_tolerance"]
    return {
        "depth_lower": metrics["depth"] - depth_low,
        "depth_upper": depth_high - metrics["depth"],
        "width": bands["max_width_error"] - metrics["max_cd_error"],
        "bow": bands["max_wall_bulge"] - metrics["max_bow"],
    }


def compare(
    pair_id: str,
    arms: dict[int, dict[str, Any]],
    bands: dict[str, float],
    minimum_width_cells: float,
) -> dict[str, Any]:
    if set(arms) != set(RAY_ARMS):
        raise ValueError(f"pair is incomplete: {pair_id}")
    low, high = arms[500], arms[2_000]
    item: dict[str, Any] = {
        "pair_id": pair_id,
        "panel_id": low["inputs"]["panel_id"],
        "repeat_index": low["inputs"]["repeat_index"],
        "seed_label": low["inputs"]["rng_seed"],
        "arm_order_in_log": [
            row["numerical_profile"]["rays_per_point"]
            for row in sorted((low, high), key=lambda row: row["timestamp"])
        ],
        "case_keys": {"500": low["case_key"], "2000": high["case_key"]},
        "states": {"500": low["state"], "2000": high["state"]},
        "runtime_s": {"500": low["elapsed_s"], "2000": high["elapsed_s"]},
        "runtime_ratio_2000_to_500": high["elapsed_s"] / low["elapsed_s"],
        "categorical_mismatches": [],
        "measurements": None,
        "signed_deltas_500_minus_2000": None,
        "absolute_deltas": None,
        "continuous_equivalence_qualified": False,
    }
    if low["state"] != "complete_measured" or high["state"] != "complete_measured":
        item["categorical_mismatches"].append("both_arms_complete_measured")
        return item

    low_m = low["measurements"]
    high_m = high["measurements"]
    item["measurements"] = {}
    for rays, measured in ((500, low_m), (2_000, high_m)):
        etch = measured["etch"]
        finite = etch is not None and all(
            isinstance(etch[name], (int, float)) and math.isfinite(etch[name])
            for name in METRICS
        )
        item["measurements"][str(rays)] = {
            "availability": measured["availability"],
            "reason_codes": measured["reason_codes"],
            "selected_cycle": measured["selected_cycle"],
            "minimum_width_cells": measured["minimum_width_cells"],
            "resolution_available": (
                measured["minimum_width_cells"] is not None
                and measured["minimum_width_cells"] >= minimum_width_cells
            ),
            "all_required_metrics_finite": finite,
            "assumed_band_checks": measured["assumed_band_result"]["checks"],
            "assumed_band_margins": margins(etch, bands) if finite else None,
            "etch": etch,
        }

    low_summary = item["measurements"]["500"]
    high_summary = item["measurements"]["2000"]
    if low_summary["availability"] != high_summary["availability"]:
        item["categorical_mismatches"].append("availability")
    if low_summary["reason_codes"] != high_summary["reason_codes"]:
        item["categorical_mismatches"].append("reason_codes")
    if low_summary["selected_cycle"] != high_summary["selected_cycle"]:
        item["categorical_mismatches"].append("selected_cycle")
    if not low_summary["resolution_available"] or not high_summary["resolution_available"]:
        item["categorical_mismatches"].append("resolution_available")
    if not low_summary["all_required_metrics_finite"] or not high_summary["all_required_metrics_finite"]:
        item["categorical_mismatches"].append("required_metrics_finite")
    for name in ("depth", "width", "bow"):
        if (
            low_summary["assumed_band_checks"][name]
            != high_summary["assumed_band_checks"][name]
        ):
            item["categorical_mismatches"].append(f"assumed_band_{name}")

    if low_summary["etch"] is not None and high_summary["etch"] is not None:
        signed = {
            name: low_summary["etch"][name] - high_summary["etch"][name]
            for name in METRICS
        }
        item["signed_deltas_500_minus_2000"] = signed
        item["absolute_deltas"] = {name: abs(value) for name, value in signed.items()}
    return item


def archive_mismatch_checkpoints(
    events: list[dict[str, Any]], mismatch_pairs: set[str]
) -> list[dict[str, Any]]:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    archived = []
    for row in events:
        if row["inputs"]["pair_id"] not in mismatch_pairs or not row.get("checkpoint"):
            continue
        source = ROOT / row["checkpoint"]["path"]
        target = ARCHIVE / source.name
        if source.exists():
            shutil.copyfile(source, target)
        elif not target.exists():
            raise FileNotFoundError(f"checkpoint missing: {source}")
        if digest(target) != row["checkpoint"]["sha256"]:
            raise ValueError(f"checkpoint copy differs: {source}")
        archived.append(
            {
                "pair_id": row["inputs"]["pair_id"],
                "case_key": row["case_key"],
                "rays_per_point": row["numerical_profile"]["rays_per_point"],
                "path": str(target.relative_to(ROOT)),
                "sha256": digest(target),
            }
        )
    return sorted(archived, key=lambda item: (item["pair_id"], item["rays_per_point"]))


def build() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text())
    events = load_events()
    source_events = event_source()
    if source_events != PUBLIC_EVENTS:
        PUBLIC_EVENTS.write_text(source_events.read_text())
    if len(events) != manifest["execution"]["case_cap"]:
        raise ValueError("Phase B event count differs from the frozen case cap")

    by_pair: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in events:
        by_pair[row["inputs"]["pair_id"]][
            row["numerical_profile"]["rays_per_point"]
        ] = row
    comparisons = [
        compare(
            pair_id,
            by_pair[pair_id],
            manifest["assumed_comparison_bands"],
            manifest["comparison_rules"]["minimum_width_cells_must_be_at_least"],
        )
        for pair_id in sorted(by_pair)
    ]
    mismatches = [item for item in comparisons if item["categorical_mismatches"]]
    incomplete = [
        item
        for item in comparisons
        if set(item["states"].values()) != {"complete_measured"}
        or item["measurements"] is None
    ]
    mismatch_pairs = {item["pair_id"] for item in mismatches}
    archived = archive_mismatch_checkpoints(events, mismatch_pairs)

    complete = [item for item in comparisons if item["absolute_deltas"] is not None]
    maximum_deltas = {}
    for metric in METRICS:
        worst = max(complete, key=lambda item: item["absolute_deltas"][metric])
        maximum_deltas[metric] = {
            "value": worst["absolute_deltas"][metric],
            "pair_id": worst["pair_id"],
        }

    panel_summaries = []
    for panel_id in sorted({item["panel_id"] for item in comparisons}):
        panel_items = [item for item in comparisons if item["panel_id"] == panel_id]
        width_margins = [
            item["measurements"][arm]["assumed_band_margins"]["width"]
            for item in panel_items
            for arm in ("500", "2000")
            if item["measurements"] is not None
        ]
        panel_summaries.append(
            {
                "panel_id": panel_id,
                "pair_count": len(panel_items),
                "categorical_mismatch_pairs": sum(
                    bool(item["categorical_mismatches"]) for item in panel_items
                ),
                "closest_absolute_width_margin": min(
                    (abs(value) for value in width_margins), default=None
                ),
                "width_boundary_interpretation": (
                    "Observed margin only; no numerical-equivalence allowance."
                    if width_margins
                    else "No usable width margin."
                ),
            }
        )

    if incomplete:
        decision = "inconclusive_due_to_missing_or_failed_comparison"
    elif mismatches:
        decision = "reject_500_for_categorical_triage_on_this_panel"
    else:
        decision = "advance_500_to_later_numerical_checks_categorical_agreement_only"
    runtime_ratios = [item["runtime_ratio_2000_to_500"] for item in comparisons]
    return {
        "schema_version": 1,
        "campaign": manifest["campaign"],
        "status": "complete_reviewed",
        "highest_supported_claim": (
            "Across 13 exact unseen seed-labelled pairs at grid 0.005, 500 rays "
            "changed the assumed depth classification in all three depth-boundary "
            "pairs and the assumed bow classification in one of three narrow-profile "
            "pairs relative to 2,000 rays."
        ),
        "sources": [
            {"path": str(MANIFEST.relative_to(ROOT)), "sha256": digest(MANIFEST)},
            {"path": str(PUBLIC_EVENTS.relative_to(ROOT)), "sha256": digest(PUBLIC_EVENTS)},
            {"path": Path(__file__).name, "sha256": digest(Path(__file__))},
        ],
        "execution": {
            "planned_runs": manifest["execution"]["case_cap"],
            "state_counts": dict(sorted(Counter(row["state"] for row in events).items())),
            "pair_count": len(comparisons),
            "median_runtime_ratio_2000_to_500": statistics.median(runtime_ratios),
            "minimum_runtime_ratio_2000_to_500": min(runtime_ratios),
            "maximum_runtime_ratio_2000_to_500": max(runtime_ratios),
            "runtime_interpretation": manifest["reporting_contract"]["runtime_interpretation"],
        },
        "comparisons": comparisons,
        "categorical_mismatches": [
            {
                "pair_id": item["pair_id"],
                "panel_id": item["panel_id"],
                "mismatches": item["categorical_mismatches"],
            }
            for item in mismatches
        ],
        "maximum_absolute_deltas": maximum_deltas,
        "panel_summaries": panel_summaries,
        "archived_mismatch_checkpoints": archived,
        "decision": {
            "result": decision,
            "candidate_500_rays": "does_not_advance",
            "next_action": (
                "Do not use 500 rays as the broad Bosch exploration setting. "
                "Evaluate a fresh intermediate ray count or redesign the numerical ladder."
            ),
        },
        "prohibited_claims": [
            "2,000 rays is numerical truth.",
            "500 rays is universally inaccurate.",
            "Continuous measurement equivalence was tested.",
            "The assumed comparison bands are fabrication specifications.",
            "Grid, advection, domain, caps, or execution layout are qualified.",
        ],
        "limits": manifest["limits"],
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "decision": document["decision"],
                "mismatch_pairs": len(document["categorical_mismatches"]),
                "state_counts": document["execution"]["state_counts"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

"""Publish the paired 250/500-ray Bosch triage review."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics

from scripts.autoresearch_event_log import validate_log


ROOT = Path(__file__).resolve().parent
RUNTIME_EVENTS = ROOT / "autoresearch-results/restart_audit/bosch_ray_phase_a_events.jsonl"
PUBLIC_EVENTS = ROOT / "evidence/numerical/bosch_ray_phase_a_events.jsonl"
MANIFEST = ROOT / "evidence/numerical/bosch_ray_phase_a_manifest.json"
OUTPUT = ROOT / "evidence/numerical/bosch_ray_phase_a_review.json"
ARCHIVE = ROOT / "evidence/numerical/bosch_ray_phase_a_checkpoints"
METRICS = (
    "depth", "cd_top", "cd_middle", "cd_bottom", "cd_min", "cd_max",
    "max_cd_error", "sidewall_angle_deg", "max_bow", "scallop_rms",
    "maximum_center_shift",
)
ARCHIVE_PANELS = {"narrow_profile", "availability_challenge"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event_source() -> Path:
    return RUNTIME_EVENTS if RUNTIME_EVENTS.exists() else PUBLIC_EVENTS


def load_events() -> list[dict]:
    errors, rows = validate_log(event_source())
    if errors:
        raise ValueError("invalid Phase A event log: " + "; ".join(errors))
    return [row for _, row in rows]


def band_checks(row: dict) -> dict | None:
    measurements = row.get("measurements")
    return measurements and measurements.get("assumed_band_result", {}).get("checks")


def compare(pair_id: str, arms: dict[int, tuple[int, dict]]) -> dict:
    if set(arms) != {250, 500}:
        raise ValueError(f"pair is incomplete: {pair_id}")
    line_250, low = arms[250]
    line_500, high = arms[500]
    result = {
        "pair_id": pair_id,
        "panel_id": low["inputs"]["panel_id"],
        "repeat_index": low["inputs"]["repeat_index"],
        "sources": {
            "250": {"line_number": line_250, "event_hash": low["event_hash"]},
            "500": {"line_number": line_500, "event_hash": high["event_hash"]},
        },
        "states": {"250": low["state"], "500": high["state"]},
        "runtime_s": {"250": low["elapsed_s"], "500": high["elapsed_s"]},
        "state_match": low["state"] == high["state"],
        "availability_match": None,
        "selected_cycle_match": None,
        "assumed_band_check_matches": None,
        "metric_deltas": None,
        "failure": None,
    }
    if low["state"] != "complete_measured" or high["state"] != "complete_measured":
        guard_depths = {}
        for rays, row in ((250, low), (500, high)):
            message = (row.get("error") or {}).get("message", "")
            match = re.fullmatch(r"etch barely moved: depth=(-?[0-9.]+)", message)
            guard_depths[str(rays)] = float(match.group(1)) if match else None
        result["failure"] = {
            "classification": "wrapper_minimum_etch_depth_guard",
            "guard_triggered_at_both_ray_counts": all(
                row["state"] == "failed_deterministic" for row in (low, high)
            ),
            "reported_depths": guard_depths,
            "interpretation": (
                "The wrapper stopped both ray arms because the modeled etch stayed "
                "below its configured minimum resolved depth. No profile comparison "
                "is available for this pair."
            ),
        }
        return result

    low_measurements = low["measurements"]
    high_measurements = high["measurements"]
    result["availability_match"] = (
        low_measurements["availability"] == high_measurements["availability"]
    )
    result["selected_cycle_match"] = (
        low_measurements["selected_cycle"] == high_measurements["selected_cycle"]
    )
    checks_250 = band_checks(low)
    checks_500 = band_checks(high)
    assert checks_250 is not None and checks_500 is not None
    result["assumed_band_check_matches"] = {
        name: checks_250[name] == checks_500[name]
        for name in ("depth", "width", "bow")
    }
    if low_measurements["etch"] is not None and high_measurements["etch"] is not None:
        result["metric_deltas"] = {
            name: abs(low_measurements["etch"][name] - high_measurements["etch"][name])
            for name in METRICS
        }
    return result


def build() -> dict:
    events = load_events()
    source_events = event_source()
    if source_events != PUBLIC_EVENTS:
        PUBLIC_EVENTS.write_text(source_events.read_text())
    public_sha = digest(PUBLIC_EVENTS)
    by_pair: dict[str, dict[int, tuple[int, dict]]] = defaultdict(dict)
    for line_number, row in enumerate(events, 1):
        by_pair[row["inputs"]["pair_id"]][row["numerical_profile"]["rays_per_point"]] = (
            line_number, row
        )
    comparisons = [compare(pair_id, by_pair[pair_id]) for pair_id in sorted(by_pair)]

    complete = [item for item in comparisons if item["metric_deltas"] is not None]
    maximum_deltas = {}
    for metric in METRICS:
        worst = max(complete, key=lambda item: item["metric_deltas"][metric])
        maximum_deltas[metric] = {
            "value": worst["metric_deltas"][metric],
            "pair_id": worst["pair_id"],
        }

    repeated_values: dict[tuple[str, int, str], list[float]] = defaultdict(list)
    for row in events:
        if row["state"] != "complete_measured" or row["measurements"]["etch"] is None:
            continue
        panel_id = row["inputs"]["panel_id"]
        if panel_id not in {"design_center", "narrow_profile"}:
            continue
        rays = row["numerical_profile"]["rays_per_point"]
        for metric in METRICS:
            repeated_values[(panel_id, rays, metric)].append(row["measurements"]["etch"][metric])
    repeat_ranges = {}
    for (panel_id, rays, metric), values in repeated_values.items():
        repeat_ranges.setdefault(panel_id, {}).setdefault(str(rays), {})[metric] = {
            "count": len(values),
            "observed_range": max(values) - min(values),
            "interpretation": "observed three-stream range; not a population uncertainty bound",
        }

    archived = []
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for row in events:
        if row["inputs"]["panel_id"] not in ARCHIVE_PANELS or not row.get("checkpoint"):
            continue
        source = ROOT / row["checkpoint"]["path"]
        target = ARCHIVE / source.name
        if source.exists():
            shutil.copyfile(source, target)
        elif not target.exists():
            raise FileNotFoundError(f"checkpoint missing: {source}")
        if digest(target) != row["checkpoint"]["sha256"]:
            raise ValueError(f"checkpoint copy differs: {source}")
        archived.append({
            "case_id": row["case_key"],
            "panel_id": row["inputs"]["panel_id"],
            "rays_per_point": row["numerical_profile"]["rays_per_point"],
            "path": str(target.relative_to(ROOT)),
            "sha256": digest(target),
        })

    categorical_mismatches = [
        {
            "pair_id": item["pair_id"],
            "panel_id": item["panel_id"],
            "availability_match": item["availability_match"],
            "selected_cycle_match": item["selected_cycle_match"],
            "assumed_band_check_matches": item["assumed_band_check_matches"],
        }
        for item in complete
        if item["availability_match"] is not True
        or item["selected_cycle_match"] is not True
        or not all(item["assumed_band_check_matches"].values())
    ]
    runtime_ratios = [
        item["runtime_s"]["500"] / item["runtime_s"]["250"] for item in complete
    ]
    symmetric_guard_pairs = sum(
        item["failure"] is not None
        and item["failure"]["guard_triggered_at_both_ray_counts"]
        for item in comparisons
    )
    return {
        "schema_version": 1,
        "campaign": "bosch-ray-phase-a-v1",
        "status": "complete_reviewed",
        "highest_supported_claim": (
            "Fresh 250- and 500-ray pairs agree on the current-grid reference and "
            "center cases, but the narrow profile changes the assumed bow-band "
            "decision in all three streams and the availability challenge changes "
            "the assumed depth-band decision. 250 rays does not advance."
        ),
        "sources": [
            {"path": str(MANIFEST.relative_to(ROOT)), "sha256": digest(MANIFEST)},
            {"path": str(PUBLIC_EVENTS.relative_to(ROOT)), "sha256": public_sha},
            {"path": Path(__file__).name, "sha256": digest(Path(__file__))},
        ],
        "execution": {
            "planned_runs": 32,
            "state_counts": dict(sorted(Counter(row["state"] for row in events).items())),
            "complete_pairs": len(complete),
            "symmetric_minimum_depth_guard_pairs": symmetric_guard_pairs,
            "median_500_to_250_runtime_ratio_on_complete_pairs": statistics.median(runtime_ratios),
            "runtime_interpretation": "same host during this campaign; broad cost comparison only",
        },
        "comparisons": comparisons,
        "maximum_absolute_deltas": maximum_deltas,
        "repeat_ranges": repeat_ranges,
        "categorical_mismatches": categorical_mismatches,
        "archived_mismatch_checkpoints": archived,
        "decision": {
            "candidate_250_rays": "rejected_for_phase_b",
            "candidate_500_rays": "requires_fresh_2000_ray_phase_b",
            "reason": (
                "250 rays did not preserve all assumed-band decisions across the "
                "paired panel. Phase A cannot qualify 500 rays."
            ),
        },
        "limits": [
            "Assumed-band changes are study comparisons, not fabrication pass/fail changes.",
            "Continuous metric differences are reported without an engineering-equivalence claim.",
            "The two low-movement recipes triggered the same wrapper guard at both ray counts and provide no profile comparison.",
            "The result applies only to this 0.005-grid 2D panel.",
            "2,000 rays remains a tested comparator, not numerical truth.",
        ],
    }


def main() -> None:
    document = build()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": document["decision"], "state_counts": document["execution"]["state_counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()

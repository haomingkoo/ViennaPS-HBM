"""Run the missing arms of the current-grid Bosch ray ladder."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
from pathlib import Path
from typing import Any

import bosch_ray_phase_a as phase_a
import bosch_ray_phase_b as phase_b
from scripts.autoresearch_event_log import append_event, validate_log


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "evidence/numerical/bosch_ray_current_grid_ladder_manifest.json"
OUTPUT = ROOT / "autoresearch-results/restart_audit/bosch_ray_current_grid_ladder_events.jsonl"
CHECKPOINTS = OUTPUT.parent / "bosch_ray_current_grid_ladder_checkpoints"
PHASE_B_MANIFEST = ROOT / "evidence/numerical/bosch_ray_phase_b_manifest.json"
PHASE_B_EVENTS = ROOT / "evidence/numerical/bosch_ray_phase_b_events.jsonl"
NEW_RAY_ARMS = (250, 750, 1_000)
REUSED_RAY_ARMS = (500, 2_000)
PANEL_IDS = ("design_center", "narrow_profile", "depth_boundary")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)


def case_id(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()[:16]


def phase_b_cases() -> list[dict[str, Any]]:
    manifest = json.loads(PHASE_B_MANIFEST.read_text())
    if manifest != phase_b.build_manifest():
        raise ValueError("Phase B manifest differs from its builder or cited sources")
    return [
        row for row in phase_b.expand_cases(manifest)
        if row["panel_id"] in PANEL_IDS
    ]


def paired_sources() -> list[dict[str, Any]]:
    rows = phase_b_cases()
    grouped: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["pair_id"], {})[row["rays_per_point"]] = row
    expected_pairs = 3 * len(PANEL_IDS)
    if len(grouped) != expected_pairs:
        raise ValueError(f"expected {expected_pairs} Phase B pairs")
    result = []
    ordered = sorted(
        grouped.items(),
        key=lambda item: (PANEL_IDS.index(item[1][500]["panel_id"]), item[0]),
    )
    for pair_id, arms in ordered:
        if set(arms) != set(REUSED_RAY_ARMS):
            raise ValueError(f"Phase B arms differ for {pair_id}")
        first = arms[500]
        result.append({
            "pair_id": pair_id,
            "panel_id": first["panel_id"],
            "roles": first["roles"],
            "repeat_index": first["repeat_index"],
            "geometry": first["geometry"],
            "recipe": first["recipe"],
            "maximum_cycles": first["maximum_cycles"],
            "grid_delta": first["grid_delta"],
            "rng_seed": first["rng_seed"],
            "phase_b_case_ids": {
                str(rays): arms[rays]["case_id"] for rays in REUSED_RAY_ARMS
            },
        })
    return result


def build_manifest() -> dict[str, Any]:
    phase_b_manifest = json.loads(PHASE_B_MANIFEST.read_text())
    pairs = paired_sources()
    return {
        "schema_version": 1,
        "campaign": "bosch-ray-current-grid-ladder-v1",
        "question": (
            "How do wall time, repeat spread, and measured shape movement change "
            "across 250, 500, 750, 1,000, and 2,000 rays at grid 0.005?"
        ),
        "authority": (
            "Observed cost and response movement for nine exact Phase B pairs. "
            "No ray count is truth and no inherited tutorial band is an accuracy limit."
        ),
        "pairs": pairs,
        "numerics": {
            "grid_delta": 0.005,
            "new_ray_arms": list(NEW_RAY_ARMS),
            "reused_ray_arms": list(REUSED_RAY_ARMS),
            "complete_ladder": sorted((*NEW_RAY_ARMS, *REUSED_RAY_ARMS)),
            "threads_per_worker": phase_b_manifest["numerics"]["threads_per_worker"],
            "maximum_workers": phase_b_manifest["numerics"]["maximum_workers"],
            "simulation_dimension": 2,
        },
        "rng_policy": {
            "paired_by_seed_label": True,
            "pointwise_common_random_numbers_claimed": False,
            "pair_count": len(pairs),
            "seed_labels": [row["rng_seed"] for row in pairs],
        },
        "measurements": [
            "selected cycle",
            "etch depth",
            "top, middle, bottom, minimum, and maximum CD",
            "maximum bow",
            "scallop RMS",
            "sidewall angle",
            "measurement availability and reason codes",
            "wall time",
        ],
        "execution": {
            "new_case_cap": len(pairs) * len(NEW_RAY_ARMS),
            "checkpoint_policy": "save one selected-cycle checkpoint per new run",
            "retry_policy": "one identical retry for a first transient infrastructure error only",
            "scientific_stop_rule": "run every frozen case to a logged terminal state",
        },
        "assumed_comparison_bands": phase_b_manifest["assumed_comparison_bands"],
        "interpretation_rules": [
            "Report raw observations without converting movement into accuracy error.",
            "Keep the three geometry panels separate.",
            "Do not assume that spread or movement improves monotonically.",
            "Do not select an exploration setting from runtime alone.",
            "The selected-cycle rule is inherited for exact compatibility with Phase B; its tutorial bands are not accuracy limits.",
        ],
        "sources": [
            {"path": Path(__file__).name, "sha256": digest(Path(__file__))},
            {"path": str(PHASE_B_MANIFEST.relative_to(ROOT)), "sha256": digest(PHASE_B_MANIFEST)},
            {"path": str(PHASE_B_EVENTS.relative_to(ROOT)), "sha256": digest(PHASE_B_EVENTS)},
            {"path": Path(phase_b.__file__).name, "sha256": digest(Path(phase_b.__file__))},
            {"path": Path(phase_a.__file__).name, "sha256": digest(Path(phase_a.__file__))},
            {"path": "traveler_metrics.py", "sha256": digest(ROOT / "traveler_metrics.py")},
            {"path": "tsv_process.py", "sha256": digest(ROOT / "tsv_process.py")},
            {"path": "scripts/autoresearch_event_log.py", "sha256": digest(ROOT / "scripts/autoresearch_event_log.py")},
        ],
    }


def freeze_manifest() -> None:
    document = build_manifest()
    rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if MANIFEST.exists() and MANIFEST.read_text() != rendered:
        raise ValueError(f"refusing to overwrite different manifest: {MANIFEST}")
    MANIFEST.write_text(rendered)
    print(json.dumps({
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "pairs": len(document["pairs"]),
        "new_runs": document["execution"]["new_case_cap"],
    }, sort_keys=True))


def expand_cases(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    cases = []
    for pair_index, pair in enumerate(manifest["pairs"]):
        arms = NEW_RAY_ARMS if pair_index % 2 == 0 else tuple(reversed(NEW_RAY_ARMS))
        for rays in arms:
            payload = {
                "campaign": manifest["campaign"],
                "panel_id": pair["panel_id"],
                "roles": pair["roles"],
                "pair_id": pair["pair_id"],
                "repeat_index": pair["repeat_index"],
                "geometry": pair["geometry"],
                "recipe": pair["recipe"],
                "maximum_cycles": pair["maximum_cycles"],
                "grid_delta": pair["grid_delta"],
                "rays_per_point": rays,
                "rng_seed": pair["rng_seed"],
            }
            cases.append({**payload, "case_id": case_id(payload)})
    return cases


def environment() -> dict[str, Any]:
    result = phase_b.environment()
    result["runner_sha256"] = digest(Path(__file__))
    result["execution_helper_sha256"] = digest(Path(phase_a.__file__))
    return result


def run_case(task: tuple[dict[str, Any], dict[str, Any], str, dict[str, Any], int]) -> dict[str, Any]:
    phase_a.CHECKPOINTS = CHECKPOINTS
    event = phase_a.run_case(task)
    event["stage"] = "bosch_ray_current_grid_ladder"
    return event


def latest_events(manifest: dict[str, Any], manifest_hash: str) -> dict[str, dict[str, Any]]:
    if not OUTPUT.exists():
        return {}
    errors, rows = validate_log(OUTPUT)
    if errors:
        raise ValueError("invalid event log: " + "; ".join(errors))
    expected = {case["case_id"]: case for case in expand_cases(manifest)}
    latest = {}
    for line_number, row in rows:
        case = expected.get(row["case_key"])
        if case is None or row["manifest_hash"] != manifest_hash:
            raise ValueError(f"stale or unexpected event at line {line_number}")
        expected_hash = hashlib.sha256(canonical(case).encode()).hexdigest()
        if row["case_payload_hash"] != expected_hash:
            raise ValueError(f"case payload differs at line {line_number}")
        latest[row["case_key"]] = row
    return latest


def run(max_cases: int | None) -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest != build_manifest():
        raise ValueError("manifest differs from builder or cited sources")
    manifest_hash = digest(MANIFEST)
    cases = expand_cases(manifest)
    latest = latest_events(manifest, manifest_hash)
    pending_all = [
        (case, 2 if case["case_id"] in latest and latest[case["case_id"]]["retryable"] else 1)
        for case in cases
        if case["case_id"] not in latest or latest[case["case_id"]]["retryable"]
    ]
    if max_cases is not None and max_cases % len(NEW_RAY_ARMS):
        raise ValueError("--max-cases must preserve complete three-arm pairs")
    pending = pending_all[:max_cases] if max_cases is not None else pending_all
    print(
        f"planned={len(cases)} terminal={len(cases) - len(pending_all)} "
        f"pending={len(pending_all)} selected={len(pending)}",
        flush=True,
    )
    env = environment()
    with futures.ProcessPoolExecutor(max_workers=manifest["numerics"]["maximum_workers"]) as executor:
        jobs = {
            executor.submit(run_case, (case, manifest, manifest_hash, env, attempt)): case
            for case, attempt in pending
        }
        for index, future in enumerate(futures.as_completed(jobs), 1):
            event = future.result()
            append_event(OUTPUT, event)
            print(
                f"[{index}/{len(pending)}] {event['inputs']['pair_id']} "
                f"rays={event['numerical_profile']['rays_per_point']} "
                f"state={event['state']} elapsed={event['elapsed_s']:.1f}s",
                flush=True,
            )
    errors, rows = validate_log(OUTPUT)
    if errors:
        raise ValueError("event log failed validation: " + "; ".join(errors))
    print(f"validated_events={len(rows)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "run", "status"))
    parser.add_argument("--max-cases", type=int)
    args = parser.parse_args()
    if args.action == "build":
        freeze_manifest()
        return
    manifest = json.loads(MANIFEST.read_text())
    if args.action == "run":
        run(args.max_cases)
        return
    cases = expand_cases(manifest)
    latest = latest_events(manifest, digest(MANIFEST))
    print(json.dumps({
        "planned": len(cases),
        "terminal": sum(not row["retryable"] for row in latest.values()),
        "pending": sum(
            case["case_id"] not in latest or latest[case["case_id"]]["retryable"]
            for case in cases
        ),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

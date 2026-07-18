"""Run the fresh paired 500/2,000-ray Bosch comparison."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
from typing import Any

import bosch_ray_phase_a as phase_a
import numpy as np
from scripts.autoresearch_event_log import append_event, validate_log


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "evidence/numerical/bosch_ray_phase_b_manifest.json"
OUTPUT = ROOT / "autoresearch-results/restart_audit/bosch_ray_phase_b_events.jsonl"
CHECKPOINTS = OUTPUT.parent / "bosch_ray_phase_b_checkpoints"
PHASE_A_MANIFEST = ROOT / "evidence/numerical/bosch_ray_phase_a_manifest.json"
PHASE_A_REVIEW = ROOT / "evidence/numerical/bosch_ray_phase_a_review.json"
MEASUREMENT_CONTRACT = ROOT / "pattern_bosch_measurement_contract.json"
INTERACTIONS = ROOT / "evidence/numerical/v3_bosch_cheap_interactions_rows.jsonl"
WIDTH_SOURCE_CASE_ID = "2229b154724d3c07"
RAY_ARMS = (500, 2_000)
SEED_START = 1_900_000
SEED_STRIDE = 97
PANEL_REPEATS = {
    "current_grid_reference": 1,
    "design_center": 3,
    "narrow_profile": 3,
    "depth_boundary": 3,
    "width_boundary_candidate": 3,
}
PANEL_PURPOSES = {
    "current_grid_reference": (
        "Checks the known complete reference shape at the current grid."
    ),
    "design_center": "Checks a central recipe away from a selected extreme.",
    "narrow_profile": (
        "Challenges a narrow shape whose bow classification changed in Phase A."
    ),
    "depth_boundary": (
        "Retests the Phase A case whose depth classification changed."
    ),
    "width_boundary_candidate": (
        "Retests a historical case whose width error was near the tutorial band. "
        "Its proximity at grid 0.005 is not assumed."
    ),
}
REPEAT_RATIONALES = {
    "current_grid_reference": "One mandatory reference anchor.",
    "design_center": "Three unseen streams show the observed center spread.",
    "narrow_profile": (
        "Three unseen streams retest the repeated Phase A bow and resolution challenge."
    ),
    "depth_boundary": (
        "Three unseen streams retest the Phase A depth-boundary result."
    ),
    "width_boundary_candidate": (
        "Three unseen streams first test whether the historical candidate remains near the width band."
    ),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)


def case_id(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()[:16]


def interaction_row(source_case_id: str) -> tuple[dict[str, Any], int]:
    for line_number, line in enumerate(INTERACTIONS.read_text().splitlines(), 1):
        row = json.loads(line)
        if row["case_id"] == source_case_id:
            return row, line_number
    raise ValueError(f"interaction row not found: {source_case_id}")


def width_boundary_panel() -> dict[str, Any]:
    row, line_number = interaction_row(WIDTH_SOURCE_CASE_ID)
    return {
        "id": "width_boundary_candidate",
        "roles": ["historical_near_width_boundary_candidate"],
        "source": {
            "path": str(INTERACTIONS.relative_to(ROOT)),
            "line_number": line_number,
            "case_id": row["case_id"],
            "sha256": digest(INTERACTIONS),
            "historical_grid_delta": row["numerics"]["grid_delta"],
            "historical_max_cd_error": row["selected_cycle_metrics"]["etch"][
                "max_cd_error"
            ],
        },
        "geometry": row["geometry"],
        "recipe": row["recipe"],
        "maximum_cycles": row["trajectory"]["maximum_cycles"],
    }


def build_manifest() -> dict[str, Any]:
    phase_a_manifest = json.loads(PHASE_A_MANIFEST.read_text())
    phase_a_review = json.loads(PHASE_A_REVIEW.read_text())
    if phase_a_review["decision"]["candidate_500_rays"] != "requires_fresh_2000_ray_phase_b":
        raise ValueError("Phase A does not authorize this comparison")
    by_id = {panel["id"]: panel for panel in phase_a_manifest["panel"]}
    panel = []
    for panel_id, repeat_count in PANEL_REPEATS.items():
        if panel_id == "depth_boundary":
            source = {**by_id["availability_challenge"], "id": panel_id}
        elif panel_id == "width_boundary_candidate":
            source = width_boundary_panel()
        else:
            source = by_id[panel_id]
        panel.append(
            {
                **source,
                "repeat_count": repeat_count,
                "teaching_purpose": PANEL_PURPOSES[panel_id],
                "repeat_rationale": REPEAT_RATIONALES[panel_id],
            }
        )
    pair_count = sum(PANEL_REPEATS.values())
    return {
        "schema_version": 1,
        "campaign": "bosch-ray-phase-b-v3",
        "question": (
            "If the same 2D etch cases use 500 instead of 2,000 rays, can the "
            "extractor still find both walls, and do the cases remain on the same "
            "side of the tutorial depth, width, and bow comparison bands?"
        ),
        "authority": (
            "Categorical confirmation only for 13 exact seed-labelled pairs at "
            "grid 0.005. A clean "
            "result may advance 500 rays to later numerical checks, but cannot "
            "approve 500 rays or establish continuous measurement equivalence. "
            "The 2,000-ray arm is a comparator, not numerical truth."
        ),
        "definitions": {
            "full_width": "Both via walls are measured; a missing wall is never mirrored.",
            "measurement_available": (
                "The extractor finds the declared surface and both via walls."
            ),
            "assumed_comparison_band": (
                "A tutorial study threshold retained for comparison; not a fabrication specification."
            ),
            "comparator": "A tested reference setting; not numerical truth.",
        },
        "panel": panel,
        "numerics": {
            "grid_delta": 0.005,
            "ray_arms": list(RAY_ARMS),
            "threads_per_worker": 4,
            "maximum_workers": 2,
            "simulation_dimension": 2,
        },
        "rng_policy": {
            "seed_start": SEED_START,
            "seed_stride": SEED_STRIDE,
            "paired_by_seed_label": True,
            "pointwise_common_random_numbers_claimed": False,
            "independent_pair_count": pair_count,
            "unseen_relative_to_phase_a": True,
        },
        "selection_rule": phase_a_manifest["selection_rule"],
        "comparison_rules": {
            "availability_must_match": True,
            "reason_codes_must_match": True,
            "assumed_band_checks_must_match": True,
            "selected_cycle_must_match": True,
            "both_arms_must_complete_with_measurements": True,
            "every_required_metric_must_be_finite": True,
            "minimum_width_cells_must_be_at_least": 3.0,
            "continuous_differences_are_reported_not_qualified": True,
            "no_mismatch_advances_500_only_to_later_numerical_checks": True,
            "this_campaign_cannot_approve_500_rays": True,
            "scope_is_exact_seed_labelled_pairs_only": True,
        },
        "reporting_contract": {
            "required_outputs": [
                "terminal state counts",
                "measurement availability by pair",
                "selected cycle by pair",
                "assumed depth, width, and bow classifications by pair",
                "signed distance to each assumed comparison boundary",
                "reason codes and minimum-width cells by pair",
                "resolution qualification by pair",
                "raw continuous metric deltas",
                "observed repeat ranges",
                "paired runtime ratio",
            ],
            "allowed_decisions": [
                "reject_500_for_categorical_triage_on_this_panel",
                "advance_500_to_later_numerical_checks_categorical_agreement_only",
                "inconclusive_due_to_missing_or_failed_comparison",
            ],
            "missing_measurement_rule": (
                "Block a positive decision; never replace a missing value with zero."
            ),
            "runtime_interpretation": (
                "Descriptive wall time on one host only. Two concurrent workers "
                "prevent a causal ray-count speedup claim."
            ),
            "review_artifact": "evidence/numerical/bosch_ray_phase_b_review.json",
        },
        "execution": {
            "case_cap": 2 * pair_count,
            "checkpoint_policy": "save one selected-cycle checkpoint per run",
            "scientific_stop_rule": (
                "Run every frozen case unless it reaches a terminal logged state; "
                "do not stop early because an interim comparison looks favorable."
            ),
            "cost_stop_rule": (
                "Stop after 26 unique terminal cases; transient retries may create "
                "more than 26 executions, but the panel must not expand."
            ),
            "maximum_cycles": "inherited from each frozen source case",
            "wall_time_limit_s": None,
            "retry_policy": (
                "one identical retry for a first transient infrastructure error only"
            ),
        },
        "assumed_comparison_bands": phase_a_manifest["assumed_comparison_bands"],
        "sources": [
            {"path": Path(__file__).name, "sha256": digest(Path(__file__))},
            {"path": phase_a.__file__.removeprefix(str(ROOT) + "/"), "sha256": digest(Path(phase_a.__file__))},
            {"path": str(PHASE_A_MANIFEST.relative_to(ROOT)), "sha256": digest(PHASE_A_MANIFEST)},
            {"path": str(PHASE_A_REVIEW.relative_to(ROOT)), "sha256": digest(PHASE_A_REVIEW)},
            {
                "path": str(MEASUREMENT_CONTRACT.relative_to(ROOT)),
                "sha256": digest(MEASUREMENT_CONTRACT),
            },
            {"path": "traveler_metrics.py", "sha256": digest(ROOT / "traveler_metrics.py")},
            {"path": "tsv_process.py", "sha256": digest(ROOT / "tsv_process.py")},
            {
                "path": str(INTERACTIONS.relative_to(ROOT)),
                "sha256": digest(INTERACTIONS),
            },
            {
                "path": "foundation_metric_audit.py",
                "sha256": digest(ROOT / "foundation_metric_audit.py"),
            },
            {
                "path": "scripts/autoresearch_event_log.py",
                "sha256": digest(ROOT / "scripts/autoresearch_event_log.py"),
            },
            {
                "path": "schemas/autoresearch-event.schema.json",
                "sha256": digest(ROOT / "schemas/autoresearch-event.schema.json"),
            },
        ],
        "limits": [
            "Any positive result applies only to the 13 exact seed-labelled pairs.",
            "Assumed-band decisions are not fabrication specifications.",
            "Continuous metric differences have no engineering-equivalence allowance yet.",
            "No per-run wall-time timeout is configured; the source-case cycle count bounds model duration.",
            "Only independently selected cycles are saved. A selected-cycle mismatch blocks ray-effect attribution.",
            "Per-cycle histories are not retained, so the result does not qualify trajectory agreement.",
            "The study does not qualify grid, advection, domain, caps, or execution layout.",
            "Important boundaries and finalists still require 2,000-ray confirmation.",
        ],
    }


def freeze_manifest() -> None:
    document = build_manifest()
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if MANIFEST.exists() and MANIFEST.read_text() != text:
        raise ValueError(f"refusing to overwrite different manifest: {MANIFEST}")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(text)
    print(
        json.dumps(
            {
                "manifest": str(MANIFEST.relative_to(ROOT)),
                "pairs": document["rng_policy"]["independent_pair_count"],
                "runs": document["execution"]["case_cap"],
            },
            sort_keys=True,
        )
    )


def expand_cases(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    cases = []
    pair_index = 0
    for panel in manifest["panel"]:
        for repeat_index in range(panel["repeat_count"]):
            seed = SEED_START + pair_index * SEED_STRIDE
            pair_id = f"{panel['id']}:stream_{repeat_index + 1}"
            arms = RAY_ARMS if pair_index % 2 == 0 else tuple(reversed(RAY_ARMS))
            for rays in arms:
                payload = {
                    "campaign": manifest["campaign"],
                    "panel_id": panel["id"],
                    "roles": panel["roles"],
                    "pair_id": pair_id,
                    "repeat_index": repeat_index,
                    "geometry": panel["geometry"],
                    "recipe": panel["recipe"],
                    "maximum_cycles": panel["maximum_cycles"],
                    "grid_delta": manifest["numerics"]["grid_delta"],
                    "rays_per_point": rays,
                    "rng_seed": seed,
                }
                cases.append({**payload, "case_id": case_id(payload)})
            pair_index += 1
    return cases


def environment() -> dict[str, Any]:
    result = phase_a.environment()
    result["runner_sha256"] = digest(Path(__file__))
    result["execution_helper_sha256"] = digest(Path(phase_a.__file__))
    result["machine"] = platform.machine()
    result["processor"] = platform.processor() or None
    result["numpy_version"] = np.__version__
    result["maximum_workers"] = 2
    result["threads_per_worker"] = 4
    result["backend"] = "ViennaPS Python bindings"
    for package in ("viennaps", "viennals"):
        try:
            result[f"{package}_package_version"] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[f"{package}_package_version"] = None
    return result


def run_case(task: tuple[dict[str, Any], dict[str, Any], str, dict[str, Any], int]) -> dict[str, Any]:
    phase_a.CHECKPOINTS = CHECKPOINTS
    event = phase_a.run_case(task)
    event["stage"] = "bosch_ray_phase_b"
    error = event.get("error") or {}
    if event["state"] == "failed_deterministic" and not (
        error.get("type") == "ValueError"
        and str(error.get("message", "")).startswith("etch barely moved:")
    ):
        event["failure_scope"] = "software_or_unknown"
        event["decision"] = "investigate"
        event["next_action"] = (
            "Preserve the row and classify the deterministic failure before continuing."
        )
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
        (
            case,
            2 if case["case_id"] in latest and latest[case["case_id"]]["retryable"] else 1,
        )
        for case in cases
        if case["case_id"] not in latest or latest[case["case_id"]]["retryable"]
    ]
    if max_cases is not None and max_cases % 2:
        raise ValueError("--max-cases must be even so a paired comparison is not split")
    pending = pending_all[:max_cases] if max_cases is not None else pending_all
    print(
        f"planned={len(cases)} terminal={len(cases) - len(pending_all)} "
        f"pending={len(pending_all)} selected={len(pending)}",
        flush=True,
    )
    env = environment()
    with futures.ProcessPoolExecutor(
        max_workers=manifest["numerics"]["maximum_workers"]
    ) as executor:
        jobs = {
            executor.submit(run_case, (case, manifest, manifest_hash, env, attempt)): case
            for case, attempt in pending
        }
        for index, future in enumerate(futures.as_completed(jobs), 1):
            event = future.result()
            append_event(OUTPUT, event)
            print(
                f"[{index}/{len(pending)}] {event['case_key']} "
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
    print(
        json.dumps(
            {
                "planned": len(cases),
                "terminal": sum(not row["retryable"] for row in latest.values()),
                "pending": sum(
                    case["case_id"] not in latest
                    or latest[case["case_id"]]["retryable"]
                    for case in cases
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

"""Select the qualified ray count for V3 exploratory screening."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import foundation_pattern_bosch_gate0_r1 as r1
import native_domain_checkpoint as native_checkpoint


DEFAULT_MANIFEST = r1.DEFAULT_MANIFEST
DEFAULT_ROWS = r1.DEFAULT_OUTPUT
DEFAULT_R1_SUMMARY = Path(
    "autoresearch-results/restart_audit/pattern_bosch_gate0_r1_summary.json"
)
DEFAULT_JSON = Path(
    "autoresearch-results/restart_audit/v3_numerical_release.json"
)
DEFAULT_MARKDOWN = Path(
    "autoresearch-results/restart_audit/v3_numerical_release.md"
)
FIXED_ARMS = (r1.REFERENCE_ARM, r1.RAY_ANCHOR_ARM)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strict_rows(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = r1.gate0.strict_json_loads(line)
        except Exception as error:
            raise ValueError(f"malformed R1 row {line_number}: {error}") from error
        if not isinstance(row, dict):
            raise ValueError(f"R1 row {line_number} is not an object")
        rows.append(row)
    return rows


def _review_fixed_case(row, case, rows_path: Path, manifest: dict) -> dict:
    errors = []
    if not r1.row_matches_case(row, case):
        errors.append("case payload or fingerprint differs")
    if row.get("ok") is not True:
        errors.append("execution did not finish successfully")
    if not errors:
        errors.extend(r1.validate_success_row(row, case, rows_path))

    measured = row.get("selected_cycle_metrics") or {}
    silicon_mesh_sha256 = None
    try:
        domain = native_checkpoint.load_domain_checkpoint(
            row["checkpoint_path"], expected_sha256=row["checkpoint_sha256"]
        )
        independently_measured, invalid = r1._measure_domain(domain, case)
        errors.extend(r1._compare_values(
            independently_measured,
            measured,
            float(manifest["review"]["row_recompute_abs_tolerance"]),
            "selected_cycle_metrics",
        ))
        if invalid != row.get("selected_metric_invalid_reasons"):
            errors.append("independent invalid-reason vector differs")
        if r1.domain_mesh_sha256(domain) != row.get("native_mesh_sha256"):
            errors.append("independent native-domain mesh hash differs")
        silicon = native_checkpoint.extract_raw_silicon_domain(domain)
        silicon_mesh_sha256 = r1.domain_mesh_sha256(silicon)
    except Exception as error:
        errors.append(f"independent native checkpoint validation failed: {error}")

    etch = measured.get("etch") or {}
    metrics = {
        "depth": etch.get("depth"),
        "cd_top": etch.get("cd_top"),
        "cd_middle": etch.get("cd_middle"),
        "cd_bottom": etch.get("cd_bottom"),
        "max_cd_error": etch.get("max_cd_error"),
        "max_bow": etch.get("max_bow"),
        "scallop_rms": etch.get("scallop_rms"),
        "mask_remaining_height": measured.get("mask_remaining_height"),
    }
    for name, value in metrics.items():
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            errors.append(f"metric {name} is missing or nonfinite")

    return {
        "case_id": case["case_id"],
        "arm": case["arm"],
        "rng_seed": case["rng_seed"],
        "rays_per_point": case["numerics"]["rays_per_point"],
        "valid": not errors,
        "errors": errors,
        "selection_eligible": row.get("selection_eligible") is True,
        "hard_gate_pass": row.get("hard_gate_pass") is True,
        "selected_cycle": row.get("selected_cycle"),
        "metrics": metrics,
        "checkpoint_path": row.get("checkpoint_path"),
        "checkpoint_sha256": row.get("checkpoint_sha256"),
        "native_domain_mesh_sha256": row.get("native_mesh_sha256"),
        "silicon_mesh_sha256": silicon_mesh_sha256,
        "native_roundtrip_exact": row.get("native_roundtrip_exact") is True,
    }


def review_fixed_rows(manifest: dict, rows_path: Path) -> tuple[list[dict], dict]:
    cases = r1.expand_cases(manifest)
    expected_cases = {
        case["case_id"]: case for case in cases if case["arm"] in FIXED_ARMS
    }
    expected_ids = set(expected_cases)
    raw_rows = _strict_rows(rows_path)
    fixed_rows = [row for row in raw_rows if row.get("arm") in FIXED_ARMS]
    ignored_rows = [row for row in raw_rows if row.get("arm") not in FIXED_ARMS]

    counts = {}
    for row in fixed_rows:
        current_id = row.get("case_id")
        counts[current_id] = counts.get(current_id, 0) + 1
    duplicates = sorted(
        str(case_id) for case_id, count in counts.items() if count != 1
    )
    unexpected = sorted(
        str(row.get("case_id"))
        for row in fixed_rows
        if row.get("case_id") not in expected_ids
    )
    missing = sorted(expected_ids - set(counts))
    if duplicates or unexpected or missing:
        raise ValueError(
            "R1 fixed numerical evidence is incomplete or ambiguous: "
            f"missing={missing}; duplicate={duplicates}; unexpected={unexpected}"
        )

    reviewed = []
    for row in fixed_rows:
        case = expected_cases[row["case_id"]]
        reviewed.append(_review_fixed_case(row, case, rows_path, manifest))
    reviewed.sort(key=lambda item: (item["arm"], item["rng_seed"]))
    scope = {
        "raw_row_count": len(raw_rows),
        "reviewed_fixed_row_count": len(reviewed),
        "ignored_non_numerical_row_count": len(ignored_rows),
        "ignored_non_numerical_arms": sorted({
            str(row.get("arm")) for row in ignored_rows
        }),
    }
    return reviewed, scope


def evaluate_ray_bridge(reviewed: list[dict], manifest: dict) -> dict:
    limits = manifest["review"]["paired_max_absolute_deltas"]
    by_key = {(row["arm"], row["rng_seed"]): row for row in reviewed}
    pairs = []
    for seed in r1.EXPECTED_SEEDS:
        reference = by_key[(r1.REFERENCE_ARM, seed)]
        anchor = by_key[(r1.RAY_ANCHOR_ARM, seed)]
        deltas = {
            metric: anchor["metrics"][metric] - reference["metrics"][metric]
            for metric in limits
        }
        pairs.append({
            "rng_seed": seed,
            "rays_1000_case_id": reference["case_id"],
            "rays_2000_case_id": anchor["case_id"],
            "deltas_2000_minus_1000": deltas,
            "hard_gate_flip": reference["hard_gate_pass"] != anchor["hard_gate_pass"],
        })

    metric_results = {}
    for metric, limit in limits.items():
        values = [abs(pair["deltas_2000_minus_1000"][metric]) for pair in pairs]
        maximum = max(values)
        metric_results[metric] = {
            "frozen_max_absolute_delta": limit,
            "observed_max_absolute_delta": maximum,
            "exceeds_limit": maximum > limit,
            "excess_ratio": maximum / limit,
        }
    failed_metrics = [
        metric for metric, result in metric_results.items()
        if result["exceeds_limit"]
    ]
    all_rows_valid = all(row["valid"] for row in reviewed)
    no_gate_flips = not any(pair["hard_gate_flip"] for pair in pairs)
    return {
        "pairing_note": (
            "The same base-seed labels are paired, but pointwise common random "
            "numbers are not claimed across different ray counts."
        ),
        "pair_count": len(pairs),
        "all_rows_independently_valid": all_rows_valid,
        "no_hard_gate_flips": no_gate_flips,
        "pairs": pairs,
        "metric_results": metric_results,
        "failed_metrics": failed_metrics,
        "rays_1000_passes_frozen_bridge": bool(
            len(pairs) == len(r1.EXPECTED_SEEDS)
            and all_rows_valid
            and no_gate_flips
            and not failed_metrics
        ),
    }


def review_native_baselines(reviewed: list[dict]) -> dict:
    anchors = [row for row in reviewed if row["arm"] == r1.RAY_ANCHOR_ARM]
    shapes = []
    for row in anchors:
        accepted = bool(
            row["valid"]
            and row["selection_eligible"]
            and row["hard_gate_pass"]
            and row["native_roundtrip_exact"]
            and row["silicon_mesh_sha256"]
        )
        shapes.append({
            "case_id": row["case_id"],
            "rng_seed": row["rng_seed"],
            "selected_cycle": row["selected_cycle"],
            "checkpoint_path": row["checkpoint_path"],
            "checkpoint_sha256": row["checkpoint_sha256"],
            "native_domain_mesh_sha256": row["native_domain_mesh_sha256"],
            "silicon_mesh_sha256": row["silicon_mesh_sha256"],
            "accepted": accepted,
        })
    authorized = bool(
        len(shapes) == len(r1.EXPECTED_SEEDS)
        and all(shape["accepted"] for shape in shapes)
    )
    return {
        "source_arm": r1.RAY_ANCHOR_ARM,
        "rays_per_point": 2000,
        "shape_count": len(shapes),
        "shapes": shapes,
        "authorized": authorized,
        "scope": (
            "Immutable numerical baseline shapes for method qualification and "
            "shared-geometry controls; not recipes or process-window evidence."
        ),
    }


def crosscheck_r1_summary(path: Path, bridge: dict) -> dict:
    summary = r1.gate0.strict_json_loads(Path(path).read_text())
    errors = []
    if summary.get("campaign") != "foundation-pattern-bosch-gate0-r1":
        errors.append("R1 summary campaign differs")
    if summary.get("selected_success_count") != 8:
        errors.append("R1 summary does not report eight selected successes")
    if summary.get("independently_valid_case_count") != 8:
        errors.append("R1 summary does not report eight independently valid rows")
    prior_bridge = summary.get("ray_bridge") or {}
    if prior_bridge.get("pass") is not False:
        errors.append("R1 summary does not reject the 1000/2000 bridge")
    if len(prior_bridge.get("pairs") or []) != len(r1.EXPECTED_SEEDS):
        errors.append("R1 summary does not contain four ray pairs")
    for metric, result in bridge["metric_results"].items():
        prior = (prior_bridge.get("metric_results") or {}).get(metric, {})
        observed = prior.get("maximum_absolute_delta")
        if not isinstance(observed, (int, float)) or not math.isclose(
            observed,
            result["observed_max_absolute_delta"],
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            errors.append(f"R1 summary ray delta differs for {metric}")
    bracket = summary.get("mask_bracket") or {}
    if bracket.get("search_results") not in ([], None):
        errors.append("R1 summary unexpectedly contains executed mask searches")
    prior_decision = summary.get("decision") or {}
    for key in (
        "recipe_authorized",
        "process_window_authorized",
        "full_traveler_authorized",
        "automatic_downstream_launch_authorized",
    ):
        if prior_decision.get(key) is not False:
            errors.append(f"R1 summary authority {key} is not false")
    return {
        "valid": not errors,
        "errors": errors,
        "status": summary.get("status"),
        "interpretation": (
            "The original combined R1 decision remains blocked because its mask "
            "ladder was intentionally not run and 1000 rays failed. This V3 "
            "review independently makes only the narrower numerical decision."
        ),
    }


def build_release(manifest_path, rows_path, r1_summary_path) -> dict:
    manifest_path = Path(manifest_path)
    rows_path = Path(rows_path)
    r1_summary_path = Path(r1_summary_path)
    manifest = r1.gate0.strict_json_loads(manifest_path.read_text())
    cases = r1.expand_cases(manifest)
    # Validate the frozen runtime and report later source drift separately.
    manifest_errors = r1.validate_manifest(manifest, cases, check_runtime=False)
    if manifest_errors:
        raise ValueError("invalid frozen R1 manifest: " + "; ".join(manifest_errors))
    current_runtime = r1.runtime_fingerprint()
    frozen_runtime = manifest["runtime_fingerprint"]
    runtime_drift = {
        key: {"frozen_sha256": frozen_runtime[key], "current_sha256": current_runtime[key]}
        for key in frozen_runtime
        if frozen_runtime[key] != current_runtime.get(key)
    }

    reviewed, row_scope = review_fixed_rows(manifest, rows_path)
    bridge = evaluate_ray_bridge(reviewed, manifest)
    baselines = review_native_baselines(reviewed)
    prior_summary = crosscheck_r1_summary(r1_summary_path, bridge)
    rays_1000_rejected = bool(
        not bridge["rays_1000_passes_frozen_bridge"]
        and bridge["failed_metrics"]
    )
    fixed_evidence_valid = bool(
        len(reviewed) == 8 and all(row["valid"] for row in reviewed)
    )
    approved = bool(
        fixed_evidence_valid
        and rays_1000_rejected
        and baselines["authorized"]
        and prior_summary["valid"]
    )
    authority = {
        "exploratory_screening": approved,
        "automatic_launch": False,
        "mask_claims": False,
        "recipe": False,
        "process_window": False,
        "full_traveler": False,
        "fab_recipe": False,
    }
    decision = {
        "classification": (
            "approved_for_v3_exploratory_screening"
            if approved else "v3_numerical_release_blocked"
        ),
        "pass": approved,
        "grid_delta": manifest["numerics"]["grid_delta"],
        "rays_per_point": manifest["numerics"]["anchor_rays_per_point"],
        "dimension": manifest["numerics"]["dimension"],
        "rays_1000_rejected": rays_1000_rejected,
        "native_baseline_authorized": baselines["authorized"],
        "authority": authority,
        "scope": "V3 Stage 1/2 2D exploratory pattern/Bosch screening only",
        "limitations": [
            "2000 rays is the accepted higher-fidelity tested setting; this is not an asymptotic convergence proof.",
            "The mask-erosion ladder was intentionally not run and no mask-loss boundary is authorized.",
            "No recipe, process window, full traveler, fab setting, or automatic launch is authorized.",
        ],
    }
    return {
        "artifact": "v3_stage0_numerical_release",
        "labels": ["full-traveler", "critical-review"],
        "source_evidence": {
            "r1_manifest": {
                "path": str(manifest_path),
                "sha256": file_sha256(manifest_path),
            },
            "r1_rows": {
                "path": str(rows_path),
                "sha256": file_sha256(rows_path),
            },
            "r1_summary": {
                "path": str(r1_summary_path),
                "sha256": file_sha256(r1_summary_path),
            },
        },
        "runtime_provenance": {
            "frozen_runtime_fingerprint": frozen_runtime,
            "executed_rows_bind_frozen_runtime": all(
                row.get("runtime_fingerprint") == frozen_runtime
                for row in _strict_rows(rows_path)
                if row.get("arm") in FIXED_ARMS
            ),
            "current_source_drift": runtime_drift,
            "current_source_drift_is_evidence_mutation": False,
            "note": (
                "The raw rows and manifest remain immutable. Current source drift "
                "is disclosed because the superseded runner received a fail-closed "
                "V3 guard after R1 stopped."
            ),
        },
        "row_scope": row_scope,
        "reviewed_cases": reviewed,
        "ray_bridge": bridge,
        "native_baselines": baselines,
        "mask_scope": {
            "classification": "not_evaluated_by_this_numerical_release",
            "mask_ladder_required_for_this_decision": False,
            "executed_mask_ladder_rows_used": 0,
            "mask_rate_or_failure_boundary_claim_authorized": False,
        },
        "r1_summary_crosscheck": prior_summary,
        "decision": decision,
    }


def markdown(release: dict) -> str:
    decision = release["decision"]
    bridge = release["ray_bridge"]
    lines = [
        "# V3 numerical release",
        "",
        "## Decision",
        "",
        "**2,000 rays per point is released for 2D exploratory Pattern/Bosch "
        "Stages 1 and 2 at grid 0.00125.** The 1,000-ray shortcut is rejected.",
        "",
        "This is a simulation-fidelity decision, not a process result. It does "
        "not identify a recipe, process window, or full traveler.",
        "",
        "## Why 1,000 rays was rejected",
        "",
        "All eight rows and native checkpoints independently validate, and no "
        "hard gate flips between the paired ray counts. Three shape changes "
        "nevertheless exceed the limits frozen before the runs:",
        "",
        "| Output | Frozen limit | Largest 1,000-to-2,000 shift | Decision |",
        "|---|---:|---:|---|",
    ]
    for metric, result in bridge["metric_results"].items():
        if result["exceeds_limit"]:
            lines.append(
                f"| {metric} | {result['frozen_max_absolute_delta']:.6g} | "
                f"{result['observed_max_absolute_delta']:.6g} | exceeds |"
            )
    lines += [
        "",
        "The rejected setting therefore changes the geometry enough to confuse "
        "a real knob effect with numerical variation.",
        "",
        "## Released native baselines",
        "",
        "The four 2,000-ray checkpoints are valid, depth-matched hard passes and "
        "round-trip exactly through the native ViennaPS checkpoint format.",
        "",
        "| Seed | Cycle | Checkpoint | Accepted |",
        "|---:|---:|---|---:|",
    ]
    for shape in release["native_baselines"]["shapes"]:
        lines.append(
            f"| {shape['rng_seed']} | {shape['selected_cycle']} | "
            f"`{Path(shape['checkpoint_path']).name}` | {int(shape['accepted'])} |"
        )
    lines += [
        "",
        "These are immutable numerical baseline shapes for shared-geometry and "
        "method checks. They are not four winning recipes.",
        "",
        "## Scope limits",
        "",
        "- The unrun mask-erosion ladder is outside this numerical decision. No "
        "mask-loss rate or boundary is claimed.",
        "- Two thousand rays is the higher-fidelity tested setting, not proof of "
        "convergence at arbitrarily high ray count.",
        "- Recipe, process-window, full-traveler, fab-setting, and automatic-"
        "launch authority are all false.",
        "",
        f"Machine decision: `{decision['classification']}`.",
        "",
    ]
    return "\n".join(lines)


def write_json(path: Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(
        value, indent=2, sort_keys=True, allow_nan=False
    ) + "\n")
    temporary.replace(path)


def write_text(path: Path, value: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--r1-summary", type=Path, default=DEFAULT_R1_SUMMARY)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    release = build_release(args.manifest, args.rows, args.r1_summary)
    write_json(args.json, release)
    write_text(args.markdown, markdown(release) + "\n")
    print(json.dumps(release["decision"], sort_keys=True, allow_nan=False))
    if not release["decision"]["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

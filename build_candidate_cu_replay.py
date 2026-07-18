"""Export one reviewed candidate copper-fill trajectory for teaching."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

import numpy as np
import viennaps as ps

import foundation_copper_fill_trajectory as candidate
import traveler_metrics as tm
import tsv_process as tp


ROOT = Path(__file__).resolve().parent
ROWS = ROOT / "autoresearch-results/restart_audit/copper_fill_trajectory_rows.jsonl"
REVIEW = ROOT / "autoresearch-results/restart_audit/copper_fill_trajectory_summary.json"
OUTPUT = ROOT / "candidate_cu_replay.json"
PUBLIC_SOURCE = ROOT / "evidence/copper/candidate_cu_replay_source.json"
CASE_ID = "baa7937cf12fbec9"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _surface_path(nodes, lines) -> str:
    segments = np.asarray(nodes)[np.asarray(lines, dtype=int)][:, :, :2]
    return "".join(
        f"M{start[0]:.5f} {start[1]:.5f}L{end[0]:.5f} {end[1]:.5f}"
        for start, end in segments
    )


def _snapshot_surface(path: Path) -> str:
    with np.load(path) as snapshot:
        return _surface_path(snapshot["nodes"], snapshot["lines"])


def _repo_path(path: str | Path) -> Path:
    candidate_path = Path(path)
    return candidate_path if candidate_path.is_absolute() else ROOT / candidate_path


def _source_row() -> tuple[dict, int]:
    for line_number, line in enumerate(ROWS.read_text().splitlines(), 1):
        row = json.loads(line)
        if row["case_id"] == CASE_ID:
            return row, line_number
    raise ValueError(f"missing reviewed copper case {CASE_ID}")


def _replay_case(reviewed: dict) -> dict:
    input_keys = (
        "manifest_version",
        "design",
        "geometry",
        "layers",
        "model",
        "numerics",
        "target",
        "provenance",
        "runtime_fingerprint",
        "rng_seed",
        "case_id",
    )
    case = {key: reviewed[key] for key in input_keys}
    case["numerics"] = {**case["numerics"], "save_every": 1}
    return case


def _material_id(material) -> str:
    if material == ps.Material.Si:
        return "silicon"
    if material == ps.Material.SiO2:
        return "liner"
    if material == ps.Material.TaN:
        return "barrier"
    if material == tp.CU_SEED_MATERIAL:
        return "seed"
    if material == ps.Material.Cu:
        return "copper"
    raise ValueError(f"unexpected material {material}")


def _starting_materials(case: dict) -> list[dict]:
    geometry = candidate._build_seeded_stack(case)
    return [
        {
            "id": _material_id(mesh["material"]),
            "surface_path": _surface_path(mesh["nodes"], mesh["lines"]),
        }
        for mesh in tm.raw_level_set_meshes(geometry)
    ]


def _public_metrics(checkpoint: dict) -> dict:
    topology = checkpoint["topology"]
    diagnostics = checkpoint["model_diagnostics"]
    return {
        "fill_fraction": topology["fill_fraction"],
        "remaining_void_area": topology["remaining_void_area"],
        "open_void_depth": topology["open_void_depth"],
        "mouth_aperture": topology["mouth_aperture"],
        "mouth_sample_y": topology["mouth_sample_y"],
        "overburden_min": topology["overburden_min"],
        "center_velocity_mean": diagnostics["center_velocity_mean"],
        "field_velocity_mean": diagnostics["field_velocity_mean"],
        "topology_transition": checkpoint["topology_transition"]["classification"],
        "unresolved_seam_risk": checkpoint["topology_transition"]["unresolved_seam_risk"],
        "transition_reason": checkpoint["topology_transition"]["reason"],
        "previous_open_void_depth": checkpoint["topology_transition"][
            "previous_open_void_depth"
        ],
        "observed_open_void_depth_drop": checkpoint["topology_transition"][
            "observed_open_void_depth_drop"
        ],
        "disappearing_tail_max_width": checkpoint["topology_transition"][
            "disappearing_tail_max_width"
        ],
        "closure_width_bound": checkpoint["topology_transition"][
            "closure_width_bound"
        ],
    }


def _verify(replayed: dict, reviewed: dict) -> None:
    if not replayed.get("ok"):
        raise RuntimeError(replayed.get("error", "candidate replay failed"))
    if len(replayed["trajectory"]) != len(reviewed["trajectory"]):
        raise ValueError("candidate replay checkpoint count changed")
    for actual, expected in zip(replayed["trajectory"], reviewed["trajectory"], strict=True):
        if actual["checkpoint"] != expected["checkpoint"]:
            raise ValueError("candidate replay checkpoint identity changed")
        if not np.isclose(actual["elapsed"], expected["elapsed"], atol=1e-12, rtol=0):
            raise ValueError("candidate replay changed elapsed model time")
        actual_metrics = _public_metrics(actual)
        expected_metrics = _public_metrics(expected)
        for key, expected_value in expected_metrics.items():
            actual_value = actual_metrics[key]
            if isinstance(expected_value, (int, float)) and not isinstance(
                expected_value, bool
            ):
                matches = np.isclose(
                    actual_value, expected_value, atol=1e-12, rtol=0
                )
            else:
                matches = actual_value == expected_value
            if not matches:
                raise ValueError(f"candidate replay changed {key}")
        saved_path = expected.get("snapshot_path")
        if saved_path and _snapshot_surface(_repo_path(saved_path)) != _snapshot_surface(
            Path(actual["snapshot_path"])
        ):
            raise ValueError("candidate replay differs from a saved source surface")


def main() -> None:
    reviewed, line_number = _source_row()
    case = _replay_case(reviewed)
    with tempfile.TemporaryDirectory(prefix="candidate-cu-replay-") as directory:
        temporary = Path(directory)
        snapshots = temporary / "snapshots"
        replayed = candidate.run_case((case, snapshots, temporary / "progress"))
        _verify(replayed, reviewed)
        frames = []
        for checkpoint in replayed["trajectory"]:
            frames.append(
                {
                    "checkpoint": checkpoint["checkpoint"],
                    "elapsed": checkpoint["elapsed"],
                    "surface_path": _snapshot_surface(Path(checkpoint["snapshot_path"])),
                    "metrics": _public_metrics(checkpoint),
                }
            )

    PUBLIC_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    review_document = json.loads(REVIEW.read_text())
    source = {
        "schema_version": 1,
        "case_id": CASE_ID,
        "source_row": reviewed,
        "review": review_document["best_valid_miss"],
        "review_decision": review_document["decision"],
        "source": {
            "rows_path": str(ROWS.relative_to(ROOT)),
            "rows_line_number": line_number,
            "rows_sha256": _sha256(ROWS),
            "review_path": str(REVIEW.relative_to(ROOT)),
            "review_sha256": _sha256(REVIEW),
        },
    }
    PUBLIC_SOURCE.write_text(
        json.dumps(source, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    document = {
        "schema_version": 1,
        "scope": "Reviewed coarse candidate-model trajectory; not a recipe or accepted fill model.",
        "case_id": CASE_ID,
        "model": reviewed["provenance"]["candidate_model"],
        "model_controls": reviewed["model"],
        "numerics": reviewed["numerics"],
        "target": reviewed["target"],
        "target_basis": {
            key: {
                "classification": (
                    "implementation_assumption"
                    if key == "max_balance_error"
                    else "assumed_study_target"
                ),
                "physical_qualification": False,
                "source": {
                    "path": (
                        "foundation_copper_fill_structural_challenge.py"
                        if key == "max_balance_error"
                        else "program.md"
                    ),
                    "sha256": _sha256(
                        ROOT
                        / (
                            "foundation_copper_fill_structural_challenge.py"
                            if key == "max_balance_error"
                            else "program.md"
                        )
                    ),
                    "section": (
                        "candidate_case"
                        if key == "max_balance_error"
                        else "Step target specs"
                    ),
                },
            }
            for key in reviewed["target"]
        },
        "view_box": [
            -reviewed["geometry"]["x_extent"] / 2,
            -0.25,
            reviewed["geometry"]["x_extent"],
            reviewed["geometry"]["y_extent"] + 0.25,
        ],
        "starting_materials": _starting_materials(case),
        "frames": frames,
        "decision": (
            "The final transition cannot be classified reliably at this resolution. "
            "Later morphology is not interpreted."
        ),
        "citations": [
            {
                "path": str(PUBLIC_SOURCE.relative_to(ROOT)),
                "sha256": _sha256(PUBLIC_SOURCE),
                "selector": selector,
            }
            for selector in ("/source_row", "/review_decision")
        ],
    }
    OUTPUT.write_text(
        json.dumps(document, separators=(",", ":"), allow_nan=False) + "\n"
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()

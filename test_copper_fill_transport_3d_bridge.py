"""Focused guards for the dormant matched 24-case 3D transport bridge."""

from __future__ import annotations

import copy
import json
import math
import tempfile
from pathlib import Path

import numpy as np
import viennaps as ps

import copper_fill_transport_3d as metrics3d
import foundation_copper_fill_transport_3d_bridge as campaign
import review_copper_fill_transport_3d_bridge as review


ROOT = Path(__file__).resolve().parent


def manifest():
    return json.loads((ROOT / campaign.DEFAULT_MANIFEST).read_text())


def test_frozen_matrix_parent_bijection_and_commissioning_subset():
    data = manifest()
    fingerprint = {"test": "fingerprint"}
    cases = campaign.expand_cases(data, fingerprint)
    assert campaign.validate_manifest(data, cases, check_runtime=False) == []
    assert len(cases) == 24
    counts = {}
    for case in cases:
        key = (case["design"], case["numerics"]["max_reflections"])
        counts[key] = counts.get(key, 0) + 1
        assert case["numerics"]["grid_delta"] == 0.005
        assert case["numerics"]["rays_per_point"] == 2000
        assert case["numerics"]["max_boundary_hits"] == 6400
        assert case["matched_2d_parent_case_id"]
        assert math.isclose(
            case["model"]["adsorption_strength"]
            * case["model"]["suppressor_sticking_probability"],
            0.25,
            abs_tol=1e-15,
        )
    assert counts == {
        (campaign.CONTROL_NAME, 800): 8,
        (campaign.CANDIDATE_NAME, 1600): 8,
        (campaign.CANDIDATE_NAME, 3200): 8,
    }
    parent_ids = {
        item["parent_case_id"]
        for item in data["matched_2d_comparison"]["rows"]
    }
    assert len(parent_ids) == 24
    assert {case["matched_2d_parent_case_id"] for case in cases} == parent_ids
    commissioning = campaign._commissioning_cases(cases, data)
    assert len(commissioning) == 2
    assert all(case in cases for case in commissioning)


def test_manifest_mutations_fail_closed_and_runtime_is_exact():
    data = manifest()
    assert campaign.validate_runtime(data) == []
    mutations = []
    changed = copy.deepcopy(data)
    changed["geometry"]["hole_shape"] = "QUARTER"
    mutations.append(changed)
    changed = copy.deepcopy(data)
    changed["geometry"]["lateral_boundary"] = "PERIODIC"
    mutations.append(changed)
    changed = copy.deepcopy(data)
    changed["numerics"]["max_boundary_hits"] = 1000
    mutations.append(changed)
    changed = copy.deepcopy(data)
    changed["analysis"]["minimum_sector_point_count"] = 1
    mutations.append(changed)
    changed = copy.deepcopy(data)
    changed["decision_policy"]["morphology_authorized"] = True
    mutations.append(changed)
    changed = copy.deepcopy(data)
    changed["decision_policy"]["automatic_additional_launch_authorized"] = True
    mutations.append(changed)
    changed = copy.deepcopy(data)
    changed["reflection_convergence"]["maximum_paired_absolute_delta"][
        "worst_floor_to_each_lower_flux_ratio"
    ] *= 2.0
    mutations.append(changed)
    changed = copy.deepcopy(data)
    changed["reflection_convergence"][
        "parent_B_pure_reflection_worst_absolute_effect"
    ]["realized_min_floor_to_fastest_wall_velocity_ratio"] *= 2.0
    mutations.append(changed)
    changed = copy.deepcopy(data)
    changed["provenance"]["viennaps_binary_sha256"] = "0" * 64
    mutations.append(changed)
    changed = copy.deepcopy(data)
    changed["matched_2d_comparison"]["rows"] = changed[
        "matched_2d_comparison"
    ]["rows"][:-1]
    mutations.append(changed)
    assert all(
        campaign.validate_manifest(item, check_runtime=False)
        for item in mutations
    )


def _tiny_case():
    return {
        "geometry": {
            "radius": 0.10,
            "mask_height": 0.10,
            "x_extent": 0.50,
            "lateral_y_extent": 0.50,
            "depth": 0.40,
            "mouth_offset": 0.02,
            "field_radius_band": [0.15, 0.20],
        },
        "layers": {"liner": 0.03, "barrier": 0.01, "seed": 0.01},
        "numerics": {"grid_delta": 0.01},
    }


def test_explicit_d3_full_cylinder_stack_reference_and_triangles():
    geometry = metrics3d.build_seeded_stack(_tiny_case())
    assert isinstance(geometry, ps.d3.Domain)
    assert metrics3d.material_stack_names(geometry) == (
        "Si", "SiO2", "TaN", "CuSeed", "Cu"
    )
    assert metrics3d.boundary_contract(geometry)["pass"]
    reference, meshes = metrics3d.reference_from_geometry(geometry, _tiny_case())
    assert reference["coordinate_convention"]["height_axis"].startswith("z=")
    assert reference["seed_surface_connected"]
    assert reference["cavity_open_at_mouth"]
    assert reference["height_H"] > 0.0
    assert reference["kinematic_threshold_H_over_a_mouth"] > 1.0
    assert len(reference["mouth_radius_by_sector"]) == 8
    assert all(mesh["triangles"].shape[1] == 3 for mesh in meshes)
    assert all(mesh["nodes"].shape[1] == 3 for mesh in meshes)


def _tiny_process_case():
    return {
        "case_id": "tiny-api-fixture",
        "simulation_dimension": 3,
        "rng_seed": 19,
        **_tiny_case(),
        "model": {
            "suppressor_sticking_probability": 0.2,
            "suppressor_source_power": 0.0,
            "gas_mean_free_path": -1.0,
            "adsorption_strength": 1.25,
            "deactivation_rate": 0.25,
            "active_deposition_rate": 0.2,
            "suppressed_deposition_rate": 0.01,
        },
        "numerics": {
            "grid_delta": 0.01,
            "rays_per_point": 2,
            "max_reflections": 5,
            "max_boundary_hits": 20,
            "smoothing_neighbors": 1,
            "min_node_distance_factor": 0.05,
            "disk_radius": 0.0,
            "time_step_ratio": 0.4999,
            "checkpoint_interval": 0.001,
            "threads_per_worker": 1,
            "ignore_voids": True,
        },
        "target": {
            "max_balance_error": 1e-10,
            "analytic_parity_abs_tolerance": 1e-12,
        },
        "analysis": {
            "sector_offsets_degrees": [0.0, 22.5],
            "minimum_sector_point_count": 1,
        },
    }


def test_tiny_d3_process_populates_diagnostics_and_preserves_stack():
    case = _tiny_process_case()
    with tempfile.TemporaryDirectory() as temporary:
        row = campaign.run_case((case, Path(temporary)))
        assert row["ok"], row.get("error")
        assert row["model_diagnostics"]["point_count"] > 0
        assert row["protected_stack"]["survives"]
        assert row["surface_structure"]["cavity_open"]
        assert not row["surface_structure"]["unexpected_sealed_component"]
        reviewed, errors = review.review_case(row, ROOT)
        assert errors == []
        assert reviewed is not None
        assert math.isclose(
            reviewed["reference"]["kinematic_threshold_H_over_a_mouth"],
            row["reference"]["kinematic_threshold_H_over_a_mouth"],
            abs_tol=1e-12,
        )
        with np.load(row["diagnostic_snapshot_path"], allow_pickle=False) as saved:
            assert int(saved["simulation_dimension"][0]) == 3
            assert saved["pre_material_names"].tolist() == [
                "Si", "SiO2", "TaN", "CuSeed", "Cu"
            ]
            assert saved["post_material_names"].tolist() == [
                "Si", "SiO2", "TaN", "CuSeed", "Cu"
            ]
            assert all(
                f"pre_level_set_{index}_triangles" in saved.files
                and f"post_level_set_{index}_triangles" in saved.files
                for index in range(5)
            )
        json.loads(json.dumps(review._strict_jsonable(reviewed), allow_nan=False))


def _synthetic_sector_field():
    angles = np.linspace(0.0, 2.0 * math.pi, 480, endpoint=False) + 0.001
    coordinates = []
    flux = []
    coverage = []
    velocity = []
    region_values = (
        ("floor", -0.99, 0.05, 0.80, 0.20, 20.0),
        ("lower", -0.70, 0.10, 1.00, 0.40, 1.0),
        ("middle", -0.45, 0.10, 1.00, 0.40, 1.0),
        ("upper", -0.20, 0.10, 1.00, 0.40, 1.0),
    )
    for _, z, radius, local_flux, local_coverage, local_velocity in region_values:
        for angle in angles:
            coordinates.append([
                radius * math.cos(angle),
                radius * math.sin(angle),
                z,
            ])
            flux.append(local_flux)
            coverage.append(local_coverage)
            velocity.append(local_velocity)
    coordinates = np.asarray(coordinates, dtype=float)
    material_ids = np.full(
        len(coordinates), float(ps.Material.Cu.legacyId()), dtype=float
    )
    reference = {
        "floor_z": -1.0,
        "field_z": 0.0,
        "height_H": 1.0,
        "mouth_radius_minimum": 0.10,
        "mouth_radius_maximum": 0.12,
        "minimum_wall_radius": 0.10,
        "kinematic_threshold_H_over_a_mouth": 10.0,
        "field_radius_band": [0.35, 0.45],
    }
    return (
        coordinates,
        material_ids,
        np.asarray(flux),
        np.asarray(coverage),
        np.asarray(velocity),
        reference,
    )


def _valid_guards():
    return {
        "diagnostic_balance_valid": True,
        "analytic_parity_valid": True,
        "full_cylinder_and_stack_valid": True,
        "protected_stack_survives": True,
        "cavity_remains_open_without_sealed_component": True,
    }


def test_sector_metrics_cover_both_offsets_and_do_not_average_away_failure():
    coordinates, material_ids, flux, coverage, velocity, reference = (
        _synthetic_sector_field()
    )
    decisions = []
    for offset in metrics3d.SECTOR_OFFSETS_DEG:
        regions, masks = metrics3d.region_statistics(
            coordinates,
            material_ids,
            flux,
            coverage,
            velocity,
            [float(ps.Material.Cu.legacyId())],
            reference,
            offset,
        )
        assert all(
            regions[f"{name}_sector_{sector}"]["point_count"] >= 50
            for name in metrics3d.SECTOR_REGION_NAMES
            for sector in range(8)
        )
        assert all(not np.any(mask & (material_ids != ps.Material.Cu.legacyId())) for mask in masks.values())
        decisions.append(metrics3d.transport_decision(
            regions, reference, 50, _valid_guards()
        ))
    assert all(decision["pass"] for decision in decisions)
    assert all(
        decision["realized_min_floor_to_fastest_wall_velocity_ratio"] == 20.0
        for decision in decisions
    )

    # Make one angular lower-wall sector receive less suppressor than its floor.
    changed_flux = flux.copy()
    lower_start = 480
    changed_flux[lower_start: lower_start + 60] = 0.60
    regions, _ = metrics3d.region_statistics(
        coordinates,
        material_ids,
        changed_flux,
        coverage,
        velocity,
        [float(ps.Material.Cu.legacyId())],
        reference,
        0.0,
    )
    failed = metrics3d.transport_decision(regions, reference, 50, _valid_guards())
    assert not failed["pass"]
    assert not failed["conditions"][
        "floor_to_each_lower_flux_ratio_strictly_below_0p95"
    ]


def test_half_open_sector_boundaries_follow_atan2_xy_not_height():
    cardinal = metrics3d._sector_indices(
        np.asarray([1.0, 0.0, -1.0, 0.0]),
        np.asarray([0.0, 1.0, 0.0, -1.0]),
        0.0,
    )
    assert cardinal.tolist() == [0, 2, 4, 6]
    width = 2.0 * math.pi / 8
    angles = np.asarray([index * width + 1e-9 for index in range(8)])
    sectors = metrics3d._sector_indices(
        np.cos(angles), np.sin(angles), 0.0
    )
    assert sectors.tolist() == list(range(8))
    shifted = angles + math.radians(22.5)
    shifted_sectors = metrics3d._sector_indices(
        np.cos(shifted), np.sin(shifted), 22.5
    )
    assert shifted_sectors.tolist() == list(range(8))


def test_aperture_sector_coverage_ignores_outer_surface_crossings():
    nodes = []
    triangles = []

    def add_crossing(radius, angle):
        start = len(nodes)
        for delta, z in ((-0.02, -0.1), (0.0, 0.1), (0.02, -0.1)):
            nodes.append([
                radius * math.cos(angle + delta),
                radius * math.sin(angle + delta),
                z,
            ])
        triangles.append([start, start + 1, start + 2])

    add_crossing(0.1, 0.1)
    for sector in range(8):
        add_crossing(0.5, (sector + 0.5) * 2.0 * math.pi / 8.0)
    structure = metrics3d.surface_structure(
        {
            "material_name": "Cu",
            "nodes": np.asarray(nodes, dtype=float),
            "triangles": np.asarray(triangles, dtype=int),
        },
        {
            "mouth_z": 0.0,
            "mouth_radius_median": 0.1,
            "mouth_radius_maximum": 0.12,
        },
    )
    assert structure["mouth_intersection_point_count"] > 0
    assert structure["mouth_sector_count"] == 1
    assert not structure["cavity_open"]


def test_sector_count_nonfinite_and_plating_filters_fail_closed():
    coordinates, material_ids, flux, coverage, velocity, reference = (
        _synthetic_sector_field()
    )
    keep = np.ones(len(coordinates), dtype=bool)
    sector = metrics3d._sector_indices(coordinates[:, 0], coordinates[:, 1], 0.0)
    floor = np.arange(len(coordinates)) < 480
    keep[floor & (sector == 0)] = False
    regions, _ = metrics3d.region_statistics(
        coordinates[keep],
        material_ids[keep],
        flux[keep],
        coverage[keep],
        velocity[keep],
        [float(ps.Material.Cu.legacyId())],
        reference,
        0.0,
    )
    decision = metrics3d.transport_decision(regions, reference, 50, _valid_guards())
    assert not decision["conditions"]["all_required_sectors_finite_and_populated"]
    for region_name in ("lower_wall", "middle_wall", "upper_wall"):
        changed_regions = copy.deepcopy(regions)
        changed_regions[f"{region_name}_sector_1"] = {
            "point_count": 0,
            "plating_only": True,
            **{
                quantity: {"mean": None, "q10": None, "q50": None, "q90": None}
                for quantity in metrics3d.QUANTITIES
            },
        }
        changed_decision = metrics3d.transport_decision(
            changed_regions, reference, 50, _valid_guards()
        )
        assert not changed_decision["pass"]
        assert not changed_decision["conditions"][
            "all_required_sectors_finite_and_populated"
        ]
        assert changed_decision[
            "realized_min_floor_to_fastest_wall_velocity_ratio"
        ] is None
    bad = flux.copy()
    bad[0] = float("nan")
    try:
        metrics3d.region_statistics(
            coordinates,
            material_ids,
            bad,
            coverage,
            velocity,
            [float(ps.Material.Cu.legacyId())],
            reference,
            0.0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("nonfinite 3D response was accepted")


def test_analytic_law_and_protected_triangle_guard():
    flux = np.asarray([0.2, 1.0, 0.5])
    ids = np.asarray([
        ps.Material.Cu.legacyId(),
        ps.Material.Cu.legacyId(),
        ps.Material.SiO2.legacyId(),
    ], dtype=float)
    result = metrics3d.analytic_diagnostics(
        flux,
        ids,
        [float(ps.Material.Cu.legacyId())],
        pi_a=5.0,
        deactivation_rate=0.25,
        active_rate=0.2,
        suppressed_rate=0.01,
    )
    assert result["relative_balance_error"] < 1e-12
    assert result["velocity"][2] == 0.0
    mesh = {
        "material_name": "Si",
        "nodes": np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        "triangles": np.asarray([[0, 1, 2]]),
    }
    assert metrics3d.protected_stack_delta([mesh], [copy.deepcopy(mesh)])[
        "survives"
    ]
    changed = copy.deepcopy(mesh)
    changed["triangles"] = np.asarray([[0, 2, 1]])
    assert not metrics3d.protected_stack_delta([mesh], [changed])["survives"]


def test_parent_artifacts_verify_and_tampering_is_rejected():
    data = manifest()
    parents, errors = campaign.load_verified_2d_comparison(data, ROOT)
    assert errors == []
    assert len(parents) == 24
    assert len({row["diagnostic_snapshot_sha256"] for row in parents.values()}) == 16
    tampered = copy.deepcopy(data)
    tampered["matched_2d_comparison"]["rows"][0][
        "parent_row_canonical_sha256"
    ] = "0" * 64
    _, errors = campaign.load_verified_2d_comparison(tampered, ROOT)
    assert any("row hash mismatch" in error for error in errors)


def test_resume_is_strict_and_allows_only_failures_before_one_success():
    data = manifest()
    fingerprint = {"test": "resume"}
    case = campaign.expand_cases(data, fingerprint)[0]
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rows = root / "rows.jsonl"
        snapshot_dir = campaign._snapshot_directory(rows)
        snapshot_dir.mkdir()
        snapshot = snapshot_dir / f"{case['case_id']}_c0001.npz"
        snapshot.write_bytes(b"snapshot")
        common = {
            **case,
            "evidence_origin": campaign._evidence_origin(),
            "rng_stream": campaign._rng_stream(case),
        }
        success = {
            **common,
            "ok": True,
            "diagnostic_snapshot_path": str(snapshot),
            "diagnostic_snapshot_sha256": campaign._file_sha256(snapshot),
        }
        failure = {**common, "ok": False, "error": "fixture"}
        rows.write_text(json.dumps(failure) + "\n")
        assert campaign._completed_case_ids(rows, [case]) == set()
        rows.write_text(json.dumps(failure) + "\n" + json.dumps(success) + "\n")
        assert campaign._completed_case_ids(rows, [case]) == {case["case_id"]}

        invalid_artifacts = [
            json.dumps(success) + "\n" + json.dumps(success) + "\n",
            json.dumps(success) + "\n" + json.dumps(failure) + "\n",
            "{truncated\n",
            json.dumps({**success, "case_id": "unexpected"}) + "\n",
        ]
        for text in invalid_artifacts:
            rows.write_text(text)
            try:
                campaign._completed_case_ids(rows, [case])
            except ValueError:
                pass
            else:
                raise AssertionError("corrupt resume artifact was accepted")

        stale = copy.deepcopy(success)
        stale["runtime_fingerprint"] = {"stale": True}
        rows.write_text(json.dumps(stale) + "\n")
        try:
            campaign._completed_case_ids(rows, [case])
        except ValueError:
            pass
        else:
            raise AssertionError("stale runtime fingerprint was accepted")

        outside = root / "outside.npz"
        outside.write_bytes(b"snapshot")
        displaced = {
            **success,
            "diagnostic_snapshot_path": str(outside),
            "diagnostic_snapshot_sha256": campaign._file_sha256(outside),
        }
        rows.write_text(json.dumps(displaced) + "\n")
        try:
            campaign._completed_case_ids(rows, [case])
        except ValueError:
            pass
        else:
            raise AssertionError("arbitrary snapshot path was accepted")


def test_snapshot_rejects_coplanar_diagnostics_nonfinite_nodes_and_bad_triangles():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        row = campaign.run_case((_tiny_process_case(), root))
        assert row["ok"], row.get("error")
        with np.load(row["diagnostic_snapshot_path"], allow_pickle=False) as saved:
            pristine = {key: np.array(saved[key], copy=True) for key in saved.files}

        mutations = []
        changed = copy.deepcopy(pristine)
        changed["diagnostic_coordinates"][:, 1] = 0.0
        mutations.append((changed, "diagnostic coordinates are coplanar"))
        changed = copy.deepcopy(pristine)
        changed["pre_level_set_0_nodes"][0, 0] = float("nan")
        mutations.append((changed, "nodes contain nonfinite"))
        changed = copy.deepcopy(pristine)
        changed["post_level_set_4_triangles"][0, 0] = len(
            changed["post_level_set_4_nodes"]
        ) + 1
        mutations.append((changed, "triangle index is out of range"))

        for index, (arrays, expected_error) in enumerate(mutations):
            path = root / f"mutated_{index}.npz"
            with path.open("wb") as handle:
                np.savez_compressed(handle, **arrays)
            changed_row = {
                **row,
                "diagnostic_snapshot_path": str(path),
                "diagnostic_snapshot_sha256": campaign._file_sha256(path),
            }
            record, errors = review.review_case(changed_row, root)
            assert record is None
            assert any(expected_error in error for error in errors), errors


def _phase_decision(values, passed=False):
    return {
        "pass": passed,
        "conditions": {"synthetic_gate": passed},
        "floor_to_lower_flux_ratios": [
            values["worst_floor_to_each_lower_flux_ratio"]
        ],
        "lower_minus_floor_coverage": [
            values["minimum_lower_minus_floor_coverage"]
        ],
        "floor_to_lower_velocity_ratios": [
            values["worst_floor_to_each_lower_velocity_ratio"]
        ],
        "minimum_floor_minus_fastest_middle_upper_velocity": values[
            "minimum_floor_minus_middle_upper_velocity"
        ],
        "realized_min_floor_to_fastest_wall_velocity_ratio": values[
            "realized_min_floor_to_fastest_wall_velocity_ratio"
        ],
    }


def _synthetic_record(design, tier, seed, reflections, values, passed=False):
    decision = _phase_decision(values, passed)
    return {
        "row": {
            "design": design,
            "geometry_tier": tier,
            "rng_seed": seed,
            "numerics": {"max_reflections": reflections},
        },
        "phase_decisions": {
            "offset_0_degrees": copy.deepcopy(decision),
            "offset_22.5_degrees": copy.deepcopy(decision),
        },
        "phase_class_stable": True,
    }


def _reflection_records(high_deltas):
    base = {name: 0.0 for name in review.RESPONSES}
    records = []
    for tier in campaign.GEOMETRY_TIERS:
        for seed in campaign.PAIRED_BASE_SEEDS:
            records.append(_synthetic_record(
                campaign.CANDIDATE_NAME, tier, seed, 1600, base
            ))
            records.append(_synthetic_record(
                campaign.CANDIDATE_NAME,
                tier,
                seed,
                3200,
                {name: high_deltas.get(name, 0.0) for name in review.RESPONSES},
            ))
    return records


def test_reflection_convergence_enforces_every_frozen_response_tolerance():
    data = manifest()
    tolerances = data["reflection_convergence"][
        "maximum_paired_absolute_delta"
    ]
    at_limit = review.reflection_convergence(
        _reflection_records(tolerances), data
    )
    assert at_limit["eligible"]
    assert at_limit["class_stable"]
    assert at_limit["responses_within_tolerance"]
    assert at_limit["converged"]

    above = copy.deepcopy(tolerances)
    response = "worst_floor_to_each_lower_flux_ratio"
    above[response] = float(np.nextafter(above[response], math.inf))
    not_converged = review.reflection_convergence(
        _reflection_records(above), data
    )
    assert not not_converged["responses_within_tolerance"]
    assert not not_converged["converged"]
    assert not not_converged["response_deltas"][response]["pass"]

    huge = review.reflection_convergence(
        _reflection_records({response: 999999.0}), data
    )
    assert huge["eligible"] and huge["class_stable"]
    assert not huge["responses_within_tolerance"]


def _synthetic_dimension_records(oriented_signs):
    base = {name: 1.0 for name in review.RESPONSES}
    records = []
    for tier in campaign.GEOMETRY_TIERS:
        for seed in campaign.PAIRED_BASE_SEEDS:
            records.append(_synthetic_record(
                campaign.CONTROL_NAME, tier, seed, 800, base
            ))
            candidate = dict(base)
            for response, sign in oriented_signs.items():
                candidate[response] += sign if review.RESPONSES[response] else -sign
            records.append(_synthetic_record(
                campaign.CANDIDATE_NAME, tier, seed, 3200, candidate
            ))
    return records


def test_hash_pinned_2d_re_review_and_aggregate_dimensional_comparison():
    data = manifest()
    parents, errors = campaign.load_verified_2d_comparison(data, ROOT)
    assert errors == []
    evidence, errors = review.independently_review_2d(parents, data, ROOT)
    assert errors == []
    assert evidence["record_count"] == 24
    assert evidence["arm_B800"]["classification"] == "no_go"
    assert evidence["arm_C3200"]["classification"] == "no_go"
    expected_directions = {
        "worst_floor_to_each_lower_flux_ratio": 0.004757391271372133,
        "minimum_lower_minus_floor_coverage": -0.000019386797140280576,
        "worst_floor_to_each_lower_velocity_ratio": 0.0011445216389621704,
        "minimum_floor_minus_middle_upper_velocity": -0.001151993221453328,
    }
    for response, expected in expected_directions.items():
        actual = evidence["directions"]["responses"][response][
            "mean_oriented_improvement"
        ]
        assert math.isclose(actual, expected, abs_tol=1e-15)

    signs = {name: math.copysign(0.01, value) for name, value in expected_directions.items()}
    records = _synthetic_dimension_records(signs)
    directions = review.paired_B_to_C_directions(records, evidence)
    assert directions["eligible"]
    assert all(
        item["classification"] == "agreement"
        for item in directions["responses"].values()
    )
    assert all(
        "direction_agreement_count" not in item
        for item in directions["responses"].values()
    )
    comparison = review.dimensional_comparison(records, evidence, directions)
    assert comparison["eligible"]
    assert not comparison["any_reversal"]
    assert all(
        item["classification"] == "agreement"
        for item in comparison["classes"].values()
    )

    reversed_records = _synthetic_dimension_records({
        **signs,
        "worst_floor_to_each_lower_flux_ratio": -signs[
            "worst_floor_to_each_lower_flux_ratio"
        ],
    })
    reversed_directions = review.paired_B_to_C_directions(
        reversed_records, evidence
    )
    reversed_comparison = review.dimensional_comparison(
        reversed_records, evidence, reversed_directions
    )
    assert reversed_comparison["eligible"]
    assert reversed_comparison["any_reversal"]
    authoritative = [
        record for record in reversed_records
        if record["row"]["design"] == campaign.CANDIDATE_NAME
    ]
    decision = review.decision_from_evidence(
        authoritative,
        {
            "eligible": True,
            "class_stable": True,
            "responses_within_tolerance": True,
        },
        True,
        reversed_comparison,
    )
    assert decision["classification"] == (
        "three_dimensional_transport_reversal_screen_requires_numerics"
    )


def test_decisions_never_authorize_terminal_work():
    convergence = {
        "eligible": True,
        "class_stable": True,
        "responses_within_tolerance": True,
    }
    dimensional = {
        "eligible": True,
        "any_reversal": False,
        "classes": {
            "B800": {"classification": "agreement"},
            "C3200": {"classification": "agreement"},
        },
    }
    fail_record = {"phase_decisions": {"a": {"pass": False}, "b": {"pass": False}}}
    pass_record = {"phase_decisions": {"a": {"pass": True}, "b": {"pass": True}}}
    for records in ([fail_record] * 8, [pass_record] * 8):
        decision = review.decision_from_evidence(
            records, convergence, True, dimensional
        )
        assert decision["morphology_authorized"] is False
        assert decision["terminal_model_family_pivot_authorized"] is False
        assert decision["automatic_model_family_pivot_authorized"] is False
        assert decision["automatic_additional_launch_authorized"] is False
        assert decision["process_recipe_authorized"] is False
        assert decision["conditional_numerical_and_unseen_arms_required"]
    ineligible = review.decision_from_evidence(
        [fail_record] * 8, {"eligible": False, "class_stable": False}, True
    )
    assert ineligible["classification"] == (
        "reflection_comparison_ineligible_blocks_inference"
    )
    response_miss = review.decision_from_evidence(
        [fail_record] * 8,
        {
            "eligible": True,
            "class_stable": True,
            "responses_within_tolerance": False,
        },
        True,
        dimensional,
    )
    assert response_miss["classification"] == "reflection_response_not_converged"
    cross_dimension_missing = review.decision_from_evidence(
        [fail_record] * 8, convergence, True, {"eligible": False}
    )
    assert cross_dimension_missing["classification"] == (
        "cross_dimensional_comparison_ineligible"
    )


def test_missing_rows_summary_is_strict_json_and_fail_closed():
    data = manifest()
    fingerprint = campaign.runtime_fingerprint(ROOT)
    summary = review.build_summary(
        data,
        [],
        [{"line": 1, "error": "truncated"}],
        True,
        fingerprint,
        ROOT,
    )
    assert summary["status"] != "complete"
    assert not summary["decision"]["morphology_authorized"]
    encoded = json.dumps(summary, allow_nan=False)
    assert json.loads(encoded)["expected_case_count"] == 24


if __name__ == "__main__":
    test_frozen_matrix_parent_bijection_and_commissioning_subset()
    test_manifest_mutations_fail_closed_and_runtime_is_exact()
    test_explicit_d3_full_cylinder_stack_reference_and_triangles()
    test_tiny_d3_process_populates_diagnostics_and_preserves_stack()
    test_sector_metrics_cover_both_offsets_and_do_not_average_away_failure()
    test_half_open_sector_boundaries_follow_atan2_xy_not_height()
    test_aperture_sector_coverage_ignores_outer_surface_crossings()
    test_sector_count_nonfinite_and_plating_filters_fail_closed()
    test_analytic_law_and_protected_triangle_guard()
    test_parent_artifacts_verify_and_tampering_is_rejected()
    test_resume_is_strict_and_allows_only_failures_before_one_success()
    test_snapshot_rejects_coplanar_diagnostics_nonfinite_nodes_and_bad_triangles()
    test_reflection_convergence_enforces_every_frozen_response_tolerance()
    test_hash_pinned_2d_re_review_and_aggregate_dimensional_comparison()
    test_decisions_never_authorize_terminal_work()
    test_missing_rows_summary_is_strict_json_and_fail_closed()
    print("Matched 3D Cu transport bridge tests: PASS")

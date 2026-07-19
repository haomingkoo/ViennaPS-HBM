"""Focused guards for the fast adaptive pattern/Bosch Gate-0 R1."""

import copy
import json
from pathlib import Path
import tempfile

import viennaps as ps

import foundation_pattern_bosch_gate0_r1 as campaign
import native_domain_checkpoint as native_checkpoint
import review_pattern_bosch_gate0_r1 as review


def manifest():
    return json.loads(campaign.DEFAULT_MANIFEST.read_text())


def cases():
    return campaign.expand_cases(manifest())


def fake_success(case, mask_survives=True):
    return {
        **case,
        "ok": True,
        "gates": {"etch_mask_resolved": mask_survives},
    }


def test_exact_nine_to_fourteen_adaptive_matrix():
    current_manifest = manifest()
    expanded = campaign.expand_cases(current_manifest)
    # R1 is immutable historical evidence. Its matrix must still validate,
    # while the deliberate post-run supersession guard remains visible as
    # current-source drift rather than being mistaken for evidence mutation.
    assert campaign.validate_manifest(
        current_manifest, expanded, check_runtime=False
    ) == []
    assert campaign.validate_manifest(current_manifest, expanded) == [
        "runtime or source fingerprint differs"
    ]
    assert len(expanded) == 20
    assert len({case["case_id"] for case in expanded}) == 20
    assert len(campaign.initial_cases(expanded)) == 9
    assert sum(case["adaptive"]["stage"] == "fixed" for case in expanded) == 8

    searches = sorted(
        campaign._by_stage(expanded, "search"),
        key=lambda case: case["adaptive"]["rate_index"],
    )
    successes = {}
    assert len(campaign.active_case_ids(expanded, successes)) == 9

    successes[searches[0]["case_id"]] = fake_success(searches[0], True)
    assert len(campaign.active_case_ids(expanded, successes)) == 10
    successes[searches[1]["case_id"]] = fake_success(searches[1], True)
    assert len(campaign.active_case_ids(expanded, successes)) == 11
    successes[searches[2]["case_id"]] = fake_success(searches[2], False)
    active = campaign.active_case_ids(expanded, successes)
    assert len(active) == 14
    assert campaign.selected_failure_index(expanded, successes) == (2, False)

    for case in campaign._by_stage(expanded, "fixed"):
        successes[case["case_id"]] = fake_success(case)
    assert not campaign.campaign_terminal(expanded, successes)
    for case in campaign._by_stage(expanded, "confirmation", 2):
        successes[case["case_id"]] = fake_success(case, False)
    assert campaign.campaign_terminal(expanded, successes)
    assert len(successes) == 14


def test_inactive_adaptive_rows_fail_closed():
    expanded = cases()
    second_search = next(
        case for case in expanded
        if case["adaptive"] == {"stage": "search", "rate_index": 1}
    )
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        campaign.gate0.append_row(output, {
            **second_search,
            "ok": False,
            "evidence_origin": campaign.evidence_origin(),
            "error": "synthetic",
        })
        try:
            campaign.audit_existing_rows(output, expanded)
        except ValueError as error:
            assert "inactive adaptive case" in str(error)
        else:
            raise AssertionError("inactive mask-ladder branch was accepted")

    fixed = campaign._by_stage(expanded, "fixed")[0]
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rows.jsonl"
        failed = {
            **fixed,
            "ok": False,
            "evidence_origin": campaign.evidence_origin(),
            "error": "synthetic",
        }
        for _ in range(15):
            campaign.gate0.append_row(output, failed)
        try:
            campaign.audit_existing_rows(output, expanded)
        except ValueError as error:
            assert "fourteen attempted cases" in str(error)
        else:
            raise AssertionError("attempt budget overrun was accepted")


def _analytic_domain(case, depth):
    domain = ps.Domain(
        gridDelta=case["numerics"]["grid_delta"],
        xExtent=case["geometry"]["x_extent"],
        yExtent=case["geometry"]["y_extent"],
    )
    ps.MakeHole(
        domain=domain,
        holeRadius=case["geometry"]["radius"],
        holeDepth=depth,
        maskHeight=case["geometry"]["mask_height"],
        maskTaperAngle=case["recipe"]["mask_taper"],
        holeShape=ps.HoleShape.FULL,
    ).apply()
    return domain


def _measured(depth):
    return {
        "etch": {
            "depth": depth,
            "cd_top": 0.3,
            "cd_middle": 0.3,
            "cd_bottom": 0.3,
            "cd_min": 0.3,
            "cd_max": 0.3,
            "max_cd_error": 0.0,
            "sidewall_angle_deg": 0.0,
            "max_bow": 0.0,
            "scallop_rms": 0.0,
            "sample_fractions": [],
            "sample_cds": [],
        },
        "mask_remaining_height": 0.3,
        "post_etch_mask": {"opening_valid": True},
    }


def test_run_case_keeps_depth_selected_native_domain():
    case = campaign.initial_cases(cases())[0]
    depths = [0.5, 1.1, 1.24, 1.5]
    domains = [_analytic_domain(case, depth) for depth in depths]
    measurements = {
        campaign.domain_mesh_sha256(domain): _measured(depth)
        for domain, depth in zip(domains, depths)
    }
    original_make = campaign.tp.make_initial_geometry
    original_etch = campaign.tp.bosch_etch
    original_pattern = campaign.gate0.measure_pattern
    original_measure = campaign._measure_domain

    def fake_etch(current, *, on_cycle, **_kwargs):
        for cycle, domain in enumerate(domains):
            current.deepCopy(domain)
            on_cycle(current, cycle)

    try:
        campaign.tp.make_initial_geometry = lambda **_kwargs: copy_domain(domains[0])
        campaign.tp.bosch_etch = fake_etch
        campaign.gate0.measure_pattern = lambda _mesh, _case: {
            "opening_cd_bottom": 0.3,
            "mask_height": 0.3,
            "opening_valid": True,
        }
        campaign._measure_domain = lambda domain, _case: (
            copy.deepcopy(measurements[campaign.domain_mesh_sha256(domain)]), []
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rows.jsonl"
            row = campaign.run_case((case, output))
            assert row["ok"], row
            assert row["selected_cycle"] == 2
            assert row["early_stopped"]
            assert row["checkpoint_format"] == "ViennaPS .vpsd"
            restored = native_checkpoint.load_domain_checkpoint(
                row["checkpoint_path"], expected_sha256=row["checkpoint_sha256"]
            )
            assert campaign.domain_mesh_sha256(restored) == row[
                "native_mesh_sha256"
            ]
            assert measurements[row["native_mesh_sha256"]]["etch"]["depth"] == 1.24
            campaign.gate0.append_row(output, row)
            successes, attempts = campaign.audit_existing_rows(output, cases())
            assert attempts == 1
            assert set(successes) == {case["case_id"]}
            campaign.gate0.append_row(output, row)
            try:
                campaign.audit_existing_rows(output, cases())
            except ValueError as error:
                assert "attempt follows success" in str(error)
            else:
                raise AssertionError("duplicate native success was accepted")
    finally:
        campaign.tp.make_initial_geometry = original_make
        campaign.tp.bosch_etch = original_etch
        campaign.gate0.measure_pattern = original_pattern
        campaign._measure_domain = original_measure


def copy_domain(domain):
    copied = ps.Domain()
    copied.deepCopy(domain)
    return copied


def _reviewed_row(case, *, survives=True, remaining=0.3):
    gates = {
        "pattern_width": True,
        "pattern_height": True,
        "pattern_opening": True,
        "etch_depth": True,
        "etch_cd_profile": True,
        "etch_bow": True,
        "etch_mask_resolved": survives,
        "pattern_pass": True,
        "etch_pass": survives,
    }
    return {
        "case_id": case["case_id"],
        "arm": case["arm"],
        "role": case["role"],
        "rng_seed": case["rng_seed"],
        "rays_per_point": case["numerics"]["rays_per_point"],
        "mask_ion_rate": case["recipe"]["mask_ion_rate"],
        "adaptive": case["adaptive"],
        "valid": True,
        "gates": gates,
        "hard_gate_pass": survives,
        "metrics": {
            "depth": 1.25,
            "cd_top": 0.3,
            "cd_middle": 0.3,
            "cd_bottom": 0.3,
            "max_cd_error": 0.0,
            "max_bow": 0.0,
            "scallop_rms": 0.0,
            "mask_remaining_height": remaining,
        },
    }


def test_reviewer_accepts_paired_bridge_and_first_confirmed_failure():
    current_manifest = manifest()
    expanded = cases()
    reviewed = []
    for case in campaign._by_stage(expanded, "fixed"):
        reviewed.append(_reviewed_row(case))
    search0 = next(
        case for case in campaign._by_stage(expanded, "search", 0)
    )
    reviewed.append(_reviewed_row(search0, survives=True, remaining=0.01))
    search1 = next(
        case for case in campaign._by_stage(expanded, "search", 1)
    )
    reviewed.append(_reviewed_row(search1, survives=False, remaining=0.0))
    for case in campaign._by_stage(expanded, "confirmation", 1):
        reviewed.append(_reviewed_row(case, survives=False, remaining=0.0))

    assert review.ray_bridge(reviewed, current_manifest)["pass"]
    bracket = review.mask_bracket(reviewed, current_manifest)
    assert bracket["pass"]
    assert bracket["selected_failure_rate"] == -0.06
    assert len(bracket["confirmations"]) == 4


def test_manifest_mutations_fail_closed():
    changed = manifest()
    changed["mask_bracket"]["search_rates"] = [-0.05, -0.08]
    assert campaign.validate_manifest(changed, check_runtime=False)
    changed = manifest()
    changed["numerics"]["screen_rays_per_point"] = 500
    assert campaign.validate_manifest(changed, check_runtime=False)
    changed = manifest()
    changed["authority"]["recipe_authorized"] = True
    assert campaign.validate_manifest(changed, check_runtime=False)


def test_incomplete_gate_never_authorizes_native_handoffs():
    # This test exercises incomplete-campaign authority, not the immutable
    # historical runtime fingerprint. Construct the same matrix against the
    # current guarded sources so the reviewer reaches that decision branch.
    current_runtime_manifest = manifest()
    current_runtime_manifest["runtime_fingerprint"] = (
        campaign.runtime_fingerprint()
    )
    with tempfile.TemporaryDirectory() as directory:
        summary = review.build_summary(
            current_runtime_manifest, Path(directory) / "missing.jsonl"
        )
    assert not summary["decision"]["broad_pattern_bosch_screen_authorized"]
    assert not summary["decision"]["reusable_upstream_geometry_authorized"]
    assert not summary["native_handoffs"]["decision"][
        "reusable_upstream_geometry_authorized"
    ]


if __name__ == "__main__":
    test_exact_nine_to_fourteen_adaptive_matrix()
    test_inactive_adaptive_rows_fail_closed()
    test_run_case_keeps_depth_selected_native_domain()
    test_reviewer_accepts_paired_bridge_and_first_confirmed_failure()
    test_manifest_mutations_fail_closed()
    test_incomplete_gate_never_authorizes_native_handoffs()
    print("pattern/Bosch Gate-0 R1 checks: PASS")

"""The API inventory must track every current wrapper parameter."""

import inspect
import json
from pathlib import Path

import api_knob_audit as audit
import tsv_process as tp


for function_name in audit.LOCAL_FUNCTIONS:
    expected = set(inspect.signature(getattr(tp, function_name)).parameters)
    recorded = set(audit.local_signature(function_name))
    assert recorded == expected, (function_name, expected - recorded, recorded - expected)

ray_defaults = audit.parameter_defaults("RayTracingParameters")
assert {
    "raysPerPoint",
    "rngSeed",
    "useRandomSeeds",
    "maxReflections",
    "maxBoundaryHits",
    "normalizationType",
} <= set(ray_defaults)
assert set(audit.parameter_defaults("AtomicLayerProcessParameters")) == {
    "coverageTimeStep",
    "numCycles",
    "pulseTime",
    "purgePulseTime",
    "purgeTimeStep",
}

registry = json.loads(
    Path("autoresearch-results/restart_audit/knob_registry.json").read_text()
)
by_id = {record["id"]: record for record in registry["records"]}
assert {
    by_id[id]["name"]
    for id in (
        "candidate_cmp_stop_height",
        "candidate_cmp_compliance_length",
        "candidate_cmp_residual_contact",
        "candidate_cmp_plated_cu_rate",
        "candidate_cmp_seed_material",
        "candidate_cmp_seed_rate",
        "candidate_cmp_tan_rate",
        "candidate_cmp_sio2_rate",
        "candidate_cmp_si_rate",
    )
} == {
    "stopHeight",
    "complianceLength",
    "residualContact",
    "platedCuRemovalRate",
    "cuSeedMaterial",
    "cuSeedRemovalRate",
    "tantalumNitrideRemovalRate",
    "siliconDioxideRemovalRate",
    "siliconRemovalRate",
}
assert all(
    by_id[id]["implementation_status"] == "required_unset_blocks_cmp_doe"
    and by_id[id]["default"] is None
    for id in (
        "cmp_minimum_stop_retained_spec",
        "cmp_maximum_stop_erosion_spec",
        "cmp_maximum_plug_height_loss_spec",
        "cmp_maximum_plug_area_loss_spec",
    )
)
assert all(
    f"api_AtomicLayerProcessParameters_{name}" in by_id
    for name in (
        "coverageTimeStep", "numCycles", "pulseTime",
        "purgePulseTime", "purgeTimeStep",
    )
)
assert by_id[
    "api_AtomicLayerProcessParameters_purgePulseTime"
]["implementation_status"] == "api_available_native_preflight_required"

assert {
    "candidate_liner_single_particle_dose",
    "candidate_liner_single_particle_sticking",
    "candidate_barrier_seed_field_dose",
    "candidate_barrier_seed_isotropic_fraction",
    "layer_isotropic_control_dose",
} <= set(by_id)
assert all(
    by_id[id]["current_best"] is None
    and by_id[id]["evidence_status"] == "screened"
    for id in (
        "candidate_liner_single_particle_dose",
        "candidate_liner_single_particle_sticking",
        "candidate_barrier_seed_field_dose",
        "candidate_barrier_seed_isotropic_fraction",
        "layer_isotropic_control_dose",
    )
)
assert by_id["phase_factor_barrier_iso"]["implementation_status"] == "legacy_only"
assert by_id["candidate_barrier_seed_isotropic_fraction"]["implementation_status"] == "wired_model_acceptance_candidate"
assert all(
    by_id[id]["implementation_status"] == "wired_model_acceptance_candidate"
    for id in (
        "teos_p1_sticking",
        "teos_p1_rate",
        "teos_p1_order",
        "liner_model_family",
    )
)

print("API knob audit checks: PASS")

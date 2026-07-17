"""Build the curated TSV traveler knob registry.

The raw pybind signatures live in ``api_signature_audit.json``.  This file adds
the scientific meaning needed to decide what may enter a DOE and writes both a
machine-readable JSON registry and a human-readable Markdown rendering.
"""

from __future__ import annotations

import argparse
import inspect
import json
from collections import Counter
from pathlib import Path

import joint_process_doe as joint
import layer_process_models as layer_models
import tsv_process as tp


OUT_DIR = Path("autoresearch-results/restart_audit")
JSON_PATH = OUT_DIR / "knob_registry.json"
MARKDOWN_PATH = OUT_DIR / "knob_registry.md"

REQUIRED_FIELDS = {
    "id",
    "step",
    "owner_api",
    "name",
    "units",
    "default",
    "tested_range",
    "current_best",
    "classification",
    "implementation_status",
    "expected_mechanism",
    "metrics_affected",
    "known_interactions",
    "upstream_consequences",
    "downstream_consequences",
    "evidence_status",
    "supporting_experiment",
    "confidence",
    "range_provenance",
}

CLASSIFICATIONS = {
    "product_specification",
    "recipe_knob",
    "model_coefficient",
    "numerical_control",
    "structural_choice",
    "model_limitation",
}

EVIDENCE_STATUSES = {
    "untested",
    "screened",
    "replicated",
    "confirmed",
    "rejected",
    "boundary-limited",
    "structurally-unresolvable",
}


def record(
    id,
    step,
    owner_api,
    name,
    *,
    units="dimensionless",
    default=None,
    tested_range=None,
    current_best=None,
    classification,
    implementation_status,
    expected_mechanism,
    metrics_affected=(),
    known_interactions=(),
    upstream_consequences="None; this is the first modeled stage.",
    downstream_consequences="No downstream consequence has been established.",
    evidence_status="untested",
    supporting_experiment="No valid experiment yet.",
    confidence="low",
    range_provenance="No defensible range has been assigned.",
    **extra,
):
    return {
        "id": id,
        "step": step,
        "owner_api": owner_api,
        "name": name,
        "units": units,
        "default": default,
        "tested_range": tested_range,
        "current_best": current_best,
        "classification": classification,
        "implementation_status": implementation_status,
        "expected_mechanism": expected_mechanism,
        "metrics_affected": list(metrics_affected),
        "known_interactions": list(known_interactions),
        "upstream_consequences": upstream_consequences,
        "downstream_consequences": downstream_consequences,
        "evidence_status": evidence_status,
        "supporting_experiment": supporting_experiment,
        "confidence": confidence,
        "range_provenance": range_provenance,
        **extra,
    }


LEGACY_BEST = {
    "mask_taper": 4.0,
    "num_cycles": 15,
    "etch_time": 0.5,
    "neutral_rate": -0.12,
    "neutral_sticking_probability": 0.08,
    "initial_etch_time": 0.3,
    "deposition_thickness": 0.01,
    "deposition_sticking_probability": 0.005,
    "ion_source_exponent": 200,
    "theta_r_min": 90.0,
    "liner_thick": 0.02,
    "liner_sticking": 0.24,
    "barrier_thick": 0.012,
    "barrier_iso": 0.0,
    "fill_thick": 0.22,
    "fill_iso": 0.05,
    "cmp_mult": 1.5,
}

PHASE_ONE_RANGES = {
    "mask_taper": [0.0, 2.0, 4.0, 6.0],
    "num_cycles": [10, 11, 12, 13, 14, 15, 16],
    "etch_time": [0.45, 0.50, 0.55, 0.60, 0.65, 0.70],
    "neutral_rate": [-0.15, -0.12, -0.10, -0.08, -0.06, -0.04],
    "neutral_sticking_probability": [0.05, 0.08, 0.12, 0.16, 0.20, 0.24],
    "initial_etch_time": [0.15, 0.20, 0.30, 0.45],
    "deposition_thickness": [0.003, 0.005, 0.010, 0.015],
    "deposition_sticking_probability": [0.0015, 0.003, 0.005, 0.010, 0.020],
    "ion_source_exponent": [100, 200, 400, 600, 800],
    "theta_r_min": [30.0, 45.0, 60.0, 75.0, 90.0],
    "liner_thick": [0.018, 0.020, 0.024, 0.028, 0.035, 0.045],
    "liner_sticking": [0.02, 0.08, 0.16, 0.24, 0.30, 0.35],
    "barrier_thick": [0.010, 0.012, 0.014, 0.018, 0.024],
    "barrier_iso": [0.0, 0.1, 0.2, 0.4],
    "fill_thick": [0.12, 0.14, 0.15, 0.155, 0.16, 0.18, 0.22, 0.26],
    "fill_iso": [0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.6],
    "cmp_mult": [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 3.0],
}


def suspended_best(name):
    return {
        "value": LEGACY_BEST[name],
        "status": "legacy_suspended",
        "source": "G009 g005_061_confirmed_reference under phase-one metrics",
    }


def qualification_setting(value):
    """Label a configured candidate value without calling it an optimum."""
    return {
        "value": value,
        "status": "qualification_setting_not_best",
        "source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json",
    }


def build_records():
    records = []
    add = records.append

    # Declared study outputs. These stay fixed during optimization, but their
    # physical-unit calibration is still open.
    specs = [
        ("pattern_radius_spec", "pattern", "opening radius", "simulation length", 0.15, [0.15], "Generated opening radius; twice this value is the nominal CD.", ["top_cd", "bottom_cd", "aspect_ratio"], "Every downstream flux and available volume changes with CD."),
        ("pattern_width_spec", "pattern", "opening width", "simulation length", 0.30, [0.30], "Nominal opening critical dimension.", ["top_cd", "bottom_cd", "cd_bias"], "Sets etch aspect ratio and the volume that liner, seed, and Cu must occupy."),
        ("pattern_mask_height_spec", "pattern", "pattern-mask height", "simulation length", 0.30, [0.30], "Sets the patterned masking-layer thickness.", ["mask_height", "mask_remaining"], "Controls etch protection and the field stack entering mask strip or CMP-stop selection."),
        ("etch_depth_spec", "bosch_etch", "target etch depth", "simulation length", 1.25, [1.15, 1.35], "Defines the qualified blind-via depth.", ["depth", "aspect_ratio"], "Controls every downstream coverage and fill requirement."),
        ("etch_cd_tolerance_spec", "bosch_etch", "CD-profile tolerance", "simulation length", 0.06, [0.0, 0.06], "Bounds measured CD departure over declared depth fractions.", ["entrance_cd", "mid_cd", "bottom_cd", "cd_profile_error"], "Constrains layer access and Cu-fill volume."),
        ("etch_bow_spec", "bosch_etch", "maximum wall bow", "simulation length", 0.03, [0.0, 0.03], "Bounds large-scale wall deviation after removing taper and scallop residual.", ["wall_bow", "sidewall_taper"], "Sharp narrowing or bulging changes film continuity and fill pinch-off risk."),
        ("liner_min_thickness_spec", "liner", "minimum local liner thickness", "simulation length", 0.02, [0.02, None], "Requires actual interface-to-interface SiO2 thickness, not commanded dose.", ["liner_min_thickness", "liner_continuity"], "Protects the barrier/seed from direct silicon contact."),
        ("liner_coverage_spec", "liner", "minimum liner conformality", "ratio", 0.995, [0.995, 1.0], "Bounds minimum/field local thickness after metric qualification.", ["liner_bottom_field", "liner_lower_wall_field"], "Controls dielectric continuity available to barrier deposition."),
        ("barrier_min_thickness_spec", "barrier_seed", "minimum local barrier/seed thickness", "simulation length", 0.012, [0.012, None], "Requires measured local layer thickness rather than input dose.", ["barrier_min_thickness", "seed_min_thickness", "layer_continuity"], "Controls Cu isolation and seed access for plating."),
        ("barrier_coverage_spec", "barrier_seed", "minimum barrier/seed conformality", "ratio", 0.985, [0.985, 1.0], "Bounds minimum/field local thickness after separate material tracking.", ["barrier_bottom_field", "seed_bottom_field"], "Constrains whether Cu plating has a continuous geometric seed path."),
        ("fill_overburden_spec", "cu_fill", "minimum Cu overburden", "simulation length", 0.15, [0.15, None], "Requires void-free closure plus positive measured Cu height above the field plane.", ["fill_height", "minimum_overburden", "overburden_nonuniformity"], "Provides removable Cu for CMP."),
        ("fill_void_spec", "cu_fill", "internal void/seam target", "count/area", 0, [0, 0], "Requires no open cavity, sealed void, or seam under the qualified topology metric.", ["void_count", "void_area", "maximum_void_size", "seam_length"], "A void invalidates CMP and the complete traveler."),
        ("cmp_dish_spec", "cmp", "Cu dish/recess target", "simulation length", 0.0, [0.0, 0.0], "Requires the signed plug height to match the cleared field plane within a qualified tolerance.", ["cu_dish", "cu_protrusion"], "Sets final planarity for subsequent integration."),
        ("cmp_stop_survival_spec", "cmp", "CMP stop-layer survival", "boolean", True, [True], "Requires the declared hard mask or dielectric stop to remain; photoresist identity is not accepted.", ["stop_layer_loss", "material_survival"], "Prevents destructive polish from being ranked as an improvement."),
    ]
    for id, step, name, units, default, tested, mechanism, metrics, downstream in specs:
        add(record(
            id, step, "program.md / tsv_process.TARGET_SPECS", name,
            units=units, default=default, tested_range=tested,
            classification="product_specification", implementation_status="output_target",
            expected_mechanism=mechanism, metrics_affected=metrics,
            downstream_consequences=downstream, evidence_status="boundary-limited",
            supporting_experiment="Declared study target; scoring is suspended pending CTQ qualification.",
            confidence="high for declared intent; low for physical calibration",
            range_provenance="Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.",
        ))

    factor_meta = {
        "mask_taper": ("pattern", "make_initial_geometry(taper) / MakeHole.maskTaperAngle", "degrees", 0.0, "Tilts the generated mask wall and changes the etch entrance boundary.", ["top_cd", "mask_sidewall_angle", "etch_variance"], ["mask_taper x stochastic ray sampling"], "Changes the upstream aperture.", "Propagates to etch CD and all downstream access."),
        "num_cycles": ("bosch_etch", "bosch_etch(num_cycles)", "cycles", 10, "Repeats passivation, punch-through, and etch phases.", ["depth", "scallop_period", "wall_bow"], ["num_cycles x etch_time", "num_cycles x deposition_thickness"], "Consumes the patterned-mask budget.", "Sets via depth and scallop history for every deposition."),
        "etch_time": ("bosch_etch", "bosch_etch(etch_time) / Process.duration", "simulation time per cycle", 1.5, "Extends each silicon etch phase.", ["depth", "etch_rate", "wall_bow", "cd_profile"], ["etch_time x deposition_thickness", "etch_time x num_cycles", "etch_time x neutral_rate"], "None beyond the pattern mask.", "Changes aspect ratio, CD, layer coverage, and Cu-fill volume."),
        "neutral_rate": ("bosch_etch", "bosch_etch rate_fn neutral coefficient", "simulation velocity coefficient", -0.2, "Scales the neutral chemical contribution on silicon.", ["depth", "undercut", "wall_bow"], ["neutral_rate x etch_time", "neutral_rate x neutral_sticking_probability"], "None beyond mask geometry.", "Changes wall shape and downstream line-of-sight."),
        "neutral_sticking_probability": ("bosch_etch", "MultiParticleProcess.addNeutralParticle", "probability", 0.1, "Controls neutral absorption versus reflection and therefore transport into the via.", ["depth", "cd_profile", "wall_bow"], ["neutral sticking x neutral_rate", "neutral sticking x aspect ratio"], "None beyond pattern geometry.", "Changes bottom flux and downstream geometry."),
        "initial_etch_time": ("bosch_etch", "bosch_etch(initial_etch_time)", "simulation time", 0.3, "Controls the unpassivated opening/seed etch before Bosch cycling.", ["entrance_cd", "depth", "undercut"], ["initial etch x mask taper"], "Can widen the mask opening transfer.", "Sets the mouth profile inherited by all later steps."),
        "deposition_thickness": ("bosch_etch", "SingleParticleProcess.rate for passivation", "simulation length per cycle", 0.02, "Commands the passivation dose before ion punch-through.", ["polymer_thickness", "wall_bow", "depth", "scallop_amplitude"], ["deposition thickness x etch_time", "deposition thickness x grid_delta"], "None beyond pattern geometry.", "Controls wall protection and therefore downstream roughness/access."),
        "deposition_sticking_probability": ("bosch_etch", "SingleParticleProcess.stickingProbability", "probability", 0.01, "Controls passivation-particle reflection and depth transport.", ["polymer_conformality", "wall_bow", "depth"], ["deposition sticking x aspect ratio"], "None beyond pattern geometry.", "Changes sidewall protection and scallop morphology."),
        "ion_source_exponent": ("bosch_etch", "MultiParticleProcess.addIonParticle(sourcePower)", "dimensionless exponent", 200, "Controls angular collimation of ion flux and passivation punch-through.", ["depth", "bottom_shape", "wall_bow"], ["ion exponent x theta_r_min", "ion exponent x rays_per_point"], "None beyond the mask.", "Changes anisotropy and bottom access."),
        "theta_r_min": ("bosch_etch", "MultiParticleProcess.addIonParticle(thetaRMin)", "degrees", 60.0, "Sets the lower angle in the ion sticking/reflection law.", ["depth", "bottom_shape", "cd_profile"], ["theta_r_min x ion_source_exponent"], "None beyond the mask.", "Changes reflected-ion transport and wall shape."),
        "liner_thick": ("liner", "deposit_conformal(thickness) / SingleParticleProcess.rate", "commanded simulation dose", None, "Scales the requested liner deposition velocity for a fixed unit duration.", ["actual_liner_thickness", "liner_conformality", "remaining_aperture"], ["liner dose x sticking", "liner dose x etched CD"], "Consumes the etched opening.", "Constrains barrier access and final capacitance, which this model does not calculate."),
        "liner_sticking": ("liner", "deposit_conformal(sticking) / SingleParticleProcess.stickingProbability", "probability", 0.05, "Controls particle reflection and transport to the lower wall/floor.", ["liner_conformality", "liner_min_thickness"], ["liner sticking x aspect ratio", "liner sticking x dose"], "None before the liner.", "Changes barrier access and dielectric continuity."),
        "barrier_thick": ("barrier_seed", "deposit_conformal(thickness) / DirectionalProcess.directionalVelocity", "commanded simulation dose", None, "Scales the directional barrier/seed deposition distance.", ["barrier_thickness", "seed_thickness", "remaining_aperture"], ["barrier dose x barrier_iso", "barrier dose x etched CD"], "Requires a qualified liner.", "Controls seed continuity and fill access."),
        "barrier_iso": ("barrier_seed", "DirectionalProcess.isotropicVelocity / directionalVelocity", "ratio", 0.3, "Mixes isotropic and vertical components in the geometric deposition surrogate.", ["barrier_conformality", "seed_conformality", "remaining_aperture"], ["barrier_iso x barrier dose", "barrier_iso x aspect ratio"], "Requires the lined profile.", "Changes bottom coverage and mouth pinch-off risk."),
        "fill_thick": ("cu_fill", "cu_fill(thickness) / deposition velocity", "commanded simulation dose", None, "Scales the legacy geometric Cu deposition distance; it is not final Cu thickness.", ["fill_height", "void_topology", "overburden"], ["fill dose x fill_iso", "fill dose x seed geometry"], "Requires a connected seed geometry.", "Sets CMP overburden and inherited topography."),
        "fill_iso": ("cu_fill", "DirectionalProcess.isotropicVelocity / directionalVelocity", "ratio", 0.2, "Mixes isotropic and vertical growth in the legacy fill negative control.", ["void_topology", "pinch_off", "fill_height"], ["fill_iso x fill dose", "fill_iso x via CD"], "Requires the seeded geometry.", "Changes the void/pinch-off morphology presented to CMP."),
        "cmp_mult": ("cmp", "joint_process_doe.apply_cmp(mult)", "overburden multiple", None, "Multiplies a recipe-dependent overburden before one-rate isotropic removal.", ["field_clear", "dish", "material_loss"], ["cmp_mult x fill overburden", "cmp_mult x material selectivity"], "Requires a filled geometry and derived target plane.", "Can erase mask, Cu, liner, or substrate; legacy winner is suspended."),
    }
    for name in joint.SPACE:
        step, owner, units, default, mechanism, metrics, interactions, upstream, downstream = factor_meta[name]
        add(record(
            f"phase_factor_{name}", step, owner, name,
            units=units, default=default, tested_range=PHASE_ONE_RANGES[name],
            current_best=suspended_best(name), classification=(
                "structural_choice" if name == "mask_taper" else
                "recipe_knob" if name in {"num_cycles", "etch_time", "initial_etch_time", "liner_thick", "barrier_thick", "fill_thick", "cmp_mult"} else
                "model_coefficient"
            ),
            implementation_status="legacy_only",
            expected_mechanism=mechanism, metrics_affected=metrics,
            known_interactions=interactions, upstream_consequences=upstream,
            downstream_consequences=downstream, evidence_status="screened",
            supporting_experiment="Phase-one 1,948-row campaign; rankings and best values are suspended because several CTQs were invalid.",
            confidence="medium for code-path sensitivity; low for physical interpretation",
            range_provenance="Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.",
            phase_one_factor=True,
        ))

    # Wrapper controls and fixed API choices not present in the 17-factor DOE.
    wrapper_controls = [
        ("pattern_grid_delta", "pattern", "make_initial_geometry(grid_delta) / Domain.gridDelta", "grid spacing", 0.01, [0.01, 0.005, 0.0025, 0.00125, 0.000625], "numerical_control", "wired", "Controls level-set and material-interface resolution.", ["all_geometry_ctqs", "topology"], ["grid_delta x every thin layer", "grid_delta x passivation dose"], "confirmed", "Foundation grid and Bosch passivation-resolution audits; 0.00125 is accepted only for focused high-fidelity 2D etch audits.", "medium", "Numerical-convergence ladder; not a recipe range."),
        ("pattern_x_extent", "pattern", "make_initial_geometry(x_extent) / Domain.xExtent", "simulation length", 1.0, [1.0], "numerical_control", "wired", "Sets lateral distance to the domain boundary.", ["boundary_clearance", "flux_transport"], ["x_extent x boundary condition"], "screened", "No dedicated lateral-domain convergence result yet.", "low", "Wrapper default only."),
        ("pattern_y_extent", "pattern", "make_initial_geometry(y_extent) / Domain.yExtent", "simulation length", 1.5, [1.5, 2.0, 2.5], "numerical_control", "wired", "Sets vertical distance to the lower domain boundary.", ["boundary_clearance", "depth", "cd_profile"], ["y_extent x target depth"], "confirmed", "Foundation domain audit reproduced full-cycle etch CTQs within 4.4e-15 across 1.5, 2.0, and 2.5 for two seeds.", "high for tested 2D etch", "Numerical domain-convergence experiment."),
        ("pattern_hole_depth", "pattern", "MakeHole.holeDepth", "simulation length", 0.0, [0.0], "structural_choice", "fixed", "Constructs a mask opening without a pre-etched silicon cavity.", ["opening_validity"], [], "confirmed", "Direct wrapper inspection.", "high", "Fixed by the intended pattern-before-etch sequence."),
        ("pattern_hole_taper", "pattern", "MakeHole.holeTaperAngle", "degrees", 0.0, [-10.0, -5.0, 0.0, 5.0, 10.0], "structural_choice", "api_available_unwired", "Would taper a pre-existing hole; with holeDepth=0 it is not a lithography control.", ["opening_profile"], ["hole taper x hole depth"], "screened", "Legacy API screen found a small apparent etch effect, but the current pattern has zero hole depth.", "low", "API-bounded sensitivity screen; no physical lithography mapping."),
        ("pattern_hole_shape", "pattern/cu_fill", "MakeHole.holeShape", "enum", "HoleShape.QUARTER in make_initial_geometry", ["QUARTER (2D symmetry-clipped half-trench)", "FULL (2D full trench)"], "structural_choice", "wired_by_stage", "Selects a symmetry-clipped half-domain or the full feature. FULL is mandatory when judging internal fill topology because a centerline void can otherwise be clipped into an open contour.", ["void_topology", "flux_transport", "runtime"], ["shape x dimensionality", "shape x boundary condition", "shape x void classification"], "confirmed", "Phase-one used 2D QUARTER. The isolated candidate-fill and sealed-void controls use FULL and demonstrate why fill topology requires the full 2D trench; matched 3D confirmation remains separate.", "high for the 2D topology requirement", "Structural guard exercised by test_copper_suppression_fill.py; it is not an interpolated recipe range."),
        ("pattern_substrate_material", "pattern", "MakeHole.material", "material enum", "Material.Si", ["Material.Si"], "structural_choice", "fixed", "Defines the etched substrate material identity.", ["material_survival", "etch_selectivity"], [], "confirmed", "Direct wrapper/API inspection.", "high", "Declared TSV silicon substrate."),
        ("pattern_mask_material", "pattern", "MakeHole.maskMaterial", "material enum", "Material.Mask", ["Material.Mask"], "structural_choice", "fixed", "Defines the temporary pattern-mask level set.", ["mask_remaining", "stop_layer_identity"], ["mask identity x strip sequence", "mask identity x CMP stop"], "boundary-limited", "Mask identity is explicitly challenged in RESEARCH_PLAN_V2; photoresist may not be carried through physical CMP.", "high for code identity; low for physical stack", "Structural choice awaiting hard-mask versus stripped-resist decision."),
        ("pattern_mask_strip", "pattern", "strip_pattern_mask / Domain.removeMaterial", "boolean sequence choice", True, [False, True], "structural_choice", "wired", "Removes the temporary pattern mask before dielectric deposition.", ["material_stack", "remaining_aperture"], ["strip choice x CMP stop identity"], "confirmed", "Wrapper guard verifies Material.Mask is absent after stripping; full traveler wiring remains to be completed.", "high for operation", "Required by the temporary-photoresist interpretation; alternative hard-mask stack remains a controlled structural arm."),
        ("bosch_ion_rate", "bosch_etch", "bosch_etch(ion_rate) / rate_fn", "simulation velocity coefficient", -0.1, [-0.2, -0.05], "model_coefficient", "wired_fixed_in_doe", "Scales the ion-flux contribution to surface velocity.", ["depth", "bottom_shape", "cd_profile"], ["ion_rate x source exponent", "ion_rate x etch_time"], "screened", "Legacy one-factor screen; not depth-matched and omitted from the 17-factor joint space.", "low", "Model-sensitivity endpoints only."),
        ("bosch_mask_ion_rate", "pattern/bosch_etch", "bosch_etch(mask_ion_rate) / rate_fn", "simulation velocity coefficient", 0.0, [0.0, -0.01, -0.02, -0.04], "model_coefficient", "wired_model_sensitivity", "Scales ion-driven loss of the temporary pattern mask during every etch phase; zero is the historical infinite-selectivity control.", ["mask_remaining", "opening_cd_profile", "etch_depth", "etch_cd_profile", "wall_bow"], ["mask erosion x mask height", "mask erosion x taper", "mask erosion x cycle count", "mask erosion x ion transport"], "boundary-limited", "The full-width fine-grid Gate-0 block retained a resolved mask on all four seeds through -0.04. The later R1 numerical release intentionally ran no mask-ladder rows, so the first full-width survive/fail boundary remains unknown and is assigned to V3 Stage 2f.", "medium for model response; low for physical calibration", "The qualified range currently establishes survival only. Stage 2f adaptively challenges -0.05, -0.06, and -0.08, but no coefficient value is a fab selectivity range without calibration."),
        ("bosch_rays_per_point", "bosch_etch", "bosch_etch(rays_per_point) / RayTracingParameters.raysPerPoint", "rays per surface point", 1000, [250, 500, 1000, 2000, 4000], "numerical_control", "wired", "Controls Monte Carlo flux sampling density.", ["depth", "cd_profile", "bow", "run_variance"], ["rays x grid_delta", "rays x source exponent"], "screened", "Foundation CTQ qualification found ray-count effects smaller than unresolved grid bias over 250-4000 for the tested recipe.", "medium", "Numerical-convergence range."),
        ("bosch_rng_seed", "bosch_etch", "bosch_etch(rng_seed) / RayTracingParameters.rngSeed", "integer seed", None, ["explicit fixed seeds in foundation manifests"], "numerical_control", "wired", "Selects reproducible ray-tracing streams; each process phase offsets the base seed.", ["replicate_identity", "run_variance"], ["seed x rays_per_point", "seed x geometry"], "confirmed", "Fixed-seed thread-control and convergence campaigns.", "high", "Reproducibility control; not a physical range."),
        ("bosch_on_cycle", "bosch_etch", "bosch_etch(on_cycle)", "callable or null", None, [None, "cycle-history callback"], "numerical_control", "wired", "Captures intermediate geometry after each etch cycle without intentionally changing physics.", ["cycle_depth", "cycle_cd", "cycle_topology"], [], "confirmed", "Foundation cycle-history runner.", "high", "Observation callback; excluded from DOE factors."),
        ("bosch_on_polymer", "bosch_etch", "bosch_etch(on_polymer)", "callable or null", None, [None, "polymer-history callback"], "numerical_control", "wired", "Captures passivation morphology before punch-through.", ["polymer_thickness", "polymer_continuity"], [], "screened", "Bosch resolution audit saved intermediate polymer states.", "medium", "Observation callback; excluded from DOE factors."),
        ("deposit_material", "liner/barrier_seed", "deposit_conformal(material) / duplicateTopLevelSet", "material enum", None, ["SiO2", "TaN", "registered CuSeed", "Cu"], "structural_choice", "wired", "Selects the explicitly tracked deposited material layer.", ["material_survival", "layer_thickness", "continuity"], ["material identity x CMP selectivity"], "confirmed", "API audit records separate SiO2, TaN, registered CuSeed, and plated-Cu identities.", "high", "Declared material stack, not a numerical sweep."),
        ("deposit_directional", "liner/barrier_seed", "deposit_conformal(directional)", "boolean", False, [False, True], "structural_choice", "wired", "Chooses sticking-controlled particle transport or geometric directional deposition.", ["layer_conformality", "remaining_aperture"], ["model choice x dose", "model choice x aspect ratio"], "screened", "Legacy liner used False; barrier/seed used True. Neither is accepted as calibrated chemistry.", "medium for morphology; low for physical mapping", "Model-family comparison."),
        ("deposit_rays_per_point", "liner/barrier_seed", "deposit_conformal(rays_per_point) / RayTracingParameters", "rays per surface point", 1000, [1000], "numerical_control", "wired", "Controls ray sampling for SingleParticleProcess transport.", ["local_thickness", "conformality", "run_variance"], ["rays x grid_delta", "rays x sticking"], "untested", "No accepted liner/barrier ray-convergence study yet.", "low", "Wrapper default; qualification range not chosen."),
        ("deposit_rng_seed", "liner/barrier_seed", "deposit_conformal(rng_seed) / RayTracingParameters", "integer seed", None, ["explicit foundation seeds"], "numerical_control", "wired", "Makes transport comparisons reproducible on shared upstream geometry.", ["run_variance", "local_thickness"], ["seed x upstream geometry"], "screened", "Foundation layer audit manifests use explicit seeds.", "medium", "Reproducibility control, not a recipe range."),
        ("fill_directional", "cu_fill", "cu_fill(directional)", "boolean", False, [False, True], "structural_choice", "wired", "Chooses isotropic deposition or the legacy directional geometric surrogate.", ["fill_height", "void_topology", "pinch_off"], ["model choice x fill dose", "model choice x via geometry"], "rejected", "Legacy model pair is retained only as a negative control; it has not produced the required fill morphology.", "high", "Structural negative-control comparison."),
        ("cmp_target_y", "cmp", "cmp_planarize(target_y) / joint apply_cmp", "simulation height", None, ["derived liner/field plane", 0.3], "recipe_knob", "wired", "Sets the nominal planarization/endpoint plane.", ["field_clear", "dish", "erosion", "material_loss"], ["target_y x fill overburden", "target_y x selectivity"], "screened", "Legacy target-plane and overpolish curves; conclusions suspended under the one-rate model.", "low for physical CMP", "Derived model-space endpoint; no calibrated physical endpoint."),
        ("cmp_isotropic_rate", "cmp", "IsotropicProcess.rate", "simulation velocity", -1.0, [-1.0], "model_coefficient", "fixed_legacy_negative_control", "Moves every unmasked material inward at one normal velocity.", ["field_clear", "material_loss", "dish"], ["rate x process duration", "rate x material identity"], "rejected", "Controlled audit showed one-rate removal can erase unrelated materials and cannot represent physical planarization.", "high", "Legacy fixed negative control."),
        ("cmp_material_rates", "cmp", "IsotropicProcess.materialRates/defaultRate", "material-to-velocity map", None, ["single exploratory Cu-selectivity arm"], "model_coefficient", "api_available_unwired", "Assigns independent normal removal rates by material.", ["field_clear", "barrier_loss", "dielectric_erosion", "plug_loss"], ["selectivity x endpoint delay", "selectivity x stack identity"], "screened", "One exploratory legacy run; a controlled sweep remains open.", "medium for API capability; low for CMP realism", "API-available perfect-selectivity control; no calibration."),
        ("cmp_mask_materials", "cmp", "IsotropicProcess.maskMaterial(s)", "material enum/list", "Material.Undefined", ["Undefined", "declared stop layer"], "structural_choice", "api_available_unwired", "Assigns zero removal to declared protected materials.", ["stop_layer_loss", "material_survival"], ["mask identity x target_y"], "untested", "Official API inspected; physical stop identity not frozen.", "medium", "API structural choice awaiting stack decision."),
        ("cmp_planarize_cutoff", "cmp", "Planarize.cutoffHeight", "simulation height", 0.0, None, "structural_choice", "api_available_unwired", "Clips geometry at a plane and can serve as an ideal endpoint/morphology control.", ["field_clear", "ideal_planarity"], ["cutoff x input overburden"], "untested", "Planned as an ideal endpoint control, not as physical CMP.", "medium for API function", "API default; experiment not run."),
    ]
    for id, step, owner, units, default, tested, classification, implementation, mechanism, metrics, interactions, status, support, confidence, provenance in wrapper_controls:
        add(record(
            id, step, owner, id.replace("_", " "), units=units, default=default,
            tested_range=tested, classification=classification,
            current_best=(
                {
                    "value": {
                        "phase_one_pattern_etch": "QUARTER",
                        "candidate_fill_topology": "FULL",
                    },
                    "status": "stage_specific_validity_choice",
                    "source": "test_copper_suppression_fill.py and foundation_copper_fill_trajectory.py",
                }
                if id == "pattern_hole_shape" else None
            ),
            implementation_status=implementation, expected_mechanism=mechanism,
            metrics_affected=metrics, known_interactions=interactions,
            upstream_consequences="May alter the state entering this process step.",
            downstream_consequences="Any morphology or material change propagates to every later step.",
            evidence_status=status, supporting_experiment=support,
            confidence=confidence, range_provenance=provenance,
        ))

    # Candidate layer controls use explicit, non-confounded parameterizations.
    # These values are only code-path diagnostics until the accepted full-width
    # Gate-0 geometries have passed the layer model-acceptance study.
    candidate_layer_controls = [
        (
            "candidate_liner_single_particle_dose", "liner",
            "layer_process_models.deposit_single_particle(dose)",
            "single-particle commanded dose", "simulation length", None,
            [0.04], "model_coefficient", "wired_model_acceptance_candidate",
            "Scales the generic diffuse-reflection deposition velocity at fixed duration.",
            ["field_thickness", "minimum_local_thickness", "remaining_aperture"],
            ["dose x sticking probability", "dose x incoming via geometry"],
        ),
        (
            "candidate_liner_single_particle_sticking", "liner",
            "layer_process_models.deposit_single_particle(sticking_probability)",
            "single-particle sticking probability", "probability", None,
            [0.01], "model_coefficient", "wired_model_acceptance_candidate",
            "Controls absorption versus diffuse reflection and therefore precursor access to the lower via.",
            ["floor_to_field_conformality", "lower_wall_to_field_conformality", "minimum_local_thickness"],
            ["sticking x aspect ratio", "sticking x reflection ceiling", "sticking x dose"],
        ),
        (
            "candidate_barrier_seed_field_dose", "barrier_seed",
            "layer_process_models.deposit_directional_fraction(field_dose)",
            "constant horizontal-field dose", "simulation length", None,
            [0.04], "model_coefficient", "wired_model_acceptance_candidate",
            "Holds total nominal field growth fixed while the directional/isotropic split changes.",
            ["field_thickness", "minimum_local_thickness", "remaining_aperture"],
            ["field dose x isotropic fraction", "field dose x incoming aperture"],
        ),
        (
            "candidate_barrier_seed_isotropic_fraction", "barrier_seed",
            "layer_process_models.deposit_directional_fraction(isotropic_fraction)",
            "isotropic fraction of fixed field dose", "fraction", None,
            [0.0, 0.5, 1.0], "model_coefficient", "wired_model_acceptance_candidate",
            "Redistributes a fixed field dose between vertical line-of-sight and isotropic normal growth without increasing total field dose.",
            ["wall_to_field_conformality", "floor_to_field_conformality", "remaining_aperture"],
            ["isotropic fraction x aspect ratio", "isotropic fraction x field dose", "isotropic fraction x material sequence"],
        ),
        (
            "layer_isotropic_control_dose", "liner/barrier_seed",
            "layer_process_models.deposit_isotropic_control(dose)",
            "ideal isotropic-control dose", "simulation length", None,
            [0.03], "model_coefficient", "representation_control_only",
            "Provides a morphology-positive control for the metric and geometry; it is not a calibrated deposition mechanism.",
            ["field_thickness", "conformality", "minimum_local_thickness", "remaining_aperture"],
            ["control dose x grid resolution", "control dose x incoming geometry"],
        ),
    ]
    for id, step, owner, name, units, default, tested, classification, implementation, mechanism, metrics, interactions in candidate_layer_controls:
        add(record(
            id, step, owner, name,
            units=units, default=default, tested_range=tested,
            current_best=None, classification=classification,
            implementation_status=implementation,
            expected_mechanism=mechanism, metrics_affected=metrics,
            known_interactions=interactions,
            upstream_consequences="Requires an accepted full-width Bosch geometry and explicit incoming material interfaces.",
            downstream_consequences="Changes layer continuity, aperture, seed access, and the geometry inherited by Cu fill.",
            evidence_status="screened",
            supporting_experiment="test_layer_process_models.py verifies parameter bounds and the expected full-width morphology response on an analytic via only; no Gate-0 traveler geometry has been accepted.",
            confidence="high for code parameterization; low for physical applicability",
            range_provenance="Exact diagnostic values exercised by test_layer_process_models.py; not a DOE range or fab calibration.",
        ))

    # Reduced Cu-fill candidate. These are morphology-model coefficients, not
    # fab recipe knobs. The only evidence so far is the isolated rate-field,
    # material-gate, parameter-guard, and sealed-void controls; the staged
    # trajectory manifest is not counted as an executed DOE.
    candidate_fill_controls = [
        {
            "id": "candidate_fill_suppressor_sticking_probability",
            "name": "suppressorStickingProbability",
            "units": "probability",
            "default": 0.1,
            "tested_range": [0.0, 0.2],
            "current": 0.2,
            "expected_mechanism": "Controls suppressor absorption versus diffuse reflection and also multiplies the local adsorption term.",
            "known_interactions": [
                "sticking x ray-access flux",
                "sticking x adsorptionStrength",
                "sticking x aspect ratio",
            ],
            "identifiability": "It changes both transport and uptake, so morphology alone cannot separate a sticking change from a changed suppressor supply or adsorptionStrength.",
            "support": "Isolated flat and full-via rate-field checks exercised sticking=0 and 0.2; 1.1 is an invalid-input guard, not a tested process value.",
            "confidence": "medium for numerical behavior; low for morphology sensitivity",
        },
        {
            "id": "candidate_fill_suppressor_source_power",
            "name": "suppressorSourcePower",
            "units": "dimensionless angular exponent",
            "default": 1.0,
            "tested_range": [1.0],
            "current": 1.0,
            "expected_mechanism": "Shapes the angular distribution of suppressor rays entering the feature.",
            "known_interactions": [
                "source power x via aspect ratio",
                "source power x sticking",
                "source power x ray normalization",
            ],
            "identifiability": "Only one value has been exercised. Its effect can be confounded with geometry, mean free path, and sticking through the resulting access field.",
            "support": "The isolated rate-field controls exercised sourcePower=1 only; no sensitivity ranking or production DOE exists.",
            "confidence": "high for API wiring; low for sensitivity",
        },
        {
            "id": "candidate_fill_gas_mean_free_path",
            "name": "gasMeanFreePath",
            "units": "simulation length",
            "default": -1.0,
            "tested_range": [-1.0],
            "current": -1.0,
            "expected_mechanism": "Sets the ray-transport mean free path; -1 retains the ViennaRay no-gas-collision sentinel behavior.",
            "known_interactions": [
                "mean free path x feature depth",
                "mean free path x source power",
                "mean free path x sticking",
            ],
            "identifiability": "Only the -1 sentinel has been exercised. Any finite value would alter the same access field as source angle and geometry and needs an independent transport study.",
            "support": "The isolated rate-field controls and staged trajectory use the -1 default only; finite mean-free-path behavior is untested.",
            "confidence": "high for API wiring; low for finite-transport applicability",
        },
        {
            "id": "candidate_fill_adsorption_strength",
            "name": "adsorptionStrength",
            "units": "combined model adsorption coefficient",
            "default": 1.0,
            "tested_range": {
                "isolated_rate_field": [0.0, 0.25, 5.0],
                "finite_numerical_guard": [1e150],
            },
            "current": [0.1, 0.25, 0.5],
            "expected_mechanism": "Scales suppressor uptake as a combined adsorption coefficient times suppressor activity; larger values increase equilibrium suppression where flux reaches the surface.",
            "known_interactions": [
                "adsorptionStrength x sticking x suppressor flux",
                "adsorptionStrength x deactivationRate",
                "adsorptionStrength x deposition rates",
            ],
            "identifiability": "This coefficient already combines adsorption kinetics and suppressor activity. With fixed deposition rates, coverage mainly constrains its ratio to deactivationRate rather than either coefficient independently.",
            "support": "Isolated flat/rate-field tests exercised 0, 0.25, and 5; 1e150 is only an overflow guard. The 0.1/0.25/0.5 trajectory arms are staged, not completed evidence.",
            "confidence": "medium for equilibrium response; low for physical identifiability",
            "staged_range": [0.1, 0.25, 0.5],
        },
        {
            "id": "candidate_fill_deactivation_rate",
            "name": "deactivationRate",
            "units": "model inverse deposited length",
            "default": 1.0,
            "tested_range": [0.25],
            "current": 0.25,
            "expected_mechanism": "Removes suppressor coverage in proportion to local Cu growth velocity in the quasi-steady balance.",
            "known_interactions": [
                "deactivationRate x adsorptionStrength",
                "deactivationRate x activeDepositionRate",
                "deactivationRate x suppressedDepositionRate",
            ],
            "identifiability": "Coverage constrains a balance between adsorptionStrength and deactivationRate times velocity; morphology does not identify deactivationRate independently without external kinetic data.",
            "support": "The isolated rate-field controls exercised deactivationRate=0.25 only; no coefficient sweep or production DOE exists.",
            "confidence": "high for equation wiring; low for sensitivity and calibration",
        },
        {
            "id": "candidate_fill_active_deposition_rate",
            "name": "activeDepositionRate",
            "units": "simulation length per simulation time",
            "default": 1.0,
            "tested_range": [0.2],
            "current": 0.2,
            "expected_mechanism": "Sets the Cu growth velocity on an unsuppressed surface.",
            "known_interactions": [
                "active rate x process duration",
                "active rate x deactivationRate",
                "active rate x suppressed rate",
            ],
            "identifiability": "Overall growth rate is confounded with process duration, while its ratio to suppressedDepositionRate sets the modeled rate contrast.",
            "support": "The isolated rate-field controls exercised activeDepositionRate=0.2; an active rate below the suppressed rate is tested only as a rejected input.",
            "confidence": "high for limiting-rate behavior; low for physical calibration",
        },
        {
            "id": "candidate_fill_suppressed_deposition_rate",
            "name": "suppressedDepositionRate",
            "units": "simulation length per simulation time",
            "default": 0.01,
            "tested_range": [0.01],
            "current": 0.01,
            "expected_mechanism": "Sets residual Cu growth under complete suppressor coverage.",
            "known_interactions": [
                "suppressed rate x active rate",
                "suppressed rate x deactivationRate",
                "suppressed rate x process duration",
            ],
            "identifiability": "The suppressed-to-active rate ratio controls contrast, while absolute rates remain confounded with duration and the deactivation balance.",
            "support": "The isolated rate-field controls exercised suppressedDepositionRate=0.01; a larger-than-active value is tested only as a rejected input.",
            "confidence": "high for limiting-rate behavior; low for physical calibration",
        },
        {
            "id": "candidate_fill_plating_materials",
            "name": "platingMaterials",
            "units": "material enum list",
            "default": ["Material.Cu"],
            "tested_range": [
                ["Material.Cu"],
                ["registered CuSeed", "Material.Cu"],
                ["Material.Si", "Material.Cu"],
            ],
            "current": ["registered CuSeed", "Material.Cu"],
            "classification": "structural_choice",
            "expected_mechanism": "Gates positive growth to the electrically connected Cu seed and plated-Cu level sets while keeping dielectric and barrier surfaces stationary.",
            "known_interactions": [
                "material identity x explicit level-set order",
                "seed continuity x Cu handoff",
            ],
            "identifiability": "This is a material-stack contract, not a fitted kinetic coefficient; changing it changes which surfaces are allowed to plate.",
            "support": "Isolated seed-to-Cu handoff and dielectric-gate tests confirm the code path only; they do not establish a physical plating recipe.",
            "confidence": "high for the material gate; low for electrical seed realism",
        },
    ]
    for item in candidate_fill_controls:
        add(record(
            item["id"], "cu_fill",
            f"CopperSuppressionFillParams.{item['name']} / CopperSuppressionFill",
            item["name"], units=item["units"], default=item["default"],
            tested_range=item["tested_range"],
            current_best=qualification_setting(item["current"]),
            classification=item.get("classification", "model_coefficient"),
            implementation_status="candidate_extension_qualification_only",
            expected_mechanism=item["expected_mechanism"],
            metrics_affected=[
                "suppressor_flux",
                "equilibrium_coverage",
                "local_deposition_velocity",
                "bottom_to_field_velocity_ratio",
                "fill_topology",
                "overburden",
            ],
            known_interactions=item["known_interactions"],
            upstream_consequences="Requires a qualified full-domain geometry and an explicit continuous Cu-seed material level set.",
            downstream_consequences="Changes void closure, overburden, and the Cu topography inherited by CMP.",
            evidence_status="screened",
            supporting_experiment=f"{item['support']} Evidence is limited to test_copper_suppression_fill.py isolated controls; no production morphology DOE has accepted this parameter.",
            confidence=item["confidence"],
            range_provenance="Exact isolated-control values and the staged foundation manifest; no fab-calibrated range.",
            identifiability_coupling=item["identifiability"],
            staged_range=item.get("staged_range"),
            candidate_model="reduced quasi-steady suppressor-access proxy; not S-NDR, CEAC, or calibrated electrochemistry",
        ))

    candidate_cmp_controls = [
        (
            "candidate_cmp_stop_height", "stopHeight", "simulation height", 0.0,
            ["derived SiO2 stop top"], "structural_choice",
            "Sets the height below which only residual contact remains; it is derived from the incoming stop surface rather than optimized as an arbitrary plane.",
            ["endpoint", "stop_loss", "dish", "plug_loss"],
            ["stop height x incoming topography", "stop height x compliance length"],
        ),
        (
            "candidate_cmp_compliance_length", "complianceLength", "simulation length", 0.1,
            [0.1, 0.25], "model_coefficient",
            "Sets the vertical transition over which the height-dependent contact weight rises from residual to full contact.",
            ["raised_feature_preference", "dish", "endpoint_window"],
            ["compliance length x overburden", "compliance length x residual contact"],
        ),
        (
            "candidate_cmp_residual_contact", "residualContact", "fraction", 0.05,
            [0.05], "model_coefficient",
            "Retains a uniform removal fraction even at or below the stop plane.",
            ["post_endpoint_loss", "dish", "stop_erosion", "plug_loss"],
            ["residual contact x overpolish", "residual contact x material rate"],
        ),
        (
            "candidate_cmp_plated_cu_rate", "platedCuRemovalRate", "relative removal rate", 1.0,
            [1.0], "model_coefficient",
            "Defines the reference plated-Cu removal rate in the uncalibrated height-by-material law.",
            ["Cu_clear", "dish", "plug_loss"],
            ["Cu rate x duration", "Cu rate x compliance length"],
        ),
        (
            "candidate_cmp_seed_material", "cuSeedMaterial", "material enum", "Material.Undefined",
            ["registered CuSeed"], "structural_choice",
            "Identifies the distinct Cu-seed level set so seed clearing is not conflated with plated Cu.",
            ["seed_clear", "material_survival", "endpoint_sequence"],
            ["seed identity x material stack", "seed identity x serialization"],
        ),
        (
            "candidate_cmp_seed_rate", "cuSeedRemovalRate", "relative removal rate", 1.0,
            [0.8, 1.0], "model_coefficient",
            "Sets removal of the registered Cu-seed layer after plated-Cu field clear.",
            ["seed_clear", "endpoint_sequence", "plug_loss"],
            ["seed rate x seed thickness", "seed rate x overpolish"],
        ),
        (
            "candidate_cmp_tan_rate", "tantalumNitrideRemovalRate", "relative removal rate", 0.25,
            [0.25], "model_coefficient",
            "Sets TaN barrier removal relative to plated Cu.",
            ["barrier_clear", "endpoint_sequence", "stop_exposure"],
            ["TaN rate x barrier thickness", "TaN rate x overpolish"],
        ),
        (
            "candidate_cmp_sio2_rate", "siliconDioxideRemovalRate", "relative removal rate", 0.01,
            [0.01], "model_coefficient",
            "Sets SiO2 stop-layer erosion relative to plated Cu.",
            ["stop_erosion", "stop_retention", "field_planarity"],
            ["SiO2 rate x overpolish", "SiO2 rate x stop thickness"],
        ),
        (
            "candidate_cmp_si_rate", "siliconRemovalRate", "relative removal rate", 0.01,
            [0.005, 0.01], "model_coefficient",
            "Sets silicon loss if the protected stack is breached.",
            ["substrate_loss", "hard_failure"],
            ["Si rate x stop breach", "Si rate x overpolish"],
        ),
    ]
    for (
        id, name, units, default, tested_range, classification, mechanism,
        metrics, interactions,
    ) in candidate_cmp_controls:
        add(record(
            id,
            "cmp",
            f"HeightMaterialCMPParams.{name} / HeightMaterialCMP",
            name,
            units=units,
            default=default,
            tested_range=tested_range,
            current_best=qualification_setting(
                "derived_from_stack" if name == "stopHeight" else tested_range[-1]
            ),
            classification=classification,
            implementation_status="candidate_extension_qualification_only",
            expected_mechanism=mechanism,
            metrics_affected=metrics,
            known_interactions=interactions,
            upstream_consequences="Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.",
            downstream_consequences="Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.",
            evidence_status="screened",
            supporting_experiment="Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.",
            confidence="high for API wiring; low for physical calibration",
            range_provenance="Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.",
            runtime_owner="CMP exact binary d42733ed7b3355c9a8a94b45ce32b1d9536b6be9e7ff33165f172a08b49e54ef",
            candidate_model="uncalibrated local height-by-material morphology abstraction; no pad-pressure physics",
        ))

    add(record(
        "candidate_cmp_overpolish_dose",
        "cmp",
        "foundation_cmp_qualification overpolish_doses / Process.duration",
        "post-endpoint overpolish dose",
        units="simulation time/dose",
        default=0.0,
        tested_range=[0.0, 0.0025, 0.005, 0.010, 0.020, 0.030],
        current_best=None,
        classification="recipe_knob",
        implementation_status="controlled_qualification_only",
        expected_mechanism="Advances the selected removal law beyond a named field-clear event to expose residual-metal versus erosion and plug-loss windows.",
        metrics_affected=["field_clear", "dish", "stop_erosion", "plug_height_loss", "plug_area_loss"],
        known_interactions=["overpolish x every material rate", "overpolish x incoming overburden", "overpolish x compliance length"],
        upstream_consequences="Requires a named endpoint on an accepted incoming Cu topography.",
        downstream_consequences="Excess dose can consume the stop, plug, liner, or substrate and is a hard failure.",
        evidence_status="screened",
        supporting_experiment="Controlled analytic-stack qualification ladder; product limits remain unset, so no best value exists.",
        confidence="medium for model response; low for physical time mapping",
        range_provenance="Predeclared numerical qualification ladder, not a production overpolish range.",
    ))

    for id, name, metric in (
        ("cmp_minimum_stop_retained_spec", "minimum retained stop thickness", "stop_retained_thickness"),
        ("cmp_maximum_stop_erosion_spec", "maximum stop erosion", "stop_erosion"),
        ("cmp_maximum_plug_height_loss_spec", "maximum plug-height loss", "plug_height_loss"),
        ("cmp_maximum_plug_area_loss_spec", "maximum plug-area loss fraction", "plug_area_loss_fraction"),
    ):
        add(record(
            id,
            "cmp",
            "program.md / foundation_cmp_qualification.REQUIRED_RESEARCH_SURVIVAL_THRESHOLDS",
            name,
            units="simulation length or fraction",
            default=None,
            tested_range=None,
            current_best=None,
            classification="product_specification",
            implementation_status="required_unset_blocks_cmp_doe",
            expected_mechanism="Defines the functional survival margin that CMP must preserve after field-metal clear.",
            metrics_affected=[metric, "cmp_target_pass"],
            known_interactions=["survival limit x endpoint", "survival limit x incoming stack", "survival limit x grid resolution"],
            upstream_consequences="Requires product or reliability provenance; it cannot be inferred from a favorable simulation.",
            downstream_consequences="Until declared, quantitative CMP survival and the complete traveler remain blocked.",
            evidence_status="untested",
            supporting_experiment="The metric and boundary tests exist, but the authoritative limit is deliberately None.",
            confidence="high that the limit is required; absent for its numeric value",
            range_provenance="No declared value. A provenance-backed study limit is required before launch.",
        ))

    add(record(
        "geometry_qualification_tier", "cross_process", "program.md geometry tiers",
        "continuity, nominal HBM, or high-AR stress geometry",
        units="categorical geometry tier", default="continuity",
        tested_range=["continuity"],
        current_best=qualification_setting("continuity"),
        classification="structural_choice",
        implementation_status="continuity_wired_nominal_and_stress_required",
        expected_mechanism="Changes feature width, depth, aspect ratio, transport access, layer conformality, fill closure, and runtime without changing the declared tier definitions.",
        metrics_affected=[
            "aspect_ratio", "cd_profile", "layer_conformality",
            "void_topology", "overburden", "process_window",
        ],
        known_interactions=[
            "geometry tier x every transport coefficient",
            "geometry tier x grid resolution",
            "geometry tier x 2D/3D dimensionality",
        ],
        upstream_consequences="The selected pattern/etch geometry defines the incoming domain for every film and fill model.",
        downstream_consequences="A result on the continuity tier cannot substitute for the required nominal-HBM and high-AR challenges.",
        evidence_status="boundary-limited",
        supporting_experiment="The continuity tier is exercised by foundation controls. Nominal HBM and high-AR stress tiers are declared in program.md but have not yet been executed with the candidate fill model.",
        confidence="high for declared geometry; low beyond the tested continuity tier",
        range_provenance="program.md fixes the three non-interpolated qualification tiers; they are structural challenges, not a recipe sweep.",
        declared_levels={
            "continuity": {"width": 0.30, "depth": 1.25, "aspect_ratio": 4.17},
            "nominal_hbm": {"width": 0.30, "depth": 3.00, "aspect_ratio": 10.0},
            "high_ar_stress": {"width": 0.18, "depth": 3.00, "aspect_ratio": 16.7},
        },
    ))

    # Fixed or available controls on the API models actually used by wrappers.
    api_controls = [
        ("single_particle_source_exponent", "liner", "SingleParticleProcess.sourceExponent", "dimensionless exponent", 1.0, "Controls the source angular distribution for liner transport.", ["liner_conformality"], "screened", "Legacy 1/100/1000 screen reported no validated effect."),
        ("single_particle_mask_materials", "liner/bosch_etch", "SingleParticleProcess.maskMaterial(s)", "material enum/list", "Undefined for liner; Mask for polymer punch-through", "Excludes declared materials from particle-process motion.", ["mask_survival", "layer_selectivity"], "confirmed", "Direct wrapper and API inspection."),
        ("single_particle_material_rates", "liner", "SingleParticleProcess.materialRates", "material-to-rate map", None, "Allows material-dependent deposition/etch rates.", ["layer_thickness", "material_survival"], "untested", "API available but not wired."),
        ("ion_theta_r_max", "bosch_etch", "MultiParticleProcess.addIonParticle(thetaRMax)", "degrees", 90.0, "Sets the upper angle of the ion sticking transition.", ["reflected_ion_flux", "cd_profile"], "untested", "API default only."),
        ("ion_min_angle", "bosch_etch", "MultiParticleProcess.addIonParticle(minAngle)", "degrees", 80.0, "Sets the minimum reflection angle in the ion model.", ["reflected_ion_flux", "bottom_shape"], "untested", "API default only."),
        ("ion_b_sp", "bosch_etch", "MultiParticleProcess.addIonParticle(B_sp)", "dimensionless yield coefficient", -1.0, "Controls the angular sputtering-yield term.", ["ion_removal", "wall_shape"], "untested", "API default only."),
        ("ion_mean_energy", "bosch_etch", "MultiParticleProcess.addIonParticle(meanEnergy)", "model energy", 0.0, "Sets mean initial ion energy when the energy model is enabled.", ["ion_removal", "reflection_energy"], "untested", "API default only; current rate law does not calibrate energy."),
        ("ion_sigma_energy", "bosch_etch", "MultiParticleProcess.addIonParticle(sigmaEnergy)", "model energy", 0.0, "Sets ion-energy spread.", ["ion_removal_variance"], "untested", "API default only."),
        ("ion_threshold_energy", "bosch_etch", "MultiParticleProcess.addIonParticle(thresholdEnergy)", "model energy", 0.0, "Sets the sputtering threshold energy.", ["ion_removal", "selectivity"], "untested", "API default only."),
        ("ion_inflect_angle", "bosch_etch", "MultiParticleProcess.addIonParticle(inflectAngle)", "degrees", 0.0, "Sets the reflected-ion energy-law inflection angle.", ["reflection_energy", "bottom_shape"], "untested", "API default only."),
        ("ion_energy_exponent_n", "bosch_etch", "MultiParticleProcess.addIonParticle(n)", "dimensionless exponent", 1, "Shapes the reflected-ion energy-reduction curve.", ["reflection_energy", "wall_shape"], "untested", "API default only."),
        ("neutral_material_sticking", "bosch_etch", "MultiParticleProcess.addNeutralParticle(materialSticking)", "material-to-probability map", None, "Allows different neutral sticking probabilities on each material.", ["etch_selectivity", "polymer_transport"], "untested", "API available but current wrapper uses one scalar."),
        ("direction_vector", "barrier_seed/cu_fill", "DirectionalProcess.direction", "unit vector", [0.0, -1.0, 0.0], "Sets the geometric deposition direction.", ["conformality", "bottom_access", "pinch_off"], "rejected", "Legacy 0-30 degree tilt claim was retracted after shared-geometry control."),
        ("directional_mask_material", "barrier_seed/cu_fill", "DirectionalProcess.maskMaterial(s)", "material enum/list", "Material.Mask", "Prevents geometric motion on declared mask materials.", ["mask_survival", "field_deposition"], "screened", "API default used by legacy wrapper."),
        ("directional_visibility", "barrier_seed/cu_fill", "DirectionalProcess.calculateVisibility", "boolean", True, "Enables line-of-sight visibility in the geometric deposition model.", ["shadowing", "conformality"], "rejected", "Legacy True/False screen showed no validated effect in the single-via 2D domain."),
        ("directional_material_rates", "barrier_seed/cu_fill", "DirectionalProcess.materialRates / RateSet", "material-to-(directional,isotropic) map", None, "Allows material-specific geometric velocity pairs.", ["layer_selectivity", "material_survival"], "untested", "API available but not wired."),
        ("process_duration", "cross_process", "Process.duration", "simulation time", "step-specific", "Multiplies the model velocity/flux response.", ["all_morphology_ctqs"], "confirmed", "Direct wrapper inspection; many wrappers fix duration to 1.0."),
        ("flux_engine_type", "cross_process", "Process.setFluxEngineType", "enum", "AUTO", "Chooses CPU/GPU/automatic flux execution.", ["numerical_reproducibility", "runtime"], "untested", "AUTO is exercised by the isolated candidate rate-field controls. CPU_DISK is explicitly wired in the staged trajectory runner but has not yet been compared or accepted."),
    ]
    for id, step, owner, units, default, mechanism, metrics, status, support in api_controls:
        layer_source = id == "single_particle_source_exponent"
        add(record(
            id, step, owner, id.replace("_", " "), units=units,
            default=default, tested_range=(
                [1.0, 100.0, 1000.0] if layer_source else
                {"isolated_rate_field": ["AUTO"], "staged_trajectory": ["CPU_DISK"]}
                if id == "flux_engine_type" else None
            ),
            current_best=(
                qualification_setting("CPU_DISK")
                if id == "flux_engine_type" else None
            ),
            classification="numerical_control" if id in {"flux_engine_type"} else "model_coefficient",
            implementation_status=(
                "wired_model_acceptance_candidate" if layer_source else
                "wired_candidate_manifest" if id == "flux_engine_type" else
                "fixed" if status != "untested" else "api_available_unwired"
            ),
            expected_mechanism=mechanism, metrics_affected=metrics,
            known_interactions=["Must be checked against grid, dimensionality, and the owning process dose."],
            upstream_consequences="No direct upstream effect.",
            downstream_consequences="Any changed morphology propagates downstream.",
            evidence_status=status, supporting_experiment=support,
            confidence="medium" if status != "untested" else "low",
            range_provenance="API default or legacy model-sensitivity screen; no fab calibration.",
        ))

    # Advanced numerical parameter packs are listed individually so a future
    # campaign cannot change a solver default without leaving an audit trail.
    parameter_defaults = {
        "RayTracingParameters": {
            "diskRadius": 0.0, "ignoreFluxBoundaries": False,
            "maxBoundaryHits": 1000, "maxReflections": 4294967295,
            "minNodeDistanceFactor": 0.05, "normalizationType": 0,
            "raysPerPoint": 1000, "rngSeed": 0, "smoothingNeighbors": 1,
            "useRandomSeeds": True,
        },
        "AdvectionParameters": {
            "adaptiveTimeStepSubdivisions": 20, "adaptiveTimeStepping": False,
            "calculateIntermediateVelocities": False, "checkDissipation": True,
            "dissipationAlpha": 1.0, "ignoreVoids": False,
            "integrationScheme": 0, "spatialScheme": 0,
            "temporalScheme": 0, "timeStepRatio": 0.4999,
            "velocityOutput": False,
        },
        "CoverageParameters": {
            "initialized": False, "maxIterations": 4294967295,
            "tolerance": 0.0,
        },
        "AtomicLayerProcessParameters": {
            "coverageTimeStep": 1.0, "numCycles": 1,
            "pulseTime": 1.0, "purgePulseTime": 0.0,
            "purgeTimeStep": 1.0,
        },
    }
    numerical_effect = {
        "raysPerPoint": "Monte Carlo sampling density and variance",
        "rngSeed": "reproducible random stream",
        "useRandomSeeds": "deterministic versus automatically randomized streams",
        "maxReflections": "maximum particle reflection history",
        "maxBoundaryHits": "maximum boundary interactions",
        "timeStepRatio": "level-set advection timestep size",
        "adaptiveTimeStepping": "adaptive versus fixed advection steps",
        "ignoreVoids": "whether enclosed void regions participate in advection",
        "tolerance": "coverage-iteration convergence threshold",
        "maxIterations": "coverage-iteration ceiling",
        "coverageTimeStep": "surface-coverage update interval during an atomic-layer pulse",
        "numCycles": "number of repeated atomic-layer pulse cycles",
        "pulseTime": "precursor exposure duration per atomic-layer cycle",
        "purgePulseTime": "desorption/purge interval after an atomic-layer pulse",
        "purgeTimeStep": "surface-coverage update interval during purge",
    }
    candidate_ray_settings = {
        "diskRadius": {
            "current": 0.0,
            "tested": {"isolated_rate_field": [0.0], "staged_trajectory": [0.0]},
        },
        "ignoreFluxBoundaries": {
            "current": False,
            "tested": {"isolated_rate_field": [False], "staged_trajectory": [False]},
        },
        "maxBoundaryHits": {
            "current": 1000,
            "tested": {"isolated_rate_field": [1000], "staged_trajectory": [1000]},
        },
        "maxReflections": {
            "current": 100,
            "tested": {
                "isolated_rate_field": [4294967295],
                "staged_trajectory": [100],
            },
        },
        "minNodeDistanceFactor": {
            "current": 0.05,
            "tested": {"isolated_rate_field": [0.05], "staged_trajectory": [0.05]},
        },
        "normalizationType": {
            "current": "NormalizationType.SOURCE (0)",
            "tested": {
                "isolated_rate_field": ["SOURCE (default)"],
                "staged_trajectory": ["SOURCE (explicit)"],
            },
        },
        "raysPerPoint": {
            "current": 1000,
            "tested": {
                "isolated_rate_field": [500, 1000, 2000],
                "staged_trajectory": [1000],
            },
        },
        "rngSeed": {
            "current": "design seed 91000 + checkpoint index",
            "tested": {
                "isolated_rate_field": [17, 19, 731, 811],
                "staged_trajectory": ["91000 + checkpoint index"],
            },
        },
        "smoothingNeighbors": {
            "current": 1,
            "tested": {"isolated_rate_field": [1], "staged_trajectory": [1]},
        },
        "useRandomSeeds": {
            "current": False,
            "tested": {"isolated_rate_field": [False], "staged_trajectory": [False]},
        },
    }
    for pack, defaults in parameter_defaults.items():
        for name, default in defaults.items():
            candidate_ray = (
                candidate_ray_settings.get(name)
                if pack == "RayTracingParameters" else None
            )
            required_void_guard = (
                pack == "AdvectionParameters" and name == "ignoreVoids"
            )
            unsafe_ald_purge = (
                pack == "AtomicLayerProcessParameters"
                and name == "purgePulseTime"
            )
            add(record(
                f"api_{pack}_{name}",
                "cu_fill" if required_void_guard else
                "liner/barrier_seed" if pack == "AtomicLayerProcessParameters" else
                "cross_process",
                f"{pack}.{name}", name,
                units="API-specific numerical setting", default=default,
                tested_range=(
                    candidate_ray["tested"] if candidate_ray else
                    [False, True] if required_void_guard else
                    ["explicit fixed seeds"] if name == "rngSeed" else
                    [False, True] if name == "useRandomSeeds" else None
                ),
                current_best=(
                    qualification_setting(candidate_ray["current"])
                    if candidate_ray else
                    {
                        "value": True,
                        "status": "mandatory_validity_guard",
                        "source": "test_copper_suppression_fill.py sealed-void control",
                    }
                    if required_void_guard else None
                ),
                classification="numerical_control",
                implementation_status=(
                    "required_candidate_void_guard" if required_void_guard else
                    "api_available_native_preflight_required"
                    if pack == "AtomicLayerProcessParameters" else
                    "wired_candidate_manifest" if candidate_ray else
                    "wired" if name in {"raysPerPoint", "rngSeed", "useRandomSeeds"} else
                    "api_available_unwired"
                ),
                expected_mechanism=(
                    "Freezes inaccessible enclosed-void interfaces during advection so trapped voids cannot spuriously heal from zero-flux reactivation."
                    if required_void_guard else
                    numerical_effect.get(
                        name, f"Controls the {name} numerical behavior of {pack}."
                    )
                ),
                metrics_affected=(
                    ["closed_void_count", "closed_void_area", "void_topology", "target_pass"]
                    if required_void_guard else
                    ["numerical_convergence", "runtime", "all geometry outputs if changed"]
                ),
                known_interactions=(
                    ["void accessibility", "local suppressor flux", "topology checkpointing"]
                    if required_void_guard else
                    ["grid_delta", "process model", "geometry complexity"]
                ),
                upstream_consequences="No physical upstream consequence; may alter numerical realization.",
                downstream_consequences=(
                    "Without the guard, false void healing can invalidate fill acceptance and the CMP input geometry."
                    if required_void_guard else
                    "Numerical bias or variance propagates through every later geometry."
                ),
                evidence_status=(
                    "confirmed" if required_void_guard else
                    "boundary-limited" if unsafe_ald_purge else
                    "screened" if pack == "AtomicLayerProcessParameters" else
                    "untested" if candidate_ray and name == "maxReflections" else
                    "screened" if candidate_ray else
                    "screened" if name in {"raysPerPoint", "rngSeed", "useRandomSeeds"} else
                    "untested"
                ),
                supporting_experiment=(
                    "A controlled sealed void shrank when ignoreVoids=false and was preserved exactly when true; true is mandatory for candidate-fill execution."
                    if required_void_guard else
                    "A subprocess preflight using the installed ViennaPS 4.6.1 SingleParticleALD completed with purgePulseTime=0, while enabling a 0.05 purge pulse exited with native signal 11 (shell status 139); purge-enabled ALD is blocked pending isolation or an upstream fix."
                    if unsafe_ald_purge else
                    "Installed ViennaPS 4.6.1 ALD parameter object was audited; a no-purge one- and ten-cycle full-width smoke path completed, but this does not qualify ALD morphology or physical coefficients."
                    if pack == "AtomicLayerProcessParameters" else
                    "Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study."
                    if candidate_ray else
                    "Foundation fixed-seed ray/thread controls." if name in {"raysPerPoint", "rngSeed", "useRandomSeeds"}
                    else "Captured from installed ViennaPS 4.6.1 defaults; not independently varied."
                ),
                confidence=(
                    "high for the void-preservation guard"
                    if required_void_guard else
                    "high for the observed native failure; low for its root cause"
                    if unsafe_ald_purge else
                    "high for API wiring; low for ALD model acceptance"
                    if pack == "AtomicLayerProcessParameters" else
                    "high for wiring; low for candidate-fill sensitivity or convergence"
                    if candidate_ray else
                    "high for default capture; low for sensitivity unless tested"
                ),
                range_provenance=(
                    "Exact false/true sealed-void control; true is a validity guard, not an optimization factor."
                    if required_void_guard else
                    "Default parameter capture plus a bounded native smoke test; no ALD DOE range is authorized."
                    if pack == "AtomicLayerProcessParameters" else
                    "Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence."
                    if candidate_ray else
                    "Installed API default; any future range requires numerical-convergence evidence."
                ),
            ))

    # Relevant installed alternative models. Their controls are model
    # coefficients until calibrated; availability does not make them fab knobs.
    alternative_controls = [
        ("teos_p1_sticking", "liner", "TEOSDeposition.stickingProbabilityP1", "probability", None, "Primary TEOS precursor sticking."),
        ("teos_p1_rate", "liner", "TEOSDeposition.rateP1", "model deposition rate", None, "Primary TEOS contribution rate."),
        ("teos_p1_order", "liner", "TEOSDeposition.orderP1", "reaction order", None, "Primary TEOS reaction-order response."),
        ("teos_p2_sticking", "liner", "TEOSDeposition.stickingProbabilityP2", "probability", 0.0, "Secondary TEOS precursor sticking."),
        ("teos_p2_rate", "liner", "TEOSDeposition.rateP2", "model deposition rate", 0.0, "Secondary TEOS contribution rate."),
        ("teos_p2_order", "liner", "TEOSDeposition.orderP2", "reaction order", 0.0, "Secondary TEOS reaction-order response."),
        ("teos_pecvd_radical_sticking", "liner", "TEOSPECVD.stickingProbabilityRadical", "probability", None, "Radical sticking and lower-via transport."),
        ("teos_pecvd_radical_rate", "liner", "TEOSPECVD.depositionRateRadical", "model deposition rate", None, "Radical deposition contribution."),
        ("teos_pecvd_ion_rate", "liner", "TEOSPECVD.depositionRateIon", "model deposition rate", None, "Ion-assisted deposition contribution."),
        ("teos_pecvd_ion_exponent", "liner", "TEOSPECVD.exponentIon", "dimensionless exponent", None, "Ion angular collimation."),
        ("teos_pecvd_ion_sticking", "liner", "TEOSPECVD.stickingProbabilityIon", "probability", 1.0, "Ion sticking probability."),
        ("teos_pecvd_radical_order", "liner", "TEOSPECVD.reactionOrderRadical", "reaction order", 1.0, "Radical reaction order."),
        ("teos_pecvd_ion_order", "liner", "TEOSPECVD.reactionOrderIon", "reaction order", 1.0, "Ion reaction order."),
        ("teos_pecvd_min_ion_angle", "liner", "TEOSPECVD.minAngleIon", "degrees", 0.0, "Minimum ion-angle control."),
        ("ald_sticking", "liner/barrier_seed", "SingleParticleALDParams.stickingProbability", "probability", 1.0, "Adsorption probability per ALD exposure."),
        ("ald_growth_per_cycle", "liner/barrier_seed", "SingleParticleALDParams.growthPerCycle", "simulation length/cycle", 0.0, "Growth increment per ALD cycle."),
        ("ald_incoming_flux", "liner/barrier_seed", "SingleParticleALDParams.incomingFlux", "model flux", 0.0, "Incoming precursor flux."),
        ("ald_evaporation_flux", "liner/barrier_seed", "SingleParticleALDParams.evaporationFlux", "model flux", 0.0, "Desorption/evaporation contribution."),
        ("ald_coverage_diffusion", "liner/barrier_seed", "SingleParticleALDParams.coverageDiffusionCoefficient", "model diffusivity", 0.0, "Surface redistribution of adsorbed coverage."),
        ("ald_mean_free_path", "liner/barrier_seed", "SingleParticleALDParams.gasMeanFreePath", "simulation length", -1.0, "Gas-phase transport length scale."),
        ("ald_s0", "liner/barrier_seed", "SingleParticleALDParams.s0", "dimensionless", 0.0, "Coverage-dependent sticking coefficient."),
        ("neutral_incoming_flux", "liner/cu_fill", "NeutralTransportParameters.incomingFlux", "model flux", 1.0, "Incoming neutral species supply."),
        ("neutral_zero_coverage_sticking", "liner/cu_fill", "NeutralTransportParameters.zeroCoverageSticking", "probability", 0.1, "Sticking on an uncovered surface."),
        ("neutral_desorption_rate", "liner/cu_fill", "NeutralTransportParameters.desorptionRate", "inverse simulation time", 0.0, "Adsorbate loss from the surface."),
        ("neutral_surface_diffusion", "liner/cu_fill", "NeutralTransportParameters.surfaceDiffusionCoefficient", "model diffusivity", 0.0, "Surface transport of adsorbate coverage."),
        ("neutral_surface_site_density", "liner/cu_fill", "NeutralTransportParameters.surfaceSiteDensity", "model sites/area", 0.0000166, "Coverage capacity of the surface."),
        ("neutral_coverage_timestep", "liner/cu_fill", "NeutralTransportParameters.coverageTimeStep", "simulation time", 1.0, "Coverage update interval."),
        ("neutral_source_power", "liner/cu_fill", "NeutralTransportParameters.sourceDistributionPower", "dimensionless exponent", 1.0, "Angular source distribution."),
        ("neutral_steady_state", "liner/cu_fill", "NeutralTransportParameters.useSteadyStateCoverage", "boolean", True, "Steady-state versus transient surface coverage."),
        ("surface_diffusion_radius", "cu_fill", "SurfaceDiffusionParameters.radius", "simulation length", 0.0, "Neighborhood radius for surface-coverage diffusion."),
        ("surface_diffusion_neighbors", "cu_fill", "SurfaceDiffusionParameters.kNeighbors", "count", 16, "Neighbor count for surface diffusion."),
        ("surface_diffusion_normal_cutoff", "cu_fill", "SurfaceDiffusionParameters.normalCutoff", "dimensionless", 0.25, "Excludes strongly misaligned surface neighbors."),
        ("surface_diffusion_sigma_normal", "cu_fill", "SurfaceDiffusionParameters.sigmaNormal", "dimensionless", 0.35, "Normal-alignment weighting width."),
        ("surface_diffusion_stability", "cu_fill", "SurfaceDiffusionParameters.stabilityFactor", "dimensionless", 1.0, "Numerical stability scale for diffusion."),
        ("csv_rates_file", "cmp", "CSVFileProcess.ratesFile", "file path", None, "Supplies a spatial velocity field for a phenomenological removal control."),
        ("csv_direction", "cmp", "CSVFileProcess.direction", "unit vector", None, "Defines directional orientation of the imported velocity field."),
        ("csv_offset", "cmp", "CSVFileProcess.offset", "simulation length vector", None, "Aligns imported rates to geometry coordinates."),
        ("csv_isotropic_component", "cmp", "CSVFileProcess.isotropicComponent", "model velocity multiplier", 0.0, "Adds isotropic removal to the imported field."),
        ("csv_directional_component", "cmp", "CSVFileProcess.directionalComponent", "model velocity multiplier", 1.0, "Scales directional removal from the imported field."),
        ("csv_mask_materials", "cmp", "CSVFileProcess.maskMaterials", "material list", ["Material.Mask"], "Protects declared materials from the imported removal field."),
        ("csv_visibility", "cmp", "CSVFileProcess.calculateVisibility", "boolean", True, "Applies line-of-sight visibility to the field."),
        ("csv_custom_interpolator", "cmp", "CSVFileProcess.setCustomInterpolator", "callable", None, "Maps coordinates/rates for a custom phenomenological contact hypothesis."),
    ]
    ald_smoke_values = {
        "ald_sticking": [0.00005],
        "ald_growth_per_cycle": [0.004],
        "ald_incoming_flux": [2000000.0],
        "ald_evaporation_flux": [2.5],
        "ald_coverage_diffusion": [0.0],
        "ald_mean_free_path": [1519.87],
        "ald_s0": [3.36],
    }
    for id, step, owner, units, default, mechanism in alternative_controls:
        wired_teos = {
            "teos_p1_sticking": [0.01],
            "teos_p1_rate": [0.04],
            "teos_p1_order": [1.0],
        }.get(id)
        ald_smoke = ald_smoke_values.get(id)
        add(record(
            id, step, owner, id.replace("_", " "), units=units,
            default=default, tested_range=(
                wired_teos if wired_teos is not None else ald_smoke
            ), classification="model_coefficient",
            implementation_status=(
                "wired_model_acceptance_candidate"
                if wired_teos is not None else "api_available_unwired"
                if ald_smoke is None else "api_available_native_smoke_only"
            ),
            expected_mechanism=mechanism,
            metrics_affected=["local deposition/removal rate", "material morphology", "owning-step CTQs"],
            known_interactions=["geometry", "process duration", "grid_delta", "other coefficients in the same model"],
            upstream_consequences="Requires a qualified incoming geometry.",
            downstream_consequences="Any local thickness or topology change propagates downstream.",
            evidence_status=(
                "screened"
                if wired_teos is not None or ald_smoke is not None else "untested"
            ),
            supporting_experiment=(
                "test_layer_process_models.py exercised the installed coverage-coupled TEOS model on an analytic full-width via and showed it is not numerically equivalent to the generic single-particle model."
                if wired_teos is not None else
                "A no-purge native SingleParticleALD smoke path completed on an analytic full-width via. A documented-style nonzero purge pulse crashed the native process, so these coefficients are not accepted for a campaign."
                if ald_smoke is not None else
                "Installed ViennaPS 4.6.1 API inspection only."
            ),
            confidence="high for API availability; low for physical applicability",
            range_provenance=(
                "Exact diagnostic value only; model-acceptance range has not yet been frozen."
                if wired_teos is not None else
                "Exact no-purge smoke value only; no ALD DOE range is authorized."
                if ald_smoke is not None else
                "No range assigned. Calibrate or literature-bound before DOE inclusion."
            ),
        ))

    # Real fab controls named by the supplied process reference and primary
    # mechanism literature. They remain visible even when ViennaPS cannot yet
    # consume them; absence from code is not evidence of irrelevance.
    physical_knobs = [
        ("litho_exposure_dose", "pattern", "exposure dose", "energy/area", "Changes the resist latent image and developed CD."),
        ("litho_focus_offset", "pattern", "focus offset", "length", "Changes aerial-image contrast and resist profile."),
        ("litho_mask_bias", "pattern", "reticle/mask CD bias", "length", "Offsets printed opening CD."),
        ("litho_resist_thickness", "pattern", "photoresist coat thickness", "length", "Sets etch-mask budget and developed aspect ratio."),
        ("litho_bake_conditions", "pattern", "soft/post-exposure bake", "temperature and time", "Changes resist chemistry, diffusion, and profile."),
        ("litho_develop_conditions", "pattern", "developer chemistry/time", "chemistry and time", "Controls resist dissolution, CD, and sidewall angle."),
        ("litho_overlay", "pattern", "TSV overlay", "length", "Positions the TSV relative to device features."),
        ("drie_sf6_flow", "bosch_etch", "SF6 flow", "sccm", "Changes fluorine supply and silicon chemical etch rate."),
        ("drie_c4f8_flow", "bosch_etch", "C4F8 flow", "sccm", "Changes fluorocarbon passivation supply."),
        ("drie_chamber_pressure", "bosch_etch", "chamber pressure", "Pa or mTorr", "Changes mean free path, angular transport, and radical density."),
        ("drie_source_power", "bosch_etch", "ICP/source power", "W", "Changes plasma density and reactive-species flux."),
        ("drie_bias_power", "bosch_etch", "platen RF bias/power", "W or V", "Changes vertical ion energy and passivation punch-through."),
        ("drie_wafer_temperature", "bosch_etch", "wafer/chuck temperature", "degC", "Changes passivation stability and reaction rates."),
        ("drie_physical_etch_time", "bosch_etch", "SF6 phase duration", "s", "Controls etch dose per Bosch cycle."),
        ("drie_physical_passivation_time", "bosch_etch", "C4F8 phase duration", "s", "Controls passivation dose per cycle."),
        ("drie_switching_transient", "bosch_etch", "gas switching/purge time", "s", "Changes overlap and transient chemistry between cycle phases."),
        ("liner_teos_flow", "liner", "TEOS flow", "sccm or mass flow", "Changes precursor supply for oxide growth."),
        ("liner_ozone_flow", "liner", "O3/oxidant flow", "sccm", "Changes oxidation kinetics and film quality."),
        ("liner_temperature", "liner", "liner deposition temperature", "degC", "Changes reaction rate, surface mobility, and film density."),
        ("liner_pressure", "liner", "liner chamber pressure", "Pa or Torr", "Changes transport and conformality."),
        ("liner_deposition_time", "liner", "liner deposition time", "s", "Controls deposited thickness for fixed chemistry."),
        ("liner_chemistry_choice", "liner", "liner process/chemistry", "categorical", "Selects SACVD, PECVD, ALD, or another physical mechanism.", "structural_choice"),
        ("barrier_target_material", "barrier_seed", "barrier/adhesion material stack", "categorical", "Selects TaN/Ta or another diffusion/adhesion stack.", "structural_choice"),
        ("barrier_ar_pressure", "barrier_seed", "Ar flow/pressure", "sccm and Pa", "Changes sputter transport and scattering."),
        ("barrier_n2_flow", "barrier_seed", "N2 reactive-sputter flow", "sccm", "Changes TaN formation and composition."),
        ("barrier_target_power", "barrier_seed", "sputter target power", "W", "Changes metal flux and ionization."),
        ("barrier_substrate_bias", "barrier_seed", "substrate bias", "V", "Steers ionized metal into the via."),
        ("barrier_temperature", "barrier_seed", "substrate temperature", "degC", "Changes adhesion, mobility, and film properties."),
        ("barrier_deposition_time", "barrier_seed", "barrier/seed deposition times", "s per material", "Controls each distinct layer thickness."),
        ("fill_current_density", "cu_fill", "plating current density", "A/area", "Sets electrochemical Cu deposition rate."),
        ("fill_current_waveform", "cu_fill", "plating current waveform", "current versus time", "Controls initiation, bottom-up acceleration, and bulk fill."),
        ("fill_total_charge", "cu_fill", "plated charge/time", "C/area or s", "Sets total Cu inventory."),
        ("fill_copper_sulfate", "cu_fill", "CuSO4 concentration", "mol/L", "Sets available Cu-ion concentration."),
        ("fill_sulfuric_acid", "cu_fill", "H2SO4 concentration", "mol/L", "Controls electrolyte conductivity and kinetics."),
        ("fill_chloride", "cu_fill", "chloride concentration", "mol/L", "Couples suppressor/accelerator adsorption chemistry."),
        ("fill_suppressor", "cu_fill", "suppressor concentration", "mol/L or ppm", "Inhibits deposition, especially near the field/mouth."),
        ("fill_accelerator", "cu_fill", "accelerator concentration", "mol/L or ppm", "Promotes bottom/corner growth through coverage-dependent kinetics."),
        ("fill_leveler", "cu_fill", "leveler concentration", "mol/L or ppm", "Suppresses overfill peaks and field growth."),
        ("fill_bath_temperature", "cu_fill", "electrolyte temperature", "degC", "Changes transport, adsorption, and electrochemical kinetics."),
        ("fill_agitation", "cu_fill", "wafer rotation/agitation", "rpm or flow", "Changes boundary-layer transport into the via."),
        ("cmp_downforce", "cmp", "polish downforce/pressure", "Pa", "Changes local contact pressure and material-removal rate."),
        ("cmp_platen_speed", "cmp", "platen speed", "rpm", "Changes relative velocity in the Preston-like removal response."),
        ("cmp_carrier_speed", "cmp", "carrier speed", "rpm", "Changes relative velocity and within-wafer uniformity."),
        ("cmp_slurry_flow", "cmp", "slurry flow", "volume/time", "Changes reactant/abrasive delivery."),
        ("cmp_slurry_chemistry", "cmp", "slurry abrasive/oxidizer chemistry", "categorical/composition", "Controls material reaction and removal selectivity.", "structural_choice"),
        ("cmp_pad_choice", "cmp", "pad material/condition", "categorical", "Controls contact compliance, roughness, and pressure distribution.", "structural_choice"),
        ("cmp_selectivity", "cmp", "Cu/barrier/dielectric selectivity", "rate ratios", "Sets relative removal of the explicit material stack."),
        ("cmp_endpoint_signal", "cmp", "endpoint criterion", "signal threshold", "Detects first field-Cu clear."),
        ("cmp_overpolish_delay", "cmp", "post-endpoint overpolish", "s or fraction", "Controls residual Cu clearance versus dish/erosion."),
        ("cmp_temperature", "cmp", "pad/wafer/slurry temperature", "degC", "Changes chemical kinetics and pad response."),
    ]
    physical_metric_map = {
        "pattern": ["opening_cd", "mask_profile", "pattern_validity"],
        "bosch_etch": ["depth", "cd_profile", "bow", "scallop", "mask_remaining"],
        "liner": ["local_thickness", "conformality", "continuity", "aperture"],
        "barrier_seed": ["barrier_thickness", "seed_thickness", "continuity", "aperture"],
        "cu_fill": ["void_topology", "fill_height", "overburden", "pinch_off"],
        "cmp": ["field_clear", "dish", "erosion", "material_survival"],
    }
    for item in physical_knobs:
        id, step, name, units, mechanism, *classification = item
        add(record(
            id, step, "physical process; unsupported by current wrapper", name,
            units=units, default=None, tested_range=None, current_best=None,
            classification=classification[0] if classification else "recipe_knob",
            implementation_status="unsupported_physical",
            expected_mechanism=mechanism,
            metrics_affected=physical_metric_map[step],
            known_interactions=["Other physical controls in the same module", "incoming geometry"],
            upstream_consequences="Requires the incoming wafer/material state from the previous module.",
            downstream_consequences="Changes the morphology or material quality inherited by every later module.",
            evidence_status="untested",
            supporting_experiment="Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.",
            confidence="high that the control is physically relevant; low that the current model can predict it",
            range_provenance="No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.",
        ))

    structural_choices = [
        ("simulation_dimension", "cross_process", "ps.setDimension / Domain", "2D trench versus 3D cylindrical via", "Current 2D Cartesian geometry is an economical trench surrogate; accepted conclusions require matched 3D confirmation.", "boundary-limited"),
        ("boundary_condition", "cross_process", "Domain boundaryType", "reflective/periodic/other", "Changes particle and level-set behavior at domain boundaries.", "untested"),
        ("single_via_domain", "cross_process", "Domain geometry", "one isolated via versus via array", "Controls whether inter-via shadowing/loading can occur.", "structurally-unresolvable"),
        ("mask_stop_identity", "pattern/cmp", "material stack and strip sequence", "hard mask retained versus resist stripped plus separate stop", "Determines which layer must survive CMP and prevents photoresist from being mislabeled as a physical stop.", "boundary-limited"),
        ("barrier_seed_material_stack", "barrier_seed", "explicit level-set material order", "SiO2/TaN/(Ta)/Cu seed", "Keeps barrier, adhesion, seed, and plated Cu distinguishable for thickness and CMP selectivity.", "confirmed"),
        ("liner_model_family", "liner", "SingleParticleProcess/TEOS/ALD", "transport model choice", "Selects the representable deposition mechanism and available coefficients.", "screened"),
        ("fill_model_family", "cu_fill", "DirectionalProcess/CopperSuppressionFill/other calibrated model", "legacy constant velocity versus reduced suppressor-access proxy versus a future calibrated mechanism", "Determines whether bottom-up rate contrast, void closure, and overburden can be represented; the reduced candidate is a qualification model, not accepted electrochemistry.", "boundary-limited"),
        ("cmp_model_family", "cmp", "IsotropicProcess/Planarize/CSV/custom contact model", "uniform/selective/ideal/contact-aware removal", "Determines whether raised Cu can clear preferentially without erasing the stack.", "boundary-limited"),
    ]
    for id, step, owner, name, mechanism, status in structural_choices:
        liner_family = id == "liner_model_family"
        add(record(
            id, step, owner, name, units="categorical", default=None,
            tested_range=(
                ["SingleParticleProcess", "TEOSDeposition", "IsotropicProcess metric control"]
                if liner_family else None
            ), classification="structural_choice",
            implementation_status=(
                "wired_model_acceptance_candidate"
                if liner_family else "fixed_or_challenge_planned"
            ),
            expected_mechanism=mechanism,
            metrics_affected=["all owning-step morphology CTQs", "model validity"],
            known_interactions=["Every process coefficient in the selected model", "dimensionality", "grid resolution"],
            upstream_consequences="Defines what incoming state can be represented.",
            downstream_consequences="May qualitatively change all later morphology and failure modes.",
            evidence_status=status,
            supporting_experiment=(
                "test_layer_process_models.py confirms distinct full-width responses for the generic, TEOS, and ideal-isotropic control arms; none is yet accepted on Gate-0 geometries."
                if liner_family else
                "RESEARCH_PLAN_V2 controlled model challenges and foundation audit."
            ),
            confidence="high for the need to declare the choice; model winner not yet accepted",
            range_provenance="Structural challenge arms, not an interpolated numeric range.",
        ))

    limitations = [
        ("missing_lithography_physics", "pattern", "No exposure, focus, resist chemistry, develop, line-edge roughness, or overlay model.", ["printed_cd_distribution", "overlay", "defectivity"]),
        ("uncalibrated_physical_scale", "cross_process", "Simulation lengths and model coefficients are not mapped to a physical HBM recipe.", ["all physical-unit claims"]),
        ("two_d_trench_surrogate", "cross_process", "Cartesian 2D MakeHole represents a trench and cannot prove cylindrical 3D topology or flux behavior.", ["void_topology", "conformality", "process_window"]),
        ("missing_electrical_reliability", "cross_process", "Topography simulation does not calculate TDDB, leakage, Cu diffusion, seed resistance, adhesion, stress, or electromigration.", ["electrical_pass", "reliability_pass"]),
        ("liner_chemistry_uncalibrated", "liner", "The current SingleParticle surrogate is not calibrated SACVD/PECVD/ALD chemistry.", ["physical_liner_recipe", "film_quality"]),
        ("barrier_seed_transport_uncalibrated", "barrier_seed", "The current geometric directional surrogate is not calibrated iPVD or ALD.", ["physical_barrier_recipe", "seed_electrical_continuity"]),
        ("legacy_fill_missing_superfill", "cu_fill", "Constant directional/isotropic velocity has no suppressor, accelerator, leveler, coverage feedback, or S-NDR/CEAC mechanism.", ["void_free_fill", "overburden", "physical_fill_recipe"]),
        ("candidate_fill_reduced_physics", "cu_fill", "CopperSuppressionFill is a fixed-sticking ballistic-access proxy with a local quasi-steady suppressor balance. It omits transient chemistry, Cu-ion/electrolyte potential, accelerator and leveler fields, saturated-surface transport feedback, and a fab current waveform; it is not S-NDR or CEAC.", ["physical_fill_recipe", "mechanism_validation", "nominal_and_high_AR_extrapolation"]),
        ("single_level_set_fill_merger", "cu_fill", "The current single Cu interface removes long sub-resolution cavity tails when opposing fronts merge and cannot certify metallurgical seam continuity. Merger history must remain a hard failure unless an explicit seam-resolving representation is validated.", ["seam_free_fill", "centerline_merger", "fill_model_acceptance"]),
        ("legacy_cmp_missing_contact", "cmp", "One-rate isotropic removal has no pad contact pressure, pattern density, endpoint response, or calibrated selectivity.", ["field_clear", "dish", "erosion", "physical_cmp_recipe"]),
        ("single_feature_no_loading", "cross_process", "One local via cannot represent chamber-scale depletion, pitch-dependent loading, or wafer nonuniformity.", ["across_array_uniformity", "RIE_lag"]),
    ]
    for id, step, mechanism, metrics in limitations:
        add(record(
            id, step, "current model boundary", id.replace("_", " "),
            units="not applicable", default=None, tested_range=None,
            classification="model_limitation", implementation_status="not_represented",
            expected_mechanism=mechanism, metrics_affected=metrics,
            known_interactions=["Cannot be repaired by widening the existing coefficient range alone."],
            upstream_consequences="May invalidate the incoming-state interpretation.",
            downstream_consequences="Prevents a physical full-traveler conclusion until resolved or externally validated.",
            evidence_status="structurally-unresolvable",
            supporting_experiment="Foundation re-audit and installed API inspection.",
            confidence="high",
            range_provenance="No range: this is a missing model capability or validation domain.",
        ))

    return records


STATE_INPUT = "__state_input__"

WRAPPER_COVERAGE = {
    "make_initial_geometry": {
        "radius": "pattern_radius_spec",
        "mask_height": "pattern_mask_height_spec",
        "grid_delta": "pattern_grid_delta",
        "x_extent": "pattern_x_extent",
        "y_extent": "pattern_y_extent",
        "taper": "phase_factor_mask_taper",
        "hole_shape": "pattern_hole_shape",
    },
    "strip_pattern_mask": {"geometry": STATE_INPUT},
    "bosch_etch": {
        "geometry": STATE_INPUT,
        "num_cycles": "phase_factor_num_cycles",
        "etch_time": "phase_factor_etch_time",
        "initial_etch_time": "phase_factor_initial_etch_time",
        "ion_source_exponent": "phase_factor_ion_source_exponent",
        "neutral_sticking_probability": "phase_factor_neutral_sticking_probability",
        "deposition_thickness": "phase_factor_deposition_thickness",
        "deposition_sticking_probability": "phase_factor_deposition_sticking_probability",
        "neutral_rate": "phase_factor_neutral_rate",
        "ion_rate": "bosch_ion_rate",
        "on_cycle": "bosch_on_cycle",
        "on_polymer": "bosch_on_polymer",
        "radius": "pattern_radius_spec",
        "theta_r_min": "phase_factor_theta_r_min",
        "rays_per_point": "bosch_rays_per_point",
        "rng_seed": "bosch_rng_seed",
        "mask_ion_rate": "bosch_mask_ion_rate",
    },
    "deposit_conformal": {
        "geometry": STATE_INPUT,
        "material": "deposit_material",
        "thickness": ["phase_factor_liner_thick", "phase_factor_barrier_thick"],
        "directional": "deposit_directional",
        "sticking": "phase_factor_liner_sticking",
        "iso_ratio": "phase_factor_barrier_iso",
        "rays_per_point": "deposit_rays_per_point",
        "rng_seed": "deposit_rng_seed",
    },
    "cu_fill": {
        "geometry": STATE_INPUT,
        "thickness": "phase_factor_fill_thick",
        "directional": "fill_directional",
        "iso_ratio": "phase_factor_fill_iso",
    },
    "cmp_planarize": {
        "geometry": STATE_INPUT,
        "target_y": "cmp_target_y",
    },
}

LAYER_MODEL_COVERAGE = {
    "ray_parameters": {
        "rays_per_point": "deposit_rays_per_point",
        "rng_seed": "deposit_rng_seed",
        "max_reflections": "api_RayTracingParameters_maxReflections",
        "max_boundary_hits": "api_RayTracingParameters_maxBoundaryHits",
    },
    "deposit_single_particle": {
        "geometry": STATE_INPUT,
        "material": "deposit_material",
        "dose": "candidate_liner_single_particle_dose",
        "sticking_probability": "candidate_liner_single_particle_sticking",
        "source_exponent": "single_particle_source_exponent",
        "rays_per_point": "deposit_rays_per_point",
        "rng_seed": "deposit_rng_seed",
        "max_reflections": "api_RayTracingParameters_maxReflections",
        "max_boundary_hits": "api_RayTracingParameters_maxBoundaryHits",
    },
    "deposit_teos": {
        "geometry": STATE_INPUT,
        "material": "deposit_material",
        "dose": "teos_p1_rate",
        "sticking_probability": "teos_p1_sticking",
        "reaction_order": "teos_p1_order",
        "rays_per_point": "deposit_rays_per_point",
        "rng_seed": "deposit_rng_seed",
        "max_reflections": "api_RayTracingParameters_maxReflections",
        "max_boundary_hits": "api_RayTracingParameters_maxBoundaryHits",
    },
    "directional_components": {
        "field_dose": "candidate_barrier_seed_field_dose",
        "isotropic_fraction": "candidate_barrier_seed_isotropic_fraction",
    },
    "deposit_directional_fraction": {
        "geometry": STATE_INPUT,
        "material": "deposit_material",
        "field_dose": "candidate_barrier_seed_field_dose",
        "isotropic_fraction": "candidate_barrier_seed_isotropic_fraction",
        "direction": "direction_vector",
        "calculate_visibility": "directional_visibility",
    },
    "deposit_isotropic_control": {
        "geometry": STATE_INPUT,
        "material": "deposit_material",
        "dose": "layer_isotropic_control_dose",
    },
}


def validate(records):
    ids = [item["id"] for item in records]
    assert len(ids) == len(set(ids)), "registry IDs must be unique"
    by_id = {item["id"]: item for item in records}

    for item in records:
        missing = REQUIRED_FIELDS - set(item)
        assert not missing, (item.get("id"), sorted(missing))
        assert item["classification"] in CLASSIFICATIONS, item["id"]
        assert item["evidence_status"] in EVIDENCE_STATUSES, item["id"]
        assert item["step"] and item["owner_api"] and item["name"], item["id"]
        assert item["units"] is not None, item["id"]
        assert isinstance(item["metrics_affected"], list), item["id"]
        assert isinstance(item["known_interactions"], list), item["id"]
        assert item["range_provenance"], item["id"]

    phase = [item for item in records if item.get("phase_one_factor")]
    assert len(phase) == 17, len(phase)
    assert {item["name"] for item in phase} == set(joint.SPACE)
    for item in phase:
        assert item["current_best"]["status"] == "legacy_suspended"
        assert set(joint.SPACE[item["name"]]) <= set(item["tested_range"])

    assert sum(item["implementation_status"] == "unsupported_physical" for item in records) >= 40
    assert sum(item["classification"] == "model_limitation" for item in records) >= 8

    candidate_ids = {
        "candidate_fill_suppressor_sticking_probability",
        "candidate_fill_suppressor_source_power",
        "candidate_fill_gas_mean_free_path",
        "candidate_fill_adsorption_strength",
        "candidate_fill_deactivation_rate",
        "candidate_fill_active_deposition_rate",
        "candidate_fill_suppressed_deposition_rate",
        "candidate_fill_plating_materials",
    }
    assert {
        by_id[id]["name"] for id in candidate_ids
    } == {
        "suppressorStickingProbability",
        "suppressorSourcePower",
        "gasMeanFreePath",
        "adsorptionStrength",
        "deactivationRate",
        "activeDepositionRate",
        "suppressedDepositionRate",
        "platingMaterials",
    }
    for id in candidate_ids:
        assert by_id[id]["evidence_status"] == "screened"
        assert by_id[id]["current_best"]["status"] == "qualification_setting_not_best"
        assert by_id[id]["identifiability_coupling"]
    assert by_id["candidate_fill_plating_materials"]["classification"] == "structural_choice"
    assert all(
        by_id[id]["classification"] == "model_coefficient"
        for id in candidate_ids - {"candidate_fill_plating_materials"}
    )

    candidate_cmp_parameter_ids = {
        "candidate_cmp_stop_height": "stopHeight",
        "candidate_cmp_compliance_length": "complianceLength",
        "candidate_cmp_residual_contact": "residualContact",
        "candidate_cmp_plated_cu_rate": "platedCuRemovalRate",
        "candidate_cmp_seed_material": "cuSeedMaterial",
        "candidate_cmp_seed_rate": "cuSeedRemovalRate",
        "candidate_cmp_tan_rate": "tantalumNitrideRemovalRate",
        "candidate_cmp_sio2_rate": "siliconDioxideRemovalRate",
        "candidate_cmp_si_rate": "siliconRemovalRate",
    }
    assert {
        id: by_id[id]["name"] for id in candidate_cmp_parameter_ids
    } == candidate_cmp_parameter_ids
    assert all(
        by_id[id]["implementation_status"]
        == "candidate_extension_qualification_only"
        for id in candidate_cmp_parameter_ids
    )
    assert by_id["candidate_cmp_seed_material"]["classification"] == "structural_choice"
    assert by_id["candidate_cmp_stop_height"]["classification"] == "structural_choice"
    for id in (
        "cmp_minimum_stop_retained_spec",
        "cmp_maximum_stop_erosion_spec",
        "cmp_maximum_plug_height_loss_spec",
        "cmp_maximum_plug_area_loss_spec",
    ):
        assert by_id[id]["classification"] == "product_specification"
        assert by_id[id]["implementation_status"] == "required_unset_blocks_cmp_doe"
        assert by_id[id]["default"] is None

    void_guard = by_id["api_AdvectionParameters_ignoreVoids"]
    assert void_guard["implementation_status"] == "required_candidate_void_guard"
    assert void_guard["current_best"]["value"] is True
    assert void_guard["current_best"]["status"] == "mandatory_validity_guard"
    assert set(void_guard["tested_range"]) == {False, True}

    tiers = by_id["geometry_qualification_tier"]
    assert set(tiers["declared_levels"]) == {
        "continuity", "nominal_hbm", "high_ar_stress"
    }
    assert by_id["pattern_hole_shape"]["implementation_status"] == "wired_by_stage"
    assert by_id["fill_void_spec"]["classification"] == "product_specification"
    assert by_id["fill_overburden_spec"]["classification"] == "product_specification"

    for function_name, parameters in WRAPPER_COVERAGE.items():
        actual = set(inspect.signature(getattr(tp, function_name)).parameters)
        assert actual == set(parameters), (
            function_name,
            "unregistered", sorted(actual - set(parameters)),
            "stale", sorted(set(parameters) - actual),
        )
        for target in parameters.values():
            for target_id in target if isinstance(target, list) else [target]:
                assert target_id == STATE_INPUT or target_id in by_id, (function_name, target_id)

    for function_name, parameters in LAYER_MODEL_COVERAGE.items():
        actual = set(inspect.signature(getattr(layer_models, function_name)).parameters)
        assert actual == set(parameters), (
            function_name,
            "unregistered", sorted(actual - set(parameters)),
            "stale", sorted(set(parameters) - actual),
        )
        for target in parameters.values():
            for target_id in target if isinstance(target, list) else [target]:
                assert target_id == STATE_INPUT or target_id in by_id, (function_name, target_id)

    for pack in (
        "RayTracingParameters", "AdvectionParameters", "CoverageParameters",
        "AtomicLayerProcessParameters",
    ):
        expected = set(parameter_defaults_for(pack))
        recorded = {
            item["id"].removeprefix(f"api_{pack}_")
            for item in records
            if item["id"].startswith(f"api_{pack}_")
        }
        assert recorded == expected, (pack, expected - recorded, recorded - expected)


def parameter_defaults_for(name):
    import viennaps as ps

    instance = getattr(ps, name)()
    return {
        attribute: getattr(instance, attribute)
        for attribute in dir(instance)
        if not attribute.startswith("_") and not callable(getattr(instance, attribute))
    }


def counts_for(records):
    return {
        "total": len(records),
        "by_step": dict(sorted(Counter(item["step"] for item in records).items())),
        "by_classification": dict(sorted(Counter(item["classification"] for item in records).items())),
        "by_implementation_status": dict(sorted(Counter(item["implementation_status"] for item in records).items())),
        "by_evidence_status": dict(sorted(Counter(item["evidence_status"] for item in records).items())),
        "phase_one_factors": sum(bool(item.get("phase_one_factor")) for item in records),
        "unsupported_physical_controls": sum(item["implementation_status"] == "unsupported_physical" for item in records),
        "model_limitations": sum(item["classification"] == "model_limitation" for item in records),
    }


def build_document(records):
    return {
        "schema_version": 1,
        "audit_date": "2026-07-11",
        "status": "foundation_reaudit_in_progress",
        "scope": "Current TSV wrappers, directly relevant installed ViennaPS controls, unsupported physical controls, product targets, numerical controls, structural choices, and model limitations.",
        "warning": "All phase-one current-best values are legacy_suspended. Model-sensitivity ranges are not fab-calibrated recipe ranges.",
        "source_files": [
            "program.md",
            "train.md",
            "prepare.md",
            "RESEARCH_PLAN_V2.md",
            "tsv_process.py",
            "layer_process_models.py",
            "full_2d_layer_metrics.py",
            "test_layer_process_models.py",
            "joint_process_doe.py",
            "foundation_copper_fill_trajectory.py",
            ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json",
            "test_copper_suppression_fill.py",
            "patches/viennaps-copper-suppression-fill.patch",
            "api_knob_audit.py",
            "autoresearch-results/restart_audit/api_signature_audit.json",
            "autoresearch-results/full_campaign/*/raw_rows.jsonl",
        ],
        "external_evidence": [
            "https://viennatools.github.io/ViennaPS/geo/basic/hole.html",
            "https://viennatools.github.io/ViennaPS/process/",
            "https://viennatools.github.io/ViennaPS/models/prebuilt/isotropic.html",
            "https://github.com/ViennaTools/ViennaPS/blob/v4.6.1/examples/atomicLayerDeposition/atomicLayerDeposition.py",
            "https://viennatools.github.io/ViennaPS/process/",
            "https://www.nist.gov/publications/metrology-needs-tsv-fabrication",
            "https://www.nist.gov/publications/impact-adsorbates-metal-deposition-through-curvature-enhanced-accelerator-coverage",
            "https://www.cambridge.org/core/services/aop-cambridge-core/content/view/5190AA6FCFAD44D56EBF6DCA47CA7E15/S1946427400620912a.pdf/contactmechanics_based_model_for_dishing_and_erosion_in_chemicalmechanical_polishing.pdf",
        ],
        "classification_vocabulary": sorted(CLASSIFICATIONS),
        "evidence_status_vocabulary": sorted(EVIDENCE_STATUSES),
        "counts": counts_for(records),
        "records": records,
    }


def pretty(value):
    if value is None:
        return "not assigned"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def md(value):
    return pretty(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(document):
    counts = document["counts"]
    lines = [
        "# TSV traveler knob and range registry\n\n",
        f"Status: `{document['status']}`. {document['warning']}\n\n",
        "This registry separates declared outputs, executable recipe proxies, model coefficients, numerical controls, structural choices, unsupported physical controls, and model limitations. `current_best` is not a recommendation when its status is `legacy_suspended`.\n\n",
        "## Inventory\n\n",
        "| Item | Count |\n|---|---:|\n",
        f"| Total records | {counts['total']} |\n",
        f"| Phase-one DOE factors | {counts['phase_one_factors']} |\n",
        f"| Unsupported physical controls | {counts['unsupported_physical_controls']} |\n",
        f"| Model limitations | {counts['model_limitations']} |\n\n",
        "### Classification counts\n\n",
        "| Classification | Count |\n|---|---:|\n",
    ]
    for name, count in counts["by_classification"].items():
        lines.append(f"| `{name}` | {count} |\n")

    lines += [
        "\n## The 17 phase-one factors\n\n",
        "These ranges are the union of phase-one sampled values. They are model-sensitivity ranges, not calibrated fab ranges.\n\n",
        "| Factor | Step | Class | Units | Default | Tested values | Legacy best | Evidence |\n",
        "|---|---|---|---|---|---|---|---|\n",
    ]
    for item in (item for item in document["records"] if item.get("phase_one_factor")):
        lines.append(
            f"| `{item['name']}` | {md(item['step'])} | `{item['classification']}` | "
            f"{md(item['units'])} | {md(item['default'])} | {md(item['tested_range'])} | "
            f"{md(item['current_best'])} | `{item['evidence_status']}` |\n"
        )

    lines += ["\n## Complete registry\n\n"]
    step_order = ["pattern", "bosch_etch", "liner", "barrier_seed", "cu_fill", "cmp", "cross_process"]
    remaining = sorted(set(item["step"] for item in document["records"]) - set(step_order))
    for step in step_order + remaining:
        items = [item for item in document["records"] if item["step"] == step]
        if not items:
            continue
        lines.append(f"### {step.replace('_', ' ').title()}\n\n")
        for item in items:
            lines += [
                f"#### `{item['id']}` — {item['name']}\n\n",
                f"- Owner/API: `{item['owner_api']}`\n",
                f"- Classification / implementation: `{item['classification']}` / `{item['implementation_status']}`\n",
                f"- Units / default / tested range: {md(item['units'])} / {md(item['default'])} / {md(item['tested_range'])}\n",
                f"- Current best: {md(item['current_best'])}\n",
                f"- Expected mechanism: {item['expected_mechanism']}\n",
                f"- Metrics affected: {md(item['metrics_affected'])}\n",
                f"- Known interactions: {md(item['known_interactions'])}\n",
                f"- Upstream consequence: {item['upstream_consequences']}\n",
                f"- Downstream consequence: {item['downstream_consequences']}\n",
                f"- Evidence: `{item['evidence_status']}`; confidence: {item['confidence']}\n",
                f"- Supporting experiment: {item['supporting_experiment']}\n",
                f"- Range provenance: {item['range_provenance']}\n\n",
            ]
    return "".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Validate registry and require generated files to be current.")
    args = parser.parse_args()

    records = build_records()
    validate(records)
    document = build_document(records)
    json_text = json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    markdown_text = render_markdown(document)

    if args.check:
        assert JSON_PATH.read_text() == json_text, f"stale {JSON_PATH}"
        assert MARKDOWN_PATH.read_text() == markdown_text, f"stale {MARKDOWN_PATH}"
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        JSON_PATH.write_text(json_text)
        MARKDOWN_PATH.write_text(markdown_text)

    counts = document["counts"]
    print(
        f"knob registry: {counts['total']} records, "
        f"{counts['phase_one_factors']} phase factors, "
        f"{counts['unsupported_physical_controls']} unsupported physical controls"
    )


if __name__ == "__main__":
    main()

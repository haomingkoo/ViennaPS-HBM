# TSV traveler knob and range registry

Status: `range_requalification_in_progress`. All phase-one current-best values are legacy_suspended. Model-sensitivity ranges are not fab-calibrated recipe ranges.

This registry separates declared outputs, executable recipe proxies, model coefficients, numerical controls, structural choices, unsupported physical controls, and model limitations. `current_best` is not a recommendation when its status is `legacy_suspended`.

Primary-source range findings and unresolved mappings are recorded in [range-research.md](range-research.md).

## Inventory

| Item | Count |
|---|---:|
| Total records | 249 |
| Phase-one DOE factors | 17 |
| Unsupported physical controls | 50 |
| Model limitations | 11 |

### Classification counts

| Classification | Count |
|---|---:|
| `model_coefficient` | 94 |
| `model_limitation` | 11 |
| `numerical_control` | 39 |
| `product_specification` | 18 |
| `recipe_knob` | 55 |
| `structural_choice` | 32 |

### DOE eligibility counts

Only factors marked for range requalification may enter the first range-finding stage. Numerical controls have a separate benchmark.

| Eligibility | Count |
|---|---:|
| `excluded_rejected` | 5 |
| `legacy_suspended` | 7 |
| `mechanism_or_measurement_gate_first` | 17 |
| `not_a_tuning_factor` | 29 |
| `not_wired` | 55 |
| `numerical_benchmark_only` | 39 |
| `range_requalification_required` | 23 |
| `requires_model_and_calibration` | 50 |
| `review_required` | 24 |

## The 17 phase-one factors

These ranges are the union of phase-one sampled values. They are model-sensitivity ranges, not calibrated fab ranges.

| Factor | Step | Class | Units | Default | Tested values | Legacy best | Evidence |
|---|---|---|---|---|---|---|---|
| `mask_taper` | pattern | `structural_choice` | degrees | 0.0 | [0.0, 2.0, 4.0, 6.0] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 4.0} | `screened` |
| `num_cycles` | bosch_etch | `recipe_knob` | cycles | 10 | [10, 11, 12, 13, 14, 15, 16] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 15} | `screened` |
| `etch_time` | bosch_etch | `recipe_knob` | simulation time per cycle | 1.5 | [0.45, 0.5, 0.55, 0.6, 0.65, 0.7] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.5} | `screened` |
| `neutral_rate` | bosch_etch | `model_coefficient` | simulation velocity coefficient | -0.2 | [-0.15, -0.12, -0.1, -0.08, -0.06, -0.04] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": -0.12} | `screened` |
| `neutral_sticking_probability` | bosch_etch | `model_coefficient` | probability | 0.1 | [0.05, 0.08, 0.12, 0.16, 0.2, 0.24] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.08} | `screened` |
| `initial_etch_time` | bosch_etch | `recipe_knob` | simulation time | 0.3 | [0.15, 0.2, 0.3, 0.45] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.3} | `screened` |
| `deposition_thickness` | bosch_etch | `model_coefficient` | simulation length per cycle | 0.02 | [0.003, 0.005, 0.01, 0.015] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.01} | `screened` |
| `deposition_sticking_probability` | bosch_etch | `model_coefficient` | probability | 0.01 | [0.0015, 0.003, 0.005, 0.01, 0.02] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.005} | `screened` |
| `ion_source_exponent` | bosch_etch | `model_coefficient` | dimensionless exponent | 200 | [100, 200, 400, 600, 800] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 200} | `screened` |
| `theta_r_min` | bosch_etch | `model_coefficient` | degrees | 60.0 | [30.0, 45.0, 60.0, 75.0, 90.0] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 90.0} | `screened` |
| `liner_thick` | liner | `recipe_knob` | commanded simulation dose | not assigned | [0.018, 0.02, 0.024, 0.028, 0.035, 0.045] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.02} | `screened` |
| `liner_sticking` | liner | `model_coefficient` | probability | 0.05 | [0.02, 0.08, 0.16, 0.24, 0.3, 0.35] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.24} | `screened` |
| `barrier_thick` | barrier_seed | `recipe_knob` | commanded simulation dose | not assigned | [0.01, 0.012, 0.014, 0.018, 0.024] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.012} | `screened` |
| `barrier_iso` | barrier_seed | `model_coefficient` | ratio | 0.3 | [0.0, 0.1, 0.2, 0.4] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.0} | `screened` |
| `fill_thick` | cu_fill | `recipe_knob` | commanded simulation dose | not assigned | [0.12, 0.14, 0.15, 0.155, 0.16, 0.18, 0.22, 0.26] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.22} | `screened` |
| `fill_iso` | cu_fill | `model_coefficient` | ratio | 0.2 | [0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.6] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.05} | `screened` |
| `cmp_mult` | cmp | `recipe_knob` | overburden multiple | not assigned | [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 3.0] | {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 1.5} | `screened` |

## Complete registry

### Pattern

#### `pattern_radius_spec` — opening radius

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 0.15 / [0.15]
- Current best: not assigned
- Expected mechanism: Generated opening radius; twice this value is the nominal CD.
- Metrics affected: ["top_cd", "bottom_cd", "aspect_ratio"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Every downstream flux and available volume changes with CD.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `pattern_width_spec` — opening width

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 0.3 / [0.3]
- Current best: not assigned
- Expected mechanism: Nominal opening critical dimension.
- Metrics affected: ["top_cd", "bottom_cd", "cd_bias"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Sets etch aspect ratio and the volume that liner, seed, and Cu must occupy.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `pattern_mask_height_spec` — pattern-mask height

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 0.3 / [0.3]
- Current best: not assigned
- Expected mechanism: Sets the patterned masking-layer thickness.
- Metrics affected: ["mask_height", "mask_remaining"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Controls etch protection and the field stack entering mask strip or CMP-stop selection.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `phase_factor_mask_taper` — mask_taper

- Owner/API: `make_initial_geometry(taper) / MakeHole.maskTaperAngle`
- Classification / implementation: `structural_choice` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degrees / 0.0 / [0.0, 2.0, 4.0, 6.0]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 4.0}
- Expected mechanism: Tilts the generated mask wall and changes the etch entrance boundary.
- Metrics affected: ["top_cd", "mask_sidewall_angle", "etch_variance"]
- Known interactions: ["mask_taper x stochastic ray sampling"]
- Upstream consequence: Changes the upstream aperture.
- Downstream consequence: Propagates to etch CD and all downstream access.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `pattern_radius_input` — pattern radius input

- Owner/API: `make_initial_geometry(radius) / MakeHole.holeRadius`
- Classification / implementation: `structural_choice` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / 0.15 / [0.12, 0.15, 0.18]
- Current best: not assigned
- Expected mechanism: Sets the constructed opening radius independently of the comparison target.
- Metrics affected: ["opening_cd_profile", "etch_cd_profile", "aspect_ratio"]
- Known interactions: ["radius x mask taper", "radius x directional transport"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: high for wiring; low for physical mapping
- Supporting experiment: The active teaching export varies the constructor radius at three saved values; those values are not a calibrated lithography range.
- Range provenance: Saved model-space sensitivity values from config/process.toml; range requalification required.

#### `pattern_mask_height_input` — pattern mask height input

- Owner/API: `make_initial_geometry(mask_height) / MakeHole.maskHeight`
- Classification / implementation: `structural_choice` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / 0.3 / [0.3]
- Current best: not assigned
- Expected mechanism: Sets the constructed mask height independently of the comparison target.
- Metrics affected: ["mask_remaining", "opening_profile", "etch_handoff"]
- Known interactions: ["mask height x mask erosion", "mask height x cycle count"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: high for wiring; low for physical mapping
- Supporting experiment: The constructor input is wired and measured, but no range-finding ladder has been completed.
- Range provenance: Wrapper default only; range requalification required before a mask-erosion study.

#### `pattern_grid_delta` — pattern grid delta

- Owner/API: `make_initial_geometry(grid_delta) / Domain.gridDelta`
- Classification / implementation: `numerical_control` / `wired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: grid spacing / 0.01 / [0.01, 0.005, 0.0025, 0.00125, 0.000625]
- Current best: not assigned
- Expected mechanism: Controls level-set and material-interface resolution.
- Metrics affected: ["all_geometry_ctqs", "topology"]
- Known interactions: ["grid_delta x every thin layer", "grid_delta x passivation dose"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `confirmed`; confidence: medium
- Supporting experiment: Foundation grid and Bosch passivation-resolution audits; 0.00125 is accepted only for focused high-fidelity 2D etch audits.
- Range provenance: Numerical-convergence ladder; not a recipe range.

#### `pattern_x_extent` — pattern x extent

- Owner/API: `make_initial_geometry(x_extent) / Domain.xExtent`
- Classification / implementation: `numerical_control` / `wired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / 1.0 / [1.0]
- Current best: not assigned
- Expected mechanism: Sets lateral distance to the domain boundary.
- Metrics affected: ["boundary_clearance", "flux_transport"]
- Known interactions: ["x_extent x boundary condition"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: low
- Supporting experiment: No dedicated lateral-domain convergence result yet.
- Range provenance: Wrapper default only.

#### `pattern_y_extent` — pattern y extent

- Owner/API: `make_initial_geometry(y_extent) / Domain.yExtent`
- Classification / implementation: `numerical_control` / `wired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / 1.5 / [1.5, 2.0, 2.5]
- Current best: not assigned
- Expected mechanism: Sets vertical distance to the lower domain boundary.
- Metrics affected: ["boundary_clearance", "depth", "cd_profile"]
- Known interactions: ["y_extent x target depth"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `confirmed`; confidence: high for tested 2D etch
- Supporting experiment: Foundation domain audit reproduced full-cycle etch CTQs within 4.4e-15 across 1.5, 2.0, and 2.5 for two seeds.
- Range provenance: Numerical domain-convergence experiment.

#### `pattern_hole_depth` — pattern hole depth

- Owner/API: `MakeHole.holeDepth`
- Classification / implementation: `structural_choice` / `fixed`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / 0.0 / [0.0]
- Current best: not assigned
- Expected mechanism: Constructs a mask opening without a pre-etched silicon cavity.
- Metrics affected: ["opening_validity"]
- Known interactions: []
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `confirmed`; confidence: high
- Supporting experiment: Direct wrapper inspection.
- Range provenance: Fixed by the intended pattern-before-etch sequence.

#### `pattern_hole_taper` — pattern hole taper

- Owner/API: `MakeHole.holeTaperAngle`
- Classification / implementation: `structural_choice` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degrees / 0.0 / [-10.0, -5.0, 0.0, 5.0, 10.0]
- Current best: not assigned
- Expected mechanism: Would taper a pre-existing hole; with holeDepth=0 it is not a lithography control.
- Metrics affected: ["opening_profile"]
- Known interactions: ["hole taper x hole depth"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: low
- Supporting experiment: Legacy API screen found a small apparent etch effect, but the current pattern has zero hole depth.
- Range provenance: API-bounded sensitivity screen; no physical lithography mapping.

#### `pattern_substrate_material` — pattern substrate material

- Owner/API: `MakeHole.material`
- Classification / implementation: `structural_choice` / `fixed`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material enum / Material.Si / ["Material.Si"]
- Current best: not assigned
- Expected mechanism: Defines the etched substrate material identity.
- Metrics affected: ["material_survival", "etch_selectivity"]
- Known interactions: []
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `confirmed`; confidence: high
- Supporting experiment: Direct wrapper/API inspection.
- Range provenance: Declared TSV silicon substrate.

#### `pattern_mask_material` — pattern mask material

- Owner/API: `MakeHole.maskMaterial`
- Classification / implementation: `structural_choice` / `fixed`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material enum / Material.Mask / ["Material.Mask"]
- Current best: not assigned
- Expected mechanism: Defines the temporary pattern-mask level set.
- Metrics affected: ["mask_remaining", "stop_layer_identity"]
- Known interactions: ["mask identity x strip sequence", "mask identity x CMP stop"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `boundary-limited`; confidence: high for code identity; low for physical stack
- Supporting experiment: Mask identity is explicitly challenged in RESEARCH_PLAN_V2; photoresist may not be carried through physical CMP.
- Range provenance: Structural choice awaiting hard-mask versus stripped-resist decision.

#### `pattern_mask_strip` — pattern mask strip

- Owner/API: `strip_pattern_mask / Domain.removeMaterial`
- Classification / implementation: `structural_choice` / `wired`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: boolean sequence choice / true / [false, true]
- Current best: not assigned
- Expected mechanism: Removes the temporary pattern mask before dielectric deposition.
- Metrics affected: ["material_stack", "remaining_aperture"]
- Known interactions: ["strip choice x CMP stop identity"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `confirmed`; confidence: high for operation
- Supporting experiment: Wrapper guard verifies Material.Mask is absent after stripping; full traveler wiring remains to be completed.
- Range provenance: Required by the temporary-photoresist interpretation; alternative hard-mask stack remains a controlled structural arm.

#### `litho_exposure_dose` — exposure dose

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: energy/area / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes the resist latent image and developed CD.
- Metrics affected: ["opening_cd", "mask_profile", "pattern_validity"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `litho_focus_offset` — focus offset

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: length / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes aerial-image contrast and resist profile.
- Metrics affected: ["opening_cd", "mask_profile", "pattern_validity"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `litho_mask_bias` — reticle/mask CD bias

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: length / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Offsets printed opening CD.
- Metrics affected: ["opening_cd", "mask_profile", "pattern_validity"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `litho_resist_thickness` — photoresist coat thickness

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: length / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Sets etch-mask budget and developed aspect ratio.
- Metrics affected: ["opening_cd", "mask_profile", "pattern_validity"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `litho_bake_conditions` — soft/post-exposure bake

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: temperature and time / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes resist chemistry, diffusion, and profile.
- Metrics affected: ["opening_cd", "mask_profile", "pattern_validity"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `litho_develop_conditions` — developer chemistry/time

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: chemistry and time / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls resist dissolution, CD, and sidewall angle.
- Metrics affected: ["opening_cd", "mask_profile", "pattern_validity"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `litho_overlay` — TSV overlay

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: length / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Positions the TSV relative to device features.
- Metrics affected: ["opening_cd", "mask_profile", "pattern_validity"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `missing_lithography_physics` — missing lithography physics

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: No exposure, focus, resist chemistry, develop, line-edge roughness, or overlay model.
- Metrics affected: ["printed_cd_distribution", "overlay", "defectivity"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

### Bosch Etch

#### `etch_depth_spec` — target etch depth

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 1.25 / [1.15, 1.35]
- Current best: not assigned
- Expected mechanism: Defines the qualified blind-via depth.
- Metrics affected: ["depth", "aspect_ratio"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Controls every downstream coverage and fill requirement.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `etch_cd_tolerance_spec` — CD-profile tolerance

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 0.06 / [0.0, 0.06]
- Current best: not assigned
- Expected mechanism: Bounds measured CD departure over declared depth fractions.
- Metrics affected: ["entrance_cd", "mid_cd", "bottom_cd", "cd_profile_error"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Constrains layer access and Cu-fill volume.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `etch_bow_spec` — maximum wall bow

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 0.03 / [0.0, 0.03]
- Current best: not assigned
- Expected mechanism: Bounds large-scale wall deviation after removing taper and scallop residual.
- Metrics affected: ["wall_bow", "sidewall_taper"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Sharp narrowing or bulging changes film continuity and fill pinch-off risk.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `phase_factor_num_cycles` — num_cycles

- Owner/API: `bosch_etch(num_cycles)`
- Classification / implementation: `recipe_knob` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: cycles / 10 / [10, 11, 12, 13, 14, 15, 16]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 15}
- Expected mechanism: Repeats passivation, punch-through, and etch phases.
- Metrics affected: ["depth", "scallop_period", "wall_bow"]
- Known interactions: ["num_cycles x etch_time", "num_cycles x deposition_thickness"]
- Upstream consequence: Consumes the patterned-mask budget.
- Downstream consequence: Sets via depth and scallop history for every deposition.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_etch_time` — etch_time

- Owner/API: `bosch_etch(etch_time) / Process.duration`
- Classification / implementation: `recipe_knob` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation time per cycle / 1.5 / [0.45, 0.5, 0.55, 0.6, 0.65, 0.7]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.5}
- Expected mechanism: Extends each silicon etch phase.
- Metrics affected: ["depth", "etch_rate", "wall_bow", "cd_profile"]
- Known interactions: ["etch_time x deposition_thickness", "etch_time x num_cycles", "etch_time x neutral_rate"]
- Upstream consequence: None beyond the pattern mask.
- Downstream consequence: Changes aspect ratio, CD, layer coverage, and Cu-fill volume.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_neutral_rate` — neutral_rate

- Owner/API: `bosch_etch rate_fn neutral coefficient`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation velocity coefficient / -0.2 / [-0.15, -0.12, -0.1, -0.08, -0.06, -0.04]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": -0.12}
- Expected mechanism: Scales the neutral chemical contribution on silicon.
- Metrics affected: ["depth", "undercut", "wall_bow"]
- Known interactions: ["neutral_rate x etch_time", "neutral_rate x neutral_sticking_probability"]
- Upstream consequence: None beyond mask geometry.
- Downstream consequence: Changes wall shape and downstream line-of-sight.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_neutral_sticking_probability` — neutral_sticking_probability

- Owner/API: `MultiParticleProcess.addNeutralParticle`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / 0.1 / [0.05, 0.08, 0.12, 0.16, 0.2, 0.24]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.08}
- Expected mechanism: Controls neutral absorption versus reflection and therefore transport into the via.
- Metrics affected: ["depth", "cd_profile", "wall_bow"]
- Known interactions: ["neutral sticking x neutral_rate", "neutral sticking x aspect ratio"]
- Upstream consequence: None beyond pattern geometry.
- Downstream consequence: Changes bottom flux and downstream geometry.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_initial_etch_time` — initial_etch_time

- Owner/API: `bosch_etch(initial_etch_time)`
- Classification / implementation: `recipe_knob` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation time / 0.3 / [0.15, 0.2, 0.3, 0.45]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.3}
- Expected mechanism: Controls the unpassivated opening/seed etch before Bosch cycling.
- Metrics affected: ["entrance_cd", "depth", "undercut"]
- Known interactions: ["initial etch x mask taper"]
- Upstream consequence: Can widen the mask opening transfer.
- Downstream consequence: Sets the mouth profile inherited by all later steps.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_deposition_thickness` — deposition_thickness

- Owner/API: `SingleParticleProcess.rate for passivation`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length per cycle / 0.02 / [0.003, 0.005, 0.01, 0.015]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.01}
- Expected mechanism: Commands the passivation dose before ion punch-through.
- Metrics affected: ["polymer_thickness", "wall_bow", "depth", "scallop_amplitude"]
- Known interactions: ["deposition thickness x etch_time", "deposition thickness x grid_delta"]
- Upstream consequence: None beyond pattern geometry.
- Downstream consequence: Controls wall protection and therefore downstream roughness/access.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_deposition_sticking_probability` — deposition_sticking_probability

- Owner/API: `SingleParticleProcess.stickingProbability`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / 0.01 / [0.0015, 0.003, 0.005, 0.01, 0.02]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.005}
- Expected mechanism: Controls passivation-particle reflection and depth transport.
- Metrics affected: ["polymer_conformality", "wall_bow", "depth"]
- Known interactions: ["deposition sticking x aspect ratio"]
- Upstream consequence: None beyond pattern geometry.
- Downstream consequence: Changes sidewall protection and scallop morphology.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_ion_source_exponent` — ion_source_exponent

- Owner/API: `MultiParticleProcess.addIonParticle(sourcePower)`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless exponent / 200 / [100, 200, 400, 600, 800]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 200}
- Expected mechanism: Controls angular collimation of ion flux and passivation punch-through.
- Metrics affected: ["depth", "bottom_shape", "wall_bow"]
- Known interactions: ["ion exponent x theta_r_min", "ion exponent x rays_per_point"]
- Upstream consequence: None beyond the mask.
- Downstream consequence: Changes anisotropy and bottom access.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_theta_r_min` — theta_r_min

- Owner/API: `MultiParticleProcess.addIonParticle(thetaRMin)`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degrees / 60.0 / [30.0, 45.0, 60.0, 75.0, 90.0]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 90.0}
- Expected mechanism: Sets the lower angle in the ion sticking/reflection law.
- Metrics affected: ["depth", "bottom_shape", "cd_profile"]
- Known interactions: ["theta_r_min x ion_source_exponent"]
- Upstream consequence: None beyond the mask.
- Downstream consequence: Changes reflected-ion transport and wall shape.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Active V3 Bosch code path plus phase-one range history; prior rankings and best values remain suspended.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `bosch_polymer_deposition_duration` — bosch polymer deposition duration

- Owner/API: `bosch_etch / apply_process(depo_model, 1.0)`
- Classification / implementation: `structural_choice` / `hardcoded_fixed`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model time per cycle / 1.0 / [1.0]
- Current best: not assigned
- Expected mechanism: Sets the duration of each polymer-deposition phase independently of the commanded deposition rate.
- Metrics affected: ["polymer_thickness", "wall_protection", "runtime"]
- Known interactions: ["deposition duration x deposition rate", "deposition duration x cycle count"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `untested`; confidence: high for wiring; no physical calibration
- Supporting experiment: The wrapper hard-codes this duration to 1.0; it has not been varied independently.
- Range provenance: Fixed implementation value, not a qualified range.

#### `bosch_polymer_removal_duration` — bosch polymer removal duration

- Owner/API: `bosch_etch / apply_process(depo_removal, 1.0)`
- Classification / implementation: `structural_choice` / `hardcoded_fixed`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model time per cycle / 1.0 / [1.0]
- Current best: not assigned
- Expected mechanism: Sets the duration of directional polymer punch-through before each silicon etch phase.
- Metrics affected: ["polymer_floor_clearance", "wall_protection", "runtime"]
- Known interactions: ["removal duration x removal rate", "removal duration x cycle count"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `untested`; confidence: high for wiring; no physical calibration
- Supporting experiment: The wrapper hard-codes this duration to 1.0; it has not been varied independently.
- Range provenance: Fixed implementation value, not a qualified range.

#### `bosch_polymer_removal_rate` — bosch polymer removal rate

- Owner/API: `bosch_etch / SingleParticleProcess(rate=-deposition_thickness)`
- Classification / implementation: `model_coefficient` / `hardcoded_coupled`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation velocity coefficient / negative of deposition_thickness / ["-deposition_thickness"]
- Current best: not assigned
- Expected mechanism: Uses the polymer-deposition amount as an equal-magnitude directional removal rate; it is not independently tunable.
- Metrics affected: ["polymer_floor_clearance", "wall_protection", "depth", "bow"]
- Known interactions: ["removal rate x deposition rate", "removal rate x ion direction"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `untested`; confidence: high for wiring; no physical calibration
- Supporting experiment: Direct wrapper inspection shows an exact coupling to deposition_thickness.
- Range provenance: Derived coupling, not an independent range.

#### `bosch_polymer_removal_sticking` — bosch polymer removal sticking

- Owner/API: `bosch_etch / SingleParticleProcess(stickingProbability=1.0)`
- Classification / implementation: `model_coefficient` / `hardcoded_fixed`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / 1.0 / [1.0]
- Current best: not assigned
- Expected mechanism: Fixes the directional polymer-removal particle to stick on first contact.
- Metrics affected: ["polymer_floor_clearance", "wall_protection"]
- Known interactions: ["removal sticking x via geometry"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `untested`; confidence: high for wiring; no physical calibration
- Supporting experiment: The wrapper hard-codes stickingProbability to 1.0.
- Range provenance: Fixed implementation value, not a qualified range.

#### `bosch_polymer_deposition_source_exponent` — bosch polymer deposition source exponent

- Owner/API: `SingleParticleProcess.sourceExponent for depo_model`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless angular exponent / ViennaPS API default / ["API default"]
- Current best: not assigned
- Expected mechanism: Would change the angular distribution used for polymer deposition; the wrapper currently accepts the ViennaPS default.
- Metrics affected: ["polymer_conformality", "wall_protection", "depth", "bow"]
- Known interactions: ["deposition source exponent x sticking", "deposition source exponent x aspect ratio"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `untested`; confidence: high for omission; default value not asserted
- Supporting experiment: The active polymer-deposition constructor does not pass sourceExponent.
- Range provenance: API input is visible but no wrapper range is defined.

#### `bosch_ion_rate` — bosch ion rate

- Owner/API: `bosch_etch(ion_rate) / rate_fn`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation velocity coefficient / -0.1 / [-0.2, -0.05]
- Current best: not assigned
- Expected mechanism: Scales the ion-flux contribution to surface velocity.
- Metrics affected: ["depth", "bottom_shape", "cd_profile"]
- Known interactions: ["ion_rate x source exponent", "ion_rate x etch_time", "ion_rate x theta_r_min"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: high for wiring; low for physical mapping
- Supporting experiment: The 500-ray factor-pair export includes ion-rate cases. Their range and effects remain unqualified for a new screen.
- Range provenance: Saved model-sensitivity endpoints only; range requalification required.

#### `bosch_rays_per_point` — bosch rays per point

- Owner/API: `bosch_etch(rays_per_point) / RayTracingParameters.raysPerPoint`
- Classification / implementation: `numerical_control` / `wired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: rays per surface point / 1000 / [250, 500, 1000, 2000, 4000]
- Current best: not assigned
- Expected mechanism: Controls Monte Carlo flux sampling density.
- Metrics affected: ["depth", "cd_profile", "bow", "run_variance"]
- Known interactions: ["rays x grid_delta", "rays x source exponent"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: medium
- Supporting experiment: Foundation CTQ qualification found ray-count effects smaller than unresolved grid bias over 250-4000 for the tested recipe.
- Range provenance: Numerical-convergence range.

#### `bosch_rng_seed` — bosch rng seed

- Owner/API: `bosch_etch(rng_seed) / RayTracingParameters.rngSeed`
- Classification / implementation: `numerical_control` / `wired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: integer seed / not assigned / ["explicit fixed seeds in foundation manifests"]
- Current best: not assigned
- Expected mechanism: Selects reproducible ray-tracing streams; each process phase offsets the base seed.
- Metrics affected: ["replicate_identity", "run_variance"]
- Known interactions: ["seed x rays_per_point", "seed x geometry"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `confirmed`; confidence: high
- Supporting experiment: Fixed-seed thread-control and convergence campaigns.
- Range provenance: Reproducibility control; not a physical range.

#### `bosch_on_cycle` — bosch on cycle

- Owner/API: `bosch_etch(on_cycle)`
- Classification / implementation: `numerical_control` / `wired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: callable or null / not assigned / [null, "cycle-history callback"]
- Current best: not assigned
- Expected mechanism: Captures intermediate geometry after each etch cycle without intentionally changing physics.
- Metrics affected: ["cycle_depth", "cycle_cd", "cycle_topology"]
- Known interactions: []
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `confirmed`; confidence: high
- Supporting experiment: Foundation cycle-history runner.
- Range provenance: Observation callback; excluded from DOE factors.

#### `bosch_on_polymer` — bosch on polymer

- Owner/API: `bosch_etch(on_polymer)`
- Classification / implementation: `numerical_control` / `wired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: callable or null / not assigned / [null, "polymer-history callback"]
- Current best: not assigned
- Expected mechanism: Captures passivation morphology before punch-through.
- Metrics affected: ["polymer_thickness", "polymer_continuity"]
- Known interactions: []
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: medium
- Supporting experiment: Bosch resolution audit saved intermediate polymer states.
- Range provenance: Observation callback; excluded from DOE factors.

#### `ion_theta_r_max` — ion theta r max

- Owner/API: `MultiParticleProcess.addIonParticle(thetaRMax)`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degrees / 90.0 / not assigned
- Current best: not assigned
- Expected mechanism: Sets the upper angle of the ion sticking transition.
- Metrics affected: ["reflected_ion_flux", "cd_profile"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API default only.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `ion_min_angle` — ion min angle

- Owner/API: `MultiParticleProcess.addIonParticle(minAngle)`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degrees / 80.0 / not assigned
- Current best: not assigned
- Expected mechanism: Sets the minimum reflection angle in the ion model.
- Metrics affected: ["reflected_ion_flux", "bottom_shape"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API default only.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `ion_b_sp` — ion b sp

- Owner/API: `MultiParticleProcess.addIonParticle(B_sp)`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless yield coefficient / -1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Controls the angular sputtering-yield term.
- Metrics affected: ["ion_removal", "wall_shape"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API default only.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `ion_mean_energy` — ion mean energy

- Owner/API: `MultiParticleProcess.addIonParticle(meanEnergy)`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model energy / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Sets mean initial ion energy when the energy model is enabled.
- Metrics affected: ["ion_removal", "reflection_energy"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API default only; current rate law does not calibrate energy.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `ion_sigma_energy` — ion sigma energy

- Owner/API: `MultiParticleProcess.addIonParticle(sigmaEnergy)`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model energy / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Sets ion-energy spread.
- Metrics affected: ["ion_removal_variance"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API default only.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `ion_threshold_energy` — ion threshold energy

- Owner/API: `MultiParticleProcess.addIonParticle(thresholdEnergy)`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model energy / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Sets the sputtering threshold energy.
- Metrics affected: ["ion_removal", "selectivity"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API default only.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `ion_inflect_angle` — ion inflect angle

- Owner/API: `MultiParticleProcess.addIonParticle(inflectAngle)`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degrees / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Sets the reflected-ion energy-law inflection angle.
- Metrics affected: ["reflection_energy", "bottom_shape"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API default only.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `ion_energy_exponent_n` — ion energy exponent n

- Owner/API: `MultiParticleProcess.addIonParticle(n)`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless exponent / 1 / not assigned
- Current best: not assigned
- Expected mechanism: Shapes the reflected-ion energy-reduction curve.
- Metrics affected: ["reflection_energy", "wall_shape"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API default only.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `neutral_material_sticking` — neutral material sticking

- Owner/API: `MultiParticleProcess.addNeutralParticle(materialSticking)`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material-to-probability map / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Allows different neutral sticking probabilities on each material.
- Metrics affected: ["etch_selectivity", "polymer_transport"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API available but current wrapper uses one scalar.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `drie_sf6_flow` — SF6 flow

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: sccm / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes fluorine supply and silicon chemical etch rate.
- Metrics affected: ["depth", "cd_profile", "bow", "scallop", "mask_remaining"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `drie_c4f8_flow` — C4F8 flow

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: sccm / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes fluorocarbon passivation supply.
- Metrics affected: ["depth", "cd_profile", "bow", "scallop", "mask_remaining"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `drie_chamber_pressure` — chamber pressure

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: Pa or mTorr / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes mean free path, angular transport, and radical density.
- Metrics affected: ["depth", "cd_profile", "bow", "scallop", "mask_remaining"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `drie_source_power` — ICP/source power

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: W / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes plasma density and reactive-species flux.
- Metrics affected: ["depth", "cd_profile", "bow", "scallop", "mask_remaining"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `drie_bias_power` — platen RF bias/power

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: W or V / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes vertical ion energy and passivation punch-through.
- Metrics affected: ["depth", "cd_profile", "bow", "scallop", "mask_remaining"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `drie_wafer_temperature` — wafer/chuck temperature

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degC / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes passivation stability and reaction rates.
- Metrics affected: ["depth", "cd_profile", "bow", "scallop", "mask_remaining"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `drie_physical_etch_time` — SF6 phase duration

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: s / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls etch dose per Bosch cycle.
- Metrics affected: ["depth", "cd_profile", "bow", "scallop", "mask_remaining"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `drie_physical_passivation_time` — C4F8 phase duration

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: s / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls passivation dose per cycle.
- Metrics affected: ["depth", "cd_profile", "bow", "scallop", "mask_remaining"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `drie_switching_transient` — gas switching/purge time

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: s / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes overlap and transient chemistry between cycle phases.
- Metrics affected: ["depth", "cd_profile", "bow", "scallop", "mask_remaining"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

### Liner

#### `liner_min_thickness_spec` — minimum local liner thickness

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 0.02 / [0.02, null]
- Current best: not assigned
- Expected mechanism: Requires actual interface-to-interface SiO2 thickness, not commanded dose.
- Metrics affected: ["liner_min_thickness", "liner_continuity"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Protects the barrier/seed from direct silicon contact.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `liner_coverage_spec` — minimum liner conformality

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: ratio / 0.995 / [0.995, 1.0]
- Current best: not assigned
- Expected mechanism: Bounds minimum/field local thickness after metric qualification.
- Metrics affected: ["liner_bottom_field", "liner_lower_wall_field"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Controls dielectric continuity available to barrier deposition.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `phase_factor_liner_thick` — liner_thick

- Owner/API: `deposit_conformal(thickness) / SingleParticleProcess.rate`
- Classification / implementation: `recipe_knob` / `legacy_only`
- DOE eligibility: `legacy_suspended`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: commanded simulation dose / not assigned / [0.018, 0.02, 0.024, 0.028, 0.035, 0.045]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.02}
- Expected mechanism: Scales the requested liner deposition velocity for a fixed unit duration.
- Metrics affected: ["actual_liner_thickness", "liner_conformality", "remaining_aperture"]
- Known interactions: ["liner dose x sticking", "liner dose x etched CD"]
- Upstream consequence: Consumes the etched opening.
- Downstream consequence: Constrains barrier access and final capacitance, which this model does not calculate.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Phase-one 1,948-row campaign; rankings and best values are suspended because several CTQs were invalid.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_liner_sticking` — liner_sticking

- Owner/API: `deposit_conformal(sticking) / SingleParticleProcess.stickingProbability`
- Classification / implementation: `model_coefficient` / `legacy_only`
- DOE eligibility: `legacy_suspended`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / 0.05 / [0.02, 0.08, 0.16, 0.24, 0.3, 0.35]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.24}
- Expected mechanism: Controls particle reflection and transport to the lower wall/floor.
- Metrics affected: ["liner_conformality", "liner_min_thickness"]
- Known interactions: ["liner sticking x aspect ratio", "liner sticking x dose"]
- Upstream consequence: None before the liner.
- Downstream consequence: Changes barrier access and dielectric continuity.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Phase-one 1,948-row campaign; rankings and best values are suspended because several CTQs were invalid.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `candidate_liner_single_particle_dose` — single-particle commanded dose

- Owner/API: `layer_process_models.deposit_single_particle(dose)`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / not assigned / [0.04]
- Current best: not assigned
- Expected mechanism: Scales the generic diffuse-reflection deposition velocity at fixed duration.
- Metrics affected: ["field_thickness", "minimum_local_thickness", "remaining_aperture"]
- Known interactions: ["dose x sticking probability", "dose x incoming via geometry"]
- Upstream consequence: Requires an accepted full-width Bosch geometry and explicit incoming material interfaces.
- Downstream consequence: Changes layer continuity, aperture, seed access, and the geometry inherited by Cu fill.
- Evidence: `screened`; confidence: high for code parameterization; low for physical applicability
- Supporting experiment: test_layer_process_models.py verifies parameter bounds and the expected full-width morphology response on an analytic via only; no Gate-0 traveler geometry has been accepted.
- Range provenance: Exact diagnostic values exercised by test_layer_process_models.py; not a DOE range or fab calibration.

#### `candidate_liner_single_particle_sticking` — single-particle sticking probability

- Owner/API: `layer_process_models.deposit_single_particle(sticking_probability)`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / not assigned / [0.01]
- Current best: not assigned
- Expected mechanism: Controls absorption versus diffuse reflection and therefore precursor access to the lower via.
- Metrics affected: ["floor_to_field_conformality", "lower_wall_to_field_conformality", "minimum_local_thickness"]
- Known interactions: ["sticking x aspect ratio", "sticking x reflection ceiling", "sticking x dose"]
- Upstream consequence: Requires an accepted full-width Bosch geometry and explicit incoming material interfaces.
- Downstream consequence: Changes layer continuity, aperture, seed access, and the geometry inherited by Cu fill.
- Evidence: `screened`; confidence: high for code parameterization; low for physical applicability
- Supporting experiment: test_layer_process_models.py verifies parameter bounds and the expected full-width morphology response on an analytic via only; no Gate-0 traveler geometry has been accepted.
- Range provenance: Exact diagnostic values exercised by test_layer_process_models.py; not a DOE range or fab calibration.

#### `single_particle_source_exponent` — single particle source exponent

- Owner/API: `SingleParticleProcess.sourceExponent`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless exponent / 1.0 / [1.0, 100.0, 1000.0]
- Current best: not assigned
- Expected mechanism: Controls the source angular distribution for liner transport.
- Metrics affected: ["liner_conformality"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `screened`; confidence: medium
- Supporting experiment: Legacy 1/100/1000 screen reported no validated effect.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `single_particle_material_rates` — single particle material rates

- Owner/API: `SingleParticleProcess.materialRates`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material-to-rate map / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Allows material-dependent deposition/etch rates.
- Metrics affected: ["layer_thickness", "material_survival"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API available but not wired.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `teos_p1_sticking` — teos p1 sticking

- Owner/API: `TEOSDeposition.stickingProbabilityP1`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / not assigned / [0.01]
- Current best: not assigned
- Expected mechanism: Primary TEOS precursor sticking.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: test_layer_process_models.py exercised the installed coverage-coupled TEOS model on an analytic full-width via and showed it is not numerically equivalent to the generic single-particle model.
- Range provenance: Exact diagnostic value only; model-acceptance range has not yet been frozen.

#### `teos_p1_rate` — teos p1 rate

- Owner/API: `TEOSDeposition.rateP1`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model deposition rate / not assigned / [0.04]
- Current best: not assigned
- Expected mechanism: Primary TEOS contribution rate.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: test_layer_process_models.py exercised the installed coverage-coupled TEOS model on an analytic full-width via and showed it is not numerically equivalent to the generic single-particle model.
- Range provenance: Exact diagnostic value only; model-acceptance range has not yet been frozen.

#### `teos_p1_order` — teos p1 order

- Owner/API: `TEOSDeposition.orderP1`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: reaction order / not assigned / [1.0]
- Current best: not assigned
- Expected mechanism: Primary TEOS reaction-order response.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: test_layer_process_models.py exercised the installed coverage-coupled TEOS model on an analytic full-width via and showed it is not numerically equivalent to the generic single-particle model.
- Range provenance: Exact diagnostic value only; model-acceptance range has not yet been frozen.

#### `teos_p2_sticking` — teos p2 sticking

- Owner/API: `TEOSDeposition.stickingProbabilityP2`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Secondary TEOS precursor sticking.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_p2_rate` — teos p2 rate

- Owner/API: `TEOSDeposition.rateP2`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model deposition rate / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Secondary TEOS contribution rate.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_p2_order` — teos p2 order

- Owner/API: `TEOSDeposition.orderP2`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: reaction order / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Secondary TEOS reaction-order response.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_pecvd_radical_sticking` — teos pecvd radical sticking

- Owner/API: `TEOSPECVD.stickingProbabilityRadical`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Radical sticking and lower-via transport.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_pecvd_radical_rate` — teos pecvd radical rate

- Owner/API: `TEOSPECVD.depositionRateRadical`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model deposition rate / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Radical deposition contribution.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_pecvd_ion_rate` — teos pecvd ion rate

- Owner/API: `TEOSPECVD.depositionRateIon`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model deposition rate / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Ion-assisted deposition contribution.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_pecvd_ion_exponent` — teos pecvd ion exponent

- Owner/API: `TEOSPECVD.exponentIon`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless exponent / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Ion angular collimation.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_pecvd_ion_sticking` — teos pecvd ion sticking

- Owner/API: `TEOSPECVD.stickingProbabilityIon`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Ion sticking probability.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_pecvd_radical_order` — teos pecvd radical order

- Owner/API: `TEOSPECVD.reactionOrderRadical`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: reaction order / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Radical reaction order.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_pecvd_ion_order` — teos pecvd ion order

- Owner/API: `TEOSPECVD.reactionOrderIon`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: reaction order / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Ion reaction order.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `teos_pecvd_min_ion_angle` — teos pecvd min ion angle

- Owner/API: `TEOSPECVD.minAngleIon`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degrees / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Minimum ion-angle control.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `liner_teos_flow` — TEOS flow

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: sccm or mass flow / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes precursor supply for oxide growth.
- Metrics affected: ["local_thickness", "conformality", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `liner_ozone_flow` — O3/oxidant flow

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: sccm / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes oxidation kinetics and film quality.
- Metrics affected: ["local_thickness", "conformality", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `liner_temperature` — liner deposition temperature

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degC / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes reaction rate, surface mobility, and film density.
- Metrics affected: ["local_thickness", "conformality", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `liner_pressure` — liner chamber pressure

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: Pa or Torr / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes transport and conformality.
- Metrics affected: ["local_thickness", "conformality", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `liner_deposition_time` — liner deposition time

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: s / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls deposited thickness for fixed chemistry.
- Metrics affected: ["local_thickness", "conformality", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `liner_chemistry_choice` — liner process/chemistry

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `structural_choice` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Selects SACVD, PECVD, ALD, or another physical mechanism.
- Metrics affected: ["local_thickness", "conformality", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `liner_model_family` — transport model choice

- Owner/API: `SingleParticleProcess/TEOS/ALD`
- Classification / implementation: `structural_choice` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / ["SingleParticleProcess", "TEOSDeposition", "IsotropicProcess metric control"]
- Current best: not assigned
- Expected mechanism: Selects the representable deposition mechanism and available coefficients.
- Metrics affected: ["all owning-step morphology CTQs", "model validity"]
- Known interactions: ["Every process coefficient in the selected model", "dimensionality", "grid resolution"]
- Upstream consequence: Defines what incoming state can be represented.
- Downstream consequence: May qualitatively change all later morphology and failure modes.
- Evidence: `screened`; confidence: high for the need to declare the choice; model winner not yet accepted
- Supporting experiment: test_layer_process_models.py confirms distinct full-width responses for the generic, TEOS, and ideal-isotropic control arms; none is yet accepted on Gate-0 geometries.
- Range provenance: Structural challenge arms, not an interpolated numeric range.

#### `liner_chemistry_uncalibrated` — liner chemistry uncalibrated

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: The current SingleParticle surrogate is not calibrated SACVD/PECVD/ALD chemistry.
- Metrics affected: ["physical_liner_recipe", "film_quality"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

### Barrier Seed

#### `barrier_min_thickness_spec` — minimum local barrier/seed thickness

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 0.012 / [0.012, null]
- Current best: not assigned
- Expected mechanism: Requires measured local layer thickness rather than input dose.
- Metrics affected: ["barrier_min_thickness", "seed_min_thickness", "layer_continuity"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Controls Cu isolation and seed access for plating.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `barrier_coverage_spec` — minimum barrier/seed conformality

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: ratio / 0.985 / [0.985, 1.0]
- Current best: not assigned
- Expected mechanism: Bounds minimum/field local thickness after separate material tracking.
- Metrics affected: ["barrier_bottom_field", "seed_bottom_field"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Constrains whether Cu plating has a continuous geometric seed path.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `phase_factor_barrier_thick` — barrier_thick

- Owner/API: `deposit_conformal(thickness) / DirectionalProcess.directionalVelocity`
- Classification / implementation: `recipe_knob` / `legacy_only`
- DOE eligibility: `legacy_suspended`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: commanded simulation dose / not assigned / [0.01, 0.012, 0.014, 0.018, 0.024]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.012}
- Expected mechanism: Scales the directional barrier/seed deposition distance.
- Metrics affected: ["barrier_thickness", "seed_thickness", "remaining_aperture"]
- Known interactions: ["barrier dose x barrier_iso", "barrier dose x etched CD"]
- Upstream consequence: Requires a qualified liner.
- Downstream consequence: Controls seed continuity and fill access.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Phase-one 1,948-row campaign; rankings and best values are suspended because several CTQs were invalid.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_barrier_iso` — barrier_iso

- Owner/API: `DirectionalProcess.isotropicVelocity / directionalVelocity`
- Classification / implementation: `model_coefficient` / `legacy_only`
- DOE eligibility: `legacy_suspended`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: ratio / 0.3 / [0.0, 0.1, 0.2, 0.4]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.0}
- Expected mechanism: Mixes isotropic and vertical components in the geometric deposition surrogate.
- Metrics affected: ["barrier_conformality", "seed_conformality", "remaining_aperture"]
- Known interactions: ["barrier_iso x barrier dose", "barrier_iso x aspect ratio"]
- Upstream consequence: Requires the lined profile.
- Downstream consequence: Changes bottom coverage and mouth pinch-off risk.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Phase-one 1,948-row campaign; rankings and best values are suspended because several CTQs were invalid.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `candidate_barrier_seed_field_dose` — constant horizontal-field dose

- Owner/API: `layer_process_models.deposit_directional_fraction(field_dose)`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / not assigned / [0.04]
- Current best: not assigned
- Expected mechanism: Holds total nominal field growth fixed while the directional/isotropic split changes.
- Metrics affected: ["field_thickness", "minimum_local_thickness", "remaining_aperture"]
- Known interactions: ["field dose x isotropic fraction", "field dose x incoming aperture"]
- Upstream consequence: Requires an accepted full-width Bosch geometry and explicit incoming material interfaces.
- Downstream consequence: Changes layer continuity, aperture, seed access, and the geometry inherited by Cu fill.
- Evidence: `screened`; confidence: high for code parameterization; low for physical applicability
- Supporting experiment: test_layer_process_models.py verifies parameter bounds and the expected full-width morphology response on an analytic via only; no Gate-0 traveler geometry has been accepted.
- Range provenance: Exact diagnostic values exercised by test_layer_process_models.py; not a DOE range or fab calibration.

#### `candidate_barrier_seed_isotropic_fraction` — isotropic fraction of fixed field dose

- Owner/API: `layer_process_models.deposit_directional_fraction(isotropic_fraction)`
- Classification / implementation: `model_coefficient` / `wired_model_acceptance_candidate`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: fraction / not assigned / [0.0, 0.5, 1.0]
- Current best: not assigned
- Expected mechanism: Redistributes a fixed field dose between vertical line-of-sight and isotropic normal growth without increasing total field dose.
- Metrics affected: ["wall_to_field_conformality", "floor_to_field_conformality", "remaining_aperture"]
- Known interactions: ["isotropic fraction x aspect ratio", "isotropic fraction x field dose", "isotropic fraction x material sequence"]
- Upstream consequence: Requires an accepted full-width Bosch geometry and explicit incoming material interfaces.
- Downstream consequence: Changes layer continuity, aperture, seed access, and the geometry inherited by Cu fill.
- Evidence: `screened`; confidence: high for code parameterization; low for physical applicability
- Supporting experiment: test_layer_process_models.py verifies parameter bounds and the expected full-width morphology response on an analytic via only; no Gate-0 traveler geometry has been accepted.
- Range provenance: Exact diagnostic values exercised by test_layer_process_models.py; not a DOE range or fab calibration.

#### `barrier_target_material` — barrier/adhesion material stack

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `structural_choice` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Selects TaN/Ta or another diffusion/adhesion stack.
- Metrics affected: ["barrier_thickness", "seed_thickness", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `barrier_ar_pressure` — Ar flow/pressure

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: sccm and Pa / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes sputter transport and scattering.
- Metrics affected: ["barrier_thickness", "seed_thickness", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `barrier_n2_flow` — N2 reactive-sputter flow

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: sccm / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes TaN formation and composition.
- Metrics affected: ["barrier_thickness", "seed_thickness", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `barrier_target_power` — sputter target power

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: W / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes metal flux and ionization.
- Metrics affected: ["barrier_thickness", "seed_thickness", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `barrier_substrate_bias` — substrate bias

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: V / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Steers ionized metal into the via.
- Metrics affected: ["barrier_thickness", "seed_thickness", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `barrier_temperature` — substrate temperature

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degC / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes adhesion, mobility, and film properties.
- Metrics affected: ["barrier_thickness", "seed_thickness", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `barrier_deposition_time` — barrier/seed deposition times

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: s per material / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls each distinct layer thickness.
- Metrics affected: ["barrier_thickness", "seed_thickness", "continuity", "aperture"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `barrier_seed_material_stack` — SiO2/TaN/(Ta)/Cu seed

- Owner/API: `explicit level-set material order`
- Classification / implementation: `structural_choice` / `fixed_or_challenge_planned`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Keeps barrier, adhesion, seed, and plated Cu distinguishable for thickness and CMP selectivity.
- Metrics affected: ["all owning-step morphology CTQs", "model validity"]
- Known interactions: ["Every process coefficient in the selected model", "dimensionality", "grid resolution"]
- Upstream consequence: Defines what incoming state can be represented.
- Downstream consequence: May qualitatively change all later morphology and failure modes.
- Evidence: `confirmed`; confidence: high for the need to declare the choice; model winner not yet accepted
- Supporting experiment: RESEARCH_PLAN_V2 controlled model challenges and foundation audit.
- Range provenance: Structural challenge arms, not an interpolated numeric range.

#### `barrier_seed_transport_uncalibrated` — barrier seed transport uncalibrated

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: The current geometric directional surrogate is not calibrated iPVD or ALD.
- Metrics affected: ["physical_barrier_recipe", "seed_electrical_continuity"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

### Cu Fill

#### `fill_overburden_spec` — minimum Cu overburden

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 0.15 / [0.15, null]
- Current best: not assigned
- Expected mechanism: Requires void-free closure plus positive measured Cu height above the field plane.
- Metrics affected: ["fill_height", "minimum_overburden", "overburden_nonuniformity"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Provides removable Cu for CMP.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `fill_void_spec` — internal void/seam target

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: count/area / 0 / [0, 0]
- Current best: not assigned
- Expected mechanism: Requires no open cavity, sealed void, or seam under the qualified topology metric.
- Metrics affected: ["void_count", "void_area", "maximum_void_size", "seam_length"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: A void invalidates CMP and the complete traveler.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `phase_factor_fill_thick` — fill_thick

- Owner/API: `cu_fill(thickness) / deposition velocity`
- Classification / implementation: `recipe_knob` / `legacy_only`
- DOE eligibility: `legacy_suspended`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: commanded simulation dose / not assigned / [0.12, 0.14, 0.15, 0.155, 0.16, 0.18, 0.22, 0.26]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.22}
- Expected mechanism: Scales the legacy geometric Cu deposition distance; it is not final Cu thickness.
- Metrics affected: ["fill_height", "void_topology", "overburden"]
- Known interactions: ["fill dose x fill_iso", "fill dose x seed geometry"]
- Upstream consequence: Requires a connected seed geometry.
- Downstream consequence: Sets CMP overburden and inherited topography.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Phase-one 1,948-row campaign; rankings and best values are suspended because several CTQs were invalid.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `phase_factor_fill_iso` — fill_iso

- Owner/API: `DirectionalProcess.isotropicVelocity / directionalVelocity`
- Classification / implementation: `model_coefficient` / `legacy_only`
- DOE eligibility: `legacy_suspended`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: ratio / 0.2 / [0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.6]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 0.05}
- Expected mechanism: Mixes isotropic and vertical growth in the legacy fill negative control.
- Metrics affected: ["void_topology", "pinch_off", "fill_height"]
- Known interactions: ["fill_iso x fill dose", "fill_iso x via CD"]
- Upstream consequence: Requires the seeded geometry.
- Downstream consequence: Changes the void/pinch-off morphology presented to CMP.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Phase-one 1,948-row campaign; rankings and best values are suspended because several CTQs were invalid.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `fill_directional` — fill directional

- Owner/API: `cu_fill(directional)`
- Classification / implementation: `structural_choice` / `wired`
- DOE eligibility: `excluded_rejected`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: boolean / false / [false, true]
- Current best: not assigned
- Expected mechanism: Chooses isotropic deposition or the legacy directional geometric surrogate.
- Metrics affected: ["fill_height", "void_topology", "pinch_off"]
- Known interactions: ["model choice x fill dose", "model choice x via geometry"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `rejected`; confidence: high
- Supporting experiment: Legacy model pair is retained only as a negative control; it has not produced the required fill morphology.
- Range provenance: Structural negative-control comparison.

#### `candidate_fill_suppressor_sticking_probability` — suppressorStickingProbability

- Owner/API: `CopperSuppressionFillParams.suppressorStickingProbability / CopperSuppressionFill`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / 0.1 / [0.0, 0.2]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.2}
- Expected mechanism: Controls suppressor absorption versus diffuse reflection and also multiplies the local adsorption term.
- Metrics affected: ["suppressor_flux", "equilibrium_coverage", "local_deposition_velocity", "bottom_to_field_velocity_ratio", "fill_topology", "overburden"]
- Known interactions: ["sticking x ray-access flux", "sticking x adsorptionStrength", "sticking x aspect ratio"]
- Upstream consequence: Requires a qualified full-domain geometry and an explicit continuous Cu-seed material level set.
- Downstream consequence: Changes void closure, overburden, and the Cu topography inherited by CMP.
- Evidence: `screened`; confidence: medium for numerical behavior; low for morphology sensitivity
- Supporting experiment: Isolated flat and full-via rate-field checks exercised sticking=0 and 0.2; 1.1 is an invalid-input guard, not a tested process value. Evidence is limited to test_copper_suppression_fill.py isolated controls; no production morphology DOE has accepted this parameter.
- Range provenance: Exact isolated-control values and the staged foundation manifest; no fab-calibrated range.

#### `candidate_fill_suppressor_source_power` — suppressorSourcePower

- Owner/API: `CopperSuppressionFillParams.suppressorSourcePower / CopperSuppressionFill`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless angular exponent / 1.0 / [1.0]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 1.0}
- Expected mechanism: Shapes the angular distribution of suppressor rays entering the feature.
- Metrics affected: ["suppressor_flux", "equilibrium_coverage", "local_deposition_velocity", "bottom_to_field_velocity_ratio", "fill_topology", "overburden"]
- Known interactions: ["source power x via aspect ratio", "source power x sticking", "source power x ray normalization"]
- Upstream consequence: Requires a qualified full-domain geometry and an explicit continuous Cu-seed material level set.
- Downstream consequence: Changes void closure, overburden, and the Cu topography inherited by CMP.
- Evidence: `screened`; confidence: high for API wiring; low for sensitivity
- Supporting experiment: The isolated rate-field controls exercised sourcePower=1 only; no sensitivity ranking or production DOE exists. Evidence is limited to test_copper_suppression_fill.py isolated controls; no production morphology DOE has accepted this parameter.
- Range provenance: Exact isolated-control values and the staged foundation manifest; no fab-calibrated range.

#### `candidate_fill_gas_mean_free_path` — gasMeanFreePath

- Owner/API: `CopperSuppressionFillParams.gasMeanFreePath / CopperSuppressionFill`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / -1.0 / [-1.0]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": -1.0}
- Expected mechanism: Sets the ray-transport mean free path; -1 retains the ViennaRay no-gas-collision sentinel behavior.
- Metrics affected: ["suppressor_flux", "equilibrium_coverage", "local_deposition_velocity", "bottom_to_field_velocity_ratio", "fill_topology", "overburden"]
- Known interactions: ["mean free path x feature depth", "mean free path x source power", "mean free path x sticking"]
- Upstream consequence: Requires a qualified full-domain geometry and an explicit continuous Cu-seed material level set.
- Downstream consequence: Changes void closure, overburden, and the Cu topography inherited by CMP.
- Evidence: `screened`; confidence: high for API wiring; low for finite-transport applicability
- Supporting experiment: The isolated rate-field controls and staged trajectory use the -1 default only; finite mean-free-path behavior is untested. Evidence is limited to test_copper_suppression_fill.py isolated controls; no production morphology DOE has accepted this parameter.
- Range provenance: Exact isolated-control values and the staged foundation manifest; no fab-calibrated range.

#### `candidate_fill_adsorption_strength` — adsorptionStrength

- Owner/API: `CopperSuppressionFillParams.adsorptionStrength / CopperSuppressionFill`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: combined model adsorption coefficient / 1.0 / {"finite_numerical_guard": [1e+150], "isolated_rate_field": [0.0, 0.25, 5.0]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": [0.1, 0.25, 0.5]}
- Expected mechanism: Scales suppressor uptake as a combined adsorption coefficient times suppressor activity; larger values increase equilibrium suppression where flux reaches the surface.
- Metrics affected: ["suppressor_flux", "equilibrium_coverage", "local_deposition_velocity", "bottom_to_field_velocity_ratio", "fill_topology", "overburden"]
- Known interactions: ["adsorptionStrength x sticking x suppressor flux", "adsorptionStrength x deactivationRate", "adsorptionStrength x deposition rates"]
- Upstream consequence: Requires a qualified full-domain geometry and an explicit continuous Cu-seed material level set.
- Downstream consequence: Changes void closure, overburden, and the Cu topography inherited by CMP.
- Evidence: `screened`; confidence: medium for equilibrium response; low for physical identifiability
- Supporting experiment: Isolated flat/rate-field tests exercised 0, 0.25, and 5; 1e150 is only an overflow guard. The 0.1/0.25/0.5 trajectory arms are staged, not completed evidence. Evidence is limited to test_copper_suppression_fill.py isolated controls; no production morphology DOE has accepted this parameter.
- Range provenance: Exact isolated-control values and the staged foundation manifest; no fab-calibrated range.

#### `candidate_fill_deactivation_rate` — deactivationRate

- Owner/API: `CopperSuppressionFillParams.deactivationRate / CopperSuppressionFill`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model inverse deposited length / 1.0 / [0.25]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.25}
- Expected mechanism: Removes suppressor coverage in proportion to local Cu growth velocity in the quasi-steady balance.
- Metrics affected: ["suppressor_flux", "equilibrium_coverage", "local_deposition_velocity", "bottom_to_field_velocity_ratio", "fill_topology", "overburden"]
- Known interactions: ["deactivationRate x adsorptionStrength", "deactivationRate x activeDepositionRate", "deactivationRate x suppressedDepositionRate"]
- Upstream consequence: Requires a qualified full-domain geometry and an explicit continuous Cu-seed material level set.
- Downstream consequence: Changes void closure, overburden, and the Cu topography inherited by CMP.
- Evidence: `screened`; confidence: high for equation wiring; low for sensitivity and calibration
- Supporting experiment: The isolated rate-field controls exercised deactivationRate=0.25 only; no coefficient sweep or production DOE exists. Evidence is limited to test_copper_suppression_fill.py isolated controls; no production morphology DOE has accepted this parameter.
- Range provenance: Exact isolated-control values and the staged foundation manifest; no fab-calibrated range.

#### `candidate_fill_active_deposition_rate` — activeDepositionRate

- Owner/API: `CopperSuppressionFillParams.activeDepositionRate / CopperSuppressionFill`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length per simulation time / 1.0 / [0.2]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.2}
- Expected mechanism: Sets the Cu growth velocity on an unsuppressed surface.
- Metrics affected: ["suppressor_flux", "equilibrium_coverage", "local_deposition_velocity", "bottom_to_field_velocity_ratio", "fill_topology", "overburden"]
- Known interactions: ["active rate x process duration", "active rate x deactivationRate", "active rate x suppressed rate"]
- Upstream consequence: Requires a qualified full-domain geometry and an explicit continuous Cu-seed material level set.
- Downstream consequence: Changes void closure, overburden, and the Cu topography inherited by CMP.
- Evidence: `screened`; confidence: high for limiting-rate behavior; low for physical calibration
- Supporting experiment: The isolated rate-field controls exercised activeDepositionRate=0.2; an active rate below the suppressed rate is tested only as a rejected input. Evidence is limited to test_copper_suppression_fill.py isolated controls; no production morphology DOE has accepted this parameter.
- Range provenance: Exact isolated-control values and the staged foundation manifest; no fab-calibrated range.

#### `candidate_fill_suppressed_deposition_rate` — suppressedDepositionRate

- Owner/API: `CopperSuppressionFillParams.suppressedDepositionRate / CopperSuppressionFill`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length per simulation time / 0.01 / [0.01]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.01}
- Expected mechanism: Sets residual Cu growth under complete suppressor coverage.
- Metrics affected: ["suppressor_flux", "equilibrium_coverage", "local_deposition_velocity", "bottom_to_field_velocity_ratio", "fill_topology", "overburden"]
- Known interactions: ["suppressed rate x active rate", "suppressed rate x deactivationRate", "suppressed rate x process duration"]
- Upstream consequence: Requires a qualified full-domain geometry and an explicit continuous Cu-seed material level set.
- Downstream consequence: Changes void closure, overburden, and the Cu topography inherited by CMP.
- Evidence: `screened`; confidence: high for limiting-rate behavior; low for physical calibration
- Supporting experiment: The isolated rate-field controls exercised suppressedDepositionRate=0.01; a larger-than-active value is tested only as a rejected input. Evidence is limited to test_copper_suppression_fill.py isolated controls; no production morphology DOE has accepted this parameter.
- Range provenance: Exact isolated-control values and the staged foundation manifest; no fab-calibrated range.

#### `candidate_fill_plating_materials` — platingMaterials

- Owner/API: `CopperSuppressionFillParams.platingMaterials / CopperSuppressionFill`
- Classification / implementation: `structural_choice` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material enum list / ["Material.Cu"] / [["Material.Cu"], ["registered CuSeed", "Material.Cu"], ["Material.Si", "Material.Cu"]]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": ["registered CuSeed", "Material.Cu"]}
- Expected mechanism: Gates positive growth to the electrically connected Cu seed and plated-Cu level sets while keeping dielectric and barrier surfaces stationary.
- Metrics affected: ["suppressor_flux", "equilibrium_coverage", "local_deposition_velocity", "bottom_to_field_velocity_ratio", "fill_topology", "overburden"]
- Known interactions: ["material identity x explicit level-set order", "seed continuity x Cu handoff"]
- Upstream consequence: Requires a qualified full-domain geometry and an explicit continuous Cu-seed material level set.
- Downstream consequence: Changes void closure, overburden, and the Cu topography inherited by CMP.
- Evidence: `screened`; confidence: high for the material gate; low for electrical seed realism
- Supporting experiment: Isolated seed-to-Cu handoff and dielectric-gate tests confirm the code path only; they do not establish a physical plating recipe. Evidence is limited to test_copper_suppression_fill.py isolated controls; no production morphology DOE has accepted this parameter.
- Range provenance: Exact isolated-control values and the staged foundation manifest; no fab-calibrated range.

#### `api_AdvectionParameters_ignoreVoids` — ignoreVoids

- Owner/API: `AdvectionParameters.ignoreVoids`
- Classification / implementation: `numerical_control` / `required_candidate_void_guard`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / false / [false, true]
- Current best: {"source": "test_copper_suppression_fill.py sealed-void control", "status": "mandatory_validity_guard", "value": true}
- Expected mechanism: Freezes inaccessible enclosed-void interfaces during advection so trapped voids cannot spuriously heal from zero-flux reactivation.
- Metrics affected: ["closed_void_count", "closed_void_area", "void_topology", "target_pass"]
- Known interactions: ["void accessibility", "local suppressor flux", "topology checkpointing"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Without the guard, false void healing can invalidate fill acceptance and the CMP input geometry.
- Evidence: `confirmed`; confidence: high for the void-preservation guard
- Supporting experiment: A controlled sealed void shrank when ignoreVoids=false and was preserved exactly when true; true is mandatory for candidate-fill execution.
- Range provenance: Exact false/true sealed-void control; true is a validity guard, not an optimization factor.

#### `surface_diffusion_radius` — surface diffusion radius

- Owner/API: `SurfaceDiffusionParameters.radius`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Neighborhood radius for surface-coverage diffusion.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `surface_diffusion_neighbors` — surface diffusion neighbors

- Owner/API: `SurfaceDiffusionParameters.kNeighbors`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: count / 16 / not assigned
- Current best: not assigned
- Expected mechanism: Neighbor count for surface diffusion.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `surface_diffusion_normal_cutoff` — surface diffusion normal cutoff

- Owner/API: `SurfaceDiffusionParameters.normalCutoff`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless / 0.25 / not assigned
- Current best: not assigned
- Expected mechanism: Excludes strongly misaligned surface neighbors.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `surface_diffusion_sigma_normal` — surface diffusion sigma normal

- Owner/API: `SurfaceDiffusionParameters.sigmaNormal`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless / 0.35 / not assigned
- Current best: not assigned
- Expected mechanism: Normal-alignment weighting width.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `surface_diffusion_stability` — surface diffusion stability

- Owner/API: `SurfaceDiffusionParameters.stabilityFactor`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Numerical stability scale for diffusion.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `fill_current_density` — plating current density

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: A/area / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Sets electrochemical Cu deposition rate.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_current_waveform` — plating current waveform

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: current versus time / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls initiation, bottom-up acceleration, and bulk fill.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_total_charge` — plated charge/time

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: C/area or s / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Sets total Cu inventory.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_copper_sulfate` — CuSO4 concentration

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: mol/L / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Sets available Cu-ion concentration.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_sulfuric_acid` — H2SO4 concentration

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: mol/L / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls electrolyte conductivity and kinetics.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_chloride` — chloride concentration

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: mol/L / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Couples suppressor/accelerator adsorption chemistry.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_suppressor` — suppressor concentration

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: mol/L or ppm / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Inhibits deposition, especially near the field/mouth.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_accelerator` — accelerator concentration

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: mol/L or ppm / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Promotes bottom/corner growth through coverage-dependent kinetics.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_leveler` — leveler concentration

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: mol/L or ppm / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Suppresses overfill peaks and field growth.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_bath_temperature` — electrolyte temperature

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degC / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes transport, adsorption, and electrochemical kinetics.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_agitation` — wafer rotation/agitation

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: rpm or flow / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes boundary-layer transport into the via.
- Metrics affected: ["void_topology", "fill_height", "overburden", "pinch_off"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `fill_model_family` — legacy constant velocity versus reduced suppressor-access proxy versus a future calibrated mechanism

- Owner/API: `DirectionalProcess/CopperSuppressionFill/other calibrated model`
- Classification / implementation: `structural_choice` / `fixed_or_challenge_planned`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Determines whether bottom-up rate contrast, void closure, and overburden can be represented; the reduced candidate is a qualification model, not accepted electrochemistry.
- Metrics affected: ["all owning-step morphology CTQs", "model validity"]
- Known interactions: ["Every process coefficient in the selected model", "dimensionality", "grid resolution"]
- Upstream consequence: Defines what incoming state can be represented.
- Downstream consequence: May qualitatively change all later morphology and failure modes.
- Evidence: `boundary-limited`; confidence: high for the need to declare the choice; model winner not yet accepted
- Supporting experiment: RESEARCH_PLAN_V2 controlled model challenges and foundation audit.
- Range provenance: Structural challenge arms, not an interpolated numeric range.

#### `legacy_fill_missing_superfill` — legacy fill missing superfill

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Constant directional/isotropic velocity has no suppressor, accelerator, leveler, coverage feedback, or S-NDR/CEAC mechanism.
- Metrics affected: ["void_free_fill", "overburden", "physical_fill_recipe"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

#### `candidate_fill_reduced_physics` — candidate fill reduced physics

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: CopperSuppressionFill is a fixed-sticking ballistic-access proxy with a local quasi-steady suppressor balance. It omits transient chemistry, Cu-ion/electrolyte potential, accelerator and leveler fields, saturated-surface transport feedback, and a fab current waveform; it is not S-NDR or CEAC.
- Metrics affected: ["physical_fill_recipe", "mechanism_validation", "nominal_and_high_AR_extrapolation"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

#### `single_level_set_fill_merger` — single level set fill merger

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: The current single Cu interface removes long sub-resolution cavity tails when opposing fronts merge and cannot certify metallurgical seam continuity. Merger history must remain a hard failure unless an explicit seam-resolving representation is validated.
- Metrics affected: ["seam_free_fill", "centerline_merger", "fill_model_acceptance"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

### Cmp

#### `cmp_dish_spec` — Cu dish/recess target

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: simulation length / 0.0 / [0.0, 0.0]
- Current best: not assigned
- Expected mechanism: Requires the signed plug height to match the cleared field plane within a qualified tolerance.
- Metrics affected: ["cu_dish", "cu_protrusion"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Sets final planarity for subsequent integration.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `cmp_stop_survival_spec` — CMP stop-layer survival

- Owner/API: `program.md / tsv_process.TARGET_SPECS`
- Classification / implementation: `product_specification` / `output_target`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `assumed_comparison_band`
- Units / default / tested range: boolean / true / [true]
- Current best: not assigned
- Expected mechanism: Requires the declared hard mask or dielectric stop to remain; photoresist identity is not accepted.
- Metrics affected: ["stop_layer_loss", "material_survival"]
- Known interactions: []
- Upstream consequence: None; this is the first modeled stage.
- Downstream consequence: Prevents destructive polish from being ranked as an improvement.
- Evidence: `boundary-limited`; confidence: high for declared intent; low for physical calibration
- Supporting experiment: Declared study target; scoring is suspended pending CTQ qualification.
- Range provenance: Declared study target retained for continuity; physical-unit and tolerance provenance remain uncalibrated.

#### `phase_factor_cmp_mult` — cmp_mult

- Owner/API: `joint_process_doe.apply_cmp(mult)`
- Classification / implementation: `recipe_knob` / `legacy_only`
- DOE eligibility: `legacy_suspended`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: overburden multiple / not assigned / [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 3.0]
- Current best: {"source": "G009 g005_061_confirmed_reference under phase-one metrics", "status": "legacy_suspended", "value": 1.5}
- Expected mechanism: Multiplies a recipe-dependent overburden before one-rate isotropic removal.
- Metrics affected: ["field_clear", "dish", "material_loss"]
- Known interactions: ["cmp_mult x fill overburden", "cmp_mult x material selectivity"]
- Upstream consequence: Requires a filled geometry and derived target plane.
- Downstream consequence: Can erase mask, Cu, liner, or substrate; legacy winner is suspended.
- Evidence: `screened`; confidence: medium for code-path sensitivity; low for physical interpretation
- Supporting experiment: Phase-one 1,948-row campaign; rankings and best values are suspended because several CTQs were invalid.
- Range provenance: Model-sensitivity range assembled from wrapper defaults and earlier simulations; no fab calibration.

#### `cmp_target_y` — cmp target y

- Owner/API: `cmp_planarize(target_y) / joint apply_cmp`
- Classification / implementation: `recipe_knob` / `wired`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation height / not assigned / ["derived liner/field plane", 0.3]
- Current best: not assigned
- Expected mechanism: Sets the nominal planarization/endpoint plane.
- Metrics affected: ["field_clear", "dish", "erosion", "material_loss"]
- Known interactions: ["target_y x fill overburden", "target_y x selectivity"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: low for physical CMP
- Supporting experiment: Legacy target-plane and overpolish curves; conclusions suspended under the one-rate model.
- Range provenance: Derived model-space endpoint; no calibrated physical endpoint.

#### `cmp_isotropic_rate` — cmp isotropic rate

- Owner/API: `IsotropicProcess.rate`
- Classification / implementation: `model_coefficient` / `fixed_legacy_negative_control`
- DOE eligibility: `excluded_rejected`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation velocity / -1.0 / [-1.0]
- Current best: not assigned
- Expected mechanism: Moves every unmasked material inward at one normal velocity.
- Metrics affected: ["field_clear", "material_loss", "dish"]
- Known interactions: ["rate x process duration", "rate x material identity"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `rejected`; confidence: high
- Supporting experiment: Controlled audit showed one-rate removal can erase unrelated materials and cannot represent physical planarization.
- Range provenance: Legacy fixed negative control.

#### `cmp_material_rates` — cmp material rates

- Owner/API: `IsotropicProcess.materialRates/defaultRate`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material-to-velocity map / not assigned / ["single exploratory Cu-selectivity arm"]
- Current best: not assigned
- Expected mechanism: Assigns independent normal removal rates by material.
- Metrics affected: ["field_clear", "barrier_loss", "dielectric_erosion", "plug_loss"]
- Known interactions: ["selectivity x endpoint delay", "selectivity x stack identity"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: medium for API capability; low for CMP realism
- Supporting experiment: One exploratory legacy run; a controlled sweep remains open.
- Range provenance: API-available perfect-selectivity control; no calibration.

#### `cmp_mask_materials` — cmp mask materials

- Owner/API: `IsotropicProcess.maskMaterial(s)`
- Classification / implementation: `structural_choice` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material enum/list / Material.Undefined / ["Undefined", "declared stop layer"]
- Current best: not assigned
- Expected mechanism: Assigns zero removal to declared protected materials.
- Metrics affected: ["stop_layer_loss", "material_survival"]
- Known interactions: ["mask identity x target_y"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `untested`; confidence: medium
- Supporting experiment: Official API inspected; physical stop identity not frozen.
- Range provenance: API structural choice awaiting stack decision.

#### `cmp_planarize_cutoff` — cmp planarize cutoff

- Owner/API: `Planarize.cutoffHeight`
- Classification / implementation: `structural_choice` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation height / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Clips geometry at a plane and can serve as an ideal endpoint/morphology control.
- Metrics affected: ["field_clear", "ideal_planarity"]
- Known interactions: ["cutoff x input overburden"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `untested`; confidence: medium for API function
- Supporting experiment: Planned as an ideal endpoint control, not as physical CMP.
- Range provenance: API default; experiment not run.

#### `candidate_cmp_stop_height` — stopHeight

- Owner/API: `HeightMaterialCMPParams.stopHeight / HeightMaterialCMP`
- Classification / implementation: `structural_choice` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation height / 0.0 / ["derived SiO2 stop top"]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": "derived_from_stack"}
- Expected mechanism: Sets the height below which only residual contact remains; it is derived from the incoming stop surface rather than optimized as an arbitrary plane.
- Metrics affected: ["endpoint", "stop_loss", "dish", "plug_loss"]
- Known interactions: ["stop height x incoming topography", "stop height x compliance length"]
- Upstream consequence: Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.
- Downstream consequence: Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.
- Evidence: `screened`; confidence: high for API wiring; low for physical calibration
- Supporting experiment: Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.
- Range provenance: Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.

#### `candidate_cmp_compliance_length` — complianceLength

- Owner/API: `HeightMaterialCMPParams.complianceLength / HeightMaterialCMP`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / 0.1 / [0.1, 0.25]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.25}
- Expected mechanism: Sets the vertical transition over which the height-dependent contact weight rises from residual to full contact.
- Metrics affected: ["raised_feature_preference", "dish", "endpoint_window"]
- Known interactions: ["compliance length x overburden", "compliance length x residual contact"]
- Upstream consequence: Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.
- Downstream consequence: Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.
- Evidence: `screened`; confidence: high for API wiring; low for physical calibration
- Supporting experiment: Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.
- Range provenance: Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.

#### `candidate_cmp_residual_contact` — residualContact

- Owner/API: `HeightMaterialCMPParams.residualContact / HeightMaterialCMP`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: fraction / 0.05 / [0.05]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.05}
- Expected mechanism: Retains a uniform removal fraction even at or below the stop plane.
- Metrics affected: ["post_endpoint_loss", "dish", "stop_erosion", "plug_loss"]
- Known interactions: ["residual contact x overpolish", "residual contact x material rate"]
- Upstream consequence: Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.
- Downstream consequence: Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.
- Evidence: `screened`; confidence: high for API wiring; low for physical calibration
- Supporting experiment: Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.
- Range provenance: Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.

#### `candidate_cmp_plated_cu_rate` — platedCuRemovalRate

- Owner/API: `HeightMaterialCMPParams.platedCuRemovalRate / HeightMaterialCMP`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: relative removal rate / 1.0 / [1.0]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 1.0}
- Expected mechanism: Defines the reference plated-Cu removal rate in the uncalibrated height-by-material law.
- Metrics affected: ["Cu_clear", "dish", "plug_loss"]
- Known interactions: ["Cu rate x duration", "Cu rate x compliance length"]
- Upstream consequence: Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.
- Downstream consequence: Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.
- Evidence: `screened`; confidence: high for API wiring; low for physical calibration
- Supporting experiment: Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.
- Range provenance: Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.

#### `candidate_cmp_seed_material` — cuSeedMaterial

- Owner/API: `HeightMaterialCMPParams.cuSeedMaterial / HeightMaterialCMP`
- Classification / implementation: `structural_choice` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material enum / Material.Undefined / ["registered CuSeed"]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": "registered CuSeed"}
- Expected mechanism: Identifies the distinct Cu-seed level set so seed clearing is not conflated with plated Cu.
- Metrics affected: ["seed_clear", "material_survival", "endpoint_sequence"]
- Known interactions: ["seed identity x material stack", "seed identity x serialization"]
- Upstream consequence: Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.
- Downstream consequence: Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.
- Evidence: `screened`; confidence: high for API wiring; low for physical calibration
- Supporting experiment: Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.
- Range provenance: Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.

#### `candidate_cmp_seed_rate` — cuSeedRemovalRate

- Owner/API: `HeightMaterialCMPParams.cuSeedRemovalRate / HeightMaterialCMP`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: relative removal rate / 1.0 / [0.8, 1.0]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 1.0}
- Expected mechanism: Sets removal of the registered Cu-seed layer after plated-Cu field clear.
- Metrics affected: ["seed_clear", "endpoint_sequence", "plug_loss"]
- Known interactions: ["seed rate x seed thickness", "seed rate x overpolish"]
- Upstream consequence: Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.
- Downstream consequence: Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.
- Evidence: `screened`; confidence: high for API wiring; low for physical calibration
- Supporting experiment: Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.
- Range provenance: Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.

#### `candidate_cmp_tan_rate` — tantalumNitrideRemovalRate

- Owner/API: `HeightMaterialCMPParams.tantalumNitrideRemovalRate / HeightMaterialCMP`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: relative removal rate / 0.25 / [0.25]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.25}
- Expected mechanism: Sets TaN barrier removal relative to plated Cu.
- Metrics affected: ["barrier_clear", "endpoint_sequence", "stop_exposure"]
- Known interactions: ["TaN rate x barrier thickness", "TaN rate x overpolish"]
- Upstream consequence: Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.
- Downstream consequence: Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.
- Evidence: `screened`; confidence: high for API wiring; low for physical calibration
- Supporting experiment: Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.
- Range provenance: Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.

#### `candidate_cmp_sio2_rate` — siliconDioxideRemovalRate

- Owner/API: `HeightMaterialCMPParams.siliconDioxideRemovalRate / HeightMaterialCMP`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: relative removal rate / 0.01 / [0.01]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.01}
- Expected mechanism: Sets SiO2 stop-layer erosion relative to plated Cu.
- Metrics affected: ["stop_erosion", "stop_retention", "field_planarity"]
- Known interactions: ["SiO2 rate x overpolish", "SiO2 rate x stop thickness"]
- Upstream consequence: Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.
- Downstream consequence: Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.
- Evidence: `screened`; confidence: high for API wiring; low for physical calibration
- Supporting experiment: Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.
- Range provenance: Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.

#### `candidate_cmp_si_rate` — siliconRemovalRate

- Owner/API: `HeightMaterialCMPParams.siliconRemovalRate / HeightMaterialCMP`
- Classification / implementation: `model_coefficient` / `candidate_extension_qualification_only`
- DOE eligibility: `mechanism_or_measurement_gate_first`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: relative removal rate / 0.01 / [0.005, 0.01]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.01}
- Expected mechanism: Sets silicon loss if the protected stack is breached.
- Metrics affected: ["substrate_loss", "hard_failure"]
- Known interactions: ["Si rate x stop breach", "Si rate x overpolish"]
- Upstream consequence: Requires a void-free Cu plug, positive overburden, and an explicit SiO2/TaN/CuSeed/Cu stack.
- Downstream consequence: Determines field clearing, endpoint order, dish, stop erosion, plug loss, and whether the traveler survives CMP.
- Evidence: `screened`; confidence: high for API wiring; low for physical calibration
- Supporting experiment: Exact C++/Python parity and controlled analytic-stack tests only; no product CMP DOE or calibration exists.
- Range provenance: Exact default and qualification-control values from the hash-pinned extension; not a fab-calibrated range.

#### `candidate_cmp_overpolish_dose` — post-endpoint overpolish dose

- Owner/API: `foundation_cmp_qualification overpolish_doses / Process.duration`
- Classification / implementation: `recipe_knob` / `controlled_qualification_only`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation time/dose / 0.0 / [0.0, 0.0025, 0.005, 0.01, 0.02, 0.03]
- Current best: not assigned
- Expected mechanism: Advances the selected removal law beyond a named field-clear event to expose residual-metal versus erosion and plug-loss windows.
- Metrics affected: ["field_clear", "dish", "stop_erosion", "plug_height_loss", "plug_area_loss"]
- Known interactions: ["overpolish x every material rate", "overpolish x incoming overburden", "overpolish x compliance length"]
- Upstream consequence: Requires a named endpoint on an accepted incoming Cu topography.
- Downstream consequence: Excess dose can consume the stop, plug, liner, or substrate and is a hard failure.
- Evidence: `screened`; confidence: medium for model response; low for physical time mapping
- Supporting experiment: Controlled analytic-stack qualification ladder; product limits remain unset, so no best value exists.
- Range provenance: Predeclared numerical qualification ladder, not a production overpolish range.

#### `cmp_minimum_stop_retained_spec` — minimum retained stop thickness

- Owner/API: `program.md / foundation_cmp_qualification.REQUIRED_RESEARCH_SURVIVAL_THRESHOLDS`
- Classification / implementation: `product_specification` / `required_unset_blocks_cmp_doe`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `unresolved`
- Units / default / tested range: simulation length or fraction / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Defines the functional survival margin that CMP must preserve after field-metal clear.
- Metrics affected: ["stop_retained_thickness", "cmp_target_pass"]
- Known interactions: ["survival limit x endpoint", "survival limit x incoming stack", "survival limit x grid resolution"]
- Upstream consequence: Requires product or reliability provenance; it cannot be inferred from a favorable simulation.
- Downstream consequence: Until declared, quantitative CMP survival and the complete traveler remain blocked.
- Evidence: `untested`; confidence: high that the limit is required; absent for its numeric value
- Supporting experiment: The metric and boundary tests exist, but the authoritative limit is deliberately None.
- Range provenance: No declared value. A provenance-backed study limit is required before launch.

#### `cmp_maximum_stop_erosion_spec` — maximum stop erosion

- Owner/API: `program.md / foundation_cmp_qualification.REQUIRED_RESEARCH_SURVIVAL_THRESHOLDS`
- Classification / implementation: `product_specification` / `required_unset_blocks_cmp_doe`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `unresolved`
- Units / default / tested range: simulation length or fraction / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Defines the functional survival margin that CMP must preserve after field-metal clear.
- Metrics affected: ["stop_erosion", "cmp_target_pass"]
- Known interactions: ["survival limit x endpoint", "survival limit x incoming stack", "survival limit x grid resolution"]
- Upstream consequence: Requires product or reliability provenance; it cannot be inferred from a favorable simulation.
- Downstream consequence: Until declared, quantitative CMP survival and the complete traveler remain blocked.
- Evidence: `untested`; confidence: high that the limit is required; absent for its numeric value
- Supporting experiment: The metric and boundary tests exist, but the authoritative limit is deliberately None.
- Range provenance: No declared value. A provenance-backed study limit is required before launch.

#### `cmp_maximum_plug_height_loss_spec` — maximum plug-height loss

- Owner/API: `program.md / foundation_cmp_qualification.REQUIRED_RESEARCH_SURVIVAL_THRESHOLDS`
- Classification / implementation: `product_specification` / `required_unset_blocks_cmp_doe`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `unresolved`
- Units / default / tested range: simulation length or fraction / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Defines the functional survival margin that CMP must preserve after field-metal clear.
- Metrics affected: ["plug_height_loss", "cmp_target_pass"]
- Known interactions: ["survival limit x endpoint", "survival limit x incoming stack", "survival limit x grid resolution"]
- Upstream consequence: Requires product or reliability provenance; it cannot be inferred from a favorable simulation.
- Downstream consequence: Until declared, quantitative CMP survival and the complete traveler remain blocked.
- Evidence: `untested`; confidence: high that the limit is required; absent for its numeric value
- Supporting experiment: The metric and boundary tests exist, but the authoritative limit is deliberately None.
- Range provenance: No declared value. A provenance-backed study limit is required before launch.

#### `cmp_maximum_plug_area_loss_spec` — maximum plug-area loss fraction

- Owner/API: `program.md / foundation_cmp_qualification.REQUIRED_RESEARCH_SURVIVAL_THRESHOLDS`
- Classification / implementation: `product_specification` / `required_unset_blocks_cmp_doe`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `unresolved`
- Units / default / tested range: simulation length or fraction / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Defines the functional survival margin that CMP must preserve after field-metal clear.
- Metrics affected: ["plug_area_loss_fraction", "cmp_target_pass"]
- Known interactions: ["survival limit x endpoint", "survival limit x incoming stack", "survival limit x grid resolution"]
- Upstream consequence: Requires product or reliability provenance; it cannot be inferred from a favorable simulation.
- Downstream consequence: Until declared, quantitative CMP survival and the complete traveler remain blocked.
- Evidence: `untested`; confidence: high that the limit is required; absent for its numeric value
- Supporting experiment: The metric and boundary tests exist, but the authoritative limit is deliberately None.
- Range provenance: No declared value. A provenance-backed study limit is required before launch.

#### `csv_rates_file` — csv rates file

- Owner/API: `CSVFileProcess.ratesFile`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: file path / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Supplies a spatial velocity field for a phenomenological removal control.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `csv_direction` — csv direction

- Owner/API: `CSVFileProcess.direction`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: unit vector / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Defines directional orientation of the imported velocity field.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `csv_offset` — csv offset

- Owner/API: `CSVFileProcess.offset`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length vector / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Aligns imported rates to geometry coordinates.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `csv_isotropic_component` — csv isotropic component

- Owner/API: `CSVFileProcess.isotropicComponent`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model velocity multiplier / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Adds isotropic removal to the imported field.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `csv_directional_component` — csv directional component

- Owner/API: `CSVFileProcess.directionalComponent`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model velocity multiplier / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Scales directional removal from the imported field.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `csv_mask_materials` — csv mask materials

- Owner/API: `CSVFileProcess.maskMaterials`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material list / ["Material.Mask"] / not assigned
- Current best: not assigned
- Expected mechanism: Protects declared materials from the imported removal field.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `csv_visibility` — csv visibility

- Owner/API: `CSVFileProcess.calculateVisibility`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: boolean / true / not assigned
- Current best: not assigned
- Expected mechanism: Applies line-of-sight visibility to the field.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `csv_custom_interpolator` — csv custom interpolator

- Owner/API: `CSVFileProcess.setCustomInterpolator`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: callable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Maps coordinates/rates for a custom phenomenological contact hypothesis.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `cmp_downforce` — polish downforce/pressure

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: Pa / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes local contact pressure and material-removal rate.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_platen_speed` — platen speed

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: rpm / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes relative velocity in the Preston-like removal response.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_carrier_speed` — carrier speed

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: rpm / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes relative velocity and within-wafer uniformity.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_slurry_flow` — slurry flow

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: volume/time / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes reactant/abrasive delivery.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_slurry_chemistry` — slurry abrasive/oxidizer chemistry

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `structural_choice` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical/composition / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls material reaction and removal selectivity.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_pad_choice` — pad material/condition

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `structural_choice` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls contact compliance, roughness, and pressure distribution.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_selectivity` — Cu/barrier/dielectric selectivity

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: rate ratios / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Sets relative removal of the explicit material stack.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_endpoint_signal` — endpoint criterion

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: signal threshold / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Detects first field-Cu clear.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_overpolish_delay` — post-endpoint overpolish

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: s or fraction / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls residual Cu clearance versus dish/erosion.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_temperature` — pad/wafer/slurry temperature

- Owner/API: `physical process; unsupported by current wrapper`
- Classification / implementation: `recipe_knob` / `unsupported_physical`
- DOE eligibility: `requires_model_and_calibration`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: degC / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes chemical kinetics and pad response.
- Metrics affected: ["field_clear", "dish", "erosion", "material_survival"]
- Known interactions: ["Other physical controls in the same module", "incoming geometry"]
- Upstream consequence: Requires the incoming wafer/material state from the previous module.
- Downstream consequence: Changes the morphology or material quality inherited by every later module.
- Evidence: `untested`; confidence: high that the control is physically relevant; low that the current model can predict it
- Supporting experiment: Registered from the supplied via-middle process reference and mechanism literature; no executable mapping yet.
- Range provenance: No model range. Requires tool data, primary literature bounds, or calibration before DOE inclusion.

#### `cmp_model_family` — uniform/selective/ideal/contact-aware removal

- Owner/API: `IsotropicProcess/Planarize/CSV/custom contact model`
- Classification / implementation: `structural_choice` / `fixed_or_challenge_planned`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Determines whether raised Cu can clear preferentially without erasing the stack.
- Metrics affected: ["all owning-step morphology CTQs", "model validity"]
- Known interactions: ["Every process coefficient in the selected model", "dimensionality", "grid resolution"]
- Upstream consequence: Defines what incoming state can be represented.
- Downstream consequence: May qualitatively change all later morphology and failure modes.
- Evidence: `boundary-limited`; confidence: high for the need to declare the choice; model winner not yet accepted
- Supporting experiment: RESEARCH_PLAN_V2 controlled model challenges and foundation audit.
- Range provenance: Structural challenge arms, not an interpolated numeric range.

#### `legacy_cmp_missing_contact` — legacy cmp missing contact

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: One-rate isotropic removal has no pad contact pressure, pattern density, endpoint response, or calibrated selectivity.
- Metrics affected: ["field_clear", "dish", "erosion", "physical_cmp_recipe"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

### Cross Process

#### `geometry_qualification_tier` — continuity, nominal HBM, or high-AR stress geometry

- Owner/API: `program.md geometry tiers`
- Classification / implementation: `structural_choice` / `continuity_wired_nominal_and_stress_required`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical geometry tier / continuity / ["continuity"]
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": "continuity"}
- Expected mechanism: Changes feature width, depth, aspect ratio, transport access, layer conformality, fill closure, and runtime without changing the declared tier definitions.
- Metrics affected: ["aspect_ratio", "cd_profile", "layer_conformality", "void_topology", "overburden", "process_window"]
- Known interactions: ["geometry tier x every transport coefficient", "geometry tier x grid resolution", "geometry tier x 2D/3D dimensionality"]
- Upstream consequence: The selected pattern/etch geometry defines the incoming domain for every film and fill model.
- Downstream consequence: A result on the continuity tier cannot substitute for the required nominal-HBM and high-AR challenges.
- Evidence: `boundary-limited`; confidence: high for declared geometry; low beyond the tested continuity tier
- Supporting experiment: The continuity tier is exercised by foundation controls. Nominal HBM and high-AR stress tiers are declared in program.md but have not yet been executed with the candidate fill model.
- Range provenance: program.md fixes the three non-interpolated qualification tiers; they are structural challenges, not a recipe sweep.

#### `process_duration` — process duration

- Owner/API: `Process.duration`
- Classification / implementation: `model_coefficient` / `fixed`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation time / step-specific / not assigned
- Current best: not assigned
- Expected mechanism: Multiplies the model velocity/flux response.
- Metrics affected: ["all_morphology_ctqs"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `confirmed`; confidence: medium
- Supporting experiment: Direct wrapper inspection; many wrappers fix duration to 1.0.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `flux_engine_type` — flux engine type

- Owner/API: `Process.setFluxEngineType`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: enum / AUTO / {"isolated_rate_field": ["AUTO"], "staged_trajectory": ["CPU_DISK"]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": "CPU_DISK"}
- Expected mechanism: Chooses CPU/GPU/automatic flux execution.
- Metrics affected: ["numerical_reproducibility", "runtime"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: AUTO is exercised by the isolated candidate rate-field controls. CPU_DISK is explicitly wired in the staged trajectory runner but has not yet been compared or accepted.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `api_RayTracingParameters_diskRadius` — diskRadius

- Owner/API: `RayTracingParameters.diskRadius`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0.0 / {"isolated_rate_field": [0.0], "staged_trajectory": [0.0]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.0}
- Expected mechanism: Controls the diskRadius numerical behavior of RayTracingParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_RayTracingParameters_ignoreFluxBoundaries` — ignoreFluxBoundaries

- Owner/API: `RayTracingParameters.ignoreFluxBoundaries`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / false / {"isolated_rate_field": [false], "staged_trajectory": [false]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": false}
- Expected mechanism: Controls the ignoreFluxBoundaries numerical behavior of RayTracingParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_RayTracingParameters_maxBoundaryHits` — maxBoundaryHits

- Owner/API: `RayTracingParameters.maxBoundaryHits`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 1000 / {"isolated_rate_field": [1000], "staged_trajectory": [1000]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 1000}
- Expected mechanism: maximum boundary interactions
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_RayTracingParameters_maxReflections` — maxReflections

- Owner/API: `RayTracingParameters.maxReflections`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 4294967295 / {"isolated_rate_field": [4294967295], "staged_trajectory": [100]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 100}
- Expected mechanism: maximum particle reflection history
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_RayTracingParameters_minNodeDistanceFactor` — minNodeDistanceFactor

- Owner/API: `RayTracingParameters.minNodeDistanceFactor`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0.05 / {"isolated_rate_field": [0.05], "staged_trajectory": [0.05]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 0.05}
- Expected mechanism: Controls the minNodeDistanceFactor numerical behavior of RayTracingParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_RayTracingParameters_normalizationType` — normalizationType

- Owner/API: `RayTracingParameters.normalizationType`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0 / {"isolated_rate_field": ["SOURCE (default)"], "staged_trajectory": ["SOURCE (explicit)"]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": "NormalizationType.SOURCE (0)"}
- Expected mechanism: Controls the normalizationType numerical behavior of RayTracingParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_RayTracingParameters_raysPerPoint` — raysPerPoint

- Owner/API: `RayTracingParameters.raysPerPoint`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 1000 / {"isolated_rate_field": [500, 1000, 2000], "staged_trajectory": [1000]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 1000}
- Expected mechanism: Monte Carlo sampling density and variance
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_RayTracingParameters_rngSeed` — rngSeed

- Owner/API: `RayTracingParameters.rngSeed`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0 / {"isolated_rate_field": [17, 19, 731, 811], "staged_trajectory": ["91000 + checkpoint index"]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": "design seed 91000 + checkpoint index"}
- Expected mechanism: reproducible random stream
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_RayTracingParameters_smoothingNeighbors` — smoothingNeighbors

- Owner/API: `RayTracingParameters.smoothingNeighbors`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 1 / {"isolated_rate_field": [1], "staged_trajectory": [1]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": 1}
- Expected mechanism: Controls the smoothingNeighbors numerical behavior of RayTracingParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_RayTracingParameters_useRandomSeeds` — useRandomSeeds

- Owner/API: `RayTracingParameters.useRandomSeeds`
- Classification / implementation: `numerical_control` / `wired_candidate_manifest`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / true / {"isolated_rate_field": [false], "staged_trajectory": [false]}
- Current best: {"source": ".scratch/full-traveler-autoresearch/foundation_copper_fill_manifest.json", "status": "qualification_setting_not_best", "value": false}
- Expected mechanism: deterministic versus automatically randomized streams
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for wiring; low for candidate-fill sensitivity or convergence
- Supporting experiment: Isolated candidate rate-field controls exercised the listed default values; staged trajectory values are configured but not accepted by a convergence study.
- Range provenance: Isolated-control value plus the explicit staged manifest setting; staged values are not production DOE evidence.

#### `api_AdvectionParameters_adaptiveTimeStepSubdivisions` — adaptiveTimeStepSubdivisions

- Owner/API: `AdvectionParameters.adaptiveTimeStepSubdivisions`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 20 / not assigned
- Current best: not assigned
- Expected mechanism: Controls the adaptiveTimeStepSubdivisions numerical behavior of AdvectionParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_AdvectionParameters_adaptiveTimeStepping` — adaptiveTimeStepping

- Owner/API: `AdvectionParameters.adaptiveTimeStepping`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / false / not assigned
- Current best: not assigned
- Expected mechanism: adaptive versus fixed advection steps
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_AdvectionParameters_calculateIntermediateVelocities` — calculateIntermediateVelocities

- Owner/API: `AdvectionParameters.calculateIntermediateVelocities`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / false / not assigned
- Current best: not assigned
- Expected mechanism: Controls the calculateIntermediateVelocities numerical behavior of AdvectionParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_AdvectionParameters_checkDissipation` — checkDissipation

- Owner/API: `AdvectionParameters.checkDissipation`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / true / not assigned
- Current best: not assigned
- Expected mechanism: Controls the checkDissipation numerical behavior of AdvectionParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_AdvectionParameters_dissipationAlpha` — dissipationAlpha

- Owner/API: `AdvectionParameters.dissipationAlpha`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Controls the dissipationAlpha numerical behavior of AdvectionParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_AdvectionParameters_integrationScheme` — integrationScheme

- Owner/API: `AdvectionParameters.integrationScheme`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0 / not assigned
- Current best: not assigned
- Expected mechanism: Controls the integrationScheme numerical behavior of AdvectionParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_AdvectionParameters_spatialScheme` — spatialScheme

- Owner/API: `AdvectionParameters.spatialScheme`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0 / not assigned
- Current best: not assigned
- Expected mechanism: Controls the spatialScheme numerical behavior of AdvectionParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_AdvectionParameters_temporalScheme` — temporalScheme

- Owner/API: `AdvectionParameters.temporalScheme`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0 / not assigned
- Current best: not assigned
- Expected mechanism: Controls the temporalScheme numerical behavior of AdvectionParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_AdvectionParameters_timeStepRatio` — timeStepRatio

- Owner/API: `AdvectionParameters.timeStepRatio`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0.4999 / not assigned
- Current best: not assigned
- Expected mechanism: level-set advection timestep size
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_AdvectionParameters_velocityOutput` — velocityOutput

- Owner/API: `AdvectionParameters.velocityOutput`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / false / not assigned
- Current best: not assigned
- Expected mechanism: Controls the velocityOutput numerical behavior of AdvectionParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_CoverageParameters_initialized` — initialized

- Owner/API: `CoverageParameters.initialized`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / false / not assigned
- Current best: not assigned
- Expected mechanism: Controls the initialized numerical behavior of CoverageParameters.
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_CoverageParameters_maxIterations` — maxIterations

- Owner/API: `CoverageParameters.maxIterations`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 4294967295 / not assigned
- Current best: not assigned
- Expected mechanism: coverage-iteration ceiling
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `api_CoverageParameters_tolerance` — tolerance

- Owner/API: `CoverageParameters.tolerance`
- Classification / implementation: `numerical_control` / `api_available_unwired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: coverage-iteration convergence threshold
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `untested`; confidence: high for default capture; low for sensitivity unless tested
- Supporting experiment: Captured from installed ViennaPS 4.6.1 defaults; not independently varied.
- Range provenance: Installed API default; any future range requires numerical-convergence evidence.

#### `simulation_dimension` — 2D trench versus 3D cylindrical via

- Owner/API: `ps.setDimension / Domain`
- Classification / implementation: `structural_choice` / `fixed_or_challenge_planned`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Current 2D Cartesian geometry is an economical trench surrogate; accepted conclusions require matched 3D confirmation.
- Metrics affected: ["all owning-step morphology CTQs", "model validity"]
- Known interactions: ["Every process coefficient in the selected model", "dimensionality", "grid resolution"]
- Upstream consequence: Defines what incoming state can be represented.
- Downstream consequence: May qualitatively change all later morphology and failure modes.
- Evidence: `boundary-limited`; confidence: high for the need to declare the choice; model winner not yet accepted
- Supporting experiment: RESEARCH_PLAN_V2 controlled model challenges and foundation audit.
- Range provenance: Structural challenge arms, not an interpolated numeric range.

#### `boundary_condition` — reflective/periodic/other

- Owner/API: `Domain boundaryType`
- Classification / implementation: `structural_choice` / `fixed_or_challenge_planned`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Changes particle and level-set behavior at domain boundaries.
- Metrics affected: ["all owning-step morphology CTQs", "model validity"]
- Known interactions: ["Every process coefficient in the selected model", "dimensionality", "grid resolution"]
- Upstream consequence: Defines what incoming state can be represented.
- Downstream consequence: May qualitatively change all later morphology and failure modes.
- Evidence: `untested`; confidence: high for the need to declare the choice; model winner not yet accepted
- Supporting experiment: RESEARCH_PLAN_V2 controlled model challenges and foundation audit.
- Range provenance: Structural challenge arms, not an interpolated numeric range.

#### `single_via_domain` — one isolated via versus via array

- Owner/API: `Domain geometry`
- Classification / implementation: `structural_choice` / `fixed_or_challenge_planned`
- DOE eligibility: `excluded_rejected`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Controls whether inter-via shadowing/loading can occur.
- Metrics affected: ["all owning-step morphology CTQs", "model validity"]
- Known interactions: ["Every process coefficient in the selected model", "dimensionality", "grid resolution"]
- Upstream consequence: Defines what incoming state can be represented.
- Downstream consequence: May qualitatively change all later morphology and failure modes.
- Evidence: `structurally-unresolvable`; confidence: high for the need to declare the choice; model winner not yet accepted
- Supporting experiment: RESEARCH_PLAN_V2 controlled model challenges and foundation audit.
- Range provenance: Structural challenge arms, not an interpolated numeric range.

#### `uncalibrated_physical_scale` — uncalibrated physical scale

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Simulation lengths and model coefficients are not mapped to a physical HBM recipe.
- Metrics affected: ["all physical-unit claims"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

#### `two_d_trench_surrogate` — two d trench surrogate

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Cartesian 2D MakeHole represents a trench and cannot prove cylindrical 3D topology or flux behavior.
- Metrics affected: ["void_topology", "conformality", "process_window"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

#### `missing_electrical_reliability` — missing electrical reliability

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Topography simulation does not calculate TDDB, leakage, Cu diffusion, seed resistance, adhesion, stress, or electromigration.
- Metrics affected: ["electrical_pass", "reliability_pass"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

#### `single_feature_no_loading` — single feature no loading

- Owner/API: `current model boundary`
- Classification / implementation: `model_limitation` / `not_represented`
- DOE eligibility: `not_a_tuning_factor`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: not applicable / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: One local via cannot represent chamber-scale depletion, pitch-dependent loading, or wafer nonuniformity.
- Metrics affected: ["across_array_uniformity", "RIE_lag"]
- Known interactions: ["Cannot be repaired by widening the existing coefficient range alone."]
- Upstream consequence: May invalidate the incoming-state interpretation.
- Downstream consequence: Prevents a physical full-traveler conclusion until resolved or externally validated.
- Evidence: `structurally-unresolvable`; confidence: high
- Supporting experiment: Foundation re-audit and installed API inspection.
- Range provenance: No range: this is a missing model capability or validation domain.

### Barrier Seed/Cu Fill

#### `direction_vector` — direction vector

- Owner/API: `DirectionalProcess.direction`
- Classification / implementation: `model_coefficient` / `fixed`
- DOE eligibility: `excluded_rejected`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: unit vector / [0.0, -1.0, 0.0] / not assigned
- Current best: not assigned
- Expected mechanism: Sets the geometric deposition direction.
- Metrics affected: ["conformality", "bottom_access", "pinch_off"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `rejected`; confidence: medium
- Supporting experiment: Legacy 0-30 degree tilt claim was retracted after shared-geometry control.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `directional_mask_material` — directional mask material

- Owner/API: `DirectionalProcess.maskMaterial(s)`
- Classification / implementation: `model_coefficient` / `fixed`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material enum/list / Material.Mask / not assigned
- Current best: not assigned
- Expected mechanism: Prevents geometric motion on declared mask materials.
- Metrics affected: ["mask_survival", "field_deposition"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `screened`; confidence: medium
- Supporting experiment: API default used by legacy wrapper.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `directional_visibility` — directional visibility

- Owner/API: `DirectionalProcess.calculateVisibility`
- Classification / implementation: `model_coefficient` / `fixed`
- DOE eligibility: `excluded_rejected`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: boolean / true / not assigned
- Current best: not assigned
- Expected mechanism: Enables line-of-sight visibility in the geometric deposition model.
- Metrics affected: ["shadowing", "conformality"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `rejected`; confidence: medium
- Supporting experiment: Legacy True/False screen showed no validated effect in the single-via 2D domain.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

#### `directional_material_rates` — directional material rates

- Owner/API: `DirectionalProcess.materialRates / RateSet`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material-to-(directional,isotropic) map / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Allows material-specific geometric velocity pairs.
- Metrics affected: ["layer_selectivity", "material_survival"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `untested`; confidence: low
- Supporting experiment: API available but not wired.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

### Liner/Barrier Seed

#### `deposit_material` — deposit material

- Owner/API: `deposit_conformal(material) / duplicateTopLevelSet`
- Classification / implementation: `structural_choice` / `wired`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material enum / not assigned / ["SiO2", "TaN", "registered CuSeed", "Cu"]
- Current best: not assigned
- Expected mechanism: Selects the explicitly tracked deposited material layer.
- Metrics affected: ["material_survival", "layer_thickness", "continuity"]
- Known interactions: ["material identity x CMP selectivity"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `confirmed`; confidence: high
- Supporting experiment: API audit records separate SiO2, TaN, registered CuSeed, and plated-Cu identities.
- Range provenance: Declared material stack, not a numerical sweep.

#### `deposit_directional` — deposit directional

- Owner/API: `deposit_conformal(directional)`
- Classification / implementation: `structural_choice` / `wired`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: boolean / false / [false, true]
- Current best: not assigned
- Expected mechanism: Chooses sticking-controlled particle transport or geometric directional deposition.
- Metrics affected: ["layer_conformality", "remaining_aperture"]
- Known interactions: ["model choice x dose", "model choice x aspect ratio"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: medium for morphology; low for physical mapping
- Supporting experiment: Legacy liner used False; barrier/seed used True. Neither is accepted as calibrated chemistry.
- Range provenance: Model-family comparison.

#### `deposit_rays_per_point` — deposit rays per point

- Owner/API: `deposit_conformal(rays_per_point) / RayTracingParameters`
- Classification / implementation: `numerical_control` / `wired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: rays per surface point / 1000 / [1000]
- Current best: not assigned
- Expected mechanism: Controls ray sampling for SingleParticleProcess transport.
- Metrics affected: ["local_thickness", "conformality", "run_variance"]
- Known interactions: ["rays x grid_delta", "rays x sticking"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `untested`; confidence: low
- Supporting experiment: No accepted liner/barrier ray-convergence study yet.
- Range provenance: Wrapper default; qualification range not chosen.

#### `deposit_rng_seed` — deposit rng seed

- Owner/API: `deposit_conformal(rng_seed) / RayTracingParameters`
- Classification / implementation: `numerical_control` / `wired`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: integer seed / not assigned / ["explicit foundation seeds"]
- Current best: not assigned
- Expected mechanism: Makes transport comparisons reproducible on shared upstream geometry.
- Metrics affected: ["run_variance", "local_thickness"]
- Known interactions: ["seed x upstream geometry"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `screened`; confidence: medium
- Supporting experiment: Foundation layer audit manifests use explicit seeds.
- Range provenance: Reproducibility control, not a recipe range.

#### `layer_isotropic_control_dose` — ideal isotropic-control dose

- Owner/API: `layer_process_models.deposit_isotropic_control(dose)`
- Classification / implementation: `model_coefficient` / `representation_control_only`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / not assigned / [0.03]
- Current best: not assigned
- Expected mechanism: Provides a morphology-positive control for the metric and geometry; it is not a calibrated deposition mechanism.
- Metrics affected: ["field_thickness", "conformality", "minimum_local_thickness", "remaining_aperture"]
- Known interactions: ["control dose x grid resolution", "control dose x incoming geometry"]
- Upstream consequence: Requires an accepted full-width Bosch geometry and explicit incoming material interfaces.
- Downstream consequence: Changes layer continuity, aperture, seed access, and the geometry inherited by Cu fill.
- Evidence: `screened`; confidence: high for code parameterization; low for physical applicability
- Supporting experiment: test_layer_process_models.py verifies parameter bounds and the expected full-width morphology response on an analytic via only; no Gate-0 traveler geometry has been accepted.
- Range provenance: Exact diagnostic values exercised by test_layer_process_models.py; not a DOE range or fab calibration.

#### `api_AtomicLayerProcessParameters_coverageTimeStep` — coverageTimeStep

- Owner/API: `AtomicLayerProcessParameters.coverageTimeStep`
- Classification / implementation: `numerical_control` / `api_available_native_preflight_required`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: surface-coverage update interval during an atomic-layer pulse
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for API wiring; low for ALD model acceptance
- Supporting experiment: Installed ViennaPS 4.6.1 ALD parameter object was audited; a no-purge one- and ten-cycle full-width smoke path completed, but this does not qualify ALD morphology or physical coefficients.
- Range provenance: Default parameter capture plus a bounded native smoke test; no ALD DOE range is authorized.

#### `api_AtomicLayerProcessParameters_numCycles` — numCycles

- Owner/API: `AtomicLayerProcessParameters.numCycles`
- Classification / implementation: `numerical_control` / `api_available_native_preflight_required`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 1 / not assigned
- Current best: not assigned
- Expected mechanism: number of repeated atomic-layer pulse cycles
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for API wiring; low for ALD model acceptance
- Supporting experiment: Installed ViennaPS 4.6.1 ALD parameter object was audited; a no-purge one- and ten-cycle full-width smoke path completed, but this does not qualify ALD morphology or physical coefficients.
- Range provenance: Default parameter capture plus a bounded native smoke test; no ALD DOE range is authorized.

#### `api_AtomicLayerProcessParameters_pulseTime` — pulseTime

- Owner/API: `AtomicLayerProcessParameters.pulseTime`
- Classification / implementation: `numerical_control` / `api_available_native_preflight_required`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: precursor exposure duration per atomic-layer cycle
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for API wiring; low for ALD model acceptance
- Supporting experiment: Installed ViennaPS 4.6.1 ALD parameter object was audited; a no-purge one- and ten-cycle full-width smoke path completed, but this does not qualify ALD morphology or physical coefficients.
- Range provenance: Default parameter capture plus a bounded native smoke test; no ALD DOE range is authorized.

#### `api_AtomicLayerProcessParameters_purgePulseTime` — purgePulseTime

- Owner/API: `AtomicLayerProcessParameters.purgePulseTime`
- Classification / implementation: `numerical_control` / `api_available_native_preflight_required`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: desorption/purge interval after an atomic-layer pulse
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `boundary-limited`; confidence: high for the observed native failure; low for its root cause
- Supporting experiment: A subprocess preflight using the installed ViennaPS 4.6.1 SingleParticleALD completed with purgePulseTime=0, while enabling a 0.05 purge pulse exited with native signal 11 (shell status 139); purge-enabled ALD is blocked pending isolation or an upstream fix.
- Range provenance: Default parameter capture plus a bounded native smoke test; no ALD DOE range is authorized.

#### `api_AtomicLayerProcessParameters_purgeTimeStep` — purgeTimeStep

- Owner/API: `AtomicLayerProcessParameters.purgeTimeStep`
- Classification / implementation: `numerical_control` / `api_available_native_preflight_required`
- DOE eligibility: `numerical_benchmark_only`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: API-specific numerical setting / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: surface-coverage update interval during purge
- Metrics affected: ["numerical_convergence", "runtime", "all geometry outputs if changed"]
- Known interactions: ["grid_delta", "process model", "geometry complexity"]
- Upstream consequence: No physical upstream consequence; may alter numerical realization.
- Downstream consequence: Numerical bias or variance propagates through every later geometry.
- Evidence: `screened`; confidence: high for API wiring; low for ALD model acceptance
- Supporting experiment: Installed ViennaPS 4.6.1 ALD parameter object was audited; a no-purge one- and ten-cycle full-width smoke path completed, but this does not qualify ALD morphology or physical coefficients.
- Range provenance: Default parameter capture plus a bounded native smoke test; no ALD DOE range is authorized.

#### `ald_sticking` — ald sticking

- Owner/API: `SingleParticleALDParams.stickingProbability`
- Classification / implementation: `model_coefficient` / `api_available_native_smoke_only`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / 1.0 / [5e-05]
- Current best: not assigned
- Expected mechanism: Adsorption probability per ALD exposure.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: A no-purge native SingleParticleALD smoke path completed on an analytic full-width via. A documented-style nonzero purge pulse crashed the native process, so these coefficients are not accepted for a campaign.
- Range provenance: Exact no-purge smoke value only; no ALD DOE range is authorized.

#### `ald_growth_per_cycle` — ald growth per cycle

- Owner/API: `SingleParticleALDParams.growthPerCycle`
- Classification / implementation: `model_coefficient` / `api_available_native_smoke_only`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length/cycle / 0.0 / [0.004]
- Current best: not assigned
- Expected mechanism: Growth increment per ALD cycle.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: A no-purge native SingleParticleALD smoke path completed on an analytic full-width via. A documented-style nonzero purge pulse crashed the native process, so these coefficients are not accepted for a campaign.
- Range provenance: Exact no-purge smoke value only; no ALD DOE range is authorized.

#### `ald_incoming_flux` — ald incoming flux

- Owner/API: `SingleParticleALDParams.incomingFlux`
- Classification / implementation: `model_coefficient` / `api_available_native_smoke_only`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model flux / 0.0 / [2000000.0]
- Current best: not assigned
- Expected mechanism: Incoming precursor flux.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: A no-purge native SingleParticleALD smoke path completed on an analytic full-width via. A documented-style nonzero purge pulse crashed the native process, so these coefficients are not accepted for a campaign.
- Range provenance: Exact no-purge smoke value only; no ALD DOE range is authorized.

#### `ald_evaporation_flux` — ald evaporation flux

- Owner/API: `SingleParticleALDParams.evaporationFlux`
- Classification / implementation: `model_coefficient` / `api_available_native_smoke_only`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model flux / 0.0 / [2.5]
- Current best: not assigned
- Expected mechanism: Desorption/evaporation contribution.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: A no-purge native SingleParticleALD smoke path completed on an analytic full-width via. A documented-style nonzero purge pulse crashed the native process, so these coefficients are not accepted for a campaign.
- Range provenance: Exact no-purge smoke value only; no ALD DOE range is authorized.

#### `ald_coverage_diffusion` — ald coverage diffusion

- Owner/API: `SingleParticleALDParams.coverageDiffusionCoefficient`
- Classification / implementation: `model_coefficient` / `api_available_native_smoke_only`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model diffusivity / 0.0 / [0.0]
- Current best: not assigned
- Expected mechanism: Surface redistribution of adsorbed coverage.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: A no-purge native SingleParticleALD smoke path completed on an analytic full-width via. A documented-style nonzero purge pulse crashed the native process, so these coefficients are not accepted for a campaign.
- Range provenance: Exact no-purge smoke value only; no ALD DOE range is authorized.

#### `ald_mean_free_path` — ald mean free path

- Owner/API: `SingleParticleALDParams.gasMeanFreePath`
- Classification / implementation: `model_coefficient` / `api_available_native_smoke_only`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation length / -1.0 / [1519.87]
- Current best: not assigned
- Expected mechanism: Gas-phase transport length scale.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: A no-purge native SingleParticleALD smoke path completed on an analytic full-width via. A documented-style nonzero purge pulse crashed the native process, so these coefficients are not accepted for a campaign.
- Range provenance: Exact no-purge smoke value only; no ALD DOE range is authorized.

#### `ald_s0` — ald s0

- Owner/API: `SingleParticleALDParams.s0`
- Classification / implementation: `model_coefficient` / `api_available_native_smoke_only`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless / 0.0 / [3.36]
- Current best: not assigned
- Expected mechanism: Coverage-dependent sticking coefficient.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `screened`; confidence: high for API availability; low for physical applicability
- Supporting experiment: A no-purge native SingleParticleALD smoke path completed on an analytic full-width via. A documented-style nonzero purge pulse crashed the native process, so these coefficients are not accepted for a campaign.
- Range provenance: Exact no-purge smoke value only; no ALD DOE range is authorized.

### Liner/Bosch Etch

#### `single_particle_mask_materials` — single particle mask materials

- Owner/API: `SingleParticleProcess.maskMaterial(s)`
- Classification / implementation: `model_coefficient` / `fixed`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: material enum/list / Undefined for liner; Mask for polymer punch-through / not assigned
- Current best: not assigned
- Expected mechanism: Excludes declared materials from particle-process motion.
- Metrics affected: ["mask_survival", "layer_selectivity"]
- Known interactions: ["Must be checked against grid, dimensionality, and the owning process dose."]
- Upstream consequence: No direct upstream effect.
- Downstream consequence: Any changed morphology propagates downstream.
- Evidence: `confirmed`; confidence: medium
- Supporting experiment: Direct wrapper and API inspection.
- Range provenance: API default or legacy model-sensitivity screen; no fab calibration.

### Liner/Cu Fill

#### `neutral_incoming_flux` — neutral incoming flux

- Owner/API: `NeutralTransportParameters.incomingFlux`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model flux / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Incoming neutral species supply.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `neutral_zero_coverage_sticking` — neutral zero coverage sticking

- Owner/API: `NeutralTransportParameters.zeroCoverageSticking`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: probability / 0.1 / not assigned
- Current best: not assigned
- Expected mechanism: Sticking on an uncovered surface.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `neutral_desorption_rate` — neutral desorption rate

- Owner/API: `NeutralTransportParameters.desorptionRate`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: inverse simulation time / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Adsorbate loss from the surface.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `neutral_surface_diffusion` — neutral surface diffusion

- Owner/API: `NeutralTransportParameters.surfaceDiffusionCoefficient`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model diffusivity / 0.0 / not assigned
- Current best: not assigned
- Expected mechanism: Surface transport of adsorbate coverage.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `neutral_surface_site_density` — neutral surface site density

- Owner/API: `NeutralTransportParameters.surfaceSiteDensity`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: model sites/area / 1.66e-05 / not assigned
- Current best: not assigned
- Expected mechanism: Coverage capacity of the surface.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `neutral_coverage_timestep` — neutral coverage timestep

- Owner/API: `NeutralTransportParameters.coverageTimeStep`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation time / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Coverage update interval.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `neutral_source_power` — neutral source power

- Owner/API: `NeutralTransportParameters.sourceDistributionPower`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: dimensionless exponent / 1.0 / not assigned
- Current best: not assigned
- Expected mechanism: Angular source distribution.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

#### `neutral_steady_state` — neutral steady state

- Owner/API: `NeutralTransportParameters.useSteadyStateCoverage`
- Classification / implementation: `model_coefficient` / `api_available_unwired`
- DOE eligibility: `not_wired`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: boolean / true / not assigned
- Current best: not assigned
- Expected mechanism: Steady-state versus transient surface coverage.
- Metrics affected: ["local deposition/removal rate", "material morphology", "owning-step CTQs"]
- Known interactions: ["geometry", "process duration", "grid_delta", "other coefficients in the same model"]
- Upstream consequence: Requires a qualified incoming geometry.
- Downstream consequence: Any local thickness or topology change propagates downstream.
- Evidence: `untested`; confidence: high for API availability; low for physical applicability
- Supporting experiment: Installed ViennaPS 4.6.1 API inspection only.
- Range provenance: No range assigned. Calibrate or literature-bound before DOE inclusion.

### Pattern/Bosch Etch

#### `bosch_mask_ion_rate` — bosch mask ion rate

- Owner/API: `bosch_etch(mask_ion_rate) / rate_fn`
- Classification / implementation: `model_coefficient` / `wired_model_sensitivity`
- DOE eligibility: `range_requalification_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: simulation velocity coefficient / 0.0 / [0.0, -0.01, -0.02, -0.04]
- Current best: not assigned
- Expected mechanism: Scales ion-driven loss of the temporary pattern mask during every etch phase; zero is the historical infinite-selectivity control.
- Metrics affected: ["mask_remaining", "opening_cd_profile", "etch_depth", "etch_cd_profile", "wall_bow"]
- Known interactions: ["mask erosion x mask height", "mask erosion x taper", "mask erosion x cycle count", "mask erosion x ion transport"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `boundary-limited`; confidence: medium for model response; low for physical calibration
- Supporting experiment: The full-width fine-grid Gate-0 block retained a resolved mask on all four seeds through -0.04. The later R1 numerical release intentionally ran no mask-ladder rows, so the first full-width survive/fail boundary remains unknown and is assigned to V3 Stage 2f.
- Range provenance: The qualified range currently establishes survival only. Stage 2f adaptively challenges -0.05, -0.06, and -0.08, but no coefficient value is a fab selectivity range without calibration.

### Pattern/Cmp

#### `mask_stop_identity` — hard mask retained versus resist stripped plus separate stop

- Owner/API: `material stack and strip sequence`
- Classification / implementation: `structural_choice` / `fixed_or_challenge_planned`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: categorical / not assigned / not assigned
- Current best: not assigned
- Expected mechanism: Determines which layer must survive CMP and prevents photoresist from being mislabeled as a physical stop.
- Metrics affected: ["all owning-step morphology CTQs", "model validity"]
- Known interactions: ["Every process coefficient in the selected model", "dimensionality", "grid resolution"]
- Upstream consequence: Defines what incoming state can be represented.
- Downstream consequence: May qualitatively change all later morphology and failure modes.
- Evidence: `boundary-limited`; confidence: high for the need to declare the choice; model winner not yet accepted
- Supporting experiment: RESEARCH_PLAN_V2 controlled model challenges and foundation audit.
- Range provenance: Structural challenge arms, not an interpolated numeric range.

### Pattern/Cu Fill

#### `pattern_hole_shape` — pattern hole shape

- Owner/API: `MakeHole.holeShape`
- Classification / implementation: `structural_choice` / `wired_by_stage`
- DOE eligibility: `review_required`
- Acceptance-criterion evidence: `not_applicable`
- Units / default / tested range: enum / HoleShape.QUARTER in make_initial_geometry / ["QUARTER (2D symmetry-clipped half-trench)", "FULL (2D full trench)"]
- Current best: {"source": "test_copper_suppression_fill.py and foundation_copper_fill_trajectory.py", "status": "stage_specific_validity_choice", "value": {"candidate_fill_topology": "FULL", "phase_one_pattern_etch": "QUARTER"}}
- Expected mechanism: Selects a symmetry-clipped half-domain or the full feature. FULL is mandatory when judging internal fill topology because a centerline void can otherwise be clipped into an open contour.
- Metrics affected: ["void_topology", "flux_transport", "runtime"]
- Known interactions: ["shape x dimensionality", "shape x boundary condition", "shape x void classification"]
- Upstream consequence: May alter the state entering this process step.
- Downstream consequence: Any morphology or material change propagates to every later step.
- Evidence: `confirmed`; confidence: high for the 2D topology requirement
- Supporting experiment: Phase-one used 2D QUARTER. The isolated candidate-fill and sealed-void controls use FULL and demonstrate why fill topology requires the full 2D trench; matched 3D confirmation remains separate.
- Range provenance: Structural guard exercised by test_copper_suppression_fill.py; it is not an interpolated recipe range.

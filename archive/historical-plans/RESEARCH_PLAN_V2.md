# Full TSV traveler research plan v2

Status: superseded by `RESEARCH_PLAN_V3.md` for DOE scale, sequencing, effect
screening, and downstream-propagation decisions. This file remains the detailed
metric/model audit history. Product targets were not changed.

Former status: active foundation re-audit. The 1,948 saved travelers are phase-one
evidence, not an accepted optimum or a substitute for the work below.

## Fixed objective

The declared product and step specifications in `program.md` remain the fixed
destination. We will improve process settings and, where the implemented model
cannot express the required mechanism, improve the process model. We will not
relax a target, change a weight, rename a proxy, or hide an invalid result to
make a recipe pass.

The recommended recipe must be a robust full-traveler pass, not merely the
lowest nominal loss. Rank candidates in this order:

1. Valid simulation, topology, and metrics.
2. Every hard gate.
3. Every declared step target.
4. Replicated p90 and worst-case robustness.
5. Full-process loss.
6. Process-window width and sensitivity.
7. Practical complexity and interpretability.

## What counts as an input or output

Every recorded quantity must carry one of these labels.

- **Product specification:** fixed geometry or performance requirement.
- **Process control:** a setting an engineer can intentionally change.
- **Noise factor:** uncontrolled or manufacturing variation used to test
  robustness.
- **Model coefficient:** a calibrated or uncalibrated physics parameter; it is
  not automatically a fab control.
- **Numerical control:** grid, rays, timestep, boundary, or solver choice.
- **Structural choice:** process model, material stack, dimensionality, or
  boundary condition.
- **Hard-gate output:** a functional requirement that must pass.
- **Diagnostic output:** explains direction, sensitivity, or failure mode.
- **Downstream constraint:** determines whether the next process remains
  feasible.
- **Unavailable property:** a required electrical/reliability property the
  current model cannot calculate; it stays visible as missing evidence.

## Step-by-step input/output chain

### 1. Pattern / lithography output

Inputs and variations:

- Fixed targets: opening CD 0.30 and mask height 0.30.
- Representable geometry factors: opening radius/CD, mask height, mask taper,
  and opening profile.
- Robustness factors: CD bias, height variation, and taper variation within
  declared tolerances.
- Not currently represented: exposure dose, focus, resist chemistry,
  development, line-edge roughness, and overlay to device features.

Outputs:

- Top, middle, and bottom opening CD.
- CD bias from target.
- Opening-center position/shift, mask height, and separate left/right sidewall
  angles.
- Opening validity and remaining aperture.

Decision rule: `MakeHole()` is a parameterized pattern output, not an optical
lithography model. Dose/focus conclusions are prohibited without another
model; CD/height/taper propagation studies are valid. Pattern scores must be
measured from the generated geometry rather than copied from requested inputs.

### 2. Bosch silicon DRIE

Inputs:

- Upstream mask geometry.
- Cycle count, etch time, initial etch time, neutral rate, neutral sticking,
  passivation dose/thickness, passivation sticking, ion rate, ion angular
  exponent, and reflection-angle control.
- Numerical controls: grid spacing, ray count/sampling, timestep/advection,
  domain extent, and boundary conditions.

Outputs:

- Depth and aspect ratio.
- Entrance, upper, middle, lower, and bottom CD at declared depth fractions.
- Minimum and maximum usable-sidewall CD.
- Sidewall taper angle.
- Maximum bow relative to the large-scale fitted wall.
- Scallop/roughness residual after removing taper and bow.
- Bottom shape/rounding and mask remaining.

The selected depth-matched checkpoint must retain an open mask feature resolved
by more than two grid cells. This is a numerical survival gate until a
calibrated resist-loss limit exists; it does not convert the uncalibrated mask
erosion coefficient into a fab setting.

Decision rule: depth-match every profile comparison. Extract CD and wall shape
from the raw silicon boundary; the x-binned outer envelope is not valid for a
nearly vertical wall.

### 3. SiO2 liner

Inputs:

- Qualified etched geometry.
- Deposition dose/thickness, sticking/transport parameters, and any validated
  conformality controls.
- Numerical transport and grid controls.

Outputs:

- Minimum local thickness on field, upper wall, lower wall, and floor.
- Bottom/field and lower-wall/field conformality.
- Thickness non-uniformity along the usable surface.
- Layer continuity/pinhole status.
- Remaining aperture and downstream accessibility.

Decision rule: the hard thickness/coverage gates remain as declared. A global
floor displacement is not accepted as local thickness or continuity. The
legacy `floor_reach_metric` is directionally invalid and cannot be reused.

### 4. Barrier and seed

Inputs:

- Lined geometry and remaining aperture.
- Separate barrier, adhesion, and seed layer doses where represented.
- Directionality, angular/visibility transport, and validated model controls.

Material representation:

- Track SiO2, TaN, optional Ta, and Cu seed as distinct ordered level sets.
- Keep Cu seed and plated Cu distinguishable by level-set identity even when
  both use the Cu material rate.

Outputs:

- Minimum local barrier and seed thickness.
- Bottom/field and lower-wall/field conformality.
- Barrier and seed continuity.
- Remaining aperture.
- Seed connectivity evidence available to the fill step.

Decision rule: do not claim diffusion blocking or electrical seed continuity
from average geometric coverage alone.

### Mask and CMP stop identity

The phase-one `Material.Mask` cannot remain semantically ambiguous. Challenge
two explicit structures before the full traveler is frozen:

1. A durable patterned hard mask that also serves as the protected CMP stop.
2. Temporary photoresist stripped after DRIE, with a separately represented
   field dielectric/hard mask as the CMP stop.

The first is the simpler abstraction; the second more closely follows the
supplied via-middle sequence. Both must preserve the non-negotiable stop-layer
survival gate. Choose using the declared product stack and downstream
morphology, then use one identity consistently in code, metrics, figures, and
prose. Never carry photoresist through CMP while calling the result physical.

### 5. Cu electrofill

Inputs:

- Qualified seed geometry and connectivity.
- Physical controls to map or calibrate: plated charge/current waveform,
  accelerator, suppressor, leveler, chloride, transport/agitation, and time.
- Model coefficients for surface coverage, curvature enhancement, transport,
  and deposition rate must be kept distinct from physical controls.
- Select the mechanism from the mapped feature scale: CEAC is a candidate for
  accelerator area compression, while micrometre-scale TSVs motivate testing
  suppressor-breakdown physics. The first candidate is only a reduced
  quasi-steady suppressor-access model; it cannot be called S-NDR until it
  reproduces a current-potential response or a published limiting case.

Outputs:

- Internal void count, area, maximum size, and connectivity to the opening.
- Seam length or closed seam status.
- Minimum fill height and center/field fill height.
- Field overburden: minimum, mean, and non-uniformity.
- Mouth pinch-off and trapped-cavity status.
- Layer/material survival.
- Frozen-region floor, lower-wall, middle-wall, upper-wall, mouth, and field
  flux, coverage, velocity, and point counts; report floor/wall ratios against
  the geometry's axial-versus-lateral kinematic requirement.

Hard morphology sequence: a successful fill is a void-free Cu plug that
reaches the field and leaves positive overburden. Neither floor coverage nor a
small outer-surface scalar can substitute for this state.

The declared minimum fill thickness of 0.15 is evaluated as minimum
overburden across the via center and sampled field after void-free closure. It
is an output CTQ, not the input velocity-time deposition dose.

### 6. CMP

Inputs:

- Void-free plug, positive overburden, surface topography, and explicit
  material stack.
- Bulk removal control, endpoint criterion/delay, overpolish time or fraction,
  Cu/barrier/dielectric selectivity, and a validated pressure/contact model or
  declared abstraction.

Required stages:

1. Bulk removal of raised Cu.
2. First plated-Cu field-clear event recorded separately.
3. Cu-seed clear, TaN clear, and all-field-metals-clear events recorded
   separately; the full product endpoint is not conflated with first Cu clear.
4. Explicit post-endpoint overpolish states referenced to a named clear event,
   with declared material rates and stop layer.

Outputs:

- Residual field Cu and barrier.
- Endpoint reached/not reached.
- Cu dish and field dielectric erosion.
- Stop-layer loss and plug-height loss.
- Cu, barrier, liner, silicon, and mask/stop-layer survival.
- Empty-domain or substrate-loss failures classified separately.
- Clearing-to-hard-failure survival window and the narrower all-step-target
  window reported separately.

Decision rule: no CMP score is valid after substrate loss, plug loss, or total
geometry erasure. A lower dish never overrides a hard failure.

## Metric and resolution qualification

Before a production DOE:

1. Build analytic vertical, tapered, bowed, and scalloped walls with known CD
   profiles and verify the DRIE metrics.
2. Build analytic nested layers with known thickness and verify minimum local
   thickness, conformality, aperture, and continuity metrics.
3. Build open-void, sealed-void, seam, complete-fill, and overburden fixtures;
   verify topology metrics and visual agreement.
4. Build analytic pre-CMP stacks with known residual Cu, dish, and erosion;
   verify endpoint and material-survival classification.
5. Run grid convergence. The present 0.012 barrier on a 0.01 grid is only 1.2
   cells thick and cannot support a credible uniformity claim. Select a grid
   only after the relevant outputs converge within a declared tolerance.
6. Run ray-count and stochastic convergence for transport models.
7. Run matched 2D-trench and 3D-cylindrical-via cases. A 2D DOE may be used as
   an economical surrogate only for outputs whose 2D-to-3D discrepancy is
   quantified and acceptably stable.

Every metric test must include a positive case, the relevant failure case, and
a monotonic perturbation with a known direction.

## Model acceptance experiments

These are controlled mechanism tests, not the final DOE.

### Fill challenge

- Reuse at least two qualified etched/seeded geometries with materially
  different but in-spec CD profiles.
- Preserve the current constant-velocity fill as a negative control.
- Test credible installed ViennaPS APIs or a custom coverage/curvature model.
- First run a low-level coordinate-dependent morphology positive control to
  prove geometry and topology metrics can recognize a good fill. It is not a
  recipe result. Then bind one narrow C++ coverage/transport model; Python
  cannot compose a custom ViennaPS surface chemistry model in this checkout.
- Before any morphology coefficient sweep, run a static transport-sign screen.
  Every paired stream must make the floor less suppressed and faster than the
  lower, middle, and upper walls. A center/field contrast is insufficient, and
  a parameter family that cannot reverse the floor/wall ordering is rejected
  without spending a morphology DOE.
- Current checkpoint: the 168-case coarse screen, 128-cell numerical
  confirmation, and 24-cell lower-sticking boundary confirmation are complete
  with no accepted transport design. A proposed 16-cell boundary design was
  rejected before launch because its boundary-hit cap of 1,000 was below the
  requested 1,600/3,200 reflection depths. The corrected design used a cap of
  6,400 and newly executed a matched 0.0125 control plus the 0.00625 candidate
  at both reflection depths across both geometry tiers and four paired streams.
  All 24 cells are valid, and the 0.00625 response is exactly unchanged from
  1,600 to 3,200 reflections. It still passes 0/8 streams: worst flux ratio
  0.988828 versus the strict target below 0.95 and worst velocity ratio 1.004256
  versus the target above 1.05. Its 0.004147 worst-flux improvement over the
  matched 0.0125 control is below the predeclared 0.016714 continuation
  threshold. No further 2D boundary launch or morphology DOE is authorized.
  Recorded decision:
  `two_dimensional_transport_no_go_requires_matched_3d_before_pivot`.
  Before retaining or replacing this model family, freeze and independently
  audit a matched 2D-versus-3D transport bridge for the capped 0.0125 control
  and reflection-converged 0.00625 miss, preserving normalized geometry,
  coefficients, paired streams, numerical guards, and strict sign/H/a gates.
- Sweep enough dose and chemistry/model controls to observe incomplete fill,
  bottom-up closure, overfill, and pinch-off if the model can produce them.
- Save raw material meshes, topology, metrics, and representative images.

Acceptance: zero internal void/seam under the declared metric, positive
overburden, no aperture pinch-off before closure, layer survival, and grid
convergence.

For the HBM-scale hypothesis, the first physical candidate is a reduced
suppressor-breakdown model. It is not called S-NDR until it reproduces the
required potential/current hysteresis or an independently published limiting
case. CEAC remains a competing smaller-feature mechanism rather than a generic
synonym for all bottom-up fill.

### CMP challenge

- Start from an analytic filled plug and from at least two accepted simulated
  fills so CMP is not judged only on one inherited topography.
- Compare the legacy one-rate isotropic model, native geometric
  planarization, material-selective removal, and the isolated continuous
  `HeightMaterialCMP` height-by-material abstraction.
- Use `Planarize` only as an ideal endpoint/metric control. Use material-rate
  `IsotropicProcess` as a perfect-selectivity control. The exact C++ candidate
  may test a phenomenological local-contact hypothesis, but it contains no
  pad-pressure, pad-deformation, pattern-density, or calibrated Preston-law
  physics and must remain labeled accordingly.
- Sweep through under-clear, first clear, nominal overpolish, and destructive
  overpolish.

Acceptance: field Cu clears, the stop stack and plug survive, dish/erosion are
valid, failure classes are distinct, and the result is stable to grid and
small endpoint perturbations.

The current literature establishes the need for multi-stage endpoint control
and Cu/barrier/dielectric selectivity, but does not provide a universal
stop-loss or plug-loss threshold transferable to this uncalibrated geometry.
Until product provenance supplies those limits, run only normalized survival
sensitivity maps and retain `target_pass = false/undefined`; do not promote a
test-fixture threshold into the product specification.

If either model cannot pass this controlled challenge, return to model
development. Do not launch a large recipe DOE against a structurally failing
model.

## Knob and range registry

Before sampling, inspect every wrapper signature, default, call site, installed
ViennaPS constructor, and underlying process API. For every parameter record:

- Step, function/API, name, units, default, tested range, and current best.
- Input classification from this plan.
- Physical mechanism and expected response direction.
- Metrics affected, known interactions, and upstream/downstream consequences.
- Range provenance: calibrated, literature-bounded, physically bounded, or
  model-sensitivity only.
- Evidence state: untested, screened, replicated, confirmed, rejected,
  boundary-limited, or structurally unresolved.
- Supporting experiment and confidence.

No parameter is removed for convenience. It may be held fixed only with
recorded evidence or because it is a product/numerical/structural choice rather
than a process control.

## Staged DOE and provisional scale

Exact counts will be recomputed from the accepted factor count and the model
terms we intend to estimate. The counts below are provisional lower bounds,
not a runtime cap.

1. **Noise study:** 32-64 identical DRIE repeats at representative and edge
   recipes, plus grid/ray convergence, to separate stochastic and numerical
   variation from process effects.
2. **Broad screen:** at least 512 unique, space-filling recipes across the
   defensible ranges, normally with four shared upstream seeds for downstream
   arms. Include replicated center/reference points and explicit boundaries.
3. **Response and interaction study:** roughly 768-1,024 unique recipes for a
   validated hierarchical response model when about 17-25 effective factors
   remain. Include independent lack-of-fit and holdout points.
4. **Feasible-region refinement:** 256-512 new recipes placed around every
   credible feasible region and Pareto alternative, not only the scalar winner.
5. **Boundary expansion:** add points outside every winning tested edge before
   calling it an optimum.
6. **Finalist confirmation:** several credible recipes on at least 32 unseen
   DRIE seeds or an evidence-based larger count.
7. **Process-window perturbation:** 512 or more multivariate perturbations
   around each finalist, including realistic correlated noise where evidence
   supports it.

Broad screening may use qualified 2D surrogates. Model qualification, selected
interaction checks, finalists, and final traveler proof must include 3D
cylindrical vias. The existing coarse `render_3d.py` picture is not validation.

Geometry is tiered rather than silently rescaled: the historical 0.30 x 1.25
AR-4.17 case is for continuity and numerical qualification; the nominal
5 um x 50 um HBM case maps to 0.30 x 3.00 (AR 10); and a 3 um x 50 um stress
case maps to 0.18 x 3.00 (AR 16.7). The nominal tier is mandatory in the
2D-to-3D bridge and finalist proof. The stress tier must be reported even if
it fails. This geometry mapping does not calibrate recipe coefficients.

### 2D-to-3D surrogate bridge

The 2D campaign is the low-cost screening layer; 3D is the final physical
authority.

- Select a paired bridge set spanning the nominal region, every important
  factor boundary, strong interactions, Pareto alternatives, and each major
  failure morphology.
- Run the exact paired recipe and matched numerical settings in a 2D trench and
  a 3D cylindrical via.
- Compare metric validity, effect direction, rank ordering, interaction sign,
  topology class, and margin to every hard specification.
- Estimate the 3D-minus-2D discrepancy for outputs with stable correspondence.
  Show the raw paired points and hold out part of the bridge set when testing
  any correction.
- Reject 2D as a surrogate for an output if it changes a pass/fail decision,
  reverses an important interaction, misses a 3D void/topology failure, or has
  error comparable with the remaining specification margin.
- Run finalist confirmation and final process-window perturbations in 3D even
  when the 2D bridge passes.

The paired count will follow observed discrepancy and stochastic variance. A
starting bridge of 24-48 deliberately diverse recipes is a minimum diagnostic,
not an automatic stopping point.

Run 3D bridge audits after model/metric acceptance, after the broad screen,
after interaction selection, after feasible-region refinement or a boundary
win, and throughout finalist/process-window confirmation. A 3D check is a
decision gate, not a decorative final render.

Upstream geometry is generated once per upstream recipe/seed and reused across
all downstream arms. Equivalent simulations are cached by a complete model,
geometry, grid, recipe, and seed signature.

## Execution graph and unattended runtime

Work is parallelized by evidence dependency, not by launching every CPU-heavy
batch at once.

The following preparation tracks may run concurrently:

- non-ideal mask geometry, mask-erosion, and Bosch checkpoint qualification;
- liner/barrier/seed metric, full-2D bridge, and seed-loss qualification;
- dimension-safe 3D Cu transport implementation and prelaunch review;
- controlled CMP selectivity/endpoint metrics and loss-limit definition;
- test/gate traceability, registry maintenance, analysis, and publication.

Current 2D-first checkpoint (2026-07-12): before the broad screen, run one
24-case full-2D Gate 0 using four disjoint, shared Bosch base streams. It pairs
quarter versus full geometry, grid 0.0025 versus 0.00125, and mask-ion rates
0, -0.01, -0.02, and -0.04 at the saved cycle-13 checkpoint. Every checkpoint
must be hash-verified and independently remeasured. Gate 0 may authorize only
the broad pattern/Bosch screen; it cannot select a recipe or support a
robustness claim.

The following handoffs remain serial:

1. Commission one continuity and one nominal 3D transport case before
   releasing the frozen 3D core.
2. Use the 3D decision to authorize either a small morphology pilot or a
   staged-plating model pivot; never run both speculatively.
3. Require a valid void-free Cu plug with positive overburden before the CMP
   recipe DOE.
4. Require individually qualified step metrics before the coupled traveler
   screen, then require unseen-seed confirmation before process-window claims.

On the 24 GB host, 3D transport runs at no more than two workers. A
multi-threaded film batch does not run concurrently with the heavy 3D batch.
Commissioning records wall time and peak RSS; pause rather than silently
changing a frozen matrix when a cell exceeds its declared resource guard.

Frozen simulation batches are direct local processes and do not depend on an
active language-model session. Each runner must:

- derive immutable case IDs from the manifest, source hashes, runtime binary,
  geometry, recipe, numerics, and seed;
- append every attempt to JSONL and save/hash the associated snapshot before
  reporting it complete;
- resume only verified successful case IDs and preserve invalid attempts;
- reject duplicate active launches through a campaign lock;
- expose PID, command, start time, heartbeat, log, and exit status under
  `autoresearch-results/runtime/<campaign>/`;
- run the reviewer only at a predeclared checkpoint and never change the
  manifest, targets, ranges, or stopping rule.

The project supervisor may retry the same frozen command after a process-level
failure because verified rows are resumable. It may not create a new design.
This lets ViennaPS continue for hours or days after a Codex session ends while
leaving scientific control with the next review checkpoint.

Launch an accepted manifest without an attached model session using:

```bash
scripts/launch-frozen-campaign.sh CAMPAIGN --max-restarts 2 -- \
  env PYTHONPATH=/path/to/exact-viennaps \
  .venv/bin/python -u FROZEN_RUNNER.py --workers N
```

Read `autoresearch-results/runtime/CAMPAIGN/status.json` for status and
heartbeat, and `run.log` for stdout/stderr. Restart by issuing the exact same
command; the runner, not the supervisor, verifies and skips completed case
IDs. The supervisor and detached launcher are guarded by
`test_frozen_campaign_supervisor.py`.

## Analysis package

Retain the full multi-output data. Do not analyze only scalar loss.

- Distribution, missingness, invalidity, topology, and hard-gate audit.
- Pearson and Spearman associations where appropriate, clearly labeled as
  exploratory rather than causal.
- Main-effect contrasts and standardized effect sizes.
- Nonlinear response surfaces for every important CTQ with observed samples
  and uncertainty shown.
- Hierarchical within-step and cross-step interaction models.
- Cross-validated global sensitivity/variance decomposition where the
  surrogate is accurate enough.
- Noise-versus-process variance decomposition using shared geometries.
- Feasibility probability and joint all-spec pass maps.
- Pareto fronts for competing CTQs.
- Local gradients, failure-boundary distance, and process-window width around
  finalists.
- Held-out residuals, lack-of-fit, extrapolation, boundary, and model-form
  warnings.

Dominance is accepted only when its ranking is stable across seeds, reasonable
analysis choices, and held-out validation. A near-zero correlation does not
reject a nonlinear or interacting factor.

## Checkpoints and generation records

- Append checkpointed rows in small atomic blocks; never overwrite prior
  campaign evidence.
- Record complete recipe, model version, metric version, grid, seed, geometry
  ID, upstream parent ID, timestamps, and code commit.
- Save raw meshes/images for all new failure classes, boundary winners,
  finalists, and audit samples.
- Run formal analysis checkpoints after the noise study, model-acceptance
  tests, broad screen, interaction study, refinement, boundary expansion, and
  confirmation.
- Every generation records hypothesis, held and changed factors, design,
  ranges, seeds, invalid rows, best feasible candidate, best miss, all CTQ
  passes/failures, uncertainty, interactions, boundary status, model
  implications, keep/discard decision, and next experiment.

## Model routing for the campaign

- Sol owns scientific planning, model acceptance, range changes, analysis,
  critical review, and publication claims.
- Frozen simulation manifests run as direct checkpointed shell batches by
  default. A language model adds no value while ViennaPS is CPU-bound and can
  consume substantial usage merely by monitoring the process.
- Terra may be used only for execution recovery or a bounded mechanical task
  that genuinely needs an agent. It does not make scientific decisions.
- The executor may not change targets, metrics, models, ranges, designs,
  replicate policy, or stopping rules. Any such decision returns to Sol.
- Execution runs stop at the formal analysis checkpoints listed above; Sol
  audits the rows and authorizes the next frozen manifest.
- Record `direct_batch_no_llm` as executor provenance for shell batches. When
  an executor model is genuinely used, record its exact model and CLI version.

## Visual evidence rules

- Use a fixed, accessible legend for silicon, SiO2, TaN, Ta, Cu seed, plated
  Cu, mask/stop material, and void.
- Transparent or sub-resolution layers use a contrasting outline or hatch;
  transparency must never look like absence.
- Seed and plated Cu may share a copper color family but retain separate
  boundaries/labels.
- A blank panel means invalid/erased geometry and is explicitly annotated.
- Quantitative rows remain authoritative; morphology images explain the
  mechanism and are required before accepting a new failure or pass.

The final report will include two clearly separated traveler views:

1. **Ideal reference traveler:** the target morphology after pattern, DRIE,
   liner, barrier/seed, void-free Cu plus overburden, and endpoint-controlled
   CMP. It is labeled as a specification schematic, not simulated evidence.
2. **Simulated traveler:** exact raw-material profiles from one accepted recipe
   at every step, with the corresponding CTQ values and margins. A step
   selector/scrubber will let readers follow how one shared geometry evolves.

Each panel uses the same axes, material colors, target bands, and annotations
so shape changes are visually comparable rather than decorative.

## Completion condition

The research is complete only when a full traveler passes all six declared
steps robustly on controlled, recorded stochastic confirmation runs, has a measured usable process window, and is
supported by auditable multi-output evidence. A completed campaign, improved
loss, or identified model ceiling is not completion. If credible model
alternatives are exhausted, that remains an active engineering blocker until
the strict goal-blocking criteria are met.

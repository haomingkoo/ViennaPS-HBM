# ViennaPS-HBM Context

## Domain

ViennaPS-HBM models the via-middle TSV traveler used for HBM-style memory stacks. The research objective is a defensible full-process result, not a single-step proxy win.

## Glossary

- **Full TSV traveler**: The six-step flow from patterning through CMP on one simulated via: pattern, Bosch etch, liner, barrier/seed, copper fill, and CMP.
- **Target spec**: The numeric pass/fail and score definition for each traveler step. `program.md` is the source of intent; `tsv_process.TARGET_SPECS` is the executable source.
- **Step target score**: A lower-is-better distance to one step target. It must include hard gates before any raw proxy ranking can matter.
- **Full-process loss**: The scalar research metric used by autoresearch. It combines p90 score, missing step passes, CMP mask consumption, and invalid metric penalties.
- **Depth-matched etch**: An etch comparison where candidate profiles reach comparable depth before straightness is judged.
- **Legacy fill tip gap**: The existing floor-relative center-height quantity. Its name and physical interpretation are under re-audit; it is not accepted as proof of a residual void or of void-free fill.
- **Resolved void-free fill**: A full-domain topology result with no open cavity,
  trapped component, or secondary open seam/mesh defect above the declared
  grid-dependent detection limit. It is not proof of metallurgical seam quality.
- **CopperSuppressionFill candidate**: An uncalibrated quasi-steady
  suppressor-access/rate model. It is neither CEAC nor S-NDR evidence and must
  run with void surfaces frozen so a trapped cavity cannot heal numerically.
- **Unresolved narrow-tail merger**: Two simulated Cu fronts remove a long
  centerline tail narrower than twice the bounded front motion plus one grid
  cell. It may conserve area, but the single interface cannot certify a
  metallurgically continuous seam-free plug, so it remains a hard fill failure.
- **CMP mask consumption**: A destructive polish outcome where the mask no longer survives. It remains a hard failure, but the legacy label must not hide Cu, oxide, silicon, or total-domain loss.
- **Invalid metric penalty**: A bad-region signal for failed or non-finite metrics. It should be retained in results, not filtered away as an outlier.
- **Autoresearch generation**: One planned DOE iteration that carries top candidates, adapts the factor space, runs replicates, reviews failures, and logs the next decision.

## Standing Constraints

- Report full traveler claims against the target specs, not raw proxies.
- Treat fill and CMP structural ceilings honestly when the model cannot satisfy the physical target.
- Review every generation for failed specs, replicate stability, hard gates, boundary artifacts, and the next decision before claiming progress.

## Active DOE methodology

`RESEARCH_PLAN_V3.md` is the active experiment sequence. Start with broad
low/nominal/high skews, rank direct effects and correlations against practical
detection thresholds, propagate exact saved geometries into downstream CTQs,
then run focused DOE on sensitive controls while retaining interaction-only
factors. Noise and numerical studies are qualification gates, not the campaign
objective. The old scalar-loss loop, repeat-heavy 640-case screen, and
Bosch-only S1 freezer are superseded and fail closed.

Stage 0 is complete. The R1 watcher intentionally stopped the batch after the
four 1,000-ray and four 2,000-ray anchors were present; the obsolete mask
ladder was not run. All eight native checkpoints independently validate.
The 1,000-ray arm is rejected because its depth, bottom-CD, and bow shifts
exceed the limits frozen before execution. Grid 0.00125, 2,000 rays per point,
and 2D are released only for exploratory V3 Pattern/Bosch Stages 1 and 2.
The four 2,000-ray checkpoints are immutable numerical baselines, not recipe
winners. The release does not authorize a mask-boundary claim, recipe,
process window, full traveler, fab setting, automatic launch, or a claim of
asymptotic ray convergence.

V3 Stage 1 launched as the frozen detached campaign
`v3-pattern-skew-stage1-20260713` at 2026-07-13 12:19 Singapore time. It runs
the complete 27-case opening-CD x mask-height x taper geometry screen with two
seven-thread workers, grid 0.00125, 2,000 rays per point, one shared reserved
seed block, depth-matched selection, native checkpoints, and a runner-level
duplicate lock. The direct batch uses no LLM. Stage 2a source is ready but is
unfrozen and cannot launch automatically; Stage 1 must finish and be reviewed
first.

V3 Stage 1 is now complete and independently reviewed: 27/27 native
checkpoints are valid, with zero execution failures. Opening CD strongly
propagates into etched CD, taper has a non-linear morphology effect, and mask
height has no promoted etch-shape main effect while erosion is fixed at zero.
Only the nominal 0.30 CD / 0.30 height / 2-degree taper case passes all pattern
and etch gates in this single shared random block. These are confirmation
hypotheses, not a recipe or yield claim.

V3 Stage 2a is now the active detached campaign
`v3-pattern-bosch-stage2a-final-20260714`. It runs 96 broad Bosch recipes (50
exact anchors plus 46 space-filling points) with two seven-thread workers and
no LLM. Before freeze, its effect thresholds were corrected to include
`3*sqrt(2)*sample SD` from the four disjoint released nominal 2,000-ray
baselines, preventing independent-stream recipe differences below the measured
noise floor from being promoted. Runtime status is
`autoresearch-results/runtime/v3-pattern-bosch-stage2a-final-20260714/status.json`.

Stage 2a now has an adaptive analysis stop at the first 19 frozen rows: the
nominal recipe and exact low/high anchors for all nine Bosch controls. At the
observed throughput, waiting for all 96 before learning would take roughly six
days and is not acceptable autoresearch cadence. A detached watcher will stop
the supervisor at 19 rows; the remaining interaction and space-filling cases
will run only if the broad effect read justifies them. This operational pivot
was made after two rows, based on runtime and design structure rather than a
favorable metric, and is recorded in `prepare.md` and the state ledger.

Stage 2a screens nine process-response factors at zero mask erosion. The wired
`mask_ion_rate` coefficient is not silently omitted: it is an uncalibrated
model-sensitivity control and has its own adaptive Stage 2f hard-gate challenge
with mask-geometry and ion-transport interactions. Its outcome cannot be
reported as a physical resist-selectivity recipe without calibration.

## Active foundation re-audit

The 1,948-run campaign is complete as an execution record but is not an
accepted full-traveler solution. Its fill metric, CMP failure classification,
target geometry, range realism, screening design, pattern scoring, layer
coverage, dimensionality, resolution, and RNG semantics are under re-audit.

- Do not resume from an old winning recipe or scalar metric.
- Do not call model-coefficient ranges realistic without calibration or
  literature-backed scaling.
- Keep the original and candidate fill metrics separate until raw mesh,
  topology, and visual checks agree.
- Treat the legacy first-four-step pass labels as withdrawn: pattern echoed
  inputs, film coverage was directionally invalid, and width duplicated bulge.
- Treat 2D as a potential screening surrogate only; final physical authority is
  the periodically checked 3D cylindrical via.
- Record explicit ViennaPS ray seeds and numerical settings for every new run.
- A 14-cycle Bosch run consumes 43 sequential ray streams. Bases closer than
  43 are correlated checkpoints, not independent replicates; new manifests
  must reject them while reusing the same disjoint bases across compared arms.
- Pattern output is measured as bottom/middle/top CD, height, center shift,
  left/right taper, and aperture validity. `MakeHole()` is not a focus/dose
  model, so those geometry sensitivities cannot be relabeled as lithography
  recipe conclusions without calibration.
- The temporary pattern mask must remain open and resolved through the selected
  depth-matched Bosch cycle. Complete or sub-two-grid-cell mask loss is a hard
  numerical survival failure; its erosion coefficient remains uncalibrated.
- Treat total geometry erasure, substrate loss, Cu loss, and mask loss as
  separate CMP outcomes.
- Grid delta 0.01 is rejected; its DRIE depth bias against 0.005 was 0.03371.
  A single-cycle eight-cell anchor accepts 0.00125 for the focused 2D audit.
  The recovered four-seed full-cycle history has exactly one common passing
  checkpoint: cycle 13, with depth 1.223 to 1.311. Use it as the qualified
  downstream geometry checkpoint, not as a claimed global etch optimum.
- The 0.0025 seed-52000 profile reaches 1.468 in a domain ending at -1.5, but
  paired repeats at vertical extents 2.0 and 2.5 reproduce every audited CTQ
  within 4.4e-15. The apparent boundary-risk hypothesis is rejected; the
  fine-grid shift comes from repeated-cycle discretization/passivation behavior.
- Treat fill dose and fill product thickness as different quantities. The old
  dose range stopped at 0.26 for a 1.25-deep via; a directional control reaches
  the field near 1.25 but leaves impractical field-to-center relief.
- Use a full 2D cross-section for fill topology. Half/quarter 2D `MakeHole`
  geometries clip centerline voids at symmetry; secondary below-field open
  components are hard invalid topology, not void-free results.
- Candidate Cu fill must set `AdvectionParameters.ignoreVoids=true`, gate both
  the custom seed and plated Cu, retain pinch-off history, and pass the staged
  full-domain morphology qualification before entering a broad DOE.
- The 24-case checkpoint and eight-case fine-grid fill transition blocks all
  reproduce unresolved narrow-tail mergers. Exact width review withdrew the
  initial depth-only nonconservation diagnosis. The corrected four-arm pilot
  still has no accepted fill. Its clean 32-case access/coverage follow-up also
  has no pass: higher sticking pinches, merges, or invalidates topology, while
  lambda 1 and 2 at sticking 0.05 stay open but are censored at duration 3.
  The runner uses `base_seed + checkpoint`, so consecutive labels in that
  screen overlap heavily and are not independent replicates. The corrected
  72-case lower-sticking expansion used four bases spaced by 1,000 across its
  320-checkpoint horizon. All 72 rows are valid hard failures: 48 pinch/closed-
  void flags and 24 unresolved mergers, with overlapping invalid-topology flags
  on 13 rows. The leading region closes about 79% of cavity area but advances
  the floor only 0.0915 of 1.25 before failure. This is sidewall closure, not
  bottom-up filling, and remains model evidence rather than a production DOE.
- The exact five-material structural challenge now cleanly separates model law
  from representation. The current quasi-steady candidate creates a sealed
  lateral-closure void at both grid 0.01 and 0.005. A prescribed bottom-up
  morphology control on the same stacks is void-free, exceeds 0.15 minimum
  overburden, and preserves every protected interface at both grids. This
  rejects the candidate law and accepts only the representation control.
- Do not launch the first 84-case transport-sign draft. Independent prelaunch
  review found that it used only the continuity geometry, could combine sign
  and kinematic evidence from different designs, used too narrow an analytic
  coefficient interval for a model-family pivot, and did not freeze every
  claimed manifest field. The replacement must make the nominal 0.30 by 3.00
  tier authoritative and guard those conditions before execution.
- The corrected replacement completed 168/168 current rows with zero errors
  and a complete independent review. No tested sticking/source-power design
  passes the floor-versus-wall transport sign in either tier, and no analytic
  coefficient case clears the cross-tier H/a requirement. The closest coarse
  miss is sticking 0.025 / sourcePower 0; its worst flux ratios are 1.002 and
  1.021 (target below 0.95), and its worst velocity ratios are 0.998 and 0.957
  (target above 1.05) for continuity and nominal HBM. Treat this as a selector
  for numerical/boundary confirmation, not a terminal model-family rejection.
- The follow-up numerical confirmation completed 128/128 metric-valid logical
  cells with eight exact parent reuses and 120 reviewed new executions. The
  grid/ray/reflection factorial produces no class-changing interaction or
  identified artifact. Sticking 0.0125 improves the high-fidelity worst flux
  ratio from 1.01504 to 0.99297 by more than the largest paired numerical
  effect, but still passes 0/8 streams and reaches only 1.00298 worst
  floor/lower-wall velocity versus the target above 1.05.
- The first proposed 0.00625 follow-up was rejected before launch: its inherited
  boundary-hit cap of 1,000 was below maxReflections 1,600/3,200 and would have
  confounded the sticking comparison. The corrected campaign used a cap of
  6,400 and added eight newly executed, matched-cap 0.0125 controls. All 24 new
  cells are metric-valid. The 0.00625 arms are exactly converged between 1,600
  and 3,200 reflections, but pass 0/8 streams; their worst flux and velocity
  ratios are 0.988828 and 1.004256 against strict targets below 0.95 and above
  1.05. The worst-flux improvement from the matched 0.0125 control is only
  0.004147, below the predeclared 0.016714 continuation threshold. The 2D
  lower-sticking expansion therefore stops. Morphology and a model-family pivot
  remain unauthorized until an independently audited matched 2D-versus-3D
  transport bridge tests the capped 0.0125 control and converged 0.00625 miss.
  Recorded decision:
  `two_dimensional_transport_no_go_requires_matched_3d_before_pivot`.
- The first 10-case layer block had complete data but lacked a predeclared
  numerical decision. Its fingerprinted 12-case replacement passes all 14
  grid/ray tolerances across four shared seeds with no gate changes. Grid
  0.00125 and 2,000 rays per point are qualified for exploratory layer-factor
  screening only; the baseline liner and barrier/seed recipe still fails.
- The temporary pattern mask is stripped in controlled layer/CMP stacks. TaN,
  the registered `CuSeed` material, plated Cu, and the SiO2 stop remain
  distinct. The named seed identity survives resumable `.vpsd` serialization;
  the earlier anonymous numeric custom ID did not.
- The isolated `HeightMaterialCMP` C++ binding now advects one continuous
  height-by-material law and passes source/binary, Python/C++ parity,
  material-gating, deterministic tiny-stack, and 2D/3D binding checks. It is
  accepted only as an uncalibrated local morphology abstraction; it contains
  no pad-pressure physics. Signed-region connectivity now detects full and
  one-wall cuts, reports unresolved features at or below roughly two grid
  cells, and preserves all four material connections under the controlled
  Planarize arm at both qualification grids. CMP DOE remains blocked because no
  endpoint/window campaign has run, stop/plug loss limits are not yet declared,
  and no non-prescribed fill model has produced the required incoming plug.
- Continue from `RESEARCH_PLAN_V3.md`, `FOUNDATION_REAUDIT.md`, issues 06–09,
  and `autoresearch-results/restart_audit/state.json`. The legacy state file is
  retained as evidence, and the V3 ledger does not authorize automatic resume
  or launch. Runtime status files remain the execution record.

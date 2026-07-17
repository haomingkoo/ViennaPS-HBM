# TSV traveler test and gate audit

## Purpose and authority

This document classifies every standalone `test_*.py` file and separates four
questions that must not be conflated:

1. Does a metric or hard gate implement the declared study requirement?
2. Is a simulation numerically and procedurally auditable?
3. Does a model contain the mechanism needed to answer the process question?
4. Does the historical/public report still reproduce its frozen evidence?

A green historical or publication regression is not a current traveler pass.
Likewise, an ideal geometry control proves that a metric can recognize a target
shape; it does not prove that a physical recipe produces that shape.

The current product targets remain in `program.md`. Production scoring remains
suspended as stated there. This audit does not change a target, tolerance,
model coefficient, manifest, result, or research decision.

## Exact runtime matrix

The repository currently needs three separate ViennaPS binaries. Tests must be
routed by capability, not run under one ambient `PYTHONPATH`.

| Runtime | ViennaPS binary SHA-256 | CopperSuppressionFill | HeightMaterialCMP |
|---|---|---:|---:|
| Stock `.venv` | `0fb3e28628a60ae1206fde1f584fa55d1590e380569a5d7984fc8b6a34334480` | no | no |
| `/tmp/viennaps-copper-exact` | `8970850eb6d3ffbd621a454e70b8d4504e4d9d7d6e953312915c92fdc1c87a8d` | yes | no |
| `/tmp/viennaps-height-material-cmp-exact` | `d42733ed7b3355c9a8a94b45ce32b1d9536b6be9e7ff33165f172a08b49e54ef` | no | yes |

Use:

```bash
.venv/bin/python scripts/run_capability_tests.py
```

The default is a hash- and capability-verified plan; it launches no tests.
Execution is explicit because several tests contain real ViennaPS simulations:

```bash
.venv/bin/python scripts/run_capability_tests.py stock
.venv/bin/python scripts/run_capability_tests.py cu
.venv/bin/python scripts/run_capability_tests.py cmp
.venv/bin/python scripts/run_capability_tests.py all
```

The runner fails when a test is missing, listed twice, or added without an
explicit runtime classification. It does not bypass the independent source,
patch, and exact-binary checks in `test_height_material_cmp.py`.

## Authoritative test-family classification

`Product/metric` means a current CTQ or hard-gate primitive. `Method` means
provenance, numerical validity, resume behavior, model implementation, or
review logic. `Control` means a positive, negative, or limiting experiment that
cannot establish a process recipe. `Historical` and `publication` tests are
kept outside current scientific authority.

| Test | Runtime | Classification | Scientific authority |
|---|---|---|---|
| `test_api_knob_audit.py` | stock | Active method guard, partial | Wrapper signatures and selected API defaults only; not proof of a complete knob registry |
| `test_bosch_rng_schedule.py` | stock | Active method guard | Rejects overlapping Bosch phase-seed streams and retries failed rows |
| `test_capability_test_runner.py` | stock | Environment/runtime guard | Verifies inventory routing, exact hashes, capabilities, and clean `PYTHONPATH` selection |
| `test_cmp_controlled_stack.py` | stock | Active limiting controls | Ideal planarization, perfect selectivity, phenomenological removal, and destructive negative control; not realistic CMP authority |
| `test_cycle_history.py` | stock | Active method guard | Exposes monotonic depth checkpoints; not a robustness study by itself |
| `test_foundation_layer_audit.py` | stock | Active step/method guard, partial | Fingerprint and current liner gate logic; does not establish full-2D material connectivity |
| `test_freeze_pattern_bosch_screen_manifest.py` | stock | Active supersession guard | Proves the obsolete repeat-heavy 640-case screen cannot freeze under the V3 methodology |
| `test_frozen_campaign_supervisor.py` | stock | Active runtime guard | Lock, retry, heartbeat, status, and detached execution behavior |
| `test_full_process_review.py` | stock | Historical-only regression | Phase-one scalar reviewer and synthetic `target_score`; no V2 traveler authority |
| `test_layer_model_acceptance_design.py` | stock | Historical design guard | Preserves the unlaunched 640-case layer design for audit; V3 requires screen-then-focus redesign before launch |
| `test_layer_process_models.py` | stock | Active layer-model guard | Constant-field-dose directional/isotropic split, full-width morphology response, TEOS-versus-simple model distinction, isotropic representation control, and parameter bounds |
| `test_legacy_metric_guard.py` | stock | Active containment guard | Blocks the three retired phase-one joint scripts without an explicit override |
| `test_mask_erosion.py` | stock | Active pattern/etch model guard | Shared-stream monotonic mask erosion, complete consumption, and invalid positive erosion-rate rejection |
| `test_pattern_bosch_checkpoint_handoff.py` | stock | Active handoff guard | Hash-bound Gate-0 surface reconstruction on the original grid, independent CTQ comparison, no gate flip, and malformed-checkpoint rejection |
| `test_pattern_bosch_gate0.py` | stock | Active campaign-contract/reviewer guard | Frozen 24-case full-2D pattern/Bosch Gate-0 matrix, disjoint within-arm streams, hash-bound cycle-13 checkpoints, fail-closed resume, independent metric recomputation, numerical bridges, erosion bracket, and broad-screen-only authority; synthetic fixtures do not constitute campaign evidence |
| `test_pattern_bosch_screen_design.py` | stock | Historical design regression | Preserves the superseded 160-recipe/640-case matrix for audit; it has no active freezer authority |
| `test_pattern_bosch_screen_runner.py` | stock | Historical executor regression | Preserves fail-closed resume and metric behavior for old artifacts; no V3 launch authority |
| `test_process_reproducibility.py` | stock | Active method guard, partial | Same-seed mesh reproducibility and different-seed sensitivity; not stream-independence proof |
| `test_publication_data.py` | stock | Publication-only regression | Frozen counts, copy, HTML structure, and accessibility; never a simulation gate |
| `test_review_bosch_cycle_history.py` | stock | Active reviewer guard, partial | Failed-attempt recovery selection; current fingerprint validation remains open |
| `test_review_foundation_layer_audit.py` | stock | Active reviewer/method guard | Grid/ray pairing, drift, nonfinite data, fingerprints, and bounded exploratory authority |
| `test_review_foundation_metric_audit.py` | stock | Current pattern/etch gate guard | Initial opening validity, measured mask height, and resolved surviving post-etch mask |
| `test_review_pattern_bosch_checkpoint_handoffs.py` | stock | Active handoff-review guard | All four reviewed full-width shapes required, exact seed accounting, strict JSON, upstream-review binding, and reuse-only authority |
| `test_review_pattern_bosch_screen.py` | stock | Active broad-screen reviewer guard | Independent checkpoint/selection/gate recomputation, dominant invalid and hard-gate penalties, four-seed robust ranking, direction-aware adverse p90/worst summaries, boundary warnings, and refinement-only authority |
| `test_shared_upstream.py` | stock | Historical-only regression | Phase-one joint-runner grouping and source-literal check |
| `test_target_specs.py` | stock | Stale proxy regression | Retired `tip_gap`, `floor_reach`, and scalar target-score behavior; not an active target test |
| `test_full_2d_layer_metrics.py` | stock | Current product/metric guard | Both fields, both walls, floor, aperture, conservative asymmetry handling, rejection of symmetry-clipped input, and solid-region field-to-floor connectivity including cuts and sub-resolution films |
| `test_traveler_metrics.py` | stock | Current product/metric guard | Pattern, CD, taper, bow, quarter-layer thickness, solid connectivity, fill topology, overburden, CMP endpoint, dish, and stop-loss fixtures |
| `test_v3_methodology_guards.py` | stock | Active methodology guard | Blocks both superseded screen freezers and old state-ledger resume; requires screen, propagation, and focused-DOE sequencing |
| `test_gate0_publication_checkpoint.py` | stock | Publication evidence guard | Keeps Gate-0 denominators, mask-boundary language, and publication data aligned with audited rows |
| `test_native_domain_checkpoint.py` | stock | Active handoff guard | Verifies exact native ViennaPS domain save/load and rejects corrupted checkpoints |
| `test_pattern_bosch_discovery_s1.py` | stock | Superseded-draft guard | Preserves design/reviewer regression checks while proving the Bosch-only S1 runner rejects launch under V3 |
| `test_pattern_bosch_gate0_r1.py` | stock | Completed numerical-evidence guard | Validates the frozen paired ray anchors, independent streams, native checkpoints, resume rules, and bounded R1 authority |
| `test_watch_pattern_bosch_gate0_r1_anchors.py` | stock | Completed runtime-transition guard | Proves the watcher stops R1 only after the exact four 2,000-ray anchors validate; it cannot review, freeze, or launch another campaign |
| `test_v3_numerical_release.py` | stock | Active numerical-release guard | Independently reloads all eight fixed R1 checkpoints, rejects 1,000 rays at frozen limits, authorizes four 2,000-ray baselines and 2D exploratory Stage 1/2 numerics only, and keeps mask, recipe, process-window, traveler, fab, and launch authority false |
| `test_v3_pattern_bosch_stage2a.py` | stock | Active Stage 2a design/executor/reviewer guard | Enforces 96 unique broad Bosch recipes, exact low/nominal/high and interaction anchors, independent 2,000-ray seed intervals, numerical-aware effect thresholds, target-depth crossing with censoring, native resumable checkpoints, correlation/VIF preflight, grouped holdout checks, visible mask/cycle deferrals, and hypothesis-only authority |
| `test_v3_pattern_skew_stage1.py` | stock | Active Stage 1 design/executor/reviewer guard | Enforces the complete balanced 27-case pattern-geometry matrix, released 2,000-ray numerics, one explicit shared 43-seed nuisance block, measured pattern outputs, depth matching and target-depth crossing, native resumable checkpoints, effective numerical-aware thresholds, descriptive correlations/interactions, visible failures, and screening-only authority |
| `test_copper_fill_trajectory.py` | Cu | Active model/method guard | Checkpointing, topology transitions, material identity, disjoint streams, and fingerprinted resume |
| `test_copper_fill_transport_3d_bridge.py` | Cu | Active 3D model/method guard | Exact 24-cell bridge contract, genuine 3D geometry, sectors, provenance, review, and bounded authority |
| `test_copper_fill_transport_boundary_confirmation.py` | Cu | Active model/method guard | Frozen boundary matrix, cap/reflection convergence, invalid-row handling, and no automatic downstream authority |
| `test_copper_fill_transport_confirmation.py` | Cu | Active model/method guard | Frozen confirmation matrix, parent compatibility, retry handling, effects, and boundary trigger |
| `test_copper_fill_transport_sign_screen.py` | Cu | Active model/method guard | Regional transport-sign gates, analytic parity, complete matrix, resume, and no morphology ranking |
| `test_copper_suppression_fill.py` | Cu | Active model implementation guard | Coverage/rate algebra, material gating, access ordering, void freezing, and intact seed-to-Cu handoff |
| `test_foundation_copper_fill_structural_challenge.py` | Cu | Active model-acceptance control | Candidate versus prescribed morphology-positive control; model representation, not a recipe DOE |
| `test_morphology_fill_control.py` | Cu | Active metric/model control | Positive fill sequence and trapped-void negative control; no electrochemistry claim |
| `test_review_copper_fill_access_surface.py` | Cu | Active reviewer guard | Surface aggregation, censoring, fingerprint drift, invalid metrics, retries, and incomplete matrices |
| `test_review_copper_fill_boundary_refinement.py` | Cu | Active reviewer guard | Complete matrix, worst-seed ranking, censoring, retries, and current/superseded evidence |
| `test_review_copper_fill_regional_kinematics.py` | Cu | Active reviewer guard | Left/right regional rates, dynamic width, common-time comparison, missing snapshots, and bounded no-go logic |
| `test_review_copper_fill_trajectory.py` | Cu | Active reviewer guard | Unresolved seam rejection, attempts, partial JSONL, duplicate success, and fingerprint failures |
| `test_review_copper_fill_transition.py` | Cu | Active reviewer guard | Resolution-aware transition classes, fine-grid completeness, mesh re-audit, and retained errors |
| `test_review_copper_fill_transport_effects.py` | Cu | Active analysis guard | Descriptive main-effect/interaction decomposition explicitly scoped as non-calibration |
| `test_foundation_cmp_qualification.py` | CMP | Current product/model/method guard | Endpoint, residual metals, material connectivity, layer/plug survival, invalid geometry, resolution, and deliberately blocked undeclared loss limits |
| `test_height_material_cmp.py` | CMP | Active exact-model/provenance guard | Python/C++ law parity, exact 2D/3D binding, invalid parameters, source commit, patch, source, and binary hashes |

## Ranked blockers and disposition

### 1. No current V2 end-to-end traveler gate — legitimate

The only test named as a full-process review is the historical scalar reviewer.
The active tests qualify components. A V2 integration test should be added only
after individually qualified steps can be chained without replacing real
handoffs by analytic stacks. Until then, “all tests pass” must not be translated
into “the traveler passes.”

### 2. CMP survival limits are undeclared — legitimate hard blocker

Minimum retained stop thickness, maximum stop erosion, maximum plug-height
loss, and maximum plug-area loss remain unset. The values in the CMP tests are
test fixtures only. The CMP recipe DOE must remain blocked until provenance-
backed study limits are declared and hashed into its manifest.

### 3. Layer connectivity and combined minimum are incomplete — legitimate

The current foundation layer runner uses quarter geometry and sums separate TaN
and Cu-seed minima. The sum is conservative but is not the required co-located
combined thickness and can falsely reject a viable stack. A tested full-width
interface metric now exposes both fields and both walls, but it is not yet wired
to the stochastic Bosch checkpoints. The next bounded qualification should use
that metric, full-2D material-region connectivity, the existing liner-to-seed
combined-interface measurement, and a small Cu-seed-loss handoff stress before
fill.

### 4. Pattern-mask erosion is now guarded but not yet campaign-qualified

The Bosch wrapper now exposes bounded nonpositive mask erosion; monotonic loss,
complete consumption, initial opening validity, measured mask height, and a
resolved surviving post-etch mask have focused tests. Historical etch evidence
used the ideal zero-erosion setting, however. A physically defensible erosion
range and fresh depth-matched campaign evidence are still required before mask
survival contributes to a robust process-window claim.

### 5. Dimension safety is local rather than repository-wide — infrastructure

`tsv_process.py` still sets dimension 2 at import. The dedicated 3D bridge must
remain isolated from that dependency and must prove explicit `ps.d3`/
`viennals.d3`, triangular non-coplanar surfaces, sector population, and measured
3D geometry. A future general cleanup should remove import-time dimension
mutation, but it is outside this bounded slice.

### 6. Historical Bosch “four-seed” evidence is correlated — guarded going forward

The saved 52000–52003 blocks came from overlapping `base + process_index`
streams: a 14-cycle run consumes 43 sequential seeds. The new RNG-schedule guard
prevents repeating that mistake, but the old shapes remain historical geometry
blocks rather than four independent robustness replicates. Fresh evidence must
use disjoint base streams and preserve pairing across compared recipes.

### 7. Bosch provenance remains weaker than Cu provenance — infrastructure

Success-only resume is now guarded, but the foundation Bosch case identity does
not yet bind runner, metric, and runtime-binary hashes as comprehensively as the
Cu campaigns. Add those fingerprints before the next expensive Bosch campaign;
do not rewrite historical rows in place.

### 8. The custom runtime split is real — routed, not scientifically resolved

The capability runner removes the accidental test failure caused by executing
the CMP exact-hash test under the Cu-only binary. An end-to-end custom-model
traveler still needs either one combined qualified extension or a tested,
hash-verified saved-domain handoff between the Cu and CMP processes.

### 9. Retired scalar executables now fail closed; import-space cleanup remains

`TARGET_SPECS`, `target_score`, `floor_reach_metric`, and `fill_tip_gap` remain
for reproducible history. Every known executable consumer now requires an
explicit `--allow-legacy-metrics` override, and the guard test inventories all
eleven scripts. Active V2 runners do not use those scores. Moving the retired
functions out of `tsv_process.py` remains desirable, but is no longer a silent
execution path into optimization.

### 10. Current CMP-model registry coverage is explicit; limits remain open

The registry now records all nine `HeightMaterialCMPParams` fields, the
overpolish-dose ladder, exact CMP-runtime ownership, interactions, tested
qualification values, and four deliberately unset survival specifications.
Those records make the missing limits visible; they do not invent values or
authorize a CMP DOE. Per-runtime live API introspection should still be added
to the registry generator so future extension fields cannot drift unnoticed.

### 11. Staged Cu current/waveform physics is absent — declared model limitation

`CopperSuppressionFill` is a quasi-steady transport/coverage surrogate with
constant active and suppressed rate coefficients. The morphology-only staged
positive control is not electroplating physics. Complete the matched 3D
transport decision first. If the no-go survives, a stateful staged model is a
model-development experiment, not another coefficient sweep of the current
family.

### 12. Publication regressions can block evidence updates accidentally

The public-report test deliberately pins 1,948 phase-one travelers, 17 legacy
factors, and old mask-consumption terminology. Keep it as a separate publication
lane and update it atomically with reviewed public data. Never use it as a
scientific go/no-go gate.

## Gate order for the next campaign

1. Exact runtime and inventory routing.
2. Metric validity, complete rows, fingerprints, and hard failures visible.
3. Current step product gates.
4. Model-mechanism acceptance, including matched 3D where required.
5. Independent replication and numerical convergence.
6. Only then: DOE screening, response surfaces, interactions, refinement,
   unseen-seed confirmation, and process-window perturbation.
7. Publication regression after the scientific review artifact is accepted.

This order prevents a green legacy test, ideal control, lower scalar loss, or
wrong-runtime failure from deciding the traveler.

# Full TSV traveler DOE plan v3

Status: active methodology. This plan supersedes the DOE scale and sequencing
in `archive/historical-plans/RESEARCH_PLAN_V2.md`. Product targets in
`program.md` are unchanged.

Numerical profiles, failure logging, and the staged optimization loop follow
`NUMERICAL_AUTORESEARCH_PRD.md`.

## Research question

Which controllable inputs cause engineering-significant changes in their own
process step, which of those changes propagate downstream, and what settings
produce the widest robust full-traveler process window?

First, vary every real pattern and Bosch input across a broad range. Keep only
inputs that change the profile by more than normal simulation variation. Then
run the saved profiles through liner, seed, fill, and CMP to learn which changes
matter downstream. Use those sensitive inputs in the focused DOE and hold the
rest constant at documented nominal values.

Numerical checks support that question. They receive a bounded qualification
campaign before broad physical DOE because an unqualified cheap profile can
move the measured answer or waste most of the compute budget.

## Required sequence

1. **Broad skew screening.** Exercise every defensible input actually used by
   the simulator at low, nominal, and high conditions, supplemented by
   interior combinations spread across the full range.
2. **Rank effects.** Measure direct step effects, input-output associations,
   nonlinearities, and selected interactions against practical detection limits.
3. **Prove propagation.** Carry exact saved upstream geometries through fixed
   downstream probe recipes. Do not regenerate the geometry for each arm.
4. **Focus.** Run a response-surface DOE on sensitive controls. Hold a weak
   control constant only after its main effect and interactions are both below
   detection limits.
5. **Confirm and stress.** Use unseen seeds, boundary expansion, matched 2D/3D
   checks, and multivariate perturbations around finalists.

Fine local steps are prohibited before the broad surface establishes a local
gradient and a useful input resolution.

## Two ways a tuning knob can matter

- **Step-sensitive:** a control materially changes a critical output metric
  (CTQ), failure shape, or hard gate in the step it owns.
- **Traveler-relevant:** that change also alters a later CTQ, failure shape,
  hard gate, or distance to a downstream failure boundary. Failure shapes
  include bowing, pinch-off, seams, and voids.

An upstream control may be step-sensitive but traveler-insignificant. Report
that result rather than promoting it into the focused traveler DOE. CMP has no
downstream process, so its own endpoint, survival, dish, and erosion outcomes
are its traveler outcomes.

A weak main effect remains active when it participates in a validated
interaction.

## What counts as a detectable change

A change counts only when it is larger than engineering relevance, numerical
error, run-to-run variation, and geometry resolution.

For each output `y`, define the screening threshold:

```text
T_y = max(
    practical engineering change,
    observed numerical-fidelity shift,
    3 * paired stochastic SD,
    two grid cells for geometry outputs
)
```

Initial practical engineering changes are provisional one-fifth-of-target
heuristics. Minimum specifications are not literally symmetric margins. These
values are effect-resolution rules, not replacement specifications, and must
be revised when product provenance supplies better practical limits.

All dimensional values below are in model length.

| Output | Initial practical change |
|---|---:|
| Etch depth | 0.020 |
| CD at any scored depth | 0.012 |
| Wall bow | 0.006 |
| Liner minimum thickness | 0.004 |
| Liner conformality | 0.001 fraction |
| Barrier/seed minimum thickness | 0.0024 |
| Barrier/seed conformality | 0.003 fraction |
| Fill overburden | 0.030 |
| Void, seam, pinch-off, continuity, endpoint, or survival | repeated topology or gate transition |
| Exact-zero targets without a tolerance | metric-convergence error and at least two grid cells |

A main effect advances only when:

- its magnitude is at least `T_y`;
- its bootstrap 95% interval excludes zero;
- its direction repeats in at least 75% of paired runs that reuse the same
  upstream geometry; and
- recipes excluded from model fitting show the same effect.

Here, paired stochastic SD is the standard deviation of within-seed
differences, not the spread of unrelated recipes. Uncertainty uses a grouped
bootstrap over recipes or shared-geometry blocks.

An interaction advances when its difference-of-differences exceeds `T_y`, its
sign repeats on confirmation data, and adding it reduces grouped held-out RMSE
by at least 5%.

For an upstream control to become traveler-relevant, the exact shared-geometry
comparison must additionally cause a downstream effect of at least the
downstream `T_y`, a repeated gate/topology transition in at least three of four
paired blocks, or a material change in distance to a failure boundary.

## Broad ranges and useful input steps

- Include the wrapper default, accepted references, known failures, prior
  boundaries, and the complete defensible range for every screened control.
- Every continuous control receives explicit low, nominal, and high skews.
- The broad response span must be at least both `5 x` the combined run-to-run
  variation measured from repeated recipes and `2 x T_y`, or cross a
  specification/failure boundary.
- If the response is comparable with noise, increase the factor contrast or
  defensible range; do not insert smaller steps.
- If a winning point lies on an edge, extend that edge by 25% of the sampled
  range on its linear or log scale and test the old edge, new midpoint, and new
  edge on two disjoint seeds.
- Stop expansion only after the response turns, a hard failure appears, or a
  documented physical/API bound is reached.
- After screening, choose local input resolution from
  `delta_x = T_y / abs(local response gradient)`.

## Range evidence and calibration boundary

The current width 0.30 may be illustrated as 5 µm, giving aspect ratios 4.17
and 10 for depths 1.25 and 3.00. This aligns the deeper teaching tier with
NIST's approximate 5 µm by 50 µm TSV scale. It is a geometry anchor, not a
calibration of model time or velocity. [NIST TSV
metrology](https://www.nist.gov/publications/metrology-needs-tsv-fabrication)

Published Bosch examples span different masks, tools, and chambers. They
commonly use about 100–300 cycles, while individual passivation and etch steps
span roughly 1.5–10 seconds in the reviewed experiments. These values guide
physical context only. The repo's normalized rates, durations, sticking
probabilities, ion-source exponent, and reflection angle do not map to sccm,
watts, pressure, seconds, etch rate, or selectivity without measured
calibration. [Representative DRIE study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8150727/)
and [ViennaPS particle-model API](https://viennatools.github.io/ViennaPS/models/prebuilt/multiParticle.html)

Published conformal TSV stacks can use films near 100 nm liner, 32 nm barrier,
and 33 nm seed. The much thicker normalized teaching layers in this repo are
geometry and measurement controls. Barrier and seed must be measured
separately; geometric continuity does not establish dielectric reliability,
diffusion blocking, adhesion, or electrical plating continuity. [Conformal
TSV stack study](https://www.sciencedirect.com/science/article/abs/pii/S0167931713000592)

Physical bottom-up copper filling depends on bath composition, additive
concentration, potential or current, transport, wetting, and seed state. The
current sticking-by-source-exponent map is therefore a transport-model
sensitivity map, not a plating process window. [NIST suppressor-breakdown TSV
study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7543049/)

Product specifications, manufacturing noise factors, model coefficients,
numerical controls, and recipe controls remain separate. A model coefficient
does not become a fab setting merely because it is sensitive.

## Correlation and interaction analysis

Four different questions must not be collapsed into one correlation heatmap.

1. **Design independence.** Confirm that the DOE did not move several knobs
   together. Target maximum absolute Pearson and Spearman correlation below
   0.15; hard limit 0.25. Require VIF below 1.5 and disclose planned aliases.
2. **Knob-to-output effect.** Report Pearson, Spearman, standardized
   low-to-high effects, held-out permutation importance, and uncertainty.
3. **Knob interactions.** Identify when one knob's effect depends on another
   using hierarchical terms and sampled two-dimensional response surfaces.
4. **Downstream propagation.** Relate pattern/etch morphology to
   liner, seed, fill, and CMP outcomes while blocking on the exact upstream
   geometry and controlling the downstream recipe.

Near-zero linear correlation does not reject a nonlinear or interacting
control. Correlation is evidence for screening, not a causal claim by itself.

## First screening ranges

These are broad model-sensitivity ranges for the continuity geometry. They are
not calibrated fab recipes. Pattern entries are measured geometry
skews/robustness inputs because ViennaPS does not simulate exposure or develop.

| Input | Units | Low | Nominal | High | Main direct read | Downstream read |
|---|---|---:|---:|---:|---|---|
| Pattern opening CD | model length | 0.24 | 0.30 | 0.36 | transferred top/mid/bottom CD | liner/seed access and fill margin |
| Pattern mask height | model length | 0.24 | 0.30 | 0.36 | mask survival and aperture | etch and layer process margin |
| Pattern taper | degrees | -4 | 2 | 6 | transferred taper, bow, CD | conformality and aperture |
| Bosch etch time | model time/cycle | 0.20 | 0.50 | 2.00 | depth/cycle, CD, bow | layer and fill access |
| Initial etch time | model time | 0.10 | 0.30 | 0.50 | entrance CD and initial undercut | upper-wall coverage |
| Neutral-rate coefficient | model velocity/flux | -0.20 | -0.08 | -0.03 | depth, CD, bow | remaining aperture |
| Neutral sticking | probability | 0.02 | 0.08 | 0.30 | CD, undercut, bow | wall/floor coverage |
| Passivation thickness | model length/cycle | 0.003 | 0.005 | 0.040 | scallop, bow, CD | wall access and seed continuity |
| Passivation sticking | probability | 0.001 | 0.010 | 0.030 | passivation distribution | wall/floor accessibility |
| Ion-source exponent | dimensionless | 50 | 400 | 1,000 | directionality, bottom shape | floor access |
| Reflection-angle control | degrees | 25 | 45 | 90 | reflected-ion transport and CD | bottom/sidewall profile |
| Ion-rate coefficient | model velocity/flux | -0.22 | -0.10 | -0.04 | depth, anisotropy, bottom shape | layer/fill access |

The broad Bosch design uses log spacing for etch time, sticking probabilities,
passivation thickness, and ion-source exponent; signed rates use log spacing in
magnitude. Exact range provenance remains in the knob registry and frozen
design. Any factor whose full response remains below detection is expanded or
held only under the rules above.

Before a stage freezes, its machine-readable factor table must record name,
units, classification, low/nominal/high, transform, range basis, direct and
downstream outputs, held values, exclusion rationale, and predeclared
interactions. Installed API controls omitted from the current wrapper remain
visible in the registry and require a model-family decision; they cannot be
silently called insensitive.

## Experiment program

Each stage is frozen and reviewed separately. Conditional stages do not launch
when their model or metric gate fails. The 147-case first checkpoint generates
screening hypotheses; it cannot by itself confirm a factor or interaction.

The first broad decision checkpoint is 147 cases: the simulation fidelity
check, pattern matrix, broad Bosch screen, and targeted repeatability check.
The later conditional program is at least 1,500 cases plus adaptive
promoted-effect and full-downstream confirmation blocks. It is never launched
as one blind batch; every stage stops for review and model-gate decisions.

| Stage | Design | Simulation cases | Decision |
|---|---|---:|---|
| 0. Numerical profile qualification | Coarse-to-fine ladders for rays, grid, advection, domain, caps, and execution layout on a morphology-diverse panel | adaptive, capped per manifest | Select geometry-scoped discovery and confirmation profiles; no process conclusion |
| 1. Pattern skew | `3 x 3 x 3` low/nominal/high geometry matrix for measured opening CD, mask height, and taper, each etched with a fixed reference recipe | 27 | Pattern-to-etch propagation; no dose/focus claim |
| 2a. Broad Bosch screen | 96 unique recipes: center, every one-factor low/high skew, prior good/failure anchors, foldover/interaction anchors, and optimized space-filling points | 96 | Direct effect, curvature, correlation, and failure-boundary screen |
| 2b. Repeatability check | One disjoint repeat for 16 morphology- and factor-diverse recipes | 16 | Check model adequacy and choose contrasts for formal confirmation |
| 2c. Cycle-count effect test | Matched-total-dose 6/12/24-cycle comparison across four disjoint seeds | 12 | Test the known non-monotonic cycle effect at matched depth |
| 2d. Pattern x Bosch foldover | Four pattern profiles x three Bosch contrast settings x two shared seeds | 24 | Detect whether pattern shape changes Bosch factor effects |
| 2e. Promoted-effect confirmation | Low/high x four paired seeds per promoted main effect; `2 x 2` x four paired seeds per promoted interaction | 8 per main; 16 per interaction | Confirm effect direction before holding any knob constant |
| 2f. Mask-erosion model challenge | Bounded search beyond the surviving -0.04 coefficient, four-seed confirmation of the first survive/fail pair, then small shared-seed foldovers with mask height, taper, and ion transport | adaptive; up to 44 | Locate the resolved-mask hard-gate boundary and interactions without calling the uncalibrated coefficient a fab selectivity setting |
| 3a. Layer data-transfer and metric check | Four exact accepted R1 shapes through bounded liner/barrier controls | up to 20 | Validate saved-geometry transfer; no optimization claim |
| 4. Liner screen | 12 shared etched-geometry blocks x 5 predeclared low/nominal/high/foldover settings | 60 | Liner effects and geometry interactions |
| 5. Barrier/seed screen | 12 shared lined-geometry blocks x 6 predeclared low/nominal/high/foldover settings | 72 | Thickness, continuity, aperture, and upstream interactions |
| 3b. Layer downstream consequence test | 24 exact saved profiles: six good, six near gates, six distinct failures, six factor-space extremes; three accepted layer probe paths | 72 | Separate etch-sensitive from layer-relevant controls |
| 6a. Existing fill 2D-versus-3D decision | Execute the already-predeclared matched bridge for the accepted 0.0125 control and converged 0.00625 miss | 24 | Decide whether to retain or replace the rejected 2D model family |
| 6b. New fill model qualification | Low/nominal/high transport-sign challenge for a new/retained model only | 24 conditional | Decide whether the model can express bottom-up growth |
| 6c. Fill morphology | 12 shared seeded geometries x 8 balanced settings; only after 6b passes | 96 conditional | Void, seam, pinch-off, and overburden surfaces |
| 7a. CMP requirements and endpoint qualification | Declare stop/plug loss limits, then challenge three plug/topography classes across endpoint/overpolish controls | at least 24 conditional | Decide whether clearing and layer survival can coexist |
| 7b. CMP screen | 12 shared accepted plugs x 6 settings; only after 7a passes | 72 conditional | Endpoint, selectivity, and survival window |
| 7c. Full downstream consequence test | Continue the 24 morphology-diverse layer states through accepted fill/CMP probe paths | conditional | Establish fill/CMP traveler relevance |
| 8. 2D versus 3D cross-check | 24 deliberately diverse recipes, each in 2D and 3D | 48 | Authorize which 2D effects and rankings transfer |
| 9. Full-traveler DOE | 160 unique active-factor combinations plus 32 targeted repeats | 192 | Cross-step interactions and joint feasibility |
| 10. Focused refinement | New points around every credible feasible/Pareto region | 96 | Local response surfaces |
| 11. Boundary expansion | Up to eight edge directions x three outward levels x two seeds | up to 48 | Reject false boundary optima |
| 12a. Finalist screening | Six finalists x at least 32 unseen seeds in the qualified screening dimension | at least 192 | Tail/worst-case ranking; report tolerance bounds, not a stable p90 from sparse tails |
| 12b. Final 3D confirmation | Two finalists x 32 unseen nominal-HBM seeds, plus two finalists x 8 high-AR stress seeds | 80 | Required 3D authority and reported stress result |
| 13. Process-margin map | Two finalists x 96 blocked multivariate perturbations in 3D, with predeclared unique seed intervals and replicated center/boundary sentinels | at least 192 | Robust usable window |

For Stage 1, the pattern hard gate uses the raw mask opening intersected at the
silicon surface (`y=0`) against the exact 0.30 target, with one grid cell only
as numerical representation allowance. The CD sampled five percent up the
mask and the middle/top CDs remain profile diagnostics. The 0.24 and 0.36
inputs are deliberate stress conditions; the etch `+/- 0.06` band is not a
pattern tolerance.

`mask_ion_rate` is intentionally not mixed into Stage 2a's nine recipe-factor
surface. It is a wired but uncalibrated model coefficient that controls a hard
gate. Stage 2f must keep its failures visible, depth-match surviving profiles,
and test its interaction with mask geometry and ion transport. Its result may
qualify a simulator sensitivity or failure bracket; it cannot be reported as a
physical resist-selectivity recipe without calibration evidence.

## Focused DOE rule

After screening, the focused factor set contains every control that is:

- step-sensitive;
- traveler-relevant;
- part of a validated interaction; or
- still uncertain because the screening model failed held-out adequacy.

All other recipe controls are held at their documented nominal/reference
values. The focused manifest records every held value and the evidence used to
hold it. For up to five active continuous factors, use a three-level response-
surface design with explicit lack-of-fit points. With more than five active
factors, use a new maximin/D-optimal augmentation sized for the exact
hierarchical terms; do not fit an underdetermined interaction model.

This focused checkpoint occurs immediately after each step's screening,
propagation, and four-seed promoted-effect review—before that step's controls
enter the full-traveler DOE. Stage 10 is later refinement of the coupled
traveler, not the first focused DOE.

## Shared-geometry blocking

One upstream recipe and seed create one immutable native `.vpsd` geometry.
Every downstream alternative in a comparison deep-copies that exact domain and
uses the same declared downstream random block. Regenerating Bosch geometry for
each downstream arm is prohibited.

The propagation selection is based on factor-space and morphology diversity,
not only the lowest scalar loss. It must include feasible shapes, near-gate
shapes, distinct failure morphologies, and tested extremes.

## Model gates and current evidence

- Four current R1 native checkpoints are saved geometries verified as
  unchanged. They are four repeats of one recipe and qualify numerical
  fidelity and data transfer only; they cannot rank knobs or establish
  correlations.
- A limited four-shape liner/barrier data-transfer and metric check may run
  after R1 review. It is not optimization evidence.
- The authoritative 24-shape propagation bridge waits for the broad screen to
  produce morphology-diverse native checkpoints.
- Liner and barrier/seed DOE waits for accepted local-thickness, continuity,
  aperture, and model-family tests on exact Bosch shapes.
- Fill morphology DOE is prohibited until the candidate transport field makes
  the floor less suppressed and faster than the walls on every paired stream.
  The current 2D suppression law is rejected and remains a known failure
  reference.
- CMP recipe DOE is prohibited until an accepted incoming plug exists and the
  model clears field metals while preserving plug, liner, substrate, and the
  durable stop layer. One-rate isotropic removal remains a known over-removal
  failure.
- Physical dose, focus, gas-flow, pressure, power, bath chemistry, and pad-
  pressure conclusions remain prohibited where the current wrapper exposes
  only geometry proxies or uncalibrated model coefficients.

## Immediate execution order

1. Finish the current 250-ray commissioning run and retain its rows. Because
   the campaign changes more than ray count and has no frozen online stop
   event, report mismatches without granting or withdrawing authority.
2. Freeze a clean ray-count qualification on one morphology-diverse panel.
   Hold stopping rules fixed and include null, near-gate, failure, curvature,
   and interaction sentinels. Treat 500 rays as provisional until it passes.
3. Qualify grid, advection, domain, cap, and execution settings on the same
   panel. Treat 2,000 rays as a tested reference, not numerical truth.
4. Run a four-shape downstream data-transfer and metric check after layer
   metrics/model acceptance; label it diagnostic.
5. Freeze Stage 1 and Stage 2a/2b with broad skews, independent RNG intervals,
   native checkpoints, and effect/correlation output. These stages cannot
   recommend process settings.
6. Select the 24-shape propagation set from observed broad-screen results.
7. Run the Pattern x Bosch foldover and four-seed confirmation for every
   promoted factor/interaction.
8. Run the focused DOE only after the effect and propagation reviews produce a
   hashed active-factor list and documented held constants.

No old scalar-loss loop, 640-case repeat-heavy Bosch screen, phase-one fill
ranking, or phase-one CMP ranking may resume this plan.

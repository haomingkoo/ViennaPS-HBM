# Interactive TSV tutorial

## Outcome

Teach a new engineer how one simplified TSV moves from mask opening to CMP.
The guide must show how equipment controls affect physical mechanisms, how
ViennaPS represents those mechanisms, and how measured geometry feeds the next
decision.

The teaching outcome is how to study process margin, not how to draw an
ideal-looking profile. Here, margin means distance from a failure boundary in
the tested simulation range. It is not verified fabrication margin. For each
step, a learner should be able to name the failure, the machine controls that
can move it, the modeled surrogate, the measurement that detects recovery, and
the tradeoff that can create another failure.

This document governs the public tutorial. `program.md` records the campaign's
assumed comparison targets and research rules; it is not a source of calibrated
fab limits.

## Required learning flow

1. Show the six major process steps and the purpose of each layer.
   Explain that the modeled structure is still a blind via. Later wafer thinning
   exposes the bottom and completes the through-silicon connection.
2. Separate equipment controls, physical effects, ViennaPS inputs, numerical
   settings, and measured outputs.
   Mark the equipment-to-model relationship as qualitative unless a calibrated
   conversion exists.
3. Compare at least two controls together for every step-level sensitivity
   viewer.
4. Show actual saved or reproducibly replayed simulation geometry. Do not use a
   drawing as evidence for a simulated result.
5. Measure the result. Use depth, width, coverage, aperture, void, overburden,
   endpoint, and connectivity where the implemented step supports them.
6. Show passing controls and failures separately. A prescribed geometry control
   is not a candidate physical model.
7. State the next decision and what the evidence does not prove.
8. Before the studies, annotate one cross-section with the measurement
   locations: depth, top/middle/bottom width, bow, film thickness, remaining
   opening, void, copper above the surface, field, plug recess, and stop loss.
9. Label each interactive result at the point of use as a saved sensitivity
   example, screening DOE, confirmation, prescribed control, or teaching sketch.
10. Show a saved failure/recovery pair for each supported failure mode. State
    the controls changed, the measurement boundary crossed, and the cost or
    downstream tradeoff. If both outcomes have not been reproduced, label the
    boundary unresolved.

## Evidence rules

- Every public result links to a schema-validated JSON file.
- Public citations must validate from a clean clone.
- Replay builders may require ignored native checkpoints. Their committed
  publication data must cite a committed source bundle.
- Missing values stay missing. They do not become zero or a pass.
- Intermediate etch cycles show measurements but do not receive final recipe
  acceptance.
- Invalid geometry, a missing required layer, or an unresolved seam or void
  stops the affected interpretation. Missing an assumed depth band is reported
  as a comparison result, not a physical process failure.
- Model coefficients are not machine settings. Quantitative conversion requires
  tool-specific calibration data.
- A configured target is not external evidence. Each visible threshold must be
  classified as calibrated, literature-derived, geometry-derived, assumed, or
  unresolved. A measured value is a result, not a source for its criterion. An
  assumed target may organize a comparison but cannot qualify a physical process.
- Raw measurements remain visible when acceptance is suspended.

## Screening DOE contract

A screening DOE identifies which factors move useful measurements. It does not
start by declaring a recipe winner.

1. Vary several factors together with a named design matrix.
2. Include repeated reference or center cases to estimate simulation noise.
3. Measure both the current step and relevant downstream handoffs.
4. Report effect sizes, interactions, uncertainty, invalid runs, and runtime.
5. Retain identical upstream geometries for fair downstream comparisons.
6. Promote a factor only when its observed effect is larger than numerical and
   repeat-to-repeat variation.
7. Refine the range only after screening identifies useful factors and cliffs.

The nine-cell step viewers are saved sensitivity examples. They are not a
completed screening DOE, an interaction estimate, or a process window.

## Delivery sequence

1. **Inventory complete:** keep one generated contract for active controls and
   comparison criteria.
2. **Measurements and speed settings not ready:** finish detection limits,
   numerical drift, repeat variation, and useful-change thresholds. The current
   numeric bands remain assumed comparisons rather than fabrication limits.
3. **Range pilot complete:** the first mask-plus-Bosch pilot used 25
   three-level cases across 12 implemented controls. Twenty cases returned all
   14 declared measurements. Five final geometries were saved but the declared
   wall-intersection measurement could not read them. Its
   0.01-grid, 250-ray profile is intentionally unqualified and supports only
   validity, runtime, raw response spans, contrasting observed states, and
   selection of cases for confirmation. It cannot attribute an effect or locate
   a boundary.
4. **Repeated screen is a draft and blocked:** the proposed 54-case screen uses the same
   25-row matrix with two declared random-stream blocks and four independent
   reference repeats. It remains blocked until the measurements and exploration
   profile are qualified for screening.
5. **Experiments pending:** run bounded per-step screens before focused tuning.
   Preserve invalid, missing, stopped, and retried cases as separate outcomes.
6. **Tutorial in progress:** replace teaching sketches with saved simulation
   frames, measurement overlays, and evidence-linked conclusions.
7. **Release pending:** regenerate stale data, pass CI and browser checks, then
   publish the same committed HTML that was reviewed.

Delivery is tracked in six outcome-based issues:

- [#11: corrected pilot evidence](https://github.com/haomingkoo/ViennaPS-HBM/issues/11)
- [#12: fast exploration setting](https://github.com/haomingkoo/ViennaPS-HBM/issues/12)
- [#13: repeated mask/Bosch screen](https://github.com/haomingkoo/ViennaPS-HBM/issues/13)
- [#14: downstream multi-factor studies](https://github.com/haomingkoo/ViennaPS-HBM/issues/14)
- [#15: concise teaching guide](https://github.com/haomingkoo/ViennaPS-HBM/issues/15)
- [#5: CI and evidence-gated deployment](https://github.com/haomingkoo/ViennaPS-HBM/issues/5)

No current stage authorizes a fab recipe, calibrated process limit, or robust
full-traveler process window.

Before designing the matrix, maintain one factor registry covering every active
traveler step. Each entry must include:

- factor name and owning process step;
- code and configuration location;
- classification: starting geometry, physical/model, numerical, or fixed
  implementation detail;
- plain-language mechanism and expected measurement response;
- equipment influences, with no claimed conversion unless calibrated;
- low, reference, and high values with a source or an explicit `unknown`;
- constraints, invalid combinations, and downstream measurements affected;
- runtime cost and whether a restart from an upstream checkpoint is possible.

No factor enters the DOE with an invented range. Unknown range provenance is a
research task. Numerical controls such as grid spacing and ray count are tuned
in a separate stability study and are not mixed with physical factor effects.
The current inventory is maintained in `docs/factor-registry.md`.
Source-backed range findings and unresolved mappings are maintained in
`docs/range-research.md`.
The experiment contract and response map are maintained in
`docs/screening-doe-plan.md`.

The initial screen must cover all eligible implemented model factors. If the
factor count is too large for one unaliased design, use sequential blocks with
declared aliases and bridge cases. Do not silently drop a factor because it is
slow or inconvenient.

Keep the complete registry as advanced provenance. The main tutorial shows a
smaller generated table containing only active teaching factors, explored
values, evidence class, affected measurements, and the missing calibration.
Do not present unwired APIs, legacy controls, or numerical settings as machine
tuning knobs.

## Completion checks

- Desktop and mobile layouts have no overlap or horizontal overflow.
- Every slider selects a saved or replayed frame and changes the visible shape.
- Dynamic studies use at least five checkpoints.
- Pass criteria come from the evidence data rather than duplicated page values.
- The copper candidate replay marks the first unreliable transition and stops.
- Browser tests cover interactions, measurements, warnings, and source links.
- The deployed page matches the committed HTML and passes CI.
- Every active DOE factor is registered and read from configuration. Public
  builders do not duplicate its value in page copy or a second code path.
- CI fails when a registered factor loses its source, classification, range
  status, measurement feedback, or implementation locator.

The tutorial can teach an incomplete model. It cannot call that model a
fab-ready recipe or a validated full-traveler process window.

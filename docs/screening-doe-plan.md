# Screening DOE plan

Status: the 25-case range pilot and its classification recovery are complete.
The legacy extractor returned values for 20 rows, but its etch values are
suspended because it mirrored one wall in a full-width geometry. The five
incomplete rows now have explicit availability classes. The active extractor
requires both walls. Factor levels and speed settings remain exploratory. The
repeated 54-case screening study is a draft and cannot run because resolution,
repeat, numerical, and useful-change checks remain incomplete.

Tracker: [fast-setting confirmation #12](https://github.com/haomingkoo/ViennaPS-HBM/issues/12)
must finish before [the repeated screen #13](https://github.com/haomingkoo/ViennaPS-HBM/issues/13)
can run. Phase A did not advance 250 rays and Phase B did not advance 500 rays
for their tested categorical scopes. The next unit is a six-case 1,000-ray
bridge with four disagreement cases, `width_boundary_candidate:stream_3`, and
`current_grid_reference:stream_1`. Each pair must preserve measurement
availability, reason codes, selected cycle, resolution, finite required metrics,
and its depth, width, and bow band results. The bridge does not qualify a
screening profile by itself.

## Next freezeable screening unit

The completed 25-case pilot is coarse range finding under its stated limits.
It uses a definitive-screening matrix as an efficient 25-point coverage pattern;
formal screening inference is withheld.
Do not launch the repeated mask-plus-Bosch screen until one immutable,
schema-validated manifest contains:

- the complete implemented factor list, with each factor marked `include`,
  `fixed`, `separate_block`, or `blocked` and a reason;
- qualified low, reference, and high levels for included factors;
- exact measurement definitions, regions, units, detection limits, controls,
  numerical drift, repeat uncertainty, and useful-change thresholds;
- an approved exploration profile and a separate confirmation profile;
- exact upstream geometry, streams, repeats, blocks, run order, interactions,
  case rows, case caps, stop checks, retry permissions, and cache keys;
- runner, source, environment, checkpoint, and output provenance; and
- a versioned analysis contract that links every effect to source rows and
  records aliases, uncertainty, thresholds, and held-out checks.

The active teaching contract and the full implementation inventory are not
experiment manifests. Every included factor must cross-reference one registry
record, or the active contract must be declared the sole canonical experiment
source before a matrix is generated.

[`pattern_bosch_factor_projection.json`](../pattern_bosch_factor_projection.json)
accounts for all current mask/Bosch registry records. Twelve implemented controls
enter main range finding. Mask height and modeled mask erosion form a separate
boundary block. Older campaigns may supply evidence, but absence from an older
matrix is not a reason to exclude a control.

The current mask-plus-Bosch measurement definitions and unresolved qualification
fields are recorded in
[`pattern_bosch_measurement_contract.json`](../pattern_bosch_measurement_contract.json).
Its `null` fields are blockers, not values to estimate or fill by convention.

## Question

Which implemented model factors produce changes larger than numerical and
repeat-to-repeat variation in:

- the measurements at their own process step; and
- the measurements inherited by later process steps?

The screen does not determine a fab recipe. Model-to-equipment calibration is a
separate task.

## Endpoint used by the first Bosch screen

The first recipe screen treats completed cycle count as a process control and
measures the final saved cycle. Etch depth is therefore a response, not a
checkpoint-selection target. A row that is shallow, too deep, or numerically
invalid remains boundary evidence.

A separate depth-matched morphology view may select the checkpoint nearest a
declared depth for shape comparison. It must not estimate the effect of cycle
count or be combined with the recipe-screen analysis.

The wrapper also contains coupled controls. `deposition_thickness` sets polymer
deposition and equal-magnitude directional polymer removal.
`ion_source_exponent` affects silicon-ion transport and polymer removal. The
design and analysis must retain those couplings rather than label either result
as a pure physical mechanism.

## Gate vocabulary

- **Validity gate:** the run completed with matching provenance, valid geometry,
  and required measurements. This is mandatory evidence hygiene.
- **Representation gate:** the model and grid can resolve the event being
  claimed. An unresolved seam or missing layer measurement stops interpretation.
- **Handoff gate:** the modeled input required by the next step exists, such as
  an open aperture or connected geometric seed. It is a model-state condition,
  not automatically a fab limit.
- **Assumed study band:** an inherited numeric comparison target. It may organize
  plots but cannot qualify a physical process.
- **Literature-derived criterion:** a published threshold whose material,
  geometry, measurement method, and application match the modeled question.
- **Geometry-derived criterion:** a threshold calculated from the declared
  geometry and handoff requirement, with the derivation saved.
- **Calibrated acceptance limit:** a sourced product or process requirement tied
  to physical units, measurement method, and application. None is currently
  established for this tutorial's normalized geometry bands.

## Why this is staged

NIST describes screening designs as a way to identify important main effects
among many candidate factors before response-surface fitting. NIST also warns
that fractional designs have an alias structure that must match the intended
model. Center runs help reveal curvature and instability. Constrained,
hierarchical, or hard-to-randomize problems may require a computer-generated
design rather than a standard fraction.

Sources:

- [NIST screening designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3346.htm)
- [NIST fractional factorial designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri334.htm)
- [NIST adding center points](https://www.itl.nist.gov/div898/handbook/pri/section3/pri337.htm)
- [NIST modeling DOE data and aliases](https://www.itl.nist.gov/div898/handbook/pri/section4/pri43.htm)
- [NIST computer-aided designs for constrained experiments](https://www.itl.nist.gov/div898/handbook/pri/section5/pri51.htm)

## Stage 0: qualify observation and cost

1. Freeze metric definitions, units, sampled regions, and missing-value rules.
2. Reproduce one known failure and one prescribed positive control for each
   topology or continuity measurement.
3. Benchmark grid, rays, time step, repeats, threads, domain size, and save
   cadence separately from the process factors.
4. Measure paired numerical differences and repeated-seed variation for every
   response used by the DOE.
5. Record runtime, memory, retry reason, invalidity class, and checkpoint reuse.

The smallest numerical setting that preserves useful shapes, effect directions,
and measurement resolution becomes the exploration profile. Higher settings
confirm boundaries and finalists. A documentation example value is not a
qualification result.

## Stage 1: range finding

Use `docs/factor-registry.md` as the complete audit inventory. Build the design
from records whose DOE eligibility permits the current stage. For every eligible
factor:

1. obtain a published or model-documented range that applies to the same factor,
   or record the range as unknown;
2. when no transferable range exists, preregister a small exploratory model-space
   bracket and state why each endpoint is safe to test;
3. test low, reference, and high with paired streams for direction and separate
   independent streams for run-to-run variation;
4. retain valid modeled boundary events and assumed-band misses as evidence;
5. shrink only numerically invalid ranges;
6. expand a quiet edge once when the model and mechanism allow it.

Exploratory levels may enter range finding, but not the screening matrix until
they produce valid measurements or bracket a modeled boundary. They never become
fab ranges without calibration.

For the current 12-control mask/Bosch block, the coarse range pilot uses a
25-run three-level definitive screening matrix. The exact coded design is saved
in `pattern_bosch_range_pilot_design.json`. It has rank 13 for the intercept and
12 linear terms, zero pairwise linear-factor correlation, and zero coded
cross-products between main effects and quadratic or two-factor-interaction
columns. Those diagnostics verify the matrix construction; they do not qualify
the ranges, simulation settings, or resulting effects.

The later screening study will repeat the 25 rows with two declared random
streams and add four independently seeded reference repeats, for 54 simulation
cases. That repeated design remains blocked until the measurements and faster
simulation profile are qualified for screening.

The coarse pilot may report invalid regions, raw response spans, and contrasting
observed states at its named setting. It may nominate cases for confirmation.
It cannot attribute a factor effect or locate a boundary, and it does not
estimate screening effects, uncertainty, curvature, or two-factor interactions.
The repeated screen may estimate broad main effects and curvature flags after
its blockers clear.
Promoted interactions then use held-out 2×2 bridge panels. Required bridges
include cycle count with etch time and polymer amount. They also include etch
time with both removal coefficients and ion direction with the reflection
threshold.

Source: Jones and Nachtsheim describe three-level definitive screening designs
with `2m + 1` runs for `m` quantitative factors. Main effects are separated from
second-order effects, but interaction interpretation still requires care:
[A class of three-level designs for definitive screening](https://doi.org/10.1080/00224065.2011.11917841).

## Stage 2: step screening

Use a named fractional-factorial, definitive-screening, or computer-generated
design selected after the eligible factor count and constraints are known. The
frozen design report must contain:

- coded and natural factor levels;
- design type, run count, blocks, center/repeat rows, and randomization rule;
- model-matrix rank, pair correlations, and alias table;
- main effects and only predeclared mechanism-supported interactions;
- exact upstream checkpoint and random stream for every row;
- planned step and downstream responses;
- estimated runtime and a resumable batch manifest.

The following blocks remain separate:

- mask geometry and Bosch etch;
- liner model family and its nested factors;
- barrier and seed, kept as distinct materials;
- copper mechanism qualification before copper morphology;
- CMP only after valid incoming fill and material-loss measurements exist.

Within a block, reuse the same upstream checkpoint to isolate downstream factor
effects. To estimate cross-step effects, add a small crossed bridge panel of
representative upstream checkpoints by promoted downstream factors. Treat the
upstream checkpoint and random stream as blocks; reused downstream rows are not
independent replicates.

For copper, screen transport access factors separately from kinetic balance.
Do not estimate active rate, suppressed rate, duration, adsorption, and
deactivation as independent effects when the parameterization confounds them.

## Measurement feedback

| Step | Immediate feedback | Downstream feedback |
|---|---|---|
| Mask | top/bottom opening CD, height, taper | etch depth/CD/bow and mask survival |
| Bosch | depth, top/mid/bottom CD, bow, scallop, neck | liner coverage and remaining aperture |
| Liner | field/wall/floor thickness, continuity, opening | barrier/seed coverage and fill aperture |
| Barrier | regional thickness, continuity, opening | seed access and fill aperture |
| Seed | geometric continuity, regional thickness, opening | copper model input; electrical continuity remains unmeasured |
| Copper | regional transport/growth, open/sealed void, seam history, overburden | CMP starting topology and endpoint demand |
| CMP | field clearance, plug/stop/material loss, connectivity | final geometric state only |

An upstream failure makes some downstream responses structurally unavailable.
Report the handoff outcome first. Estimate downstream continuous effects only
within the valid-handoff cases and name that conditional population. Do not
convert missing downstream values into a penalty or compare complete cases as
though they represented the original matrix.

## Promotion and stopping

A factor is promoted only when its effect:

- exceeds the maximum of measurement resolution, qualified numerical drift,
  repeat uncertainty, and the preregistered useful-change threshold;
- repeats in held-out or paired blocks;
- changes a relevant step or downstream measurement; and
- remains interpretable under the model's known limitations.

Promote an interaction only when its difference-of-differences exceeds the same
response-specific threshold and repeats in a held-out bridge case.

Stop a branch when the model cannot produce both outcomes, the measurement is
unresolved, every row fails the same upstream handoff, or another range split
cannot change the engineering conclusion. Freeze a batch cap, total case cap,
one permitted edge expansion, and minimum useful improvement before running.
Only promoted factors enter focused
response-surface work. NIST notes that a two-level design with center points can
detect curvature but cannot fit it; a second-order design is chosen only after
screening identifies a useful local region.

Source: [NIST response-surface designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri336.htm).

## Required public outputs

- schema-validated factor registry;
- frozen design matrix and alias report;
- active-factor and acceptance-criterion contract generated from real config
  keys and call sites;
- append-only run/event ledger;
- raw measurements with citations to saved rows and checkpoints;
- effect and interaction plots with uncertainty;
- step-to-downstream response map;
- invalid, censored, stopped, and retried cases;
- runtime and numerical-stability charts;
- a claim ledger that labels each conclusion measured, checkpoint-verified,
  literature-supported, assumed, or unresolved.
- schema-validated effect rows containing factor/interaction ID, response and
  metric hash, source row IDs, estimate, units, uncertainty, numerical and repeat
  envelopes, useful-change threshold, aliases, blocks, and held-out result.

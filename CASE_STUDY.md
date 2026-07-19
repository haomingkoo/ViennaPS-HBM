# Engineering a simplified TSV process study with ViennaPS

## Result

This project builds a simplified six-step TSV traveler and uses saved ViennaPS
geometry to study how model controls affect the shape passed downstream. The
strongest completed result is a focused 2D dry-etch region that repeatedly
produces target-depth, near-vertical walls with controlled top, middle, and
bottom CD. It is a simulation result in model space, not a fabrication recipe.

[Open the interactive guide](https://kooexperience.com/ViennaPS-HBM/explainer.html)

## Engineering question

The goal is not to make one attractive cross-section. It is to determine which
controls move decision-relevant measurements, reproduce known failure modes,
carry the same geometry through downstream steps, and identify where the model
or measurement can no longer support a claim.

The simplified traveler covers:

1. mask geometry;
2. Bosch silicon etch;
3. oxide liner;
4. barrier and copper seed;
5. copper fill; and
6. CMP.

## How ViennaPS is used

Each step combines a current material domain, a process model, numerical
controls, and a duration. ViennaPS moves the material interfaces. The updated
domain becomes the next step’s input. Separate measurement code then reads
geometry, coverage, topology, and connectivity from the saved state.

This project distinguishes four kinds of input:

- equipment controls, such as pressure, power, gas timing, current, or polish
  endpoint;
- physical effects, such as directionality, surface reaction, or selectivity;
- ViennaPS model coefficients that approximate those effects; and
- numerical settings, such as grid spacing and rays per point.

The last two are not equipment recipes. Mapping equipment controls to model
coefficients requires wafer measurements from a specific process.

## Measurement-first workflow

The first campaign showed why a large sweep can still be wrong. A copper score
used center height as a proxy for void closure, and an etch extractor mirrored
one wall even though the saved geometry contained two independent walls. Those
conclusions were withdrawn.

The corrected workflow is:

1. define the defect and measurement;
2. test a known failure and a clear control;
3. freeze geometry, inputs, random streams, and numerical settings;
4. run a multifactor screen;
5. keep every hard-gate measurement separate;
6. focus only on controls that move useful responses;
7. confirm finalists on unseen streams and a higher numerical setting; and
8. state the highest claim the evidence supports.

The full method is in [the experiment playbook](docs/experiment-playbook.md).

## Focused etch result

The most useful local interaction was between simulated ion-arrival
directionality and directional removal strength. A nine-cell focused map plus
repeats found a small straight-wall region. One selected saved profile reports:

| Measurement | Saved value |
|---|---:|
| Depth | 1.249 model units |
| Top CD | 0.331 |
| Middle CD | 0.323 |
| Bottom CD | 0.322 |
| Wall bow | 0.005 |
| Rays per point | 500 |

The profile has good wall shape for the assumed teaching comparison. Its floor
is still rounded or uneven. Floor peak-to-valley, center relief, symmetry, and
unresolved extrema remain separate qualification work; the project does not
hide that gap inside a single shape score.

Evidence:

- [focused profile export](bosch_tutorial_data.json)
- [cycle replay](bosch_trajectory_replay.json)
- [current interpretation](docs/current-run.md)

## Numerical-cost study

The project compared 250, 500, 750, 1,000, and 2,000 rays on the same three
etch profiles with three random streams each. Median runtime rose from 54.1
seconds at 500 rays to 206.5 seconds at 2,000 rays. Measurement movement and
repeat spread did not improve monotonically as rays increased.

A focused grid bridge found that grid 0.0025 was 3.6 to 5.0 times faster than
0.00125 on the tested local cases. Grid 0.005 changed the selected width
profile and was stopped. The working policy is therefore 500 rays and grid
0.0025 for exploration near this region, followed by a 1,000-ray check for
promoted cases.

This is a compute policy, not an accuracy percentage. No numerical setting is
treated as ground truth.

Evidence:

- [five-level ray review](evidence/numerical/bosch_ray_current_grid_ladder_review.json)
- [focused grid and ray bridge](evidence/numerical/v3_bosch_grid_speed_bridge_phase_b_review.json)

## Downstream learning

The project measures the handoff at every step:

| Step | Immediate feedback | Main downstream risk |
|---|---|---|
| Mask | opening CD, height, taper | restricted or shifted etch access |
| Etch | depth, CD profile, wall and floor shape | poor deep-film coverage |
| Liner | regional thickness, continuity, aperture | seed access and remaining fill opening |
| Barrier/seed | regional thickness and continuity | high resistance or inaccessible copper growth |
| Copper | regional growth, seam and void topology | invalid CMP starting state |
| CMP | field clearance, plug/stop loss, connectivity | recessed or disconnected final plug |

A prescribed copper motion is retained only as a measurement control. It shows
that the topology checks can recognize a clear geometric outcome. It is not
presented as electroplating physics. The tested transport law did not establish
the required bottom-up growth, so the physical copper-fill search remains open.

## Reproducibility and evidence

Experiments use frozen manifests, schema-validated rows, saved checkpoints,
source hashes, and reviews that state one decision and its limit. Unknown
measurements remain `null`. Failed and unresolved cases are retained instead of
being converted into zeros or hidden penalties.

The static guide can be opened from a clean clone. Numerical charts and their
source rows are committed. Some native simulation replays still require the
qualified local ViennaPS runtime and checkpoints named by their publication
exports; that boundary is stated in the [README](README.md#reproduction-boundary).

## What this demonstrates

- building and modifying multi-material ViennaPS process flows;
- implementing geometry, topology, continuity, and material-survival metrics;
- designing multifactor and numerical-sensitivity experiments;
- controlling stochastic comparisons and geometry handoffs;
- separating model coefficients from equipment settings;
- detecting and retracting invalid measurements;
- publishing interactive, citable simulation evidence; and
- stopping a search when missing physics prevents a defensible result.

## Next proof

The next bounded study will qualify floor-shape measurements, add repeated
floor-measurable cases around the focused etch region, and test a constrained
ask/tell search prospectively. A candidate earns promotion only if it preserves
depth, CD, wall and floor shape, validity, and numerical stability on held-out
executions.

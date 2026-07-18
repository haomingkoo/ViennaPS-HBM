# program.md -- objective

(Supersedes `archive/historical-plans/PRD.md`, the original design doc.
This is the current, standing objective -- update it when the goal changes,
rather than letting the notebook/README drift from what this says.)

The bounded feedback, logging, and numerical-speed protocol is defined in
`NUMERICAL_AUTORESEARCH_PRD.md`.

## Goal

Demonstrate real engineering capability with ViennaPS on a current,
concrete industry problem: forming and filling the TSVs that HBM4/HBM4E
memory stacks depend on. Not "run a simulation tool" -- "use data to find
out what actually controls the outcome, catch mistakes along the way, and
report an honest, defensible result."

## The three things that have to be right

1. **Straight etch** -- the TSV sidewall must not bow or scallop.
2. **Target depth** -- deep enough to connect through the die after
   backside thinning; nowhere near full wafer thickness (~700-775um
   pre-thinning; see `MAX_REALISTIC_ASPECT_RATIO` in `tsv_process.py`).
3. **Void-free fill** -- the copper fill must not trap an air pocket.

## Declared study product spec (the numeric target every comparison is graded against)

Stated once, here, so no comparison anywhere in this project (notebook,
README, explainer) compares two things at different depths and calls it
fair -- that mistake has already happened twice (prepare.md items 3 and
7) and once more in the explainer (uncaught until directly pointed out).
Every before/after, failure/fix, or DOE-winner claim must be evaluated
against these numbers, at matched depth:

| Metric | Spec | Rationale |
|---|---|---|
| **Depth** | 1.25 +/- 0.1 (sim units) | fixed study target retained for comparison continuity; its mapping to a physical HBM depth is not yet calibrated and must not be called a production recipe |
| **CD profile** | 0.30 +/- 0.06 at every scored depth | raw-boundary top/middle/bottom and sampled CD must stay inside the intended width band; this is independent of straightness |
| **Wall bow (straightness)** | <= 0.03 maximum radius deviation from a fitted straight wall | fixed study threshold; legacy outer-envelope estimates and the prior duplicated width/bulge metric are suspended |
| **Fill void/seam** | none (ideal) | no open cavity, sealed void, or seam under the raw-topology metric; the phase-one floor-relative quantity was not a residual gap measurement |

These are the fixed targets for the current study. Their physical-unit mapping
and tolerance provenance remain an explicit calibration gap; that gap does not
authorize silently moving the targets during optimization.

## Geometry tiers and physical interpretation

The phase-one geometry is retained for continuity, but it is not the sole
physical confirmation case. NIST reports typical TSV dimensions within roughly
a factor of two of 5 um diameter by 50 um depth, and a published via-middle
reliability study uses 3 um by 50 um. The traveler therefore uses three named
geometry tiers:

| Tier | Physical interpretation | Model geometry | AR | Role |
|---|---|---:|---:|---|
| Continuity | uncalibrated phase-one demonstrator | width 0.30, depth 1.25 | 4.17 | metric, software, and historical-regression qualification |
| Nominal HBM | 5 um x 50 um via-middle TSV | width 0.30, depth 3.00 | 10.0 | required mechanism and finalist confirmation |
| High-AR stress | 3 um x 50 um via-middle TSV | width 0.18, depth 3.00 | 16.7 | robustness and model-limit challenge |

The nominal mapping uses 5 um / 0.30 = 16.67 um per model unit. Under that
mapping the existing liner, barrier/seed, and overburden thresholds correspond
to about 0.333 um, 0.200 um, and 2.50 um, respectively. These are transparent
implied values, not calibrated production specifications. Geometry scaling
does not calibrate ViennaPS rates, time, bath chemistry, plasma settings, or
CMP pressure.

The continuity tier remains the numeric scoring case until its metrics and
models are qualified. It cannot by itself support an HBM success claim. An
accepted full traveler must also preserve the required morphology on the
nominal tier in matched 2D/3D checks and must report the high-AR stress result,
including failures. Sources: [NIST TSV metrology](https://www.nist.gov/publications/metrology-needs-tsv-fabrication)
and [3 um via-middle liner reliability](https://www.sciencedirect.com/science/article/pii/S016793171630034X).

If a future finding changes what "good" means, update this table
explicitly and say why -- don't let notebook/explainer prose drift to a
different implicit target than what's written here.

## Step target specs

Every DOE row must say which step target it is trying to satisfy and rank
by distance to that target, not by a raw proxy that happens to move. If no
tested row meets a target, report the best miss and run a wider DOE before
calling the space understood.

| Step | Target spec | DOE ranking rule |
|---|---|---|
| Pattern | measured bottom opening CD=0.30; mask height=0.30; connected opening | pass measured geometry first; taper is a structural input and may vary only if the complete traveler benefits |
| Etch | depth=1.25 +/- 0.1; every scored CD within 0.30 +/- 0.06; bow<=0.03; pattern mask remains resolved with an open aperture through the selected cycle | rank valid depth-matched profiles; complete or numerically unresolved mask loss is a hard failure; CD, taper, bow, and scallop remain separate outputs |
| Liner | minimum local thickness>=0.02; floor/field and lower-wall/field conformality>=0.995; continuous; aperture open | pass all functional gates first, then maximize margin and uniformity |
| Barrier+seed | combined minimum local thickness>=0.012; minimum floor/field conformality>=0.985; both layers continuous; seed aperture open | pass the distinct barrier and seed material gates first, then maximize margin |
| Cu fill | no open/sealed void or seam; reaches field; minimum overburden>=0.15 | topology gates first, then overburden margin and uniformity; input dose is not product thickness |
| CMP | field Cu/barrier clear; dish=0; durable stop layer, plug, liner, and substrate survive | survival and endpoint are hard gates; dish is scored only afterward |

For Cu fill, `thickness>=0.15` is a measured output: the minimum Cu
overburden above the field plane across the via center and sampled field after
the cavity is filled. It is not the input deposition distance. The legacy
`tip_gap=0` intent is now measured directly as no open cavity, sealed void, or
seam. This corrects an invalid proxy without relaxing the functional target.
In 2D, that topology gate requires a full cross-section (or a validated mirror
reconstruction), because a symmetry boundary can clip a trapped centerline
void. "No void" means none resolved above the declared grid detection limit;
pinch-off history remains a failure even if later level-set evolution merges
interfaces. A long narrow cavity tail removed by opposing fronts is recorded
as an unresolved centerline merger and remains a seam hard failure even when
its area change is numerically plausible. The model does not establish
metallurgical seam quality, so a later `void_free` mesh cannot erase that
history.

Fill-mechanism screens must separate floor, lower-wall, middle-wall,
upper-wall, mouth, and field flux/coverage/velocity. A center-versus-field
average is not evidence of bottom-up growth. Before a morphology DOE, the
candidate transport field must make the floor less suppressed and faster than
the walls on every paired stream, with axial advance able to outrun lateral
closure on the declared geometry.

When a trajectory derives checkpoint RNG seeds as `base_seed + checkpoint`,
replicate base seeds must be separated beyond the full checkpoint horizon.
Reusing the same effective seeds at shifted times is correlated evidence, not
independent replication. The same non-overlapping base streams should remain
paired across process alternatives for fair common-random-number comparisons.

The photoresist pattern mask is stripped after DRIE. CMP therefore protects a
separately represented durable field stop/hard-mask layer. The non-negotiable
"mask consumption" rule is preserved as stop-layer consumption: any complete
loss of that protected layer, or any liner/substrate damage, is a hard failure.

The table states target intent. Production scoring is currently suspended
until pattern, CD-depth, local film thickness, fill topology, CMP endpoint, and
material-survival metrics pass the qualification protocol in
`archive/historical-plans/RESEARCH_PLAN_V2.md`.

## Scope

Models Phase 2 of the real via-middle process only (pattern -> Bosch etch ->
liner -> barrier+seed -> Cu fill -> CMP), one via at a time, at single-feature
topography scale. Broad screening may use a qualified 2D trench surrogate, but
critical model checks, interactions, finalists, process-window evidence, and
the accepted traveler require matched 3D cylindrical-via confirmation on the
nominal geometry tier.

The active scope includes the scientifically defensible model improvements
needed to meet the fixed targets: coverage/transport-dependent Cu fill and
endpoint/selectivity/topography-aware CMP. The legacy constant-direction fill
and one-rate isotropic removal remain negative controls.

## Explicitly out of scope

- Package-level warpage, dummy-die stress, JEDEC thickness budgets
- TC-bonding vs. hybrid-bonding thermal/mechanical reliability
- JEDEC SPHBM4 signaling/clocking
- Intel ZAM, HBF, GPU-in-base-die, CoWoS vs. CoWoP packaging
- True inter-via loading effects (RIE lag) -- would need multiple vias
  sharing one domain, competing for reactant flux
- Package-scale or wafer-scale validation beyond one local via geometry
- Claiming fab-ready physical settings before model coefficients are calibrated
  to measured profiles, electrochemistry, and CMP data

## Current deliverables

- `RESEARCH_PLAN_V3.md` -- active broad-skew, effect/correlation,
  downstream-propagation, focused-DOE, confirmation, and completion sequence
- `archive/historical-plans/RESEARCH_PLAN_V2.md` -- retained metric/model qualification history;
  superseded for DOE scale and sequencing
- `FOUNDATION_REAUDIT.md` -- retractions, confirmed failures, and evidence gaps
- `docs/evidence-map.md` -- claim-to-artifact status and reproduction limits
- `autoresearch-results/restart_audit/` -- checkpointed foundation and campaign
  state
- `archive/` -- superseded campaigns and the original proof of concept
- A rebuilt notebook/explainer only after accepted metrics and a validated
  traveler replace the legacy phase-one claims

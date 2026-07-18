# Numerical autoresearch PRD

Status: active. This document defines how the project learns quickly without confusing cheap simulation with trustworthy evidence.

## Outcome

Find the cheapest geometry-scoped simulation profile that preserves the decisions made by a declared reference profile. Use it for exploration, then confirm boundaries and finalists at higher fidelity.

This work does not calibrate a wafer recipe. Physical controls, model coefficients, numerical controls, and execution settings remain separate.

## Feedback loop

Every case follows the same loop:

1. Freeze the question, upstream geometry, inputs, random stream, numerical profile, measurements, hard gates, budget, and stop rule.
2. Run the case and retain its last usable checkpoint.
3. Measure the raw outputs.
4. Evaluate execution validity and every hard gate.
5. Only for feasible cases, compare quality margin, robustness, and cost.
6. Log the evidence and choose one next action.

Before the loop, qualify each hard metric. Freeze its code hash, definition, sampling region, units, detection limit, missingness rule, and expected response. Test a known-negative and prescribed positive geometry plus save/reload parity. If the metric cannot recognize both states, the related DOE is ineligible.

| Step | Required feedback |
|---|---|
| Pattern | opening CD, mask height, taper, connected opening |
| Etch | depth; top, middle, and bottom CD; taper, bow, neck, scallop; mask survival |
| Liner | field, upper-wall, lower-wall, and floor thickness; conformality, continuity, remaining aperture |
| Barrier and seed | each film's regional thickness and continuity; remaining aperture; seed electrical evidence when available |
| Copper fill | open and sealed void topology, seam or pinch-off history, regional growth, overburden |
| CMP | field clearance, dish, erosion, stop loss, plug loss, and material connectivity |

A straight etch at the wrong depth is infeasible. Attractive secondary metrics may explain a failure, but cannot cancel it.

## Three separate ledgers

- **Scientific feasibility:** product measurements and hard gates.
- **Numerical reliability:** paired response shifts, stochastic spread, mesh allowance, topology and class changes.
- **Cost and tool feasibility:** wall time, queue time, memory, threads, backend, cycle count, estimated process time, checkpoint cost, timeout, and tool limits.

Do not blend these ledgers into one loss. First find feasible cases. Then maximize margin. Then minimize cost and complexity.

## Event log

Each attempt appends one hash-chained JSONL event with timestamp, case key, manifest hash, stage, state, inputs, environment, elapsed time, measurements, error, checkpoint, retry count, an explicit `retryable` boolean, decision, next action, and stop reason. Null remains null.

Simulation states are `planned`, `running`, `complete_measured`, `complete_invalid`, `failed_transient`, `failed_deterministic`, `missing_measurement`, `needs_investigation`, and `stale_provenance`. `complete_measured` does not mean the gates pass. Store metric validity, scientific-gate result, and numerical status separately. Literature searches use separate `search_failed` and `no_usable_evidence` states.

| Outcome | Required action |
|---|---|
| Transient tool or infrastructure failure | retry once with the same case key |
| Repeated or deterministic exception | reproduce once, save the smallest failing case, investigate |
| Invalid geometry | keep the row; shrink or reparameterize the range |
| Missing measurement | fail evidence review; repair the metric before scoring |
| Search returned no usable source | broaden once, then record the evidence gap |
| Stale provenance | do not reuse until exact compatibility is established |
| Model cannot express the required state | stop the DOE and open a model-change decision |

Only a first transient infrastructure failure is retryable. It records `retryable: true`, `decision: retry_same_case`, and the exact recovery action. Every other outcome records `retryable: false`. A stop decision requires a non-empty reason. Automation may act on these fields; it must not infer a retry from an exception string.

## Numerical study

Map cost and response for rays, grid spacing, advection step, domain clearance, reflection and boundary-hit caps, process horizon, workers and threads, and checkpoint frequency. Use paired physical inputs and random streams.

The representative panel spans aspect ratio, opening, depth, bow, necking, and near-gate cases. Numerical profiles are geometry-scoped until the panel shows otherwise.

Choose the cheapest discovery profile with margin before the observed cliff. It may screen ranges. It may not confirm a boundary or finalist. Promotion requires unseen streams and the reference profile.

Current evidence:

- A fresh 26-run Phase B panel compared 500 and 2,000 rays at grid 0.005.
  Every run completed with usable measurements. All three depth-boundary pairs
  changed the assumed depth classification, and one of three narrow-profile
  pairs changed the assumed bow classification. Therefore 500 rays does not
  advance for categorical triage on this panel. The observed paired runtime
  ratio ranged from 2.81 to 4.23, with a median of 3.71. These timings are
  descriptive, and 2,000 rays is not numerical truth.

- A fresh 32-run Phase A panel compared 250 and 500 rays at grid 0.005. Twenty
  runs returned measurements. Twelve low-movement runs triggered the configured
  minimum-depth guard symmetrically. The narrow profile changed the assumed
  bow-band decision in all three paired streams, and the availability challenge
  changed the assumed depth-band decision. Therefore 250 rays does not advance.
  Phase A does not qualify 500 rays.

- The saved 500-ray bridge preserved the reviewed Bosch classifications and factor ranking while reducing paired runtime by about 4.5 times. It is provisional because the campaign also changed random streams and early-stop intervals. It does not isolate ray count.
- An earlier fine-grid study rejected 1,000 rays against 2,000 because the
  largest paired shifts exceeded its frozen continuous limits for depth, bottom
  CD, and bow. No product-gate decision changed. This remains valid for that
  grid, panel, extractor, and decision rule; it does not answer the newer
  grid-0.005 categorical question.
- The five saved 125-ray cases include a required-anchor mismatch. The run ended without a frozen stop event, so this is a partial mismatch observation rather than a formal rejection.
- All 16 saved 250-ray cases completed. The review found one hard-gate mismatch and one strong-effect direction mismatch, despite a 0.943 factor-ranking Spearman and a 10.83x paired median speedup. It receives no discovery authority.
- Older grid results were non-monotonic. No universal grid optimum has been established.

The ViennaPS sources also do not define one universal ray count. The current
library default is 1,000 rays per point, the official process tutorial shows
500, bundled process examples commonly use 500 or 1,000, and flux-engine
benchmarks use 10,000. These are defaults and example settings, not accuracy
guarantees for this TSV geometry. The project therefore selects rays from
paired measurement and decision stability, not by copying the largest or most
common published value.

The exhaustive ray ladder is retired. Phase A and Phase B used frozen panels to
remove weak candidates without changing grid spacing at the same time. The
active next study is a six-case bridge at 1,000 rays. It contains the four Phase
B disagreement pairs, `width_boundary_candidate:stream_3` as the closest-band
agreement, and `current_grid_reference:stream_1` as the current-grid agreement
anchor. The exact completed 2,000-ray arms may be reused only after their
manifest, expanded case payload, measurements, and archived checkpoint all
match.

This bridge has a narrow decision rule. Every pair must preserve complete
measurement availability, reason codes, selected cycle, adequate resolution,
finite required metrics, and each depth, width, and bow band result. If all six
pairs match, 1,000 rays advances only to continuous-response and trajectory
checks. Any mismatch stops it for this Phase B scope. Runtime is descriptive
and cannot override a mismatch. The bridge neither treats 2,000 rays as truth
nor supersedes the older fine-grid rejection of 1,000 rays.

After the ray bridge, test grid spacing, advection, domain clearance, numerical
caps, execution layout, and save cadence one at a time on bounded representative
panels. A faster exploration profile is approved only after it preserves the
measurements and decisions required by the planned screen.

## Search sequence

1. Research ranges from official documentation and primary sources. Label missing calibration.
2. Run repeated nominal cases and low/high range finding.
3. Screen factors with a bounded design and exact shared upstream geometries.
4. Confirm only mechanism-supported interactions.
5. Refine at most five active factors with a response surface. Use constrained Bayesian optimization only when held-out checks reject the simpler surface.
6. Confirm up to three finalists with unseen streams, adverse boundary points, higher fidelity, and required 3D checks.

Adam is not the default. This simulator is expensive, partly discrete, stochastic, and discontinuous at topology and validity boundaries. Designed experiments and constrained black-box optimization are more suitable.

## Guardrails and completion

- Targets, metric definitions, ranges, fidelity profiles, and model family cannot change inside a manifest version.
- Failed, missing, or invalid rows never become zeros or penalty-only rows.
- Every campaign declares its own expansion, screening, refinement, and review caps before execution. Extending a cap requires a new manifest decision.
- Stop early when the decision is stable or a model limitation is repeated.
- Publish sampled points, raw units, provenance, uncertainty, failures, and gaps. Do not interpolate a boundary unless validation supports it.

Every result states its highest claim level: implementation verified, measurement verified, numerically qualified, mechanism supported, 2D/3D transfer supported, physically calibrated, or experimentally validated. Evidence at one level does not imply the next.

The numerical program is complete only when named discovery and confirmation profiles have a stated scope, cost, measurement deltas, failure cases, fallback, and promotion rule.

## Sources

- [ViennaPS process controls](https://viennatools.github.io/ViennaPS/process/)
- [ViennaPS ray-tracing controls](https://viennatools.github.io/ViennaPS/process/rayTracingParams.html)
- [ViennaPS ray-tracing default](ViennaPS/include/viennaps/process/psProcessParams.hpp)
- [ViennaPS bundled ray-count examples](ViennaPS/examples/)
- [ViennaPS advection controls](https://viennatools.github.io/ViennaPS/process/advectionParams.html)
- [NIST guidance on choosing an experimental design](https://www.itl.nist.gov/div898/handbook/pri/section3/pri33.htm)
- [Hyperband early-stopping method](https://www.jmlr.org/papers/v18/16-558.html)
- [Constrained Bayesian optimization](https://proceedings.mlr.press/v130/eriksson21a.html)
- [Local trust-region Bayesian optimization](https://proceedings.neurips.cc/paper/2019/hash/6c990b7aca7bc7058f5e98ea909e924b-Abstract.html)
- [3D level-set Bosch simulation with Monte Carlo ray tracing](https://doi.org/10.1016/j.mee.2009.05.011)
- [TSV Bosch roughness and electrical behavior](https://doi.org/10.1088/0960-1317/18/7/075018)
- [ECS review of bottom-up copper superfilling](https://www.electrochem.org/dl/interface/wtr/wtr04/IF12-04-Pg46.pdf)

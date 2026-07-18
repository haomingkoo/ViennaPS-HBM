# Current research checkpoint

The active method is [`RESEARCH_PLAN_V3.md`](../RESEARCH_PLAN_V3.md). No recipe,
full-traveler result, or process window is authorized.

This numerical work is the current tutorial blocker because the repeated
mask/Bosch study cannot teach which controls move a measurement until a faster
setting is shown to preserve those measurements. Ray count is a simulation-cost
control, not a TSV process knob or the learner-facing result.

## Latest completed simulation block

| Item | Value |
|---|---|
| Stage | 25-case mask-plus-Bosch range pilot |
| Status | Corrected review complete: 20 measured cases and 5 saved geometries with unavailable wall-intersection measurements |
| Numerical setting | Grid 0.01 and 250 rays per point; not qualified |
| Runtime | 573.7 seconds total; 3.7 seconds median; 177.7 seconds maximum |
| Authority | Raw observations and confirmation selection only |
| Review | [`pattern_bosch_range_pilot_review.json`](../pattern_bosch_range_pilot_review.json) |
| Design | [`pattern_bosch_range_pilot_design.json`](../pattern_bosch_range_pilot_design.json) |
| Public source bundle | [`evidence/bosch/range_pilot/source_bundle.json`](../evidence/bosch/range_pilot/source_bundle.json) |

The pilot cannot rank factors, locate a boundary, estimate uncertainty or
interactions, or qualify a process window. The first review mislabeled seven
rows as geometry failures. A seven-case recovery saved the final geometry before
measurement. Two low-movement rows contain valid measurements. The remaining
five geometries are saved, but the declared wall-intersection measurement is
unavailable. Those cases remain unresolved until geometry, sampling region,
grid resolution, and extractor assumptions are checked.

The source bundle preserves the original append-only event rows. Historical
`hard_gate_pass` and `numerical_state` fields in those parent rows are
superseded by the corrected review; they must not be read as process approval
or numerical qualification.

## Earlier completed simulation block

| Item | Value |
|---|---|
| Stage | 250-ray Bosch commissioning comparison |
| Status | 16 of 16 cases completed; saved review found a gate mismatch and a strong-effect direction mismatch |
| Result | No discovery authority; 500 rays remains a provisional bridge, not a qualified profile |
| Runtime | 10.83x paired median speedup versus the tested 2,000-ray anchors |
| Review | [`evidence/numerical/v3_bosch_low_ray_qualification_review.json`](../evidence/numerical/v3_bosch_low_ray_qualification_review.json) |
| Rows | [`evidence/numerical/v3_bosch_r250_qualification_rows.jsonl`](../evidence/numerical/v3_bosch_r250_qualification_rows.jsonl) |
| Public chart | [`numerical_performance_data.json`](../numerical_performance_data.json) |

The mismatch occurs at the high neutral-sticking test. At 250 rays, the maximum
width error is 0.0742, above the 0.060 limit. At 2,000 rays, it is 0.0564 and
passes. The selected-cycle effect of deposition thickness also changes
direction. Matching trajectory classes and the 0.943 factor-ranking score do
not cancel either disagreement.

## Evidence limit

This campaign changed ray count, random streams, and early-stop intervals. It
also predates the executable attempt ledger. The result is useful commissioning
evidence, but it does not isolate ray count or prove numerical convergence.

## Next action

Do not launch the first proposed adaptive panel. The audit found that old
250-ray pilot rows cannot be paired fairly with new 500-ray rows, the nominated
panel has no clear assumed-band pass, and response-specific numerical and
repeat allowances are still null.

First qualify the measurement rules and add a clear pass plus adverse
near-limit cases. Then freeze one new manifest that holds physical inputs,
stream labels, grid, stopping, measurement code, and runtime settings fixed.
Generate fresh 250/500 pairs and independent repeats. Promote only informative
disagreements, extractor challenges, near-limit states, and a center reference
to a same-grid 500/2,000 panel. Approve an exploration setting only for the
measurements and geometries it preserves. Follow ray selection with separate
bounded checks of grid, advection, domain, caps, execution layout, and save
cadence.

## Clean ray ladder checkpoint

The paired ladder tests 250, 375, 500, 750, 1,000, and 2,000 rays on the same
seven cases. Physical inputs, random streams, and stopping rules are frozen.
The 250, 375, and 500-ray arms each have seven complete rows. The 750-ray arm
has two complete rows. No ray count is approved.

The exhaustive ladder was stopped on 18 July 2026 before launching 1,000- and
2,000-ray arms. Two concurrent 750-ray cases had run for about 57 minutes
without completing. Finished rows and resumable manifests were retained. This
is a planned cost stop, not a failed simulation or a numerical conclusion.

Short schema and browser checks also ran on the host while this ladder was
active. One 750-ray case overlapped a slower browser regression and took about
29 minutes. The measurements remain paired, but the wall-time data was not
collected on an otherwise idle machine. Use the timings for broad cost
comparison. Recheck close finalists on an isolated host before claiming a
precise speed ratio.

The completed low-ray rows are historical cost and disagreement evidence. They
may inform case selection but cannot be paired with new rows. The replacement
adaptive panel uses a new frozen manifest and fresh ray arms. A lower-ray
setting is promoted only if it preserves the required measurements and
boundary decisions on the held-out panel.

Validate the committed evidence from a clean clone:

```bash
python build_numerical_evidence_bundle.py --check
python build_numerical_performance_data.py
python scripts/validate_evidence.py numerical_performance_data.json \
  schemas/numerical-performance.schema.json
```

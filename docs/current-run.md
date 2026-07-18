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
| Stage | Matched current-grid ray ladder |
| Status | Complete: operational exploration profile selected |
| Scope | Three etched-shape panels × five ray counts × three streams; 45 runs |
| Ray counts | 250, 500, 750, 1,000, and 2,000 rays per point |
| Runtime | Median across nine runs: 33.1, 54.1, 91.2, 121.6, and 206.5 seconds |
| Result | Successive depth and full-wall movement was not monotonic with ray count |
| Review | [`evidence/numerical/bosch_ray_current_grid_ladder_review.json`](../evidence/numerical/bosch_ray_current_grid_ladder_review.json) |
| Manifest | [`evidence/numerical/bosch_ray_current_grid_ladder_manifest.json`](../evidence/numerical/bosch_ray_current_grid_ladder_manifest.json) |

For this scoped 2D study, use 500 rays for broad exploration and 1,000 rays for
sensitivity checks. Investigate deep unstable profiles with a separate grid or
model study. This is a compute-budget decision, not proof that 500 rays is
accurate or that 2,000 rays is truth.

The median full-wall change from 1,000 to 2,000 rays was larger than the change
from 750 to 1,000 rays. More rays therefore did not produce a simple monotonic
convergence pattern on these shapes. Promoted effects and boundaries still need
higher-setting and held-out checks.

## Earlier completed Phase B

The earlier 13-pair 500-versus-2,000 panel found four changes in assumed
tutorial-band classifications. Those bands are not fabrication limits. The
panel remains useful disagreement evidence and is superseded as the current
cost comparison by the five-level ladder above.

## Earlier completed Phase A

| Item | Value |
|---|---|
| Stage | Fresh 250-versus-500-ray Bosch triage |
| Status | Complete review: 250 rays does not advance |
| Scope | Eight profile categories at grid 0.005; 32 runs |
| Result | 20 measured runs; 12 symmetric minimum-depth guard stops |
| Runtime | On completed pairs, 500 rays took 1.87 times the 250-ray wall time at the median |
| Review | [`evidence/numerical/bosch_ray_phase_a_review.json`](../evidence/numerical/bosch_ray_phase_a_review.json) |
| Manifest | [`evidence/numerical/bosch_ray_phase_a_manifest.json`](../evidence/numerical/bosch_ray_phase_a_manifest.json) |

The reference and center pairs kept the same measurement availability and
assumed-band decisions. The narrow profile changed the assumed bow-band
decision in all three paired streams. The availability-challenge pair changed
the assumed depth-band decision. Those are study comparisons, not fabrication
pass/fail changes, but they are enough to stop 250 rays from advancing.

Both low-movement recipes triggered the configured minimum-etch-depth guard at
250 and 500 rays in all three streams. They provide repeatable guard evidence,
not profile measurements. The review keeps these states separate from the 20
measured runs.

Phase A could not qualify 500 rays. Phase B above completed that comparison and
found that 500 rays also changes required tutorial classifications.

## Earlier completed range pilot

| Item | Value |
|---|---|
| Stage | 25-case mask-plus-Bosch range pilot |
| Status | Corrected review complete: legacy etch values suspended; five incomplete profiles classified |
| Numerical setting | Grid 0.01 and 250 rays per point; not qualified |
| Runtime | 573.7 seconds total; 3.7 seconds median; 177.7 seconds maximum |
| Authority | Raw observations and confirmation selection only |
| Review | [`pattern_bosch_range_pilot_review.json`](../pattern_bosch_range_pilot_review.json) |
| Design | [`pattern_bosch_range_pilot_design.json`](../pattern_bosch_range_pilot_design.json) |
| Public source bundle | [`evidence/bosch/range_pilot/source_bundle.json`](../evidence/bosch/range_pilot/source_bundle.json) |

The pilot cannot rank factors, locate a boundary, estimate uncertainty or
interactions, or qualify a process window. The first review mislabeled seven
rows as geometry failures. A seven-case recovery saved the final geometry before
measurement. The follow-up audit found that the legacy etch extractor mirrored
the positive wall even though the pilot used a full-width via. Its etch values
are therefore suspended. Of the five incomplete rows, two contain both walls
outside the old search window, two provide one wall at the requested heights,
and one does not intersect the declared wafer surface. Physical causes and
numerical convergence remain unresolved.

The active full-width extractor now measures left-to-right width, records center
shift, refuses to mirror a missing wall, and returns explicit availability
states. The five-profile review and archived native checkpoints are in
[`evidence/bosch/pattern_bosch_unavailable_profile_review.json`](../evidence/bosch/pattern_bosch_unavailable_profile_review.json).

The source bundle preserves the original append-only event rows. Historical
`hard_gate_pass` and `numerical_state` fields in those parent rows are
superseded by the corrected review; they must not be read as process approval
or numerical qualification.

## Earlier completed simulation block

| Item | Value |
|---|---|
| Stage | 250-ray Bosch commissioning comparison |
| Status | 16 of 16 cases completed; saved review found a gate mismatch and a strong-effect direction mismatch |
| Result | At this checkpoint, 500 rays remained provisional. Phase B above later rejected it for the tested categorical panel. |
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

Freeze a small intermediate-ray bridge using the four Phase B disagreement
pairs plus at least one agreement anchor. Compare categorical outcomes and raw
measurement differences against compatible 2,000-ray rows. If no intermediate
setting survives, use 2,000 rays for scoped confirmation and redesign the broad
screen rather than calling a cheaper setting accurate. Grid, advection, domain,
caps, execution layout, and save cadence remain separate checks.

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

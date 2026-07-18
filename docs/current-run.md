# Current research checkpoint

The active method is [`RESEARCH_PLAN_V3.md`](../RESEARCH_PLAN_V3.md). No recipe,
full-traveler result, or process window is authorized.

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

Freeze a varied panel of clear passes, clear failures, difficult shapes and
cases near each limit. Keep the inputs, random streams and stopping rule fixed.
Change only the ray count. Compare every measurement and pass/fail result, then
check whether a failure boundary moves. Approve 500 rays for broad screening
only if those paired checks agree. Confirm boundaries and finalists at 2,000
rays.

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

Replace the exhaustive ladder with an adaptive confirmation panel. Use the
completed low-ray rows to find cases with the largest measurement disagreement,
different morphology, and proximity to a modeled boundary. Run only that panel
at 1,000 and 2,000 rays. A lower-ray setting is promoted only if it preserves
the required measurements and boundary decisions on the held-out panel.

Validate the committed evidence from a clean clone:

```bash
python build_numerical_evidence_bundle.py --check
python build_numerical_performance_data.py
python scripts/validate_evidence.py numerical_performance_data.json \
  schemas/numerical-performance.schema.json
```

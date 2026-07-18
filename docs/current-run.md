# Current research checkpoint

The active method is [`RESEARCH_PLAN_V3.md`](../RESEARCH_PLAN_V3.md). No recipe,
full-traveler result, or process window is authorized.

## Latest completed simulation block

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

Validate the committed evidence from a clean clone:

```bash
python build_numerical_evidence_bundle.py --check
python build_numerical_performance_data.py
python scripts/validate_evidence.py numerical_performance_data.json \
  schemas/numerical-performance.schema.json
```

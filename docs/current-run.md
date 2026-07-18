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

The gate mismatch occurs at the high neutral-sticking anchor. The selected-cycle
effect of deposition thickness also changes direction. The trajectory classes
match and the factor-ranking Spearman is 0.943, but those secondary results
cannot cancel either required mismatch.

## Evidence limit

This campaign changed ray count, random streams, and early-stop intervals. It
also predates the executable attempt ledger. The result is useful commissioning
evidence, but it does not isolate ray count or prove numerical convergence.

## Next action

Freeze a new morphology-diverse qualification panel. Hold stopping rules fixed
while changing one numerical control. Include null and near-gate sentinels.
Also include failures, curvature, and interactions. Require absolute metric
agreement and unchanged gates. Bound any failure-boundary movement before a
cheap profile receives screening authority.

Validate the committed evidence from a clean clone:

```bash
python build_numerical_evidence_bundle.py --check
python build_numerical_performance_data.py
python scripts/validate_evidence.py numerical_performance_data.json \
  schemas/numerical-performance.schema.json
```

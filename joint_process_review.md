# Joint Process DOE Review

Status: 317/1024 checkpointed rows across 80 recipes.

Ranking rule: hard-gate invalid metrics and CMP mask consumption, then maximize replicated step-target pass count, then minimize p90 full-process score. This prevents a single lucky replicate, a destructive CMP setting, or a raw proxy score from becoming the story.

## Critical read

- Current best: `dry_best_downstream_best` / `c0105606c514` with mean step pass count 3.5, p90 score 0.5272.
- Failed or unstable specs on current best: liner, fill, cmp.
- Do not claim a full-process success yet; report the best miss and why it misses.
- CMP mask consumption appears in the sampled space; high polish can improve dish while destroying the mask.
- Fill remains a recurring target miss; tip-gap, not floor coverage, is the gating metric.
- Some recipes hit invalid-metric penalties; keep them as bad-region evidence, not deleted outliers.

## Top candidates

| Rank | Recipe | Runs | Step pass mean | Pass range | p90 score | depth | bulge | tip gap | CMP dish | mask consumed |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `dry_best_downstream_best` | 4/4 | 3.5 | [3, 4] | 0.5272 | 1.162 | 0.002451 | 0.1582 | 0.2323 | 0 |
| 2 | `depth_centered_dry_alt` | 4/4 | 3.25 | [3, 4] | 0.7254 | 1.235 | 0.002451 | 0.1403 | 0.4518 | 0 |
| 3 | `joint_broad_0050` | 4/4 | 3 | [3, 3] | 1.832 | 1.336 | 0.01294 | 0.1636 | 1.049 | 0 |
| 4 | `joint_broad_0037` | 4/4 | 3 | [2, 4] | 2.53 | 1.291 | 0.02202 | 0.1375 | 1.587 | 0 |
| 5 | `joint_broad_0061` | 4/4 | 3 | [3, 3] | 2.777 | 1.426 | 0.01226 | 0.1952 | 1.386 | 0 |
| 6 | `joint_broad_0023` | 4/4 | 3 | [3, 3] | 3.568 | 1.172 | 0.07898 | 0.1323 | 0.7529 | 0 |
| 7 | `joint_broad_0042` | 4/4 | 3 | [3, 3] | 5.179 | 1.613 | 0.02208 | 0.1446 | 1.443 | 0 |
| 8 | `joint_broad_0019` | 4/4 | 3 | [3, 3] | 10.72 | 1.943 | 0.09287 | 0.1341 | 1.504 | 0 |

## Step failures

| Failure | Rows |
|---|---:|
| `fill` | 317 |
| `cmp` | 317 |
| `etch` | 284 |
| `liner` | 200 |
| `barrier` | 94 |
| `cmp_mask_consumed` | 80 |
| `invalid_metric_penalty` | 2 |

## Best-candidate step stability

| Step | Pass rate | Mean score |
|---|---:|---:|
| `pattern` | 1 | 0 |
| `etch` | 1 | 0.08171 |
| `liner` | 0.5 | 0.006787 |
| `barrier` | 1 | 0.005433 |
| `fill` | 0 | 0.1582 |
| `cmp` | 0 | 0.2323 |

## Boundary checks

- No single shared factor across the top 4 candidates in the current checkpoint.

## Largest sampled effects

| Factor | Mean-score range |
|---|---:|
| `fill_thick` | 7.076 |
| `neutral_rate` | 6.09 |
| `fill_iso` | 5.965 |
| `barrier_thick` | 5.826 |
| `etch_time` | 5.812 |
| `cmp_mult` | 4.95 |
| `neutral_sticking_probability` | 4.69 |
| `theta_r_min` | 4.347 |

## Next decision

Finish the current checkpointed bootstrap before calling a winner. Partial results are useful for monitoring, but the focus half of the mixed design must be included in the first real generation.

# Joint Process DOE Review

Status: 474 checkpointed rows across 114 recipes.

Ranking rule: hard-gate invalid metrics and CMP mask consumption, then maximize replicated step-target pass count, then minimize p90 full-process score. This prevents a single lucky replicate, a destructive CMP setting, or a raw proxy score from becoming the story.

## Critical read

- Current best: `iter009_fill155_iso0_cmp165` / `662c8477721b` with mean step pass count 4, p90/worst score 0.9107/0.9107.
- Failed or unstable specs on current best: fill, cmp.
- Do not claim a full-process success yet; report the best miss and why it misses.
- CMP mask consumption appears in the sampled space; high polish can improve dish while destroying the mask.
- Fill remains a recurring target miss; tip-gap, not floor coverage, is the gating metric.
- Some recipes hit invalid-metric penalties; keep them as bad-region evidence, not deleted outliers.

## Top candidates

| Rank | Recipe | Runs | Step pass mean | Pass range | p90 score | worst score | depth | bulge | tip gap | CMP dish | mask consumed |
|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `iter009_fill155_iso0_cmp165` | 8/8 | 4 | [4, 4] | 0.9107 | 0.9107 | 1.163 | 0.002739 | 0.163 | 0.603 | 0 |
| 2 | `iter008_filliso0_liner035_cmp165` | 8/8 | 4 | [4, 4] | 0.9418 | 0.9418 | 1.162 | 0.002691 | 0.1518 | 0.655 | 0 |
| 3 | `iter005_liner035_cmp165` | 8/8 | 4 | [4, 4] | 0.9667 | 0.9667 | 1.165 | 0.003211 | 0.1515 | 0.6531 | 0 |
| 4 | `iter004_liner035_cmp16` | 8/8 | 4 | [4, 4] | 1.389 | 1.389 | 1.16 | 0.004239 | 0.147 | 0.6828 | 0 |
| 5 | `iter003_liner035_cmp15` | 8/8 | 4 | [4, 4] | 1.514 | 1.514 | 1.164 | 0.004427 | 0.1487 | 0.8054 | 0 |
| 6 | `dry_best_downstream_best` | 4/4 | 3.5 | [3, 4] | 0.5272 | 0.5272 | 1.162 | 0.002451 | 0.1582 | 0.2323 | 0 |
| 7 | `joint_broad_0094` | 4/4 | 3.5 | [3, 4] | 2.702 | 2.702 | 1.192 | 0.03116 | 0.1475 | 1.422 | 0 |
| 8 | `depth_centered_dry_alt` | 4/4 | 3.25 | [3, 4] | 0.7254 | 0.7254 | 1.235 | 0.002451 | 0.1403 | 0.4518 | 0 |

## Step failures

| Failure | Rows |
|---|---:|
| `fill` | 474 |
| `cmp` | 474 |
| `etch` | 399 |
| `liner` | 263 |
| `barrier` | 135 |
| `cmp_mask_consumed` | 102 |
| `invalid_metric_penalty` | 2 |

## Best-candidate step stability

| Step | Pass rate | Mean score |
|---|---:|---:|
| `pattern` | 1 | 0 |
| `etch` | 1 | 0.09129 |
| `liner` | 1 | 0.002938 |
| `barrier` | 1 | 0.006529 |
| `fill` | 0 | 0.163 |
| `cmp` | 0 | 0.603 |

## Boundary checks

- Sampled ranges were not supplied; no boundary claim is made.

## Largest marginal sampled effects

These are balanced-screen associations, not dominance or causal interaction claims; confirm important effects on shared upstream geometries.

| Factor | Mean-score range |
|---|---:|
| `cmp_mult` | 8.62 |
| `fill_thick` | 8.185 |
| `neutral_rate` | 6.51 |
| `fill_iso` | 5.878 |
| `etch_time` | 5.774 |
| `barrier_thick` | 5.046 |
| `theta_r_min` | 4.628 |
| `num_cycles` | 4.216 |

## Next decision

Finish the current checkpointed bootstrap before calling a winner. Partial results are useful for monitoring, but the focus half of the mixed design must be included in the first real generation.

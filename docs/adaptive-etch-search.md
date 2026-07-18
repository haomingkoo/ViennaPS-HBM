# Adaptive etch search

## Purpose

Find a small repeatable etch region with the least useful simulation work.
The search must keep depth, top/middle/bottom CD, bow, floor shape, validity,
and runtime visible. It must not hide a missed measurement inside one score.

This is black-box optimization. It is not Adam-style training: ViennaPS does
not provide the smooth, trustworthy gradients that Adam requires.

## Two separate decisions

1. **How cheaply can a case be explored?** Compare grid and ray settings on
   the same physical cases and random streams. Freeze the cheapest setting
   that preserves the measurements needed by the study.
2. **Which process-model settings should run next?** Hold the numerical
   profile fixed. Use completed cases to select the next process cases.

Do not optimize process controls and numerical controls together. A coarse
grid must not win merely because it changes the measured geometry.

## Search loop

### 1. Start with a small spread

Use a space-filling or screening design across defensible factor ranges. Add
known good, boundary, and failure shapes. Repeat the center before ranking
settings.

### 2. Keep separate response models

Model these outputs separately:

- depth;
- top, middle, and bottom CD;
- bow and sidewall angle;
- floor peak-to-valley and symmetry, when measurable;
- measurement availability and simulation validity; and
- wall time.

The fixed depth and width values in `program.md` are teaching comparisons.
They are not fabrication tolerances. Until calibrated limits exist, report
distance from the target and the observed repeat spread instead of a PASS.

### 3. Choose three new cases per batch

- one case predicted to improve the measured profile while keeping the other
  responses close to target;
- one case near an uncertain boundary; and
- one diverse case that prevents the search from becoming too local.

Use a local trust region around the repeatable cluster. Expand it only when
confirmed improvement reaches an edge. Shrink it after a full batch produces
no useful improvement or repeatedly invalid geometry.

### 4. Stop for evidence, not exhaustion

Stop the local search when any of these occurs:

- three batches produce no change larger than measurement resolution and
  observed repeat variation;
- the local region has been shrunk twice;
- proposed cases repeatedly fail for the same model limitation; or
- the predeclared run or time budget is reached.

Confirm at most three finalists on unseen random streams and a higher ray
setting. A higher ray count is a sensitivity check, not ground truth.

## Method choice

A local constrained Bayesian search is the first choice after screening. It
uses prior cases and uncertainty, which is useful when each new run is costly.
The first implementation should stay dependency-free until the saved data can
demonstrate that a surrogate predicts held-out cases usefully. If it does, use
a maintained ask/tell optimizer rather than writing a new Bayesian package.

The current saved data are not ready for that step. Only one focused cell has
three repeats, and floor shape is unavailable in one of the 12 focused runs.
The next batch should add repeated, floor-measurable cases around the local
region before an optimizer is allowed to rank new settings.

Other methods remain conditional:

- **TPE** is useful when the final space mixes categorical, integer, and
  conditional factors.
- **CMA-ES or a genetic algorithm** can handle noisy continuous searches, but
  population-based generations may spend too many simulations here.
- **MADS** is a fallback when the local response is too discontinuous for a
  useful surrogate.
- **Grid search** remains useful only for very small, deliberate maps and
  numerical comparisons.

## Sources

- [Hyperband: adaptive resource allocation](https://www.jmlr.org/papers/v18/16-558.html)
- [TuRBO: local Bayesian optimization](https://papers.nips.cc/paper_files/paper/2019/hash/6c990b7aca7bc7058f5e98ea909e924b-Abstract.html)
- [Constrained Bayesian optimization with noisy experiments](https://ai.meta.com/research/publications/constrained-bayesian-optimization-with-noisy-experiments/)
- [NOMAD: constrained derivative-free optimization](https://nomad-4-user-guide.readthedocs.io/en/latest/Introduction.html)
- [Adam: gradient-based optimization](https://arxiv.org/abs/1412.6980)

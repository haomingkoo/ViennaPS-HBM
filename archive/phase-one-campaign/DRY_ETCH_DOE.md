# Dry Etch DOE Protocol

Status: historical reproduction protocol. Do not launch the 96x3, 512x6, or
local autoresearch commands below as active research. The active method is
`RESEARCH_PLAN_V3.md`: broad low/nominal/high screening, effect/correlation
ranking, downstream propagation, and only then focused DOE on sensitive knobs.

This is the standing protocol for the Bosch dry-etch study. The etch step
is not "done" because one raw bulge sweep found a nice-looking profile; it
is done only when recipes are scored against the target structure:

| Metric | Target |
|---|---|
| Depth | `1.25 +/- 0.10` |
| Width | `0.30 +/- 0.06` |
| Wall bulge | `<= 0.03` |
| Shape support metrics | top/mid/bottom width, taper delta, sidewall fit/scallop when enough sidewall points exist |

The canonical target implementation is `tsv_process.TARGET_SPECS["etch"]`.
Do not rank a shallow via as a winner because its raw bulge is smaller.

## Physical Model Assumptions

The script stays close to how Bosch DRIE is described in process sources:
the process alternates silicon etching and sidewall passivation, so cycle
count, etch-step aggressiveness, passivation thickness/sticking, and
ion/radical balance all belong in the DOE. Sources used to sanity-check
the factor set:

- Oxford Instruments DRIE overview: Bosch uses fluorine etch chemistry
  plus fluorocarbon passivation, repeated over many cycles to form deep
  vertical profiles.
- Schaper et al., J. Vac. Sci. Technol. B, "Effect of process parameters
  on via formation in Si using deep reactive ion etching": via profile and
  morphology depend on gas flows, pressure control, coil/platen powers,
  chamber condition, and target sidewall angle.
- Owen et al., "High Aspect Ratio Deep Silicon Etching": switching time,
  passivation parameters, pressure, power, and ARDE affect undercut,
  scalloping, and achievable aspect ratio.
- Samco Bosch equipment note: bottom passivation removal and ion/radical
  balance can shift profiles between tapered and reverse-tapered shapes.

The ViennaPS model exposes these as simulation knobs, not exact fab recipe
controls. The DOE therefore reports model coefficients and simulated
shape metrics, not calibrated fab settings.

## Factors

`dry_etch_doe.py` varies every dry-etch control that affects the simulated
profile:

| Factor | Broad range | Focus range |
|---|---:|---:|
| `mask_taper` | `0, 2, 4` | `0, 2` |
| `num_cycles` | `10, 11, 12, 13, 14, 15, 16, 18` | `12, 13, 14, 15, 16` |
| `etch_time` | `0.35, 0.40, 0.45, 0.50, 0.55, 0.60` | `0.40, 0.45, 0.50, 0.55` |
| `neutral_rate` | `-0.08, -0.10, -0.12, -0.15, -0.18, -0.20` | `-0.08, -0.10, -0.12, -0.15` |
| `neutral_sticking_probability` | `0.03, 0.05, 0.08, 0.12` | `0.03, 0.05, 0.08` |
| `initial_etch_time` | `0.20, 0.30, 0.45` | `0.20, 0.30, 0.45` |
| `deposition_thickness` | `0.005, 0.010, 0.015, 0.020` | `0.005, 0.010, 0.015` |
| `deposition_sticking_probability` | `0.005, 0.010, 0.020` | `0.005, 0.010, 0.020` |
| `ion_source_exponent` | `100, 200, 400, 600` | `200, 400, 600` |
| `theta_r_min` | `45, 60, 75` | `45, 60, 75` |

The default design is mixed: about 60% broad balanced coverage and 40%
focused coverage near plausible target-depth recipes.

## Execution

Pilot smoke test:

```sh
.venv/bin/python -u dry_etch_doe.py \
  --recipes 2 --replicates 1 --workers 2 \
  --design mixed \
  --out /tmp/dry_etch_doe_check.jsonl \
  --summary /tmp/dry_etch_doe_check_summary.json
```

Current serious run:

```sh
.venv/bin/python -u dry_etch_doe.py \
  --recipes 96 --replicates 3 --workers 10 \
  --design mixed --seed 11
```

Larger follow-up if the first mixed run leaves the winner at a boundary:

```sh
.venv/bin/python -u dry_etch_doe.py \
  --recipes 512 --replicates 6 --workers 10 \
  --design mixed --seed 29
```

The output is checkpointed by `recipe_hash + replicate`, not just row
number, so the script can resume safely even when the design changes.

## Autoresearch Loop

Use `autoresearch_dry_etch.py` for Karpathy-style iteration: previous
summary in, next experiment plan out, then the controller launches the
next DOE and appends the input/plan/output to a research log.

After the current serious run finishes and `dry_etch_doe_summary.json`
has been regenerated, run:

```sh
.venv/bin/python -u autoresearch_dry_etch.py \
  --bootstrap-summary dry_etch_doe_summary.json \
  --generations 1 \
  --recipes 96 \
  --replicates 4 \
  --workers 10 \
  --top-n 8
```

The controller writes:

- `autoresearch_dry_etch/gen_###_plan.json`
- `autoresearch_dry_etch/gen_###_space.json`
- `autoresearch_dry_etch/gen_###_anchors.json`
- `autoresearch_dry_etch/gen_###_results.jsonl`
- `autoresearch_dry_etch/gen_###_summary.json`
- `autoresearch_dry_etch/research_log.md`

Planning rules:

- carry forward the top target-scored recipes as anchors so they are
  replicated instead of rediscovered by chance
- if winners sit at a tested boundary, expand that factor one step into
  the physically plausible expansion space
- if winners are interior, narrow that factor around the winning values
- keep enough values per factor to still detect curvature and interactions

## Current Autoresearch Result

Completed runs:

- Generation 0: `96 recipes x 3 replicates`, mixed broad/focused design.
- Generation 1: `96 recipes x 4 replicates`, top 8 from generation 0
  carried as anchors.
- Generation 2: `64 recipes x 4 replicates`, top 4 from generation 1
  carried as anchors, focused boundary/local search.

Current best recipe from `autoresearch_dry_etch/gen_002_summary.json`:

```json
{
  "mask_taper": 2.0,
  "num_cycles": 12,
  "etch_time": 0.6,
  "neutral_rate": -0.08,
  "neutral_sticking_probability": 0.2,
  "initial_etch_time": 0.3,
  "deposition_thickness": 0.005,
  "deposition_sticking_probability": 0.003,
  "ion_source_exponent": 600,
  "theta_r_min": 45.0
}
```

Summary metrics over 4 replicates:

- target pass rate: `1.0`
- p90 dry-etch score: `1.172`
- mean dry-etch score: `1.151`
- mean depth: `1.163`
- mean bulge: `0.00268`
- mean width-profile error: `0.0274`
- invalid metric runs: `0`

The runner did not emit `boundary_notes` for generation 2, but the best
recipe uses the high tested `neutral_sticking_probability=0.2` and low
`deposition_sticking_probability=0.003`. Treat this as a strong current
candidate, not a final fab optimum. The next useful generation should be
small and local: replicate the top two recipes more heavily and perturb
neutral sticking, deposition sticking, `etch_time`, and cycle count around
the winning point.

## Ranking

Rows carry:

- final `target_pass` and `target_score`
- final `dry_etch_score`
- per-cycle `cycle_trace`
- depth, bulge, width error, top/mid/bottom width, taper delta
- optional sidewall slope and scallop RMS when the extracted sidewall has
  enough body points to fit

Ranking rule:

1. Target pass rate first.
2. Then p90 dry-etch score, because this is a Monte Carlo ray-traced
   process and a single lucky replicate is not a winner.
3. Then inspect `boundary_notes`. If the top recipes all sit on a tested
   boundary, expand that factor and rerun before calling it a sweet spot.

## Report Rule

The explainer/report sliders must cover the best sampled dry-etch region
from `dry_etch_doe_summary.json`. If the best recipe is outside the
current slider range, update the report data and regenerate the HTML. Do
not publish or describe an online report as current until the generated
HTML has been rebuilt and deployed from these local results.

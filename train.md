# train.md -- what's fixed, what's varied

The experimental protocol. When running a new sweep or test, check here
first: don't silently change something this file says should be held
constant, and don't forget to vary something it says should be tested.

## Held constant across all experiments (unless the experiment is
## specifically about this)

- `radius = 0.15` -- via radius. Never varied by the DOE; if you need to
  test a different radius, that's a new experiment, not a parameter sweep.
- `mask_height = 0.3` (from `make_initial_geometry`'s default)
- Grid resolution (`gridDelta`, defaults to domain-computed)
- The measurement metric itself: `bulge = max |x - radius|` over the
  sidewall body region (`y in [0.85*depth, 0.2]`, `x > 0.2*radius`) --
  see prepare.md for exactly why this metric, not scallop RMS or fit
  slope, is the one to trust.

## The etch step's tunable parameters (what the 768-run DOE varied)

| Parameter | Tested range | Effect on bulge (measured) |
|---|---|---|
| `etch_time` | 0.5, 1.0, 1.5, 2.0 | **Dominant** (0.097 effect range) |
| `neutral_sticking_probability` | 0.02-0.3 (8 values) | 2nd (0.086) |
| `deposition_thickness` | 0.01, 0.02, 0.04 | 3rd (0.020) -- **interacts with etch_time**, see below |
| `ion_source_exponent` | 50-1000 (8 values) | Smallest (0.009) |

Known interaction: `deposition_thickness`'s effect flips direction
depending on `etch_time` (thin passivation best at etch_time=0.5, thick
best at etch_time=2.0). Any future sweep involving these two parameters
should treat them as interacting, not independent.

Known non-monotonic effect: cycle granularity at fixed target depth has a
real optimum (12 cycles beats both 6 and 24), not a "finer is always
better" trend.

## Downstream steps' tunable parameters (what sweep_downstream.py varies)

- Liner: `thickness` (>= `MIN_LINER_THICKNESS=0.02`), `sticking`
- Barrier+seed: `thickness` (>= `MIN_BARRIER_THICKNESS=0.012`), `iso_ratio`
- Fill (superconformal): `thickness` (>= `MIN_FILL_THICKNESS=0.15`), `iso_ratio`

All three have a **functional minimum thickness constraint** before
optimizing coverage -- without it, the sweep trivially picks the thinnest
tested option (thin = easier to "reach" the floor, but not functionally
protective). See prepare.md's log for how this was caught.

## Before adding a new parameter to a sweep

1. Add it to this file's table (expected range, what it's expected to do).
2. If it could plausibly interact with an existing parameter, say so here
   before running anything -- don't discover it by surprise afterward.
3. Decide the functional minimum (if it's a thickness/coverage-style
   parameter) before running the sweep, not after seeing a degenerate
   "thinnest wins" result.

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

## Patterning (Step 1) parameters

`ps.MakeHole` exposes `maskTaperAngle` (wired through `make_initial_geometry`'s
`taper` arg) and `holeTaperAngle` (not wired through at all until this was
screened -- prepare.md item 16). `maskTaperAngle` has a real, non-monotonic
effect on etch bulge (up to 0.04, bigger than `deposition_thickness`);
`holeTaperAngle`'s effect is small (~0.005, similar to `ion_source_exponent`).
Not yet depth-matched/confirmed as a genuine improvement -- see prepare.md
item 16 before trusting any specific "best" taper value. `radius` and
`mask_height` are feature-size specs, not recipe knobs -- held fixed per
the "held constant" section above, not part of the tuning-knob search.

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

**Updated winner (prepare.md item 17):** the combined top-4 DOE
(etch_time x neutral_sticking_probability x initial_etch_time x
neutral_rate, `sweep_top4.py`) found `neutral=0.05, initial_etch_time=0.3,
neutral_rate=-0.1` beats the old `neutral=0.2, neutral_rate=-0.2` by
~37%, depth-matched and replicated (14 cycles now needed for comparable
depth, not 12 -- the new recipe etches slightly less per cycle). This is
now the production recipe everywhere downstream depends on it. Also:
`neutral_rate`'s DOE effect range (0.110) is nearly as large as
`etch_time`'s (0.112) -- it belongs with `etch_time` as a top-tier knob,
not a minor one.

## Downstream steps' tunable parameters (what sweep_downstream.py varies)

- Liner: `thickness` (>= `MIN_LINER_THICKNESS=0.02`), `sticking`
- Barrier+seed: `thickness` (>= `MIN_BARRIER_THICKNESS=0.012`), `iso_ratio`
- Fill (superconformal): `thickness` (>= `MIN_FILL_THICKNESS=0.15`), `iso_ratio`

All three have a **functional minimum thickness constraint** before
optimizing coverage -- without it, the sweep trivially picks the thinnest
tested option (thin = easier to "reach" the floor, but not functionally
protective). See prepare.md's log for how this was caught.

**Closed: liner/barrier/fill have no untested hidden knobs left.** Unlike
etch (which had 7 real parameters nobody had varied), the underlying
ViennaPS process models for these three steps expose only a small,
fully-characterized set: `SingleParticleProcess` (liner) = rate, sticking
(both swept), `sourceExponent` (screened, no effect -- prepare.md item
11), `maskMaterial` (structural, not a recipe knob). `DirectionalProcess`
(barrier+seed, fill) = direction vector (screened as an angle, no
validated effect after correcting a test-methodology bug -- prepare.md
item 12), directionalVelocity/isotropicVelocity = thickness/iso_ratio
(both swept), `calculateVisibility` (screened, no effect), `maskMaterial`
(structural). Confirmed via direct API introspection
(`help(ps.DirectionalProcess.__init__)` etc.), not just by not having
tried something yet.

## CMP's tunable parameters

`cmp_planarize` uses `ps.IsotropicProcess(rate=-1.0)` for a duration
computed from the overburden. `rate`'s magnitude is not an outcome
parameter (only changes numerical step convention for a fixed target);
`target_y` is the one real knob. See prepare.md item 13 for the
target_y sweep and the real (not modeling-gap) trade-off it found between
clearing the field quickly (visible residual dishing) and polishing deep
enough to flatten it (unrealistic Cu/via-height loss). Material-selective
removal (`materialRates`) is implemented but not verified to add a
qualitatively distinct knob beyond rescaling the target_y effect --
treat as open, not closed (prepare.md's "open" list).

## Standing methodology: screen, then refine

Every step's full parameter space should be screened (2 levels, one-
factor-at-a-time from the current best point) *before* committing to a
deep combined sweep on a subset. Don't assume the parameters already
being swept are the only ones that matter -- check every real parameter
the underlying function exposes (including ones with defaults you've
never overridden). This caught 2 real knobs (`initial_etch_time`,
`neutral_rate`) that rank above 2 of the original DOE's 4 parameters.
Verify screening deltas against a metric that's actually valid at the
tested parameter values -- a metric tuned for the baseline can silently
misfire at a different point in the space (see prepare.md's log, item 10).

## Before adding a new parameter to a sweep

1. Add it to this file's table (expected range, what it's expected to do).
2. If it could plausibly interact with an existing parameter, say so here
   before running anything -- don't discover it by surprise afterward.
3. Decide the functional minimum (if it's a thickness/coverage-style
   parameter) before running the sweep, not after seeing a degenerate
   "thinnest wins" result.

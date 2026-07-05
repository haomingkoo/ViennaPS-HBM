# prepare.md -- evaluation methodology + running log

## The metric (don't change this without a documented reason)

**Wall bulge** = `max(|x - radius|)` over sidewall points where
`depth*0.85 < y < 0.2` and `x > 0.2*radius`. This measures deviation from
a perfectly straight vertical wall at the nominal radius -- it catches
symmetric bowing that a linear best-fit slope (an earlier, abandoned
metric) averages away and hides.

**Why not scallop RMS or fit slope:** both were tried first and both can
report "good" on a visibly bowed via, because they measure residual from
a *fitted* line (which bows with the profile) rather than deviation from
the *ideal* straight wall. Bulge doesn't have this problem. If you're
tempted to add a new metric, check it against a known-bowed profile
first -- does it correctly flag the bowing, or does it get fooled the
same way?

**Depth comparisons must be depth-matched.** Comparing bulge (or any
shape metric) across two runs at different depths is not a fair
comparison -- shallower vias trivially show less bulge regardless of
recipe quality (less distance for ARDE to accumulate). Any "before/after"
or "failure/fix" comparison must use comparable depths, or say explicitly
that it doesn't and why that's still meaningful.

**Coverage-style metrics (liner/barrier/fill sweeps) need a functional
minimum thickness gate**, or the optimizer trivially picks the thinnest
option tested. See train.md for the specific minimums per layer.

## Running log -- what was tried, what worked, what didn't

1. **2-parameter sweep (ion x neutral), 9 then 25 points.** Found
   neutral_sticking as the apparent dominant knob. Superseded by the
   4-parameter DOE, which found etch_time dominates instead -- the
   smaller sweep's answer was an artifact of not testing etch_time at all.
2. **Fit-slope metric.** Missed symmetric bowing (a via can have zero net
   slope, top and bottom lined up, while bulging out in the middle).
   Replaced with the bulge metric above.
3. **Raw DOE winner (bulge=0.0145 at 3 cycles).** Looked like a ~3.7x
   improvement. Confound: short etch_time at fixed cycle count means a
   shallower via. Corrected via depth-matched replicated verification
   (3 runs each, old vs. new recipe, both at comparable depth ~1.2-1.3):
   real improvement is ~2.8x (mean 0.051 -> 0.018, non-overlapping ranges).
4. **Finer cycling test (15 cycles x short etch_time vs. 5 x long).**
   Hypothesis "finer control = straighter" was wrong -- finer cycling was
   *worse* (0.104 vs 0.053). Later the 768-run DOE confirmed: cycle
   granularity has a real optimum (12), not a monotonic trend.
5. **Downstream sweep, first pass.** Liner/barrier/fill sweeps initially
   picked the thinnest tested option every time (trivial "reaches
   further because there's less to reach" artifact). Fixed by adding a
   functional minimum thickness constraint per layer.
6. **Superconformal Cu fill "100% coverage" claim.** The sweep's coverage
   metric (overall floor position) didn't match the notebook's stricter
   centerline-seal check. Re-measured: gap reduced from 1.163
   (subconformal) to 0.109 (superconformal) -- real, large improvement,
   but not literally zero. Root cause investigated: increasing fill
   thickness past ~0.18 makes the gap *worse*, not better (0.19 -> 0.96
   at thickness=1.2) -- ruled out "just needs more material." Real
   explanation: real superfill closes sharp corners via curvature-
   dependent accelerator chemistry (CEAC -- Curvature Enhanced
   Accelerator Coverage), which `DirectionalProcess`'s constant direction
   vector structurally cannot represent. Documented as a known modeling
   ceiling, not an unresolved bug.
7. **Failure-vs-fix visual, etch step.** Caught depth-mismatch: comparing
   etch_time=2.0 vs. 0.5 at the *same* cycle count made the "failure"
   case look worse partly because it was just much deeper, not fairly
   compared on straightness. Fixed with `BAD_CYCLES` chosen to
   depth-match `PRODUCTION_CYCLES`.
8. **all_material_profiles() duplicate-material-name bug.** Barrier/seed
   and Cu fill are both tagged `Material.Cu` (two separate level sets).
   A name-keyed dict silently drops one. Fixed by iterating the ordered
   list positionally instead of by name lookup.
9. **HBM process-flow understanding, corrected mid-project (see
   README).** TSVs are formed at the wafer level (batch), not per-die
   individually; the via stays blind until backside reveal; the base
   logic die (not the top die) is the one without a through-via.

## Open, not yet attempted

- Curvature-dependent (CEAC-like) Cu fill model -- would need a custom
  rate function with access to local surface curvature, not just
  `DirectionalProcess`'s constant vector. Real research task, not a
  quick parameter fix.
- True inter-via loading effects (tested once with periodic vs. isolated
  domains at a single pitch/parameter set -- no effect observed; either
  the pitch tested wasn't tight enough or this flux model doesn't capture
  chamber-scale reactant depletion, only local ray-traced visibility).

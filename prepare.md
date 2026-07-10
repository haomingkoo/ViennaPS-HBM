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

**Every process step needs a target spec before DOE ranking.** A sweep is
not done when it can sort a raw metric; it is done when each row is scored
against the step target in `program.md` / `tsv_process.TARGET_SPECS`.
Rank target pass first, then distance-to-target. For fill, floor coverage
is supporting data only because it saturates; the target metric is
centerline tip-gap. For etch, depth and width are part of the target
structure; a shallower or narrower/wider via is not a winner just because
its raw bulge is low.

**A slider/report range must cover the best sampled target region.** If
the best target score sits on a grid boundary, expand the DOE beyond that
edge and regenerate the report data before calling it a sweet spot. The
report must show real sampled points only; no interpolated or invented
"best" values.

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

10. **Screening design across all 11 real etch parameters** (not just the
    4 the original DOE covered -- `deposition_sticking_probability`,
    `neutral_rate`, `ion_rate`, `initial_etch_time`, `radius`,
    `mask_height`, `theta_r_min` were all real function parameters,
    hardcoded/defaulted and never varied). First pass falsely showed
    `mask_height=0.2` causing bulge=0.35 (26x baseline) -- a metric bug,
    not a real effect: the bulge y-window was hardcoded to `y < 0.2`,
    tuned for the baseline `mask_height=0.3`; at `mask_height=0.2` the
    mask top sits at y=0.2 too, so the metric picked up mask-edge noise.
    Fixed by scaling the y-window with `mask_height`. Corrected result:
    `initial_etch_time` (0.031) and `neutral_rate` (0.028) both rank
    above `deposition_thickness` (0.020) and `ion_source_exponent`
    (0.009) -- real, previously-missed knobs, now the subject of
    `sweep_top4.py`'s combined DOE.
11. **Screened liner/barrier/fill for other hidden parameters.**
    `DirectionalProcess`'s `calculateVisibility` flag: no effect (True
    vs. False identical) -- makes sense, nothing else in a single-via
    domain to shadow. `SingleParticleProcess`'s `sourceExponent` on the
    liner: no effect across 1.0/100.0/1000.0. Both ruled out cleanly,
    not silently ignored -- the liner/barrier/fill sweeps' existing
    thickness+sticking/iso_ratio parameters remain the ones that matter.

12. **Direction-angle knob for Cu fill/barrier -- claim made, then retracted.**
    Tried tilting `DirectionalProcess`'s direction vector (0-30 deg off
    vertical) to see if it reduces the residual centerline tip-gap (the
    CEAC-ceiling gap documented in item 6). Two separate angle sweeps gave
    contradictory pictures (first: 10 deg looked ~25% better; a finer
    re-sweep around it showed the opposite, monotonically worsening
    trend) -- initially misread as "doesn't replicate, must be noise."
    That was wrong on two counts. Root cause, confirmed by direct test:
    (a) `DirectionalProcess` (the fill model) is itself fully
    deterministic -- 4 replicates at a fixed angle on a fixed input
    geometry return bit-identical results, zero variance; (b)
    `bosch_etch`'s ray-traced `MultiParticleProcess` genuinely does have
    run-to-run Monte Carlo noise -- 4 runs of *identical* etch+liner+seed
    parameters gave via-floor depths of -1.166, -1.17, -1.17, -1.18 (~1%
    spread, differing point counts too). Each of the two angle sweeps
    silently rebuilt its own base via from scratch, so they were each
    internally consistent (no fill-side noise) but were comparing angles
    against *different, independently-noisy* base geometries -- not a
    valid controlled comparison. Redone properly (one `geo_seed` built
    once, deep-copied per angle, swept 0-30 deg): the relationship is
    non-monotonic and 0 deg (straight down, no tilt) is among the best
    values tested, not the worst. **Retracting the earlier "10 deg tilt
    gives ~25% improvement" claim -- it was a test-methodology artifact,
    not a real effect.** No validated angle-tilt benefit for Cu fill;
    the CEAC-ceiling finding in item 6 stands as the operative
    conclusion for the fill gap, not this. Standing lesson: any
    "controlled" comparison built on top of an etched via must reuse one
    `geo_seed` object (build once, deep-copy per test arm) -- never
    regenerate the via per comparison arm, since etch has real MC noise
    that will contaminate the comparison.

13. **CMP screening: `rate` is not an outcome parameter; `target_y` is the
    only real knob, and it has a genuine, non-obvious sweet-spot tension.**
    `cmp_planarize` uses `ps.IsotropicProcess(rate=-1.0)` for a fixed
    duration computed from the overburden -- `rate`'s magnitude only
    changes the numerical step convention, not the final planarized
    state, so it isn't a real tuning knob. Tried adding Cu:field
    material-selective removal (`materialRates={Cu: -k}, defaultRate=-1`)
    to model dishing; before that, discovered the pre-CMP via-center
    surface already sits well below the surrounding mound (a real
    pre-existing dip inherited from the fill step, not a CMP artifact).
    Swept `target_y` alone (holding non-selective rate) and measured the
    residual gap between via-center and the nearby field mound after
    planarizing: barely clearing the pre-CMP mound leaves a *large* gap
    (0.11-1.17, an under-polished-looking profile with residual bumps),
    and continued over-polish shrinks it asymptotically (down to
    ~0.02-0.03) but only by grinding far past the field-clearing point,
    deep into the via's actual Cu volume (confirmed via
    `all_material_profiles` -- the Mask layer is long gone by then).
    Real conclusion: there is a genuine trade-off, not a clean sweet spot
    -- stopping as soon as the field clears (what a real fab would do, to
    avoid wasting Cu/time/via height) leaves visible residual
    non-planarity; eliminating that residual requires an unrealistic
    amount of extra material loss. This is an honest, real finding, not
    a modeling gap to fix. Caught and fixed a related robustness bug
    along the way: `all_material_profiles()` crashed
    (`IndexError: too many indices`) once over-polish fully consumed the
    Mask level set -- `ls.ToSurfaceMesh` returns an empty 1-D array for a
    level set with nothing left to mesh, and the function assumed 2-D
    output unconditionally. Fixed to return an empty point array for
    that material instead of crashing.

14. **Correction to item 13 and to the shipped notebook's CMP section --
    the existing "over-polish causes dishing, exact-target fixes it"
    narrative is factually backwards.** Checked the notebook's actual
    Step 6 cell (`fig_cmp_final.png`) against a robust field-vs-via
    metric (mean y over `x>0.3` vs `x<0.1`, not a narrow fixed window --
    item 13's original window was too narrow to catch this). Result on
    the real production recipe (ETCH/LINER/BARRIER/FILL_SUPERCONFORMAL,
    PRODUCTION_CYCLES=12): at the notebook's "fixed" case (exact nominal
    overburden, 1.0x), dish (field-via) = 1.35 -- *larger*, not smaller,
    than the notebook's "failure mode" case (1.6x over-polish), which
    measures 0.70. The notebook's own printed metric
    (`target_y - post-polish max height`) doesn't catch this because it
    only measures how far the single highest point sits below target,
    not the field-vs-via relative recess that "dishing" actually means.
    Swept the over-polish multiplier further (1x-10x): dish keeps
    shrinking (1.35 -> 0.05) but **the entire Mask level set is fully
    consumed by 2x** -- i.e. reaching acceptable dishing in this model
    requires removing multiple mask-heights' worth of material, far
    beyond any real fab's CMP budget (which stops within a thin
    overburden margin specifically because the barrier layer's different
    removal rate lets the process self-limit). Conclusion: like the
    CEAC/fill-gap ceiling (item 6), this is a genuine structural
    limitation, not a tunable sweet spot -- `ps.IsotropicProcess` here is
    a uniform, non-topography-sensitive removal model, and real CMP's
    actual planarizing mechanism (pad-pressure-dependent removal that
    preferentially clears raised regions) isn't represented at all. Any
    realistic overpolish budget in this model leaves severe dishing.
    **Action: rewrite the notebook's CMP section with this corrected,
    verified story** rather than leave the backwards claim in a shipped
    deliverable.

15. **Comprehensive (denser) combined DOE for liner/barrier/fill/CMP**
    (`sweep_downstream_comprehensive.py`, 64+64+80 points + a 20-point CMP
    curve, vs. the earlier 25/20/30-point `sweep_downstream.py` passes).
    Liner and fill winners landed at grid boundaries (sticking=0.3, the
    max tested; iso_ratio=0.03, the min tested) -- checked the top-5
    rankings before trusting them: liner's coverage is flat (0.995-0.996)
    across sticking 0.22-0.3 (a real plateau, not a cut-off trend);
    barrier's coverage is *bit-identical* (0.9892630...) across iso_ratio
    0.18-0.44 once thickness=0.0143 -- iso_ratio has no effect on barrier
    coverage in that range; fill's coverage saturates at exactly 1.0
    across most of the grid, meaning this coverage metric can't
    distinguish recipes once they "fully reach the floor" (the real
    differentiator remains the stricter centerline-seal check from item
    6, not this coverage metric). Net result: the denser grids landed
    within ~0.03% of the earlier smaller sweeps' winners -- confirms
    those were already near-optimal rather than finding something new.
    The CMP curve (0.9x-10x overpolish) gives a clean, precise version of
    the item 13/14 finding: dish falls from 1.28 to 0.04 monotonically,
    crossing from "mask intact" to "mask fully consumed" at mult~1.6-1.7
    -- confirming the structural-ceiling conclusion with real numbers
    instead of a handful of ad hoc points.

16. **Patterning (Step 1) screening -- a real, previously-untested knob
    source.** `ps.MakeHole` exposes two taper angles neither
    `tsv_process.py` nor any DOE had touched: `maskTaperAngle` (wired
    through as `taper`, but only ever called at the default 0.0) and
    `holeTaperAngle` (not wired through `make_initial_geometry` at all).
    Screened both at +-5/10 deg against the etch bulge metric:
    `holeTaperAngle`'s effect is small (0.003-0.006, similar in size to
    `ion_source_exponent`'s already-ranked 0.009). `maskTaperAngle`'s
    effect is real and non-monotonic, up to 0.04 -- bigger than
    `deposition_thickness`'s 0.020 -- with large tapers in either
    direction hurting and a possible shallow improvement near +4 deg. A
    finer scan (0-8 deg) was too jagged run-to-run to trust as a smooth
    trend (same MC-noise trap as the retracted direction-angle finding,
    item 12) -- replicated 0 deg vs 4 deg (3x each): 4 deg does look
    better (bulge ~0.012 vs ~0.015) but **also etches ~6% deeper**
    (-1.256 vs -1.186) in the same cycle count, an unresolved depth
    confound (see the metric note above -- deeper vias trivially show
    different bulge). Not yet depth-matched and verified -- do not
    report a "taper improves things" claim until that's done. Action:
    include `maskTaperAngle` in the joint multi-step DOE (task requested
    by the user) since its effect size clearly earns a place among the
    "effective knobs," but treat its current apparent optimum as
    unconfirmed.

17. **`sweep_top4.py`'s 800-run combined DOE on etch_time x
    neutral_sticking_probability x initial_etch_time x neutral_rate --
    real winner, but the raw ranking was confounded exactly like item 3.**
    The script hardcoded `NUM_CYCLES=3` for speed; its top-5 winners all
    landed at depth ~-0.31 to -0.34 -- far shallower than the production
    recipe's ~-1.19 at 12 cycles, so the raw bulge ranking wasn't
    trustworthy on its own (same shallow-via-trivially-less-bulge trap).
    Depth-matched the winner (etch_time=0.5, neutral=0.05,
    initial_etch_time=0.3, neutral_rate=-0.1) at 14 cycles (needed for
    comparable depth, since the new recipe etches slightly less per
    cycle) against the current production recipe (neutral=0.2,
    neutral_rate=-0.2) at 12 cycles, 3 replicates each: candidate
    0.0083-0.0127 (mean 0.0112) vs. current production 0.0129-0.0226
    (mean 0.0177) -- a genuine, non-overlapping ~37% improvement.
    **Adopted as the new production etch recipe** (14 cycles).
    Also caught a real methodology lesson: the earlier one-factor-at-a-
    time screening (item 10) ranked `initial_etch_time` (0.031) above
    `neutral_rate` (0.028); the full combined DOE found the opposite --
    `neutral_rate`'s effect range (0.110) is almost as large as
    `etch_time`'s (0.112), while `initial_etch_time`'s (0.007) is the
    smallest of the four. Screening from a single baseline point can
    mis-rank parameters that interact -- it's still useful for a first
    pass (it correctly flagged both as worth including), but the
    combined DOE is what determines the real ranking, not the screen.

18. **Checked whether `etch_time=0.5` (the smallest value ever tested,
    in both the 768-run and 800-run DOEs) is a genuine optimum or an
    unchecked boundary artifact.** Tested below it (0.2, 0.3, 0.4, 0.5),
    depth-matched at each (cycle count adjusted per etch_time to reach
    ~1.15-1.19 depth): bulge gets monotonically *worse* going lower
    (0.2->0.094, 0.3->0.054, 0.4->0.028, 0.5->0.013) -- confirms 0.5 is
    a genuine local optimum in this direction, not a cutoff artifact.

19. **`sweep_joint_5steps.py`'s first version repeated the item-12
    mistake -- caught before trusting the result.** First run appeared to
    show liner thickness meaningfully changing the fill tip-gap (a real
    cross-step interaction the sequential per-step sweeps couldn't have
    found). Before reporting it: checked whether rows sharing the same
    nominal (mask_taper, etch_time) actually shared the same etched
    geometry. They didn't -- 16 rows at (0.0, 0.4) had 15 distinct etch
    depths, because the script called a fresh, independently-noisy
    `bosch_etch` for every single downstream combination instead of
    building the etch once per (mask_taper, etch_time) and branching
    downstream comparisons from that one shared base. Exact repeat of
    the item-12 trap, in a new script. Fixed: `build_etch_base()` now
    runs once per (mask_taper, etch_time) pair (4 total), and
    `run_downstream()` deep-copies that one base for all 16 liner x
    barrier x fill x fill_iso combinations under it. Re-running before
    trusting any cross-step interaction claim.

20. **Joint 5-step DOE (`sweep_joint_5steps.py`, corrected version, item
    19's fix applied): a real, verified cross-stage trade-off, and task
    #18's "global optimum" answered honestly as a Pareto trade-off, not
    a single point.** Effect ranges on fill tip-gap across the 64-run
    grid: `etch_time` (0.034) and `fill_thick` (0.033) dominate, then
    `mask_taper` (0.023) and `fill_iso` (0.017), with `liner_thick`
    (0.006) and `barrier_thick` (0.001) minor/interaction-only (the
    liner_thick "sign" flips depending on the other parameters in 12/32
    groupings -- a small, real interaction, not a clean main effect).
    The important finding: `mask_taper=0` gives the *best* etch bulge
    (0.0076) while `mask_taper=4` gives the *best* fill tip-gap (0.180
    mean vs. 0.203) -- opposite directions on the same knob. Verified
    this is real, not a depth-confound artifact: depth-matched taper=0
    (depth -1.248, bulge 0.0076) against taper=4 at 13 cycles (depth
    -1.239, bulge 0.0119) -- taper=0 is unambiguously better for bulge.
    The tip-gap comparison, if anything, *understates* taper=4's
    advantage -- at fixed 14 cycles taper=4 etches deeper (-1.323 vs
    -1.248), and a deeper via should make fill closure harder, yet
    taper=4 still wins on tip-gap despite that handicap. **Conclusion:
    there is no single "global optimum" for the full chain -- mask taper
    angle is a genuine trade-off between etch wall-straightness and Cu
    fill closure quality, first surfaced by testing all 5 steps' knobs
    jointly instead of each step optimized against only its own local
    metric** (exactly the failure mode a purely sequential/isolated
    per-step optimization can't detect, since etch screening never
    measures downstream fill quality and vice versa).

21. **Retracting item 20's "cross-stage trade-off" claim -- it didn't
    survive replication.** Item 20 (and the notebook section built from
    it) claimed `mask_taper=0` wins on etch bulge while `mask_taper=4`
    wins on fill tip-gap, verified with a single depth-matched run each.
    Rebuilding the notebook and re-executing it produced the *opposite*
    bulge result from a fresh run -- the same real-time contradiction
    that should have been the signal to stop and replicate properly
    before shipping the claim, exactly the mistake already documented in
    item 12. Replicated properly this time: bulge at taper=0, 10 reps:
    [0.0127, 0.0080, 0.0125, 0.0126, 0.0127, 0.0126, 0.0127, 0.0127,
    0.0079, 0.0087] -- a genuine **bimodal** distribution, not simple
    noise around one value (7/10 cluster near 0.0126, 3/10 drop to
    ~0.008). Taper=4, 10 reps: exactly 0.0119 every single time, zero
    measured variance. Fill tip-gap, 6 full-pipeline reps each: taper=0
    range [0.135, 0.205], taper=4 range [0.136, 0.203] -- **the ranges
    almost completely overlap**, meaning the "tip-gap trade-off" side of
    the claim has no statistical basis at this sample size. Corrected
    conclusion: no verified trade-off. What IS real and reproducible:
    `maskTaperAngle=4` gives a remarkably stable, zero-variance bulge
    result, while `maskTaperAngle=0` (a perfectly vertical mask sidewall)
    produces a genuinely bimodal bulge distribution -- a real numerical-
    stability finding (plausibly: a sharp 90-degree corner at the via
    mouth introduces ray-tracing sampling variance that a slight taper
    removes), not a "which taper is better" finding. Rewrote the
    notebook's dedicated section around this corrected, narrower, but
    still genuine and interesting result. Standing lesson (again):
    single-run "verification," even depth-matched, is not verification
    for a ray-traced MC process -- always replicate at n>=5-10 before
    trusting a comparison, and if two separate checks of the "same"
    result disagree, that disagreement IS the finding until resolved,
    not something to average away or ignore.

22. **DOE objective correction -- every step now has an explicit target
    spec, and sweeps must rank by target miss, not raw proxy minima.**
    The previous downstream DOE was still structurally wrong in two ways:
    it optimized liner/barrier/fill by floor coverage even though fill
    coverage saturates at 1.0 while the real void-free target (tip_gap=0)
    remains unmet, and the explainer sliders did not cover the lower
    iso_ratio region where the best fill miss had appeared. Corrective
    rule: pattern, etch, liner, barrier, fill, and CMP each have a target
    spec in `program.md` and `tsv_process.TARGET_SPECS`; DOE rows record
    `target_pass` and `target_score`; report sliders default to the best
    sampled target score and must be expanded when the best point is on a
    tested boundary. This is a methodology fix, not a prose cleanup.
    Reran the report-side target grid: etch slider best sampled target
    score is `etch_time=0.5, neutral_rate=-0.12` (depth -1.332, bulge
    0.0032, width_error 0.0064) -- a candidate only, not adopted without
    replication. Expanded fill through the functional thickness floor and
    physical lower iso bound: best sampled target miss is
    `thickness=0.15, iso_ratio=0.0`, still nonzero tip_gap (~0.151 on the
    report base; ~0.119 on a fresh comprehensive-sweep etched base). That
    base-geometry spread is real etch MC contamination of downstream
    deterministic fill comparisons, so do not quote one fill number as an
    absolute winner without naming the base geometry or aggregating across
    etched bases.

23. **Dry-etch autoresearch loop implemented and run through two
    generations.** The detailed dry-etch study is now a real iterative
    harness, not a one-shot grid: `dry_etch_doe.py` is the inner
    checkpointed runner, and `autoresearch_dry_etch.py` reads a summary,
    carries forward top recipes as anchors, expands or narrows the factor
    space, runs the next generation, and appends
    `autoresearch_dry_etch/research_log.md`. Generation 0 was the clean
    96-recipe x 3-replicate mixed dry-etch DOE. Generation 1 carried the
    top 8 recipes and ran 96 x 4; it found two genuine challengers but
    also many rejected boundary regions. Generation 2 focused on the top
    4 and ran 64 x 4; current best is recipe hash `15252a63cb7c`:
    `mask_taper=2`, `num_cycles=12`, `etch_time=0.6`,
    `neutral_rate=-0.08`, `neutral_sticking_probability=0.2`,
    `initial_etch_time=0.3`, `deposition_thickness=0.005`,
    `deposition_sticking_probability=0.003`, `ion_source_exponent=600`,
    `theta_r_min=45`. It passed target in 4/4 replicates, with p90
    dry-etch score 1.172, mean depth 1.163, mean bulge 0.00268, and mean
    width-profile error 0.0274. No boundary notes were triggered in the
    summary, but several top contenders sit on expanded boundaries
    (`neutral_sticking_probability=0.2`, low deposition sticking), so the
    next honest follow-up is targeted replication / a small local
    perturbation around the top 2 recipes, not another broad screen. The
    existing explainer's two visible dry-etch sliders cover the winning
    `etch_time=0.6` and `neutral_rate=-0.08`, but the report UI does not
    yet expose all important dry-etch knobs from this autoresearch run
    (e.g. neutral sticking, deposition sticking, ion exponent), so do not
    describe the published HTML as fully updated until the report is
    rebuilt around these results.

## Open, not yet attempted

- Curvature-dependent (CEAC-like) Cu fill model -- would need a custom
  rate function with access to local surface curvature, not just
  `DirectionalProcess`'s constant vector. Real research task, not a
  quick parameter fix.
- True inter-via loading effects (tested once with periodic vs. isolated
  domains at a single pitch/parameter set -- no effect observed; either
  the pitch tested wasn't tight enough or this flux model doesn't capture
  chamber-scale reactant depletion, only local ray-traced visibility).
- Cu:field material-selective CMP removal (`IsotropicProcess`'s
  `materialRates`) -- implemented and ran once (item 13), but not swept
  as its own parameter; since it's a uniform per-material multiplier
  (not topography/pressure sensitive), it likely just rescales the
  `target_y` effect rather than adding a qualitatively new knob, but
  that's an assumption, not a verified result.

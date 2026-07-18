# prepare.md -- evaluation methodology + running log

This log preserves historical filenames so earlier decisions remain traceable.
Retired phase-one scripts now live under `archive/phase-one-campaign/` and
`archive/phase-one-sweeps/`. They are not current run instructions; use
`docs/current-run.md` for the active checkpoint.

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

24. **Fresh full-traveler replication confirms that pilot rankings need
    tails, but does not establish a viable traveler.** Campaign generation
    002 ran both canonical full-process anchors for 16 fresh Bosch seeds
    each, preserving one upstream geometry ID per seed. The robustly ranked
    best miss is `dry_best_downstream_best` (mean 3.375/6 step passes,
    p90 score 0.5639); it still fails liner in 10/16 runs, fill in 16/16,
    and CMP in 16/16. `depth_centered_dry_alt` has lower mean tip gap but
    a worse p90 and only 3.25/6 mean passes. The apparent one-factor effect
    table from this two-anchor comparison is confounded because both anchors
    change many knobs; it must not be used for dominance claims. Use at
    least 4 replicates for broad screening and 16 fresh seeds only for
    anchor/finalist stability, with p90 and worst step-pass count reported.

25. **The high-fill-isotropy boundary is a negative controlled result, not an
    optimum.** Campaign generation 006 held the G003_0056 Bosch geometry and
    minimum liner/barrier stack fixed, then ran 60 downstream arms x 4 shared
    geometry replicates with fill isotropic ratio 0.10–0.60, fill thickness
    0.15–0.26, and CMP multiplier 1.5–2.2. All 240 rows failed liner, fill,
    and CMP; 184 consumed the mask. The best mask-surviving arm still had
    tip gap 0.1547 and dish 0.4789, while a top `fill_iso=0.6` arm had a
    worse 0.3095 gap. This rejects “increase isotropic fill” as the local
    remedy. It is evidence for, but not proof of, a CEAC/directional-fill
    structural limitation; retain the distinction in final reporting.

26. **A local process window can be robust yet still infeasible.** G008 ran a
    complete 3^4 downstream map (liner sticking 0.16/0.24/0.30, fill
    thickness 0.18/0.22/0.26, fill iso 0/0.05/0.10, CMP multiplier
    1.2/1.5/1.8) across four shared Bosch geometries. Forty-eight of 81
    settings preserve the mask in every replicate, but all 324 rows fail the
    zero-gap fill and zero-dish CMP targets. Do not describe a mask-survival
    region as a feasible process window; call it a robust-miss window.

27. **Promising post-screen recipes need their own unseen-seed confirmation.**
    G008's four-seed winner `window_059` was compared against the previously
    stable G005_061 reference on 16 new shared upstream seeds (G009). Both
    retained exactly four passing steps, but both still missed fill/CMP. The
    reference won the specified p90 rank (1.109 vs 1.133); the new candidate
    had lower mean gap/dish but a slightly worse p90. Preserve that Pareto
    distinction and never promote either as a manufacturing recipe.

28. **Foundation re-audit opened; no fill/CMP correction accepted yet.**
    The legacy `fill_tip_gap(points, via_floor)` is provably zero when the
    center surface remains at the floor and grows as that surface rises. A
    candidate field-relative metric has the opposite monotonic direction, but
    its physical validity still needs raw level-set and topology checks. The
    old CMP wrapper can remove Cu, oxide, silicon, and mask together; total
    domain erosion was previously collapsed into the mask-consumed flag. The
    128-recipe, 17-factor screen has full rank for a 76-column categorical
    main-effect model, but it was not designed to estimate the full interaction
    surface. Its ranges are ViennaPS model coefficients without fab
    calibration, so they are sensitivity ranges, not demonstrated realistic
    recipe ranges. Issue 06 preregisters the competing hypotheses and tests.

29. **Successful fill and CMP need an intermediate-state morphology gate.**
    The supplied HBM via-middle process reference shows the intended sequence:
    electroplating leaves a filled Cu plug plus positive field overburden, then
    CMP clears that overburden while leaving the plug and surrounding stack.
    The current constant-velocity fill plus one-rate isotropic removal has not
    demonstrated that sequence. A small legacy fill scalar, lower dish, or a
    surviving mask fragment cannot substitute for it. The packaging TCB/NCF
    illustration is downstream context, not part of the six-step traveler.
    Treat the supplied diagram as a qualitative morphology check; retain NIST
    CEAC and contact-mechanics/material-selectivity sources as the mechanism
    evidence.

30. **Etch CD profiles must use the raw silicon boundary.** The existing
    `profile_points()` helper bins by x and keeps only the highest y, which is
    appropriate for the top outer envelope but collapses nearly vertical wall
    segments. On a target-depth etched geometry it returned only 72 envelope
    points and almost no sidewall points at requested depth slices, while the
    raw silicon mesh contained 239 nodes including 124 usable wall nodes.
    Therefore the current single `width_error`/`wall_bulge` read is under
    re-audit. Add raw-boundary top/middle/bottom CD, taper, maximum bow, and
    scallop/roughness checks before interpreting the next etch DOE.

31. **Layer and CMP outputs need physically staged metrics.** Liner and
    barrier/seed require minimum local thickness, bottom/field and lower-wall/
    field conformality, continuity, non-uniformity, and remaining aperture;
    the legacy global-floor displacement is not a local-thickness measure.
    Successful fill must include a void-free plug and positive overburden.
    CMP must then record first field clear as the endpoint and treat any
    additional removal as a separate overpolish interval with declared
    Cu/barrier/dielectric selectivity. Record residual field Cu, Cu dish,
    stop-layer erosion, plug-height loss, and material survival separately.

32. **Phase-one pattern, liner, barrier, and width passes are retracted pending
    metric replacement.** `floor_reach_metric` returns 1.0 for no floor
    deposition and 0.984 for a +0.020 film on a -1.25 floor, so it is not a
    coverage measure. Pattern scoring copied the requested radius, width, and
    height constants instead of measuring generated geometry. Etch
    `width_error` was exactly twice `wall_bulge`, with an exactly doubled
    threshold, so the two claimed gates were redundant. These are metric-form
    failures, not process evidence; retain the old rows but do not use their
    first-four-step pass labels.

33. **Corrected G003 design diagnostics.** The generation plan says 18 wired
    factors, but `SPACE` contains 17. Recalculation from 128 unique raw recipes
    gives categorical main-effect rank 76/76, largest ordinal-index
    correlation 0.2092 (`mask_taper`/`theta_r_min`), largest raw-value Pearson
    correlation 0.2297 (`neutral_sticking_probability`/`fill_iso`), and minimum
    pair-cell coverage 39/42 (92.86%, `neutral_rate`/`fill_thick`). Earlier
    draft values 0.254 and 38/42 were not reproducible and are replaced.

34. **The 1,948-row campaign is a 2D trench study, not 3D TSV proof.**
    `tsv_process.py` fixes ViennaPS to 2D, and the official `MakeHole`
    documentation states that a hole in 2D corresponds to a trench. The
    existing `render_3d.py` is explicitly a coarse five-cycle closing picture,
    not a measurement. Preserve 2D as a possible screening surrogate only
    after matched 2D/3D discrepancy checks; qualify fill topology, critical
    interactions, finalists, and final traveler evidence in 3D.

35. **Thin layers and small shape effects are under-resolved.** With
    `grid_delta=0.01`, the 0.020 liner is two cells, the 0.012 barrier is 1.2
    cells, and a ~0.014 bulge is ~1.4 cells. No continuity, uniformity, or
    small-bulge claim is accepted without grid convergence or an explicitly
    justified rescaling/finer grid.

36. **Directional Cu deposition is not a superfill model.** The current model
    contains no electrochemical current/potential, ion transport, additive
    coverage, history, or curvature feedback. Installed Python APIs can run a
    low-level coordinate-dependent morphology positive control, but custom
    ViennaPS surface-model composition is C++ only. Resolve physical scale
    before choosing CEAC: primary NIST work indicates suppressor-breakdown/
    S-NDR behavior is a competing and likely more relevant mechanism for
    micrometre-scale TSVs. Bind one narrow coverage model only after that
    decision; do not run another `fill_thick`/`fill_iso` DOE first.

37. **CMP has three useful installed controls, none a complete physical
    model.** `Planarize` is an exact height cut for an ideal endpoint/metric
    control. Material-rate `IsotropicProcess` is a selectivity control but has
    no topography or pressure. `CSVFileProcess` can implement a
    position-dependent phenomenological velocity, at the cost of single-thread
    Python callbacks. Challenge these on an analytic filled stack, record first
    field clear and explicit overpolish, and keep all material-loss flags
    nonexclusive.

38. **Mask, material, endpoint, and seed semantics must be corrected before
    CMP.** The current photoresist-like `Mask` is never stripped yet must
    survive CMP; barrier/seed and plated Cu are both tagged Cu; and the CMP
    target is the global liner-envelope maximum rather than a field stop plane.
    Preserve the hard stop-layer survival requirement while explicitly
    separating temporary resist, durable stop/hard mask, TaN/Ta, Cu seed, and
    plated Cu.

39. **Phase-one “unseen seeds” were fresh stochastic executions, not controlled
    seeds.** The CLI seed constructs recipes; replicate IDs do not set a
    ViennaPS RNG. Record explicit simulator RNG state before using reproducible
    unseen-seed language. Also note that G003 had 128 distinct upstream tuples,
    so its shared-upstream flag did not produce cross-recipe geometry reuse.

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
# Foundation re-audit: numerical qualification (2026-07-11)

- An 88-case explicit-seed audit completed with 88 unique valid rows and zero
  errors. The raw-boundary pattern/DRIE metrics and RNG controls passed their
  analytic/reproducibility checks.
- A passing step vector does not imply numerical qualification. At 2,000 rays
  per point, grid delta 0.01 versus 0.005 shifted DRIE depth by a paired mean
  absolute 0.03371, 8.2 times the baseline stochastic SD and 34% of the depth
  tolerance. Bottom CD moved 0.00964. Therefore 0.01 is rejected for scored
  DRIE, liner, barrier, fill, and CMP conclusions.
- Ray-count comparisons from 250 through 4,000 rays per point did not change
  the declared DRIE pass vector and were smaller than the unresolved grid
  bias. Do not spend production-DOE compute on higher ray counts until grid
  convergence is established.
- Resume rule: extend with new 0.0025 cases using the same eight explicit
  seeds and pair them to the saved 0.005 rows. Re-running the 0.005 cases would
  be duplicate simulation, not stronger evidence.
- Before changing from four oversubscribed workers to two seven-thread
  workers, a fixed-seed control reproduced the raw mesh within 8.9e-16 and
  preserved topology and every CTQ. Runtime scheduling is therefore not a
  material confound for the finer-grid extension.
- The first 0.0025 visual pair raised a domain-size concern: seed 52000
  etched to 1.468 in a domain ending at -1.5, leaving 0.032 (about 13 cells).
  Its lower CD also collapsed from 0.304 to 0.225. Preserve this as evidence
  that the numerical setup fails, but test the apparent confound before
  assigning causality.
- The completed 8-pair 0.0025 block is unanimous about failure. Mean absolute
  deltas from 0.005 are 0.15513 depth, 0.06237 bottom CD, 0.02310 maximum CD
  error, and 0.01993 bow. The fine-grid recipe passes depth 0/8, CD 5/8, and
  bow 3/8. Minimum lower-boundary clearance is only 0.01722 (6.9 cells).
- Decision: the old etch pass is withdrawn at qualified-resolution review.
  Diagnose one Bosch cycle and expand the domain before rerunning a full etch;
  do not compensate by retuning the recipe on an unresolved grid.
- The 16-case single-cycle audit explains the instability. At grid 0.00125
  (four cells per 0.005 passivation dose), measured minimum wall polymer is
  0.004741. Relative to grid 0.0025, one-cycle depth moves 0.001086, bottom CD
  0.001130, and bow 0.000534. These are small per cycle but can compound
  nonlinearly over 14 cycles.
- Before freezing 0.00125, run one eight-cell (0.000625) anchor on the same four
  seeds. This is cheaper and more diagnostic than another guessed full-cycle
  run.
- The eight-cell anchor completed 4/4 valid. Against it, grid 0.00125 shifts
  one-cycle depth 0.000678, bottom CD 0.000149 mean absolute, bow 0.000214,
  and minimum polymer thickness 0.0000295 (0.6%). These satisfy the declared
  stochastic-spread and target-margin criteria. Use 0.00125 for the focused
  high-fidelity 2D full-cycle audit, after the vertical-domain check.
- The vertical-domain check falsified the boundary explanation. For seeds
  52000 and 52001 at grid 0.0025, extents 1.5, 2.0, and 2.5 agree across all
  audited etch CTQs within 4.4e-15. The low-clearance image looked suspicious,
  but the controlled intervention shows that it did not cause the profile
  shift. Record this correction explicitly: visual plausibility is a
  hypothesis generator, not causal evidence. Keep extent 2.0 for margin and
  attribute the 0.005-to-0.0025 change to cumulative discretization/passivation
  behavior pending the 0.00125 cycle-history result.
- The first high-fidelity seed completed its expensive simulation but failed
  while `numpy.savez_compressed` lazily imported `zipfile`: the in-flight
  worker still used Homebrew Python 3.13.12 after the installed runtime moved
  to 3.13.14. No CTQs survived that exception, so the failed attempt remains
  visible and seed 52000 has a separate recovery manifest. Long-running workers
  now preload `zipfile` before simulation so an incompatible serialization
  runtime fails at startup rather than after 45 minutes. Review logic groups a
  valid recovery by simulator seed without deleting the failed attempt.
- The isolated recovery completed in 2,120.2 seconds. Across four valid unique
  simulator seeds, cycle 13 is the only checkpoint that passes depth, CD, and
  bow simultaneously for every seed. Its depth range is 1.22306 to 1.31083,
  mean maximum CD error is 0.03585, and mean bow is 0.01768. Cycle 12 passes
  depth for only 3/4 seeds and cycle 14 for 2/4, so cycle 13 is a narrow
  depth-matched checkpoint, not evidence of a wide cycle-count window or a
  global etch-recipe optimum.

## Cu-fill mechanism correction (2026-07-11)

- Do not translate "bottom-up fill" directly into CEAC. NIST's primary TSV
  literature treats suppressor-breakdown/S-NDR as the key mechanism for larger
  Cu TSVs, while CEAC is a distinct accelerator-area-compression mechanism
  associated with smaller damascene features.
- The declared 0.30 x 1.25 model geometry has no physical length calibration.
  Until that mapping exists, concentrations, potentials, transport
  coefficients, and plating times are model coefficients—not fab controls.
- Geometry and metric capability are no longer an open question. A
  deterministic low-level ViennaLS control produces, in sequence, an open
  incomplete fill, void-free closure, and 0.0800 minimum positive overburden.
  A separate top-heavy control produces one sealed pinch-off void (area
  0.2099, height 0.9865). This validates the topology classifier and reproduces
  the failure mode, but the prescribed velocity fields are not electrochemical
  evidence and cannot be tuned as a recipe.
- Any future S-NDR claim must retain suppressor adsorption,
  deposition-driven deactivation, local concentration/transport, and
  active-versus-suppressed deposition rates, then reproduce the characteristic
  current-potential behavior or a published limiting case. The present
  quasi-steady suppressor-access candidate is narrower and may not be reported
  as S-NDR or electrochemistry. A coordinate-dependent bottom-up velocity
  remains only a positive morphology control.
- A controlled ideal-trench range check found a more basic phase-one error:
  `fill_thick` is a deposition distance, but the search stopped at 0.26 for a
  1.25-deep via. The unchanged directional model reaches the field at about
  1.25 and creates positive center overburden by 1.4. The old "unclosed fill
  ceiling" is therefore rejected; it was never tested over a range capable of
  filling the via.
- The high-dose directional control is not a practical recipe. It also grows
  approximately 1.4 on the field, preserving about 1.25 field-to-center
  relief. It proves geometric reach, while simultaneously showing why
  field-suppressing superfill physics and a CMP handoff metric still matter.

## CMP controlled-stack correction (2026-07-11)

- CMP now uses distinct SiO2-stop, TaN-barrier, Cu-seed, and plated-Cu level-set
  identities in controlled tests. Residual field thickness is measured between
  adjacent interfaces; coincident cumulative level-set boundaries are not
  misread as residual metal.
- `Planarize` at the measured stop plane gives the expected ideal endpoint:
  field films clear, dish is zero, and the stop survives. It is a metric
  control, not a pressure/contact model.
- Applying 0.30 of the old one-rate isotropic removal consumes the entire 0.03
  stop and removes more than 0.10 of substrate. This is a destructive
  stop/substrate-loss mode caused by indiscriminate removal, not ordinary CMP
  overpolish and not evidence that the incoming traveler itself was empty.
- The staged candidate passes a deterministic topography control. A 0.05
  raised field-Cu bump clears plated Cu at duration 0.260 under an explicitly
  uncalibrated height-weighted law. A separate equal-metal endpoint stage
  clears seed and barrier at total duration 0.280; dish is 0.00843 with zero
  measured stop/substrate loss. Another 0.005 overpolish increases dish to
  0.01343 while the ideal zero-rate SiO2 stop remains intact. These results
  prove separate first-clear, endpoint, and overpolish states; they do not
  validate pad pressure, compliance, or selectivity ratios.
- API/source review found that the staged arm never applies topography and
  material selectivity at the same time. Its `CSVFileProcess` bulk stage is a
  visibility-gated coordinate law with every non-plated material masked; the
  endpoint stage then switches abruptly to equal-rate isotropic Cu/seed/TaN
  removal with a perfectly protected stop. It is endpoint plumbing, not yet a
  continuous height-and-material-selective CMP abstraction.
- The controlled CMP fixture also needs correction before a response surface:
  `HoleShape.QUARTER` is only a half-trench in 2D, both field samples lie in one
  positive-x bump, and the 0.01 seed/barrier layers have only one cell. Replace
  it with a full cross-section, symmetric and asymmetric topography controls,
  dense two-sided field sampling, and a grid-0.0025 versus 0.00125 gate.
- The smallest candidate model should use one unchanged scalar normal-velocity
  law through bulk clear, endpoint, and overpolish: a material rate multiplied
  by a bounded height/contact weight relative to the measured stop plane. This
  can be called an uncalibrated height-and-material-selective abstraction only;
  downforce, pad compliance/contact pressure, slurry chemistry, speed, and
  endpoint hardware remain unsupported until calibrated or modeled explicitly.
- Do not analyze a shared artifact while a subagent is still editing it. An
  intermediate CMP printout differed from the final code and briefly looked
  like uncontrolled simulation noise. After the agent completed, three fresh
  Python processes reproduced the final checkpoint vector exactly. Wait for
  the completion boundary, then rerun independently before assigning a
  stochastic cause.
- The replacement pre-DOE harness now builds five full-2D analytic
  topographies with distinct Si, 0.030 SiO2 stop, 0.010 TaN, 0.010 named
  CuSeed, and plated Cu, after stripping the temporary pattern mask. Dense
  metrics and synthetic fixtures independently catch residual field plated Cu,
  seed, and TaN; local stop breach; liner/barrier/seed loss; a disconnected
  plug; substrate loss; under-clear; dish; and protrusion. The ideal,
  material-only, height-only, and destructive native controls pass their
  expected directions.
- The exact combined candidate is blocked in the installed Python API:
  `CSVFileProcess` gives a callback the coordinate but not material identity,
  while `IsotropicProcess` accepts material rates but not coordinates. The
  harness therefore raises `ExactControlUnavailable` instead of recreating the
  invalid two-stage approximation. A narrow C++ velocity-field binding is
  required before height and material selectivity can act simultaneously or a
  CMP response surface can be authorized.
- That API blocker is now removed in an isolated pinned build, not in the
  project `.venv`. `HeightMaterialCMP` supplies one continuous no-ray scalar
  velocity from local height and material identity; 2D/3D bindings,
  Python/C++ parity, material gating, tiny-stack advection, deterministic fresh
  processes, invalid parameters, and source/patch/binary hashes pass. Its
  metadata explicitly records that it is an uncalibrated morphology
  abstraction with no pad-pressure physics. This is plumbing qualification,
  not a CMP process result.
- Independent review still blocks every CMP response surface. No actual
  endpoint/overpolish or numerical qualification artifact exists; plated-Cu
  first clear and all-field-metals clear need separate names; two disconnected
  layer fragments can satisfy the current aggregate extent check; malformed or
  inverted geometry lacks a complete invalid gate; and stop/plug functional
  loss limits are not declared. A morphology-only positive fill cannot serve
  as physical incoming-fill evidence. Fix the metric fixtures first, then run
  the bounded structural-control, endpoint, convergence, and 3D smoke gates.

## Cu-fill topology and reduced-model guards (2026-07-11)

- The new candidate is a quasi-steady suppressor-access model, not S-NDR,
  CEAC, or liquid electrochemistry. A fixed-sticking diffuse ray field supplies
  a normalized access proxy; local equilibrium balances suppressor adsorption
  against deposition-driven deactivation. `adsorptionStrength` combines an
  adsorption coefficient and activity, and scaling it with `deactivationRate`
  is not independently identifiable from morphology. Keep these as
  uncalibrated model coefficients until a published limiting case is
  reproduced.
- A sealed-void negative control exposed a serious false-success path. With
  ViennaPS's default `ignoreVoids=false`, an inaccessible Cu surface has zero
  suppressor flux, reverts to the active rate, and shrank a 0.0600 trapped-void
  area to 0.01020 in 0.2 model time. Setting
  `AdvectionParameters.ignoreVoids=true` preserved the same void area exactly.
  Every candidate-fill execution must carry this guard, and a trapped void
  remains a hard failure rather than being allowed to heal numerically.
- `MakeHole(QUARTER)` and `MakeHole(HALF)` are half-trenches in 2D. A trapped
  centerline void can therefore be clipped by the reflective boundary and
  appear as an open mesh, defeating a closed-component-only test. Fill
  topology qualification now uses `HoleShape.FULL`. Secondary open components
  below the field are invalid seam/mesh defects, and a synthetic clipped-void
  fixture is rejected instead of being labelled void-free.
- Fill progress now retains separate responses: open-void area, trapped-void
  area/count/size, topology validity, post-seed-cavity fill fraction, mouth
  aperture, pinch-off state, field/center overburden, and the grid-dependent
  void detection limit. Fill fraction is a trajectory response, not a
  replacement for the resolved-void-free and positive-overburden gates.
  ViennaLS cannot establish metallurgical seam quality after two fronts merge;
  preserve pinch-off history and state that limitation explicitly.
- The isolated full-2D-trench rate-field check is deterministic but still only
  a mechanism check. At `adsorptionStrength=0.25`, field/floor suppressor flux
  is 1.0054/0.2736, coverage is 0.8194/0.2687, and growth velocity is
  0.04431/0.14896; the relative equilibrium residual is 9.45e-16. Two fresh
  processes reproduced the values exactly. This proves bottom-faster ordering,
  not void-free morphology or recipe feasibility.
- Material gating is now explicit. A controlled stack grows on the registered
  `CuSeed` material, transitions to plated-Cu material IDs after the duplicated Cu layer
  separates, and gives zero velocity on SiO2. Production wiring must always
  allow both seed and plated Cu while continuing to exclude liner and barrier.
- Anonymous numeric custom materials are not resumable with ViennaPS `.vpsd`:
  `Custom#1001` returned as a different custom ID after Writer/Reader even
  though its mesh was exact. Replacing it with the registered name `CuSeed`
  preserves both material identity and every mesh node/connectivity entry in a
  fresh round trip. Resume tests now load checkpoint 1 and actually execute
  checkpoint 2; merely reopening an already terminal case is not a resume test.
- A convex-cap versus concave-bowl access control passes the reduced model's
  intended sign check without implying electrochemistry. At matched radius and
  fixed seed, the exposed cap receives 1.097 times the suppressor flux and has
  higher coverage; the less-suppressed bowl grows 1.171 times faster. Duplicate
  runs are exact and the equilibrium residual is 1.08e-15.
- The first four morphology trajectories appeared to produce three void-free
  fills, including the deliberately unsuppressed conformal control. Critical
  trajectory review rejected all three. Their open-cavity depth fell by 0.515
  to 1.107 in one checkpoint, which first looked nonconservative. Exact mesh
  inspection corrected that interpretation: the disappearing region is a long
  pointed/slit tail whose maximum width is small enough for opposing fronts to
  merge within one step. The event is an unresolved centerline-seam risk, not
  proof of impossible bulk material motion. The original rows remain visible
  as superseded evidence.
- The transition guard is now width-aware. A large depth jump with a
  disappearing tail no wider than twice the maximum front motion plus one grid
  cell is classified as an unresolved narrow-tail merger; a wider unexplained
  loss is nonconservative or unmeasurable. Both remain hard failures, but the
  reason is preserved accurately. The corrected four-arm rerun reports seam
  aspect ratios from 15.8 to 52.0 and no accepted target pass.
- A 24-case, four-seed checkpoint study at grid delta 0.01 halved the increment
  from 0.05 to 0.025 and 0.0125. Every case still failed. In the uniform-growth
  control the failure stayed at model time 0.50 and the depth jump remained
  1.091 to 1.107. In the suppressed arm the mean jump decreased from 0.514 to
  0.391. A further eight-case grid-0.005 block also reproduces the narrow-tail
  merger in all eight runs; the suppressed arm removes a tail only about
  0.0059 wide but 0.370 tall. Checkpoint and grid refinement therefore do not
  certify seam-free closure. The access/rate law can still be studied, but a
  production fill claim needs either an explicit seam-resolving representation
  or a guard that rejects every two-front merger.
- The first 32-case access/coverage surface produced 31 valid rows and one
  deterministic failure. Replaying its saved checkpoint localized the crash to
  a two-node double-edge fragment: edge-count degree made it look closed, but
  it is not a simple polygon, so `ordered_closed_component` indexed an empty
  traversal candidate. The fill runner now filters that degenerate fragment
  before quantitative topology measurement, marks the row invalid with an
  explicit degenerate-component/seam flag, and retains a full traceback for any
  future error. Because the runner fingerprint changed, all 32 cases are being
  rerun cleanly; the 33 earlier attempts remain preserved rather than mixed
  into the new surface.
- The clean rerun completed 32/32 current-fingerprint rows with no current
  errors; all 33 earlier attempts, including two error attempts, remain visible
  as superseded evidence. No point passes. All higher-sticking settings end in
  pinch-off, invalid topology, or an unresolved narrow-tail merger. Lambda 1
  and 2 at sticking 0.05 retain an open mouth through duration 3, but they are
  unfinished censored trajectories, not valid fills. The response is strongly
  non-monotonic, and the only no-hard-failure points lie on the lowest tested
  sticking boundary. The next model experiment therefore expands sticking to
  0.025, fills lambda 0.5 to 1.25, extends duration to 8, and uses four unseen
  seeds per point. Its ranking is predeclared around validity, hard gates, and
  worst-seed bottom-up progress; scalar loss and a lucky replicate are absent.
- Prelaunch review caught that the intended four replicates were not actually
  independent. The runner sets each ray seed to `base_seed + checkpoint`; bases
  94000 through 94003 over 320 checkpoints create 1,280 uses but only 323
  unique seed values. The first launch was stopped after 12 completed rows, and
  those rows remain preserved as invalid-design evidence. The corrected v2
  manifest uses bases 94000, 95000, 96000, and 97000, shared across designs for
  paired comparisons but disjoint within each recipe. A runner guard now
  rejects overlapping streams whenever the manifest requires independent
  trajectory replicates. Earlier multi-seed Cu-fill blocks that used
  consecutive bases remain useful for deterministic failure reproduction, but
  their uncertainty and independent-replication language is withdrawn.
- The corrected v2 boundary refinement completed 72/72 valid rows with one
  runtime fingerprint, no errors, no censors, and no target events. Every
  trajectory reaches a hard failure before duration 8: 48 report pinch-off or
  a closed void, 24 report an unresolved narrow-tail merger, 13 also become
  topologically invalid, and one retains a degenerate closed fragment. These
  labels overlap by design, so their counts exceed 72. At sticking 0.025,
  raising the coverage scale from 0.5 to 1.25 delays mean failure from 2.625 to
  5.35 and increases mean cavity-area reduction from 0.1753 to 0.1999, but
  mean floor advance stays near 0.09. The leading worst stream reaches about
  79% area fill while advancing the floor only 0.0915 of a 1.25-deep via.
  Saved interface histories show the sidewalls closing inward around a nearly
  stationary floor, followed by a tiny trapped loop or unresolved tail. This
  rejects more lambda-by-sticking-only compute as the next move. A remaining
  mechanism coefficient—especially suppressed/active deposition-rate ratio—
  must change before another boundary expansion is scientifically useful.
- Region-resolved inspection overturns the tentative rate-ratio plan. On all
  72 initial diagnostic surfaces, floor/lower-wall suppressor flux is 1.0105
  to 1.1326, floor coverage is higher by 0.00023 to 0.06588, and floor/lower-
  wall velocity is only 0.8041 to 0.9967. The continuity geometry requires at
  least H/a=9.851 axial-to-lateral velocity ratio (about 12.5 using the
  measured lower-wall clearance) to reach the field before sidewall closure.
  Because `v=Va*(1-theta)+Vs*theta`, `Va>=Vs`, and coverage increases with
  suppressor flux, changing Va/Vs cannot reverse the observed ordering. Do not
  launch a suppressed/active-rate morphology DOE under this access field.
- The next bounded question is transport sign, not recipe optimization. First
  verify an exact-stack prescribed bottom-localized positive control at two
  grids; then use one-checkpoint static rate fields to ask whether any valid
  sticking/source-angle setting makes the floor less suppressed and faster
  than every wall region. Only a sign-qualified transport point may enter a
  morphology screen. The current center-minus-field velocity is not a bottom-
  up metric and must be supplemented by floor/lower/middle/upper-wall regions.
- Finite `gasMeanFreePath` is not qualified as a transport knob. ViennaRay's
  `rayTraceKernel.hpp` computes a path-dependent scatter probability but, on a
  scatter, advances the origin by the unit-uniform decision variate itself
  (`origin + direction * rnd`) rather than a sampled exponential flight
  distance. Until collision-distance statistics and ray-weight conservation
  are fixed and tested, only the `-1` ballistic sentinel is admissible.
- The exact protected-stack structural challenge separates a bad candidate
  law from a bad geometry representation. At grid 0.01 and 0.005, the current
  quasi-steady law gives nearly identical initial floor/lower-wall velocity
  ratios (0.9949 and 0.9944) and creates one sealed lateral-closure void. The
  same two grids under a prescribed bottom-up morphology control use a ratio
  of 20, reach resolved void-free fill, retain minimum overburden 0.15227 and
  0.15084, and leave every protected interface unchanged. The candidate rate
  law is rejected; the positive result is a representation control, not an
  electroplating recipe or validation of S-NDR/CEAC chemistry.
- An independent prelaunch audit rejected the first 84-case transport-sign
  draft before it consumed simulation time. It used only the 0.30 by 1.25
  continuity geometry even though the nominal 0.30 by 3.00 HBM tier is the
  required mechanism case; it could combine a sign pass from one design with
  an H/a pass from another; its analytic Pi_A range was too narrow to support
  a model-family no-go; and its validator did not freeze all geometry, layer,
  ray, threshold, and provenance fields. A transport screen is not authorized
  merely because its code runs: those four conditions must be guarded and
  tested before launch.
- The corrected coarse transport screen completed 168/168 valid current rows:
  continuity and nominal-HBM geometries, seven sticking levels, three source
  powers, and four paired disjoint ray streams. All 168 saved one-checkpoint
  morphologies retain one valid open component, an open mouth, resolved front
  motion, the protected stack, and equilibrium residual below 2.7e-14. No
  strange topology or material motion explains the result.
- No tested design passes the required transport sign on all four streams in
  either geometry tier. The closest tested miss is sticking 0.025 with source
  power 0. Its worst floor/lower-wall flux ratios are 1.002 in the continuity
  case and 1.021 in nominal HBM, versus the strict target below 0.95; the
  corresponding worst velocity ratios are 0.998 and 0.957, versus the target
  above 1.05. Higher sticking worsens the flux ordering monotonically in all
  24 tier/power/seed sequences, and nominal HBM has a larger wrong-sign flux
  ratio than continuity in all 84 paired comparisons. The required and broad
  analytic coefficient envelopes also produce zero cross-tier H/a passes.
  This is a coarse no-go for the current 2D ballistic transport proxy, not yet
  a model-family rejection.
- A balanced descriptive decomposition on log regional ratios quantifies what
  controls this sampled surface. Sticking accounts for 99.57% of continuity
  and 99.85% of nominal-HBM flux-ratio sum of squares; source power contributes
  only 0.32% and 0.10% directly to that flux response. After the nonlinear
  coverage law converts flux to growth velocity, source power and interaction
  become material: continuity velocity shares are 59.02% sticking, 22.69%
  power, and 18.19% interaction; nominal shares are 30.92%, 57.33%, and
  11.36%. Paired-stream residual shares remain below 0.4%. These percentages
  are range- and scale-specific screening evidence, not universal physical
  dominance or calibration.
- The closest miss lies at the tested lower-sticking boundary and the physical
  lower source-power bound. Before a pivot, confirm or expand that boundary and
  separate grid 0.01/0.005, 1000/2000 rays, and max-reflection 400/800 effects
  on both tiers. A terminal pivot still requires matched 3D transport.
- The first offline review attempt failed safely without writing a conclusion:
  at the physical `R/Va=0` coefficient boundary, one required-grid case mixed
  finite zero ratios with an undefined 0/0 stream, and the reviewer attempted
  `min()` before checking eligibility. The 168 simulations and snapshots were
  preserved; a reviewer-only regression now records the undefined stream as
  visible and ineligible, emits strict JSON, and completes with zero current
  artifact errors. Do not rerun valid simulations to repair analysis code.
- The frozen numerical confirmation initially failed its independent launch
  audit for three reasons: the exact temporary runtime was absent, the manifest
  validator did not freeze the full target object, and the normal test entry
  point omitted its strict-JSON contract. The runtime was rebuilt to the exact
  expected binary hash, the target validator now rejects changed values and
  extra keys, and all 12 confirmation tests run from the standard command.
  This is a durable rule: a scientifically correct matrix is still no-go when
  its executable, thresholds, or normal test path are not frozen.
- The repaired 128-cell confirmation completed with eight hash-verified parent
  reuses and 120 new executions; all 128 cells are metric-valid. Grid 0.01
  versus 0.005, 1,000 versus 2,000 rays, and maxReflections 400 versus 800
  create zero class-changing interactions and zero identified coarse or
  reflection artifacts. At the high-fidelity cell, lowering sticking from
  0.025 to 0.0125 improves the worst cross-tier flux ratio from 1.01504 to
  0.99297. The 0.02207 improvement exceeds the largest paired numerical effect
  or interaction, 0.01671, so it is a real boundary trend within this model.
  It is not a pass: both designs clear zero of eight combined transport streams,
  and the lower-sticking worst velocity ratio is 1.00298 versus the strict
  target above 1.05.
- The 128-cell result required one more lower-sticking boundary at 0.00625,
  grid 0.005, 2,000 rays, and maxReflections 1,600 versus 3,200 on both tiers
  and all four paired streams. It did not authorize morphology, automatic
  launch, or a model-family pivot.
- The first 16-cell boundary design was rejected before launch because it
  inherited `maxBoundaryHits=1000`, below both requested reflection depths.
  Its absorption-only residual bound therefore could not bound total ray
  termination, and comparing it with historical 0.0125 rows would have mixed a
  sticking effect with a boundary-hit-cap change. The corrected design raises
  the cap to 6,400 and adds eight newly executed, matched-cap 0.0125 controls.
  Durable guard: a reflection-convergence study must freeze and validate every
  independent ray-termination cap, and a changed cap requires a matched control.
- The corrected lower-boundary confirmation completed 24/24 newly executed,
  metric-valid cells: eight 0.0125 controls at 800 reflections and eight
  0.00625 streams at each of 1,600 and 3,200 reflections, split across the
  continuity and nominal-HBM tiers with four paired RNG streams. The two
  0.00625 reflection arms have identical classes and zero paired change in all
  four reviewed transport responses. The historical cap-1,000 versus new
  cap-6,400 0.0125 comparison also has zero paired response change, but remains
  context only; the new matched-cap control is the decision authority.
- Lowering sticking from 0.0125 to 0.00625 improves every paired flux stream,
  but only changes the worst cross-tier flux ratio from 0.992974 to 0.988828.
  The 0.004147 worst-response improvement is below the predeclared 0.016714
  continuation threshold. The candidate still passes 0/8 combined transport
  streams and its worst velocity ratio is 1.004256, versus the strict target
  above 1.05. This closes automatic 2D boundary expansion: it is a
  reflection-converged no-go for this 2D transport screen, not a morphology or
  recipe result.
- Decision:
  `two_dimensional_transport_no_go_requires_matched_3d_before_pivot`.
  Morphology, another automatic lower-sticking expansion, and a model-family
  pivot remain unauthorized. The next fill-model decision must use a frozen,
  independently audited, matched 2D-versus-3D transport bridge for the
  matched-cap 0.0125 control and reflection-converged 0.00625 candidate before
  deciding whether the quasi-steady model family should be replaced.

## Liner and barrier/seed qualification correction (2026-07-11)

- The first 10-case grid block completed without simulator or metric errors,
  and all resolved liner, barrier, and seed interfaces remained continuous
  with open apertures. Data completeness is not numerical qualification.
- The baseline liner minimum thickness is 0.03433 and passes the 0.020 gate,
  but floor/field conformality is 0.87115 and lower-wall/field conformality is
  0.85900 versus the 0.995 target. The original runner omitted the lower-wall
  term from its pass label; the runner and independent reviewer now require it.
- The combined barrier-plus-seed minimum is 0.004797 versus the 0.012 target,
  even though floor/field conformality is about 0.99949. Individual barrier and
  seed lower-wall/field ratios near 0.231 explain why a floor-only coverage
  read is insufficient. These baseline misses are much larger than observed
  mid-to-fine grid shifts and are credible recipe failures, not evidence that
  the metric rewards missing film.
- The two finest-grid pairs were only a spot check and no quantitative
  tolerances were declared before that run. Do not retroactively qualify it.
  The next block fingerprints the runner, metrics, process wrapper, and binary;
  predeclares maximum paired deltas; uses four shared seed labels; and compares
  both grid 0.00125 versus 0.000625 and 2,000 versus 4,000 rays per point.
- That replacement block completed 12/12 valid with exact runtime
  fingerprints. All 14 declared metrics pass both comparisons across four
  shared seeds, with no functional, continuity, or aperture gate changes.
  The largest critical grid shifts are 0.002124 for liner floor/field and
  0.001636 for liner lower-wall/field conformality; the corresponding ray-count
  shifts are 0.001990 and 0.000877, all below the predeclared 0.0025 limits.
  Grid 0.00125 and 2,000 rays per point are therefore accepted for exploratory
  layer-factor screening only. Finalists and any near-gate row still require
  fine-grid confirmation; the failing baseline recipe is not rescued by this
  numerical qualification.

## Pattern/Bosch and runtime-control correction (2026-07-12)

- The saved Bosch bases 52000 through 52003 are not four independent
  replicates. `bosch_etch()` consumes one ray seed for the initial etch and
  three per cycle, so a 14-cycle run uses 43 consecutive streams. Adjacent
  bases share 42 of those 43 streams. The saved profiles remain useful fixed
  geometry blocks, but their spread is not a robustness estimate. New Bosch
  manifests must use a base-seed stride of at least `1 + 3*num_cycles`; a
  runner test now rejects overlapping schedules while preserving the same
  disjoint bases across compared process arms for common-random-number pairing.
- Failed foundation rows formerly counted as completed case IDs. Resume now
  skips only `ok=true` rows, so a process-level failure is retried rather than
  silently accepted as a finished experiment. New expensive runners must go
  further by binding the case payload, runner, metric, process wrapper, and
  exact runtime hashes and by rejecting malformed ledgers, duplicate success,
  or success followed by failure.
- Pattern measurement now supports both symmetry-clipped and full 2D masks.
  It reports bottom/middle/top CD, opening-center position and shift, left and
  right sidewall angle, mask height, and aperture validity from the generated
  mesh. These are geometry outputs; they are not exposure-dose or focus
  conclusions because `MakeHole()` contains no optical lithography model.
- The Bosch wrapper now exposes a nonpositive ion-driven mask-erosion
  coefficient. Zero preserves the historical infinite-selectivity control;
  positive values are rejected. Shared-stream tests show monotonic mask loss
  and retain complete consumption as an explicit hard failure. The selected
  depth-matched cycle must keep an open mask feature resolved by more than two
  grid cells. This is a numerical survival gate, not a calibrated resist-loss
  specification.
- A single-seed, grid-0.01, 250-ray range-finding preflight bracketed the next
  mask experiment; it is not a DOE or recipe result. After 14 cycles, remaining
  mask height was 0.2907 at rate 0, 0.2165 at -0.01, 0.1433 at -0.02, and zero
  at -0.04. The cycle-13 CD error and bow also moved, so mask erosion cannot be
  studied only as a remaining-thickness response. The frozen Gate-0 matrix
  must include both survival and consumption arms and judge the silicon CTQs
  at the same depth-matched checkpoint.
- Cycle checkpoints are now written atomically and carry their case ID, cycle,
  raw silicon and mask polylines, and SHA-256. Downstream film comparisons may
  reuse a checkpoint only when the corresponding attempt is valid and the
  checkpoint payload and hash are independently verified.
- Repository tests belong to three exact runtime capabilities: stock ViennaPS,
  the Cu-only extension, and the CMP-only extension. The capability-routed test
  command verifies all binary hashes and capabilities before executing a group
  and treats publication and historical regressions separately from current
  scientific authority. A green historical or wrong-runtime test is not a
  traveler pass.
- The generated registry now has 232 records and explicitly includes every
  field in `HeightMaterialCMPParams`, its exact CMP-only runtime ownership, the
  tested overpolish-dose ladder, and four required survival limits whose values
  remain `None`. Registry completeness does not solve the missing product
  limits; it prevents those missing limits and custom-model controls from being
  omitted when the CMP campaign is designed.
- All eleven known executable consumers of `TARGET_SPECS`, `target_score`,
  `floor_reach_metric`, or `fill_tip_gap` now fail closed unless the caller
  supplies `--allow-legacy-metrics` for explicit historical reproduction.
  This preserves old artifacts and scripts without letting a stale proxy sweep
  re-enter the active V2 campaign by accident.
- A primary-source check did not justify inventing the four missing CMP
  survival limits. A published via-middle TSV flow uses separate Cu,
  barrier/isolation, and SiN-stop polishing stages and reports less than 150 Å
  ILD mapping range and less than 100 Å post-process Cu extrusion, but those are
  achieved process outputs, not allowable SiO2-stop or Cu-plug loss limits
  transferable to this uncalibrated geometry (doi:10.1016/j.mee.2011.03.004).
  Experiments also show that downforce, time, and Cu/barrier/oxide selectivity
  jointly control TSV dishing/protrusion (doi:10.1016/j.mee.2015.12.004;
  doi:10.1088/1674-4926/35/2/026002). None supplies a universal product limit
  that maps directly to the current model units. Keep all four limits `None`.
  Before product provenance exists, CMP may report a normalized sensitivity
  map of retained stop fraction, stop erosion, plug-height loss, and plug-area
  loss versus endpoint/overpolish, but it may not emit a target pass or recipe.
- The first long Gate-0 launch exposed a supervisor-test blind spot: a plain
  `nohup` descendant was reaped when the invoking execution cell ended, even
  though the earlier short detached test passed. It wrote no simulation rows.
  The launcher now uses a detached macOS `screen` session and changes to the
  repository before execution. A survival smoke test proves the supervisor and
  nested child remain alive after the launcher exits. Interrupt handling now
  terminates the complete descendant tree; its regression test proves a nested
  worker is not orphaned. The unchanged 24-case command was relaunched under
  this durable path; the failed launcher attempt remains visible in its runtime
  log and stale-lock archive.
- The numerically qualified liner/barrier metric was still a quarter-symmetry
  measurement. Reusing it on a stochastic full-width Bosch checkpoint would
  silently mirror one wall and hide left/right field or sidewall imbalance.
  A separate full-2D film metric now measures both fields, both walls, the
  floor, and the remaining aperture. Its conformality denominator is the
  thicker of the two field films, so asymmetry cannot improve a pass label.
  Analytic tests cover symmetric film, asymmetric field/wall thickness, and
  rejection of a clipped quarter section. Material-region connectivity remains
  a separate hard gate; sampled interface thickness is not proof of an
  electrically continuous seed path.
- Gate-0 checkpoints contain raw silicon polylines rather than a native
  ViennaPS domain. They cannot be handed to liner deposition by assumption:
  `FromSurfaceMesh` reinitializes a level set and could change a near-boundary
  CTQ. A dedicated handoff guard now verifies the checkpoint payload and file
  hash, reconstructs silicon on the original grid, independently remeasures
  depth/CD/bow/scallop, bounds surface and depth drift to one quarter cell,
  CD/bow/scallop drift to one half cell, and sidewall-angle drift to 0.1
  degree, and rejects any etch gate flip. The wider CD bound follows from two
  independently moving walls. An analytic full-width trench round trip is
  exact to floating-point tolerance. Each completed stochastic Gate-0
  checkpoint must still pass this guard before it becomes a reusable upstream
  geometry; otherwise the selected cases must be rerun with native level-set
  checkpoints.
- The prepared broad pattern/Bosch screen is 160 unique recipes by four
  disjoint Bosch streams, or 640 depth-matched trajectories. It combines 117
  maximin-selected Latin-hypercube recipes over 12 jointly varied factors with
  43 unique anchors covering the reference, transformed center, every
  one-factor low/high boundary, and a 5-by-4 mask-height-versus-erosion stress
  block. The selected LHS has maximum absolute pairwise factor correlation
  0.172. Mask height is held at the declared 0.30 target in the joint LHS;
  sweeping it everywhere would have turned most of the broad screen into
  intentional pattern-spec failures. Cycle count is recorded as the
  depth-matching result over cycles 1 through 50, with early termination after
  depth 1.45 to protect the domain; it is not treated as an independent shape
  winner. Starting at cycle 6 would bias against fast recipes, while a 22-cycle
  ceiling would bias against slow recipes. The ranges are explicitly
  model-space sensitivities, and the design prohibits claims about
  unrepresented dose, focus, gas flows, pressure,
  power, temperature, or switching transients. Gate-0 and all four geometry
  handoffs must pass before an execution manifest can be frozen or launched.
- The 640-case executor is prepared but deliberately unlaunchable: its frozen
  manifest does not exist. The freezer requires a complete 24-case Gate-0 pass
  plus four accepted full-width checkpoint handoffs, then binds both review
  hashes, the deterministic design, every relevant source file, and the exact
  ViennaPS/ViennaLS binaries. The runner keeps only the current best and
  fallback meshes in memory, records a scalar cycle history, replaces
  nonfinite outputs with visible nulls plus reasons, requires a real Bosch
  cycle (cycle >=1) before any hard pass, saves the selected raw geometry
  atomically, and rejects stale, malformed, duplicate, or post-success resume
  rows. Synthetic early-stop and depth-selection tests confirm that the cycle
  closest to target is retained rather than the final over-etched shape.
- The broad-screen reviewer is also predeclared before execution. It
  independently reloads each selected mesh, remeasures pattern and etch CTQs,
  verifies the complete cycle history and early-stop state, and recomputes all
  eight primitive gates. A nonfinite or provenance-invalid row receives a
  1,000,000 penalty; each primitive hard-gate miss receives 1,000 before any
  continuous distance term. Recipes are aggregated only across their four
  streams and ranked by invalid count, missing hard passes, worst primitive
  gate count, worst score, adverse p90, then mean. Tail direction is explicit:
  high CD/bow/scallop/error is adverse, while low remaining mask is adverse;
  raw depth is descriptive and depth-to-target error is ranked. Any best
  feasible or best-miss recipe within 2% of a tested factor boundary is marked
  for expansion and cannot be called an optimum. A complete review can
  authorize targeted pattern/Bosch refinement only, never a recipe, process
  window, downstream recipe, or full traveler.
- Gate-0 first-row checkpoint (2026-07-12 02:01 UTC): the first two of 24
  cases completed on the quarter-reference arm in 2,273 and 2,340 seconds.
  Both checkpoints passed hash validation, independent metric recomputation,
  and all declared pattern/etch/mask gates. Their cycle-13 depths are 1.26964
  and 1.33449, maximum CD errors 0.03605 and 0.03595, bows 0.01432 and
  0.01916, and remaining masks 0.29934 and 0.29962. The second depth is only
  0.0155 below the upper target limit, reinforcing the need for disjoint
  stochastic streams. This is quarter-geometry evidence only: the full-width
  representation, grid bridge, erosion monotonicity/bracket, and remaining 22
  cases are pending, so no screen or downstream work is authorized.
- Layer API audit correction: the historical barrier/seed wrapper sets
  `directionalVelocity = thickness` and `isotropicVelocity = thickness *
  iso_ratio`. Increasing `iso_ratio` therefore increases total horizontal-field
  dose while changing conformality, so its apparent effect cannot be assigned
  to isotropy alone. New qualification work must hold field dose constant and
  split it as `directional = dose * (1 - isotropic_fraction)` and `isotropic =
  dose * isotropic_fraction`. The isotropic endpoint is a representation
  control, not a calibrated recipe or physical process recommendation.
- The installed API exposes generic single-particle deposition, TEOS/PECVD,
  and ALD process families. TEOS at reaction order one is not equivalent to
  the generic single-particle model because surface coverage changes sticking
  and reflection; a coarse matched-dose diagnostic changed floor-to-field
  conformality by about 0.016. Liner model family and TEOS reaction order must
  therefore be treated as explicit structural/model-form hypotheses before
  recipe screening. No TEOS, PECVD, or ALD mechanism is accepted solely
  because it reaches a numerical thickness target.
- The API audit originally omitted `AtomicLayerProcessParameters`, even though
  `SingleParticleALD` requires its pulse, cycle, coverage-step, and purge
  controls. All five controls are now registered. A bounded subprocess
  preflight on the installed ViennaPS 4.6.1 completed for one and ten cycles
  with `purgePulseTime=0`, but a documented-style 0.05 purge pulse on the same
  full-width analytic via exited with native signal 11 (shell status 139).
  ALD therefore remains an API-available hypothesis, not a campaign model;
  purge-enabled execution must be isolated or fixed upstream before a DOE.
- The layer model-acceptance program is now predeclared as 640 fixed
  pre-confirmation simulations plus at most 192 adaptive confirmations. It
  contains a 48-case ray/reflection preflight, 264 liner model-surface cases,
  and 328 sequential barrier/seed interaction cases. Every downstream arm
  reuses the same four accepted full-width Bosch shapes; the barrier study
  carries two different liner inputs to expose cross-step dependence. The
  ideal isotropic arm is metric/morphology control only. Any barrier/seed pass
  requiring isotropic fraction >=0.9 is labeled boundary/model limited rather
  than an iPVD recipe. Execution remains fail-closed until Gate-0, all four
  handoffs, and an independently tested material-region connectivity metric
  pass; no launch manifest exists.
- The pre-existing solid-region connectivity primitive was already frozen in
  `traveler_metrics.py`; the missing piece was its full-width layer
  integration. `full_2d_layer_metrics.py` now combines sampled thickness with
  connected negative-grid components and places floor/field anchors at the
  incoming interfaces using a resolution-scaled neighborhood. Mid-film
  anchors are invalid here because ViennaLS exposes a narrow interface band,
  not every solid-interior grid point. An intact U-shaped layer passes; a severed right wall
  fails even when every sampled thickness still looks good; a film at or below
  two grid cells is unresolved rather than passed; and a resolved asymmetric
  film keeps the conservative thinner-wall margin. This removes the
  connectivity launch blocker without changing any Gate-0 frozen source.
  A real nested ViennaPS SiO2/TaN/CuSeed control also retains three distinct,
  independently connected material regions after the complete stack is built;
  the check is not limited to a generic test-material stub.
- Pattern/Bosch Gate-0 completed all 24 cases on supervisor attempt 1 with
  zero runtime errors, 24 hash-valid checkpoints, and 24/24 initial-pattern
  passes. The frozen critical review correctly blocks the next screen. The
  full-width fine reference passes etch 3/4: seed 62000 reaches depth
  1.35068067, which is 0.00068067 above the fixed 1.35 upper gate and remains a
  hard near-boundary miss. Across all arms, depth passes 22/24, CD profile
  23/24, bow 22/24, and mask resolution 24/24.
- The representation bridges fail their predeclared tolerances. Full versus
  quarter differs by as much as 0.06856 in depth (limit 0.02) and 0.01670 in
  top CD (limit 0.01), with one gate flip. Grid 0.0025 versus 0.00125 differs
  by as much as 0.17630 in depth, 0.09868 in bottom CD, 0.02752 in bow, and
  0.07723 in maximum CD error, with gate flips. The coarse arm's approximately
  fourfold speedup therefore cannot justify using it as the broad-screen
  authority, and quarter geometry cannot substitute for full width under this
  evidence.
- Mask loss is monotonic but not failure-bracketed. Remaining mask ranges are
  0.23061-0.23118 at mask ion rate -0.01, 0.16231-0.16316 at -0.02, and
  0.02682-0.02722 at -0.04. Even -0.04 survives on all four seeds and remains
  more than 21 fine-grid cells thick, so the earlier coarse preflight did not
  establish the required full-cycle failure bracket. Expand beyond -0.04 with
  a bounded one-seed bracket, then confirm the surviving/failing transition
  on all four streams; do not relabel -0.04 as the failure edge.
- Saved surface meshes are not yet safe downstream checkpoints. Seed 62000 is
  ineligible because its full-width reference misses the depth gate. The other
  three reconstructions drift by 0.43-0.48 grid cells against a predeclared
  0.25-cell surface limit; seed 61000 also exceeds its top-CD handoff tolerance.
  Do not loosen the frozen tolerance post hoc. The corrective Gate-0 must save
  a native level-set/domain checkpoint, select a depth-matched full-width fine
  state per seed, and prove exact or accepted reconstruction before layer work.
  No broad screen, downstream layer launch, recipe, or process-window claim is
  authorized by this completed Gate-0.
- Public-review correction (2026-07-13): the handoff denominator is 0/3
  eligible reloads, not 0/4. Four source checkpoints exist, but seed 62000 was
  excluded before reload comparison because its source etch failed depth. The
  phrase "just before mask failure" was also rejected: no failure was observed,
  so the data locate only a surviving point at -0.04, not its distance from the
  failure boundary. These distinctions are now guarded by
  `test_gate0_publication_checkpoint.py` and shown explicitly in the public
  checkpoint.
- Gate-0 R1 is frozen as an adaptive 9-to-14-case correction, not a broad DOE.
  It uses full-width grid 0.00125 geometry, depth-matches each seed, compares
  1000 with 2000 rays on four shared seed labels, searches mask ion rates
  -0.05, -0.06, and -0.08 only until the first resolved-mask failure, then
  confirms that rate on the other three seeds. Selected states are saved as
  native `.vpsd` domains and independently reloaded; no surface-mesh
  reconstruction is used. Passing R1 may authorize only the broad
  pattern/Bosch screen.
- Launch-integrity mistake (2026-07-13): an initial detached R1 process started
  while a delegated code review was still applying final fixes. The on-disk
  runner and reviewer hashes changed before any row completed. The process was
  interrupted, zero rows were accepted, and its runtime log remains under
  `pattern-bosch-gate0-r1-20260713` as rejected evidence. Durable rule: all
  implementation and review agents must be terminal, focused tests must pass,
  and runtime fingerprints must be checked twice before a campaign starts.
  The final campaign was relaunched separately as
  `pattern-bosch-gate0-r1-final-20260713` with matching frozen hashes.
- Noise-audit correction (2026-07-13): the earlier 32-row stochastic baseline
  is not an independent replicate set. Its adjacent base seeds differ by one,
  while a 14-cycle Bosch trajectory consumes 43 process RNG streams, so the
  streams overlap. Do not use that block to choose replicate count, calculate
  SNR, or claim that four repeats are sufficient. The disjoint Gate-0 seeds
  and the new discovery sentinels are the current noise evidence. Every new
  manifest must verify seed spacing against its complete process-seed horizon.
- Broad-first pivot: do not launch the prepared 160-recipe x 4-seed screen.
  It spends 480 of 640 trajectories repeating recipes, mixes product geometry
  and structural stresses into the recipe surface, and uses a stale erosion
  range. The replacement nominal screen holds CD, mask height, taper, and mask
  erosion fixed; spans the nine active Bosch controls broadly; estimates noise
  at predeclared sentinel recipes; and allocates extra seeds only to boundary,
  high-margin, uncertain, or finalist recipes. Fine factor increments are
  derived later from response gradient divided by the combined stochastic and
  numerical noise floor, not chosen before the response surface exists.
- Full-traveler DOE correction (2026-07-13): the replacement Bosch-only screen
  was still insufficient as campaign authority. A parameter movement is not a
  useful traveler finding merely because it exceeds simulator variation. The
  active method is now broad low/nominal/high skew screening, direct effect and
  correlation ranking, exact saved-geometry propagation into later CTQs, then
  focused DOE on sensitive controls with weak controls held at documented
  nominal values. Every factor receives separate `step-sensitive` and
  `traveler-relevant` labels; weak main effects remain active when a confirmed
  interaction matters. `RESEARCH_PLAN_V3.md` defines practical detection
  thresholds, range expansion, shared-geometry blocks, staged case counts, and
  model gates. The old scalar-loss state, 640-case freezer, and Bosch-only S1
  freezer are explicitly superseded and fail closed.
- Watcher correction (2026-07-13): the guarded R1 anchor watcher initially
  treated a 380-second supervisor-heartbeat delay as fatal while both verified
  simulation workers remained alive and CPU-bound. It exited without signaling
  R1. The liveness guard now tolerates up to 900 seconds but still requires the
  exact campaign, PIDs, commands, parent/process group, lock, and live child;
  the stop action remains gated on all four independently validated anchors.
- R1 fidelity interim (2026-07-13): the first two 2,000-ray pairs both preserve
  hard-gate decisions, but the 1,000-to-2,000 shifts already exceed frozen
  numerical limits. Seed 62000 changes depth by 0.05106 versus the 0.02 limit;
  the two-pair maximum bottom-CD shift is 0.01562 versus 0.01, and maximum bow
  shift is 0.00673 versus 0.005. Therefore 1,000 rays cannot pass the bridge
  even if the remaining pairs agree. The last two already-running anchors are
  retained to complete the four-shape 2,000-ray baseline and native handoffs,
  not to rescue the rejected shortcut. No tolerance is loosened.
- Superseded-runner guard sequencing: the old 640-case freezer and both old
  state-ledger resume paths now fail closed, and the superseded Bosch-only S1
  runner rejects constructed manifests. The old 640-case runner itself is an
  active R1 import and must not change while R1 is running because that would
  invalidate the frozen source fingerprint. Its default manifest does not
  exist. Add the direct V3/supersession rejection immediately after R1 reaches
  a terminal state, then rerun the capability inventory.
- V3 numerical release (2026-07-13): all eight fixed R1 rows and their native
  checkpoints independently reload, remeasure, and match their frozen case
  payloads. The 1,000-ray setting is rejected for shape screening because its
  paired maximum shifts versus 2,000 rays exceed the predeclared limits for
  depth (0.05106 versus 0.02), bottom CD (0.01562 versus 0.01), and bow
  (0.00673 versus 0.005). The four 2,000-ray checkpoints are released as
  immutable numerical baselines, and grid 0.00125 / 2,000 rays / 2D is the V3
  Stage 1/2 exploratory setting. This is selection of the higher-fidelity
  tested arm, not an asymptotic convergence proof. The intentionally unrun
  mask ladder is outside this narrow decision, so no mask-loss boundary is
  authorized; recipe, process-window, full-traveler, fab-setting, and
  automatic-launch authority all remain false. The machine-readable decision
  and critical review are `v3_numerical_release.json` and
  `v3_numerical_release.md` under `autoresearch-results/restart_audit/`.
- R1 reached its intentional terminal transition with four validated 2,000-ray
  anchors and no mask-ladder rows. The watcher interrupted the supervisor with
  status 130, then exited successfully. The deferred direct guard is now
  installed: both the old 640-case runner and Bosch-only S1 runner reject even
  manually constructed manifests under V3.
- V3 completeness correction (2026-07-13): the nine-factor Bosch recipe screen
  does not include `mask_ion_rate`. That coefficient is wired and controls a
  resolved-mask hard gate, but it is an uncalibrated simulator coefficient, not
  a fab selectivity setting. The fine full-width Gate-0 evidence establishes
  survival only through -0.04; R1 intentionally executed no mask-ladder rows.
  V3 Stage 2f now owns the bounded survive/fail search, four-seed confirmation,
  and shared-seed interactions with mask height, taper, and ion transport.
  Stage 2a must disclose this separation and cannot claim that all wired Bosch
  controls were screened.
- Stage 1 prelaunch audit (2026-07-13): the first implementation was not frozen
  after its focused tests passed. Independent review caught a fail-open
  numerical-release type check, missing runner-level duplicate lock, caller-CWD
  path splitting, an inherited pattern gate that incorrectly reused the etch
  +/-0.06 tolerance, asymmetric-taper curvature bias, incomplete three-level
  interaction reads, and unrecorded early-stop RNG consumption. The corrected
  Stage 1 measures surface CD at y=0 against the exact 0.30 pattern target with
  one grid cell of numerical allowance; five-percent, middle, and top CDs remain
  profile diagnostics. It uses type-strict release gates, repo-rooted paths,
  `flock`, transformed-coordinate curvature, full 3x3 additive residuals plus
  edge difference-of-differences, actual seed-prefix accounting, and drains all
  in-flight results after a failure. The complete 37-test stock-runtime suite
  passes after correcting one stale historical R1 test to separate immutable
  structural validation from disclosed post-run source drift.
- V3 Stage 1 launch (2026-07-13 12:19 +08): frozen manifest file SHA-256
  `714d896416ea89f733ca1c980d2cb25624d6d2356ba8114dff8d3421e431ff47`
  (canonical object SHA-256
  `319e8004682f73d9289566944827429fc9331c19656e959045cccac683d40138`)
  launched under `v3-pattern-skew-stage1-20260713`. It contains 27 full-width
  2D cases at grid 0.00125 and 2,000 rays per point, two seven-thread workers,
  shared reserved seeds 81000-81042, native per-case checkpoints, two supervised
  retries, and no LLM execution. Stage 2a remains unfrozen and unlaunched.
- V3 Stage 1 completion and review (2026-07-14): all 27 pattern-geometry
  cases completed on the first supervisor attempt with zero execution errors;
  all native checkpoints independently reloaded and validated. One case passes
  every pattern and etch gate: opening CD 0.30, mask height 0.30, taper 2
  degrees under the fixed reference Bosch recipe and the single shared random
  block. This is not a recommended recipe or robustness result. Opening CD
  moves marginal top, middle, and bottom etched CD by about 0.119, 0.126, and
  0.120 over the 0.24-to-0.36 skew. Taper creates engineering-visible,
  non-linear CD, bow, and sidewall-angle changes; the 2-degree marginal bow is
  lower than either tested edge. Mask height changes its own remaining height
  but promotes no etch-shape main effect because erosion was fixed at zero.
  Opening-CD-by-taper and other interaction signals remain confirmation
  hypotheses only. Durable rule: deliberately off-target geometry rows are
  useful effect evidence but their pattern-gate failures must not be described
  as process-yield estimates.
- Stage 2a noise-threshold correction (2026-07-14): the prepared independent-
  stream Bosch screen originally used numerical and practical thresholds but
  deferred stochastic variation. That violated the broad-first requirement to
  distinguish signal from simulator noise before ranking factors. The four
  disjoint released 2,000-ray nominal baselines are now used directly. For
  independent recipe contrasts, the stochastic component is conservatively
  `3*sqrt(2)*sample SD`; this raises the effective depth threshold to 0.12853,
  bottom-CD threshold to 0.03625, bow threshold to 0.01392, and sidewall-angle
  threshold to 1.20998 degrees. Four repeats are still a small baseline and
  promoted recipes require their own disjoint replication.
- V3 Stage 2a launch (2026-07-14 07:24 +08): the noise-aware 96-case Bosch
  manifest is frozen with file SHA-256
  `b8828cda21193e2f047bf29d206ab9b3657715a56a4851c7491c5caede14f6e1`
  and canonical SHA-256
  `cbb089dbd6f9ee95acd498b369be1c12786201252faab1c0a66747b12aab0eef`.
  It contains 50 exact anchors and 46 optimized space-filling recipes across
  nine Bosch controls, holds the Stage 1 all-gate nominal geometry fixed, uses
  96 non-overlapping RNG intervals, and runs two seven-thread workers. The
  first identical launch was stopped before producing a row because its
  supervisor was attached to the Codex process; that interrupted log is kept.
  The accepted run is detached in screen session
  `viennaps-v3-pattern-bosch-stage2a-final-20260714` and uses no LLM.
- Stage 2a cadence correction (2026-07-14): waiting for all 96 independent-
  stream cases before the first decision would take about six days at the
  observed two-case throughput and would repeat the monolithic-autoresearch
  mistake. Before any favorable full-matrix result existed, the first 19
  frozen rows were designated as the adaptive analysis checkpoint: nominal
  plus exact low/high anchors for each of the nine Bosch factors. A detached
  watcher requests a supervised stop at 19 written rows. The remaining exact
  interaction anchors and space-filling cases are not discarded; they require
  authorization from the 19-row broad effect read. The first two completed
  anchors are physically coherent: nominal passes at depth 1.2443, maximum CD
  error 0.0361, and bow 0.0160, while etch_time 0.2 reaches only depth 1.0653
  after all 30 cycles and fails depth and CD-profile gates. This is a lower
  reachability boundary, not an optimum or a complete factor ranking.
- Stage 2a 19-anchor effect review (2026-07-15): all nominal plus low/high
  Bosch anchors are valid, but they are an OFAT prioritization checkpoint, not
  a completed interaction DOE. Relative to the conservative independent-stream
  noise thresholds, `etch_time` and `deposition_thickness` are dominant
  reachability controls; some extreme endpoints cannot support depth-matched
  morphology contrasts and must be labeled boundary evidence rather than a
  missing effect. Among depth-matched contrasts, `ion_source_exponent`,
  `ion_rate`, and `neutral_rate` produce the largest multi-output morphology
  changes. `neutral_sticking_probability` is promoted because it moves middle
  CD by 5.15 thresholds and sidewall angle by 2.72 thresholds despite weaker
  bow and cycle effects. `initial_etch_time`, `theta_r_min`, and
  `deposition_sticking_probability` are held nominal in the first reduced
  combined DOE, not permanently rejected; the passivation-thickness-by-
  sticking interaction remains a separate physical challenge. Durable rule:
  rank factor changes against per-output noise and keep reachability failures
  visible before reducing the factor set; do not interpret an unavailable
  depth-matched contrast as zero sensitivity.
- Cheap Bosch screening qualification launch (2026-07-15): a separate frozen
  16-simulation campaign now tests whether 500 rays can preserve the broad
  ranking already observed at 2,000 rays. It contains nominal plus low/high
  anchors for the six promoted controls (`etch_time`, passivation thickness,
  ion directionality, ion rate, neutral rate, and neutral sticking) and three
  additional nominal repeats. Grid 0.00125 and the 2D domain are unchanged;
  early stopping is reduced from depth 1.45 to 1.36, after the upper 1.35 spec
  edge. Two seven-thread workers write a separate JSONL ledger and native
  checkpoints under campaign `v3-bosch-cheap-qualification-20260715`. The
  combined interaction DOE is blocked unless this qualification preserves
  large-effect directions, strong-factor retention, and reachability-boundary
  classifications. Existing Stage 2a artifacts are immutable inputs and were
  not overwritten or deleted.
- Cheap Bosch screening qualification result (2026-07-15): all 16/16 cases
  completed in 3 h 20 min with valid metrics and no retry. Relative to the
  preserved 2,000-ray anchors, the 500-ray mode matched all 13 anchor hard-gate
  decisions, all trajectory classes, and the direction of all 27 reference
  effects that exceeded their effective thresholds. All six promoted factors
  remained screen-positive; their composite ordering had Spearman correlation
  1.000, and all four cheap nominal repeats passed. Median paired runtime
  speedup was 4.47x. Therefore 500 rays is qualified only for broad interaction
  discovery on this fixed 2D Bosch problem. It does not carry product-gate,
  recipe, process-window, or confirmation authority; promoted interactions and
  finalists still require 2,000-ray independent confirmation. This was a
  research-efficiency result, not a process-recipe improvement.
- Cheap Bosch interaction discovery result (2026-07-16): all 28/28 exact
  interaction corners completed on the first supervised attempt; eight pass
  every Bosch hard gate and 14 eligible difference-of-differences contrasts
  exceed the conservative interaction thresholds. Etch-time-by-passivation-
  thickness has no feasible extreme corner and strong depth/cycle interaction,
  so both factors must be refined inward rather than optimized at an edge.
  Low etch time is rescued by stronger ion or neutral removal, confirming dose
  compensation. Neutral rate by neutral sticking is a crossed interaction:
  high/low and low/high pass while both matching extremes fail, with a 7.54-
  threshold maximum-CD-error contrast. Ion directionality by ion rate is also
  material: the lower-magnitude ion-rate setting passes at either directionality
  extreme, while aggressive removal creates CD/bow failures; the maximum-CD-
  error and bow contrasts are 7.04 and 2.53 thresholds. Strong directionality
  rescues thin passivation, but thick passivation remains reachability-limited.
  Durable rule: do not refine the rejected extreme corners. Use transformed
  half-steps between each low/nominal/high anchor for the interior response
  surface, then confirm only promoted interior candidates at 2,000 rays.

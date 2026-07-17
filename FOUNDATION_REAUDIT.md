# TSV traveler foundation re-audit

Status: in progress. The 1,948-run campaign is preserved as phase-one evidence,
but its fill ranking, CMP ranking, response-surface claims, and final recipe are
not accepted inputs to a new DOE.

## Confirmed problems

1. **The target geometry is not yet representative of the stated high-AR
   via-middle case.** The executable target is 0.30 wide and 1.25 deep, AR
   4.17. A published via-middle example is 3 µm wide and 50 µm deep, AR 17.
   Aspect ratio is dimensionless, so model-unit scaling does not resolve the
   difference. Source: [3 µm via-middle TSV reliability study](https://www.sciencedirect.com/science/article/pii/S016793171630034X).
2. **The tested ranges are not physically calibrated.** They are ViennaPS
   coefficients selected from defaults and previous simulations. Until a
   mapping to tool inputs or measured geometry exists, they are model
   sensitivity ranges, not realistic fab recipe ranges.
3. **The legacy fill quantity has disputed semantics.** It measures the center
   surface height above the via floor. On analytic geometry it is zero at the
   floor and increases as the surface rises. A fixed-geometry dose series
   confirms that direction. Whether it represents a useful fill-front quantity
   remains open; it is not accepted as a residual void gap.
4. **Outer-surface metrics cannot prove void-free fill.** Raw Cu level-set
   meshes develop disconnected internal components at larger doses. A topology
   metric and visual/raw-mesh agreement are required.
5. **CMP failure modes were collapsed.** `IsotropicProcess(rate=-1.0)` applies
   one negative velocity to all materials. Some rows remove mask, Cu, oxide,
   and silicon, yet were recorded only as mask consumption. ViennaPS supports
   masked or material-specific rates; the one-rate default was the wrong basis
   for physical CMP claims. Source: [ViennaPS isotropic process](https://viennatools.github.io/ViennaPS/models/prebuilt/isotropic.html).
6. **The old fill/CMP pair does not reproduce the intended process
   morphology.** A via-middle traveler should leave a void-free copper plug
   plus copper overburden after electroplating, then selectively clear the
   overburden without erasing the via, dielectric, or silicon. The supplied
   [HBM via-middle process illustration](https://x.com/zephyr_z9/status/1995148359795916981)
   is useful as a qualitative sequence check: its fill and CMP panels are not
   what the current constant-velocity fill plus one-rate isotropic removal
   produces. The illustration is not calibration evidence; the underlying
   mechanisms still require primary sources and executable acceptance tests.
7. **The existing outer-envelope extraction is not a valid CD-depth
   measurement.** `profile_points()` bins by x and keeps only the highest y.
   That is useful for the vacuum-facing top envelope, but it discards most
   nodes on a nearly vertical via wall. Direct inspection of the raw silicon
   level-set mesh retains the missing wall. Etch depth profiles, top/mid/bottom
   CD, taper, bow, and scallop must therefore use the raw silicon boundary.
8. **The legacy liner/barrier coverage proxy is directionally wrong.**
   `floor_reach_metric(y_before, pts_after)` returns 1.0 when the floor does
   not move at all. For a floor at -1.25, a +0.020 film returns 0.984. It
   therefore rewards no deposition and penalizes deposited thickness; the
   phase-one liner and barrier pass labels are not physical coverage evidence.
9. **Pattern was scored from requested constants rather than measured
   geometry.** `score_steps()` inserts radius 0.15, width 0.30, and mask height
   0.30 without measuring the generated opening. Pattern passes in phase one
   do not demonstrate a metric check.
10. **Etch width and bulge were not independent outputs.** `width_error()` is
    exactly `2 * wall_bulge()`, and its 0.06 limit is exactly twice the 0.03
    bulge limit. The two gates are redundant. Raw-boundary CD-versus-depth must
    replace the claimed independent width measurement.
11. **The main campaign is a 2D trench surrogate, not a cylindrical TSV
    simulation.** The module fixes ViennaPS to 2D. ViennaPS documents that a
    2D `MakeHole` corresponds to a trench, whereas a 3D hole is cylindrical.
    Phase-one fill topology and curvature claims therefore cannot be promoted
    to a 3D TSV without a quantified 2D-to-3D discrepancy study. Source:
    [ViennaPS MakeHole geometry](https://viennatools.github.io/ViennaPS/geo/basic/hole.html).
12. **Several claimed effects are at or below credible grid resolution.** At
    grid delta 0.01, the 0.020 liner is two cells, the 0.012 barrier is 1.2
    cells, and a roughly 0.014 bulge is 1.4 cells. Minimum thickness,
    continuity, and small-bulge conclusions require grid convergence or a
    rescaled/finer domain.
13. **The current Cu process is a geometric directional emulation, not
    electrofill.** It applies one constant directional velocity plus a fixed
    isotropic fraction for unit duration. It contains no current/potential,
    Cu-ion transport, suppressor, accelerator, leveler, coverage state, or
    curvature feedback. More `fill_thick`/`fill_iso` sampling cannot turn this
    model into superfill. Source: [ViennaPS DirectionalProcess](https://viennatools.github.io/ViennaPS/models/prebuilt/directional.html).
14. **The missing fill mechanism required an explicit physical case.** CEAC
    describes accelerator area compression in smaller features. Primary NIST
    work identifies suppressor breakdown and S-shaped negative differential
    resistance (S-NDR) as important for micrometre-scale TSV bottom filling.
    The study now separates the old AR-4.17 continuity case from a mapped
    5 um x 50 um nominal case and 3 um x 50 um stress case. This supports a
    reduced suppressor-breakdown first hypothesis, while all kinetic inputs
    remain uncalibrated model coefficients. It is not an S-NDR result unless
    the characteristic electrochemical response or a published limiting case
    is reproduced. Source: [NIST TSV electrochemistry](https://www.nist.gov/programs-projects/electrochemistry).
15. **The material stack is conflated.** Barrier/seed is tagged as Cu, and the
    bulk fill is another Cu level set. TaN/Ta barrier loss, seed continuity,
    bulk-Cu topology, and material-selective CMP cannot be independently
    measured until the layers are represented and identified separately.
16. **Mask identity and lifetime are physically inconsistent.** The modeled
    mask is described as photoresist, never stripped after DRIE, receives every
    downstream film, and must survive CMP. The hard survival gate remains in
    force, but the implementation must explicitly distinguish temporary resist
    from a durable hard mask or CMP stop layer rather than silently carrying
    photoresist through the traveler.
17. **The claimed unseen seeds were not controlled simulator seeds.** The DOE
    seed randomizes recipe construction; replicate IDs are not passed to a
    ViennaPS RNG. Phase-one repetitions are fresh stochastic executions, but
    they are not reproducible unseen-seed confirmation until simulator RNG
    state is explicitly controlled and recorded.
18. **The CMP stop plane was not physically measured.** `target_y` is the
    global maximum of the liner outer envelope, not a declared field stop-plane
    statistic. CMP endpoint, residual field Cu, and overpolish cannot be
    interpreted until the stop layer and field ROI are explicit.

## Minimum useful CTQ set

The product and step specifications remain fixed. These measurements explain
whether and why a process meets them without creating an unmanageable metric
catalog.

| Step | Essential intermediate outputs |
|---|---|
| Pattern | opening CD, mask height, mask taper |
| Bosch DRIE | depth; top/middle/bottom CD; taper angle; maximum bow; scallop/roughness |
| Liner | minimum local thickness; bottom/field and lower-wall/field conformality; thickness non-uniformity; continuity; remaining aperture |
| Barrier/seed | minimum local thickness; bottom/field and lower-wall/field conformality; continuity; remaining aperture |
| Cu fill | internal void/seam; fill height; positive and sufficiently uniform overburden; no mouth pinch-off |
| CMP | residual field Cu; endpoint reached; dish; stop-layer erosion; plug-height loss; Cu plug, liner, and substrate preserved |

For DRIE, CD-versus-depth is the primary profile. A fitted large-scale line
gives taper, deviation from that line gives bow, and the short-period residual
gives scallop/roughness. These quantities must not be collapsed into one
generic width error.

## Screening-design audit

The G003 screen used 128 unique recipes over 17 factors and four stochastic
repeats per recipe.

- A categorical main-effect model needs 76 columns including the intercept.
  The generated 128-recipe matrix has rank 76, so main effects are estimable in
  principle.
- The design is balanced random sampling, not orthogonal. Recalculation from
  the 128 unique raw recipes gives a largest ordinal-index pair correlation of
  0.2092 (`mask_taper` versus `theta_r_min`) and a largest raw-value Pearson
  correlation of 0.2297 (`neutral_sticking_probability` versus `fill_iso`).
- Pair-level cells are mostly visited (minimum observed coverage 39/42, or
  92.86%), but
  most cells have too little independent recipe coverage to identify nonlinear
  interactions.
- A full quadratic model for 17 continuous factors already needs 171
  coefficients before replication. The 128 unique recipes cannot estimate that
  surface.
- All 128 G003 recipes have distinct upstream factor tuples. Consequently,
  `--shared-upstream` did not create cross-recipe shared geometry in that
  broad screen, although later local combination blocks did reuse geometries.
- Therefore G003 can be retained only as an exploratory main-effect screen
  under its old metrics. It cannot support claims that most of the response
  surface or important interactions were covered.

## Installed model options and boundaries

- `DirectionalProcess` is only a constant-vector geometric emulation.
- `MultiParticleProcess` exposes ray flux and material to its rate function,
  but not position, curvature, surface coverage, or history.
- `SingleParticleALD` contains evolving adsorbate coverage but not CEAC area
  compression, suppressor competition, or TSV S-NDR kinetics.
- The installed Python bindings cannot compose a custom ViennaPS surface model
  and velocity field; official custom model composition is C++ only. A
  low-level `viennals.VelocityField` can serve as a clearly labeled morphology
  positive control, followed by one narrow bound C++ superfill model. Source:
  [ViennaPS custom models](https://viennatools.github.io/ViennaPS/models/custom/).
- Copper superfill requires coverage/transport physics. CEAC is a candidate
  for the appropriate scale; TSV-scale S-NDR is a competing hypothesis that
  must be resolved from the physical case. Sources: [NIST CEAC paper](https://www.nist.gov/publications/superfilling-when-adsorbed-accelerators-are-mobile),
  [NIST spatiotemporal TSV model](https://www.nist.gov/publications/spatial-temporal-modeling-extreme-bottom-filling-through-silicon-vias).
- `Planarize` is an exact geometric height cut, useful as an ideal endpoint and
  metric control, not a CMP physics model.
- `IsotropicProcess` supports material-specific rates but remains normal-rate
  and topography/pressure blind.
- `CSVFileProcess` can apply position-dependent velocity and masking, enabling
  a phenomenological height-weighted CMP prototype. A Python interpolator
  forces single-thread execution and is not calibrated contact mechanics.
- CMP dishing depends on local pressure distribution, material selectivity,
  pad properties, pattern geometry, and polishing conditions. Source:
  [contact-mechanics CMP model](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/5190AA6FCFAD44D56EBF6DCA47CA7E15/S1946427400620912a.pdf/contactmechanics_based_model_for_dishing_and_erosion_in_chemicalmechanical_polishing.pdf).

## Required morphology sequence

The next implementation must demonstrate this sequence on raw material
profiles before it is eligible for a DOE:

1. Etch creates an open, depth/width-qualified silicon via.
2. Liner and barrier/seed remain continuous from field to bottom without
   closing the opening.
3. Copper grows bottom-up, contains no sealed internal void, reaches the field,
   and intentionally forms measurable overburden.
4. CMP clears field copper and stops in a physically declared stack while the
   copper plug, dielectric, and silicon remain.

The CMP audit must distinguish bulk clearing from post-endpoint overpolish.
Before endpoint, raised Cu is the primary removal target. After field Cu first
clears, continued removal is an explicit overpolish interval with declared
Cu/barrier/dielectric selectivity and stop-layer loss. This staged abstraction
must be tested before considering a full pad-contact implementation.

The TCB/NCF stack illustration supplied alongside the via-middle diagram is
downstream packaging context. It is not part of this six-step TSV formation
traveler and must not be mixed into its pass/fail score.

## Controlled results after the reset

- The first CTQ block completed 88/88 unique valid cases. Explicit seeds
  reproduce meshes within floating-point reduction order, and seven versus 14
  ViennaPS threads changes a fixed-seed mesh by at most 8.9e-16.
- Grid delta 0.01 is rejected. Against paired 0.005 runs it shifts DRIE depth
  by mean absolute 0.03371, 8.2 baseline stochastic standard deviations.
- The completed 0.0025 extension changes the profile much more: paired mean
  absolute shifts are 0.15513 depth and 0.06237 bottom CD. Depth passes 0/8,
  CD 5/8, and bow 3/8. Minimum lower-boundary clearance is only 0.01722 (6.9
  cells), which initially raised a boundary-risk hypothesis.
- That boundary hypothesis is rejected by a four-case controlled repeat.
  Vertical extents 1.5, 2.0, and 2.5 reproduce depth, top/middle/bottom CD,
  maximum CD error, bow, scallop RMS, and sidewall angle within a maximum
  absolute difference of 4.4e-15 for the two shared seeds. The large 0.005 to
  0.0025 shift is intrinsic to repeated-cycle resolution/passivation behavior,
  not clipping by the lower domain boundary. Extent 2.0 is retained for ample
  clearance in the high-fidelity audit.
- The old fill-dose range was structurally incapable of testing closure. It
  stopped at 0.26 for a 1.25-deep via. The unchanged directional control
  reaches the field near dose 1.25 and positive center overburden near 1.4,
  disproving the prior zero-gap-ceiling conclusion. It also leaves about 1.25
  field-to-center relief, so it is not a practical electrofill recipe.
- Analytic metrics now classify local film thickness/conformality/continuity,
  open and sealed fill voids, overburden, CMP endpoint, adjacent residual
  films, dish, erosion, stop loss, and substrate loss.
- On a controlled stack, `Planarize` is a clean ideal CMP endpoint. The old
  one-rate 0.30 removal consumes a 0.03 stop and more than 0.10 of substrate;
  this is destructive indiscriminate removal, not normal overpolish.
- A full-2D analytic CMP harness now separates residual plated Cu, seed, TaN,
  stop erosion, protected-layer continuity, plug connection/loss, substrate
  loss, dish, and protrusion. Its native controls and synthetic failure
  fixtures pass. An isolated C++ `HeightMaterialCMP` velocity field now supplies
  height and material identity continuously; its exact binding and source
  qualification pass, while its metadata correctly says pad-pressure physics
  is absent. This removes the API blocker but not the scientific one. No
  endpoint/window or numerical campaign has run, the metric still needs
  adversarial disconnected/malformed-geometry and functional-loss guards, and
  no qualified physical fill supplies the incoming plug. No CMP response
  surface is authorized.
- A 20-case single-cycle passivation audit accepts grid 0.00125 against an
  eight-cell 0.000625 anchor: paired depth, bottom-CD, and bow shifts are
  0.000678, 0.000149, and 0.000214, respectively. It is the focused
  high-fidelity 2D grid; broad-screen fidelity remains to be selected after
  the focused full-cycle cycle-history audit.
- The full-cycle recovery is complete. Four valid unique seeds and one
  preserved serialization failure support cycle 13 as the only common
  depth/CD/bow pass. Its depth spans 1.22306 to 1.31083; cycles 12 and 14 pass
  depth for only 3/4 and 2/4 seeds. This freezes a downstream checkpoint, not
  a broad cycle-count process window.
- Fill topology now requires a full 2D cross-section. Secondary below-field
  open components are invalid seam/mesh defects, so both a synthetic seam and
  a symmetry-clipped trapped void fail instead of being labelled void-free.
  The metric also retains open/trapped void area, post-seed-cavity fill
  fraction, mouth aperture, pinch-off history, overburden, and a grid-dependent
  detection limit. These responses do not establish metallurgical seam quality.
- The reduced `CopperSuppressionFill` candidate passes isolated algebra,
  parameter, material-gating, seed-handoff, determinism, and equilibrium
  checks. A required `ignoreVoids=true` advection guard prevents an inaccessible
  trapped-void surface from reactivating and healing numerically. Matched
  convex/concave controls also pass the intended access/coverage/rate ordering.
  The first morphology blocks do not pass: 24 checkpoint-refinement and eight
  grid-refinement cases all create a long sub-resolution centerline merger.
  Exact mesh-width review classifies this as unresolved seam risk, correcting
  the earlier depth-only claim of impossible cavity motion. The clean 32-case
  identifiable access/coverage surface has no accepted pass. All higher-
  sticking points fail; lambda 1 and 2 at sticking 0.05 remain open but are
  time-censored. A prelaunch audit then found that consecutive replicate bases
  overlap when the runner uses `base_seed + checkpoint`, so the earlier
  two-seed uncertainty language is withdrawn. The corrected 72-case expansion
  over lambda 0.5 to 1.25 and sticking 0.025 to 0.1 used four bases spaced by
  1,000 across its 320-checkpoint horizon. Every row fails before duration 8;
  none is censored. Increasing lambda at sticking 0.025 delays failure and
  raises area fill toward 0.79, but the worst-stream floor advance remains only
  0.0915 of a 1.25-deep via. This is a replicated sidewall-closure regime, not
  bottom-up superfill. An exact-stack structural challenge then rejects the
  candidate law at grid 0.01 and 0.005 while a prescribed bottom-up control
  reaches void-free positive overburden at both grids without moving the
  protected stack. The topology representation can pass; the current law
  cannot. Independent review blocked the first transport-sign draft because
  it omitted the nominal HBM tier, allowed cross-design evidence mixing, used
  a narrow analytic coefficient range for a no-go decision, and incompletely
  froze its manifest. No 3D confirmation or physical calibration yet
  authorizes a production DOE.
- Its corrected 168-case replacement uses paired continuity and nominal-HBM
  geometries, seven sticking levels, three source powers, and four disjoint
  common ray streams. All rows and snapshots are valid, but every design fails
  the regional floor-versus-wall sign gate in both tiers. The best coarse miss
  is sticking 0.025 / sourcePower 0: worst flux ratios 1.002 and 1.021 versus
  less than 0.95, and velocity ratios 0.998 and 0.957 versus greater than 1.05,
  for continuity and nominal HBM. Both the required coefficient grid and a
  broad analytic envelope have zero cross-tier H/a passes. The accepted
  conclusion is only that numerical and boundary confirmation is required;
  grid/ray/reflection and matched-3D gates still block a model-family pivot.
- The 128-cell numerical confirmation is complete with 128 valid cells, eight
  exact parent reuses, and 120 new executions. Grid, ray-count, and reflection
  effects create no class-changing interaction. At grid 0.005, 2,000 rays, and
  maxReflections 800, lowering sticking from 0.025 to 0.0125 improves the worst
  cross-tier flux ratio from 1.01504 to 0.99297. The 0.02207 gain exceeds the
  largest paired numerical effect or interaction, 0.01671, so the boundary
  trend survives the numerical challenge. It still fails: both designs pass
  0/8 transport streams, and the lower-sticking worst velocity ratio is only
  1.00298 versus the required value above 1.05.
- The first reviewer-required 0.00625 design was rejected before launch because
  `maxBoundaryHits=1000` was lower than maxReflections 1,600/3,200. That would
  invalidate the claimed termination residual and confound the comparison with
  historical 0.0125 rows. The corrected 24-cell campaign uses
  `maxBoundaryHits=6400` throughout and includes eight new matched-cap 0.0125
  controls rather than reusing the historical cap-1,000 rows.
- The corrected boundary confirmation is complete with 24/24 newly executed,
  metric-valid cells. At sticking 0.00625, the 1,600- and 3,200-reflection arms
  have the same no-go class and zero paired change across all four reported
  responses. Both arms pass 0/8 combined transport streams. Their worst
  floor/lower-wall flux ratio is 0.988828 versus the strict target below 0.95;
  their worst velocity ratio is 1.004256 versus the strict target above 1.05.
  Every paired flux stream improves from the matched-cap 0.0125 control, but
  the worst-response improvement is only 0.004147, below the predeclared
  0.016714 continuation threshold. The apparent lower-sticking trend therefore
  does not continue strongly enough to justify another 2D boundary expansion.
- The accepted decision is
  `two_dimensional_transport_no_go_requires_matched_3d_before_pivot`.
  Morphology, automatic lower-sticking expansion, model-family pivot, and
  terminal physical claims remain blocked. The next decision experiment is a
  frozen, independently audited, matched 2D-versus-3D transport bridge for the
  capped 0.0125 control and reflection-converged 0.00625 miss; it must compare
  gate class, effect direction, and margin on the same normalized geometries
  and paired transport streams before the candidate model family is retained
  or replaced.
- The initial 10-case layer block was complete but not numerically qualified. At the
  baseline, liner minimum thickness is 0.03433 versus 0.020, while floor/field
  and lower-wall/field conformality are 0.87115 and 0.85900 versus 0.995.
  Combined barrier/seed minimum is 0.004797 versus 0.012. All resolved
  interfaces remain continuous and open. Its predeclared, fingerprinted
  12-case replacement now passes every one of 14 maximum-delta checks for grid
  0.00125 versus 0.000625 and 2,000 versus 4,000 rays per point across four
  shared seeds, with no gate changes. This authorizes exploratory layer-factor
  screening, not final recipe acceptance or physical calibration.
- The extension is reproducible from ViennaPS commit
  `2956ed587984c6dc38be24c6e2390e10c9b2f0a7` using patch SHA-256
  `c0791af6f28a7e5214064f9e914f6c7c665e1c61ed730bc81caf7f097edd0d81`
  and `scripts/build-viennaps-copper-suppression-fill.sh`.

## Evidence still required

- Qualify the declared 5 um x 50 um nominal and 3 um x 50 um stress geometry
  mappings; geometry selection is explicit, but process coefficients and
  tolerances still require calibration.
- Quantify 2D trench versus 3D cylindrical-via discrepancies. Use 2D only as
  a screened surrogate for outputs whose discrepancy is acceptably bounded;
  confirm critical fill/CMP behavior and finalists in 3D.
- Establish tolerances instead of exact floating-point equality where justified.
- Validate fill height, remaining target-plane deficit, and void topology on
  analytic and simulated geometries.
- Require a minimum overburden state before CMP; a low or recessed fill front
  is not a successful fill merely because a legacy scalar is small.
- Validate local layer thickness and conformality against raw nested material
  boundaries; the legacy floor-position proxy is not accepted as thickness.
- Measure the generated pattern rather than copying its requested constants
  into the score.
- Separate CMP field clear, mask loss, Cu loss, substrate loss, and empty-domain
  outcomes.
- Assign range provenance to every factor before choosing a new DOE.
- Record ViennaPS package 4.6.1, local source commit
  `2956ed587984c6dc38be24c6e2390e10c9b2f0a7`, extension patch/hash, and
  explicit RNG policy in every new artifact.
- Choose the new unique-recipe count from the response model to be estimated,
  with independent lack-of-fit points and controlled, recorded stochastic
  confirmation.

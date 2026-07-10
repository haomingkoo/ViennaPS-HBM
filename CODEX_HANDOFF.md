# Handoff prompt — paste this to Codex

You're picking up work on `~/ViennaPS-HBM`, a ViennaPS (TU Wien topography
simulator) demo of real via-middle TSV manufacturing (HBM4/HBM4E), built
for an MTS (Member of Technical Staff) interview. Read `CLAUDE.md` first —
it points you to `program.md` (fixed objective + product spec), `train.md`
(what's fixed vs. varied), `prepare.md` (evaluation methodology + a
numbered running log of every finding, including retracted ones). Read
all three before touching anything. They are the source of truth, not
this handoff — this handoff is just orientation.

## What this project actually is

Not "run a simulation," but "use data to find out what controls the
outcome, catch mistakes along the way, report an honest result." The
whole point is the discipline: screen every real parameter → combined
DOE on the ones that matter → depth-match and replicate before trusting
a result → retract claims that don't survive replication. Two claims
got made and retracted on-page during this project (CMP dishing
direction, a patterning-taper trade-off) — that's a feature, not
something to clean up.

## Where things live

- `tsv_process.py` — core simulation module (etch/liner/barrier/fill/CMP)
- `build_notebook.py` → generates `tsv_traveler.ipynb`
- `build_explainer_data.py` (runs real ViennaPS sims) + `build_explainer.py`
  (assembles template + data) → generates `explainer.html` from
  `explainer_template.html` + `explainer_data.json`
- `README.md` — findings summary; `program.md`/`train.md`/`prepare.md` —
  the autoresearch loop docs
- Repo: `git@github.com:haomingkoo/ViennaPS-HBM.git` — **direct pushes to
  `main` are established practice for this repo**, no PR needed
- Live demo: `https://kooexperience.com/ViennaPS-HBM/explainer.html`,
  auto-deployed via GitHub Pages from `main` (already enabled, nothing to
  set up)

## Current verified state (as of this handoff)

- **Etch production recipe**: `etch_time=0.5, neutral_sticking_probability=0.05,
  initial_etch_time=0.3, neutral_rate=-0.1, ion_source_exponent=200,
  deposition_thickness=0.01`, **14 cycles**. Found via screening all 11
  real etch parameters (not just the original 4), then an 800-run
  combined DOE on the top-4, depth-matched and replicated (~1.5x better
  wall bulge than the old recipe). This is what `tsv_process.py`'s
  defaults and the notebook/explainer currently use.
- **Liner/barrier/fill**: comprehensively DOE'd, confirmed near-optimal —
  **except** a newer, wider fill sweep (thickness down to 0.10, iso_ratio
  down to 0.01) found `thickness=0.14, iso_ratio=0.01` gives tip_gap
  ≈0.096-0.156 (depending on exact geometry state), better than the
  notebook's current "production" 0.18/0.05 (~0.19 gap). **Not yet
  adopted** — flagged in the explainer's own caption as an open finding,
  not a verified winner. This is the most concrete next task (see below).
- **CMP**: real structural ceiling. Nominal overburden leaves severe
  dishing; fixing it requires enough extra removal to fully consume the
  mask. Documented, not a tuning gap.
- **Fill tip-gap**: never reaches the 0 (ideal) spec at any tested
  setting — a genuine miss against the product spec in `program.md`, a
  CEAC/curvature-limited-chemistry ceiling that `DirectionalProcess`'s
  constant-direction model can't represent.
- **Patterning mask-taper "trade-off"**: retracted. First pass (1 run
  each) claimed taper=0 wins on etch bulge, taper=4 wins on fill
  tip-gap. Replicated properly (6-10 runs): the tip-gap half of the
  claim didn't hold (ranges overlap almost completely). What's real:
  taper=4 gives a near-zero-variance bulge every run; taper=0 gives a
  genuinely bimodal distribution. A numerical-stability finding, not a
  "better via" finding.
- **explainer.html**: fully redesigned as a dark instrument-panel /
  numbered findings-log document (not a marketing webapp) per explicit
  user pushback that the first version read as "AI slop." Has a stated
  product-spec table, a screening-DOE bar chart, two interactive
  explorers (etch: 4 real sliders, 63-point real grid on the primary 2;
  fill: 2 real sliders, 100-point real grid), and honestly-labeled
  retractions.

## Hard-won methodology lessons — do not repeat these

1. **Depth-match before comparing any bulge/quality metric.** A
   shallower via trivially shows less bulge. This mistake happened 3
   times in this project before being caught (prepare.md items 3, 7, and
   once in the explainer's FAIL-vs-PRODUCTION panel). The product spec
   in `program.md` exists specifically so every comparison has one
   target depth (1.25 ± 0.1) to match against.
2. **Etch has real Monte Carlo noise; fill/barrier deposition does
   not.** `bosch_etch` uses a ray-traced `MultiParticleProcess` — running
   the *exact same parameters* twice gives different results (confirmed:
   depth varying ~1% run to run). `DirectionalProcess` (fill, barrier)
   is fully deterministic given a fixed input geometry. Never trust a
   single etch-derived comparison; replicate 5-10x. A "controlled"
   comparison across parameter values must build the base (etched)
   geometry **once** and `deepCopy` it per variant — regenerating a
   fresh etch per comparison arm silently reintroduces this noise as if
   it were a real effect (this happened twice in this project: the
   direction-angle finding, and the first version of the joint 5-step
   sweep — both had to be redone).
3. **`profile_points()`'s output order is the real contour trace — never
   re-sort it by x.** This was the root cause of an hours-long rendering
   bug hunt in the explainer: re-sorting profile arrays by x before
   plotting/trimming destroys the coherent trace wherever a real lobe,
   overhang, or pinch-point exists, manufacturing fake spikes that look
   like debris but aren't. Always filter by y (`points[points[:,1] <=
   y_ceiling]`), never sort-then-reconnect. The notebook's own
   `trim_for_display` already does this correctly — copy that pattern,
   don't reinvent one.
4. **Sweep scripts need exception handling + incremental checkpointing.**
   Some parameter corners are genuinely non-functional recipes (net
   deposition instead of net etch) and will trip `bosch_etch`'s own
   sanity assertion. That's a real, useful finding — catch it (`except
   AssertionError`), record `bulge=None`, keep going. Save results every
   N iterations, not just at the end, or one bad corner loses the whole
   run (happened once, cost ~43 min of compute).
5. **A screening pass (one-factor-at-a-time) can mis-rank parameters
   that interact.** It's a legitimate cheap first pass, but the full
   combined DOE is what determines the real ranking — don't stop at the
   screen's ranking.
6. **Before trusting a boundary optimum** (a winner sitting at the edge
   of the tested range), test beyond it. Two real findings in this
   project were boundary optima that turned out to be genuine local
   optima when checked (etch_time=0.5), and one wasn't fully checked
   until this handoff (fill thickness/iso_ratio — see next section).

## Concrete next tasks

1. **Verify or reject the new fill finding properly.** `thickness=0.14,
   iso_ratio=0.01` looked better in a wider sweep. Before calling it a
   new production recipe: (a) replicate it (fill is deterministic given
   a fixed base geometry, so this is really about confirming the
   measurement, not noise), (b) check it isn't *also* a boundary optimum
   — push thickness below 0.10 and iso_ratio below 0.01 and see if the
   trend keeps improving or turns around, (c) only then update
   `tsv_process.py`'s notebook-facing constants, `build_notebook.py`'s
   `FILL_SUPERCONFORMAL`, README, and the explainer's "production"
   labels/defaults together, consistently.
2. **Consider whether liner/barrier deserve the same wider-range
   re-check** now that fill's "already near-optimal" conclusion turned
   out to be wrong once a wider range was actually tried. Don't assume;
   check.
3. **Extend the explainer's interactive explorers to liner/barrier/CMP**
   if the user asks for "more sliders" again — currently only etch and
   fill have interactive explorers; liner/barrier/CMP only have static
   before/after panels. (User has repeatedly pushed for more
   interactivity and denser real-data grids, not interpolation.)
4. **Check the task list** in this session's tracker (tasks #11-22 were
   created/completed across this project) — most are done, but verify
   state rather than assume.

## Working style this user expects (learned the hard way this session)

- **Extremely low tolerance for verbose/hedging text.** Said "so
  verbose" and "i don't like verbiage like as if you are hedging"
  multiple times. Keep prose terse; let the work speak.
- **Wants real, verified numbers — will push back hard on anything that
  looks synthetic, interpolated, or approximated.** Multiple rendering
  "fixes" got rejected because they substituted synthetic shapes for
  real simulated data; the fix that finally worked was going back to
  the real data and finding the actual bug in how it was being handled.
- **Explicitly said not to be conservative with compute** ("i have the
  cpu/gpu, why are you so conservative") — run wide, dense sweeps
  rather than small illustrative ones.
- **Rejects generic "AI-generated" design/writing.** The explainer went
  through a full visual redesign after being called "AI slop" — the
  fix was a distinctive, subject-grounded visual identity (dark
  instrument-panel palette tied to the real plasma-etch physics), not
  just polish.
- **Verify visually, not just numerically**, for anything rendered —
  screenshot and actually look at it before claiming a fix works. Several
  "fixes" in this session looked correct in the data but were visibly
  wrong (spikes, blank renders, disconnected shapes) until actually
  screenshotted and inspected.

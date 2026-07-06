# ViaForge -- HBM4/HBM4E TSV Process Simulation

A [ViennaPS](https://github.com/ViennaTools/ViennaPS) simulation of the
via-middle TSV process loop used in HBM manufacturing, run end to end in
[`tsv_traveler.ipynb`](tsv_traveler.ipynb), with a 768-run 4-parameter DOE
on the etch step and swept-optimal downstream parameters (not formulaic
guesses) for every following step.

Also see the standalone interactive explainer: [`explainer.html`](explainer.html).

## Where this fits in the real process

The via-middle TSV flow has 4 phases (per the "TSV Formation: Via Middle
Process for HBM DRAM" diagram shared for this project): **Phase 1**
pre-processing (FEOL: transistors built), **Phase 2** the TSV formation
loop (pattern -> Bosch etch -> liner -> barrier+seed -> Cu fill -> CMP --
this is what this repo simulates), **Phase 3** BEOL (back-end metal
wiring), **Phase 4** backside reveal (carrier bonding -> backgrinding ->
silicon etch reveal -> passivation+bumping -- this is the "'Through' step"
where a blind via becomes a real through-via).

Two corrections worth being explicit about, since they came up during
this project and are easy to get wrong:
- **TSVs are formed at the wafer level** (every die on a wafer, in one
  batch process) *before* dicing and stacking -- not one die etched
  individually as a standalone action, and not after the dies are
  already stacked (that's a different, less common approach called
  "via-last").
- **Only Phase 2 leaves a blind via.** It doesn't become a true
  through-via until Phase 4 (backside reveal) happens, later, after
  BEOL and after the wafer is diced. In a finished stack, the base
  logic die doesn't need a through-via at all (it connects to the
  package/interposer directly); every DRAM die above it does.

This repo's notebook models Phase 2 only, one via at a time.

## What's in the notebook

| Stage | What it shows | Real parameter / source |
|---|---|---|
| Pattern + Bosch DRIE etch | **768-run, 4-parameter DOE**, then an **11-parameter screening pass** (all of `bosch_etch`'s real knobs, not just the 4 already being varied) found 2 more that matter, then an **800-run combined DOE** on the new top-4 (`etch_time`, `neutral_sticking_probability`, `initial_etch_time`, `neutral_rate`) found a ~37% better, depth-matched-and-replicated winner | ~50um deep, 5-10um diameter TSVs, SF6/C4F8 Bosch cycling -- via-middle process diagram |
| Failure mode vs. fix | Side-by-side profile: long etch_time / low isotropic component produces a heavily bowed, over-deep via; the current production recipe produces genuinely straight sidewalls | same DOE data |
| Patterning's mask taper angle | A first pass claimed a real etch-vs-fill trade-off from this never-before-tested knob; replication (6-10 runs, not 1) showed the fill-side half of that claim doesn't survive -- retracted. What's real: one taper value gives a reproducibly stable (near-zero-variance) etch result, the other a genuinely bimodal one | `ps.MakeHole`'s `maskTaperAngle` |
| Liner (SiO2) | Isotropic deposition, swept-optimal thickness/sticking probability (comprehensive 64-run sweep against the current etch geometry, ~99.6% floor coverage) -- matches SACVD's real thermal-flow conformality | SACVD/TEOS-O3 liner writeup |
| Barrier + seed (TaN/Ta/Cu) | Plain isotropic deposition physically stalls at the via floor at this aspect ratio; a directional model (iPVD's "ion bullets"), swept-optimal (comprehensive 64-run sweep, ~99% floor coverage) -- `iso_ratio` turned out to have zero measurable effect once thickness clears a functional minimum | iPVD directional-sputter writeup |
| Cu fill | **Subconformal** (naive isotropic) traps a large void; **conformal** (uniform rate) leaves a thin seam; **superconformal** (directional, swept-optimal via an 80-run sweep) reaches the floor with a much smaller residual gap -- the canonical via-fill spectrum, and the real "popcorning" failure mode that superfill chemistry (suppressor/accelerator/leveler) is engineered to avoid | Cu electroplating superfill writeup + canonical fill-spectrum diagram |
| CMP | **A claim retracted, not a clean success.** An earlier version claimed "over-polish causes dishing, the nominal amount fixes it" -- backwards. The nominal (textbook-correct) overburden leaves severe dishing; fixing it needs 5-10x more material removal than any real fab would polish, destroying the mask along the way. A genuine structural ceiling of this simple uniform-removal model, documented rather than hidden | -- |
| Closing 3D render | One full 3D run (`render_3d.py`) of the current production parameters, showing the real round via and scalloping (materials now correctly separated -- an earlier version rendered the mask's flat top merged into the via walls, looking like a stray plane) | -- |

## The DOE, honestly

768 runs is not a fab-calibrated DOE -- there's no measured process data to
validate against, and (unlike a real industrial DOE) no statistical
replication built into the sweep itself. It's a dense sensitivity study on
simulation model coefficients. Two things are worth stating plainly because
they came up during this project and mattered:

1. **A real confound, caught and corrected.** The raw sweep's top-ranked
   result looked dramatically better than it really was: sweeping
   `etch_time` at a fixed cycle count means short `etch_time` produces a
   shallower via, and shallower vias trivially show less wall bulge
   (less depth for aspect-ratio-dependent etching to accumulate)
   independent of whether the recipe is actually better. Caught by
   regenerating the winner at a depth comparable to the pre-DOE baseline
   and checking whether the improvement held up -- it did, just not by as
   much as the confounded number implied (~2.8x, not ~3.7x).
2. **Run-to-run noise is real.** These are Monte Carlo ray-traced flux
   models; a single run's bulge measurement varies meaningfully run to
   run (observed range: 0.015-0.023 for the same "winning" parameters
   across 3 replicates). The reported improvement factor is based on
   replicated means with non-overlapping ranges, not a single lucky run.
3. **Passivation (`deposition_thickness`) interacts with `etch_time` --
   there's no universal "more/less passivation is better."** At the
   winning `etch_time=0.5`, thin passivation (0.01-0.02) is best and
   thick (0.04) makes it worse (mean bulge 0.028-0.029 vs. 0.069). At a
   long, aggressive `etch_time=2.0`, the relationship flips: thick
   passivation is best (0.112) and thin is worst (0.161). How much
   protective coating you need depends on how aggressive the etch step
   itself is, not a fixed rule.
4. **Cycle granularity has a real optimum, not a monotonic trend.** At
   matched target depth (~1.2), 6 coarse cycles gives bulge 0.056, the
   DOE's own 12-cycle recipe gives 0.023 (best), and 24 finer cycles
   gives 0.074 (worse again). Neither "coarser" nor "finer" is
   universally better -- there's a sweet spot in the middle.
5. **A one-factor-at-a-time screen can mis-rank parameters that
   interact.** Screening all 11 of `bosch_etch`'s real parameters (not
   just the original DOE's 4) found `initial_etch_time` ranked above
   `neutral_rate`. A full 800-run combined DOE on the new top-4 found the
   opposite: `neutral_rate`'s effect is nearly as large as `etch_time`'s,
   while `initial_etch_time` turned out to be the smallest of the four.
   The screen is a useful, cheap first pass -- it correctly flagged both
   as worth including -- but the combined DOE, not the screen, decides
   the real ranking. This DOE's winner (~37% better wall bulge than the
   previous production recipe, depth-matched and replicated) is now the
   production recipe used throughout the notebook.
6. **A claim was made, contradicted itself on rebuild, and got
   retracted.** Checking all 5 process steps' real parameters jointly
   (not each step optimized only against its own metric) is how a
   cross-stage interaction would show up if one existed. It looked like
   one did for patterning's mask taper angle -- until rebuilding the
   notebook produced the opposite result from a fresh run of the "same"
   comparison. Replicating properly (6-10 runs instead of 1) showed the
   fill-side half of the claim doesn't survive at all (the two
   candidates' result ranges almost completely overlap); what's real is
   a numerical-stability difference in the etch step itself, not a
   trade-off between etch and fill. Reported this way, not smoothed over,
   because the tidier version was wrong.
7. **CMP's "over-polish causes dishing" claim was backwards.** Checked
   against a field-vs-via measurement rather than assumed: the nominal,
   textbook-correct overburden amount leaves *severe* dishing, and fixing
   it requires removing far more material than any real fab would ever
   polish -- enough to fully consume the mask layer along the way. A
   genuine structural ceiling of the simple uniform-removal CMP model
   used here (it has no concept of polish-pad contact pressure, which is
   the actual mechanism that lets real CMP planarize), not a tuning gap.

## Explicitly out of scope

ViennaPS is a level-set **topography/process** simulator (etch, deposition,
oxidation) at single-feature scale. None of this models, and the notebook
doesn't claim to model:

- Package-level warpage, dummy-die stress, or JEDEC thickness budgets
- TC-bonding vs. hybrid-bonding thermal/mechanical reliability
- JEDEC SPHBM4 signaling/clocking standards
- Intel ZAM, HBF, GPU-in-base-die architectures, or CoWoS vs. CoWoP packaging
- True inter-via loading effects (the via-array closing visual tiles one
  converged profile for visual context; it does not simulate multiple
  vias competing for reactant flux)

Those are real, useful industry context (see `PRD.md`) but belong to a
different class of tool (mechanical/thermal FEA, package-level EDA), not
this one.

## Running it

```sh
python3.13 -m venv .venv
source .venv/bin/activate
pip install matplotlib pillow jupyter nbconvert numpy
# ViennaPS must be built from source -- see "Environment" below
python3 sweep_big.py            # ~55 min, 768 runs, writes sweep_big_results.json
python3 sweep_downstream.py     # ~1 min, writes sweep_downstream_results.json
python3 render_3d.py            # ~1 min, writes fig_3d_via.png
python3 build_notebook.py
jupyter nbconvert --to notebook --execute --inplace tsv_traveler.ipynb
```

## Environment: ViennaPS on macOS

The `viennaps`/`viennals` **PyPI wheels are currently broken on macOS**
(each bundles its own copy of VTK/libomp, which conflicts with itself and
with Homebrew's copies -- segfaults on any simulation call; see upstream
[issue #167](https://github.com/ViennaTools/ViennaPS/issues/167)). Fix used
here: build both from source against Homebrew's libs.

```sh
brew install vtk embree libomp
export CMAKE_ARGS="-DOpenMP_ROOT=$(brew --prefix libomp)"
pip install /path/to/ViennaPS       # clone github.com/ViennaTools/ViennaPS
pip install --force-reinstall --no-deps /path/to/ViennaPS/build/_deps/viennals-src
```

Note: these are Monte Carlo ray-traced flux models -- expect small
run-to-run numerical noise, not bit-identical results between runs.

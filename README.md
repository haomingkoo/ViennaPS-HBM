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
| Pattern + Bosch DRIE etch | **768-run, 4-parameter DOE** (`ion_source_exponent`, `neutral_sticking_probability`, `etch_time`, `deposition_thickness`) identifying `etch_time` as the dominant knob for wall bulge -- bigger than the isotropic component a smaller 2-parameter sweep had suggested was dominant | ~50um deep, 5-10um diameter TSVs, SF6/C4F8 Bosch cycling -- via-middle process diagram |
| Failure mode vs. fix | Side-by-side profile: long etch_time / low isotropic component produces a heavily bowed, over-deep via; the DOE's sweet spot (etch_time=0.5, ion=200, neutral=0.2) produces genuinely straight sidewalls | same DOE data |
| Liner (SiO2) | Isotropic deposition, swept-optimal thickness/sticking probability (25-run sweep against the DOE-winning geometry, 99.6% floor coverage) -- matches SACVD's real thermal-flow conformality | SACVD/TEOS-O3 liner writeup |
| Barrier + seed (TaN/Ta/Cu) | Plain isotropic deposition physically stalls at the via floor at this aspect ratio; a directional model (iPVD's "ion bullets"), swept-optimal (25-run sweep, 99% floor coverage) | iPVD directional-sputter writeup |
| Cu fill | **Subconformal** (naive isotropic) traps a large void; **conformal** (uniform rate) leaves a thin seam; **superconformal** (directional, swept-optimal via a 30-run sweep) reaches the floor with a much smaller residual gap -- the canonical via-fill spectrum, and the real "popcorning" failure mode that superfill chemistry (suppressor/accelerator/leveler) is engineered to avoid | Cu electroplating superfill writeup + canonical fill-spectrum diagram |
| CMP | Planarizes back to the pad surface | -- |
| Closing 3D render | One full 3D run (`render_3d.py`) of the DOE-tuned parameters, showing the real round via and scalloping | -- |

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

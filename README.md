# ViennaPS TSV Traveler -- HBM4/HBM4E

A [ViennaPS](https://github.com/ViennaTools/ViennaPS) simulation of the
via-middle TSV process loop used in HBM manufacturing, run end to end in
[`tsv_traveler.ipynb`](tsv_traveler.ipynb).

## What's in the notebook

| Stage | What it shows | Real parameter / source |
|---|---|---|
| Pattern + Bosch DRIE etch | Sidewall scalloping and a **2-parameter sensitivity sweep** identifying `neutral_sticking_probability` (the isotropic/chemical SF6 component) as the real tuning knob for scalloping -- more than ion directionality | ~50um deep, 5-10um diameter TSVs, SF6/C4F8 Bosch cycling -- via-middle process diagram |
| Failure mode vs. fix | Side-by-side profile: low-directionality/high-isotropic parameters produce a bowed via; the sweep's sweet spot produces straight sidewalls | same sweep data |
| Liner (SiO2) | Isotropic, low-sticking deposition reaches deep into a ~10:1 AR via -- matches SACVD's real thermal-flow conformality | SACVD/TEOS-O3 liner writeup |
| Barrier + seed (TaN/Ta/Cu) | Plain isotropic deposition physically stalls at the via floor at this aspect ratio; a directional model (iPVD's "ion bullets") reaches it | iPVD directional-sputter writeup |
| Cu fill | **Naive isotropic fill traps a void** (seals near the opening, ~1.76um of the via left empty); **directional bottom-up fill reaches within ~0.25um of the floor** -- the real "popcorning" failure mode and why superfill chemistry (suppressor/accelerator/leveler) is engineered to grow bottom-up | Cu electroplating superfill writeup |
| CMP | Planarizes back to the pad surface | -- |
| Closing 3D render | One full 3D run (`render_3d.py`) of the tuned parameters, showing the real round via and scalloping | -- |

## Explicitly out of scope

ViennaPS is a level-set **topography/process** simulator (etch, deposition,
oxidation) at single-feature scale. None of this models, and the notebook
doesn't claim to model:

- Package-level warpage, dummy-die stress, or JEDEC thickness budgets
- TC-bonding vs. hybrid-bonding thermal/mechanical reliability
- JEDEC SPHBM4 signaling/clocking standards
- Intel ZAM, HBF, GPU-in-base-die architectures, or CoWoS vs. CoWoP packaging

Those are real, useful industry context (see `PRD.md`) but belong to a
different class of tool (mechanical/thermal FEA, package-level EDA), not
this one.

## Running it

```sh
python3.13 -m venv .venv
source .venv/bin/activate
pip install matplotlib pillow jupyter nbconvert numpy
# ViennaPS must be built from source -- see "Environment" below
python3 sweep.py           # ~1 min, writes sweep_results.json
python3 render_3d.py       # ~1 min, writes fig_3d_via.png
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

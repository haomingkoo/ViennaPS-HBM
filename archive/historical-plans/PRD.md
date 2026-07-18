# PRD: ViennaPS TSV Process Demo (HBM4/HBM4E)

## Goal
Demonstrate ViennaPS's capability as a process/topography simulator by modeling
the TSV ("via-middle") process loop used in HBM manufacturing — as a
standalone proof of concept that could later feed into a broader tool
(e.g. Coventor/SEMulator3D-style workflow).

## What we're building
One Jupyter notebook — a "TSV traveler" — simulating the full via-middle
loop on one representative via, step by step, each with an inline
surface-profile diagram:

| Step | Real process step | What it shows |
|------|--------------------|----------------|
| 1 | Patterning (mask) | Starting geometry |
| 2 | Deep silicon etch (Bosch: SF6/C4F8 cycling) | Sidewall scalloping / aspect-ratio-dependent etching; **parameter sweep** over etch/passivation cycle timing and ion energy to show the straight-sidewall-vs-scalloping-vs-depth-rate tradeoff, calling out a "sweet spot"; per-cycle snapshots animated into a GIF |
| 3 | Liner deposition (SiO2) | Conformality over the scalloped sidewall |
| 4 | Barrier + seed (TaN/Ta/Cu) | Conformality risk rising with aspect ratio |
| 5 | Cu fill | Naive conformal fill (void/pinch-off) vs. controlled bottom-up fill |
| 6 | CMP | Planarization, exposed Cu pad |

Built on ViennaPS's existing example models (`SF6O2Etching`, ALD/isotropic
deposition, `IsotropicProcess`) with parameters adapted to real numbers,
not custom physics.

## Real parameters used (sourced from shared industry material)
- TSV: ~50 µm deep, 5–10 µm diameter (~5–10:1 aspect ratio), scalloped
  sidewalls from Bosch DRIE.
- Extreme-AR Cu pillar trend: 3–5:1 → 15–20:1, <10 µm diameter before
  bend/break risk (Samsung VCS/FOWLP).
- Hybrid-bonding Cu pad: 0.4 µm pad / 0.8 µm pitch, dishing controlled
  from +20 Å protrusion to −10 Å recess via CMP + wet ALE (Samsung
  HBM4E hybrid bonding).

## Explicitly out of scope
Everything below was useful industry context but is a package/system-level
question, not a topography simulation ViennaPS can do:
- Package warpage, dummy-die stress, thickness budget (JEDEC 775µm→900µm+)
- TC bonding vs. hybrid bonding thermal/mechanical reliability
- JEDEC SPHBM4 signaling/clocking standard
- GPU-in-base-die / HBF / Intel ZAM architectures, NVIDIA rack roadmap
- CoWoS vs. CoWoP board assembly

These get one line each in the demo README as "why not modeled here,"
not faked.

## Known blocker (found + fixed)
ViennaPS's macOS PyPI wheels (both `viennaps` and `viennals`) each bundle
their own copies of VTK/libomp, conflicting with each other and with
Homebrew's copies — segfaulting on any simulation call (upstream
[issue #167](https://github.com/ViennaTools/ViennaPS/issues/167) covers
the libomp half of it). Fixed by building **both** packages from source
against Homebrew's `vtk`/`embree`/`libomp` (`CMAKE_ARGS=-DOpenMP_ROOT=$(brew --prefix libomp)`)
instead of `pip install ViennaPS`. Verified: the unmodified upstream
`boschProcess` example now runs clean end to end.

## Deliverable
- `tsv_traveler.ipynb` — the notebook above, runnable top to bottom, with
  inline surface-profile diagrams and the animated etch-cycle GIF.
- A short README tying each result to the real fab challenge it illustrates.
- (Optional follow-up, not this pass: export key notebook figures into slides.)

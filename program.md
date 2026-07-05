# program.md -- objective

(Supersedes PRD.md, which is left in place as the original design doc.
This is the current, standing objective -- update it when the goal changes,
rather than letting the notebook/README drift from what this says.)

## Goal

Demonstrate real engineering capability with ViennaPS on a current,
concrete industry problem: forming and filling the TSVs that HBM4/HBM4E
memory stacks depend on. Not "run a simulation tool" -- "use data to find
out what actually controls the outcome, catch mistakes along the way, and
report an honest, defensible result."

## The three things that have to be right

1. **Straight etch** -- the TSV sidewall must not bow or scallop.
2. **Target depth** -- deep enough to connect through the die after
   backside thinning; nowhere near full wafer thickness (~700-775um
   pre-thinning; see `MAX_REALISTIC_ASPECT_RATIO` in `tsv_process.py`).
3. **Void-free fill** -- the copper fill must not trap an air pocket.

## Scope

Models Phase 2 of the real via-middle process only (pattern -> Bosch etch
-> liner -> barrier+seed -> Cu fill -> CMP), one via at a time, at
single-feature topography scale. See README's "Where this fits in the
real process" section for the full 4-phase picture and where this sits
in it.

## Explicitly out of scope

- Package-level warpage, dummy-die stress, JEDEC thickness budgets
- TC-bonding vs. hybrid-bonding thermal/mechanical reliability
- JEDEC SPHBM4 signaling/clocking
- Intel ZAM, HBF, GPU-in-base-die, CoWoS vs. CoWoP packaging
- True inter-via loading effects (RIE lag) -- would need multiple vias
  sharing one domain, competing for reactant flux
- Curvature-dependent (CEAC-like) Cu fill growth -- the real electroplating
  mechanism that closes sharp corners; `DirectionalProcess`'s constant
  direction vector cannot represent this (see prepare.md's log)

## Current deliverables

- `tsv_traveler.ipynb` -- the full 6-step notebook, DOE-winning parameters
  throughout, good/bad pairs for every step, all-layers cross-sections,
  12-die stack closing visual
- `explainer.html` -- standalone interactive report (published as an
  Artifact), DOE effects chart + etch_time/neutral explorer
- `README.md` -- findings, corrected process-flow understanding, sources

# Full TSV Traveler Campaign Protocol

This is the launch contract for the long-running full-traveler study. It supersedes the small managed pilot as the research protocol, while preserving the pilot as evidence.

## Objective and terminal condition

Establish a reproducible, critical account of pattern -> Bosch etch -> liner -> barrier/seed -> Cu fill -> CMP. Stop only after every phase below has an auditable artifact and final review, or after a structural model ceiling is demonstrated with replicated evidence.

The lower-is-better full-process loss is a monitoring metric. It is never sufficient by itself to claim a recipe, interaction, or full-traveler success.

## Non-negotiable gates

- Valid metrics precede all ranking.
- CMP mask consumption is a hard failure.
- Etch comparisons must be depth-matched.
- Liner, barrier/seed, and fill must meet functional minimum thickness gates.
- Fill coverage cannot replace centerline tip gap.
- Downstream comparisons reuse each shared upstream geometry; Bosch Monte Carlo variation must not impersonate a process interaction.
- A boundary optimum is provisional until its range has been expanded.
- A recommended recipe requires independent/unseen-seed replication.
- Do not claim zero-gap fill or realistic CMP when the current models cannot represent the required physics.

## Stages and evidence

1. Validate the canonical review/scoring kernel with synthetic hard-gate, invalid-metric, stability, and boundary tests.
2. Reproduce and decompose the pilot baseline. Preserve pilot artifacts under `autoresearch-results/` as historical evidence.
3. Build the knob registry from wrapper call sites and ViennaPS API inspection. Each knob records owner, units, default, range, type, mechanism, interactions, and evidence status.
4. Measure Bosch stochastic variation across repeated identical geometries and choose replicate counts from observed uncertainty.
5. Screen unconfirmed knobs in controlled step-specific blocks. Use at least four replicated shared bases when a downstream factor is compared.
6. Run within-step and cross-step interaction designs only for screened important factors. Record the reference geometry IDs used by every downstream arm.
7. Refine feasible regions with broad blocks of 96--160 recipes and at least four replicates, then local blocks of at least 64 recipes and six replicates.
8. Expand every winning tested boundary before naming an optimum.
9. Confirm finalists on 8--12 unseen seeds/independent geometries.
10. Perturb finalists around each recipe knob to estimate the usable process window, p90, and worst-case outcome.
11. Publish robust winner, credible alternatives, and Pareto tradeoffs. Separate tuning misses from structural ceilings.

## Required artifacts

Use `autoresearch-results/full_campaign/` for all new campaign data. Each generation needs plan, registry snapshot, design/space, upstream-geometry manifest, raw rows, summary, critical review, scalar metric, and next-decision record. Append durable findings and negative results to `prepare.md`.

The final package includes the complete score history, machine-readable rows, registry, methods, target-spec tables, robustness/process-window tables, Pareto alternatives, model-limit evidence, and a publication-style critical review.

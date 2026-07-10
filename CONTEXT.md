# ViennaPS-HBM Context

## Domain

ViennaPS-HBM models the via-middle TSV traveler used for HBM-style memory stacks. The research objective is a defensible full-process result, not a single-step proxy win.

## Glossary

- **Full TSV traveler**: The six-step flow from patterning through CMP on one simulated via: pattern, Bosch etch, liner, barrier/seed, copper fill, and CMP.
- **Target spec**: The numeric pass/fail and score definition for each traveler step. `program.md` is the source of intent; `tsv_process.TARGET_SPECS` is the executable source.
- **Step target score**: A lower-is-better distance to one step target. It must include hard gates before any raw proxy ranking can matter.
- **Full-process loss**: The scalar research metric used by autoresearch. It combines p90 score, missing step passes, CMP mask consumption, and invalid metric penalties.
- **Depth-matched etch**: An etch comparison where candidate profiles reach comparable depth before straightness is judged.
- **Tip gap**: The centerline residual gap after copper fill. This is the gating fill metric; floor coverage is supporting data.
- **CMP mask consumption**: A destructive polish outcome where the mask no longer survives. It is a hard failure even if dish improves.
- **Invalid metric penalty**: A bad-region signal for failed or non-finite metrics. It should be retained in results, not filtered away as an outlier.
- **Autoresearch generation**: One planned DOE iteration that carries top candidates, adapts the factor space, runs replicates, reviews failures, and logs the next decision.

## Standing Constraints

- Report full traveler claims against the target specs, not raw proxies.
- Treat fill and CMP structural ceilings honestly when the model cannot satisfy the physical target.
- Review every generation for failed specs, replicate stability, hard gates, boundary artifacts, and the next decision before claiming progress.

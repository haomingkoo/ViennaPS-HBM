# Code review — 2026-07-18

Scope: active Python, numerical evidence, CI, and the public explainer. Archived
campaigns were inspected as history but were not refactored.

## Correctness review

| Priority | Finding | Status |
|---|---|---|
| P0 | Copper-fill review accepted contradictory void flags and missing diagnostic records. | Fixed with fail-closed checks and adversarial tests. |
| P0 | Partial low-ray runs were published as formal rejections without a frozen stop event. | Fixed in publication vocabulary; partial mismatches remain observations. |
| P0 | The promised attempt ledger had no repository writer, chain check, or executable retry hook. | Fixed with `scripts/autoresearch_event_log.py`, schema rules, and chain/retry tests. Active campaign runners do not use it yet. |
| P0 | The 500-ray bridge changes rays, random streams, and stopping intervals together. | Claim reduced to provisional. A clean single-variable qualification is required. |
| P0 | Public copy called 500 rays the exploration setting despite the Phase B rejection, and described a 1,000-ray promotion check that no code enforced. | Public claim corrected. Candidate-specific numerical qualification remains open. |
| P1 | Low-ray workers can discard failed attempts and retry indefinitely after restarts. | Open. The executed runner is retained as evidence; replace it with the ledger-backed runner for the next clean qualification. |
| P1 | Runner fingerprints omit some wrapper, builder, and reviewer code. | Open. Existing rows remain commissioning evidence only. |
| P1 | The saved-review rule can miss material absolute drift or boundary movement. | Open. The next qualification must gate normalized per-anchor deltas and boundary displacement. |
| P1 | Native ViennaPS scientific tests are not executable on GitHub-hosted CI. | Open and disclosed. CI covers portable code and publication checks only. |
| P1 | The frozen macOS simulation environment cannot currently install packages because its Homebrew Python/Expat linkage is stale. | Open. Keep it frozen for native tests and use a separate locked development environment. |
| P1 | Rebuilding `step_experiments.json` twice with the same declared seed did not produce a byte-identical artifact on the reviewed native runtime. | Open. Keep the committed reviewed artifact authoritative. Do not hide the difference with rounding or truncation; isolate the first divergent field and runtime source before regenerating it for release. |
| P2 | Exact native runtime dependencies and checkpoints are not fully rebuildable from a clean clone. | Partly fixed for numerical chart evidence; full native reproduction remains open. |

## Ponytail audit

Ranked simplifications; no speculative framework is recommended.

1. Combine the three thin frozen-campaign wrappers after their current studies
   close. They repeat manifest loading, pending-case selection, worker setup,
   JSONL append, and resume logic.
2. Move retired scalar-score helpers out of the active `tsv_process.py` path.
   They encode the withdrawn phase-one objective and make current intent harder
   to find.
3. Keep JSON Schema plus the standard library. Pydantic would duplicate the
   public schema and add no current capability.
4. Keep campaign ranges in frozen manifests. Moving historical DOE values into
   one global configuration file would weaken provenance.
5. Do not add Adam, a generic optimizer framework, or an application backend.
   The present problem is constrained, discontinuous, and evidence-limited.

## Verification

- Ruff covers every tracked active Python file.
- Ty checks the maintained runtime and publication path.
- JSON Schema tests reject missing fields, invalid retry states, stale hashes,
  broken selectors, and impossible status labels.
- Browser tests exercise saved-output controls and the numerical charts.
- The exact stock ViennaPS runtime passed all 36 routed tests locally. The 16
  custom Cu/CMP-runtime tests remain separate from GitHub-hosted CI.

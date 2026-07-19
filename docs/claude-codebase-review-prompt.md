# Independent codebase review prompt

Use the prompt below with Claude from the repository root.

```text
Act as an independent staff-level scientific-software reviewer. Review this
ViennaPS-HBM repository read-only. Do not edit files, run long simulations,
rewrite generated evidence, or assume that a visually plausible profile is a
validated process result.

Project intent
--------------
This is a public teaching and research repository for a simplified TSV process
traveler using ViennaPS. It should demonstrate strong capability in process
modeling, metrology, multifactor experimentation, numerical-cost tuning,
evidence handling, and honest scientific limits. It must not present ViennaPS
model coefficients as fab recipes or assumed teaching bands as calibrated
specifications.

Start by reading
----------------
- AGENTS.md if present
- README.md
- CASE_STUDY.md
- program.md
- docs/experiment-playbook.md
- docs/current-run.md
- docs/adaptive-etch-search.md
- docs/screening-doe-plan.md
- docs/evidence-map.md
- docs/code-review-2026-07-18.md
- .github/workflows/ci.yml
- scripts/run_capability_tests.py

Then inspect the active code, tests, schemas, evidence directories, generated
publication builders, archive, and Git history where useful.

Review questions
----------------
1. Public story
   - Can a new engineer understand what was modeled, what was measured, what
     was learned, and what remains open?
   - Does the repository show advanced ViennaPS capability, or does the volume
     of files obscure it?
   - Identify verbose, repetitive, unexplained, or AI-sounding public prose.

2. Scientific correctness
   - Are physical controls, model controls, geometry inputs, numerical settings,
     and measurements kept separate?
   - Find unsupported pass/fail limits, magic numbers, proxy metrics, or claims
     above the evidence level.
   - Check whether “ideal profile,” “void-free,” “connected,” “converged,” and
     “qualified” are used consistently.
   - Confirm that depth, top/middle/bottom/minimum CD, taper, bow, scallop,
     symmetry, and floor shape cannot cancel one another in a single score.
   - Check whether the current focused search actually includes floor shape.

3. Experiment design and optimization
   - Trace range research -> measurement qualification -> numerical profile ->
     multifactor screening -> focused tuning -> held-out confirmation.
   - Identify skipped stages, weak ranges, aliases, missing repeats, coupled
     factors, or unjustified interactions.
   - Determine whether autoresearch is genuinely adaptive. Distinguish event
     logging/resume logic from automated model fitting and case proposal.
   - Assess whether the stated plan for constrained local Bayesian optimization
     is supported by enough repeated data.

4. Numerical evidence
   - Audit grid, rays, random streams, stopping rules, runtime comparisons, and
     checkpoint selection.
   - Look for comparisons that changed more than one variable.
   - Do not treat a larger ray count or finer grid as truth without evidence.
   - Verify that faster settings have a named scope and promotion/fallback rule.

5. Code correctness and maintainability
   - Trace the active execution paths end to end.
   - Find duplicate functions, dead code, unused flags, hard-coded experiment
     values, inconsistent config ownership, stale comments/docstrings, and
     silent test files.
   - Check that each CLI has clear inputs, deterministic outputs, and failure
     behavior.
   - Flag overengineering using YAGNI: unnecessary abstractions, dependencies,
     wrappers, or speculative flexibility.
   - Do not recommend a framework merely to reorganize files.

6. Repository hygiene
   - Classify every top-level Python file as public core, publication builder,
     active research, test, historical/archive, or dead/duplicate.
   - Identify tracked files under ignored paths, absolute local paths, generated
     duplicates, large embedded assets, and competing evidence authorities.
   - Propose the smallest safe public directory structure that preserves frozen
     provenance.
   - State which files can be deleted now, which should move only through a
     versioned migration, and which must remain.

7. Evidence and data contracts
   - Reconcile manifests, event JSONL, measurement rows, checkpoints, reviews,
     publication exports, schemas, hashes, and archival snapshots.
   - Find missing required fields, guessed values, stale provenance, incomplete
     indexes, unlisted artifacts, and duplicate native checkpoints.
   - Recommend a minimal canonical evidence layout. Do not invent data.

8. Reproducibility and CI
   - Execute only fast, safe checks unless a native runtime is already verified.
   - Confirm that CI actually runs tests rather than merely listing them.
   - Check clean-clone publication rebuild, schema validation, lint, type checks,
     browser tests, hooks, and dependency locks.
   - Identify tests that silently pass because their functions are never called.

Required output
---------------
A. Executive verdict: 5-10 sentences, including the highest claim this repo can
   support today.
B. Top findings: ranked by severity. Each finding must include file:line,
   evidence, impact, and the smallest safe fix.
C. Public-repo inventory: counts and a table assigning every top-level Python
   file to one category. Put the full table in an appendix if long.
D. Scientific claim audit: supported, overstated, unresolved, or stale.
E. CI/reproducibility audit: commands run, commands skipped, and exact reasons.
F. Ponytail audit: one line per removable complexity item, biggest deletion
   first, ending with estimated lines and dependencies removable.
G. Three-phase cleanup plan:
   1) safe now, no provenance break;
   2) versioned path/data migration;
   3) optional improvements only if a measured need appears.
H. Five questions that must be answered before the next simulation campaign.

Rules
-----
- Cite exact paths and line numbers for every important claim.
- Say “unknown” when evidence is absent.
- Do not count generated HTML size as code complexity without explaining the
  no-server deployment requirement.
- Do not delete archives or frozen evidence merely because they are old.
- Do not propose commercial-tool comparisons.
- Prefer deletion and documentation over new abstractions.
- Keep calibrated requirements, assumed teaching bands, numerical agreement,
  and model limitations visibly separate.
```

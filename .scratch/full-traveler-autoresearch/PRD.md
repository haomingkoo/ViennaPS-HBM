# PRD: Full TSV Traveler Autoresearch

Status: ready-for-agent
Label: ready-for-agent

## Problem Statement

The repo has useful ViennaPS experiments, but the current research story is still too easy to weaken: dry-etch wins can distract from the full TSV traveler, partial sweeps can be mistaken for conclusions, and review logic can drift across scripts. The user needs a defensible autoresearch loop that demonstrates a well-thought-through full process from patterning through CMP, including critical review of failed specs and structural model ceilings.

## Solution

Build and run a clean full-traveler autoresearch workflow. The workflow should use a dedicated branch, local PRD/issues, an architecture-reviewed module plan, `autoresearch-results/` run artifacts, a scalar lower-is-better metric, and a generated critical review artifact for every meaningful generation. The first implementation seam is the full-process review module: it owns aggregation, hard gates, scalar loss, failure taxonomy, boundary notes, and the next decision.

## User Stories

1. As the project owner, I want the experiment to optimize the full TSV traveler, so that the result is not just a dry-etch story.
2. As the project owner, I want a clean baseline branch and commit, so that autoresearch can use git as memory.
3. As the project owner, I want a PRD and issue breakdown, so that agents can work from a clear objective instead of ad hoc prompts.
4. As a reviewer, I want CMP mask consumption to be a hard gate, so that destructive polish settings cannot win by improving dish.
5. As a reviewer, I want invalid metrics retained as penalties, so that bad regions remain visible evidence.
6. As a reviewer, I want each step target scored against the project specs, so that raw proxies cannot become false wins.
7. As a reviewer, I want replicated p90 ranking, so that one lucky replicate cannot become the headline.
8. As a researcher, I want failed and unstable specs listed for the current best candidate, so that the next generation has a real hypothesis.
9. As a researcher, I want boundary notes on top candidates, so that edge optima trigger expanded search instead of premature claims.
10. As a researcher, I want fill and CMP ceilings stated honestly, so that model limits are not hidden as unresolved tuning work.
11. As an AFK agent, I want a single full-process loss command, so that improvement can be measured consistently.
12. As an AFK agent, I want run artifacts under `autoresearch-results/`, so that generated state is separated from source.
13. As an AFK agent, I want review artifacts generated from rows, so that claims can be audited after each run.
14. As a maintainer, I want aggregation and loss rules in one interface, so that DOE, review, and autoresearch cannot drift.
15. As a maintainer, I want compile and metric guards before launch, so that background agents do not start from a broken repo.
16. As a maintainer, I want the final demo to cite the PRD, issues, architecture report, run log, and review, so that autoresearch is visible as a disciplined process.

## Implementation Decisions

- Use local markdown as the issue tracker for this research branch to avoid public GitHub side effects during experimentation.
- Treat `program.md` as the objective, `train.md` as protocol, `prepare.md` as methodology and research log, and `CONTEXT.md` as domain vocabulary.
- Use the architecture review top recommendation: deepen the full-process review module first.
- The review module interface should accept DOE rows and return ranking, scalar loss, hard-gate failures, step stability, boundary notes, and report-ready facts.
- `joint_process_doe.py`, `review_joint_process_results.py`, and `autoresearch_joint_process.py` should share that review interface instead of duplicating ranking/loss logic.
- Use `autoresearch-results/` for managed autoresearch run artifacts; keep source code, PRD, issues, and methodology docs in normal repo paths.
- Launch background codex-autoresearch only after branch baseline, compile guard, and current metric are recorded.
- The scalar metric is lower-is-better full-process loss from `review_joint_process_results.py --metric-only` until replaced by the shared review interface.
- Hard gates: CMP mask consumption and invalid metrics must dominate ranking before raw score.
- The current unmanaged checkpoint metric is `250.52721918028647`; treat it as monitoring evidence, not a complete generation.

## Testing Decisions

- Test the review seam with synthetic DOE rows that cover pass, fail, invalid metric, CMP mask-consumed, and unstable-replicate cases.
- Keep process simulation tests small; do not require long ViennaPS sweeps for unit-level review behavior.
- Use Python compile checks for the DOE, review, and autoresearch scripts as the launch guard.
- Use a real metric command against checkpoint rows before launch to verify the baseline is measurable.
- For any process-result claim, regenerate the critical markdown review and append the finding or dead end to `prepare.md`.

## Out of Scope

- Replacing ViennaPS physical models.
- Claiming true zero tip-gap copper fill if the current model cannot represent CEAC.
- Claiming realistic CMP if the current isotropic removal model still consumes the mask to reduce dish.
- Publishing GitHub issues during this local research setup.
- Redesigning the explainer UI before the full-traveler research loop is credible.

## Further Notes

- Architecture report: `/tmp/architecture-review-viennaps-hbm-20260710.html`
- Managed results directory: `./autoresearch-results/`
- Current unmanaged DOE checkpoint: 434 rows, stopped safely before completion.

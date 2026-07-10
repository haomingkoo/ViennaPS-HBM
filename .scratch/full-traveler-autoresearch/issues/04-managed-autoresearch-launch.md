# Issue 04: Launch managed background autoresearch

Status: ready-for-agent
Label: ready-for-agent

## What to build

Launch codex-autoresearch in background mode against the clean full-traveler branch. The run should improve the full TSV traveler workflow, not only dry etch, and should keep reviewing results critically after each generation.

## Acceptance criteria

- [ ] `autoresearch-results/` is initialized by the managed helper scripts.
- [ ] Background runtime launch succeeds and records a manifest.
- [ ] The objective names the full TSV traveler and the full-process loss.
- [ ] The guard command includes Python compile checks for DOE, review, and autoresearch scripts.
- [ ] The run instructions require generated review artifacts before any improvement claim.

## Blocked by

- `.scratch/full-traveler-autoresearch/issues/02-generation-artifacts.md`
- `.scratch/full-traveler-autoresearch/issues/03-clean-baseline.md`

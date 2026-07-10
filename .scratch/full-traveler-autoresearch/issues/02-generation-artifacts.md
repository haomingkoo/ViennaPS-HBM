# Issue 02: Make generation artifacts durable

Status: ready-for-agent
Label: ready-for-agent

## What to build

Make each autoresearch generation produce a complete artifact set under `autoresearch-results/`: plan, space, anchors, raw rows, summary, critical review, scalar metric, and next decision. The artifact should be enough for a later agent to resume without reading terminal history.

## Acceptance criteria

- [ ] A generation writes all run artifacts under `autoresearch-results/`.
- [ ] The review artifact names failed specs, hard-gate failures, boundary risks, and the next decision.
- [ ] The scalar metric is recorded beside the generation artifacts.
- [ ] Existing unmanaged artifacts are not mistaken for managed generation state.
- [ ] Resume instructions are visible from the artifact directory.

## Blocked by

- `.scratch/full-traveler-autoresearch/issues/01-review-kernel.md`

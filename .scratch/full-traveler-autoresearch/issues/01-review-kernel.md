# Issue 01: Establish the full-process review kernel

Status: ready-for-agent
Label: ready-for-agent

## What to build

Create one review interface for full TSV traveler DOE rows. It should own aggregation, ranking, hard gates, scalar loss, step-failure summaries, replicate stability, boundary notes, and report-ready facts. Existing DOE, review, and autoresearch scripts should use this interface instead of duplicating ranking or loss rules.

## Acceptance criteria

- [ ] DOE ranking, markdown review ranking, and metric-only loss use the same implementation.
- [ ] CMP mask consumption and invalid metrics are hard gates ahead of pass count and raw score.
- [ ] Synthetic row checks cover pass, missing step pass, invalid metric, CMP mask consumed, and replicate instability.
- [ ] `review_joint_process_results.py --metric-only` still prints one lower-is-better scalar.
- [ ] Python compile checks pass for the DOE, review, and autoresearch scripts.

## Blocked by

None - can start immediately.

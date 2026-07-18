# Research archive

This directory preserves superseded work so the current study remains readable
without deleting its history. Archived files are not the current workflow and
must not be cited as validated process-window evidence.

The archive was created from commit
`031b62f19acb2adbb6413a85debf3ccb333956ec`. Git renames preserve file history;
use `git log --follow -- <path>` to inspect it. `SHA256SUMS` records the archived
file contents after the move.

Paths inside archived documents reflect the original root layout at that
commit. They are preserved as historical records, not current instructions.

## Contents

- `original-demo/` — the first notebook, rendered figures, GIF, supporting
  demo data, and its now-stale handoff note.
- `phase-one-sweeps/` — early one-off search scripts and their outputs.
- `phase-one-campaign/` — the retired joint-process, dry-etch, and flow
  campaigns. Their scorer and several conclusions were withdrawn during the
  foundation re-audit.
- `historical-plans/` — the original PRD, superseded V2 research plan, and a
  publication audit that predates the current guide.

## What supersedes this work

- [`../program.md`](../program.md) is the standing objective and acceptance
  contract.
- [`../RESEARCH_PLAN_V3.md`](../RESEARCH_PLAN_V3.md) is the active research
  sequence.
- [`../FOUNDATION_REAUDIT.md`](../FOUNDATION_REAUDIT.md) records retractions and
  evidence gaps.
- [`../docs/evidence-map.md`](../docs/evidence-map.md) maps current claims to
  saved evidence and limits.

The committed `publication_campaign_data.json` may summarize historical results
for teaching. It does not restore the retired conclusions.

To run an archived Python entry point, expose the current root modules
explicitly and opt into legacy metrics only when the script requires it:

```bash
PYTHONPATH=. VIENNAPS_HBM_ALLOW_LEGACY_METRICS=1 \
  .venv/bin/python archive/phase-one-campaign/dry_etch_doe.py --help
```

The archived data builder remains beside the phase-one code:

```bash
.venv/bin/python archive/phase-one-campaign/build_publication_data.py
```

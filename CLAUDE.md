# CLAUDE.md

Before doing any work in this repo, read `program.md`, `train.md`, and
`prepare.md`, in that order. This project follows an autoresearch-style
loop (inspired by karpathy/autoresearch's program.md/train.md/prepare.md
split, adapted for physical simulation instead of LLM training):

- **program.md** is the fixed objective. Don't silently redefine it;
  update it explicitly if the goal actually changes.
- **train.md** is the experimental protocol -- what's held constant, what
  gets varied, and known parameter interactions. Check it before running
  a new sweep so you don't re-vary something already fixed, or miss a
  known interaction.
- **prepare.md** is the evaluation methodology (the metric, and *why*
  that metric over the alternatives that were tried and rejected) plus a
  running log of what worked and what didn't. Append to the log after
  any real finding or dead end -- don't let the next session re-derive
  something already learned here.

When running experiments (a new sweep, a new parameter, a new figure):
run it, check the result against prepare.md's evaluation methodology, log
what happened in prepare.md, and only then decide the next step -- the
same iterate/measure/log/decide loop autoresearch uses, just applied to
ViennaPS simulations instead of nanochat training runs.

Do not claim a result (a "sweet spot," an "improvement," a coverage
percentage) without checking it against a metric already defined in
prepare.md, and do not introduce a new metric without writing it into
prepare.md first, including why it's needed and what it fixes.

## Agent skills

### Issue tracker

Issues and PRDs are tracked as local markdown under `.scratch/`; external PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five-label vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repo with `CONTEXT.md` at the root and ADRs under `docs/adr/`. See `docs/agents/domain.md`.

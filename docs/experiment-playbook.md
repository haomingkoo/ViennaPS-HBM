# Experiment playbook

This is the shortest safe path from a process question to a defensible
simulation conclusion.

## What a good specification contains

A specification is not just a target number. It must declare:

| Part | Required content |
|---|---|
| Purpose | The defect or handoff being controlled. |
| Geometry | Dimension, scale, incoming materials, and the region being measured. |
| Measurement | Name, units, sampling location, algorithm version, and detection limit. |
| Criterion | Value or condition, tolerance, and whether it is calibrated, literature-derived, geometry-derived, or only an assumed study target. |
| Hard gates | Conditions that cannot be traded away, such as valid geometry, target depth, an open aperture, connected films, or a resolved void check. |
| Preference | What to improve after every hard gate is satisfied, such as straighter walls, more margin, lower variation, or lower runtime. |
| Uncertainty | Repeats, random-stream policy, numerical comparison, and missing-value rule. |
| Scope | What the result may claim and what still requires calibration or experiment. |

An “ideal profile” in this repository is a teaching reference outline. It is
not a fabrication specification. A real acceptance limit needs physical units,
a measurement method, product context, and a source or calibration dataset.

## Search sequence

1. **Qualify the measurements.** Show that each metric recognizes a known
   failure and a clear control. Missing or unresolved measurements block the
   decision.
2. **Choose an exploration setting.** Compare grid, rays, runtime, repeated
   variation, and response movement on the same cases. Numerical settings are
   not process knobs.
3. **Find useful ranges.** Start from model documentation, applicable
   literature, or a clearly labelled exploratory bracket. Keep invalid and
   quiet edges as evidence.
4. **Screen factors together.** Use a named screening design, repeated center
   cases, fixed upstream geometry, and predeclared interactions. The purpose is
   to find which controls move which measurements.
5. **Tune the smaller region.** Use separate response models for depth, each
   CD, wall shape, floor shape, validity, and runtime. A constrained local
   Bayesian search is appropriate only after enough repeatable data exist.
6. **Confirm finalists.** Use unseen random streams, adverse boundary cases, a
   higher numerical setting, and 3D where the physical claim depends on 3D.
7. **Publish the limit.** Link every conclusion to rows and checkpoints. State
   whether the evidence verifies code, measurement, numerical agreement,
   simulated mechanism, calibration, or experiment.

Do not collapse the study into one weighted score. First require valid
measurements and hard gates. Then compare process margin. Only then compare
runtime and complexity.

## What the current experiments taught us

- More rays increased runtime but did not make every etch response converge
  monotonically. Near the focused etch region, 500 rays and grid 0.0025 are the
  exploration policy; promoted cases are rechecked at 1,000 rays. This policy
  does not transfer automatically to another geometry or model.
- Top, middle, and bottom CD are necessary but not sufficient. The full wall,
  symmetry, floor shape, measurement availability, and target depth must remain
  visible.
- Ion-arrival directionality and directional removal produced a useful local
  etch interaction. It is a model-space finding until equipment-to-model
  calibration exists.
- A prescribed copper motion can test the measurement code. It cannot prove a
  physical fill recipe. An unresolved center seam remains unresolved.
- Frozen campaigns must retain the exact inputs used when they ran. A current
  config change must not rewrite historical evidence.

## Does autoresearch work here?

It works as bounded research plumbing: it freezes cases, records attempts,
preserves failures, and applies retry and stop rules. Human-reviewed follow-up
experiments have exposed a wall-measurement bug, stopped unproductive ray work,
and narrowed the etch search.

It does not yet fit response models or propose cases autonomously, and it has
not found a calibrated full-traveler process window. The current focused data
are too sparse for a surrogate to rank new recipes reliably. The next proof is
prospective: freeze a small repeated batch, let an ask/tell search nominate new
cases, and compare its held-out predictions with the executed results.

## Five supporting skills

1. `research-simulation-ranges` separates documented ranges from exploratory
   brackets.
2. `design-screening-experiments` creates the small multifactor screen and its
   stopping rules.
3. `tune-simulation-speed` selects a scoped exploration profile from cost and
   response evidence.
4. `run-simulation-autoresearch` runs a bounded, resumable feedback loop.
5. `review-simulation-results` reconciles rows, measurements, uncertainty, and
   the highest supported claim.

The skills are a workflow, not five competing agents. Each produces the input
contract required by the next one.

## Evidence storage

Use one campaign directory under `evidence/<process>/<campaign>/`:

```text
manifest.json       frozen question, inputs, cases, budget, and hashes
events.jsonl        append-only attempt and terminal-state ledger
measurements.jsonl  one schema-validated row per completed case
checkpoints/        native geometry only when needed to reproduce a claim
review.json         reconciliation, decision, limits, and next action
```

Keep small publication exports at the repository root only when the static page
loads them directly. Put superseded campaigns under `archive/`. Do not commit
temporary logs, caches, rendered browser output, or duplicated native
checkpoints. Required unknowns stay `null`; they are never replaced with zero or
an invented value.

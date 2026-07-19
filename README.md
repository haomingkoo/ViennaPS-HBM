# Simplified TSV process simulation with ViennaPS

This repository follows one simplified TSV shape through six simulated steps:

1. mask opening;
2. silicon etch;
3. oxide liner;
4. barrier and copper seed;
5. copper fill; and
6. chemical-mechanical planarization (CMP).

The modeled feature remains a blind via. Wafer thinning would expose its bottom
later and complete the through-silicon connection. That step is outside this
model.

The project is a teaching tool and research scaffold. It shows how ViennaPS
carries material geometry between process steps. It measures common failures
before a large parameter sweep.

[Open the interactive guide](https://kooexperience.com/ViennaPS-HBM/explainer.html)

[Read the engineering case study](CASE_STUDY.md)

## What the code is useful for

- Carrying one geometry through several etch, deposition, fill, and removal
  models.
- Showing how an upstream shape affects downstream access and layer coverage.
- Measuring via width, depth, bow, coating coverage, void topology, and
  material connectivity.
- Testing whether a measurement can distinguish a known failure from a
  prescribed passing control.
- Following one failed geometry through etch, films, and copper fill without
  stitching unrelated images together.
- Mapping a simulated response before spending compute on a larger design of
  experiments.

## What it does not establish

The model settings are not fabrication recipes. They are not calibrated to gas
flow, chamber pressure, plating current, or polish pressure. The current model
also does not predict adhesion, film stress, electrical resistance, wafer-scale
loading, or package behavior.

The void-free copper traveler is a prescribed geometry control. It confirms
that the measurements can recognize the intended shape. It does not validate a
physical electroplating law.

## Where this example fits

This repository is strongest as a teaching and evidence workflow. It shows the
ViennaPS process loop, replays exact saved profiles, measures geometry, and keeps
the source settings attached to each result.

It does not yet fit model parameters to wafer measurements or replace expensive
simulations with a trained surrogate. The surrounding ViennaTools ecosystem
shows how those later stages can work:

- [ViennaFit](https://github.com/ViennaTools/ViennaFit) optimizes ViennaPS model
  parameters against target geometry. It includes critical-dimension and shape
  distance metrics, sensitivity analysis, and several optimization methods.
- [ViennaPS Interpolation Workflow](https://github.com/yozoon/ViennaPS-InterpolationWorkflow)
  extracts geometry features from saved simulations, interpolates between the
  sampled cases, reconstructs a profile, and compares it with a full simulation.
- [ViennaPS LibTorch Example](https://github.com/yozoon/ViennaPS-LibTorch-Example)
  demonstrates using a trained neural estimator inside ViennaPS. It is a small
  integration example, not a calibrated TSV workflow.

The next defensible step for this project is ViennaFit-based etch calibration
against a measured or deliberately defined target profile. A surrogate becomes
useful only after the training cases, held-out checks, and permitted
interpolation range are explicit.

## Project status

The original demonstration was completed and archived. The larger research
objective is not complete. Measurement qualification, controlled failure
reproduction, matched downstream geometry, and a defensible full-traveler
process window remain active work.

- [`program.md`](program.md) defines the current objective, assumed study targets,
  and research guardrails. Its numeric bands are not fab specifications.
- [`RESEARCH_PLAN_V3.md`](RESEARCH_PLAN_V3.md) defines the next research blocks.
- [`NUMERICAL_AUTORESEARCH_PRD.md`](NUMERICAL_AUTORESEARCH_PRD.md) defines the
  feedback loop, error states, early stopping, and numerical-cost study.
- [`docs/current-run.md`](docs/current-run.md) identifies the latest completed
  checkpoint, exact runner, outputs, and blocker.
- [`docs/adaptive-etch-search.md`](docs/adaptive-etch-search.md) defines the
  small sequential search used after screening.
- [`docs/experiment-playbook.md`](docs/experiment-playbook.md) defines what a
  good specification contains, how the search narrows, what autoresearch has
  learned, and how evidence should be stored.
- [`docs/evidence-map.md`](docs/evidence-map.md) links each public claim to saved
  evidence and its limit.
- [`docs/metric-study.md`](docs/metric-study.md) separates core TSV feedback
  from uncalibrated diagnostics such as simulated wall roughness.
- [`docs/code-review-2026-07-18.md`](docs/code-review-2026-07-18.md) records the
  correctness and simplicity audit, including unresolved items.
- [`archive/README.md`](archive/README.md) indexes superseded campaigns and the
  original demo.

## Study method

Each process step follows the same loop:

```text
current geometry + process model + duration
                    |
                    v
               ps.Process(...)
                    |
                    v
updated geometry -> measure -> save -> next step
```

A useful study then follows six rules:

1. Define the defect and its measurement.
2. Test a known failure and a passing control.
3. Reuse the same upstream geometry in downstream comparisons.
4. Control random seeds and repeat stochastic runs.
5. Confirm contrasting states before estimating a boundary.
6. Change the model when tuning cannot represent the required physics.

The complete screening-to-confirmation workflow is summarized in
[`docs/experiment-playbook.md`](docs/experiment-playbook.md). In particular,
assumed teaching bands organize comparisons; they are not fabrication limits.

## Main files

| File | Purpose |
|---|---|
| `tsv_process.py` | Core geometry and process-step helpers. |
| `traveler_metrics.py` | Geometry, topology, and connectivity measurements. |
| `profile_shape_metrics.py` | Wall and floor shape diagnostics. |
| `full_2d_layer_metrics.py` | Regional film coverage and continuity measurements. |
| `layer_process_models.py` | Liner, barrier, and seed deposition models. |
| `morphology_fill_control.py` | Copper morphology controls. |
| `config/process.toml` | Runtime defaults, numerical controls, and assumed comparison targets. |
| `schemas/` | JSON contracts for published evidence and research events. |
| `evidence/` | Committed manifests, rows, checkpoints, reviews, and source hashes. |
| `explainer_template.html` | Source for the interactive guide. |
| `scripts/build/` | Active publication and evidence builders. |
| `tests/` | Runtime-routed checks, executed as Python modules. |
| `scripts/build/build_explainer.py` | Embeds publication data into `explainer.html`. |
| `program.md` | Current objective, assumed study targets, and research guardrails. |
| `docs/current-run.md` | Current research checkpoint and reproduction command. |
| `docs/code-map.md` | Supported code surface and full repository classification. |

Twenty-three completed-campaign builders remain at the root because frozen
evidence cites them or their callers. They are provenance, not the public API.
See [`docs/code-map.md`](docs/code-map.md). Superseded campaigns live under
`archive/`.

Runtime settings for the active teaching path live in `config/process.toml`.
Frozen DOE grids remain in their campaign manifests because those values are
part of the historical experiment record, not global application settings.

## View the guide locally

The tracked HTML file has no server-side dependency:

```bash
git clone https://github.com/haomingkoo/ViennaPS-HBM.git
cd ViennaPS-HBM
python3 -m http.server 8000
```

Open <http://localhost:8000/explainer.html>.

## License

This is proprietary source-available work, not an open-source project.
Personal, non-commercial evaluation is permitted. Any company, university, or
other organization must obtain written permission before internal or external
use. See [`LICENSE`](LICENSE). Third-party components, including `ViennaPS/`,
remain under their own licenses.

## Development environment

The simulation code requires Python, NumPy, Matplotlib, and a source build of
ViennaPS. On macOS, the environment used for this project was built against
Homebrew's VTK, Embree, LLVM OpenMP runtime, and CMake:

```bash
brew install vtk embree libomp cmake
python3.13 -m venv .venv
source .venv/bin/activate
pip install numpy matplotlib pillow pytest
```

Follow the [ViennaPS build instructions](https://github.com/ViennaTools/ViennaPS)
for the bindings and native dependencies.

The current local environment uses ViennaPS 4.6.1 and ViennaLS 5.8.3. The
matched 3D transport bridge has a stricter binary fingerprint and is not part
of the clean-clone smoke test. Its runner fails closed when that exact runtime
is unavailable.

Keep native simulation runtimes separate from the development environment.
The frozen macOS runtime is used only for its verified ViennaPS binary. Install
lint, schema, and browser dependencies in a fresh environment from
`requirements-dev.lock`.

## Checks

GitHub Actions runs Ruff, compiles the Python sources, executes the
dependency-free publication guards, rebuilds the explainer, and checks its
embedded JavaScript. Direct requirements are pinned in `requirements-dev.txt`;
CI installs the hash-locked `requirements-dev.lock`.
Dependabot proposes version updates for review.

Start with the routed checks instead of calling individual test files:

```bash
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python scripts/run_capability_tests.py plan
.venv/bin/python scripts/run_capability_tests.py portable
.venv/bin/python -m scripts.build.build_explainer
```

`stock`, `cu`, `cmp`, and `all` run the simulation-bearing groups after their
exact runtimes pass fingerprint checks. CI contains the authoritative lint,
type-check, evidence-validation, and browser commands.

Enable the fast local pre-push check once per clone:

```bash
git config core.hooksPath .githooks
```

The hook checks the tutorial evidence schemas, provenance, publication data,
and generated HTML before a push. CI still runs the broader lint, type, and
browser suite.

`candidate_cu_replay.json` and `bosch_trajectory_replay.json` are committed
publication data. A clean clone validates and displays them. Regenerating them
requires the ignored source rows and native checkpoints under
`autoresearch-results/`, plus the qualified ViennaPS environment used by this
study:

```bash
.venv/bin/python -m scripts.build.build_candidate_cu_replay
.venv/bin/python -m scripts.build.build_bosch_trajectory_replay
```

The wider test suite requires ViennaPS and the research artifacts used by the
selected test.

## Attempt logging and retry decisions

Prepare one event payload that follows
[`schemas/autoresearch-event.schema.json`](schemas/autoresearch-event.schema.json),
then append it without hash fields:

```bash
.venv/bin/python scripts/autoresearch_event_log.py append run-events.jsonl \
  --event-file event.json
.venv/bin/python scripts/autoresearch_event_log.py validate run-events.jsonl
.venv/bin/python scripts/autoresearch_event_log.py inspect run-events.jsonl
```

The inspect command returns `retryable`, `should_stop`, `run_action`, and the
declared next action as JSON. `--exit-code` returns 10 for the single allowed
transient retry and 20 for a stop; malformed or contradictory evidence returns
1. Deterministic failures, missing measurements, stale provenance, and missed
acceptance criteria never become automatic retries.

## Reproduction boundary

The interactive HTML can be opened from a clean clone. The current repository
does not yet contain every native checkpoint needed to rebuild the complete
teaching traveler from scratch. Until those checkpoints are published, do not
describe `build_screening_traveler.py` as a clean-clone reproduction command.
The smaller 3 × 3 step studies are generated independently by
`build_step_experiments.py`. A clean clone without ViennaPS can still use the
committed `step_experiments.json` when rebuilding the HTML.

The numerical charts are portable: their exact source rows, manifests, review,
and hashes are committed under `evidence/numerical/`. CI rebuilds the chart data
and fails if it differs.

The dry-etch interaction export contains the actual silicon contours from 28
reviewed native checkpoints. The committed JSON and HTML are portable, but
regenerating that export requires the local native checkpoint archive named by
each source row and hash.

The 25-case range-pilot viewer is also portable. Its committed source bundle
contains the validated event rows and extracted final silicon profiles. Rebuilding
the source bundle itself requires the ignored native checkpoints and raw event
logs named in the bundle.

Monte Carlo transport also introduces run-to-run variation. Reproducible
comparisons must record random seeds, geometry inputs, numerical settings, and
saved outputs.

Evidence schemas keep required keys explicit. Unknown values remain `null`;
they are never guessed. Schema or state failures block publication and report
the failing JSON pointer plus the next action.

The interactive step studies are independent 3 × 3 examples. Each one varies
two model inputs and shows only the nine saved outputs. Their checks are
simulation screening limits in model units, not fabrication specifications.
Each viewer states the measurement and what the model does not cover.

## Repository shape

The repository has three lanes: current research at the root, publication data
and the interactive guide, and superseded work under `archive/`. New work should
reuse the active metrics and config; it should not copy an archived campaign
runner as a template.

Campaign evidence should follow the manifest, event ledger, measurement rows,
checkpoints, and review layout in
[`docs/experiment-playbook.md`](docs/experiment-playbook.md). Temporary output
belongs in ignored directories and must not be required to read the published
result.

## Sources

- [ViennaPS process API](https://viennatools.github.io/ViennaPS/process/)
- [ViennaPS simulation domain](https://viennatools.github.io/ViennaPS/domain/)
- [NIST: Metrology Needs for TSV Fabrication](https://www.nist.gov/publications/metrology-needs-tsv-fabrication)
- [NIST: Modeling Extreme Bottom-Up TSV Filling](https://www.nist.gov/publications/modeling-extreme-bottom-filling-through-silicon-vias)

These sources guide the model and measurements. They do not calibrate the
simulation coefficients to a wafer process.

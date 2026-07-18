# Simplified TSV process simulation with ViennaPS

This repository follows one through-silicon via (TSV) through six simulated
handoffs:

1. mask opening;
2. silicon etch;
3. oxide liner;
4. barrier and copper seed;
5. copper fill; and
6. chemical-mechanical planarization (CMP).

The project is a teaching tool and research scaffold. It shows how ViennaPS
carries material geometry between process steps. It measures common failures
before a large parameter sweep.

[Open the interactive guide](https://kooexperience.com/ViennaPS-HBM/explainer.html)

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

## Project status

The original demonstration was completed and archived. The larger research
objective is not complete. Measurement qualification, controlled failure
reproduction, matched downstream geometry, and a defensible full-traveler
process window remain active work.

- [`program.md`](program.md) defines the current objective and hard gates.
- [`RESEARCH_PLAN_V3.md`](RESEARCH_PLAN_V3.md) defines the next research blocks.
- [`NUMERICAL_AUTORESEARCH_PRD.md`](NUMERICAL_AUTORESEARCH_PRD.md) defines the
  feedback loop, error states, early stopping, and numerical-cost study.
- [`docs/current-run.md`](docs/current-run.md) identifies the latest completed
  checkpoint, exact runner, outputs, and blocker.
- [`docs/evidence-map.md`](docs/evidence-map.md) links each public claim to saved
  evidence and its limit.
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
5. Map the pass-to-fail boundary.
6. Change the model when tuning cannot represent the required physics.

## Main files

| File | Purpose |
|---|---|
| `tsv_process.py` | Core geometry and process-step helpers. |
| `traveler_metrics.py` | Geometry, topology, and connectivity measurements. |
| `layer_process_models.py` | Liner, barrier, and seed deposition models. |
| `morphology_fill_control.py` | Copper morphology controls. |
| `config/process.toml` | Runtime defaults, numerical controls, and acceptance limits. |
| `schemas/` | JSON contracts for published evidence and research events. |
| `evidence/numerical/` | Committed rows, manifests, reviews, and hashes behind the numerical charts. |
| `scripts/autoresearch_event_log.py` | Hash-chained attempt log and retry/stop hook. |
| `numerical_performance_data.json` | Citable grid/ray cost and response evidence. |
| `build_screening_traveler.py` | Builds the prescribed teaching traveler. |
| `build_step_experiments.py` | Exports the saved mask, etch, film, and CMP studies. |
| `build_cu_fill_replay.py` | Exports copper surfaces for the interactive replay. |
| `explainer_template.html` | Source for the interactive guide. |
| `build_explainer.py` | Embeds the publication data into `explainer.html`. |
| `program.md` | Current scientific targets and hard gates. |
| `prepare.md` | Research decisions, corrections, and open limits. |
| `docs/evidence-map.md` | Current claims, evidence, status, and limits. |
| `docs/current-run.md` | Current research checkpoint and reproduction command. |

Files prefixed with `foundation_`, `review_`, `build_`, or `test_` support the
staged research checks. Superseded campaigns live under `archive/` and should
not be treated as the current workflow.

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

The same lightweight checks can be run locally:

```bash
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
ruff check tsv_process.py traveler_metrics.py full_2d_layer_metrics.py \
  layer_process_models.py morphology_fill_control.py \
  copper_fill_transport_3d.py build_screening_traveler.py \
  build_cu_fill_replay.py build_step_experiments.py build_explainer.py
ty check --python .venv/bin/python --python-version 3.13 \
  tsv_process.py traveler_metrics.py full_2d_layer_metrics.py \
  layer_process_models.py morphology_fill_control.py \
  copper_fill_transport_3d.py build_screening_traveler.py \
  build_cu_fill_replay.py build_step_experiments.py build_explainer.py
.venv/bin/python test_process_config.py
.venv/bin/python build_cu_fill_replay.py
.venv/bin/python build_explainer.py
.venv/bin/python test_publication_data.py
.venv/bin/python scripts/validate_evidence.py numerical_performance_data.json \
  schemas/numerical-performance.schema.json
.venv/bin/python test_autoresearch_event_schema.py
.venv/bin/python test_autoresearch_event_log.py
playwright install chromium
.venv/bin/python test_explainer_visual.py
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
1. Deterministic failures, missing measurements, stale provenance, and failed
hard gates never become automatic retries.

## Reproduction boundary

The interactive HTML can be opened from a clean clone. The current repository
does not yet contain every native checkpoint needed to rebuild the complete
teaching traveler from scratch. Until those checkpoints are published, do not
describe `build_screening_traveler.py` as a clean-clone reproduction command.
`build_step_experiments.py` also needs the local positive-control fill
checkpoint for its CMP example. A clean clone uses the committed
`step_experiments.json` when rebuilding the HTML.

The numerical charts are portable: their exact source rows, manifests, review,
and hashes are committed under `evidence/numerical/`. CI rebuilds the chart data
and fails if it differs.

Monte Carlo transport also introduces run-to-run variation. Reproducible
comparisons must record random seeds, geometry inputs, numerical settings, and
saved outputs.

Evidence schemas keep required keys explicit. Unknown values remain `null`;
they are never guessed. Schema or state failures block publication and report
the failing JSON pointer plus the next action.

The interactive step studies are independent examples. Their checks are
simulation screening limits in model units. They are not fabrication
specifications. Each viewer states the measurement, the tested range, and the
physics the model does not cover.

## Repository shape

The repository has three lanes: current research at the root, publication data
and the interactive guide, and superseded work under `archive/`. New work should
reuse the active metrics and config; it should not copy an archived campaign
runner as a template.

## Sources

- [ViennaPS process API](https://viennatools.github.io/ViennaPS/process/)
- [ViennaPS simulation domain](https://viennatools.github.io/ViennaPS/domain/)
- [NIST: Metrology Needs for TSV Fabrication](https://www.nist.gov/publications/metrology-needs-tsv-fabrication)
- [NIST: Modeling Extreme Bottom-Up TSV Filling](https://www.nist.gov/publications/modeling-extreme-bottom-filling-through-silicon-vias)

These sources guide the model and measurements. They do not calibrate the
simulation coefficients to a wafer process.

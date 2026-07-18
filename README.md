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

- [`program.md`](program.md) defines the current objective, assumed study targets,
  and research guardrails. Its numeric bands are not fab specifications.
- [`RESEARCH_PLAN_V3.md`](RESEARCH_PLAN_V3.md) defines the next research blocks.
- [`NUMERICAL_AUTORESEARCH_PRD.md`](NUMERICAL_AUTORESEARCH_PRD.md) defines the
  feedback loop, error states, early stopping, and numerical-cost study.
- [`docs/current-run.md`](docs/current-run.md) identifies the latest completed
  checkpoint, exact runner, outputs, and blocker.
- [`docs/adaptive-etch-search.md`](docs/adaptive-etch-search.md) defines the
  small sequential search used after screening.
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

## Main files

| File | Purpose |
|---|---|
| `tsv_process.py` | Core geometry and process-step helpers. |
| `traveler_metrics.py` | Geometry, topology, and connectivity measurements. |
| `profile_shape_metrics.py` | Tutorial-only wall and floor comparison with a target outline. |
| `layer_process_models.py` | Liner, barrier, and seed deposition models. |
| `morphology_fill_control.py` | Copper morphology controls. |
| `config/process.toml` | Runtime defaults, numerical controls, and assumed comparison targets. |
| `schemas/` | JSON contracts for published evidence and research events. |
| `evidence/numerical/` | Committed rows, manifests, reviews, and hashes behind the numerical charts. |
| `scripts/autoresearch_event_log.py` | Hash-chained attempt log and retry/stop hook. |
| `scripts/check_published_evidence.sh` | Fast schema, provenance, and generated-evidence check used locally and in CI. |
| `numerical_performance_data.json` | Citable grid/ray cost and response evidence. |
| `evidence/numerical/ray_benefit_review.json` | Citable ray-count runtime, repeat-spread, and response-movement review. |
| `bosch_tutorial_data.json` | Eighteen six-control dry-etch profiles, 28 factor-pair profiles, measurements, and citations. |
| `bosch_trajectory_replay.json` | Seven replayed checkpoints; the final frame matches a saved native checkpoint. |
| `v3_bosch_clean_ray_ladder.py` | Runs the paired ray-count cost and response-movement study. |
| `build_ray_benefit_review.py` | Summarizes compatible ray studies without treating any setting as truth. |
| `build_screening_traveler.py` | Builds the prescribed teaching traveler. |
| `build_step_experiments.py` | Exports the saved mask, etch, film, and CMP studies. |
| `build_cu_fill_replay.py` | Exports copper surfaces for the interactive replay. |
| `build_candidate_cu_replay.py` | Replays one reviewed failing copper trajectory in the original research environment. |
| `explainer_template.html` | Source for the interactive guide. |
| `build_explainer.py` | Embeds the publication data into `explainer.html`. |
| `program.md` | Current objective, assumed study targets, and research guardrails. |
| `prepare.md` | Research decisions, corrections, and open limits. |
| `docs/evidence-map.md` | Current claims, evidence, status, and limits. |
| `factor_registry.json` / `docs/factor-registry.md` | Schema-validated factor inventory and readable rendering, including hidden controls and range gaps. |
| `active_experiment_contract.json` | Generated list of the controls shown in the teaching studies, their saved values, and criterion evidence class. |
| `pattern_bosch_measurement_contract.json` | Mask and dry-etch measurement definitions plus the unresolved evidence that blocks screening. |
| `evidence/bosch/pattern_bosch_metric_controls.json` | Synthetic straight, shallow, tapered, bowed, narrow-neck, and scalloped controls for the measurement code. |
| `pattern_bosch_factor_projection.json` | Every mask and Bosch registry record classified for range finding, a separate block, accuracy work, or an explicit blocker. |
| `pattern_bosch_range_pilot_design.json` | Frozen 25-case, 12-control coarse range-pilot design. |
| `pattern_bosch_range_pilot_review.json` | Corrected claim-limited review: 20 measured profiles and 5 saved profiles with unavailable wall measurements. |
| `evidence/bosch/range_pilot/source_bundle.json` | Committed event rows and extracted final profiles behind the range-pilot viewer. |
| `docs/range-research.md` | Primary-source review of factor meanings, mathematical bounds, and unsupported range gaps. |
| `docs/range-research-log.json` | Schema-validated search log, including searches that found no transferable range. |
| `docs/screening-doe-plan.md` | Evidence requirements, staged DOE method, feedback, promotion, and stopping rules. |
| `docs/current-run.md` | Current research checkpoint and reproduction command. |
| `docs/adaptive-etch-search.md` | Adaptive etch search, stopping rules, and method choice. |
| `docs/metric-study.md` | Measurement choices, roughness status, and validation plan. |
| `TUTORIAL_PRD.md` | Public teaching requirements and evidence rules. |

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
  build_cu_fill_replay.py build_candidate_cu_replay.py \
  build_step_experiments.py build_explainer.py
ty check --python .venv/bin/python --python-version 3.13 \
  tsv_process.py traveler_metrics.py full_2d_layer_metrics.py \
  layer_process_models.py morphology_fill_control.py \
  copper_fill_transport_3d.py build_screening_traveler.py \
  build_cu_fill_replay.py build_candidate_cu_replay.py \
  build_step_experiments.py build_explainer.py
.venv/bin/python test_process_config.py
.venv/bin/python build_cu_fill_replay.py
.venv/bin/python build_ray_benefit_review.py
.venv/bin/python build_explainer.py
.venv/bin/python test_publication_data.py
.venv/bin/python test_ray_benefit_review.py
.venv/bin/python scripts/validate_evidence.py evidence/numerical/ray_benefit_review.json \
  schemas/ray-benefit-review.schema.json
.venv/bin/python scripts/validate_evidence.py numerical_performance_data.json \
  schemas/numerical-performance.schema.json
.venv/bin/python scripts/validate_evidence.py step_experiments.json \
  schemas/step-experiments.schema.json
.venv/bin/python scripts/validate_evidence.py cu_fill_replay.json \
  schemas/cu-fill-replay.schema.json
.venv/bin/python scripts/validate_evidence.py candidate_cu_replay.json \
  schemas/candidate-cu-replay.schema.json
.venv/bin/python scripts/validate_evidence.py bosch_trajectory_replay.json \
  schemas/bosch-trajectory-replay.schema.json
.venv/bin/python scripts/validate_evidence.py pattern_bosch_measurement_contract.json \
  schemas/pattern-bosch-measurement-contract.schema.json
.venv/bin/python scripts/validate_evidence.py \
  evidence/bosch/pattern_bosch_metric_controls.json \
  schemas/pattern-bosch-metric-controls.schema.json
.venv/bin/python scripts/validate_evidence.py \
  evidence/bosch/range_pilot/source_bundle.json \
  schemas/pattern-bosch-range-pilot-bundle.schema.json
.venv/bin/python scripts/validate_evidence.py pattern_bosch_range_pilot_review.json \
  schemas/pattern-bosch-range-pilot-review.schema.json
.venv/bin/python test_autoresearch_event_schema.py
.venv/bin/python test_autoresearch_event_log.py
playwright install chromium
.venv/bin/python test_explainer_visual.py
```

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
.venv/bin/python build_candidate_cu_replay.py
.venv/bin/python build_bosch_trajectory_replay.py
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

## Sources

- [ViennaPS process API](https://viennatools.github.io/ViennaPS/process/)
- [ViennaPS simulation domain](https://viennatools.github.io/ViennaPS/domain/)
- [NIST: Metrology Needs for TSV Fabrication](https://www.nist.gov/publications/metrology-needs-tsv-fabrication)
- [NIST: Modeling Extreme Bottom-Up TSV Filling](https://www.nist.gov/publications/modeling-extreme-bottom-filling-through-silicon-vias)

These sources guide the model and measurements. They do not calibrate the
simulation coefficients to a wafer process.

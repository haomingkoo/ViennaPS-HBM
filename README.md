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
carries material geometry between process steps. It also demonstrates how to
measure common failures before running a large parameter sweep.

[Open the interactive guide](https://haomingkoo.github.io/ViennaPS-HBM/explainer.html)

## What the code is useful for

- Carrying one geometry through several etch, deposition, fill, and removal
  models.
- Showing how an upstream shape affects downstream access and layer coverage.
- Measuring via width, depth, bow, coating coverage, void topology, and
  material connectivity.
- Testing whether a measurement can distinguish a known failure from a
  prescribed passing control.
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
| `build_screening_traveler.py` | Builds the prescribed teaching traveler. |
| `explainer_template.html` | Source for the interactive guide. |
| `build_explainer.py` | Embeds the publication data into `explainer.html`. |
| `program.md` | Current scientific targets and hard gates. |
| `prepare.md` | Research decisions, corrections, and open limits. |

Files prefixed with `foundation_`, `review_`, `build_`, or `test_` support the
staged research checks. Earlier campaign scripts remain as research history and
should not be treated as the current recommended workflow.

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

## Checks

GitHub Actions runs Ruff, compiles the Python sources, executes the
dependency-free publication guards, rebuilds the explainer, and checks its
embedded JavaScript. Ruff and `ty` are pinned in `requirements-dev.txt`.
Dependabot proposes version updates for review.

The same lightweight checks can be run locally:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
ruff check tsv_process.py traveler_metrics.py full_2d_layer_metrics.py \
  layer_process_models.py morphology_fill_control.py \
  copper_fill_transport_3d.py build_screening_traveler.py build_explainer.py
ty check --python .venv/bin/python --python-version 3.13 \
  tsv_process.py traveler_metrics.py full_2d_layer_metrics.py \
  layer_process_models.py morphology_fill_control.py \
  copper_fill_transport_3d.py build_screening_traveler.py build_explainer.py
.venv/bin/python test_process_config.py
.venv/bin/python build_explainer.py
.venv/bin/python test_publication_data.py
```

The wider test suite requires ViennaPS and the research artifacts used by the
selected test.

## Reproduction boundary

The interactive HTML can be opened from a clean clone. The current repository
does not yet contain every native checkpoint needed to rebuild the complete
teaching traveler from scratch. Until those checkpoints are published, do not
describe `build_screening_traveler.py` as a clean-clone reproduction command.

Monte Carlo transport also introduces run-to-run variation. Reproducible
comparisons must record random seeds, geometry inputs, numerical settings, and
saved outputs.

## Repository shape

The active teaching path is intentionally small. The repository also retains
self-contained campaign runners and reviewers so old results can be audited
against the code that produced them. That history duplicates some manifest,
hashing, and JSONL checks. New work should reuse the active metrics and config;
it should not copy an older campaign runner as a template.

## Sources

- [ViennaPS process API](https://viennatools.github.io/ViennaPS/process/)
- [ViennaPS simulation domain](https://viennatools.github.io/ViennaPS/domain/)
- [NIST: Metrology Needs for TSV Fabrication](https://www.nist.gov/publications/metrology-needs-tsv-fabrication)
- [NIST: Modeling Extreme Bottom-Up TSV Filling](https://www.nist.gov/publications/modeling-extreme-bottom-filling-through-silicon-vias)

These sources guide the model and measurements. They do not calibrate the
simulation coefficients to a wafer process.

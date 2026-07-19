# A simplified TSV process tutorial

This repository follows one two-dimensional shape through a simplified TSV
flow:

```text
mask → silicon etch → liner → barrier → seed → copper → planarization
```

The example is small enough to run while you change the controls. After each
step it measures the geometry that the next step receives.

[Open the interactive guide](https://kooexperience.com/ViennaPS-HBM/explainer.html)

## Run it

```bash
git clone https://github.com/haomingkoo/ViennaPS-HBM.git
cd ViennaPS-HBM
uv run tsv-tutorial
```

That command creates the environment, installs the pinned dependencies, runs
the traveler, and writes `tutorial-output/summary.json`. Install
[uv](https://docs.astral.sh/uv/getting-started/installation/) first if the
command is unavailable.

Windows and Linux use the official ViennaPS wheels. On macOS, install the
native build prerequisites once:

```bash
brew install libomp vtk embree
```

The project builds matching ViennaPS and ViennaLS source revisions on macOS.
This avoids mixing the two native packages, which the ViennaPS installation
guide marks as unsupported. The build is cached after the first run.

## What to tune

All editable controls are in [`config/tutorial.toml`](config/tutorial.toml).

| Step | Main model controls | Measurement feedback |
|---|---|---|
| Mask | Opening width, height, taper | Opening CD and mask height |
| Etch | Cycles, time, wall protection, particle direction | Depth, top/middle/bottom CD, bow |
| Liner | Deposition amount and sticking | Minimum thickness and remaining opening |
| Barrier | Amount and arrival direction | Deep coverage and remaining opening |
| Seed | Amount and arrival direction | Coverage and continuity geometry |
| Copper | Geometric growth amount and direction | Open or closed void and remaining area |
| Planarization | Cut plane | Copper retained after the cut |

Start with the etch controls. Change one setting, rerun the tutorial, and compare
depth with the three CD measurements. Then inspect whether the liner and seed
still reach the lower wall before changing copper.

See [`docs/tuning.md`](docs/tuning.md) for the practical sequence and
[`docs/measurements.md`](docs/measurements.md) for metric definitions.

## Calibrate against measured profiles

The optional calibration path uses ViennaFit to compare simulated geometry
with a reviewed target profile:

```bash
uv sync --extra calibration
```

See [`docs/calibration.md`](docs/calibration.md). Measurements extracted from
FA images must retain the source image, scale, extraction method, and reviewer.
The optimizer should never treat unreviewed image extraction as ground truth.

## What this demonstrates

- A ViennaPS domain carries material geometry from one process to the next.
- Process models move the material boundaries.
- Measurements provide feedback for the next simulation.
- Upstream geometry changes downstream access and fill risk.

The copper step in this compact example is geometric growth, not an
electroplating model. The final step is an ideal plane cut, not a CMP pad and
slurry model. The controls are simulation inputs. Converting them into gas
flow, power, current, chemistry, or pressure requires calibration against wafer
data. See [`docs/model-limits.md`](docs/model-limits.md).

## Repository map

```text
config/tutorial.toml       controls used by the example
src/viennaps_hbm/          process and measurement code
examples/run_tsv_tutorial.py
tests/test_tutorial_smoke.py
docs/                      tuning, measurements, and model limits
```

Research campaigns, raw checkpoints, and historical experiment logs are kept
outside this public tutorial repository.

## Test

```bash
uv run python tests/test_tutorial_smoke.py
```

The test checks that all seven stages execute and return usable measurements.
It does not declare the result to be a fabrication recipe.

## ViennaPS

ViennaPS represents material boundaries with level sets and applies etching or
deposition models to move those boundaries. Its `Process` interface combines a
domain, a model, a duration, and optional numerical controls. See the
[official installation guide](https://viennatools.github.io/ViennaPS/inst/)
and [process documentation](https://viennatools.github.io/ViennaPS/process/).

## License

See [`LICENSE`](LICENSE). ViennaPS and its dependencies remain under their own
licenses.

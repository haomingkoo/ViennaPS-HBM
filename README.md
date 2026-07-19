# Simplified TSV process simulation with ViennaPS

This project follows a simplified two-dimensional TSV shape through six
simulated process steps:

```text
mask opening → silicon etch → liner → barrier and seed → copper fill → polish
```

It shows how ViennaPS carries geometry from one step to the next. It also shows
which measurements reveal common failures such as bowed walls, poor deep-film
coverage, trapped copper voids, and plug loss after polishing.

[Open the interactive guide](https://kooexperience.com/ViennaPS-HBM/explainer.html)
· [Read the case study](CASE_STUDY.md)
· [Download the saved evidence](https://github.com/haomingkoo/ViennaPS-HBM/releases/tag/research-data-2026-07-19)

## What you can learn here

- How mask geometry becomes the input to a dry-etch simulation.
- How etch depth and top, middle, and bottom CD are measured.
- How wall bow and floor shape are measured.
- How liner, barrier, and seed settings affect deep coverage and the remaining
  copper opening.
- How upstream geometry changes copper-fill risk.
- How ray count and grid spacing affect runtime and measured geometry.
- How to design a screening study without treating internal comparison values
  as fabrication specifications.

## What the evidence currently supports

The project demonstrates geometry propagation, measurement checks, and saved
sensitivity studies. The interactive controls replay exact simulated outputs;
they do not interpolate or rerun ViennaPS in the browser.

The project has not established a calibrated fabrication recipe or a validated
full-traveler process window. In particular:

- the focused dry-etch region is provisional and still needs an independent
  numerical confirmation;
- the step-study panels use declared starting shapes and are not one continuous
  candidate recipe;
- the reviewed copper candidate is nearly full by area, but its final topology
  is unresolved at the tested grid;
- seed electrical continuity and physical CMP behavior are outside the current
  geometry checks.

The numerical bands used in the studies are internal comparison values. They
are not wafer specifications.

## View the guide locally

The published HTML has no server-side dependency:

```bash
git clone https://github.com/haomingkoo/ViennaPS-HBM.git
cd ViennaPS-HBM
python3 -m http.server 8000
```

Open <http://localhost:8000/explainer.html>.

## Inspect the data

Large simulation outputs are stored outside the Git history. The
[research-data release](https://github.com/haomingkoo/ViennaPS-HBM/releases/tag/research-data-2026-07-19)
contains:

- `evidence.tar.gz`: reviewed simulation evidence;
- `site-build-inputs.tar.gz`: the exact JSON used to build the guide;
- `autoresearch-results.tar.gz`: raw research-loop outputs;
- `SHA256SUMS`: checksums for every bundle.

[`artifact-manifest.json`](artifact-manifest.json) records each bundle's size,
hash, role, and source revision. The matching research code is preserved at the
[`research-snapshot-2026-07-19` tag](https://github.com/haomingkoo/ViennaPS-HBM/tree/research-snapshot-2026-07-19).

Saved evidence supports quick inspection and review. It does not replace a
runnable experiment. A fully reproducible result identifies:

- the command and configuration;
- the dependency versions;
- the random stream; and
- the expected output.

## Rebuild the publication

Install the locked development tools, run the portable checks, and rebuild the
HTML:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m playwright install chromium
python scripts/run_capability_tests.py portable
python -m scripts.build.build_explainer
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

The portable checks validate evidence schemas and provenance. They also check
the publication data and generated guide. They do not run every native ViennaPS
campaign.

## Run the native simulations

ViennaPS is a native C++ and Python package. Follow the
[official ViennaPS installation guide](https://viennatools.github.io/ViennaPS/inst/)
for your operating system. Keep ViennaPS and ViennaLS on compatible revisions.

The reviewed environment used ViennaPS 4.6.1 and ViennaLS 5.8.3. Native
campaigns also require the source rows and checkpoints named by their evidence
manifests. Start with [`docs/current-run.md`](docs/current-run.md). It records
the latest supported runner and its inputs and outputs. It also states the
unresolved gate.

Do not treat `build_screening_traveler.py` as a clean-clone reproduction
command. The repository does not yet contain every native checkpoint required
to regenerate the complete historical traveler in one command.

## How the study works

Each simulated step uses the same loop:

```text
current geometry + process model + duration
                    ↓
               ps.Process(...)
                    ↓
updated geometry → measure → save → next step
```

A defensible experiment then follows these rules:

1. Define the failure and its measurement.
2. Test a known failure and a clear passing control.
3. Reuse the same upstream geometry in downstream comparisons.
4. Record random streams and repeat stochastic runs.
5. Confirm contrasting outcomes before estimating a boundary.
6. Change the model when its physics cannot represent the required behavior.

See [`docs/experiment-playbook.md`](docs/experiment-playbook.md) for the full
screening-to-confirmation workflow.

## Repository map

| Path | Purpose |
|---|---|
| `config/process.toml` | Runtime settings and internal comparison values. |
| `tsv_process.py` | Core geometry and process-step helpers. |
| `traveler_metrics.py` | Geometry, topology, and connectivity measurements. |
| `profile_shape_metrics.py` | Wall and floor shape measurements. |
| `layer_process_models.py` | Liner, barrier, and seed deposition models. |
| `schemas/` | JSON contracts for evidence and research events. |
| `evidence/` | Reviewed rows, manifests, hashes, and numerical studies. |
| `scripts/build/` | Active evidence and publication builders. |
| `tests/` | Routed validation and simulation checks. |
| `docs/evidence-map.md` | Public claims mapped to evidence and limitations. |
| `docs/code-map.md` | Supported code, frozen provenance, and archived code. |
| `archive/` | Superseded campaigns retained for research history. |

Some completed-campaign builders remain at the repository root because frozen
evidence cites their exact paths and hashes. They are provenance, not the
recommended public interface.

## Development checks

Use the routed checks instead of running individual test files:

```bash
python scripts/run_capability_tests.py plan
python scripts/run_capability_tests.py portable
```

The simulation-bearing groups are `stock`, `cu`, `cmp`, and `all`. They run
only after the required native runtime passes its fingerprint check.

To enable the fast pre-push validation:

```bash
git config core.hooksPath .githooks
```

CI runs formatting and static checks. It also validates evidence, rebuilds the
publication, and runs browser tests. Evidence or schema failures stop
publication instead of silently filling missing values.

## Model boundary

The simulation inputs are not direct equipment settings. Converting model
controls into equipment settings requires calibration against wafer
measurements.

The current models do not predict adhesion or film stress. They also omit
electrical resistance, wafer-scale loading, and package behavior. The copper
measurement controls do not validate electroplating physics. Ideal
planarization does not model pad contact or slurry behavior.

ViennaFit is a possible next step for fitting model parameters to a reviewed
target profile. A surrogate model should come later, after its training range
and held-out checks are defined.

## License

This is proprietary source-available work, not an open-source project.
Personal non-commercial evaluation is permitted. An organization must obtain
written permission before internal or external use. See [`LICENSE`](LICENSE).
Third-party components remain under their own licenses.

## Sources

- [ViennaPS process API](https://viennatools.github.io/ViennaPS/process/)
- [ViennaPS simulation domain](https://viennatools.github.io/ViennaPS/domain/)
- [NIST: Metrology Needs for TSV Fabrication](https://www.nist.gov/publications/metrology-needs-tsv-fabrication)
- [NIST: Modeling Extreme Bottom-Up TSV Filling](https://www.nist.gov/publications/modeling-extreme-bottom-filling-through-silicon-vias)

These sources inform the model and measurements. They do not calibrate the
simulation coefficients to a fabrication process.

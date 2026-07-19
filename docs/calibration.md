# Calibrate model controls against measurements

Calibration asks a narrower question than recipe optimization: which model
coefficients reproduce a measured profile closely enough for the intended
comparison?

ViennaFit can vary ViennaPS parameters and compare the result with a target
level set. It supports profile distances, critical-dimension comparisons,
sensitivity studies, and sequential optimization.

## Minimum input

Keep the original image or measurement file beside a reviewed record containing:

- sample and process-step identifier;
- length unit and pixel-to-length scale;
- depth and top, middle, and bottom CD;
- traced left and right wall coordinates when available;
- extraction method, reviewer, and source-file checksum.

An FA image is evidence, not a numeric target by itself. Segment or trace it,
check the scale and orientation, then approve the resulting profile before a
fit begins. Missing values remain null; they are not inferred.

## ViennaFit connection

Install the pinned optional dependency:

```bash
uv sync --extra calibration
```

Then create a ViennaFit project with the incoming ViennaPS domain and the
reviewed target level set. Wrap one tutorial step as a function of named model
parameters, set defensible parameter bounds, and compare profiles with a shape
metric such as Chamfer distance. Track depth and CD separately so a visually
close but too-shallow via cannot win.

The official interface is:

```python
project = fit.Project("etch-calibration", "calibration-runs").initialize()
project.setInitialDomain(initial_domain)
project.setTargetLevelSet(reviewed_target)

optimization = fit.Optimization(project)
optimization.setProcessSequence(etch_process)
optimization.setVariableParameters(parameter_bounds)
optimization.setDistanceMetrics(primaryMetric="CCH", additionalMetrics=["CCD"])
optimization.apply(numEvaluations=budget)
```

The target domain, bounds, evaluation budget, and acceptance checks must come
from the study record. The tutorial does not invent them.

Sources: [ViennaFit documentation](https://viennatools.github.io/ViennaFit/) and
[official examples](https://github.com/ViennaTools/ViennaFit/tree/main/examples).

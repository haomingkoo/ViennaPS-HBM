# TSV simulation measurements

Use the smallest set of measurements that can detect a process failure or
change a downstream decision. A value produced by the mesh is not automatically
a product requirement.

## Core feedback

| Step | Primary measurements | Decision supported |
|---|---|---|
| Mask | opening width, height, taper, placement | Is the etch input usable? |
| Etch | depth; top, middle, bottom and minimum width; taper; bow; neck | Is the via shape usable downstream? |
| Liner | left, right and floor thickness; continuity; remaining opening | Is the via insulated without closing it? |
| Barrier and seed | left, right and floor thickness; continuity; remaining opening | Can copper reach a connected seed surface? |
| Copper | open and sealed voids; seam; overburden | Is the fill connected and void-free at the resolved scale? |
| Polish | field clearance; plug connection; recess; material loss | Is the field clear without cutting the stack? |

These measurements remain separate. A good bow value cannot compensate for a
missed depth or a disconnected seed layer.

## Compact etch-profile comparison

The tutorial adds four descriptive values for comparing a saved 2D outline
with its dotted teaching target:

- `profile_shape_rmse` gives the walls and floor equal weight, so the longer
  walls cannot hide a poor floor;
- `profile_max_deviation` reports the largest sampled miss;
- `profile_symmetry_rms` combines wall-center shift and paired floor-height
  differences;
- `floor_flatness_pv` reports the vertical distance between the highest and
  lowest sampled points on the floor. The page calls this floor unevenness;
- depth remains separate and visible.

The page displays the three distance values as a percentage of target width.
The JSON retains model units. These values rank saved shapes only. They have no
pass limit and are not wafer specifications. If the floor has missing or
multiple intersections, the floor-dependent values are `null` and the reason
is retained instead of choosing an intersection.

The tutorial-only calculation is implemented in `profile_shape_metrics.py`.
The established traveler measurements remain unchanged so earlier evidence
keeps its original code provenance.

## Roughness status

The repository already reports `scallop_rms` from
`traveler_metrics.etch_profile_metrics_2d`. It samples the wall between 10% and
85% of the etched depth. It fits a cubic profile and reports the RMS radial
residual. This is a repeatable simulated-profile diagnostic. It is not an AFM
surface-roughness measurement and has no calibrated product limit.

Published studies make the mechanism worth testing. Bosch scallops can disturb
dielectric and barrier coverage, concentrate stress and affect electrical
leakage. Other work uses RMS sidewall roughness as a measured surface statistic.
Those sources justify studying roughness; they do not supply a limit for this
normalized 2D model.

## Small validation study

1. Test smooth, tapered, bowed and known-frequency scalloped synthetic walls.
2. Check grid and ray sensitivity using the same physical profile and stopping rule.
3. Compare RMS residual, peak-to-peak scallop amplitude and scallop pitch.
4. Carry the profiles into liner and seed deposition.
5. Keep a roughness measure only if it adds useful information beyond bow,
   minimum width and local coverage.

Do not require identical decimals across numerical settings. Reject a faster
setting when it changes a major shape, failure mode, pass/fail decision, tuning
direction or useful boundary. Ignore smaller differences that remain below the
measurement resolution, observed run variation and remaining product margin.

## Sources and applicability

| Source | What it supports | What it does not support |
|---|---|---|
| [Ertl and Selberherr, 3D level-set Bosch simulation](https://doi.org/10.1016/j.mee.2009.05.011) | Monte Carlo ray transport, level-set profile evolution and cycle-time/profile studies | A universal ray count or TSV recipe |
| [Ranganathan et al., Bosch roughness and TSV behavior](https://doi.org/10.1088/0960-1317/18/7/075018) | Rough sidewalls can affect barrier uniformity and electrical leakage | A limit for `scallop_rms` |
| [Nagarajan et al., TSV sidewall scallops](https://doi.org/10.1109/TCPMT.2011.2160395) | Scallops can affect dielectric/barrier reliability and leakage | Calibration of the current simulator |
| [Automated 3D-AFM sidewall roughness measurement](https://pmc.ncbi.nlm.nih.gov/articles/PMC8904671/) | RMS roughness is a measurable sidewall statistic | Equivalence between AFM data and a 2D mesh residual |
| [Son, quantitative TSV etch-profile evaluation](https://doi.org/10.4218/etrij.14.0113.0828) | Sidewall angle, undercut, scallop and curvature are useful profile descriptors | A universal combined score or limit for this simulated target |
| [ViennaPS process documentation](https://viennatools.github.io/ViennaPS/process/) | Implemented process, ray, advection and coverage controls | Recommended accuracy settings for this geometry |

Searches covered NIST, ViennaPS/TU Wien, IEEE, AVS/AIP, IOP/JMM, ECS and
optimization proceedings. Inaccessible publisher pages and searches with no
applicable parameter ranges remain evidence gaps, not evidence of zero effect.

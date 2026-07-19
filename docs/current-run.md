# Current research checkpoint

The focused 2D etch study has found a small region with target-depth profiles,
controlled top/middle/bottom CD, low bow, and near-vertical walls. The larger
full-traveler objective is not complete, and no fabrication recipe or process
window is authorized.

## Current working result

| Item | Current evidence |
|---|---|
| Focused controls | ion-arrival directionality and directional removal strength |
| Exploration profile | grid 0.0025 and 500 rays per point, only near the tested focused region |
| Promotion check | repeat at 1,000 rays with matched geometry and process inputs |
| Representative saved profile | depth 1.249; top/middle/bottom CD 0.331/0.323/0.322; bow 0.005 |
| Remaining shape gap | saved floors are rounded or uneven; floor metrics are not qualified hard gates |
| Claim | a repeatable local simulated wall-profile region, not an equipment recipe |

The selected profile and its replay are published in
[`bosch_tutorial_data.json`](../bosch_tutorial_data.json) and
[`bosch_trajectory_replay.json`](../bosch_trajectory_replay.json).

## Why 500 rays is used for exploration

The five-level ladder ran 250, 500, 750, 1,000, and 2,000 rays on three etched
shapes with three random streams each. Runtime rose from a median 54.1 seconds
at 500 rays to 206.5 seconds at 2,000 rays. Measurement movement and repeated
spread did not decrease monotonically with ray count.

A separate focused bridge found that grid 0.0025 was 3.6 to 5.0 times faster
than 0.00125 on the tested cases. Grid 0.005 changed the selected width profile
and was stopped. At grid 0.0025, 1,000 rays took 2.0 to 2.3 times longer than
500 rays without uniformly smaller response movement.

This supports a local compute policy, not an accuracy percentage. There is no
known numerical ground truth. A different geometry, aspect ratio, process
model, unstable profile, or boundary case requires a new paired check.

Sources:

- [`evidence/numerical/bosch_ray_current_grid_ladder_review.json`](../evidence/numerical/bosch_ray_current_grid_ladder_review.json)
- [`evidence/numerical/v3_bosch_grid_speed_bridge_phase_b_review.json`](../evidence/numerical/v3_bosch_grid_speed_bridge_phase_b_review.json)

## What autoresearch currently does

The event ledger freezes cases, records terminal states, permits one declared
transient retry, preserves failures, and stops on invalid evidence or repeated
model limitations. Follow-up experiments are still selected by reviewed code
and frozen manifests. There is no live surrogate or autonomous ask/tell search
yet.

The saved data are not ready for automatic recipe ranking. Only one focused
cell has three repeats, and floor shape is unavailable in one of the twelve
focused runs. The next optimizer must earn authority on held-out predictions;
it cannot be trusted because it returns a candidate.

## Next experiment

1. Qualify floor peak-to-valley, center relief, and symmetry on synthetic and
   saved positive/negative shapes.
2. Run a small repeated, floor-measurable batch around the focused region at
   the exploration profile.
3. Fit separate response models for depth, each CD, wall shape, floor shape,
   validity, and runtime.
4. Ask for three cases: predicted improvement, uncertain boundary, and diverse
   exploration.
5. Confirm promoted cases with unseen streams and 1,000 rays.

[ViennaFit](https://github.com/ViennaTools/ViennaFit) is the preferred first
calibration tool to evaluate because it already supports target geometries,
critical-dimension and shape-distance metrics, sensitivity analysis, and bounded
optimization. It still needs measured or explicitly defined target profiles;
adopting it does not make uncalibrated model controls into equipment settings.

The search and stopping rules are in
[`adaptive-etch-search.md`](adaptive-etch-search.md). The complete experiment
contract is summarized in [`experiment-playbook.md`](experiment-playbook.md).

## Clean-clone checks

```bash
python build_numerical_evidence_bundle.py --check
python build_numerical_performance_data.py
python scripts/validate_evidence.py numerical_performance_data.json \
  schemas/numerical-performance.schema.json
python test_publication_data.py
```

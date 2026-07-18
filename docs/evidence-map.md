# Evidence map

This page separates demonstrated results from research still in progress. The
simulation outputs are evidence about the implemented models. They are not
fabrication recipes.

The status names the highest supported claim: **Implementation verified**,
**Measurement verified**, **Numerically characterized**, **Model-space no-go
in sampled space**, **Pending**, or **Withdrawn/archived**. A lower level does
not imply physical calibration or experimental validation.

| Question | Status | Authoritative source | Saved evidence | Limit |
|---|---|---|---|---|
| Is the full research objective complete? | Pending | [`program.md`](../program.md) | [`RESEARCH_PLAN_V3.md`](../RESEARCH_PLAN_V3.md) | A robust full-traveler process window has not been found. |
| Which phase-one measurements and conclusions were rejected? | Withdrawn/archived | [`FOUNDATION_REAUDIT.md`](../FOUNDATION_REAUDIT.md) | [`TEST_GATE_AUDIT.md`](../TEST_GATE_AUDIT.md), [`archive/`](../archive/) | Retired scores are historical only. |
| Does the ideal mask geometry respond to opening size? | Implementation verified | [`build_step_experiments.py`](../build_step_experiments.py) | [`step_experiments.json`](../step_experiments.json) | This is direct geometry input; lithography is not modeled. |
| Does the saved 2D etch trajectory meet every study screen? | Model-space no-go in sampled space | [`build_step_experiments.py`](../build_step_experiments.py) | [`step_experiments.json`](../step_experiments.json) | One fixed trajectory is replayed; no sampled cycle passes all screens. |
| Do liner settings change coverage and remaining aperture? | Numerically characterized | [`layer_process_models.py`](../layer_process_models.py) | [`step_experiments.json`](../step_experiments.json) | Geometry trends are shown; a passing boundary is not bracketed. |
| Do barrier and seed geometry controls change deep coverage? | Numerically characterized | [`layer_process_models.py`](../layer_process_models.py) | [`step_experiments.json`](../step_experiments.json) | Physical qualification is pending; seed has no independent acceptance limit. |
| Can the software carry one geometry lineage through successive handoffs? | Implementation verified | [`build_step_experiments.py`](../build_step_experiments.py) | Failure-chain frames and parent hashes in [`step_experiments.json`](../step_experiments.json) | This reproduces model-geometry propagation, not fab causality or electrical seed failure. |
| Can the 2D topology measurement distinguish prescribed void and no-void controls? | Measurement verified | [`traveler_metrics.py`](../traveler_metrics.py) | [`cu_fill_replay.json`](../cu_fill_replay.json), [`step_experiments.json`](../step_experiments.json) | This validates the measurement on prescribed controls, not electroplating physics. |
| Does the tested 2D suppressor law create enough bottom-up growth? | Model-space no-go in sampled space | [`foundation_copper_fill_transport_boundary_confirmation.py`](../foundation_copper_fill_transport_boundary_confirmation.py) | [`publication_interim_data.json`](../publication_interim_data.json) | The matched 3D mechanism check is still required. |
| Does ideal planarization move Cu to the selected height? | Implementation verified | [`build_step_experiments.py`](../build_step_experiments.py) | [`step_experiments.json`](../step_experiments.json) | Physical CMP qualification is pending; pad contact, pressure, and wafer-scale effects are absent. |
| How do sampled grid and ray settings change runtime and Bosch measurements? | Numerically characterized | [`build_numerical_performance_data.py`](../build_numerical_performance_data.py) | [`numerical_performance_data.json`](../numerical_performance_data.json), validated by [`schemas/numerical-performance.schema.json`](../schemas/numerical-performance.schema.json) | Grid turning points come from one coarse-grid recipe. The 500-ray bridge is provisional because more than ray count changed. |
| Is there a fab-ready recipe or validated full process window? | Pending | [`program.md`](../program.md) | None | Calibration and full matched 2D/3D confirmation remain open. |

## Reproduction levels

- **Clean clone:** open or rebuild the committed interactive guide from its
  committed JSON datasets.
- **ViennaPS environment:** run the active unit and research checks that do not
  require unpublished native checkpoints.
- **Original research environment:** rebuild studies that depend on local native
  checkpoints. The README states those boundaries explicitly.

Archived code and results are indexed in [`archive/README.md`](../archive/README.md).
Their hashes are recorded in [`archive/SHA256SUMS`](../archive/SHA256SUMS).

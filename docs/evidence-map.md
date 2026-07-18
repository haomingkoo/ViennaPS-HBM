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
| How do fab controls relate to the tutorial controls? | Pending | [Oxford DRIE](https://plasma.oxinst.com/technologies/dsie/plasmapro-100-estrelas-dsie), [Applied liner](https://www.appliedmaterials.com/us/en/product-library/producer-invia-cvd.html), [Applied barrier/seed](https://www.appliedmaterials.com/us/en/product-library/endura-ventura-pvd.html), [Lam electroplating](https://newsroom.lamresearch.com/Tech-Brief-Elements-of-Electroplating), [Applied CMP](https://www.appliedmaterials.com/il/en/semiconductor/semiconductor-technologies/cmp.html) | Equipment-to-model chain in [`explainer.html`](../explainer.html) | The sources support mechanisms and equipment influences. A quantitative mapping to ViennaPS coefficients remains uncalibrated. |
| Does the ideal mask geometry respond to opening size? | Implementation verified | [`build_step_experiments.py`](../build_step_experiments.py) | [`step_experiments.json`](../step_experiments.json) | This is direct geometry input; lithography is not modeled. |
| How do paired Bosch controls change the profile? | Numerically characterized | [`review_v3_bosch_cheap_interactions.py`](../review_v3_bosch_cheap_interactions.py) | 28 reviewed rows in [`evidence/numerical/v3_bosch_cheap_interactions_review.json`](../evidence/numerical/v3_bosch_cheap_interactions_review.json) and exported contours in [`bosch_tutorial_data.json`](../bosch_tutorial_data.json) | All 28 discovery cases are valid and 8 pass the geometry checks. They locate coupled failure regions at 500 rays; they do not confirm a recipe or process window. |
| Is a Bosch recipe or fitted interior response surface confirmed? | Pending | [`v3_bosch_clean_ray_ladder.py`](../v3_bosch_clean_ray_ladder.py) | 18 completed interior cases are preserved under [`evidence/numerical/`](../evidence/numerical/) | Three interior cases pass, but no fitted surface or finalist has completed independent 2,000-ray confirmation. |
| Do liner settings change coverage and remaining aperture? | Numerically characterized | [`layer_process_models.py`](../layer_process_models.py) | [`step_experiments.json`](../step_experiments.json) | Geometry trends are shown; a passing boundary is not bracketed. |
| Do barrier and seed geometry controls change deep coverage? | Numerically characterized | [`layer_process_models.py`](../layer_process_models.py) | [`step_experiments.json`](../step_experiments.json) | Physical qualification is pending; seed has no independent acceptance limit. |
| Can the software carry one geometry lineage through successive handoffs? | Implementation verified | [`build_step_experiments.py`](../build_step_experiments.py) | Failure-chain frames and parent hashes in [`step_experiments.json`](../step_experiments.json) | This reproduces model-geometry propagation, not fab causality or electrical seed failure. |
| Can the 2D topology measurement distinguish prescribed void and no-void controls? | Measurement verified | [`traveler_metrics.py`](../traveler_metrics.py) | [`cu_fill_replay.json`](../cu_fill_replay.json), [`step_experiments.json`](../step_experiments.json) | This validates the measurement on prescribed controls, not electroplating physics. |
| Does the tested 2D suppressor law create enough bottom-up growth? | Model-space no-go in sampled space | [`foundation_copper_fill_transport_boundary_confirmation.py`](../foundation_copper_fill_transport_boundary_confirmation.py) | [`publication_interim_data.json`](../publication_interim_data.json) | The matched 3D mechanism check is still required. |
| Does ideal planarization move Cu to the selected height? | Implementation verified | [`build_step_experiments.py`](../build_step_experiments.py) | [`step_experiments.json`](../step_experiments.json) | Physical CMP qualification is pending; pad contact, pressure, and wafer-scale effects are absent. |
| How do sampled grid and ray settings change runtime and Bosch measurements? | Numerically characterized | [`build_numerical_performance_data.py`](../build_numerical_performance_data.py) | [`numerical_performance_data.json`](../numerical_performance_data.json), validated by [`schemas/numerical-performance.schema.json`](../schemas/numerical-performance.schema.json) | Grid turning points come from one coarse-grid recipe. The 500-ray bridge is provisional because more than ray count changed. |
| Why was 250 rays rejected for broad screening? | Numerically characterized | [`review_v3_bosch_low_ray_qualification.py`](../review_v3_bosch_low_ray_qualification.py) | 250-ray row 7 and 2,000-ray row 9 in [`evidence/numerical/`](../evidence/numerical/); exact values are summarized in [`docs/current-run.md`](current-run.md) | The width result crosses the 0.060 limit. The comparison also changed random streams and stopping intervals, so it is commissioning evidence rather than a clean ray-only test. |
| Is simulated wall roughness a qualified product requirement? | Pending | [`traveler_metrics.py`](../traveler_metrics.py) | Definition and validation plan in [`docs/metric-study.md`](metric-study.md) | `scallop_rms` is a cubic-detrended 2D profile diagnostic. It is not calibrated to AFM roughness and has no product limit. |
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

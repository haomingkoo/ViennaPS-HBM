#!/bin/sh
set -eu

python=${PYTHON:-python3}

"$python" build_numerical_evidence_bundle.py --check
"$python" build_ray_benefit_review.py
"$python" build_numerical_performance_data.py

while read -r document schema; do
  "$python" scripts/validate_evidence.py "$document" "$schema"
done <<'EOF'
evidence/numerical/ray_benefit_review.json schemas/ray-benefit-review.schema.json
numerical_performance_data.json schemas/numerical-performance.schema.json
bosch_tutorial_data.json schemas/bosch-tutorial.schema.json
step_experiments.json schemas/step-experiments.schema.json
cu_fill_replay.json schemas/cu-fill-replay.schema.json
candidate_cu_replay.json schemas/candidate-cu-replay.schema.json
bosch_trajectory_replay.json schemas/bosch-trajectory-replay.schema.json
factor_registry.json schemas/factor-registry.schema.json
active_experiment_contract.json schemas/active-experiment-contract.schema.json
pattern_bosch_measurement_contract.json schemas/pattern-bosch-measurement-contract.schema.json
evidence/bosch/pattern_bosch_metric_controls.json schemas/pattern-bosch-metric-controls.schema.json
evidence/bosch/pattern_bosch_unavailable_profile_review.json schemas/pattern-bosch-unavailable-profile-review.schema.json
pattern_bosch_factor_projection.json schemas/pattern-bosch-factor-projection.schema.json
pattern_bosch_range_pilot_review.json schemas/pattern-bosch-range-pilot-review.schema.json
evidence/numerical/bosch_grid_preflight.json schemas/bosch-grid-preflight.schema.json
evidence/numerical/bosch_ray_phase_a_review.json schemas/bosch-ray-phase-a-review.schema.json
evidence/numerical/bosch_ray_phase_b_review.json schemas/bosch-ray-phase-b-review.schema.json
evidence/numerical/v3_bosch_focused_ion_map_review.json schemas/v3-bosch-focused-ion-map-review.schema.json
evidence/numerical/v3_bosch_grid_speed_bridge_review.json schemas/v3-bosch-grid-speed-bridge-review.schema.json
evidence/numerical/v3_bosch_grid_speed_bridge_phase_b_review.json schemas/v3-bosch-grid-speed-bridge-phase-b-review.schema.json
docs/range-research-log.json schemas/range-research-log.schema.json
EOF

"$python" test_evidence_schema.py
"$python" test_ray_benefit_review.py
"$python" test_autoresearch_event_schema.py
"$python" test_autoresearch_event_log.py
git diff --exit-code -- numerical_performance_data.json evidence/numerical/ray_benefit_review.json

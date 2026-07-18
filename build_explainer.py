"""Assemble the public explainer from committed publication data."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MARKER = "/*__DATA__*/"
INPUTS = {
    "campaign": "publication_campaign_data.json",
    "interim": "publication_interim_data.json",
    "cu_replay": "cu_fill_replay.json",
    "step_experiments": "step_experiments.json",
    "numerical_performance": "numerical_performance_data.json",
    "ray_benefit": "evidence/numerical/ray_benefit_review.json",
    "bosch_tutorial": "bosch_tutorial_data.json",
    "bosch_trajectory": "bosch_trajectory_replay.json",
    "candidate_cu_replay": "candidate_cu_replay.json",
    "active_contract": "active_experiment_contract.json",
    "pattern_bosch_factor_projection": "pattern_bosch_factor_projection.json",
    "pattern_bosch_range_pilot": "pattern_bosch_range_pilot_review.json",
}


def main():
    data = {
        name: json.loads((ROOT / path).read_text())
        for name, path in INPUTS.items()
    }
    template = (ROOT / "explainer_template.html").read_text()
    if template.count(MARKER) != 1:
        raise ValueError("explainer template must contain exactly one data marker")
    html = template.replace(MARKER, json.dumps(data, separators=(",", ":")))
    output = ROOT / "explainer.html"
    output.write_text(html)
    print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

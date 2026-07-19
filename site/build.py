"""Build the static explainer from reviewed saved-result inputs."""

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
MARKER = "/*__DATA__*/"
INPUTS = {
    "campaign": "publication_campaign_data.json",
    "interim": "publication_interim_data.json",
    "cu_replay": "cu_fill_replay.json",
    "step_experiments": "step_experiments.json",
    "numerical_performance": "numerical_performance_data.json",
    "ray_benefit": "evidence/numerical/ray_benefit_review.json",
    "ray_current_grid": "evidence/numerical/bosch_ray_current_grid_ladder_review.json",
    "bosch_tutorial": "bosch_tutorial_data.json",
    "bosch_trajectory": "bosch_trajectory_replay.json",
    "candidate_cu_replay": "candidate_cu_replay.json",
    "active_contract": "active_experiment_contract.json",
    "pattern_bosch_factor_projection": "pattern_bosch_factor_projection.json",
    "pattern_bosch_range_pilot": "pattern_bosch_range_pilot_review.json",
}


def build(input_dir, output_dir):
    """Write the explainer and its linked evidence files."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = {
        name: json.loads((input_dir / path).read_text())
        for name, path in INPUTS.items()
    }
    template = (ROOT / "site/explainer_template.html").read_text()
    if template.count(MARKER) != 1:
        raise ValueError("explainer template must contain one data marker")
    (output_dir / "explainer.html").write_text(
        template.replace(MARKER, json.dumps(data, separators=(",", ":")))
    )
    (output_dir / "index.html").write_text(
        '<meta http-equiv="refresh" content="0; url=explainer.html">\n'
    )
    for path in INPUTS.values():
        destination = output_dir / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_dir / path, destination)
    settings = output_dir / "config/tutorial.toml"
    settings.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config/tutorial.toml", settings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", default="public")
    args = parser.parse_args()
    build(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()

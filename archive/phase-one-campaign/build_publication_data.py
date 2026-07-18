"""Build compact, standalone HTML data from checkpointed traveler evidence."""
from __future__ import annotations

import base64
import ast
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "autoresearch-results" / "full_campaign"
OUTPUT = ROOT / "publication_campaign_data.json"


def wired_factor_count() -> int:
    source = Path(__file__).with_name("joint_process_doe.py")
    tree = ast.parse(source.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "SPACE" for target in node.targets):
            return len(ast.literal_eval(node.value))
    raise RuntimeError("joint_process_doe.SPACE not found")


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))]


def aggregate(source: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in source:
        grouped[row["name"]].append(row)
    result = []
    for name, group in grouped.items():
        recipe = group[0]["recipe"]
        scores = [row["total_score"] for row in group]
        result.append({
            "name": name,
            "recipe": {key: recipe[key] for key in (
                "liner_sticking", "fill_thick", "fill_iso", "cmp_mult"
            )},
            "runs": len(group),
            "p90": percentile(scores, 0.9),
            "worst": max(scores),
            "mean_score": statistics.mean(scores),
            "mean_gap": statistics.mean(row["tip_gap"] for row in group),
            "mean_dish": statistics.mean(row["cmp_dish"] for row in group),
            "mask_consumed_runs": sum(bool(row["cmp_mask_consumed"]) for row in group),
            "min_step_passes": min(row["step_pass_count"] for row in group),
            "full_pass_runs": sum(bool(row["full_target_pass"]) for row in group),
        })
    return sorted(result, key=lambda item: item["name"])


def image_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


stage_dirs = [
    "gen_001_pilot_reproduction", "gen_002_bosch_variance",
    "gen_003_broad_screen", "gen_004_shared_interactions",
    "gen_005_downstream_expansion", "gen_006_fill_iso_boundary",
    "gen_007_unseen_seed_confirmation", "gen_008_process_window",
    "gen_009_window_finalist_confirmation",
]
stage_rows = {name: rows(CAMPAIGN / name / "raw_rows.jsonl") for name in stage_dirs}
window_rows = stage_rows["gen_008_process_window"]
finalist_rows = stage_rows["gen_009_window_finalist_confirmation"]
data = {
    "total_travelers": sum(len(value) for value in stage_rows.values()),
    "wired_factor_count": wired_factor_count(),
    "stages": [
        {"id": "G001", "label": "Reproduce", "design": "2 reference recipes x 4 runs = 8 simulations",
         "rows": 8, "question": "Do the existing reference recipes still produce the same failures?",
         "result": "Yes. Both still fail liner coverage, Cu fill, and CMP.",
         "next": "Measure run-to-run variation before comparing more recipes."},
        {"id": "G002", "label": "Measure noise", "design": "2 recipes x 16 runs = 32 simulations",
         "rows": 32, "question": "How many repeats are needed for a fair comparison?",
         "result": "Four repeats are enough for screening; sixteen are used for final decisions.",
         "next": "Search all 17 tuning knobs across broad ranges."},
        {"id": "G003", "label": "Broad screen", "design": "128 recipes x 4 runs = 512 simulations",
         "rows": 512, "question": "Can any broad combination pass all six process steps?",
         "result": "No. The best recipes pass four steps; Cu fill and CMP still fail.",
         "next": "Check whether downstream effects are real or caused by different etched shapes."},
        {"id": "G004", "label": "Fair comparison", "design": "64 downstream recipes x 4 shared shapes = 256 simulations",
         "rows": 256, "question": "Do liner, fill, and CMP results change when every recipe starts from the same etched via?",
         "result": "The same fill and CMP failures remain. They were not caused by random DRIE shape differences.",
         "next": "Search wider liner, barrier, fill, and CMP ranges."},
        {"id": "G005", "label": "Wider search", "design": "128 downstream recipes x 4 shared shapes = 512 simulations",
         "rows": 512, "question": "Does a wider downstream search contain a recipe that fills the via and preserves the mask?",
         "result": "No. Fill and CMP still fail. The best fill result sits at the edge of the tested range.",
         "next": "Expand that edge before deciding whether the setting is truly best."},
        {"id": "G006", "label": "Test the edge", "design": "60 boundary recipes x 4 shared shapes = 240 simulations",
         "rows": 240, "question": "Will a larger isotropic fill fraction close the centerline void?",
         "result": "No. The gap stays open, and 184 simulations also remove the CMP mask.",
         "next": "Stop widening this setting and retest the two best mask-safe recipes."},
        {"id": "G007", "label": "Retest", "design": "2 recipes x 16 new shapes = 32 simulations",
         "rows": 32, "question": "Do the two best recipes stay consistent on new etched shapes?",
         "result": "The lower-dish recipe stays consistent. The smaller-gap recipe sometimes loses liner coverage.",
         "next": "Perturb the stable recipe to map its nearby operating region."},
        {"id": "G008", "label": "Map nearby", "design": "81 nearby recipes x 4 shared shapes = 324 simulations",
         "rows": 324, "question": "Is there a nearby region that improves fill and CMP without breaking earlier steps?",
         "result": "48 recipes preserve the mask, but none passes all six steps.",
         "next": "Retest the best nearby recipe on sixteen new shapes."},
        {"id": "G009", "label": "Confirm", "design": "2 recipes x 16 new shapes = 32 simulations",
         "rows": 32, "question": "Does the nearby candidate beat the previous best recipe?",
         "result": "No. Both pass the first four steps and fail Cu fill and CMP in all 32 runs.",
         "next": "Change the fill and CMP models before spending more compute on these same settings."},
    ],
    "window": aggregate(window_rows),
    "finalists": aggregate(finalist_rows),
    "finalist_seeds": [{
        "name": row["name"], "seed_index": row["replicate"],
        "score": row["total_score"], "tip_gap": row["tip_gap"],
        "dish": row["cmp_dish"], "step_passes": row["step_pass_count"],
        "mask_consumed": row["cmp_mask_consumed"],
    } for row in finalist_rows],
    "visuals": {
        "best_miss": image_uri(CAMPAIGN / "gen_005_downstream_expansion" / "figures" / "best_miss.png"),
        "mask_failure": image_uri(CAMPAIGN / "gen_005_downstream_expansion" / "figures" / "mask_failure.png"),
    },
    "gate_summary": [
        {"step": "Mask opening", "target": "width 0.30; mask height 0.30", "final": "pass 16/16", "status": "pass"},
        {"step": "Silicon DRIE", "target": "depth 1.25 +/- 0.10; width error <=0.06; bulge <=0.03", "final": "pass 16/16", "status": "pass"},
        {"step": "SiO2 liner", "target": "thickness >=0.020; coverage >=0.995", "final": "pass 16/16", "status": "pass"},
        {"step": "Barrier/seed", "target": "thickness >=0.012; coverage >=0.985", "final": "pass 16/16", "status": "pass"},
        {"step": "Cu fill", "target": "thickness >=0.150; centerline tip gap 0", "final": "fail 16/16", "status": "miss"},
        {"step": "CMP", "target": "dish 0; mask survives", "final": "fail 16/16", "status": "miss"},
    ],
}

OUTPUT.write_text(json.dumps(data, separators=(",", ":")))
print(f"wrote {OUTPUT.name}: {data['total_travelers']} saved simulations")

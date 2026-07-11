"""Build compact, standalone HTML data from checkpointed traveler evidence."""
from __future__ import annotations

import base64
import ast
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
CAMPAIGN = ROOT / "autoresearch-results" / "full_campaign"
OUTPUT = ROOT / "publication_campaign_data.json"


def wired_factor_count() -> int:
    tree = ast.parse((ROOT / "joint_process_doe.py").read_text())
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
with (ROOT / "autoresearch-results" / "results.tsv").open() as f:
    score_history = [{**row, "iteration": int(row["iteration"]), "metric": float(row["metric"])}
                     for row in csv.DictReader((line for line in f if not line.startswith("#")), delimiter="\t")]

data = {
    "total_travelers": sum(len(value) for value in stage_rows.values()),
    "wired_factor_count": wired_factor_count(),
    "score_history": score_history,
    "stages": [
        {"id": "G001", "design": "2 anchors x 4 seeds", "rows": 8,
         "hypothesis": "Historical anchors reproduce under the canonical full-traveler score.",
         "decision": "Pilot anchors remain liner/fill/CMP misses.",
         "next": "Measure Bosch stochastic variation before ranking recipes."},
        {"id": "G002", "design": "2 anchors x 16 fresh seeds", "rows": 32,
         "hypothesis": "The pilot ranking is stable enough to choose a broad-screen replicate policy.",
         "decision": "Four seeds screen; 16 seeds decide finalist stability.",
         "next": "Run a broad wired-space screen with four replicates."},
        {"id": "G003", "design": "128 recipes x 4 seeds", "rows": 512,
         "hypothesis": "A feasible full traveler exists within the 17 wired recipe factors.",
         "decision": "Broad wired-space screen finds no full traveler.",
         "next": "Hold robust upstream anchors fixed and isolate downstream interactions."},
        {"id": "G004", "design": "64 downstream arms x 4 shared geometries", "rows": 256,
         "hypothesis": "Apparent downstream effects persist when every arm sees the same Bosch geometry.",
         "decision": "Fill/CMP failure persists without Bosch-noise confounding.",
         "next": "Widen liner, barrier, fill, and CMP ranges around both anchors."},
        {"id": "G005", "design": "128 expanded arms x 4 shared geometries", "rows": 512,
         "hypothesis": "A wider downstream search contains a mask-surviving fill/CMP region.",
         "decision": "No fill or CMP pass; high fill-isotropy boundary expands.",
         "next": "Test beyond fill_iso=0.20 before calling the edge point optimal."},
        {"id": "G006", "design": "60 boundary arms x 4 shared geometries", "rows": 240,
         "hypothesis": "More isotropic fill closes the remaining centerline void.",
         "decision": "Fill isotropy through 0.60 does not close the gap; 184 mask-loss rows.",
         "next": "Stop widening that knob and confirm the credible four-step misses."},
        {"id": "G007", "design": "2 finalists x 16 unseen seeds", "rows": 32,
         "hypothesis": "The two best mask-surviving misses retain their ranking on unseen geometries.",
         "decision": "Lower-dish four-step miss is stable; gap-focused arm loses liner stability.",
         "next": "Perturb the stable reference to map the local robust-miss window."},
        {"id": "G008", "design": "3^4 local grid x 4 shared geometries", "rows": 324,
         "hypothesis": "A local region preserves upstream gates and improves both fill and CMP.",
         "decision": "48/81 settings preserve mask; 0/81 passes all six steps.",
         "next": "Confirm the new four-seed morphology candidate before comparison."},
        {"id": "G009", "design": "2 post-window finalists x 16 unseen seeds", "rows": 32,
         "hypothesis": "The local-window candidate remains preferable on sixteen unseen geometries.",
         "decision": "Both remain stable four-step misses; fill and CMP fail 32/32.",
         "next": "Accept the model-space ceiling and specify the missing CEAC/CMP physics."},
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
        {"step": "Pattern", "target": "width 0.30; mask height 0.30", "final": "pass 16/16", "status": "pass"},
        {"step": "Bosch etch", "target": "depth 1.25 +/- 0.10; width error <=0.06; bulge <=0.03", "final": "pass 16/16", "status": "pass"},
        {"step": "Liner", "target": "thickness >=0.020; coverage >=0.995", "final": "pass 16/16", "status": "pass"},
        {"step": "Barrier/seed", "target": "thickness >=0.012; coverage >=0.985", "final": "pass 16/16", "status": "pass"},
        {"step": "Cu fill", "target": "thickness >=0.150; centerline tip gap 0", "final": "fail 16/16", "status": "miss"},
        {"step": "CMP", "target": "dish 0; mask survives", "final": "fail 16/16", "status": "miss"},
    ],
}

OUTPUT.write_text(json.dumps(data, separators=(",", ":")))
print(f"wrote {OUTPUT.name}: {data['total_travelers']} checkpointed travelers")

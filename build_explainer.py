"""Assemble explainer.html from explainer_template.html + explainer_data.json."""
import json

with open("explainer_data.json") as f:
    data = json.load(f)

with open("sweep_top4_results.json") as f:
    doe800 = json.load(f)

# compact [etch_time, neutral_sticking, initial_etch_time, neutral_rate, depth, bulge]
# rows for the full 800-point DOE -- lets the explorer look up any of the 4
# real knobs exactly, not just the 2 rendered dimensions.
data["doe800"] = [
    [r["etch_time"], r["neutral"], r["initial_etch_time"], r["neutral_rate"],
     round(r["depth"], 3) if r["depth"] is not None else None,
     round(r["bulge"], 4) if r["bulge"] is not None else None]
    for r in doe800["results"]
]
data["doe800_axes"] = {
    "etch_time": doe800["etch_times"], "neutral_sticking": doe800["neutral_sticking"],
    "initial_etch_time": doe800["initial_etch_times"], "neutral_rate": doe800["neutral_rates"],
}

with open("explainer_template.html") as f:
    template = f.read()

html = template.replace("/*__DATA__*/", json.dumps(data, separators=(",", ":")))

with open("explainer.html", "w") as f:
    f.write(html)

print("wrote explainer.html")

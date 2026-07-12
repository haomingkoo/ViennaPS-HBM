"""Assemble the public explainer from the audited campaign dataset."""
import json

with open("publication_campaign_data.json") as f:
    data = {"campaign": json.load(f)}

with open("publication_interim_data.json") as f:
    data["interim"] = json.load(f)

with open("explainer_template.html") as f:
    template = f.read()

html = template.replace("/*__DATA__*/", json.dumps(data, separators=(",", ":")))

with open("explainer.html", "w") as f:
    f.write(html)

print("wrote explainer.html")

"""Assemble explainer.html from explainer_template.html + explainer_data.json."""
import json

with open("explainer_data.json") as f:
    data = json.load(f)

with open("explainer_template.html") as f:
    template = f.read()

html = template.replace("/*__DATA__*/", json.dumps(data, separators=(",", ":")))

with open("explainer.html", "w") as f:
    f.write(html)

print("wrote explainer.html")

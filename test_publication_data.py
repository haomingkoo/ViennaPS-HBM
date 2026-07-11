"""Small publication guard: the public report must match final campaign evidence."""
import json
from html.parser import HTMLParser
from pathlib import Path

data = json.loads(Path("publication_campaign_data.json").read_text())
assert data["total_travelers"] == 1948
assert data["wired_factor_count"] == 17
assert len(data["score_history"]) == 12
assert len(data["window"]) == 81
assert sum(not row["mask_consumed_runs"] for row in data["window"]) == 48
assert all(row["full_pass_runs"] == 0 for row in data["window"])
assert len(data["finalist_seeds"]) == 32
assert all(row["step_passes"] == 4 for row in data["finalist_seeds"])
assert all(row["tip_gap"] > 0 and row["dish"] > 0 for row in data["finalist_seeds"])
assert all(value.startswith("data:image/png;base64,") for value in data["visuals"].values())

template = Path("explainer_template.html").read_text()
html = Path("explainer.html").read_text()
for required in ("id=\"tutorial\"", "id=\"autoresearch\"", "id=\"history-plot\"",
                 "id=\"window-plot\"", "id=\"seed-plot\"", "id=\"visual-reads\""):
    assert required in template
assert "Using ViennaPS to research a complete TSV traveler" in html
assert '"total_travelers":1948' in html
assert "Adopted as production" not in html
assert "All 4 real knobs" not in html
assert "only 2 real continuous knobs" not in html
assert "18 wired recipe factors" not in html
assert "aria-valuetext" in template
assert "model length" in template


class MarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.range_ids, self.label_fors, self.images = [], [], set(), []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "input" and attrs.get("type") == "range":
            self.range_ids.append(attrs.get("id"))
        if tag == "label" and attrs.get("for"):
            self.label_fors.add(attrs["for"])
        if tag == "img":
            self.images.append(attrs)


audit = MarkupAudit()
audit.feed(template)
assert len(audit.ids) == len(set(audit.ids)), "duplicate HTML id"
assert all(input_id in audit.label_fors for input_id in audit.range_ids)
assert all(image.get("src") and image.get("alt") for image in audit.images)
print("publication campaign data checks: PASS")

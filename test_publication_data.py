"""Small publication guard: the public report must match final campaign evidence."""
import json
from html.parser import HTMLParser
from pathlib import Path

data = json.loads(Path("publication_campaign_data.json").read_text())
interim = json.loads(Path("publication_interim_data.json").read_text())
assert data["total_travelers"] == 1948
assert data["wired_factor_count"] == 17
assert "score_history" not in data
assert len(data["window"]) == 81
assert sum(not row["mask_consumed_runs"] for row in data["window"]) == 48
assert all(row["full_pass_runs"] == 0 for row in data["window"])
assert len(data["finalist_seeds"]) == 32
assert all(row["step_passes"] == 4 for row in data["finalist_seeds"])
assert all(row["tip_gap"] > 0 and row["dish"] > 0 for row in data["finalist_seeds"])
assert all(value.startswith("data:image/png;base64,") for value in data["visuals"].values())
assert interim["status"] == "interim"
assert interim["selected_foundation_cases"] == 376
assert interim["reviewed_logical_cells"] == 384
assert sum(interim["selected_case_accounting"].values()) == 376
assert interim["bosch"]["passing_cycle"] == 13
assert interim["bosch"]["saved_shape_count"] == 4
assert 1.15 <= interim["bosch"]["depth_min"] <= interim["bosch"]["depth_max"] <= 1.35
assert interim["layers"]["qualification_rows"] == 12
assert interim["layers"]["baseline_liner_passes"] == 0
assert interim["layers"]["baseline_barrier_seed_passes"] == 0
assert interim["layers"]["exploratory_screening_authorized"]
assert not interim["layers"]["final_recipe_acceptance_authorized"]
assert interim["cu_structural"]["candidate_passes"] == 0
assert interim["cu_structural"]["prescribed_bottom_up_passes"] == 2
assert interim["cu_transport"]["raw_cases"] == 168
assert interim["cu_transport"]["valid_cases"] == 168
assert interim["cu_transport"]["logical_designs"] == 21
assert interim["cu_transport"]["passing_cross_tier_designs"] == 0
assert len(interim["cu_transport"]["tier_designs"]) == 42
assert interim["cu_confirmation"]["logical_cells"] == 128
assert interim["cu_confirmation"]["metric_valid_cells"] == 128
assert interim["cu_confirmation"]["parent_reuses"] == 8
assert interim["cu_confirmation"]["new_executions"] == 120
assert interim["cu_confirmation"]["class_changing_numerical_interactions"] == 0
assert interim["cu_confirmation"]["numerical_artifacts"] == 0
assert interim["cu_confirmation"]["decision"]["classification"] == "lower_sticking_boundary_expansion_required"
assert interim["cu_boundary"]["logical_cells"] == 24
assert interim["cu_boundary"]["metric_valid_cells"] == 24
assert interim["cu_boundary"]["new_executions"] == 24
assert interim["cu_boundary"]["matched_control_cells"] == 8
assert interim["cu_boundary"]["reflection_convergence"]["converged"]
assert not interim["cu_boundary"]["boundary_trend"]["continued_boundary_improvement"]
assert interim["cu_boundary"]["boundary_trend"]["improves_every_stream_in_both_tiers"]
assert interim["cu_boundary"]["multiresponse_paired_directions"]["responses"][
    "worst_floor_to_each_lower_flux_ratio"
]["improved_count"] == 8
assert interim["cu_boundary"]["realized_kinematic_ratio_by_tier"]["continuity"][
    "stream_pass_count"
] == 0
assert interim["cu_boundary"]["realized_kinematic_ratio_by_tier"]["nominal_hbm"][
    "stream_pass_count"
] == 0
assert interim["cu_boundary"]["analytic_envelope"]["evaluation_status"] == (
    "not_evaluated_preliminary_flux_gate_failed"
)
assert interim["cu_boundary"]["decision"]["classification"] == (
    "two_dimensional_transport_no_go_requires_matched_3d_before_pivot"
)
assert interim["cu_boundary"]["decision"]["matched_3d_required"]
assert not interim["cu_boundary"]["decision"]["morphology_authorized"]
assert not interim["cmp"]["recipe_doe_authorized"]
assert len(interim["source_artifacts"]) == 12
assert all(len(source["sha256"]) == 64 for source in interim["source_artifacts"])

template = Path("explainer_template.html").read_text()
html = Path("explainer.html").read_text()
for required in ("id=\"latest-checkpoint\"", "id=\"current\"", "id=\"mechanism-explorer\"", "id=\"boundary-atlas\"", "id=\"actions\"", "id=\"why-order\"", "id=\"cu-screen\"",
                 "id=\"transport-surface\"", "id=\"transport-boundary\"", "id=\"tutorial\"", "id=\"autoresearch\"",
                 "id=\"stage-tabs\"", "id=\"window-plot\"", "id=\"seed-plot\"",
                 "id=\"visual-reads\"", "id=\"references\""):
    assert required in template
assert "Using ViennaPS to research a complete TSV traveler" in html
assert '"total_travelers":1948' in html
assert '"selected_foundation_cases":376' in html
assert "What the first 24 reruns changed" in html
assert "These results define the next experiment; they do not solve the full traveler." in html
assert "What the new experiments have taught us" in html
assert "Six handoffs, not one void problem" in html
assert "See how an upstream shape changes the Cu-fill risk" in html
assert "The response surfaces that will define the process window" in html
assert "FOUNDATION CHECK COMPLETE" in html
assert "SELECTED HANDOFF PASSES 4/4" not in html
assert "What to tune next, and what each move risks" in html
assert "This is the success criterion, not a claimed result" in html
assert "https://www.nist.gov/publications/metrology-needs-tsv-fabrication" in html
assert "https://viennatools.github.io/ViennaPS/process/" in html
assert "Adopted as production" not in html
assert "All 4 real knobs" not in html
assert "only 2 real continuous knobs" not in html
assert "18 wired recipe factors" not in html
assert "aria-valuetext" in template
assert "model length" in template
for banned in ("audited wired model space", "one canonical traveler",
               "No compliant full traveler", "model-limited misses",
               "fab-calibrated DOE"):
    assert banned not in template


class MarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.range_ids, self.label_fors = [], [], set()
        self.images, self.buttons, self.links = [], [], []

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
        if tag == "button":
            self.buttons.append(attrs)
        if tag == "a":
            self.links.append(attrs)


audit = MarkupAudit()
audit.feed(template)
assert len(audit.ids) == len(set(audit.ids)), "duplicate HTML id"
assert all(input_id in audit.label_fors for input_id in audit.range_ids)
assert all(image.get("src") and image.get("alt") for image in audit.images)
assert all(button.get("type") == "button" for button in audit.buttons)
assert all(link.get("href") for link in audit.links)
assert 'rel="canonical" href="https://kooexperience.com/ViennaPS-HBM/explainer.html"' in template
print("publication campaign data checks: PASS")

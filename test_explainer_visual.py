"""Render the explainer and exercise its simulation replay."""

from pathlib import Path

from playwright.sync_api import sync_playwright


def assert_copper_geometry(page):
    geometry = (
        page.locator("#fill-replay-figure path")
        .nth(1)
        .evaluate(
            """element => {
            const box = element.getBBox();
            const style = getComputedStyle(element);
            return {
                pathLength: element.getTotalLength(),
                width: box.width,
                height: box.height,
                visibility: style.visibility,
                opacity: Number(style.opacity),
                stroke: style.stroke,
            };
        }"""
        )
    )
    assert geometry["pathLength"] > 0.1
    assert geometry["width"] > 0
    assert geometry["height"] > 0
    assert geometry["visibility"] == "visible"
    assert geometry["opacity"] > 0
    assert geometry["stroke"] != "none"


def assert_step_viewers(page):
    viewer_ids = ["mask", "liner", "barrier", "seed", "cmp"]
    assert page.locator("[data-output-viewer]").count() == len(viewer_ids) + 1
    assert page.locator('[data-output-viewer="copper"]').count() == 1
    assert page.locator("#step-output-list [data-output-viewer]").evaluate_all(
        "elements => elements.map(element => element.dataset.outputViewer)"
    ) == ["mask", "liner", "barrier", "seed", "copper", "cmp"]
    assert page.locator('[data-output-viewer="bosch"]').count() == 0
    assert page.locator("#step-output-list .evidence-badge").count() == 5
    assert page.locator("#step-output-list .boundary-result").count() == 5
    assert (
        "pass the stated geometry check"
        not in page.locator("#step-output-list").inner_text()
    )
    for viewer_id in viewer_ids:
        viewer = page.locator(f'[data-output-viewer="{viewer_id}"]')
        assert viewer.count() == 1
        controls = viewer.locator("[data-parameter]")
        assert controls.count() == (3 if viewer_id == "mask" else 2)
        assert viewer.locator(".output-causal span").count() == 5
        geometry_path = viewer.locator("path[data-material]").last
        geometry = geometry_path.evaluate(
            """element => {
                const box = element.getBBox();
                return {length: element.getTotalLength(), width: box.width, height: box.height};
            }"""
        )
        assert geometry["length"] > 0
        assert geometry["width"] > 0
        assert geometry["height"] > 0
        original_path = geometry_path.get_attribute("d")
        controls.nth(0).fill(controls.nth(0).get_attribute("max"))
        controls.nth(1).fill(controls.nth(1).get_attribute("max"))
        assert geometry_path.get_attribute("d") != original_path

    assert "3/3 purely directional cases are disconnected" in page.locator(
        '[data-output-viewer="barrier"] .boundary-result'
    ).inner_text()
    assert "Removal 0.18 reaches the modeled field plane" in page.locator(
        '[data-output-viewer="cmp"] .boundary-result'
    ).inner_text()
    summary = page.locator("#saved-results-summary")
    assert summary.locator(":scope > div").count() == 4
    assert "28 valid saved pair cases" in summary.inner_text()
    assert "6/6 purely directional layers are disconnected" in summary.inner_text()
    assert "unresolved seam transition" in summary.inner_text()

    chain = page.locator("#failure-chain-viewer")
    start_path = chain.locator('path[data-chain-material="silicon"]').get_attribute("d")
    chain.get_by_role("button", name="Copper fill", exact=True).click()
    assert "Diagnostic continuation" in chain.locator(".output-status").inner_text()
    assert "traps a void" in chain.locator(".output-status").inner_text().lower()
    assert chain.locator('path[data-chain-material="copper"]').count() == 1
    assert (
        chain.locator('path[data-chain-material="silicon"]').get_attribute("d")
        != start_path
    )


def assert_numerical_evidence(page):
    response = page.locator("#numerical-response-chart")
    assert response.locator("circle").count() == 4
    assert "observed spread" in page.locator("#numerical-response-caption").inner_text()
    page.get_by_role("button", name="Ray sampling").click()
    page.select_option("#numerical-metric", "cd_bottom")
    assert response.locator("circle").count() == 4
    assert "Bottom width" in page.locator("#numerical-response-caption").inner_text()
    phase_b = page.locator("#phase-b-ray-chart")
    assert phase_b.locator(".phase-b-row").count() == 5
    assert phase_b.locator(".phase-b-mark").count() == 13
    assert phase_b.locator(".phase-b-mark.changed").count() == 4
    assert "3 of 3 different" in phase_b.inner_text()
    assert "depth band" in phase_b.inner_text()
    assert "1 of 3 different" in phase_b.inner_text()
    assert "bow band" in phase_b.inner_text()
    mismatch = page.locator("#phase-b-mismatch-chart")
    assert mismatch.locator(".phase-b-pair").count() == 4
    assert mismatch.locator(".phase-b-lane").count() == 8
    assert "1.3506" in mismatch.inner_text()
    assert "1.3466" in mismatch.inner_text()
    assert "inside" in mismatch.inner_text()
    assert "outside" in mismatch.inner_text()
    assert "same 13 etch cases" in page.locator("#phase-b-takeaway").inner_text()
    assert "median was 3.7×" in page.locator("#phase-b-runtime").inner_text().lower()
    assert page.locator('a[href*="numerical_performance_data.json"]').count() == 1


def assert_bosch_interactions(page):
    lab = page.locator("#bosch-interaction-lab")
    assert lab.locator("#bosch-corners button").count() == 4
    assert "Observed corners:" in lab.locator("#bosch-pair-result").inner_text()
    assert "saved simulated profiles" in lab.inner_text().lower()
    assert "These are not simulated equipment inputs" in lab.inner_text()
    assert lab.locator(".bosch-measure").count() >= 5
    assert lab.locator(".bosch-depth").count() == 2
    first_path = lab.locator("#bosch-profile path").nth(1).get_attribute("d")
    lab.locator("#bosch-corners button").nth(2).click()
    assert lab.locator("#bosch-profile path").nth(1).get_attribute("d") != first_path
    page.select_option("#bosch-interaction-select", "ion_source_exponent|ion_rate")
    assert lab.locator("#bosch-corners button").count() == 4
    assert "2/4 are inside" in lab.locator("#bosch-pair-result").inner_text()
    assert "Maximum width error" in lab.locator("#bosch-read").inner_text()
    assert lab.locator('a[href*="v3_bosch_cheap_interactions_rows.jsonl"]').count() == 1


def assert_range_pilot(page):
    study = page.locator("#pattern-bosch-range-pilot")
    buttons = study.locator("#pilot-case-grid button")
    assert buttons.count() == 25
    assert study.locator('#pilot-case-grid button[data-state="legacy_row_complete"]').count() == 18
    assert study.locator('#pilot-case-grid button[data-state="legacy_low_movement_row"]').count() == 2
    assert study.locator('#pilot-case-grid button[data-state="legacy_row_incomplete"]').count() == 5
    assert "no factor effects" in study.inner_text().lower()
    assert "does not locate a failure boundary" in study.inner_text().lower()
    profile = study.locator("#pilot-profile path")
    first_path = profile.get_attribute("d")
    unavailable = study.locator('#pilot-case-grid button[data-state="legacy_row_incomplete"]').first
    unavailable.click()
    assert profile.get_attribute("d") != first_path
    assert "etch measurement" in study.locator("#pilot-read").inner_text().lower()
    assert "Twelve controls changed together" in study.locator("#pilot-read").inner_text()
    assert study.locator('a[href="evidence/bosch/range_pilot/source_bundle.json"]').count() == 2


def assert_active_factor_contract(page):
    rows = page.locator("#active-factor-rows tr")
    assert rows.count() == 12
    assert "range finding" in page.locator("#knobs-guide").inner_text().lower()
    assert page.locator('a[href="active_experiment_contract.json"]').count() == 1
    factor_scope = page.locator("#pattern-bosch-factor-scope")
    assert "12 · Main range finding" in factor_scope.inner_text()
    assert "2 · Mask erosion block" in factor_scope.inner_text()
    assert "11 · Fixed choices" in factor_scope.inner_text()
    assert "6 · Assumed study targets" in factor_scope.inner_text()
    assert "2 · Save callbacks" in factor_scope.inner_text()
    assert "1 · Model limitation" in factor_scope.inner_text()
    assert "only a few controls" in factor_scope.inner_text()
    assert (
        page.evaluate("document.getElementById('knobs-guide').nextElementSibling.id")
        == "numerical-tuning"
    )


def assert_measurement_atlas(page):
    atlas = page.locator("#etch-measurement-atlas")
    profile = atlas.locator("path")
    assert profile.count() == 1
    geometry = profile.evaluate(
        "element => ({length: element.getTotalLength(), stroke: getComputedStyle(element).stroke})"
    )
    assert geometry["length"] > 1
    assert geometry["stroke"] != "none"
    text = atlas.inner_text()
    for label in ("Etch depth", "Top width", "Middle width", "Bottom width"):
        assert label in text
    assert (
        atlas.locator('a[href="pattern_bosch_measurement_contract.json"]').count() == 1
    )


def assert_saved_trajectories(page):
    bosch_path = page.locator("#bosch-cycle-figure path").nth(1)
    first_bosch_path = bosch_path.get_attribute("d")
    page.locator("#bosch-cycle-slider").fill("6")
    assert bosch_path.get_attribute("d") != first_bosch_path
    assert "Final profile" in page.locator("#bosch-cycle-read h4").inner_text()
    assert "after cycle 18" in page.locator("#bosch-cycle-read").inner_text()

    candidate_path = page.locator("#candidate-cu-figure path").last
    first_candidate_path = candidate_path.get_attribute("d")
    first_candidate_metrics = page.locator("#candidate-cu-read").inner_text()
    page.locator("#candidate-cu-slider").fill("9")
    assert page.locator("#candidate-cu-read").inner_text() != first_candidate_metrics
    assert page.locator("#candidate-cu-figure .cu-warning").count() == 0
    page.locator("#candidate-cu-slider").fill("10")
    assert candidate_path.get_attribute("d") != first_candidate_path
    assert (
        "Stop: a narrow seam cannot be resolved"
        in page.locator("#candidate-cu-read h4").inner_text()
    )
    assert page.locator("#candidate-cu-figure .cu-warning").count() == 1
    assert "Lowest copper point" in page.locator("#candidate-cu-read").inner_text()


def main():
    url = Path("explainer.html").resolve().as_uri()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(url)
        page.wait_for_selector("#fill-replay-figure svg")
        page.wait_for_selector('[data-output-viewer="cmp"] svg')
        assert_step_viewers(page)
        assert_numerical_evidence(page)
        assert_active_factor_contract(page)
        assert_measurement_atlas(page)
        assert_range_pilot(page)
        assert_bosch_interactions(page)
        assert_saved_trajectories(page)

        page.get_by_role("button", name="Wall growth faster").click()
        page.locator("#fill-progress-slider").fill("23")
        assert_copper_geometry(page)
        assert page.locator("#fill-replay-read h4").first.inner_text() == "Void trapped"
        wall_path = page.locator("#fill-replay-figure path").nth(1).get_attribute("d")

        page.get_by_role("button", name="Floor growth faster").click()
        page.locator("#fill-progress-slider").fill("23")
        assert_copper_geometry(page)
        assert (
            page.locator("#fill-replay-read h4").first.inner_text() == "Void-free fill"
        )
        floor_path = page.locator("#fill-replay-figure path").nth(1).get_attribute("d")
        assert floor_path != wall_path
        assert not page_errors

        page.set_viewport_size({"width": 390, "height": 844})
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - window.innerWidth"
        )
        assert overflow <= 0
        atlas_scroll = page.locator("#etch-measurement-atlas figure").evaluate(
            "element => ({client: element.clientWidth, scroll: element.scrollWidth})"
        )
        assert atlas_scroll["scroll"] > atlas_scroll["client"]
        browser.close()


if __name__ == "__main__":
    main()
    print("rendered explainer checks: PASS")

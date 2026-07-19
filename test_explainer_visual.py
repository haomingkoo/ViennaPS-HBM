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
    assert page.locator("[data-output-viewer]").count() == len(viewer_ids)
    assert page.locator('[data-output-viewer="copper"]').count() == 0
    assert page.locator("#step-output-list [data-traveler-step]").evaluate_all(
        "elements => elements.map(element => element.dataset.travelerStep)"
    ) == ["mask", "bosch", "liner", "barrier", "seed", "copper", "cmp"]
    assert page.locator("#step-output-list .evidence-badge").count() == 6
    assert page.locator("#step-output-list .boundary-result").count() == 7
    assert page.locator("#step-output-list .step-code").count() == 7
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

    assert (
        "3/3 purely directional cases are disconnected"
        in page.locator('[data-output-viewer="barrier"] .boundary-result').inner_text()
    )
    assert (
        "Removal 0.18 reaches the modeled field plane"
        in page.locator('[data-output-viewer="cmp"] .boundary-result').inner_text()
    )
    summary = page.locator("#saved-results-summary")
    assert summary.locator(":scope > div").count() == 4
    assert "28 valid saved pair cases" in summary.inner_text()
    assert "6/6 purely directional layers are disconnected" in summary.inner_text()
    assert "unresolved seam transition" in summary.inner_text()

    assert page.locator("#failure-chain-viewer").count() == 0
    handoff_status = page.locator("#step-output-studies .boundary-result").filter(
        has_text="Current handoff status"
    )
    assert "improve the etch floor" in handoff_status.inner_text()


def assert_numerical_evidence(page):
    runtime = page.locator("#ray-runtime-chart")
    spread = page.locator("#ray-spread-chart")
    movement = page.locator("#ray-movement-chart")
    assert runtime.locator("rect").count() == 5
    assert spread.locator("rect").count() == 5
    assert movement.locator("rect").count() == 4
    assert "3.8× as long" in page.locator("#ray-ladder-takeaway").inner_text()
    page.select_option("#ray-benefit-metric", "cd_bottom")
    assert (
        "bottom width movement"
        in page.locator("#ray-ladder-takeaway").inner_text().lower()
    )
    page.select_option("#ray-panel", "narrow_profile")
    assert page.locator("#ray-profile-overlay path").count() == 6
    profile_width = page.locator("#ray-profile-overlay path").nth(1).evaluate(
        "element => element.getBoundingClientRect().width"
    )
    assert profile_width > 200

    response = page.locator("#numerical-response-chart")
    assert response.locator("circle").count() == 4
    assert "observed spread" in page.locator("#numerical-response-caption").inner_text()
    page.select_option("#numerical-metric", "cd_bottom")
    assert response.locator("circle").count() == 4
    assert "Bottom width" in page.locator("#numerical-response-caption").inner_text()
    assert (
        page.locator('a[href*="bosch_ray_current_grid_ladder_review.json"]').count()
        == 1
    )


def assert_bosch_interactions(page):
    lab = page.locator("#bosch-interaction-lab")
    assert lab.locator("#bosch-corners button").count() == 4
    assert "Observed corners:" in lab.locator("#bosch-pair-result").inner_text()
    assert "saved simulated profiles" in lab.inner_text().lower()
    assert "Calibration — Fit from data" in lab.inner_text()
    assert lab.locator("#bosch-pair-picker button").count() == 7
    assert lab.locator("#bosch-pair-picker button[aria-pressed='true']").count() == 1
    assert lab.locator(".bosch-measure").count() >= 5
    assert lab.locator(".bosch-depth").count() == 2
    first_path = lab.locator("#bosch-profile path").nth(1).get_attribute("d")
    lab.locator("#bosch-corners button").nth(2).click()
    assert lab.locator("#bosch-profile path").nth(1).get_attribute("d") != first_path
    lab.locator(
        "#bosch-pair-picker button[data-pair='ion_source_exponent|ion_rate']"
    ).click()
    assert lab.locator("#bosch-corners button").count() == 4
    assert "2/4 are inside" in lab.locator("#bosch-pair-result").inner_text()
    assert "Top / middle / bottom CD" in lab.locator("#bosch-read").inner_text()
    assert "Sidewall angle" in lab.locator("#bosch-read").inner_text()
    assert lab.locator('a[href*="v3_bosch_cheap_interactions_rows.jsonl"]').count() == 1


def assert_bosch_multifactor(page):
    lab = page.locator("#bosch-multifactor-lab")
    assert page.evaluate(
        "document.getElementById('bosch-multifactor-lab').compareDocumentPosition(document.getElementById('bosch-interaction-lab')) & Node.DOCUMENT_POSITION_FOLLOWING"
    )
    assert lab.locator("#bosch-multifactor-map .factor-axis").count() == 6
    assert lab.locator("#bosch-multifactor-map .factor-run").count() == 18
    assert lab.locator("#bosch-multifactor-map .factor-run.selected").count() == 1
    assert "six model controls changed together" in lab.inner_text().lower()
    assert "does not interpolate" in lab.inner_text().lower()
    profile = lab.locator("#bosch-multifactor-profile path").nth(1)
    first_path = profile.get_attribute("d")
    lab.locator("#bosch-multifactor-index").fill("1")
    assert profile.get_attribute("d") != first_path
    readout = lab.locator("#bosch-multifactor-read").inner_text()
    assert "Etch phase time per cycle" in readout
    assert "Neutral surface-reaction probability" in readout
    assert "Top / middle / bottom CD" in readout
    assert "Bottom-shape diagnostic" in readout
    screening = lab.locator("#bosch-screening-result").inner_text()
    assert "Largest observed linear movements" in screening
    assert "directional removal strength" in screening.lower()
    assert "passivation added per cycle" in screening.lower()
    assert lab.locator('a[href="bosch_tutorial_data.json"]').count() == 1


def assert_focused_etch(page):
    lab = page.locator("#focused-etch-map")
    assert lab.locator("#focused-etch-grid button").count() == 9
    assert lab.locator("#focused-etch-grid button[aria-pressed='true']").count() == 1
    assert "3 saved runs" in lab.inner_text()
    profile = lab.locator("#focused-etch-profile path").nth(1)
    first_path = profile.get_attribute("d")
    lab.locator("#focused-etch-repeat").click()
    assert profile.get_attribute("d") != first_path
    assert "Run 2 of 3" in lab.inner_text()
    assert "Floor peak-to-valley" in lab.inner_text()
    assert lab.locator('a[href*="v3_bosch_focused_ion_map_rows.jsonl"]').count() == 1


def assert_range_pilot(page):
    study = page.locator("#pattern-bosch-range-pilot")
    text = study.inner_text()
    assert "Why the first etch measurements were archived" in text
    assert "Still usable" in text
    assert "Withdrawn" in text
    assert "Correction" in text
    assert "old etch values are not used" in text
    assert study.locator("#pilot-case-grid").count() == 0
    assert study.locator("#pilot-profile").count() == 0
    assert study.locator("#archive-profile-grid figure").count() == 25
    assert study.locator('a[href="pattern_bosch_range_pilot_review.json"]').count() == 1
    assert (
        study.locator('a[href="evidence/bosch/range_pilot/source_bundle.json"]').count()
        == 1
    )
    assert page.locator("#active-factor-rows").count() == 0
    assert page.locator("#pattern-bosch-factor-scope").count() == 0
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
    assert "after cycle 20" in page.locator("#bosch-cycle-read").inner_text()

    candidate_path = page.locator("#candidate-cu-figure path").last
    assert "filled by area; not converged" in page.locator(
        "#candidate-cu-read h4"
    ).inner_text()
    page.locator("#candidate-cu-slider").fill("0")
    first_candidate_path = candidate_path.get_attribute("d")
    first_candidate_metrics = page.locator("#candidate-cu-read").inner_text()
    page.locator("#candidate-cu-slider").fill("9")
    assert page.locator("#candidate-cu-read").inner_text() != first_candidate_metrics
    assert page.locator("#candidate-cu-figure .cu-warning").count() == 0
    page.locator("#candidate-cu-slider").fill("10")
    assert candidate_path.get_attribute("d") != first_candidate_path
    assert (
        "filled by area; not converged"
        in page.locator("#candidate-cu-read h4").inner_text()
    )
    assert page.locator("#candidate-cu-figure .cu-warning").count() == 1
    assert "Mouth opening" in page.locator("#candidate-cu-read").inner_text()


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
        assert_measurement_atlas(page)
        assert_range_pilot(page)
        assert_focused_etch(page)
        assert_bosch_multifactor(page)
        assert_bosch_interactions(page)
        assert_saved_trajectories(page)

        page.get_by_role("button", name="Trap a void").click()
        page.locator("#fill-progress-slider").fill("23")
        assert_copper_geometry(page)
        assert page.locator("#fill-replay-read h4").first.inner_text() == "Void trapped"
        wall_path = page.locator("#fill-replay-figure path").nth(1).get_attribute("d")

        page.get_by_role("button", name="Join the copper region").click()
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

"""Render the explainer and exercise its simulation replay."""

from pathlib import Path

from playwright.sync_api import sync_playwright


def assert_copper_geometry(page):
    geometry = page.locator("#fill-replay-figure path").nth(1).evaluate(
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
    assert geometry["pathLength"] > 0.1
    assert geometry["width"] > 0
    assert geometry["height"] > 0
    assert geometry["visibility"] == "visible"
    assert geometry["opacity"] > 0
    assert geometry["stroke"] != "none"


def assert_step_viewers(page):
    viewer_ids = ["mask", "bosch", "liner", "barrier", "seed", "cmp"]
    assert page.locator("[data-output-viewer]").count() == len(viewer_ids) + 1
    assert page.locator('[data-output-viewer="copper"]').count() == 1
    assert page.locator("#step-output-list [data-output-viewer]").evaluate_all(
        "elements => elements.map(element => element.dataset.outputViewer)"
    ) == ["mask", "bosch", "liner", "barrier", "seed", "copper", "cmp"]
    for viewer_id in viewer_ids:
        viewer = page.locator(f'[data-output-viewer="{viewer_id}"]')
        assert viewer.count() == 1
        controls = viewer.locator("[data-parameter]")
        assert controls.count() == 2
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

    mask = page.locator('[data-output-viewer="mask"]')
    etch = page.locator('[data-output-viewer="bosch"]')
    original_etch_path = etch.locator('path[data-material="silicon"]').get_attribute("d")
    mask.locator('[data-parameter="opening_width"]').fill("0")
    assert etch.locator('path[data-material="silicon"]').get_attribute("d") == original_etch_path

    chain = page.locator("#failure-chain-viewer")
    start_path = chain.locator('path[data-chain-material="silicon"]').get_attribute("d")
    chain.get_by_role("button", name="Copper fill", exact=True).click()
    assert "traps a void" in chain.locator(".output-status").inner_text().lower()
    assert chain.locator('path[data-chain-material="copper"]').count() == 1
    assert chain.locator('path[data-chain-material="silicon"]').get_attribute("d") != start_path


def assert_numerical_evidence(page):
    response = page.locator("#numerical-response-chart")
    assert response.locator("circle").count() == 4
    assert "observed spread" in page.locator("#numerical-response-caption").inner_text()
    page.get_by_role("button", name="Ray sampling").click()
    page.select_option("#numerical-metric", "cd_bottom")
    assert response.locator("circle").count() == 4
    assert "Bottom width" in page.locator("#numerical-response-caption").inner_text()
    status = page.locator("#numerical-ray-status").inner_text()
    assert "rejected" in status.lower()
    assert "Provisional exploration setting; clean paired ladder pending" in status
    assert "Current comparison baseline" in status
    assert page.locator('a[href*="numerical_performance_data.json"]').count() == 1


def assert_bosch_interactions(page):
    lab = page.locator("#bosch-interaction-lab")
    assert lab.locator("#bosch-corners button").count() == 4
    assert "actual simulated profiles" in lab.inner_text().lower()
    first_path = lab.locator("#bosch-profile path").nth(1).get_attribute("d")
    lab.locator("#bosch-corners button").nth(2).click()
    assert lab.locator("#bosch-profile path").nth(1).get_attribute("d") != first_path
    page.select_option(
        "#bosch-interaction-select", "ion_source_exponent|ion_rate"
    )
    assert lab.locator("#bosch-corners button").count() == 4
    assert "Maximum width error" in lab.locator("#bosch-read").inner_text()
    assert lab.locator('a[href*="v3_bosch_cheap_interactions_rows.jsonl"]').count() == 1


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
        assert_bosch_interactions(page)

        page.get_by_role("button", name="Wall growth faster").click()
        page.locator("#fill-progress-slider").fill("23")
        assert_copper_geometry(page)
        assert page.locator("#fill-replay-read h4").first.inner_text() == "Void trapped"
        wall_path = page.locator("#fill-replay-figure path").nth(1).get_attribute("d")

        page.get_by_role("button", name="Floor growth faster").click()
        page.locator("#fill-progress-slider").fill("23")
        assert_copper_geometry(page)
        assert page.locator("#fill-replay-read h4").first.inner_text() == "Void-free fill"
        floor_path = page.locator("#fill-replay-figure path").nth(1).get_attribute("d")
        assert floor_path != wall_path
        assert not page_errors

        page.set_viewport_size({"width": 390, "height": 844})
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - window.innerWidth"
        )
        assert overflow <= 0
        browser.close()


if __name__ == "__main__":
    main()
    print("rendered explainer checks: PASS")

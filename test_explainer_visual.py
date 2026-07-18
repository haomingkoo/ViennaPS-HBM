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
        geometry = viewer.locator("path[data-material]").first.evaluate(
            """element => {
                const box = element.getBBox();
                return {length: element.getTotalLength(), width: box.width, height: box.height};
            }"""
        )
        assert geometry["length"] > 0
        assert geometry["width"] > 0
        assert geometry["height"] > 0

    mask = page.locator('[data-output-viewer="mask"]')
    etch = page.locator('[data-output-viewer="bosch"]')
    original_mask_path = mask.locator('path[data-material="mask"]').get_attribute("d")
    original_etch_path = etch.locator('path[data-material="silicon"]').get_attribute("d")
    mask.locator("input").fill("2")
    assert mask.locator('path[data-material="mask"]').get_attribute("d") != original_mask_path
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
    assert "p10–p90" in page.locator("#numerical-response-caption").inner_text()
    page.get_by_role("button", name="Rays per point").click()
    page.select_option("#numerical-metric", "cd_bottom")
    assert response.locator("circle").count() == 4
    assert "Bottom width" in page.locator("#numerical-response-caption").inner_text()
    status = page.locator("#numerical-ray-status").inner_text()
    assert "rejected" in status.lower()
    assert "Promising, but not approved" in status
    assert "Tested reference" in status
    assert page.locator('a[href*="numerical_performance_data.json"]').count() == 1


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

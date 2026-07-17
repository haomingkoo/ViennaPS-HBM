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


def main():
    url = Path("explainer.html").resolve().as_uri()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(url)
        page.wait_for_selector("#fill-replay-figure svg")

        page.get_by_role("button", name="Wall growth faster").click()
        page.locator("#fill-progress-slider").fill("23")
        assert_copper_geometry(page)
        assert page.locator("#fill-replay-read h4").inner_text() == "Void trapped"
        wall_path = page.locator("#fill-replay-figure path").nth(1).get_attribute("d")

        page.get_by_role("button", name="Floor growth faster").click()
        page.locator("#fill-progress-slider").fill("23")
        assert_copper_geometry(page)
        assert page.locator("#fill-replay-read h4").inner_text() == "Void-free fill"
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

"""Deterministic Chat UI tests for corpus descriptions."""

import json
import re

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.deterministic,
]


def test_corpus_description_panel_renders_sanitized_markdown(page, det_base_url):
    page.route(
        "**/v1/corpora",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "data": {
                        "corpora": ["alpha", "beta"],
                        "descriptions": {
                            "alpha": ("# Alpha\nVisible **markdown** [ref_key] <script>window.__bad=1</script> [bad](javascript:alert(1))"),
                            "beta": "No description available.",
                        },
                    }
                }
            ),
        ),
    )

    page.goto(det_base_url, wait_until="domcontentloaded")
    page.wait_for_function("document.querySelector('#corpus-selector').value === 'alpha'", timeout=10000)

    info_button = page.locator("[data-testid='corpus-info-btn']")
    info_button.click()
    panel = page.locator("[data-testid='corpus-info-panel']")
    content = page.locator("[data-testid='corpus-info-content']")

    assert panel.is_visible()
    assert page.locator("[data-testid='corpus-info-title']").inner_text() == "alpha"
    assert content.locator("h1").inner_text() == "Alpha"
    assert content.locator("strong").inner_text() == "markdown"
    assert content.locator(".citation-pill").count() == 0
    assert "[ref_key]" in content.inner_text()
    assert content.locator("script").count() == 0
    assert page.evaluate("window.__bad") is None
    assert "javascript:" not in content.inner_html()

    page.locator("#corpus-selector").select_option(value="beta")
    info_button.click()
    expect_text = re.compile("No description available", re.IGNORECASE)
    assert content.get_by_text(expect_text).is_visible()


@pytest.mark.expect_console_errors
def test_corpus_description_load_failure_shows_unavailable_message(page, det_base_url):
    page.route("**/v1/corpora", lambda route: route.abort())

    page.goto(det_base_url, wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    info_button = page.locator("[data-testid='corpus-info-btn']")
    assert info_button.is_enabled()
    info_button.click()
    assert page.locator("[data-testid='corpus-info-content']").get_by_text("Corpus information unavailable.").is_visible()


def test_corpus_description_panel_keyboard_and_mobile_layout(page, det_base_url):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(det_base_url, wait_until="domcontentloaded")
    page.wait_for_function("document.querySelector('#corpus-selector').value === 'alpha'", timeout=10000)

    info_button = page.locator("[data-testid='corpus-info-btn']")
    info_button.focus()
    page.keyboard.press("Enter")

    panel = page.locator("[data-testid='corpus-info-panel']")
    assert panel.is_visible()
    box = panel.bounding_box()
    assert box is not None
    assert box["x"] >= 0
    assert box["y"] >= 0
    assert box["x"] + box["width"] <= 390
    assert box["y"] + box["height"] <= 844

    page.keyboard.press("Escape")
    assert panel.is_hidden()
    assert info_button.get_attribute("aria-expanded") == "false"
    assert info_button.evaluate("button => button === document.activeElement")

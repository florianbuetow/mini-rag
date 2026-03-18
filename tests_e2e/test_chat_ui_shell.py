"""Layer A — Deterministic browser tests: App shell and boot.

Tests 1-4 from specifications2.md section 6:
1. App boot renders shell.
2. Empty sidebar state shown when no chats exist.
3. Model selector populates and default model is preferred lightweight option.
4. Corpus selector populates and defaults to first alphabetical corpus.
"""

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.deterministic,
]


class TestAppBoot:
    """Test 1: App boot renders shell — sidebar, selectors, chat area, composer."""

    def test_sidebar_visible(self, page) -> None:
        sidebar = page.locator("[data-testid='sidebar']")
        assert sidebar.is_visible()

    def test_model_selector_visible(self, page) -> None:
        selector = page.locator("[data-testid='model-selector']")
        assert selector.is_visible()

    def test_corpus_selector_visible(self, page) -> None:
        selector = page.locator("[data-testid='corpus-selector']")
        assert selector.is_visible()

    def test_chat_area_visible(self, page) -> None:
        area = page.locator("[data-testid='chat-area']")
        assert area.is_visible()

    def test_message_input_visible(self, page) -> None:
        inp = page.locator("[data-testid='message-input']")
        assert inp.is_visible()

    def test_send_button_visible(self, page) -> None:
        btn = page.locator("[data-testid='send-btn']")
        assert btn.is_visible()

    def test_css_loaded(self, page) -> None:
        """Verify CSS is loaded by checking a computed style on the body."""
        bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        # The dark theme sets a non-default background
        assert bg != "rgba(0, 0, 0, 0)", f"CSS not loaded — body background is transparent: {bg}"


class TestEmptySidebarState:
    """Test 2: Empty sidebar state shown when no chats exist."""

    def test_empty_state_text(self, page) -> None:
        empty = page.locator("#empty-sidebar")
        assert empty.is_visible()
        assert "no conversations" in empty.text_content().lower()

    def test_no_chat_entries(self, page) -> None:
        entries = page.locator("[data-testid='chat-entry']")
        assert entries.count() == 0


class TestModelSelector:
    """Test 3: Model selector populates; default is preferred lightweight option."""

    def test_model_options_populated(self, page) -> None:
        page.wait_for_function(
            "document.querySelector('#model-selector').value !== ''",
            timeout=10000,
        )
        options = page.locator("#model-selector option")
        assert options.count() == 3  # gemma-3-1b, qwen-2.5-7b, llama-3.1-70b

    def test_option_labels_equal_model_ids(self, page) -> None:
        page.wait_for_function(
            "document.querySelector('#model-selector').value !== ''",
            timeout=10000,
        )
        options = page.locator("#model-selector option")
        for i in range(options.count()):
            opt = options.nth(i)
            assert opt.get_attribute("value") == opt.text_content()

    def test_default_is_lightweight(self, page) -> None:
        """The UI prefers gemma/qwen — gemma-3-1b is first and lightweight."""
        page.wait_for_function(
            "document.querySelector('#model-selector').value !== ''",
            timeout=10000,
        )
        selected = page.locator("#model-selector").input_value()
        assert "gemma" in selected.lower() or "qwen" in selected.lower(), f"Default model '{selected}' is not a preferred lightweight model"


class TestCorpusSelector:
    """Test 4: Corpus selector populates; defaults to first alphabetical corpus."""

    def test_corpus_options_populated(self, page) -> None:
        page.wait_for_function(
            "document.querySelector('#corpus-selector').value !== ''",
            timeout=10000,
        )
        options = page.locator("#corpus-selector option")
        assert options.count() == 3  # alpha, beta, gamma

    def test_corpora_alphabetically_ordered(self, page) -> None:
        page.wait_for_function(
            "document.querySelector('#corpus-selector').value !== ''",
            timeout=10000,
        )
        options = page.locator("#corpus-selector option")
        values = [options.nth(i).get_attribute("value") for i in range(options.count())]
        assert values == sorted(values), f"Corpora not sorted: {values}"

    def test_default_is_first_alphabetical(self, page) -> None:
        page.wait_for_function(
            "document.querySelector('#corpus-selector').value !== ''",
            timeout=10000,
        )
        selected = page.locator("#corpus-selector").input_value()
        assert selected == "alpha", f"Default corpus should be 'alpha', got '{selected}'"

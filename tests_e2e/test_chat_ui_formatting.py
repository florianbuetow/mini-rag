"""E2E tests for markdown rendering and citation pills in assistant messages.

Tests verify that:
- Assistant messages render markdown via marked.js (headings, bold, italic,
  code, lists, links, tables)
- Code blocks get syntax highlighting via highlight.js
- Links open in new tabs (target="_blank", rel="noopener noreferrer")
- Citation keys like [citation_key] render as visual pills
- XSS is prevented via DOMPurify (assistant HTML sanitized)
- User messages remain plain text (textContent, not innerHTML)

All tests use the deterministic fake server (no real LLM needed).
Trigger: send "TRIGGER_MARKDOWN" to get a markdown-formatted response.
"""

import pytest

from tests_e2e.helpers_chat_ui import (
    create_new_chat,
    send_message_and_wait,
    wait_for_selectors_loaded,
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.deterministic,
]


class TestMarkdownRendering:
    """Verify that assistant messages render markdown as HTML."""

    def test_headings_rendered(self, page):
        """Assistant response with # and ## renders as h1/h2 elements."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        assert content.locator("h1").count() >= 1
        assert content.locator("h2").count() >= 1

    def test_bold_and_italic_rendered(self, page):
        """**bold** renders as <strong>, *italic* as <em>."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        assert content.locator("strong").count() >= 1
        assert content.locator("em").count() >= 1

    def test_inline_code_rendered(self, page):
        """Backtick text renders as <code> element."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        inline_code = content.locator("code")
        assert inline_code.count() >= 1

    def test_code_block_with_highlighting(self, page):
        """Fenced code blocks render as <pre><code> with hljs classes."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        pre_block = content.locator("pre code")
        assert pre_block.count() >= 1
        # highlight.js adds hljs class
        cls = pre_block.first.get_attribute("class") or ""
        assert "hljs" in cls

    def test_ordered_list_rendered(self, page):
        """Numbered items render as <ol> with <li> children."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        assert content.locator("ol").count() >= 1
        assert content.locator("ol li").count() >= 2

    def test_links_open_in_new_tab(self, page):
        """Markdown links get target="_blank" and rel="noopener noreferrer"."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        link = content.locator("a[href='https://example.com']")
        assert link.count() >= 1
        assert link.first.get_attribute("target") == "_blank"
        rel = link.first.get_attribute("rel") or ""
        assert "noopener" in rel

    def test_table_rendered(self, page):
        """Markdown tables render as <table> elements."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        assert content.locator("table").count() >= 1
        assert content.locator("th").count() >= 2
        assert content.locator("td").count() >= 2


class TestCitationPills:
    """Verify that [citation_key] patterns render as styled pill elements."""

    def test_citation_rendered_as_pill(self, page):
        """[feynman2026quantum] becomes a .citation-pill element."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        pills = content.locator(".citation-pill")
        assert pills.count() >= 2

    def test_citation_pill_text(self, page):
        """Citation pills display the citation key text."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        pills = content.locator(".citation-pill")
        texts = [pills.nth(i).text_content() for i in range(pills.count())]
        assert any("feynman2026quantum" in t for t in texts)
        assert any("cousteau2026coral" in t for t in texts)

    def test_citation_not_in_code_blocks(self, page):
        """Citations inside code blocks should NOT become pills."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "TRIGGER_MARKDOWN")

        content = page.locator(".message-assistant .message-content").last
        # Verify pills exist outside code blocks (feature must be active)
        all_pills = content.locator(".citation-pill")
        assert all_pills.count() >= 1, "Citation pills must exist first"
        # Code blocks should not contain pill elements
        code_pills = content.locator("pre .citation-pill")
        assert code_pills.count() == 0


class TestXssSafety:
    """Verify XSS protection with markdown rendering enabled."""

    def test_dompurify_loaded_and_strips_xss(self, page):
        """DOMPurify is loaded and strips dangerous HTML attributes."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "test safe response")

        result = page.evaluate("""() => {
            // DOMPurify must be loaded
            if (typeof DOMPurify === 'undefined') return 'DOMPurify not loaded';
            // It must strip onerror handlers
            const dirty = '<img src=x onerror="alert(1)">';
            const clean = DOMPurify.sanitize(dirty);
            if (clean.includes('onerror')) return 'onerror not stripped';
            return 'ok';
        }""")
        assert result == "ok"

    def test_user_message_still_plain_text(self, page):
        """User messages must use textContent, not innerHTML (J-44)."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "<script>alert('xss')</script>")

        user_msg = page.locator(".message-user .message-content").last
        text = user_msg.text_content()
        assert "<script>" in text

        # Verify the script was NOT executed
        inner = user_msg.inner_html()
        # textContent escapes HTML, so innerHTML should show escaped entities
        assert "<script>" not in inner or "&lt;script&gt;" in inner


class TestPlainMessageStillWorks:
    """Verify that non-markdown assistant messages still render correctly."""

    def test_plain_text_response(self, page):
        """Normal (non-markdown) responses render correctly."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        response = send_message_and_wait(page, "test plain response")

        content = page.locator(".message-assistant .message-content").last
        # The deterministic response is plain text
        assert "Hello from the deterministic agent." in response
        # Should still be visible in the DOM
        assert content.is_visible()

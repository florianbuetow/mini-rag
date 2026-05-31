"""Layer A — Deterministic browser tests: Export functionality.

Tests 24-25 from specifications2.md section 6:
24. Export Markdown content is structurally correct.
25. Export JSON contains full chat object fields: id, name, model, corpus,
    messages, created_at, updated_at.
"""

import json

import pytest

from tests_e2e.helpers_chat_ui import (
    send_message_and_wait,
    wait_for_selectors_loaded,
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.deterministic,
]


def _setup_chat_with_message(page) -> None:
    """Create a chat and send one message."""
    wait_for_selectors_loaded(page)
    page.locator("[data-testid='new-chat']").click()
    page.wait_for_timeout(1000)
    send_message_and_wait(page, "export test message")


class TestExportMarkdown:
    """Test 24: Markdown export is structurally correct."""

    def test_export_menu_opens_and_closes(self, page) -> None:
        _setup_chat_with_message(page)

        export_btn = page.locator("[data-testid='export-btn']")
        export_btn.click()
        page.wait_for_timeout(300)

        menu = page.locator("#export-menu")
        assert "visible" in menu.get_attribute("class")

        # Click elsewhere to close
        page.locator("[data-testid='chat-area']").click()
        page.wait_for_timeout(300)
        assert "visible" not in (menu.get_attribute("class") or "")

    def test_markdown_export_content(self, page) -> None:
        """Markdown includes both roles and contents in order."""
        _setup_chat_with_message(page)

        # Intercept the download
        with page.expect_download() as download_info:
            page.locator("[data-testid='export-btn']").click()
            page.wait_for_timeout(200)
            page.locator("[data-testid='export-md']").click()

        download = download_info.value
        assert download.suggested_filename.endswith(".md")

        content = download.path().read_text()
        assert "# Chat Export" in content
        assert "## User" in content
        assert "## Assistant" in content
        assert "export test message" in content
        assert "Hello from the deterministic agent." in content
        assert "Searching corpus" not in content
        assert "Using 5 chunks from 2 documents" not in content
        assert "Streaming answer" not in content


class TestExportJson:
    """Test 25: JSON export contains full chat object fields."""

    def test_json_export_has_required_fields(self, page) -> None:
        _setup_chat_with_message(page)

        with page.expect_download() as download_info:
            page.locator("[data-testid='export-btn']").click()
            page.wait_for_timeout(200)
            page.locator("[data-testid='export-json']").click()

        download = download_info.value
        assert download.suggested_filename.endswith(".json")

        content = download.path().read_text()
        data = json.loads(content)

        required_fields = ["id", "name", "model", "corpus", "messages", "created_at", "updated_at"]
        for field in required_fields:
            assert field in data, f"JSON export missing required field '{field}': {list(data.keys())}"

        # Messages should include the exchange
        messages = data["messages"]
        assert len(messages) >= 2, f"Expected at least 2 messages, got {len(messages)}"
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "export test message"
        assert messages[1]["role"] == "assistant"
        assert "Hello from the deterministic agent." in messages[1]["content"]
        assert "Searching corpus" not in messages[1]["content"]
        assert "Using 5 chunks from 2 documents" not in messages[1]["content"]
        assert "Streaming answer" not in messages[1]["content"]

    def test_export_filename_derived_from_chat_name(self, page) -> None:
        """Export filename is derived from the visible chat name and sanitized."""
        _setup_chat_with_message(page)

        # Rename the chat
        entry = page.locator("[data-testid='chat-entry']").first
        entry.dblclick()
        page.wait_for_timeout(300)
        rename_input = page.locator("[data-testid='rename-input']")
        rename_input.fill("My Test Chat")
        rename_input.press("Enter")
        page.wait_for_timeout(500)

        with page.expect_download() as download_info:
            page.locator("[data-testid='export-btn']").click()
            page.wait_for_timeout(200)
            page.locator("[data-testid='export-json']").click()

        download = download_info.value
        filename = download.suggested_filename
        assert "My_Test_Chat" in filename or "my_test_chat" in filename.lower(), (
            f"Filename should contain sanitized chat name, got '{filename}'"
        )

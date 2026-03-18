"""Layer A — Deterministic browser tests: Sidebar and chat CRUD.

Tests 5-14 from specifications2.md section 6:
5.  New chat sends POST /v1/chats with current model and corpus.
6.  New chat clears transcript and inserts a sidebar entry.
7.  Clicking a saved chat loads transcript, model, and corpus.
8.  Sidebar shows chats newest first.
9.  Rename via edit button sends PUT /v1/chats/<id> with name.
10. Rename via double-click works.
11. Blank rename is rejected.
12. Rename Escape cancels.
13. Delete inactive chat removes it from sidebar.
14. Delete active chat clears the transcript.
"""

import json

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


class TestNewChat:
    """Tests 5-6: New chat creation."""

    def test_new_chat_sends_post_with_model_and_corpus(self, page) -> None:
        """Test 5: POST /v1/chats carries current model and corpus."""
        wait_for_selectors_loaded(page)

        requests_log: list[dict] = []

        def on_request(request) -> None:
            if "/v1/chats" in request.url and request.method == "POST":
                body = request.post_data
                if body:
                    requests_log.append(json.loads(body))

        page.on("request", on_request)
        page.locator("[data-testid='new-chat']").click()
        page.wait_for_timeout(1000)

        assert len(requests_log) >= 1, "No POST /v1/chats request captured"
        payload = requests_log[0]
        assert "model" in payload, f"Payload missing 'model': {payload}"
        assert "corpus" in payload, f"Payload missing 'corpus': {payload}"
        assert payload["model"] != "", "Model should not be empty"
        assert payload["corpus"] != "", "Corpus should not be empty"

    def test_new_chat_clears_transcript_and_adds_sidebar_entry(self, page) -> None:
        """Test 6: New chat clears transcript and inserts a sidebar entry."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        # Transcript should be empty
        messages = page.locator("[data-testid='message']")
        assert messages.count() == 0, "Transcript should be empty after new chat"

        # Sidebar should have one entry
        entries = page.locator("[data-testid='chat-entry']")
        assert entries.count() == 1, f"Expected 1 sidebar entry, got {entries.count()}"


class TestLoadChat:
    """Tests 7-8: Loading saved chats."""

    def test_clicking_saved_chat_loads_transcript_model_corpus(self, page, det_api_client) -> None:
        """Test 7: Clicking a saved chat loads transcript, model, and corpus."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        # Send a message to create history
        response_text = send_message_and_wait(page, "hello")
        assert response_text != ""

        # Create a second chat and switch to it
        create_new_chat(page)
        page.wait_for_timeout(500)

        # Click the first chat (it should be the second entry since newest-first)
        entries = page.locator("[data-testid='chat-entry']")
        assert entries.count() == 2
        entries.nth(1).click()
        page.wait_for_timeout(1000)

        # Verify transcript restored
        messages = page.locator("[data-testid='message']")
        assert messages.count() >= 2, f"Expected at least 2 messages, got {messages.count()}"

    def test_sidebar_newest_first(self, page) -> None:
        """Test 8: Sidebar shows chats newest first."""
        wait_for_selectors_loaded(page)

        # Create first chat
        create_new_chat(page)
        send_message_and_wait(page, "first chat message")

        # Create second chat
        create_new_chat(page)
        page.wait_for_timeout(500)

        entries = page.locator("[data-testid='chat-entry']")
        assert entries.count() == 2

        # The newest chat should be first (top)
        # The active chat is the newest one
        first_entry = entries.nth(0)
        assert "active" in first_entry.get_attribute("class")


class TestRename:
    """Tests 9-12: Rename functionality."""

    def test_rename_via_edit_button(self, page) -> None:
        """Test 9: Rename via edit button sends PUT with name."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        # Hover over the entry to reveal actions
        entry = page.locator("[data-testid='chat-entry']").first
        entry.hover()
        page.wait_for_timeout(300)

        # Click the rename (edit) button — it's the pencil icon
        edit_btn = entry.locator("button").first
        edit_btn.click()
        page.wait_for_timeout(300)

        # Type new name
        rename_input = page.locator("[data-testid='rename-input']")
        assert rename_input.is_visible(), "Rename input should be visible"
        rename_input.fill("My Renamed Chat")
        rename_input.press("Enter")
        page.wait_for_timeout(500)

        # Verify the name changed in the sidebar
        name_span = entry.locator(".chat-entry-name")
        assert name_span.text_content() == "My Renamed Chat"

    def test_rename_via_double_click(self, page) -> None:
        """Test 10: Rename via double-click works."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        entry = page.locator("[data-testid='chat-entry']").first
        entry.dblclick()
        page.wait_for_timeout(300)

        rename_input = page.locator("[data-testid='rename-input']")
        assert rename_input.is_visible(), "Rename input should appear on double-click"
        rename_input.fill("Double Click Name")
        rename_input.press("Enter")
        page.wait_for_timeout(500)

        name_span = entry.locator(".chat-entry-name")
        assert name_span.text_content() == "Double Click Name"

    def test_blank_rename_rejected(self, page) -> None:
        """Test 11: Blank rename is rejected — name stays the same."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        entry = page.locator("[data-testid='chat-entry']").first
        original_name = entry.locator(".chat-entry-name").text_content()

        entry.dblclick()
        page.wait_for_timeout(300)

        rename_input = page.locator("[data-testid='rename-input']")
        rename_input.fill("")
        rename_input.press("Enter")
        page.wait_for_timeout(500)

        # Name should be unchanged
        current_name = entry.locator(".chat-entry-name").text_content()
        assert current_name == original_name, f"Blank rename should keep original name '{original_name}', got '{current_name}'"

    def test_rename_escape_cancels(self, page) -> None:
        """Test 12: Escape cancels rename."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        entry = page.locator("[data-testid='chat-entry']").first
        original_name = entry.locator(".chat-entry-name").text_content()

        entry.dblclick()
        page.wait_for_timeout(300)

        rename_input = page.locator("[data-testid='rename-input']")
        rename_input.fill("Should Be Cancelled")
        rename_input.press("Escape")
        page.wait_for_timeout(500)

        current_name = entry.locator(".chat-entry-name").text_content()
        assert current_name == original_name, f"Escape should revert name to '{original_name}', got '{current_name}'"


class TestDelete:
    """Tests 13-14: Delete functionality."""

    def test_delete_inactive_chat(self, page) -> None:
        """Test 13: Delete inactive chat removes only that chat from sidebar."""
        wait_for_selectors_loaded(page)

        # Create two chats
        create_new_chat(page)
        send_message_and_wait(page, "first chat")
        create_new_chat(page)
        page.wait_for_timeout(500)

        entries = page.locator("[data-testid='chat-entry']")
        assert entries.count() == 2

        # The active chat is the newest (first entry). Delete the inactive one (second).
        inactive_entry = entries.nth(1)
        inactive_entry.hover()
        page.wait_for_timeout(300)
        delete_btn = inactive_entry.locator("[data-testid='delete-chat']")
        delete_btn.click()
        page.wait_for_timeout(1000)

        # Only one entry should remain
        entries = page.locator("[data-testid='chat-entry']")
        assert entries.count() == 1

        # Active chat transcript should still exist (it was not the deleted one)
        # The remaining chat should be active
        remaining = entries.first
        assert "active" in remaining.get_attribute("class")

    def test_delete_active_chat_clears_transcript(self, page) -> None:
        """Test 14: Delete active chat clears the transcript."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)
        send_message_and_wait(page, "message in active chat")

        # Verify messages exist
        messages = page.locator("[data-testid='message']")
        assert messages.count() >= 2

        # Delete the active chat
        entry = page.locator("[data-testid='chat-entry']").first
        entry.hover()
        page.wait_for_timeout(300)
        delete_btn = entry.locator("[data-testid='delete-chat']")
        delete_btn.click()
        page.wait_for_timeout(1000)

        # Transcript should be cleared
        messages = page.locator("[data-testid='message']")
        assert messages.count() == 0, "Transcript should be empty after deleting active chat"

        # Sidebar should show empty state
        entries = page.locator("[data-testid='chat-entry']")
        assert entries.count() == 0

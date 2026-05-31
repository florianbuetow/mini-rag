"""Layer A — Deterministic browser tests: Error handling and edge cases.

Tests 22-23, 26-28 from specifications2.md section 6:
22. Stream error after partial output preserves visible partial text.
23. Save failure after response surfaces a visible warning.
26. Refresh restores last active chat when implemented.
27. User-supplied HTML is escaped in transcript rendering.
28. Long transcript auto-scrolls to the latest message.
"""

import pytest

from tests_e2e.helpers_chat_ui import (
    create_new_chat,
    current_assistant_text,
    send_message_and_wait,
    wait_for_selectors_loaded,
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.deterministic,
]


class TestStreamError:
    """Test 22: Stream error after partial output."""

    def test_partial_text_preserved_on_stream_error(self, page) -> None:
        """Error during stream preserves partial text already rendered."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        # Send a message that triggers a stream error
        msg_input = page.locator("#message-input")
        msg_input.fill("TRIGGER_STREAM_ERROR please")

        expected_count = page.locator(".message-assistant").count() + 1
        page.locator("#send-btn").click()

        page.wait_for_function(
            f"document.querySelectorAll('.message-assistant').length >= {expected_count}",
            timeout=15000,
        )
        page.wait_for_function(
            "!document.getElementById('message-input').disabled",
            timeout=15000,
        )
        page.wait_for_timeout(500)

        text = current_assistant_text(page)
        # The fake error stream yields "Partial" then "error: simulated streaming error"
        assert "Partial" in text, f"Partial text should be preserved, got: {text}"

    @pytest.mark.expect_console_errors
    def test_json_error_response_message_is_rendered(self, page) -> None:
        """Non-SSE chat completion errors should render the API error message."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        page.route(
            "**/v1/chat/completions",
            lambda route: route.fulfill(
                status=500,
                content_type="application/json",
                body='{"status":500,"error":"dense search failed: embedding model timed out"}',
            ),
        )

        text = send_message_and_wait(page, "trigger json error")

        assert "dense search failed: embedding model timed out" in text
        assert page.locator(".message-error").count() >= 1

    @pytest.mark.expect_console_errors
    def test_legacy_anonymous_stream_frame_renders_contract_error(self, page) -> None:
        """Malformed legacy SSE frames should render a descriptive stream-contract error."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        page.route(
            "**/v1/chat/completions",
            lambda route: route.fulfill(
                status=200,
                content_type="text/event-stream",
                body="data: legacy token\n\ndata: [DONE]\n\n",
            ),
        )

        text = send_message_and_wait(page, "trigger malformed legacy stream")

        assert "Stream contract error" in text
        assert "failed parsing anonymous SSE frame" in text
        assert "Payload:" in text
        assert "legacy token" in text
        assert page.locator(".message-error").count() >= 1

    @pytest.mark.expect_console_errors
    def test_invalid_typed_stream_payload_renders_contract_error(self, page) -> None:
        """Typed SSE events with invalid JSON should render a descriptive error."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        page.route(
            "**/v1/chat/completions",
            lambda route: route.fulfill(
                status=200,
                content_type="text/event-stream",
                body="event: status\ndata: not-json\n\n",
            ),
        )

        text = send_message_and_wait(page, "trigger invalid json stream")

        assert "Stream contract error" in text
        assert 'failed parsing event "status"' in text
        assert "Data is not valid JSON" in text
        assert "Payload:" in text
        assert "not-json" in text
        assert page.locator(".message-error").count() >= 1


class TestSaveFailure:
    """Test 23: Save failure surfaces visible warning."""

    @pytest.mark.expect_console_errors
    def test_save_failure_shows_warning(self, page, det_base_url) -> None:
        """If PUT /v1/chats/<id> fails, a visible warning should appear."""
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        # Intercept PUT requests and make them fail
        page.route(
            "**/v1/chats/**",
            lambda route: route.fulfill(status=500, body='{"error":"simulated"}') if route.request.method == "PUT" else route.continue_(),
        )

        send_message_and_wait(page, "save should fail")

        # Wait for the warning banner
        warning = page.locator("[data-testid='save-warning']")
        warning.wait_for(state="visible", timeout=5000)
        assert warning.is_visible(), "Save failure warning should be visible"
        assert "save" in warning.text_content().lower() or "persist" in warning.text_content().lower()


class TestRefreshRestore:
    """Test 26: Refresh restores last active chat."""

    def test_refresh_restores_last_active_chat(self, page, det_base_url) -> None:
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        response = send_message_and_wait(page, "remember this chat")
        assert response != ""

        # Refresh the page
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # After refresh, the last active chat should be restored
        messages = page.locator("[data-testid='message']")
        msg_count = messages.count()
        assert msg_count >= 2, f"After refresh, expected at least 2 messages (restored chat), got {msg_count}"


class TestXSSPrevention:
    """Test 27: User-supplied HTML is escaped in transcript rendering."""

    def test_html_escaped_in_user_message(self, page) -> None:
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        xss_payload = "<script>alert('xss')</script><img src=x onerror=alert(1)>"
        send_message_and_wait(page, xss_payload)

        # The user message should show as text, not execute
        user_msgs = page.locator(".message-user .message-content")
        count = user_msgs.count()
        assert count >= 1

        user_text = user_msgs.nth(count - 1).text_content()
        assert "<script>" in user_text, "HTML should be rendered as text"

        # Verify no script elements were actually injected
        script_count = page.evaluate("document.querySelectorAll('#messages script').length")
        assert script_count == 0, "No script tags should be injected into the DOM"


class TestAutoScroll:
    """Test 28: Long transcript auto-scrolls to the latest message."""

    def test_auto_scroll_to_bottom(self, page) -> None:
        wait_for_selectors_loaded(page)
        create_new_chat(page)

        # Send multiple messages to create a long transcript
        for i in range(5):
            send_message_and_wait(page, f"message number {i + 1}")

        # Check that chat area is scrolled to bottom
        is_at_bottom = page.evaluate("""() => {
            const area = document.getElementById('chat-area');
            return Math.abs(area.scrollHeight - area.scrollTop - area.clientHeight) < 50;
        }""")
        assert is_at_bottom, "Chat area should be scrolled to the bottom after multiple messages"

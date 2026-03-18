"""Layer A — Deterministic browser tests: Composer, streaming, and persistence.

Tests 15-21 from specifications2.md section 6:
15. User message appears before stream completes.
16. Assistant message grows incrementally over at least two chunks.
17. Send controls are disabled for the duration of streaming.
18. Browser request to /v1/chat/completions contains full message history.
19. Browser request to /v1/chat/completions contains selected model.
20. Browser request to /v1/chat/completions contains selected corpus.
21. Successful completion triggers chat persistence PUT with full history.
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


def _create_chat_and_prepare(page) -> None:
    """Create a new chat and wait for selectors."""
    wait_for_selectors_loaded(page)
    page.locator("[data-testid='new-chat']").click()
    page.wait_for_timeout(1000)


class TestUserMessageAndStreaming:
    """Tests 15-17: Message display and streaming behavior."""

    def test_user_message_appears_before_stream_completes(self, page) -> None:
        """Test 15: User message appears immediately after send."""
        _create_chat_and_prepare(page)

        msg_input = page.locator("#message-input")
        msg_input.fill("Test message")

        # Use a MutationObserver to capture the user bubble appearing
        # before the assistant completes
        page.evaluate("""() => {
            window.__userBubbleAppearedFirst = false;
            window.__assistantDone = false;
            const observer = new MutationObserver(() => {
                const user = document.querySelectorAll('.message-user');
                const assistantContent = document.querySelectorAll('.message-assistant .message-content');
                if (user.length > 0 && !window.__assistantDone) {
                    window.__userBubbleAppearedFirst = true;
                }
                if (assistantContent.length > 0) {
                    const last = assistantContent[assistantContent.length - 1];
                    if (last.textContent.includes('agent.')) {
                        window.__assistantDone = true;
                    }
                }
            });
            observer.observe(document.getElementById('messages'), {
                childList: true, subtree: true, characterData: true
            });
        }""")

        page.locator("#send-btn").click()
        page.wait_for_function(
            "!document.getElementById('message-input').disabled",
            timeout=15000,
        )

        appeared_first = page.evaluate("window.__userBubbleAppearedFirst")
        assert appeared_first, "User message should appear before stream completes"

    def test_assistant_grows_incrementally(self, page) -> None:
        """Test 16: Assistant message grows incrementally over at least two chunks."""
        _create_chat_and_prepare(page)

        # Track intermediate text lengths
        page.evaluate("""() => {
            window.__textLengths = [];
            const observer = new MutationObserver(() => {
                const msgs = document.querySelectorAll('.message-assistant .message-content');
                if (msgs.length > 0) {
                    const last = msgs[msgs.length - 1];
                    const len = last.textContent.length;
                    const prev = window.__textLengths;
                    if (prev.length === 0 || prev[prev.length - 1] !== len) {
                        prev.push(len);
                    }
                }
            });
            observer.observe(document.getElementById('messages'), {
                childList: true, subtree: true, characterData: true
            });
        }""")

        msg_input = page.locator("#message-input")
        msg_input.fill("hello")
        page.locator("#send-btn").click()
        page.wait_for_function(
            "!document.getElementById('message-input').disabled",
            timeout=15000,
        )
        page.wait_for_timeout(300)

        lengths = page.evaluate("window.__textLengths")
        assert len(lengths) >= 2, f"Expected at least 2 incremental length changes, got {len(lengths)}: {lengths}"

    def test_send_controls_disabled_during_streaming(self, page) -> None:
        """Test 17: Send button and textarea disabled while streaming."""
        _create_chat_and_prepare(page)

        # Observe disabled state during streaming
        page.evaluate("""() => {
            window.__inputWasDisabled = false;
            window.__buttonWasDisabled = false;
            const observer = new MutationObserver(() => {
                if (document.getElementById('message-input').disabled) {
                    window.__inputWasDisabled = true;
                }
                if (document.getElementById('send-btn').disabled) {
                    window.__buttonWasDisabled = true;
                }
            });
            observer.observe(document.getElementById('message-input'), { attributes: true });
            observer.observe(document.getElementById('send-btn'), { attributes: true });
        }""")

        msg_input = page.locator("#message-input")
        msg_input.fill("test disabled")
        page.locator("#send-btn").click()

        page.wait_for_function(
            "!document.getElementById('message-input').disabled",
            timeout=15000,
        )

        input_was_disabled = page.evaluate("window.__inputWasDisabled")
        button_was_disabled = page.evaluate("window.__buttonWasDisabled")
        assert input_was_disabled, "Input should have been disabled during streaming"
        assert button_was_disabled, "Send button should have been disabled during streaming"

        # After streaming, controls should be re-enabled
        assert not page.locator("#message-input").is_disabled()
        assert not page.locator("#send-btn").is_disabled()


class TestCompletionPayloads:
    """Tests 18-20: Request payloads sent to /v1/chat/completions."""

    def test_request_contains_full_message_history(self, page) -> None:
        """Test 18: /v1/chat/completions request contains full message history."""
        _create_chat_and_prepare(page)

        requests_log: list[dict] = []

        def on_request(request) -> None:
            if "/v1/chat/completions" in request.url and request.method == "POST":
                body = request.post_data
                if body:
                    requests_log.append(json.loads(body))

        page.on("request", on_request)

        # Send first message
        send_message_and_wait(page, "first message")

        # Send second message — history should contain first exchange + new user msg
        send_message_and_wait(page, "second message")

        assert len(requests_log) >= 2, f"Expected at least 2 completion requests, got {len(requests_log)}"

        second_payload = requests_log[1]
        messages = second_payload["messages"]
        # Should contain: user1, assistant1, user2
        assert len(messages) >= 3, f"Expected at least 3 messages in second request, got {len(messages)}"
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "first message"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "second message"

    def test_request_contains_selected_model(self, page) -> None:
        """Test 19: /v1/chat/completions request contains selected model."""
        _create_chat_and_prepare(page)

        requests_log: list[dict] = []

        def on_request(request) -> None:
            if "/v1/chat/completions" in request.url and request.method == "POST":
                body = request.post_data
                if body:
                    requests_log.append(json.loads(body))

        page.on("request", on_request)

        # Select a specific model
        page.locator("#model-selector").select_option(value="qwen-2.5-7b")
        send_message_and_wait(page, "test model")

        assert len(requests_log) >= 1
        assert requests_log[0]["model"] == "qwen-2.5-7b"

    def test_request_contains_selected_corpus(self, page) -> None:
        """Test 20: /v1/chat/completions request contains selected corpus."""
        _create_chat_and_prepare(page)

        requests_log: list[dict] = []

        def on_request(request) -> None:
            if "/v1/chat/completions" in request.url and request.method == "POST":
                body = request.post_data
                if body:
                    requests_log.append(json.loads(body))

        page.on("request", on_request)

        page.locator("#corpus-selector").select_option(value="beta")
        send_message_and_wait(page, "test corpus")

        assert len(requests_log) >= 1
        assert requests_log[0]["corpus"] == "beta"


class TestChatPersistence:
    """Test 21: Successful completion triggers persistence PUT."""

    def test_put_with_full_history(self, page, det_api_client) -> None:
        """Test 21: After completion, PUT /v1/chats/<id> contains full history."""
        _create_chat_and_prepare(page)

        put_payloads: list[dict] = []

        def on_request(request) -> None:
            if "/v1/chats/" in request.url and request.method == "PUT":
                body = request.post_data
                if body:
                    put_payloads.append(json.loads(body))

        page.on("request", on_request)

        send_message_and_wait(page, "persistence test")

        assert len(put_payloads) >= 1, "No PUT request captured after completion"
        payload = put_payloads[-1]
        messages = payload.get("messages", [])
        assert len(messages) >= 2, f"Expected at least 2 messages (user+assistant), got {len(messages)}"

        # User message
        user_msg = messages[0]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "persistence test"

        # Assistant message — should contain the deterministic response
        assistant_msg = messages[1]
        assert assistant_msg["role"] == "assistant"
        assert "Hello from the deterministic agent." in assistant_msg["content"]

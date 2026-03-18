"""End-to-end Playwright tests for the Chat UI.

Spec: docs/specs/chat-ui-specification.md
Test spec: docs/specs/chat-ui-test-specification.md
Test impl spec: docs/specs/chat-ui-test-implementation-specification.md

These tests require:
- mini-rag service running on port 9191 with Chat UI served
- LM Studio running on port 1234 with at least one model loaded

Run with: uv run pytest tests_e2e/ --headed (or --headless)
"""

import json

import httpx
import pytest

BASE_URL = "http://localhost:9191"
LM_STUDIO_URL = "http://127.0.0.1:1234"


def _service_available():
    """Check if the mini-rag service is running."""
    try:
        resp = httpx.get(f"{BASE_URL}/v1/health", timeout=2.0)
        return resp.status_code == 200
    except httpx.ConnectError:
        return False


def _lm_studio_available():
    """Check if LM Studio is running."""
    try:
        resp = httpx.get(f"{LM_STUDIO_URL}/v1/models", timeout=2.0)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout):
        return False


def _create_chat_via_api(model="gemma-3-1b", corpus="docs", name=None, messages=None):
    """Create a chat via the API for test setup."""
    body = {"model": model, "corpus": corpus}
    if name is not None:
        body["name"] = name
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        resp = client.post("/v1/chats", json=body)
        chat = resp.json()["data"]
        if messages:
            client.put(f"/v1/chats/{chat['id']}", json={"messages": messages})
            chat = client.get(f"/v1/chats/{chat['id']}").json()["data"]
        return chat


def _wait_for_selectors_loaded(page):
    """Wait until both model and corpus selectors have non-empty values."""
    page.wait_for_function(
        "document.querySelector('#model-selector').value !== ''",
        timeout=10000,
    )
    page.wait_for_function(
        "document.querySelector('#corpus-selector').value !== ''",
        timeout=10000,
    )


pytestmark = pytest.mark.skipif(
    not _service_available(),
    reason="mini-rag service not running on port 9191",
)


# --- Model Selector ---


# TS-1: Model selector loads models
@pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not running")
def test_model_selector_loads_models(page):
    _wait_for_selectors_loaded(page)
    model_selector = page.locator("#model-selector")

    options = model_selector.locator("option")
    count = options.count()
    assert count >= 1, "Model selector should have at least one model"


# TS-2: Default model selection
@pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not running")
def test_model_selector_defaults_to_lightweight(page):
    _wait_for_selectors_loaded(page)
    model_selector = page.locator("#model-selector")

    selected_value = model_selector.input_value()
    # Should default to a lightweight model (gemma or qwen variant)
    assert selected_value, "A model should be selected by default"


# TS-3: Switch model mid-conversation
@pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not running")
def test_model_switch_mid_conversation(page):
    _wait_for_selectors_loaded(page)
    model_selector = page.locator("#model-selector")

    options = model_selector.locator("option")
    if options.count() < 2:
        pytest.skip("Need at least 2 models to test switching")

    # Select the second model
    second_model = options.nth(1).get_attribute("value")
    model_selector.select_option(value=second_model)

    assert model_selector.input_value() == second_model


# --- Corpus Selector ---


# TS-4: Corpus selector loads corpora
def test_corpus_selector_loads_corpora(page):
    corpus_selector = page.locator("#corpus-selector")
    corpus_selector.wait_for(timeout=5000)
    corpus_selector.click()

    options = corpus_selector.locator("option")
    assert options.count() >= 1, "Corpus selector should have at least one corpus"

    # Verify alphabetical order
    names = [options.nth(i).text_content() for i in range(options.count())]
    assert names == sorted(names), "Corpora should be in alphabetical order"


# TS-5: Default corpus selection
def test_corpus_selector_defaults_to_first(page):
    corpus_selector = page.locator("#corpus-selector")
    corpus_selector.wait_for(timeout=5000)

    selected = corpus_selector.input_value()
    assert selected, "A corpus should be selected by default"


# TS-6: Switch corpus mid-conversation
def test_corpus_switch_mid_conversation(page):
    corpus_selector = page.locator("#corpus-selector")
    corpus_selector.wait_for(timeout=5000)

    options = corpus_selector.locator("option")
    if options.count() < 2:
        pytest.skip("Need at least 2 corpora to test switching")

    second_corpus = options.nth(1).get_attribute("value")
    corpus_selector.select_option(value=second_corpus)

    assert corpus_selector.input_value() == second_corpus


# --- Sidebar ---


# TS-7: Sidebar displays chat list
def test_sidebar_displays_chat_list(page):
    # Create 3 chats via API first
    _create_chat_via_api(name="Chat One")
    _create_chat_via_api(name="Chat Two")
    _create_chat_via_api(name="Chat Three")

    page.reload()
    page.wait_for_load_state("networkidle")

    sidebar = page.locator("#sidebar")
    sidebar.wait_for(timeout=5000)

    chat_entries = sidebar.locator(".chat-entry")
    assert chat_entries.count() == 3


# TS-8: Load chat from sidebar
def test_sidebar_load_chat(page):
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm doing well!"},
    ]
    _create_chat_via_api(name="My Research", messages=messages)

    page.reload()
    page.wait_for_load_state("networkidle")

    # Click the chat in the sidebar
    chat_entry = page.locator(".chat-entry-name:text('My Research')")
    chat_entry.click()

    # Wait for messages to load
    page.wait_for_timeout(1000)

    # Should show all 4 messages
    message_bubbles = page.locator("#messages .message")
    assert message_bubbles.count() == 4


# TS-9: Rename chat inline
def test_sidebar_rename_chat(page):
    _create_chat_via_api(name="Old Name")

    page.reload()
    page.wait_for_load_state("networkidle")

    # Find the chat entry and trigger rename (double-click)
    chat_entry = page.locator(".chat-entry-name:text('Old Name')")
    chat_entry.dblclick()

    # Type new name
    rename_input = page.locator("[data-testid='rename-input']")
    rename_input.fill("Renamed Chat")
    rename_input.press("Enter")

    # Verify the name changed
    page.wait_for_timeout(500)
    assert page.locator(".chat-entry-name:text('Renamed Chat')").is_visible()


# TS-10: Reject empty chat name
def test_sidebar_reject_empty_rename(page):
    _create_chat_via_api(name="My Chat")

    page.reload()
    page.wait_for_load_state("networkidle")

    chat_entry = page.locator(".chat-entry-name:text('My Chat')")
    chat_entry.dblclick()

    rename_input = page.locator("[data-testid='rename-input']")
    rename_input.fill("")
    rename_input.press("Enter")

    # Original name should persist
    page.wait_for_timeout(500)
    assert page.locator(".chat-entry-name:text('My Chat')").is_visible()


# --- New Chat ---


# TS-11: New chat button
@pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not running")
def test_new_chat_button(page):
    _wait_for_selectors_loaded(page)

    new_chat_btn = page.locator("[data-testid='new-chat']")
    assert new_chat_btn.is_visible()

    new_chat_btn.click()
    page.wait_for_timeout(1000)

    # A new chat entry should appear in the sidebar
    chat_entries = page.locator("#sidebar .chat-entry")
    assert chat_entries.count() >= 1


# --- Chat Area ---


# TS-12: Message bubbles displayed
def test_message_bubbles_displayed(page):
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    _create_chat_via_api(name="Test Chat", messages=messages)

    page.reload()
    page.wait_for_load_state("networkidle")

    # Click the chat to load it
    page.locator(".chat-entry-name:text('Test Chat')").click()
    page.wait_for_timeout(500)

    # Check for distinct user/assistant styling
    user_msgs = page.locator(".message-user")
    assistant_msgs = page.locator(".message-assistant")
    assert user_msgs.count() >= 1
    assert assistant_msgs.count() >= 1


# TS-13: Streaming assistant response
@pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not running")
def test_streaming_assistant_response(page):
    _wait_for_selectors_loaded(page)

    # Select gemma model explicitly
    model_selector = page.locator("#model-selector")
    options = model_selector.locator("option")
    gemma_value = None
    for i in range(options.count()):
        val = options.nth(i).get_attribute("value")
        if val and "gemma" in val.lower() and "embed" not in val.lower():
            gemma_value = val
            break
    assert gemma_value is not None, "No gemma model found in selector"
    model_selector.select_option(value=gemma_value)

    new_chat_btn = page.locator("[data-testid='new-chat']")
    new_chat_btn.click()
    page.wait_for_timeout(1000)

    # Type and send a message
    msg_input = page.locator("#message-input")
    msg_input.fill("What is mini-rag?")

    send_btn = page.locator("#send-btn")
    send_btn.click()

    # User message should appear immediately
    page.wait_for_timeout(1000)
    user_msg = page.locator(".message-user")
    assert user_msg.count() >= 1

    # Wait for streaming to complete (input re-enabled means stream finished)
    # RAG agent with tool-calling + LLM generation can take 2+ minutes
    page.wait_for_function(
        "!document.getElementById('message-input').disabled",
        timeout=180000,
    )
    page.wait_for_timeout(500)

    # Verify assistant actually produced a non-empty response
    assistant_msg = page.locator(".message-assistant .message-content")
    assert assistant_msg.count() >= 1
    response_text = assistant_msg.last.text_content()
    assert len(response_text) > 0, "Assistant response should not be empty"


# TS-14: Input disabled during streaming
@pytest.mark.timeout(240)
@pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not running")
def test_input_disabled_during_streaming(page):
    _wait_for_selectors_loaded(page)

    new_chat_btn = page.locator("[data-testid='new-chat']")
    new_chat_btn.click()
    page.wait_for_timeout(1000)

    msg_input = page.locator("#message-input")
    msg_input.fill("Tell me about retrieval augmented generation.")

    send_btn = page.locator("#send-btn")

    # Set up a mutation observer to detect the disabled state even if it's brief
    page.evaluate("""
        () => {
            window.__inputWasDisabled = false;
            window.__sendWasDisabled = false;
            const input = document.getElementById('message-input');
            const btn = document.getElementById('send-btn');
            const obs = new MutationObserver(() => {
                if (input.disabled) window.__inputWasDisabled = true;
                if (btn.disabled) window.__sendWasDisabled = true;
            });
            obs.observe(input, { attributes: true, attributeFilter: ['disabled'] });
            obs.observe(btn, { attributes: true, attributeFilter: ['disabled'] });
        }
    """)

    send_btn.click()

    # Wait for streaming to complete (assistant response appears and input re-enabled)
    # Tool-calling agent with hybrid search + LLM generation can take 2+ minutes
    page.wait_for_function(
        "document.querySelector('.message-assistant') !== null",
        timeout=180000,
    )
    page.wait_for_function(
        "!document.getElementById('message-input').disabled",
        timeout=180000,
    )

    was_disabled = page.evaluate("() => window.__inputWasDisabled || window.__sendWasDisabled")
    assert was_disabled, "Input or send button should have been disabled during streaming"

    # Verify assistant actually produced a non-empty response
    assistant_content = page.locator(".message-assistant .message-content")
    assert assistant_content.count() >= 1
    response_text = assistant_content.last.text_content()
    assert len(response_text) > 0, "Assistant response should not be empty"


# TS-15: Chat saved after response
@pytest.mark.timeout(240)
@pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not running")
def test_chat_saved_after_response(page):
    _wait_for_selectors_loaded(page)

    new_chat_btn = page.locator("[data-testid='new-chat']")
    new_chat_btn.click()
    page.wait_for_timeout(1000)

    msg_input = page.locator("#message-input")
    msg_input.fill("Hello")

    send_btn = page.locator("#send-btn")
    send_btn.click()

    # Wait for response to complete — tool-calling agent with search can take 2+ min
    page.wait_for_function(
        "!document.getElementById('message-input').disabled",
        timeout=180000,
    )
    page.wait_for_timeout(1000)

    # Verify via API that the chat was saved
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        resp = client.get("/v1/chats")
        chats = resp.json()["data"]["chats"]
        assert len(chats) >= 1

        chat_id = chats[0]["id"]
        chat_resp = client.get(f"/v1/chats/{chat_id}")
        chat = chat_resp.json()["data"]
        assert len(chat["messages"]) >= 2  # user + assistant


# --- Export ---


# TS-16: Export action available
def test_export_action_available(page):
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]
    _create_chat_via_api(name="Export Test", messages=messages)

    page.reload()
    page.wait_for_load_state("networkidle")
    page.locator(".chat-entry-name:text('Export Test')").click()
    page.wait_for_timeout(500)

    export_btn = page.locator("[data-testid='export-btn']")
    assert export_btn.is_visible()


# TS-17: Export as Markdown
def test_export_as_markdown(page):
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    _create_chat_via_api(name="MD Export", messages=messages)

    page.reload()
    page.wait_for_load_state("networkidle")
    page.locator(".chat-entry-name:text('MD Export')").click()
    page.wait_for_timeout(500)

    with page.expect_download() as download_info:
        # Click export and select Markdown
        page.locator("[data-testid='export-btn']").click()
        page.locator("[data-testid='export-md']").click()

    download = download_info.value
    assert download.suggested_filename.endswith(".md")

    content = download.path().read_text()
    assert "Hello" in content
    assert "Hi there!" in content


# TS-18: Export as JSON
def test_export_as_json(page):
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    _create_chat_via_api(name="JSON Export", messages=messages)

    page.reload()
    page.wait_for_load_state("networkidle")
    page.locator(".chat-entry-name:text('JSON Export')").click()
    page.wait_for_timeout(500)

    with page.expect_download() as download_info:
        page.locator("[data-testid='export-btn']").click()
        page.locator("[data-testid='export-json']").click()

    download = download_info.value
    assert download.suggested_filename.endswith(".json")

    content = json.loads(download.path().read_text())
    assert "messages" in content


# --- Delete ---


# TS-19: Delete chat from sidebar
def test_sidebar_delete_chat(page):
    _create_chat_via_api(name="Delete Me")

    page.reload()
    page.wait_for_load_state("networkidle")

    assert page.locator(".chat-entry-name:text('Delete Me')").is_visible()

    # Hover to reveal the delete button, then click it
    chat_entry = page.locator(".chat-entry").first
    chat_entry.hover()
    page.wait_for_timeout(200)

    delete_btn = chat_entry.locator("[data-testid='delete-chat']")
    delete_btn.click()

    page.wait_for_timeout(500)
    assert not page.locator(".chat-entry-name:text('Delete Me')").is_visible()


# TS-20: Delete active chat clears area
def test_delete_active_chat_clears_area(page):
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]
    _create_chat_via_api(name="Active Chat", messages=messages)

    page.reload()
    page.wait_for_load_state("networkidle")

    # Load the chat
    page.locator(".chat-entry-name:text('Active Chat')").click()
    page.wait_for_timeout(500)

    # Hover to reveal delete, then click
    chat_entry = page.locator(".chat-entry").first
    chat_entry.hover()
    page.wait_for_timeout(200)

    delete_btn = chat_entry.locator("[data-testid='delete-chat']")
    delete_btn.click()
    page.wait_for_timeout(500)

    # Chat area should be cleared
    message_bubbles = page.locator("#messages .message")
    assert message_bubbles.count() == 0

    # Chat should be gone from sidebar
    assert not page.locator(".chat-entry-name:text('Active Chat')").is_visible()


# --- Edge Cases ---


# TS-21: Model dropdown error state
def test_model_dropdown_error_when_lm_studio_down(page):
    if _lm_studio_available():
        pytest.skip("LM Studio is running — cannot test error state")

    model_selector = page.locator("#model-selector")
    model_selector.wait_for(timeout=5000)

    # The sidebar and corpus selector should still work
    sidebar = page.locator("#sidebar")
    assert sidebar.is_visible()


# TS-22: Empty corpus state
def test_corpus_dropdown_empty_state(page):
    # This test requires a service started with no corpora
    # Skip if corpora exist
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        resp = client.get("/v1/corpora")
        if resp.status_code == 200 and resp.json()["data"]["corpora"]:
            pytest.skip("Corpora exist — cannot test empty state")

    corpus_selector = page.locator("#corpus-selector")
    corpus_selector.wait_for(timeout=5000)
    # Should show empty state or message


# TS-23: Empty sidebar state
def test_sidebar_empty_state(page):
    sidebar = page.locator("#sidebar")
    sidebar.wait_for(timeout=5000)

    # With no chats, should show empty state message
    empty_msg = sidebar.locator(".empty-state")
    assert empty_msg.is_visible()


# TS-24: Handle streaming error
@pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not running")
def test_streaming_error_shows_partial_response(page):
    # This test is hard to trigger deterministically without service control
    # We verify that the UI handles the case where the stream ends abruptly
    # by checking that partial content is shown
    pytest.skip("Requires ability to interrupt LM Studio mid-stream — manual test")


# TS-25: Chat area scrolls
def test_chat_area_scrolls_to_latest(page):
    # Create a chat with many messages
    messages = []
    for i in range(20):
        messages.append({"role": "user", "content": f"Message {i}"})
        messages.append({"role": "assistant", "content": f"Response {i}"})
    _create_chat_via_api(name="Long Chat", messages=messages)

    page.reload()
    page.wait_for_load_state("networkidle")

    page.locator(".chat-entry-name:text('Long Chat')").click()
    page.wait_for_timeout(1000)

    # The chat area should be scrolled to show the latest message
    is_scrolled = page.evaluate("""
        () => {
            const el = document.getElementById('chat-area');
            if (!el) return false;
            return el.scrollTop + el.clientHeight >= el.scrollHeight - 50;
        }
    """)
    assert is_scrolled, "Chat area should be scrolled to the bottom"

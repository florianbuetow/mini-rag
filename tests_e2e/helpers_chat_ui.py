"""Shared helper functions for Chat UI E2E tests.

These helpers standardize common browser interactions and assertions
across deterministic and real-RAG test suites.
"""

import re

import httpx

# Constants
BASE_URL = "http://localhost:9191"
LM_STUDIO_URL = "http://127.0.0.1:1234"
LLM_TIMEOUT = 120000  # ms, generous for tool-calling agent


def service_available() -> bool:
    """Check if the mini-rag service is running."""
    try:
        resp = httpx.get(f"{BASE_URL}/v1/health", timeout=2.0)
        return resp.status_code == 200
    except httpx.ConnectError:
        return False


def lm_studio_available() -> bool:
    """Check if LM Studio is running and has models."""
    try:
        resp = httpx.get(f"{LM_STUDIO_URL}/v1/models", timeout=2.0)
        return resp.status_code == 200
    except httpx.ConnectError:
        return False


def corpus_available(corpus_name: str) -> bool:
    """Check if a specific corpus exists on the running service."""
    try:
        resp = httpx.get(f"{BASE_URL}/v1/corpora", timeout=2.0)
        if resp.status_code == 200:
            corpora = resp.json().get("data", {}).get("corpora", [])
            return corpus_name in corpora
        return False
    except httpx.ConnectError:
        return False


def wait_for_selectors_loaded(page) -> None:
    """Wait until both model and corpus selectors have populated values."""
    page.wait_for_function(
        "document.querySelector('#model-selector').value !== ''",
        timeout=10000,
    )
    page.wait_for_function(
        "document.querySelector('#corpus-selector').value !== ''",
        timeout=10000,
    )


def select_corpus(page, corpus_name: str) -> None:
    """Select a corpus in the corpus dropdown."""
    corpus_selector = page.locator("#corpus-selector")
    corpus_selector.select_option(value=corpus_name)


def select_model(page, model_id: str) -> None:
    """Select a model in the model dropdown."""
    model_selector = page.locator("#model-selector")
    model_selector.select_option(value=model_id)


def send_message_and_wait(page, text: str, timeout_ms: int = LLM_TIMEOUT) -> str:
    """Type a message, click send, wait for the assistant response to complete.

    Returns the assistant response text (the last .message-assistant element).
    """
    msg_input = page.locator("#message-input")
    msg_input.fill(text)

    # Count assistant messages BEFORE clicking send (the frontend creates the
    # empty assistant bubble immediately on click)
    expected_count = page.locator(".message-assistant").count() + 1

    send_btn = page.locator("#send-btn")
    send_btn.click()

    # Wait for assistant response bubble to appear
    page.wait_for_function(
        f"document.querySelectorAll('.message-assistant').length >= {expected_count}",
        timeout=timeout_ms,
    )

    # Wait for streaming to finish (input re-enabled)
    page.wait_for_function(
        "!document.getElementById('message-input').disabled",
        timeout=timeout_ms,
    )

    # Small buffer for final DOM updates
    page.wait_for_timeout(500)

    return current_assistant_text(page)


def current_assistant_text(page) -> str:
    """Return the text content of the last assistant message bubble."""
    assistant_msgs = page.locator(".message-assistant .message-content")
    count = assistant_msgs.count()
    if count == 0:
        return ""
    return assistant_msgs.nth(count - 1).text_content()


def assert_has_keywords(text: str, keywords: list[str], minimum: int = 2) -> None:
    """Assert that text contains at least `minimum` of the given keywords (case-insensitive)."""
    text_lower = text.lower()
    found = [kw for kw in keywords if kw.lower() in text_lower]
    assert len(found) >= minimum, f"Expected at least {minimum} keywords from {keywords}, found {len(found)}: {found}. Text: {text[:300]}"


def has_citation_evidence(text: str) -> bool:
    """Check if response shows RAG retrieval was used.

    Accepts either explicit bracket citations [like_this] or phrases
    indicating the search tool was called and results informed the answer.
    """
    # Explicit bracket citation
    if re.search(r"\[.+?\]", text):
        return True
    # Evidence the search tool was called
    evidence_phrases = [
        "search results",
        "search_documents",
        "documents found",
        "retrieved documents",
        "based on the documents",
        "based on my search",
        "according to the",
        "the documents",
        "from the corpus",
        "relevant information",
    ]
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in evidence_phrases)


def assert_has_citation_keys(text: str, keys: list[str]) -> None:
    """Assert that at least one of the expected citation keys appears in the text."""
    text_lower = text.lower()
    found = [key for key in keys if key.lower() in text_lower]
    assert len(found) >= 1, f"Expected at least one citation key from {keys}. Text: {text[:300]}"


def assert_lacks_citation_keys(text: str, keys: list[str]) -> None:
    """Assert that none of the given citation keys appear in the text."""
    text_lower = text.lower()
    found = [key for key in keys if key.lower() in text_lower]
    assert len(found) == 0, f"Expected no citation keys from {keys}, but found: {found}. Text: {text[:300]}"


def fetch_saved_chat(api_client, chat_id: str) -> dict:
    """Fetch a saved chat via the API and return its data."""
    resp = api_client.get(f"/v1/chats/{chat_id}")
    assert resp.status_code == 200, f"Failed to fetch chat {chat_id}: {resp.status_code}"
    return resp.json()["data"]


def create_new_chat(page) -> None:
    """Click the new chat button and wait briefly."""
    page.locator("[data-testid='new-chat']").click()
    page.wait_for_timeout(1000)


def delete_all_chats(api_client) -> None:
    """Delete all chats via the API."""
    try:
        resp = api_client.get("/v1/chats")
        if resp.status_code == 200:
            for chat in resp.json().get("data", {}).get("chats", []):
                api_client.delete(f"/v1/chats/{chat['id']}")
    except httpx.ConnectError:
        pass

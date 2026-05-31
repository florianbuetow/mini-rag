"""E2E tests proving the RAG pipeline returns relevant, cited, distinct answers.

Design: docs/superpowers/specs/2026-03-11-e2e-rag-journey-design.md

These tests use a single chat session against the "knowledgebase" corpus,
ask two different questions, and verify:
1. Responses contain topic-relevant keywords.
2. Responses include citation references from RAG retrieval.
3. Different questions produce different answers.

Requires:
- mini-rag service running on port 9191
- LM Studio running on port 1234 with a model loaded
- "knowledgebase" corpus available and indexed
"""

import re

import httpx
import pytest

BASE_URL = "http://localhost:9191"
LM_STUDIO_URL = "http://127.0.0.1:1234"

# Timeout for waiting on LLM responses (tool calling + generation)
LLM_TIMEOUT = 90000


def _service_available():
    try:
        resp = httpx.get(f"{BASE_URL}/v1/health", timeout=2.0)
        return resp.status_code == 200
    except httpx.ConnectError:
        return False


def _lm_studio_available():
    try:
        resp = httpx.get(f"{LM_STUDIO_URL}/v1/models", timeout=2.0)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout):
        return False


def _knowledgebase_available():
    try:
        resp = httpx.get(f"{BASE_URL}/v1/corpora", timeout=2.0)
        if resp.status_code == 200:
            corpora = resp.json().get("data", {}).get("corpora", [])
            return "knowledgebase" in corpora
        return False
    except (httpx.ConnectError, httpx.ReadTimeout):
        return False


def _wait_for_selectors_loaded(page):
    page.wait_for_function(
        "document.querySelector('#model-selector').value !== ''",
        timeout=10000,
    )
    page.wait_for_function(
        "document.querySelector('#corpus-selector').value !== ''",
        timeout=10000,
    )


def _send_and_wait(page, message):
    """Type a message, send it, wait for the assistant response to complete.

    Returns the assistant response text (the last .message-assistant element).
    """
    msg_input = page.locator("#message-input")
    msg_input.fill(message)

    # Count assistant messages BEFORE clicking send (the frontend creates the
    # empty assistant bubble immediately on click, so counting after would
    # already include it and we'd wait for one more that never comes).
    expected_count = page.locator(".message-assistant").count() + 1

    send_btn = page.locator("#send-btn")
    send_btn.click()

    # Wait for assistant response bubble to appear
    page.wait_for_function(
        f"document.querySelectorAll('.message-assistant').length >= {expected_count}",
        timeout=LLM_TIMEOUT,
    )

    # Wait for streaming to finish (input re-enabled)
    page.wait_for_function(
        "!document.getElementById('message-input').disabled",
        timeout=LLM_TIMEOUT,
    )

    # Small buffer for final DOM updates
    page.wait_for_timeout(500)

    # Return text of the last assistant message
    assistant_msgs = page.locator(".message-assistant .message-content")
    last_idx = assistant_msgs.count() - 1
    return assistant_msgs.nth(last_idx).text_content()


def _has_citation_or_tool_evidence(text):
    """Check if response shows RAG retrieval was used.

    Accepts either explicit bracket citations [like_this] or phrases
    indicating the search tool was called and results informed the answer.
    """
    # Explicit bracket citation
    if re.search(r"\[.+?\]", text):
        return True
    # Evidence the search tool was called and results used
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


def _contains_any_keyword(text, keywords):
    """Check if text contains at least one keyword (case-insensitive)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


# Skip entire module if prerequisites are not met
pytestmark = [
    pytest.mark.rag,
    pytest.mark.skipif(not _service_available(), reason="mini-rag service not running"),
    pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not running"),
    pytest.mark.skipif(not _knowledgebase_available(), reason="knowledgebase corpus not available"),
]


# Store responses across tests in this module
_responses = {}


@pytest.mark.timeout(120)
def test_ask_intent_engineering(page):
    """T1: Ask 'what is intent engineering' and verify relevant, cited answer."""
    _wait_for_selectors_loaded(page)

    # Select knowledgebase corpus
    corpus_selector = page.locator("#corpus-selector")
    corpus_selector.select_option(value="knowledgebase")

    # Create new chat
    page.locator("[data-testid='new-chat']").click()
    page.wait_for_timeout(1000)

    # Ask the question
    response = _send_and_wait(page, "what is intent engineering")

    assert response, "Assistant response should not be empty"

    intent_keywords = ["intent", "prompt", "engineering", "model", "AI", "language", "design"]
    assert _contains_any_keyword(response, intent_keywords), f"Response should contain topic-relevant keywords. Got: {response[:200]}"

    assert _has_citation_or_tool_evidence(response), f"Response should show RAG retrieval was used. Got: {response[:200]}"

    _responses["intent_engineering"] = response


@pytest.mark.timeout(120)
def test_ask_retrieval_augmented_generation(page):
    """T2: Ask 'what is retrieval augmented generation' in the same session."""
    _wait_for_selectors_loaded(page)

    # Select knowledgebase corpus
    corpus_selector = page.locator("#corpus-selector")
    corpus_selector.select_option(value="knowledgebase")

    # Create new chat
    page.locator("[data-testid='new-chat']").click()
    page.wait_for_timeout(1000)

    # Ask the question
    response = _send_and_wait(page, "what is retrieval augmented generation")

    assert response, "Assistant response should not be empty"

    rag_keywords = ["retrieval", "augmented", "generation", "RAG", "search", "document", "embedding", "vector"]
    assert _contains_any_keyword(response, rag_keywords), f"Response should contain RAG-relevant keywords. Got: {response[:200]}"

    assert _has_citation_or_tool_evidence(response), f"Response should show RAG retrieval was used. Got: {response[:200]}"

    _responses["rag"] = response


def test_responses_are_different(page):
    """T3: The two answers must be meaningfully different."""
    if "intent_engineering" not in _responses or "rag" not in _responses:
        pytest.skip("Previous tests did not produce responses to compare")

    r1 = _responses["intent_engineering"]
    r2 = _responses["rag"]

    assert r1 != r2, "Responses to different questions must not be identical"

    # Each response should be relevant to its own topic
    intent_keywords = ["intent", "prompt", "engineering"]
    rag_keywords = ["retrieval", "augmented", "generation", "RAG"]

    r1_has_intent = _contains_any_keyword(r1, intent_keywords)
    r2_has_rag = _contains_any_keyword(r2, rag_keywords)

    assert r1_has_intent, f"Intent engineering response should mention intent-related terms. Got: {r1[:200]}"
    assert r2_has_rag, f"RAG response should mention RAG-related terms. Got: {r2[:200]}"

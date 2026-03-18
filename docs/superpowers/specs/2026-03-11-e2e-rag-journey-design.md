# E2E RAG User Journey Tests — Design

## Goal

Prove the chat app works end-to-end: a user selects the "knowledgebase" corpus,
asks different questions, and receives distinct, citation-backed answers that are
relevant to each question.

## Approach

Approach C: one chat session, multiple questions, compare responses.

## Test File

`tests_e2e/test_rag_journey.py` — separate from the existing `test_chat_ui.py`
which covers UI mechanics.

## Test Scenarios

### T1: Ask "what is intent engineering" and get a relevant, cited answer
1. Wait for selectors to load (model + corpus).
2. Select "knowledgebase" corpus.
3. Click New Chat.
4. Type "what is intent engineering" and send.
5. Wait for assistant response to complete (input re-enabled).
6. Assert: response is non-empty.
7. Assert: response contains at least one topic-relevant keyword
   (e.g. "intent", "prompt", "engineering", "model", "AI").
8. Assert: response contains a citation marker (square bracket pattern like `[...`).

### T2: Ask a different question and get a different, relevant answer
1. In the same chat, type "what is retrieval augmented generation" and send.
2. Wait for assistant response to complete.
3. Assert: response is non-empty and contains topic-relevant keywords
   (e.g. "retrieval", "augmented", "generation", "RAG", "search", "document").
4. Assert: response contains citation markers.

### T3: The two answers are meaningfully different
1. Compare the two assistant response texts.
2. Assert: they are not identical.
3. Assert: each response contains keywords relevant to its own question
   but not exclusively to the other (differentiation check).

## Fixtures & Helpers

- Reuse `_wait_for_selectors_loaded`, `_lm_studio_available`, `_service_available`
  from existing test helpers.
- Helper `_send_and_wait(page, message, timeout)` — fills input, clicks send,
  waits for streaming to complete, returns assistant response text.
- `_response_has_citation(text)` — checks for `[` pattern in response.

## Skip Conditions

All tests skip if mini-rag service or LM Studio is unavailable.

## Timeouts

120s per test — LLM responses with tool calling can take 30-60s on local models.

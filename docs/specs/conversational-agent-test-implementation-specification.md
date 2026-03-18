# Conversational Agent — Test Implementation Specification

## Test Framework & Conventions

- **Language:** Python 3.12
- **Test framework:** pytest with pytest-asyncio (asyncio_mode = "auto")
- **HTTP testing:** FastAPI `TestClient` with `stream=True` for SSE responses
- **Assertion style:** Plain `assert` statements
- **Mocking strategy:** Fake/stub classes for the Strands agent, LM Studio client, and corpus manager. No external mocking library.
- **Test location:** `tests/` directory

## Test Structure

- **File:** `tests/test_api_routes_chat_completions.py`
- **Grouping:** Standalone test functions
- **Naming:** `test_<scenario_description>`

## Test Scenario Mapping

| Test Scenario | Test Function | File |
|--------------|---------------|------|
| TS-1: Send a chat completion request | `test_chat_completion_returns_sse_response` | `tests/test_api_routes_chat_completions.py` |
| TS-2: Response streams via SSE | `test_response_is_sse_stream_with_chunks` | `tests/test_api_routes_chat_completions.py` |
| TS-3: Stream terminates with done signal | `test_sse_stream_ends_with_done_signal` | `tests/test_api_routes_chat_completions.py` |
| TS-4: Server handles client disconnect | `test_server_handles_client_disconnect` | `tests/test_api_routes_chat_completions.py` |
| TS-5: Multi-turn conversation | `test_multi_turn_conversation_sends_full_history` | `tests/test_api_routes_chat_completions.py` |
| TS-6: Reject empty messages | `test_reject_empty_messages_array` | `tests/test_api_routes_chat_completions.py` |
| TS-7: Reject invalid corpus | `test_reject_invalid_corpus_name` | `tests/test_api_routes_chat_completions.py` |
| TS-8: Handle LLM provider error | `test_sse_error_when_llm_unavailable` | `tests/test_api_routes_chat_completions.py` |
| TS-9: Handle empty retrieval | `test_response_when_no_documents_found` | `tests/test_api_routes_chat_completions.py` |
| TS-10: Concurrent completions | `test_concurrent_chat_completions` | `tests/test_api_routes_chat_completions.py` |
| TS-11: Reject when service unhealthy | `test_completions_returns_503_when_unhealthy` | `tests/test_api_routes_chat_completions.py` |

### TS-1: Send a chat completion request

- **Setup (Given):** Build app with `FakeAgent` that yields predefined text chunks. Configure `FakeCorpusManager` with corpus `"docs"`. Set healthy.
- **Action (When):** `client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "What is mini-rag?"}], "model": "gemma-3-1b", "corpus": "docs"})` with `stream=True`.
- **Assertion (Then):** Response content-type is `text/event-stream`. Collected SSE data contains the fake agent's predefined text.

### TS-2: Response is SSE stream with chunks

- **Setup (Given):** Build app with `FakeAgent` that yields 3 distinct text chunks.
- **Action (When):** Send valid chat completion request with `stream=True`.
- **Assertion (Then):** Content-type is `text/event-stream`. At least 3 SSE `data:` lines are received, each containing a chunk.

### TS-3: Stream terminates with done signal

- **Setup (Given):** Build app with `FakeAgent`.
- **Action (When):** Send valid request, consume full stream.
- **Assertion (Then):** The final SSE event contains `[DONE]` or the stream closes cleanly after all data events.

### TS-4: Server handles client disconnect

- **Setup (Given):** Build app with `FakeAgent` that yields many chunks with a small delay.
- **Action (When):** Send valid request with `stream=True`. Read 1 chunk, then close the connection.
- **Assertion (Then):** No unhandled server error is raised. The test completes without exception.

### TS-5: Multi-turn conversation

- **Setup (Given):** Build app with `FakeAgent` that records the messages it receives.
- **Action (When):** Send a request with 3 messages in the `messages` array.
- **Assertion (Then):** The `FakeAgent` received all 3 messages. Response streams successfully.

### TS-6: Reject empty messages

- **Setup (Given):** Build app. Set healthy.
- **Action (When):** `client.post("/v1/chat/completions", json={"messages": [], "model": "gemma-3-1b", "corpus": "docs"})`
- **Assertion (Then):** Status 422.

### TS-7: Reject invalid corpus

- **Setup (Given):** Build app with `FakeCorpusManager` that only knows corpus `"docs"`.
- **Action (When):** `client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hello"}], "model": "gemma-3-1b", "corpus": "nonexistent"})`
- **Assertion (Then):** Status 422.

### TS-8: Handle LLM provider error

- **Setup (Given):** Build app with `FakeAgent` that raises a connection error when invoked.
- **Action (When):** Send valid request with `stream=True`.
- **Assertion (Then):** SSE stream contains an error event with a message about the LLM provider being unreachable. Stream closes.

### TS-9: Handle empty retrieval

- **Setup (Given):** Build app with `FakeAgent` that returns a "no documents found" response when RAG retrieval yields nothing.
- **Action (When):** Send valid request.
- **Assertion (Then):** SSE stream contains text indicating no relevant documents were found.

### TS-10: Concurrent completions

- **Setup (Given):** Build app with `FakeAgent`.
- **Action (When):** Send 3 concurrent `POST /v1/chat/completions` requests using `ThreadPoolExecutor`.
- **Assertion (Then):** All 3 return SSE streams. Each stream contains the expected response data.

### TS-11: Reject when service unhealthy

- **Setup (Given):** Build app with `app_status = "shutting_down"`.
- **Action (When):** `client.post("/v1/chat/completions", json={...valid request...})`
- **Assertion (Then):** Status 503.

## Fixtures & Test Data

- **`FakeAgent` class:** A stub that replaces the Strands agent. Configurable to:
  - Yield predefined text chunks (simulating streaming)
  - Record received messages for assertion
  - Raise connection errors (simulating LM Studio down)
  - Return "no documents found" responses
- **`FakeCorpusManager`:** Stub with configurable corpus list. Returns a `FakeOrchestration` for known corpora, raises error for unknown ones.
- **`completions_app` fixture (function-scoped):** Creates app with chat completions route, `FakeAgent`, `FakeCorpusManager`, healthy status.
- **SSE parsing helper:** Utility function that reads a streaming response and parses `data:` lines into a list of strings.
- **Isolation:** Each test gets its own `FakeAgent` instance — no shared mutable state.

## Alignment Check

Full alignment. All 11 test scenarios (TS-1 through TS-11) are mapped to test functions. No gaps.

**Design note:** TS-4 (client disconnect) may be tricky to test deterministically with `TestClient`. The test should verify no exception propagates — if `TestClient` does not support mid-stream disconnect, this test can be marked as an integration-level test to be verified with Playwright E2E testing instead.

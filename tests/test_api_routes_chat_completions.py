"""Unit tests for the conversational agent chat completions endpoint.

Spec: docs/specs/conversational-agent-specification.md
Test spec: docs/specs/conversational-agent-test-specification.md

These tests will FAIL until the conversational agent feature is implemented.
"""

import json
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from typing import cast

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from minirag.api.app import unhandled_exception_handler
from minirag.api.routes_info import router as info_router
from minirag.chat_stream import ChatStreamEvent


class FakeServiceConfig:
    def __init__(self, reload: bool) -> None:
        self.reload = reload


class FakeConfig:
    def model_dump(self):
        return {"service": {"host": "127.0.0.1", "port": 9191}}

    def get_service_config(self):
        return FakeServiceConfig(reload=False)


class FakeCorpusManager:
    """Corpus manager that knows about specific corpora."""

    def __init__(self, known_corpora: list[str] | None = None) -> None:
        self._corpora = known_corpora if known_corpora is not None else ["docs"]

    def list_corpora(self) -> list[str]:
        return list(self._corpora)

    def corpus_exists(self, name: str) -> bool:
        return name in self._corpora


class FakeAgent:
    """Stub for the Strands conversational agent.

    Configurable to:
    - Yield predefined text chunks (simulating streaming)
    - Record received messages for assertion
    - Raise connection errors (simulating LM Studio down)
    - Return 'no documents found' responses
    """

    def __init__(
        self,
        chunks: list[str] | None = None,
        error: Exception | None = None,
        no_results: bool = False,
    ) -> None:
        self.chunks = chunks if chunks is not None else ["Hello", " from", " the agent"]
        self.error = error
        self.no_results = no_results
        self.received_messages: list[dict[str, str]] = []
        self.received_search_settings: dict[str, object] | None = None

    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        corpus: str,
        search_mode: str = "hybrid",
        top_k: int = 50,
        alpha: float = 0.5,
        reranking: bool = True,
        cancellation_event: threading.Event | None = None,
    ) -> Generator[ChatStreamEvent, None, None]:
        del cancellation_event
        self.received_messages = list(messages)
        self.received_search_settings = {
            "search_mode": search_mode,
            "top_k": top_k,
            "alpha": alpha,
            "reranking": reranking,
        }
        if self.error is not None:
            raise self.error
        if self.no_results:
            yield {"type": "status", "message": "Using 0 chunks from 0 documents"}
            yield {"type": "token", "text": "I could not find any relevant documents in the corpus."}
            return
        for chunk in self.chunks:
            yield {"type": "token", "text": chunk}


class EventAgent:
    """Agent that emits explicit stream events for route contract tests."""

    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.received_messages: list[dict[str, str]] = []
        self.received_search_settings: dict[str, object] | None = None

    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        corpus: str,
        search_mode: str = "hybrid",
        top_k: int = 50,
        alpha: float = 0.5,
        reranking: bool = True,
        cancellation_event: threading.Event | None = None,
    ) -> Generator[object, None, None]:
        del model, corpus, cancellation_event
        self.received_messages = list(messages)
        self.received_search_settings = {
            "search_mode": search_mode,
            "top_k": top_k,
            "alpha": alpha,
            "reranking": reranking,
        }
        yield from self.events


class CancellationAwareAgent:
    """Agent that records the cancellation event passed by the route."""

    def __init__(self) -> None:
        self.cancellation_event: threading.Event | None = None

    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        corpus: str,
        search_mode: str = "hybrid",
        top_k: int = 50,
        alpha: float = 0.5,
        reranking: bool = True,
        cancellation_event: threading.Event | None = None,
    ) -> Generator[ChatStreamEvent, None, None]:
        del messages, model, corpus, search_mode, top_k, alpha, reranking
        self.cancellation_event = cancellation_event
        yield {"type": "token", "text": "partial"}
        yield {"type": "token", "text": "unread"}


def _parse_sse_events(response: httpx.Response) -> list[dict[str, object]]:
    """Parse named SSE events from a streaming response."""
    events: list[dict[str, object]] = []
    event_name = "message"
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = "message"
            return
        raw_data = "\n".join(data_lines)
        try:
            data: object = json.loads(raw_data)
        except json.JSONDecodeError:
            data = raw_data
        events.append({"event": event_name, "data": data})
        event_name = "message"
        data_lines = []

    for line in response.iter_lines():
        if line == "":
            flush()
        elif line.startswith("event: "):
            event_name = line[len("event: ") :]
        elif line.startswith("data:"):
            data = line[len("data:") :]
            if data.startswith(" "):
                data = data[1:]
            data_lines.append(data)
    flush()
    return events


def _token_text(events: list[dict[str, object]]) -> str:
    """Return concatenated token text from parsed SSE events."""
    text = ""
    for event in events:
        if event["event"] == "token":
            data = event["data"]
            assert isinstance(data, dict)
            token_data = cast(dict[str, object], data)
            text += str(token_data["text"])
    return text


def _status_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return status payloads from parsed SSE events."""
    statuses: list[dict[str, object]] = []
    for event in events:
        if event["event"] == "status":
            data = event["data"]
            assert isinstance(data, dict)
            statuses.append(cast(dict[str, object], data))
    return statuses


def _assert_simple_status_payload(data: dict[str, object], expected_message: str, expected_type: str = "info") -> None:
    """Assert public status payload has only timestamp, message, and type."""
    assert set(data) == {"timestamp", "message", "type"}
    assert isinstance(data["timestamp"], str)
    assert data["timestamp"] != ""
    assert data["message"] == expected_message
    assert data["type"] == expected_type


def _make_app(
    agent: object | None = None,
    corpus_manager: FakeCorpusManager | None = None,
    status: str = "healthy",
) -> FastAPI:
    """Create app with chat completions route.

    Imports the completions router that does not exist yet — will fail until implemented.
    """
    from minirag.api.routes_chat_completions import router as completions_router  # noqa: F401

    app = FastAPI()
    app.state.app_status = status
    app.state.config = FakeConfig()
    app.state.corpus_manager = corpus_manager or FakeCorpusManager()
    app.state.agent = agent or FakeAgent()
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(info_router)
    app.include_router(completions_router)
    return app


VALID_REQUEST = {
    "messages": [{"role": "user", "content": "What is mini-rag?"}],
    "model": "gemma-3-1b",
    "corpus": "docs",
}


# TS-1: Send a chat completion request
def test_chat_completion_returns_sse_response():
    agent = FakeAgent(chunks=["Mini-rag", " is a", " RAG system."])
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = _parse_sse_events(resp)

    assert events[0]["event"] == "status"
    full_text = _token_text(events)
    assert "Mini-rag" in full_text


# TS-2: Response is SSE stream with chunks
def test_response_is_sse_stream_with_chunks():
    agent = FakeAgent(chunks=["chunk1", "chunk2", "chunk3"])
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        assert "text/event-stream" in resp.headers["content-type"]
        events = _parse_sse_events(resp)

    token_events = [e for e in events if e["event"] == "token"]
    assert len(token_events) >= 3


def test_stream_emits_status_before_first_token():
    """At least one status event should arrive before answer tokens."""
    client = TestClient(_make_app())

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    event_names = [str(event["event"]) for event in events]
    assert "status" in event_names
    assert "token" in event_names
    assert event_names.index("status") < event_names.index("token")


def test_status_event_payload_is_simple_ui_contract():
    """Status events should expose only timestamp, message, and type."""
    agent = EventAgent(
        [
            {
                "type": "status",
                "message": "Using 3 chunks from 2 documents",
                "status_type": "info",
            },
            {"type": "token", "text": "answer"},
        ]
    )
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    statuses = _status_events(events)
    _assert_simple_status_payload(statuses[0], "Preparing request...")
    _assert_simple_status_payload(statuses[1], "Using 3 chunks from 2 documents")


def test_status_payload_does_not_expose_internal_metadata():
    """Internal status details must not leak into the public status JSON."""
    agent = EventAgent(
        [
            {
                "type": "status",
                "message": "Searching corpus...",
                "phase": "searching",
                "search_mode": "hybrid",
                "top_k": 50,
                "alpha": 0.5,
                "reranking": True,
                "chunks": 99,
                "documents": 10,
            },
            {"type": "token", "text": "answer"},
        ]
    )
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    status = _status_events(events)[1]
    _assert_simple_status_payload(status, "Searching corpus...")
    assert "phase" not in status
    assert "chunks" not in status
    assert "documents" not in status
    assert "top_k" not in status


def test_status_type_is_normalized_to_allowed_values():
    """Unknown internal status types should fall back to info."""
    agent = EventAgent(
        [
            {
                "type": "status",
                "message": "Checking retrieval...",
                "status_type": "debug",
            },
            {"type": "token", "text": "answer"},
        ]
    )
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    _assert_simple_status_payload(_status_events(events)[1], "Checking retrieval...", expected_type="info")


def test_empty_status_message_is_still_serialized_as_simple_contract():
    """Malformed internal status without message should still produce a string message field."""
    agent = EventAgent([{"type": "status"}, {"type": "token", "text": "answer"}])
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    _assert_simple_status_payload(_status_events(events)[1], "")


def test_token_json_escapes_newlines_without_breaking_sse_framing():
    """Token text with newlines should remain one JSON token payload."""
    agent = EventAgent([{"type": "token", "text": "line 1\nline 2"}])
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    token_events = [event for event in events if event["event"] == "token"]
    assert token_events == [{"event": "token", "data": {"text": "line 1\nline 2"}}]


# TS-3: Stream terminates with done signal
def test_sse_stream_ends_with_done_signal():
    client = TestClient(_make_app())

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    assert events[-1] == {"event": "done", "data": {}}


def test_sse_stream_resets_status_before_done_signal():
    """A successful stream should clear transient UI status before completion."""
    client = TestClient(_make_app())

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    assert events[-2]["event"] == "status"
    data = events[-2]["data"]
    assert isinstance(data, dict)
    _assert_simple_status_payload(cast(dict[str, object], data), "")


# TS-4: Server handles client disconnect
def test_server_handles_client_disconnect():
    agent = FakeAgent(chunks=["a"] * 100)
    client = TestClient(_make_app(agent=agent))

    # Open stream and close after first chunk — should not raise
    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        assert resp.status_code == 200
        # Read just the first line and close
        for line in resp.iter_lines():
            if line.startswith("data: "):
                break
    # Test passes if no exception was raised


def test_stream_close_sets_cancellation_event_for_agent() -> None:
    """Closing the SSE generator should notify the active model stream."""
    from minirag.api.routes_chat_completions import stream_agent_response

    agent = CancellationAwareAgent()
    cancellation_event = threading.Event()
    stream = stream_agent_response(
        agent=agent,
        messages=[{"role": "user", "content": "hello"}],
        model="model",
        corpus="docs",
        search_mode="hybrid",
        top_k=5,
        alpha=0.5,
        reranking=True,
        cancellation_event=cancellation_event,
    )

    next(stream)
    next(stream)
    stream.close()

    assert cancellation_event.is_set()
    assert agent.cancellation_event is cancellation_event


# TS-5: Multi-turn conversation
def test_multi_turn_conversation_sends_full_history():
    agent = FakeAgent()
    client = TestClient(_make_app(agent=agent))

    multi_turn_request = {
        "messages": [
            {"role": "user", "content": "What is mini-rag?"},
            {"role": "assistant", "content": "Mini-rag is a RAG system."},
            {"role": "user", "content": "Tell me more."},
        ],
        "model": "gemma-3-1b",
        "corpus": "docs",
    }

    with client.stream("POST", "/v1/chat/completions", json=multi_turn_request) as resp:
        # consume the stream
        list(resp.iter_lines())

    # Agent should have received all 3 messages
    assert len(agent.received_messages) == 3
    assert agent.received_messages[0]["content"] == "What is mini-rag?"
    assert agent.received_messages[2]["content"] == "Tell me more."


# TS-6: Reject empty messages
def test_reject_empty_messages_array():
    client = TestClient(_make_app())

    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [], "model": "gemma-3-1b", "corpus": "docs"},
    )

    assert resp.status_code == 422


# TS-7: Reject invalid corpus
def test_reject_invalid_corpus_name():
    client = TestClient(_make_app(corpus_manager=FakeCorpusManager(["docs"])))

    resp = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "model": "gemma-3-1b",
            "corpus": "nonexistent",
        },
    )

    assert resp.status_code == 422


# TS-8: Handle LLM provider error
def test_sse_error_when_llm_unavailable():
    agent = FakeAgent(error=ConnectionError("LM Studio unreachable"))
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    error_events = [event for event in events if event["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"] == {"message": "LM Studio unreachable"}
    assert events[-1] == {"event": "done", "data": {}}


# TS-9: Handle empty retrieval
def test_response_when_no_documents_found():
    agent = FakeAgent(no_results=True)
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    full_text = _token_text(events)
    assert "could not find" in full_text.lower() or "no relevant" in full_text.lower()


# TS-10: Concurrent completions
def test_concurrent_chat_completions():
    agent = FakeAgent()
    app = _make_app(agent=agent)

    def send_request(_: int) -> tuple[int, list[dict[str, object]]]:
        c = TestClient(app)
        with c.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
            events = _parse_sse_events(resp)
            return resp.status_code, events

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(send_request, range(3)))

    for status_code, events in results:
        assert status_code == 200
        assert len(events) > 0


# TS-11: Reject when service unhealthy
def test_completions_returns_503_when_unhealthy():
    client = TestClient(_make_app(status="shutting_down"))

    resp = client.post("/v1/chat/completions", json=VALID_REQUEST)

    assert resp.status_code == 503


# --- Search settings tests ---

REQUEST_WITH_SEARCH_SETTINGS = {
    "messages": [{"role": "user", "content": "What is LLM as a judge?"}],
    "model": "gemma-3-1b",
    "corpus": "docs",
    "search_mode": "dense",
    "top_k": 20,
    "alpha": 0.3,
    "reranking": False,
}


def test_search_settings_passed_to_agent():
    """Search settings from the request should be forwarded to the agent."""
    agent = FakeAgent()
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=REQUEST_WITH_SEARCH_SETTINGS) as resp:
        list(resp.iter_lines())

    assert agent.received_search_settings is not None
    assert agent.received_search_settings["search_mode"] == "dense"
    assert agent.received_search_settings["top_k"] == 20
    assert agent.received_search_settings["alpha"] == 0.3
    assert agent.received_search_settings["reranking"] is False


def test_search_settings_default_when_omitted():
    """When search settings are omitted, defaults should be used."""
    agent = FakeAgent()
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        list(resp.iter_lines())

    assert agent.received_search_settings is not None
    assert agent.received_search_settings["search_mode"] == "hybrid"
    assert agent.received_search_settings["top_k"] == 50
    assert agent.received_search_settings["alpha"] == 0.5
    assert agent.received_search_settings["reranking"] is True


def test_search_mode_sparse_accepted():
    """Sparse search mode should be accepted."""
    agent = FakeAgent()
    client = TestClient(_make_app(agent=agent))

    request = {**VALID_REQUEST, "search_mode": "sparse"}
    with client.stream("POST", "/v1/chat/completions", json=request) as resp:
        assert resp.status_code == 200
        list(resp.iter_lines())

    assert agent.received_search_settings is not None
    assert agent.received_search_settings["search_mode"] == "sparse"


def test_search_mode_invalid_rejected():
    """Invalid search mode should be rejected."""
    client = TestClient(_make_app())

    request = {**VALID_REQUEST, "search_mode": "invalid"}
    resp = client.post("/v1/chat/completions", json=request)

    assert resp.status_code == 422


def test_top_k_zero_rejected():
    """top_k of 0 should be rejected."""
    client = TestClient(_make_app())

    request = {**VALID_REQUEST, "top_k": 0}
    resp = client.post("/v1/chat/completions", json=request)

    assert resp.status_code == 422


def test_alpha_out_of_range_rejected():
    """Alpha outside [0.0, 1.0] should be rejected."""
    client = TestClient(_make_app())

    request = {**VALID_REQUEST, "alpha": 1.5}
    resp = client.post("/v1/chat/completions", json=request)

    assert resp.status_code == 422

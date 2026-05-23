"""Unit tests for the conversational agent chat completions endpoint.

Spec: docs/specs/conversational-agent-specification.md
Test spec: docs/specs/conversational-agent-test-specification.md

These tests will FAIL until the conversational agent feature is implemented.
"""

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from minirag.api.app import unhandled_exception_handler
from minirag.api.routes_info import router as info_router


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
    ) -> Generator[str, None, None]:
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
            yield "I could not find any relevant documents in the corpus."
            return
        yield from self.chunks


def _parse_sse_events(response: httpx.Response) -> list[str]:
    """Parse SSE data events from a streaming response."""
    events: list[str] = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            data = line[len("data: ") :]
            events.append(data)
    return events


def _make_app(
    agent: FakeAgent | None = None,
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

    # Collected events should contain the agent's response text
    full_text = "".join(e for e in events if e != "[DONE]")
    assert "Mini-rag" in full_text


# TS-2: Response is SSE stream with chunks
def test_response_is_sse_stream_with_chunks():
    agent = FakeAgent(chunks=["chunk1", "chunk2", "chunk3"])
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        assert "text/event-stream" in resp.headers["content-type"]
        events = _parse_sse_events(resp)

    # Filter out the [DONE] sentinel
    data_events = [e for e in events if e != "[DONE]"]
    assert len(data_events) >= 3


# TS-3: Stream terminates with done signal
def test_sse_stream_ends_with_done_signal():
    client = TestClient(_make_app())

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    assert "[DONE]" in events


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

    # Should contain an error message
    full_text = " ".join(events)
    assert "error: LM Studio unreachable" in full_text


# TS-9: Handle empty retrieval
def test_response_when_no_documents_found():
    agent = FakeAgent(no_results=True)
    client = TestClient(_make_app(agent=agent))

    with client.stream("POST", "/v1/chat/completions", json=VALID_REQUEST) as resp:
        events = _parse_sse_events(resp)

    full_text = " ".join(e for e in events if e != "[DONE]")
    assert "could not find" in full_text.lower() or "no relevant" in full_text.lower()


# TS-10: Concurrent completions
def test_concurrent_chat_completions():
    agent = FakeAgent()
    app = _make_app(agent=agent)

    def send_request(_: int) -> tuple[int, list[str]]:
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

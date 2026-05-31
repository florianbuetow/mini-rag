"""Integration tests for the chat status SSE contract with mocked agents."""

import json
import threading
from collections.abc import Generator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from minirag.api.routes_chat_completions import router as completions_router

pytestmark = [
    pytest.mark.integration,
]


class FakeConfig:
    def model_dump(self) -> dict[str, object]:
        return {"service": {"host": "127.0.0.1", "port": 9191}}


class FakeCorpusManager:
    def corpus_exists(self, name: str) -> bool:
        return name == "docs"


class MockStreamAgent:
    """Mock agent that emits caller-provided stream events."""

    def __init__(self, events: list[object] | None = None, error: Exception | None = None) -> None:
        self.events = events if events is not None else []
        self.error = error
        self.received_messages: list[dict[str, str]] = []

    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        corpus: str,
        search_mode: str,
        top_k: int,
        alpha: float,
        reranking: bool,
        cancellation_event: threading.Event | None = None,
    ) -> Generator[object, None, None]:
        del model, corpus, search_mode, top_k, alpha, reranking, cancellation_event
        self.received_messages = list(messages)
        if self.error is not None:
            raise self.error
        yield from self.events


def _make_client(agent: MockStreamAgent) -> TestClient:
    app = FastAPI()
    app.state.app_status = "healthy"
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager()
    app.state.agent = agent
    app.include_router(completions_router)
    return TestClient(app)


def _parse_sse_events(response: httpx.Response) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    event_name = "message"
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = "message"
            return
        events.append({"event": event_name, "data": json.loads("\n".join(data_lines))})
        event_name = "message"
        data_lines = []

    for line in response.iter_lines():
        if line == "":
            flush()
        elif line.startswith("event: "):
            event_name = line[len("event: ") :]
        elif line.startswith("data:"):
            data = line[len("data:") :]
            data_lines.append(data[1:] if data.startswith(" ") else data)
    flush()
    return events


def _post_completion(client: TestClient) -> list[dict[str, object]]:
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "model": "mock-model",
            "corpus": "docs",
        },
    ) as response:
        assert response.status_code == 200
        return _parse_sse_events(response)


def _assert_status(data: object, message: str, status_type: str = "info") -> None:
    assert isinstance(data, dict)
    assert set(data) == {"timestamp", "message", "type"}
    assert isinstance(data["timestamp"], str)
    assert data["message"] == message
    assert data["type"] == status_type


def test_mocked_status_token_and_done_events_are_emitted_correctly() -> None:
    agent = MockStreamAgent(
        [
            {
                "type": "status",
                "message": "Using 2 chunks from 1 documents",
                "status_type": "info",
                "phase": "context_ready",
                "chunks": 2,
                "documents": 1,
            },
            {"type": "token", "text": "line 1\nline 2"},
        ]
    )
    events = _post_completion(_make_client(agent))

    assert [event["event"] for event in events] == ["status", "status", "token", "status", "done"]
    _assert_status(events[0]["data"], "Preparing request...")
    _assert_status(events[1]["data"], "Using 2 chunks from 1 documents")
    assert events[2] == {"event": "token", "data": {"text": "line 1\nline 2"}}
    _assert_status(events[3]["data"], "")
    assert events[4] == {"event": "done", "data": {}}
    assert agent.received_messages == [{"role": "user", "content": "hello"}]


def test_mocked_hybrid_reranking_candidate_status_is_public_status_only() -> None:
    """Candidate metrics should stream as UI-only status text, not extra public fields."""
    agent = MockStreamAgent(
        [
            {"type": "status", "message": "Searching corpus..."},
            {"type": "status", "message": "Retrieved 7 candidates for reranking"},
            {"type": "status", "message": "Reranking candidates..."},
            {"type": "status", "message": "Using 2 chunks from 2 documents"},
            {"type": "token", "text": "answer"},
        ]
    )
    events = _post_completion(_make_client(agent))

    assert [event["event"] for event in events] == [
        "status",
        "status",
        "status",
        "status",
        "status",
        "token",
        "status",
        "done",
    ]
    _assert_status(events[2]["data"], "Retrieved 7 candidates for reranking")
    _assert_status(events[3]["data"], "Reranking candidates...")
    assert events[5] == {"event": "token", "data": {"text": "answer"}}
    _assert_status(events[6]["data"], "")


def test_mocked_status_type_edge_cases_are_normalized() -> None:
    agent = MockStreamAgent(
        [
            {"type": "status", "message": "Careful now", "status_type": "warn"},
            {"type": "status", "message": "Unknown type", "status_type": "debug"},
            {"type": "token", "text": "answer"},
        ]
    )
    events = _post_completion(_make_client(agent))

    _assert_status(events[1]["data"], "Careful now", "warn")
    _assert_status(events[2]["data"], "Unknown type", "info")


def test_mocked_agent_exception_emits_error_and_done() -> None:
    events = _post_completion(_make_client(MockStreamAgent(error=RuntimeError("model failed"))))

    assert [event["event"] for event in events] == ["status", "error", "status", "done"]
    _assert_status(events[0]["data"], "Preparing request...")
    assert events[1] == {"event": "error", "data": {"message": "model failed"}}
    _assert_status(events[2]["data"], "")
    assert events[3] == {"event": "done", "data": {}}


def test_mocked_empty_status_message_still_uses_simple_status_shape() -> None:
    agent = MockStreamAgent([{"type": "status"}, {"type": "token", "text": "answer"}])
    events = _post_completion(_make_client(agent))

    _assert_status(events[1]["data"], "")

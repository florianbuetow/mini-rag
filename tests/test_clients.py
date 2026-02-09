"""Unit tests for HTTP clients."""

from typing import Any

import pytest

import minirag.clients.base as base_module
from minirag.clients.base import BaseClient
from minirag.clients.indexing import IndexingClient
from minirag.clients.query import QueryClient


class FakeResponse:
    """Minimal fake HTTP response object."""

    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> object:
        return self._payload


class FakeHttpClient:
    """Fake httpx.Client context manager."""

    def __init__(self, responses: dict[tuple[str, str], FakeResponse]) -> None:
        self._responses = responses

    def __enter__(self) -> "FakeHttpClient":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        del exc_type, exc, traceback
        return False

    def get(self, path: str) -> FakeResponse:
        return self._responses[("GET", path)]

    def request(self, method: str, url: str, json: dict[str, object] | None) -> FakeResponse:
        del json
        return self._responses[(method, url)]


class DummyClient(BaseClient):
    """Concrete client exposing BaseClient internals for testing."""

    def send_request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        require_healthy: bool,
    ) -> dict[str, object]:
        """Expose protected _request for test coverage."""
        return self._request(method=method, path=path, payload=payload, require_healthy=require_healthy)


def test_base_client_request_and_health(monkeypatch: pytest.MonkeyPatch) -> None:
    """Base client should parse successful health and request responses."""
    responses = {
        ("GET", "/v1/health"): FakeResponse(200, {"status": 200, "data": {"status": "healthy"}}),
        ("POST", "/v1/corpus/books/index"): FakeResponse(200, {"status": 200, "data": {"ok": True}}),
    }

    def fake_client_factory(*_: Any, **__: Any) -> FakeHttpClient:
        return FakeHttpClient(responses)

    monkeypatch.setattr(base_module.httpx, "Client", fake_client_factory)

    client = DummyClient(host="127.0.0.1", port=7001, http_client=None)
    payload = client.send_request(method="POST", path="/v1/corpus/books/index", payload={"x": 1}, require_healthy=True)

    assert payload == {"ok": True}


def test_indexing_and_query_clients_parse_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Typed clients should parse index/query payloads into expected structures."""

    def fake_ensure_healthy(self: BaseClient) -> None:
        del self

    monkeypatch.setattr(BaseClient, "_ensure_healthy", fake_ensure_healthy)

    def fake_request(self: BaseClient, method: str, path: str, payload: object, require_healthy: bool) -> dict[str, object]:
        del self, payload, require_healthy
        if method == "POST" and path == "/v1/corpus/books/index":
            return {"document_id": 1, "chunk_ids": [1, 2, 3]}
        if method == "DELETE" and path == "/v1/corpus/books/index":
            return {"message": "index destroyed"}
        if method == "POST" and path.startswith("/v1/corpus/"):
            return {"results": [{"chunk_id": 1, "text": "x", "score": 0.9}]}
        return {"results": [{"chunk_id": 1, "text": "x", "score": 0.9}]}

    monkeypatch.setattr(BaseClient, "_request", fake_request)

    indexing = IndexingClient(host="127.0.0.1", port=7001, http_client=None)
    doc_id, chunk_ids = indexing.index_document("books", "hello")
    assert doc_id == 1
    assert chunk_ids == [1, 2, 3]
    indexing.destroy_index("books")

    query = QueryClient(host="127.0.0.1", port=7001, http_client=None)
    results = query.search_hybrid(corpus="books", query="hello", top_k=2)
    assert len(results) == 1
    assert results[0].text == "x"


def test_base_client_rejects_invalid_connection_params() -> None:
    """Client constructor should validate host and port values."""
    with pytest.raises(ValueError):
        DummyClient(host="", port=7001, http_client=None)

    with pytest.raises(ValueError):
        DummyClient(host="127.0.0.1", port=0, http_client=None)


class BrokenJsonResponse(FakeResponse):
    """Fake response that raises on json()."""

    def __init__(self, status_code: int) -> None:
        super().__init__(status_code, {})
        self.text = "not json"

    def json(self) -> object:
        raise ValueError("invalid json")


def test_invalid_json_response_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid JSON from service should raise RuntimeError."""
    responses = {
        ("GET", "/v1/health"): FakeResponse(200, {"status": 200, "data": {"status": "healthy"}}),
        ("POST", "/v1/test"): BrokenJsonResponse(200),
    }

    def fake_factory(*_: Any, **__: Any) -> FakeHttpClient:
        return FakeHttpClient(responses)

    monkeypatch.setattr(base_module.httpx, "Client", fake_factory)
    client = DummyClient(host="127.0.0.1", port=7001, http_client=None)

    with pytest.raises(RuntimeError, match="invalid JSON response"):
        client.send_request(method="POST", path="/v1/test", payload=None, require_healthy=False)


def test_status_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP status code mismatch with envelope status should raise RuntimeError."""
    responses = {
        ("POST", "/v1/test"): FakeResponse(200, {"status": 201, "data": {"ok": True}}),
    }

    def fake_factory(*_: Any, **__: Any) -> FakeHttpClient:
        return FakeHttpClient(responses)

    monkeypatch.setattr(base_module.httpx, "Client", fake_factory)
    client = DummyClient(host="127.0.0.1", port=7001, http_client=None)

    with pytest.raises(RuntimeError, match="status mismatch"):
        client.send_request(method="POST", path="/v1/test", payload=None, require_healthy=False)


def test_error_status_raises_with_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Error response (>=400) should raise RuntimeError with error message."""
    responses = {
        ("POST", "/v1/test"): FakeResponse(422, {"status": 422, "error": "field missing"}),
    }

    def fake_factory(*_: Any, **__: Any) -> FakeHttpClient:
        return FakeHttpClient(responses)

    monkeypatch.setattr(base_module.httpx, "Client", fake_factory)
    client = DummyClient(host="127.0.0.1", port=7001, http_client=None)

    with pytest.raises(RuntimeError, match="field missing"):
        client.send_request(method="POST", path="/v1/test", payload=None, require_healthy=False)


def test_unhealthy_service_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Health check returning unhealthy status should raise RuntimeError."""
    responses = {
        ("GET", "/v1/health"): FakeResponse(503, {"status": 503, "data": {"status": "shutting_down"}}),
    }

    def fake_factory(*_: Any, **__: Any) -> FakeHttpClient:
        return FakeHttpClient(responses)

    monkeypatch.setattr(base_module.httpx, "Client", fake_factory)
    client = DummyClient(host="127.0.0.1", port=7001, http_client=None)

    with pytest.raises(RuntimeError, match="shutting_down"):
        client.send_request(method="POST", path="/v1/test", payload=None, require_healthy=True)


def test_indexing_client_rejects_empty_corpus() -> None:
    """IndexingClient should reject empty corpus name."""
    indexing = IndexingClient(host="127.0.0.1", port=7001, http_client=None)

    with pytest.raises(ValueError, match="invalid corpus name"):
        indexing.index_document("", "hello")

    with pytest.raises(ValueError, match="invalid corpus name"):
        indexing.destroy_index("")


def test_query_client_rejects_empty_corpus() -> None:
    """QueryClient should reject empty corpus name."""
    query = QueryClient(host="127.0.0.1", port=7001, http_client=None)

    with pytest.raises(ValueError, match="invalid corpus name"):
        query.search_dense("", query="hello", top_k=3)

    with pytest.raises(ValueError, match="invalid corpus name"):
        query.search_sparse("", query="hello", top_k=3)

    with pytest.raises(ValueError, match="invalid corpus name"):
        query.search_hybrid("", query="hello", top_k=3)


def test_injected_http_client_is_used() -> None:
    """BaseClient should use the injected http_client when provided."""
    responses = {
        ("GET", "/v1/health"): FakeResponse(200, {"status": 200, "data": {"status": "healthy"}}),
        ("POST", "/v1/corpus/books/index"): FakeResponse(200, {"status": 200, "data": {"ok": True}}),
    }
    fake_client = FakeHttpClient(responses)

    client = DummyClient(host="127.0.0.1", port=7001, http_client=fake_client)  # type: ignore[arg-type]
    payload = client.send_request(method="POST", path="/v1/corpus/books/index", payload={"x": 1}, require_healthy=True)

    assert payload == {"ok": True}


def test_indexing_client_rejects_empty_text() -> None:
    """IndexingClient should reject empty document text."""
    indexing = IndexingClient(host="127.0.0.1", port=7001, http_client=None)

    with pytest.raises(ValueError, match="text must not be empty"):
        indexing.index_document("books", "")

    with pytest.raises(ValueError, match="text must not be empty"):
        indexing.index_document("books", "   ")


def test_query_client_rejects_empty_query() -> None:
    """QueryClient should reject empty query strings."""
    query = QueryClient(host="127.0.0.1", port=7001, http_client=None)

    with pytest.raises(ValueError, match="query must not be empty"):
        query.search_dense("books", query="", top_k=3)

    with pytest.raises(ValueError, match="query must not be empty"):
        query.search_dense("books", query="   ", top_k=3)


def test_query_client_rejects_non_positive_top_k() -> None:
    """QueryClient should reject non-positive top_k values."""
    query = QueryClient(host="127.0.0.1", port=7001, http_client=None)

    with pytest.raises(ValueError, match="top_k must be greater than 0"):
        query.search_dense("books", query="hello", top_k=0)

    with pytest.raises(ValueError, match="top_k must be greater than 0"):
        query.search_dense("books", query="hello", top_k=-1)

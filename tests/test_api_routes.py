"""Unit tests for API route handlers with fake app state backends."""

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

import minirag.api.routes_info as routes_info
from minirag.api.app import unhandled_exception_handler
from minirag.api.routes_citation import router as citation_router
from minirag.api.routes_index import router as index_router
from minirag.api.routes_info import router as info_router
from minirag.api.routes_query import router as query_router
from minirag.corpus import validate_corpus_name
from minirag.search.types import SearchResult

CORPUS = "test"


class FakeServiceConfig:
    """Fake service config object."""

    def __init__(self, reload: bool) -> None:
        self.reload = reload


class FakeConfig:
    """Fake config for route tests."""

    def model_dump(self) -> dict[str, object]:
        return {"service": {"host": "127.0.0.1", "port": 7001}}

    def get_service_config(self) -> FakeServiceConfig:
        return FakeServiceConfig(reload=False)


class FakeOrchestration:
    """Fake orchestration backend for route tests."""

    def __init__(self) -> None:
        self.citations: dict[str, dict[str, object]] = {}

    def index_document(self, text: str, citation: dict[str, object] | None = None) -> tuple[int, list[int]]:
        del text, citation
        return (1, [1, 2])

    def destroy_index(self) -> None:
        return None

    def close_storage(self) -> None:
        return None

    def get_citation(self, citation_key: str) -> dict[str, object] | None:
        return self.citations.get(citation_key)

    def search_dense(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        return [SearchResult(chunk_id=1, document_id=1, citation_key="key1", text="dense", score=0.9)]

    def search_sparse(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        return [SearchResult(chunk_id=2, document_id=1, citation_key="key1", text="sparse", score=0.8)]

    def search_hybrid(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        return [SearchResult(chunk_id=3, document_id=1, citation_key="key1", text="hybrid", score=0.85)]


class FakeCorpusManager:
    """Fake corpus manager wrapping a single orchestration instance."""

    def __init__(self, orchestration: object) -> None:
        self._orchestration = orchestration

    def get(self, corpus: str) -> object:
        validate_corpus_name(corpus)
        return self._orchestration

    def destroy(self, corpus: str) -> None:
        validate_corpus_name(corpus)
        orch = self._orchestration
        if hasattr(orch, "destroy_index"):
            orch.destroy_index()  # type: ignore[union-attr]


def make_test_client() -> TestClient:
    """Create FastAPI app with routers and fake state dependencies."""
    app = FastAPI()
    app.state.app_status = "healthy"
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager(FakeOrchestration())

    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(info_router)
    app.include_router(index_router)
    app.include_router(query_router)
    app.include_router(citation_router)

    return TestClient(app)


def test_info_and_health_routes() -> None:
    """Info and health routes should return expected envelopes."""
    client = make_test_client()

    health_response = client.get("/v1/health")
    assert health_response.status_code == 200

    info_response = client.get("/v1/info")
    assert info_response.status_code == 200
    assert "config" in info_response.json()["data"]


def test_index_and_query_routes() -> None:
    """Index and query routes should parse payloads and return results."""
    client = make_test_client()

    index_response = client.post(f"/v1/corpus/{CORPUS}/index", json={"document": "hello world"})
    assert index_response.status_code == 200
    assert index_response.json()["data"]["chunks_indexed"] == 2

    dense_response = client.post(f"/v1/corpus/{CORPUS}/query/dense", json={"query": "hello", "top_k": 3})
    assert dense_response.status_code == 200
    dense_data = dense_response.json()["data"]
    assert dense_data["results"][0]["document_id"] == 1
    assert dense_data["results"][0]["citation_key"] == "key1"

    sparse_response = client.post(f"/v1/corpus/{CORPUS}/query/sparse", json={"query": "hello", "top_k": 3})
    assert sparse_response.status_code == 200

    hybrid_response = client.post(f"/v1/corpus/{CORPUS}/query/hybrid", json={"query": "hello", "top_k": 3})
    assert hybrid_response.status_code == 200


def test_shutdown_and_guarded_routes(monkeypatch: Any) -> None:
    """Shutdown should switch app state and guarded routes should return 503."""

    def no_op_shutdown(reload_enabled: bool) -> None:
        del reload_enabled

    monkeypatch.setattr(routes_info, "_shutdown_process_tree", no_op_shutdown)
    client = make_test_client()

    shutdown_response = client.post("/v1/shutdown")
    assert shutdown_response.status_code == 200

    blocked_response = client.post(f"/v1/corpus/{CORPUS}/index", json={"document": "x"})
    assert blocked_response.status_code == 503


class ErrorOrchestration:
    """Orchestration fake that raises on all methods."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def index_document(self, text: str, citation: dict[str, object] | None = None) -> tuple[int, list[int]]:
        del text, citation
        raise self._error

    def destroy_index(self) -> None:
        raise self._error

    def close_storage(self) -> None:
        return None

    def get_citation(self, citation_key: str) -> dict[str, object] | None:
        del citation_key
        raise self._error

    def search_dense(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        raise self._error

    def search_sparse(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        raise self._error

    def search_hybrid(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        raise self._error


class ErrorCorpusManager:
    """Corpus manager wrapping ErrorOrchestration."""

    def __init__(self, error: Exception) -> None:
        self._orchestration = ErrorOrchestration(error)
        self._error = error

    def get(self, corpus: str) -> object:
        validate_corpus_name(corpus)
        return self._orchestration

    def destroy(self, corpus: str) -> None:
        validate_corpus_name(corpus)
        raise self._error


def _make_error_client(error: Exception) -> TestClient:
    app = FastAPI()
    app.state.app_status = "healthy"
    app.state.config = FakeConfig()
    app.state.corpus_manager = ErrorCorpusManager(error)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(info_router)
    app.include_router(index_router)
    app.include_router(query_router)
    app.include_router(citation_router)
    return TestClient(app)


def test_index_value_error_returns_400() -> None:
    """ValueError from orchestration should return 400."""
    client = _make_error_client(ValueError("bad input"))

    resp = client.post(f"/v1/corpus/{CORPUS}/index", json={"document": "hello world"})
    assert resp.status_code == 400
    assert "bad input" in resp.json()["error"]


def test_index_runtime_error_returns_500_with_message() -> None:
    """RuntimeError from orchestration should return 500 with error message."""
    client = _make_error_client(RuntimeError("boom"))

    resp = client.post(f"/v1/corpus/{CORPUS}/index", json={"document": "hello world"})
    assert resp.status_code == 500
    assert resp.json()["error"] == "boom"


def test_index_unexpected_error_returns_500() -> None:
    """Unexpected exception from orchestration should return 500."""
    client = _make_error_client(OSError("disk failed"))

    resp = client.post(f"/v1/corpus/{CORPUS}/index", json={"document": "hello world"})
    assert resp.status_code == 500
    assert resp.json()["error"] == "Internal server error"


def test_query_dense_value_error_returns_400() -> None:
    """ValueError from dense search should return 400."""
    client = _make_error_client(ValueError("bad query"))

    resp = client.post(f"/v1/corpus/{CORPUS}/query/dense", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 400
    assert "bad query" in resp.json()["error"]


def test_query_dense_runtime_error_returns_500_with_message() -> None:
    """RuntimeError from dense search should return 500 with error message."""
    client = _make_error_client(RuntimeError("boom"))

    resp = client.post(f"/v1/corpus/{CORPUS}/query/dense", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 500
    assert resp.json()["error"] == "boom"


def test_query_dense_unexpected_error_returns_500() -> None:
    """Unexpected exception from dense search should return 500."""
    client = _make_error_client(OSError("disk failed"))

    resp = client.post(f"/v1/corpus/{CORPUS}/query/dense", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 500
    assert resp.json()["error"] == "Internal server error"


def test_destroy_index_success() -> None:
    """DELETE /v1/corpus/{corpus}/index should return 200 with success message."""
    client = make_test_client()

    resp = client.delete(f"/v1/corpus/{CORPUS}/index")
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "index destroyed"


def test_destroy_index_runtime_error_returns_500_with_message() -> None:
    """RuntimeError from destroy should return 500 with error message."""
    client = _make_error_client(RuntimeError("disk failure"))

    resp = client.delete(f"/v1/corpus/{CORPUS}/index")
    assert resp.status_code == 500
    assert resp.json()["error"] == "disk failure"


def test_destroy_index_unexpected_error_returns_500() -> None:
    """Unexpected exception from destroy should return 500."""
    client = _make_error_client(OSError("disk failed"))

    resp = client.delete(f"/v1/corpus/{CORPUS}/index")
    assert resp.status_code == 500
    assert resp.json()["error"] == "Internal server error"


def test_destroy_index_when_shutting_down_returns_503(monkeypatch: Any) -> None:
    """DELETE /v1/corpus/{corpus}/index should return 503 when shutting down."""

    def no_op_shutdown(reload_enabled: bool) -> None:
        del reload_enabled

    monkeypatch.setattr(routes_info, "_shutdown_process_tree", no_op_shutdown)
    client = make_test_client()
    client.post("/v1/shutdown")

    resp = client.delete(f"/v1/corpus/{CORPUS}/index")
    assert resp.status_code == 503


def test_malformed_json_returns_400() -> None:
    """Malformed JSON body should return 400."""
    client = make_test_client()

    resp = client.post(f"/v1/corpus/{CORPUS}/index", content=b"not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400
    assert "error" in resp.json()

    resp = client.post(f"/v1/corpus/{CORPUS}/query/dense", content=b"{{bad}}", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400


def test_missing_required_fields_returns_422() -> None:
    """Missing required fields should return 422."""
    client = make_test_client()

    resp = client.post(f"/v1/corpus/{CORPUS}/index", json={"wrong_key": "x"})
    assert resp.status_code == 422

    resp = client.post(f"/v1/corpus/{CORPUS}/query/dense", json={"query": "hello"})
    assert resp.status_code == 422


def test_query_sparse_value_error_returns_400() -> None:
    """ValueError from sparse search should return 400."""
    client = _make_error_client(ValueError("bad sparse query"))

    resp = client.post(f"/v1/corpus/{CORPUS}/query/sparse", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 400
    assert "bad sparse query" in resp.json()["error"]


def test_query_sparse_runtime_error_returns_500_with_message() -> None:
    """RuntimeError from sparse search should return 500 with error message."""
    client = _make_error_client(RuntimeError("boom"))

    resp = client.post(f"/v1/corpus/{CORPUS}/query/sparse", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 500
    assert resp.json()["error"] == "boom"


def test_query_sparse_unexpected_error_returns_500() -> None:
    """Unexpected exception from sparse search should return 500."""
    client = _make_error_client(OSError("disk failed"))

    resp = client.post(f"/v1/corpus/{CORPUS}/query/sparse", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 500
    assert resp.json()["error"] == "Internal server error"


def test_query_hybrid_value_error_returns_400() -> None:
    """ValueError from hybrid search should return 400."""
    client = _make_error_client(ValueError("bad hybrid query"))

    resp = client.post(f"/v1/corpus/{CORPUS}/query/hybrid", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 400
    assert "bad hybrid query" in resp.json()["error"]


def test_query_hybrid_runtime_error_returns_500_with_message() -> None:
    """RuntimeError from hybrid search should return 500 with error message."""
    client = _make_error_client(RuntimeError("boom"))

    resp = client.post(f"/v1/corpus/{CORPUS}/query/hybrid", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 500
    assert resp.json()["error"] == "boom"


def test_query_hybrid_unexpected_error_returns_500() -> None:
    """Unexpected exception from hybrid search should return 500."""
    client = _make_error_client(OSError("disk failed"))

    resp = client.post(f"/v1/corpus/{CORPUS}/query/hybrid", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 500
    assert resp.json()["error"] == "Internal server error"


def test_invalid_field_values_return_422() -> None:
    """Invalid field values should return 422."""
    client = make_test_client()

    resp = client.post(f"/v1/corpus/{CORPUS}/index", json={"document": "   "})
    assert resp.status_code == 422

    resp = client.post(f"/v1/corpus/{CORPUS}/query/dense", json={"query": "hello", "top_k": 0})
    assert resp.status_code == 422


def test_invalid_corpus_name_returns_400() -> None:
    """Invalid corpus name should return 400."""
    client = make_test_client()

    resp = client.post("/v1/corpus/123bad/index", json={"document": "hello world"})
    assert resp.status_code == 400
    assert "invalid corpus name" in resp.json()["error"]

    resp = client.post("/v1/corpus/123bad/query/dense", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 400
    assert "invalid corpus name" in resp.json()["error"]

    resp = client.post("/v1/corpus/123bad/query/sparse", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 400
    assert "invalid corpus name" in resp.json()["error"]

    resp = client.post("/v1/corpus/123bad/query/hybrid", json={"query": "hello", "top_k": 3})
    assert resp.status_code == 400
    assert "invalid corpus name" in resp.json()["error"]

    resp = client.delete("/v1/corpus/123bad/index")
    assert resp.status_code == 400
    assert "invalid corpus name" in resp.json()["error"]


def test_citation_route_returns_200() -> None:
    """GET citation should return 200 with citation data when found."""
    orch = FakeOrchestration()
    citation_data: dict[str, object] = {
        "citation_key": "smith2026",
        "source_type": "journal",
        "common": {"title": "Test"},
        "source_data": {},
    }
    orch.citations["smith2026"] = citation_data

    app = FastAPI()
    app.state.app_status = "healthy"
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager(orch)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(citation_router)

    client = TestClient(app)
    resp = client.get(f"/v1/corpus/{CORPUS}/citation/smith2026")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["citation_key"] == "smith2026"
    assert data["source_type"] == "journal"


def test_citation_route_returns_full_citation_data() -> None:
    """GET citation should return all citation fields including common and source_data."""
    orch = FakeOrchestration()
    citation_data: dict[str, object] = {
        "citation_key": "martinez2026",
        "source_type": "research_story",
        "common": {"title": "The Quantum Discovery", "author": "Dr. Elena Martinez", "date": "2026-02-09", "language": "en"},
        "source_data": {"topic": "quantum_computing", "subtopics": ["quantum_error_correction"], "institution": "Stanford University"},
    }
    orch.citations["martinez2026"] = citation_data

    app = FastAPI()
    app.state.app_status = "healthy"
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager(orch)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(citation_router)

    client = TestClient(app)
    resp = client.get(f"/v1/corpus/{CORPUS}/citation/martinez2026")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["citation_key"] == "martinez2026"
    assert data["source_type"] == "research_story"
    assert data["common"]["title"] == "The Quantum Discovery"
    assert data["common"]["author"] == "Dr. Elena Martinez"
    assert data["common"]["date"] == "2026-02-09"
    assert data["common"]["language"] == "en"
    assert data["source_data"]["topic"] == "quantum_computing"
    assert data["source_data"]["subtopics"] == ["quantum_error_correction"]
    assert data["source_data"]["institution"] == "Stanford University"


def test_citation_route_returns_404_when_not_found() -> None:
    """GET citation should return 404 when citation_key does not exist."""
    client = make_test_client()
    resp = client.get(f"/v1/corpus/{CORPUS}/citation/nonexistent")
    assert resp.status_code == 404
    assert "citation not found" in resp.json()["error"]


def test_citation_route_value_error_returns_400() -> None:
    """ValueError from get_citation should return 400."""
    client = _make_error_client(ValueError("bad citation request"))

    resp = client.get(f"/v1/corpus/{CORPUS}/citation/somekey")
    assert resp.status_code == 400
    assert "bad citation request" in resp.json()["error"]


def test_citation_route_unexpected_error_returns_500() -> None:
    """Unexpected exception from get_citation should return 500."""
    client = _make_error_client(OSError("disk failed"))

    resp = client.get(f"/v1/corpus/{CORPUS}/citation/somekey")
    assert resp.status_code == 500
    assert resp.json()["error"] == "Internal server error"


def test_citation_route_invalid_corpus_returns_400() -> None:
    """GET citation with invalid corpus name should return 400."""
    client = make_test_client()
    resp = client.get("/v1/corpus/123bad/citation/somekey")
    assert resp.status_code == 400
    assert "invalid corpus name" in resp.json()["error"]


def test_citation_route_malformed_data_returns_500() -> None:
    """GET citation should return 500 when stored citation data is malformed."""
    orch = FakeOrchestration()
    orch.citations["bad_data"] = {"citation_key": "bad_data"}  # missing source_type, common, source_data

    app = FastAPI()
    app.state.app_status = "healthy"
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager(orch)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(citation_router)

    client = TestClient(app)
    resp = client.get(f"/v1/corpus/{CORPUS}/citation/bad_data")
    assert resp.status_code == 500
    assert "malformed citation data" in resp.json()["error"]

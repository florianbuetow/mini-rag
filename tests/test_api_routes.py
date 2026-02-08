"""Unit tests for API route handlers with fake app state backends."""

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

import minirag.api.routes_info as routes_info
from minirag.api.app import unhandled_exception_handler
from minirag.api.routes_index import router as index_router
from minirag.api.routes_info import router as info_router
from minirag.api.routes_query import router as query_router
from minirag.search.types import SearchResult


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

    def index_document(self, text: str) -> tuple[int, list[int]]:
        del text
        return (1, [1, 2])

    def destroy_index(self) -> None:
        return None

    def search_dense(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        return [SearchResult(chunk_id=1, text="dense", score=0.9)]

    def search_sparse(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        return [SearchResult(chunk_id=2, text="sparse", score=0.8)]

    def search_hybrid(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        return [SearchResult(chunk_id=3, text="hybrid", score=0.85)]


def make_test_client() -> TestClient:
    """Create FastAPI app with routers and fake state dependencies."""
    app = FastAPI()
    app.state.app_status = "healthy"
    app.state.config = FakeConfig()
    app.state.orchestration = FakeOrchestration()

    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(info_router)
    app.include_router(index_router)
    app.include_router(query_router)

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

    index_response = client.post("/v1/index", json={"document": "hello world"})
    assert index_response.status_code == 200
    assert index_response.json()["data"]["chunks_indexed"] == 2

    dense_response = client.post("/v1/query/dense", json={"query": "hello", "top_k": 3})
    assert dense_response.status_code == 200

    sparse_response = client.post("/v1/query/sparse", json={"query": "hello", "top_k": 3})
    assert sparse_response.status_code == 200

    hybrid_response = client.post("/v1/query/hybrid", json={"query": "hello", "top_k": 3})
    assert hybrid_response.status_code == 200


def test_shutdown_and_guarded_routes(monkeypatch: Any) -> None:
    """Shutdown should switch app state and guarded routes should return 503."""

    def no_op_shutdown(reload_enabled: bool) -> None:
        del reload_enabled

    monkeypatch.setattr(routes_info, "_shutdown_process_tree", no_op_shutdown)
    client = make_test_client()

    shutdown_response = client.post("/v1/shutdown")
    assert shutdown_response.status_code == 200

    blocked_response = client.post("/v1/index", json={"document": "x"})
    assert blocked_response.status_code == 503

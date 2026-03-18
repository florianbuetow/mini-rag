"""Unit tests for the corpus listing endpoint (GET /v1/corpora).

Spec: docs/specs/corpus-listing-specification.md
Test spec: docs/specs/corpus-listing-test-specification.md
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from minirag.api.app import unhandled_exception_handler
from minirag.api.routes_info import router as info_router


class FakeServiceConfig:
    def __init__(self, reload: bool) -> None:
        self.reload = reload


class FakeConfig:
    def model_dump(self):
        return {"service": {"host": "127.0.0.1", "port": 7001}}

    def get_service_config(self):
        return FakeServiceConfig(reload=False)


class FakeCorpusManager:
    def __init__(self, corpora: list[str]) -> None:
        self._corpora = corpora

    def list_corpora(self) -> list[str]:
        return sorted(self._corpora)


def _make_app(corpora: list[str], status: str = "healthy") -> FastAPI:
    app = FastAPI()
    app.state.app_status = status
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager(corpora)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(info_router)
    return app


# TS-1: List corpora successfully
def test_list_corpora_returns_sorted_list():
    client = TestClient(_make_app(["alpha", "beta", "gamma"]))

    resp = client.get("/v1/corpora")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == 200
    assert data["data"]["corpora"] == ["alpha", "beta", "gamma"]
    for name in data["data"]["corpora"]:
        assert isinstance(name, str)
        assert len(name) > 0


# TS-2: Corpora returned in alphabetical order
def test_list_corpora_alphabetical_order():
    client = TestClient(_make_app(["gamma", "alpha", "beta"]))

    resp = client.get("/v1/corpora")

    assert resp.status_code == 200
    assert resp.json()["data"]["corpora"] == ["alpha", "beta", "gamma"]


# TS-3: Reject request when service unhealthy
def test_list_corpora_returns_503_when_unhealthy():
    client = TestClient(_make_app(["alpha"], status="shutting_down"))

    resp = client.get("/v1/corpora")

    assert resp.status_code == 503


# TS-4: Return empty array when no corpora exist
def test_list_corpora_empty_when_none_exist():
    client = TestClient(_make_app([]))

    resp = client.get("/v1/corpora")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == 200
    assert data["data"]["corpora"] == []

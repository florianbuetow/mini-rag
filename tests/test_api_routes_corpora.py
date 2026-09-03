"""Unit tests for the corpus listing endpoint (GET /v1/corpora).

Spec: docs/specs/corpus-listing-specification.md
Test spec: docs/specs/corpus-listing-test-specification.md
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from minirag.api.app import unhandled_exception_handler
from minirag.api.routes_info import router as info_router
from minirag.corpus import validate_corpus_name

NO_DESCRIPTION_AVAILABLE = "No description available."


class FakeServiceConfig:
    def __init__(self, reload: bool) -> None:
        self.reload = reload


class FakeConfig:
    def model_dump(self):
        return {"service": {"host": "127.0.0.1", "port": 7001}}

    def get_service_config(self):
        return FakeServiceConfig(reload=False)


class FakeCorpusManager:
    def __init__(
        self,
        corpora: list[str],
        descriptions: dict[str, str] | None = None,
        description_error: Exception | None = None,
    ) -> None:
        self._corpora = corpora
        self._descriptions = descriptions or {}
        self._description_error = description_error

    def list_corpora(self) -> list[str]:
        return sorted(self._corpora)

    def corpus_description(self, corpus: str) -> str:
        validate_corpus_name(corpus)
        if corpus not in self._corpora:
            raise FileNotFoundError(f"Corpus not found: {corpus}")
        if self._description_error is not None:
            raise self._description_error
        return self._descriptions.get(corpus, NO_DESCRIPTION_AVAILABLE)

    def corpus_descriptions(self, corpora: list[str] | None = None) -> dict[str, str]:
        names = self.list_corpora() if corpora is None else corpora
        return {name: self.corpus_description(name) for name in names}


def _make_app(
    corpora: list[str],
    status: str = "healthy",
    descriptions: dict[str, str] | None = None,
    description_error: Exception | None = None,
) -> FastAPI:
    app = FastAPI()
    app.state.app_status = status
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager(corpora, descriptions, description_error)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(info_router)
    return app


# TS-1: List corpora successfully
def test_list_corpora_returns_sorted_list():
    client = TestClient(_make_app(["alpha", "beta", "gamma"], descriptions={"alpha": "# Alpha"}))

    resp = client.get("/v1/corpora")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == 200
    assert data["data"]["corpora"] == ["alpha", "beta", "gamma"]
    assert data["data"]["descriptions"] == {
        "alpha": "# Alpha",
        "beta": NO_DESCRIPTION_AVAILABLE,
        "gamma": NO_DESCRIPTION_AVAILABLE,
    }
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
    assert data["data"]["descriptions"] == {}


def test_get_corpus_description_returns_markdown():
    client = TestClient(_make_app(["books"], descriptions={"books": "# Books\nReference material."}))

    resp = client.get("/v1/corpus/books/description")

    assert resp.status_code == 200
    assert resp.json()["data"] == {"corpus": "books", "description": "# Books\nReference material."}


def test_get_corpus_description_returns_placeholder_when_missing():
    client = TestClient(_make_app(["books"]))

    resp = client.get("/v1/corpus/books/description")

    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == NO_DESCRIPTION_AVAILABLE


def test_get_corpus_description_rejects_invalid_name():
    client = TestClient(_make_app(["books"]))

    resp = client.get("/v1/corpus/invalid.name/description")

    assert resp.status_code == 400


def test_get_corpus_description_returns_404_for_unknown_corpus():
    client = TestClient(_make_app(["books"]))

    resp = client.get("/v1/corpus/notes/description")

    assert resp.status_code == 404


def test_get_corpus_description_respects_health_guard():
    client = TestClient(_make_app(["books"], status="shutting_down"))

    resp = client.get("/v1/corpus/books/description")

    assert resp.status_code == 503


@pytest.mark.parametrize("error", [OSError("disk failed"), UnicodeError("invalid UTF-8")])
def test_get_corpus_description_returns_500_for_storage_failure(error: Exception):
    client = TestClient(_make_app(["books"], description_error=error))

    resp = client.get("/v1/corpus/books/description")

    assert resp.status_code == 500
    assert resp.json()["error"] == "Failed to read corpus description"


def test_list_corpora_returns_500_when_description_read_fails():
    client = TestClient(_make_app(["books"], description_error=UnicodeError("invalid UTF-8")))

    resp = client.get("/v1/corpora")

    assert resp.status_code == 500
    assert resp.json()["error"] == "Failed to list corpus descriptions"

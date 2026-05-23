"""Unit tests for FastAPI app factory wiring."""

from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI, Request
from starlette.types import Scope

import minirag.api.app as app_module
from minirag.config import Config


class FakeIndexConfig:
    """Fake index config tree."""

    class Embeddings:
        model_name = "cc.en.300.bin"
        dimension = 300

    class Storage:
        db_filename = "minirag.db"

    class Faiss:
        nprobe = 1

    class Tantivy:
        language = "en"
        stemming = True

    class Chunking:
        chunk_size = 300
        overlap = 0.3

    embeddings = Embeddings()
    storage = Storage()
    faiss = Faiss()
    tantivy = Tantivy()
    chunking = Chunking()


class FakeConfig:
    """Fake config object for app factory tests."""

    class SearchConfig:
        class Reranking:
            def __init__(self, enabled: bool) -> None:
                self.enabled = enabled
                self.model_name = "cross-encoder/ms-marco-MiniLM-L12-v2"
                self.candidate_multiplier = 3

        def __init__(self, reranking_enabled: bool) -> None:
            self.reranking = FakeConfig.SearchConfig.Reranking(enabled=reranking_enabled)

    def __init__(self, data_dir: Path, reranking_enabled: bool) -> None:
        self._data_dir = data_dir
        self._search = FakeConfig.SearchConfig(reranking_enabled=reranking_enabled)

    def resolve_data_dir(self, project_root: Path) -> Path:
        del project_root
        return self._data_dir

    def get_index_config(self) -> FakeIndexConfig:
        return FakeIndexConfig()

    def get_search_config(self) -> object:
        return self._search


def _prepare_startup_data_dir(data_dir: Path) -> None:
    model_dir = data_dir / "models"
    model_dir.mkdir(parents=True)
    (model_dir / "cc.en.300.bin").write_bytes(b"model")


def test_create_app_wires_state_and_routes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """App factory should create app state with corpus_manager and include routers."""
    fake_config = cast(Config, FakeConfig(tmp_path / "data", reranking_enabled=False))
    _prepare_startup_data_dir(tmp_path / "data")

    def fake_embeddings(model_path: Path, expected_dimension: int) -> object:
        del model_path, expected_dimension
        return object()

    def fake_corpus_manager(
        data_dir: Path,
        index_config: object,
        search_config: object,
        embeddings: object,
        backend_factory: object,
        reranker: object,
    ) -> object:
        del data_dir, index_config, search_config, embeddings, backend_factory, reranker
        return object()

    monkeypatch.setattr(app_module, "FastTextEmbeddings", fake_embeddings)
    monkeypatch.setattr(app_module, "CorpusManager", fake_corpus_manager)

    app = app_module.create_app(config=fake_config, project_root=tmp_path)

    assert isinstance(app, FastAPI)
    assert hasattr(app.state, "config")
    assert hasattr(app.state, "corpus_manager")
    assert not hasattr(app.state, "orchestration")
    assert not hasattr(app.state, "storage")
    assert app.state.app_status == "healthy"


@pytest.mark.asyncio
async def test_lifespan_calls_close_all_on_shutdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Lifespan context manager should call corpus_manager.close_all() on shutdown."""
    fake_config = cast(Config, FakeConfig(tmp_path / "data", reranking_enabled=False))
    _prepare_startup_data_dir(tmp_path / "data")

    close_all_called = False

    class TrackingCorpusManager:
        def close_all(self) -> None:
            nonlocal close_all_called
            close_all_called = True

    def fake_embeddings(model_path: Path, expected_dimension: int) -> object:
        del model_path, expected_dimension
        return object()

    def fake_corpus_manager(**kwargs: object) -> TrackingCorpusManager:
        del kwargs
        return TrackingCorpusManager()

    monkeypatch.setattr(app_module, "FastTextEmbeddings", fake_embeddings)
    monkeypatch.setattr(app_module, "CorpusManager", fake_corpus_manager)

    app = app_module.create_app(config=fake_config, project_root=tmp_path)

    # Run through the lifespan context
    async with app_module.lifespan(app):
        pass

    assert close_all_called, "close_all() was not called during shutdown"


@pytest.mark.asyncio
async def test_unhandled_exception_handler_wraps_error() -> None:
    """Unhandled exception handler should return error envelope."""
    app = FastAPI()
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
        "scheme": "http",
        "http_version": "1.1",
        "root_path": "",
        "app": app,
    }
    request = Request(scope)

    response = await app_module.unhandled_exception_handler(request, RuntimeError("boom"))

    assert response.status_code == 500
    assert response.body == b'{"status":500,"error":"boom"}'


def test_create_app_builds_reranker_when_enabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """App factory should build reranker and pass it into CorpusManager."""
    fake_config = cast(Config, FakeConfig(tmp_path / "data", reranking_enabled=True))
    _prepare_startup_data_dir(tmp_path / "data")
    captured: dict[str, object] = {}

    def fake_embeddings(model_path: Path, expected_dimension: int) -> object:
        del model_path, expected_dimension
        return object()

    def fake_reranker(model_name: str, model_cache_dir: Path, candidate_multiplier: int) -> object:
        captured["model_name"] = model_name
        captured["model_cache_dir"] = model_cache_dir
        captured["candidate_multiplier"] = candidate_multiplier
        return "reranker-object"

    def fake_corpus_manager(
        data_dir: Path,
        index_config: object,
        search_config: object,
        embeddings: object,
        backend_factory: object,
        reranker: object,
    ) -> object:
        del data_dir, index_config, search_config, embeddings, backend_factory
        captured["reranker"] = reranker
        return object()

    monkeypatch.setattr(app_module, "FastTextEmbeddings", fake_embeddings)
    monkeypatch.setattr(app_module, "CrossEncoderReranker", fake_reranker)
    monkeypatch.setattr(app_module, "CorpusManager", fake_corpus_manager)

    app_module.create_app(config=fake_config, project_root=tmp_path)

    assert captured["model_name"] == "cross-encoder/ms-marco-MiniLM-L12-v2"
    assert captured["model_cache_dir"] == tmp_path / "data" / "models"
    assert captured["candidate_multiplier"] == 3
    assert captured["reranker"] == "reranker-object"

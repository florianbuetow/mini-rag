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

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def validate_startup(self, project_root: Path) -> None:
        del project_root

    def resolve_data_dir(self, project_root: Path) -> Path:
        del project_root
        return self._data_dir

    def get_index_config(self) -> FakeIndexConfig:
        return FakeIndexConfig()

    def get_search_config(self) -> object:
        return object()


def test_create_app_wires_state_and_routes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """App factory should create app state and include routers."""
    fake_config = cast(Config, FakeConfig(tmp_path / "data"))

    def fake_embeddings(model_path: Path, expected_dimension: int) -> object:
        del model_path, expected_dimension
        return object()

    def fake_storage(database_path: Path) -> object:
        del database_path
        return object()

    def fake_dense(dimension: int, index_dir: Path, nprobe: int) -> object:
        del dimension, index_dir, nprobe
        return object()

    def fake_sparse(index_dir: Path, language: str, stemming: bool) -> object:
        del index_dir, language, stemming
        return object()

    def fake_orchestration(
        chunking_config: object,
        embeddings: object,
        storage: object,
        dense: object,
        sparse: object,
        search_config: object,
    ) -> object:
        del chunking_config, embeddings, storage, dense, sparse, search_config
        return object()

    monkeypatch.setattr(app_module, "FastTextEmbeddings", fake_embeddings)
    monkeypatch.setattr(app_module, "SQLiteStorage", fake_storage)
    monkeypatch.setattr(app_module, "FAISSDense", fake_dense)
    monkeypatch.setattr(app_module, "TantivySparse", fake_sparse)
    monkeypatch.setattr(app_module, "Orchestration", fake_orchestration)

    app = app_module.create_app(config=fake_config, project_root=tmp_path)

    assert isinstance(app, FastAPI)
    assert hasattr(app.state, "config")
    assert hasattr(app.state, "orchestration")
    assert app.state.app_status == "healthy"


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

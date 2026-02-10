"""Unit tests for backend orchestration factory construction and cleanup."""

from pathlib import Path
from typing import Any

import pytest

import minirag.backend_factory as factory_module


class FakeIndexConfig:
    """Minimal index config shape used by backend factory tests."""

    class Storage:
        db_filename = "minirag.db"

    class Embeddings:
        dimension = 300

    class Faiss:
        nprobe = 7

    class Tantivy:
        language = "en"
        stemming = True

    class Chunking:
        pass

    storage = Storage()
    embeddings = Embeddings()
    faiss = Faiss()
    tantivy = Tantivy()
    chunking = Chunking()


class FakeStorage:
    """Fake storage that tracks close calls."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeDense:
    """Fake dense backend that tracks destroy calls."""

    def __init__(self, dimension: int, index_dir: Path, nprobe: int) -> None:
        self.dimension = dimension
        self.index_dir = index_dir
        self.nprobe = nprobe
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


class FakeSparse:
    """Fake sparse backend."""

    def __init__(self, index_dir: Path, language: str, stemming: bool) -> None:
        self.index_dir = index_dir
        self.language = language
        self.stemming = stemming


def test_build_orchestration_happy_path_constructs_expected_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Factory should build all backends using corpus-scoped paths and arguments."""
    captured: dict[str, Any] = {}

    def fake_orchestration(**kwargs: object) -> object:
        captured["orchestration_kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setattr(factory_module, "SQLiteStorage", FakeStorage)
    monkeypatch.setattr(factory_module, "FAISSDense", FakeDense)
    monkeypatch.setattr(factory_module, "TantivySparse", FakeSparse)
    monkeypatch.setattr(factory_module, "Orchestration", fake_orchestration)

    data_dir = tmp_path / "data"
    index_config = FakeIndexConfig()
    search_config = object()
    embeddings = object()

    result = factory_module.build_orchestration(
        corpus="books",
        data_dir=data_dir,
        index_config=index_config,  # type: ignore[arg-type]
        search_config=search_config,  # type: ignore[arg-type]
        embeddings=embeddings,  # type: ignore[arg-type]
    )

    assert result == {"ok": True}
    kwargs = captured["orchestration_kwargs"]
    storage = kwargs["storage"]
    dense = kwargs["dense"]
    sparse = kwargs["sparse"]

    assert isinstance(storage, FakeStorage)
    assert isinstance(dense, FakeDense)
    assert isinstance(sparse, FakeSparse)

    assert storage.database_path == data_dir / "storage" / "books" / "minirag.db"
    assert dense.dimension == 300
    assert dense.nprobe == 7
    assert dense.index_dir == data_dir / "index" / "books" / "faiss"
    assert sparse.index_dir == data_dir / "index" / "books" / "tantivy"
    assert sparse.language == "en"
    assert sparse.stemming is True


def test_build_orchestration_closes_storage_when_faiss_init_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Factory should close storage when FAISS initialization fails."""
    created_storage: list[FakeStorage] = []

    class FailingDense:
        def __init__(self, dimension: int, index_dir: Path, nprobe: int) -> None:
            del dimension, index_dir, nprobe
            raise RuntimeError("faiss failed")

    def fake_storage(database_path: Path) -> FakeStorage:
        storage = FakeStorage(database_path=database_path)
        created_storage.append(storage)
        return storage

    monkeypatch.setattr(factory_module, "SQLiteStorage", fake_storage)
    monkeypatch.setattr(factory_module, "FAISSDense", FailingDense)

    with pytest.raises(RuntimeError, match="faiss failed"):
        factory_module.build_orchestration(
            corpus="books",
            data_dir=tmp_path / "data",
            index_config=FakeIndexConfig(),  # type: ignore[arg-type]
            search_config=object(),  # type: ignore[arg-type]
            embeddings=object(),  # type: ignore[arg-type]
        )

    assert len(created_storage) == 1
    assert created_storage[0].closed is True


def test_build_orchestration_closes_storage_and_destroys_dense_when_tantivy_init_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Factory should destroy dense and close storage when Tantivy initialization fails."""
    created_storage: list[FakeStorage] = []
    created_dense: list[FakeDense] = []

    class FailingSparse:
        def __init__(self, index_dir: Path, language: str, stemming: bool) -> None:
            del index_dir, language, stemming
            raise RuntimeError("tantivy failed")

    def fake_storage(database_path: Path) -> FakeStorage:
        storage = FakeStorage(database_path=database_path)
        created_storage.append(storage)
        return storage

    def fake_dense(dimension: int, index_dir: Path, nprobe: int) -> FakeDense:
        dense = FakeDense(dimension=dimension, index_dir=index_dir, nprobe=nprobe)
        created_dense.append(dense)
        return dense

    monkeypatch.setattr(factory_module, "SQLiteStorage", fake_storage)
    monkeypatch.setattr(factory_module, "FAISSDense", fake_dense)
    monkeypatch.setattr(factory_module, "TantivySparse", FailingSparse)

    with pytest.raises(RuntimeError, match="tantivy failed"):
        factory_module.build_orchestration(
            corpus="books",
            data_dir=tmp_path / "data",
            index_config=FakeIndexConfig(),  # type: ignore[arg-type]
            search_config=object(),  # type: ignore[arg-type]
            embeddings=object(),  # type: ignore[arg-type]
        )

    assert len(created_storage) == 1
    assert created_storage[0].closed is True
    assert len(created_dense) == 1
    assert created_dense[0].destroyed is True

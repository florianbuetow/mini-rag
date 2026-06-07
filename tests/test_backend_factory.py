"""Unit tests for backend orchestration factory construction and cleanup."""

from pathlib import Path
from typing import Any

import pytest
import tiktoken

import minirag.backend_factory as factory_module
from minirag.config import IndexConfig


class FakeEmbeddingsConfig:
    """Minimal embeddings config shape with a provider-aware active dimension."""

    def __init__(self, provider: str = "fasttext", dimension: int = 300) -> None:
        self.provider = provider
        self.model_name = "cc.en.300.bin"
        self.dimension = dimension
        self.lmstudio = None

    def active_dimension(self) -> int:
        return self.dimension


class FakeIndexConfig:
    """Minimal index config shape used by backend factory tests."""

    class Storage:
        db_filename = "minirag.db"

    class Faiss:
        nprobe = 7

    class Tantivy:
        language = "en"
        stemming = True

    class Chunking:
        chunk_size = 4
        overlap = 0.5

    def __init__(self, embeddings: FakeEmbeddingsConfig | None = None) -> None:
        self.storage = self.Storage()
        self.embeddings = embeddings if embeddings is not None else FakeEmbeddingsConfig()
        self.faiss = self.Faiss()
        self.tantivy = self.Tantivy()
        self.chunking = self.Chunking()


class FakeStorage:
    """Fake storage that tracks close calls."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeDense:
    """Fake dense backend that tracks close calls."""

    def __init__(self, dimension: int, index_dir: Path, nprobe: int) -> None:
        self.dimension = dimension
        self.index_dir = index_dir
        self.nprobe = nprobe
        self.closed = False

    def close(self) -> None:
        self.closed = True


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
        reranker=None,
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
    assert kwargs["reranker"] is None


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
            reranker=None,
        )

    assert len(created_storage) == 1
    assert created_storage[0].closed is True


def test_build_orchestration_closes_storage_and_closes_dense_when_tantivy_init_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Factory should close dense and storage when Tantivy initialization fails."""
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
            reranker=None,
        )

    assert len(created_storage) == 1
    assert created_storage[0].closed is True
    assert len(created_dense) == 1
    assert created_dense[0].closed is True


def test_build_orchestration_raises_exception_group_when_faiss_init_and_storage_close_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Factory should report both init and cleanup failures from FAISS path."""

    class FailingStorage:
        def __init__(self, database_path: Path) -> None:
            self.database_path = database_path

        def close(self) -> None:
            raise RuntimeError("storage close failed")

    class FailingDense:
        def __init__(self, dimension: int, index_dir: Path, nprobe: int) -> None:
            del dimension, index_dir, nprobe
            raise RuntimeError("faiss failed")

    monkeypatch.setattr(factory_module, "SQLiteStorage", FailingStorage)
    monkeypatch.setattr(factory_module, "FAISSDense", FailingDense)

    with pytest.raises(ExceptionGroup) as exc_info:
        factory_module.build_orchestration(
            corpus="books",
            data_dir=tmp_path / "data",
            index_config=FakeIndexConfig(),  # type: ignore[arg-type]
            search_config=object(),  # type: ignore[arg-type]
            embeddings=object(),  # type: ignore[arg-type]
            reranker=None,
        )

    messages = [str(err) for err in exc_info.value.exceptions]
    assert any("faiss failed" in message for message in messages)
    assert any("storage close failed" in message for message in messages)


def test_build_orchestration_raises_exception_group_when_tantivy_init_and_cleanup_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Factory should report Tantivy init error plus dense/storage cleanup failures."""

    class FailingStorage:
        def __init__(self, database_path: Path) -> None:
            self.database_path = database_path

        def close(self) -> None:
            raise RuntimeError("storage close failed")

    class FailingDenseClose:
        def __init__(self, dimension: int, index_dir: Path, nprobe: int) -> None:
            del dimension, index_dir, nprobe

        def close(self) -> None:
            raise RuntimeError("dense close failed")

    class FailingSparse:
        def __init__(self, index_dir: Path, language: str, stemming: bool) -> None:
            del index_dir, language, stemming
            raise RuntimeError("tantivy failed")

    monkeypatch.setattr(factory_module, "SQLiteStorage", FailingStorage)
    monkeypatch.setattr(factory_module, "FAISSDense", FailingDenseClose)
    monkeypatch.setattr(factory_module, "TantivySparse", FailingSparse)

    with pytest.raises(ExceptionGroup) as exc_info:
        factory_module.build_orchestration(
            corpus="books",
            data_dir=tmp_path / "data",
            index_config=FakeIndexConfig(),  # type: ignore[arg-type]
            search_config=object(),  # type: ignore[arg-type]
            embeddings=object(),  # type: ignore[arg-type]
            reranker=None,
        )

    messages = [str(err) for err in exc_info.value.exceptions]
    assert any("tantivy failed" in message for message in messages)
    assert any("dense close failed" in message for message in messages)
    assert any("storage close failed" in message for message in messages)


@pytest.mark.parametrize(("provider", "dimension"), [("fasttext", 300), ("lmstudio", 1024)])
def test_dense_index_uses_active_provider_dimension(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, provider: str, dimension: int) -> None:
    """The dense index is created with the active provider's embedding dimension."""
    captured: dict[str, Any] = {}

    def fake_orchestration(**kwargs: object) -> object:
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(factory_module, "SQLiteStorage", FakeStorage)
    monkeypatch.setattr(factory_module, "FAISSDense", FakeDense)
    monkeypatch.setattr(factory_module, "TantivySparse", FakeSparse)
    monkeypatch.setattr(factory_module, "Orchestration", fake_orchestration)

    index_config = FakeIndexConfig(FakeEmbeddingsConfig(provider=provider, dimension=dimension))
    factory_module.build_orchestration(
        corpus="books",
        data_dir=tmp_path / "data",
        index_config=index_config,  # type: ignore[arg-type]
        search_config=object(),  # type: ignore[arg-type]
        embeddings=object(),  # type: ignore[arg-type]
        reranker=None,
    )

    assert captured["kwargs"]["dense"].dimension == dimension


def _index_config(embeddings: dict[str, Any], chunking: dict[str, Any]) -> IndexConfig:
    return IndexConfig.model_validate(
        {
            "chunking": chunking,
            "embeddings": embeddings,
            "storage": {"db_filename": "minirag.db"},
            "faiss": {"index_type": "IndexFlatIP", "nprobe": 1},
            "tantivy": {"language": "en", "stemming": True},
        }
    )


def test_build_chunker_selects_word_chunker_for_fasttext() -> None:
    """The fastText provider yields a word-based chunker."""
    index_config = _index_config(
        embeddings={"provider": "fasttext", "model_name": "cc.en.300.bin", "dimension": 300},
        chunking={"chunk_size": 4, "overlap": 0.5},
    )

    chunks = factory_module.build_chunker(index_config)("one two three four five six")

    assert chunks[0] == "one two three four"


def test_build_chunker_selects_token_chunker_for_lmstudio() -> None:
    """The LM Studio provider yields a token-budget chunker bounded by 80% of the window."""
    index_config = _index_config(
        embeddings={
            "provider": "lmstudio",
            "model_name": "cc.en.300.bin",
            "dimension": 300,
            "lmstudio": {
                "base_url": "http://127.0.0.1:1234/v1",
                "model_name": "bge",
                "dimension": 1024,
                "max_input_tokens": 512,
                "safety_fraction": 0.80,
            },
        },
        chunking={"chunk_size": 4, "overlap": 0.3},
    )

    long_text = " ".join(f"word{i}" for i in range(2000))
    chunks = factory_module.build_chunker(index_config)(long_text)

    encoding = tiktoken.get_encoding("cl100k_base")
    assert len(chunks) > 1
    assert all(len(encoding.encode(chunk)) <= 409 for chunk in chunks)

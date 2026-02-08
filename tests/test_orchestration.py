"""Unit tests for orchestration coordination logic."""

from typing import Final, cast

import pytest

from minirag.config import ChunkingConfig, DenseSearchConfig, HybridConfig, SearchConfig, SparseSearchConfig
from minirag.orchestration import Orchestration
from minirag.retrieval.dense_interface import DenseRetrieval
from minirag.retrieval.sparse_interface import SparseRetrieval
from minirag.search.embeddings import FastTextEmbeddings
from minirag.search.types import SearchResult
from minirag.storage.interface import Storage


class FakeEmbeddings:
    """Fake embeddings provider."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]


class FakeStorage:
    """Fake storage backend."""

    def __init__(self) -> None:
        self.documents: dict[int, str] = {}
        self.chunks: dict[int, tuple[int, str]] = {}
        self._next_document_id = 1
        self._next_chunk_id = 1

    def insert_document(self, content: str) -> int:
        document_id = self._next_document_id
        self._next_document_id = self._next_document_id + 1
        self.documents[document_id] = content
        return document_id

    def insert_chunk(self, document_id: int, content: str) -> int:
        chunk_id = self._next_chunk_id
        self._next_chunk_id = self._next_chunk_id + 1
        self.chunks[chunk_id] = (document_id, content)
        return chunk_id

    def get_document(self, document_id: int) -> str:
        return self.documents[document_id]

    def get_chunk(self, chunk_id: int) -> tuple[int, str]:
        return self.chunks[chunk_id]

    def destroy(self) -> None:
        self.documents = {}
        self.chunks = {}


class FakeDense:
    """Fake dense retrieval backend."""

    def __init__(self) -> None:
        self.indexed: dict[int, list[float]] = {}

    def index(self, chunk_id: int, embedding: list[float]) -> None:
        self.indexed[chunk_id] = embedding

    def search(self, query_embedding: list[float], top_k: int) -> list[tuple[int, float]]:
        del query_embedding
        sorted_ids = sorted(self.indexed.keys())
        return [(chunk_id, 1.0 - 0.1 * idx) for idx, chunk_id in enumerate(sorted_ids[:top_k])]

    def destroy(self) -> None:
        self.indexed = {}


class FakeSparse:
    """Fake sparse retrieval backend."""

    def __init__(self) -> None:
        self.indexed: dict[int, str] = {}

    def index(self, chunk_id: int, content: str) -> None:
        self.indexed[chunk_id] = content

    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        del query
        sorted_ids = sorted(self.indexed.keys(), reverse=True)
        return [(chunk_id, 1.0 - 0.1 * idx) for idx, chunk_id in enumerate(sorted_ids[:top_k])]

    def destroy(self) -> None:
        self.indexed = {}


def make_orchestration() -> Orchestration:
    """Create orchestration with fake dependencies."""
    search_config = SearchConfig(
        hybrid=HybridConfig(alpha=0.5),
        dense=DenseSearchConfig(),
        sparse=SparseSearchConfig(),
    )

    return Orchestration(
        chunking_config=ChunkingConfig(chunk_size=4, overlap=0.5),
        embeddings=cast(FastTextEmbeddings, FakeEmbeddings()),
        storage=cast(Storage, FakeStorage()),
        dense=cast(DenseRetrieval, FakeDense()),
        sparse=cast(SparseRetrieval, FakeSparse()),
        search_config=search_config,
    )


def test_orchestration_index_and_search() -> None:
    """Orchestration should index and execute all search modes."""
    orchestration = make_orchestration()
    text: Final[str] = "one two three four five six"

    document_id, chunk_ids = orchestration.index_document(text)

    assert document_id == 1
    assert len(chunk_ids) >= 2

    dense_results = orchestration.search_dense(query="one", top_k=5)
    sparse_results = orchestration.search_sparse(query="one", top_k=5)
    hybrid_results = orchestration.search_hybrid(query="one", top_k=5)

    assert len(dense_results) >= 1
    assert len(sparse_results) >= 1
    assert len(hybrid_results) >= 1
    assert isinstance(hybrid_results[0], SearchResult)


def test_orchestration_destroy_and_validation() -> None:
    """Destroy should clear backends and invalid inputs should fail."""
    orchestration = make_orchestration()
    orchestration.index_document("one two three four five")
    orchestration.destroy_index()

    assert orchestration.search_dense(query="q", top_k=3) == []

    with pytest.raises(ValueError):
        orchestration.index_document("  ")

    with pytest.raises(ValueError):
        orchestration.search_sparse(query="", top_k=1)

    with pytest.raises(ValueError):
        orchestration.search_hybrid(query="q", top_k=0)

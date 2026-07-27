"""Regression tests for idempotent document re-indexing."""

from functools import partial
from pathlib import Path
from typing import cast

from minirag.config import DenseSearchConfig, HybridConfig, RerankingConfig, SearchConfig, SparseSearchConfig
from minirag.ingestion.chunker import chunk_text
from minirag.orchestration import Orchestration
from minirag.retrieval.dense_interface import DenseRetrieval
from minirag.retrieval.sparse_interface import SparseRetrieval
from minirag.search.embeddings_interface import Embeddings
from minirag.search.types import ScoredChunk
from minirag.storage.interface import Storage
from minirag.storage.sqlite import SQLiteStorage


class FakeEmbeddings:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]


class TrackingDense:
    def __init__(self) -> None:
        self.indexed: dict[int, list[float]] = {}
        self.removed: list[list[int]] = []

    def index(self, chunk_id: int, embedding: list[float]) -> None:
        self.indexed[chunk_id] = embedding

    def remove_ids(self, chunk_ids: list[int]) -> int:
        self.removed.append(list(chunk_ids))
        removed = 0
        for chunk_id in chunk_ids:
            if chunk_id in self.indexed:
                removed += 1
                del self.indexed[chunk_id]
        return removed

    def search(self, query_embedding: list[float], top_k: int) -> list[ScoredChunk]:
        del query_embedding
        return [ScoredChunk(chunk_id=chunk_id, score=1.0) for chunk_id in sorted(self.indexed)[:top_k]]

    def persist(self) -> None:
        pass

    def destroy(self) -> None:
        self.indexed = {}


class TrackingSparse:
    def __init__(self) -> None:
        self.indexed: dict[int, str] = {}
        self.removed: list[list[int]] = []

    def index(self, chunk_id: int, content: str) -> None:
        self.indexed[chunk_id] = content

    def remove_ids(self, chunk_ids: list[int]) -> None:
        self.removed.append(list(chunk_ids))
        for chunk_id in chunk_ids:
            self.indexed.pop(chunk_id, None)

    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        del query
        return [ScoredChunk(chunk_id=chunk_id, score=1.0) for chunk_id in sorted(self.indexed)[:top_k]]

    def persist(self) -> None:
        pass

    def destroy(self) -> None:
        self.indexed = {}


def _make_orchestration(tmp_path: Path) -> tuple[Orchestration, SQLiteStorage, TrackingDense, TrackingSparse]:
    storage = SQLiteStorage(database_path=tmp_path / "storage.db")
    dense = TrackingDense()
    sparse = TrackingSparse()
    search_config = SearchConfig(
        hybrid=HybridConfig(alpha=0.5),
        dense=DenseSearchConfig(),
        sparse=SparseSearchConfig(),
        reranking=RerankingConfig(
            enabled=False,
            model_name="cross-encoder/ms-marco-MiniLM-L12-v2",
            candidate_multiplier=3,
        ),
    )
    orchestration = Orchestration(
        chunker=partial(chunk_text, chunk_size=4, overlap=0.5),
        embeddings=cast(Embeddings, FakeEmbeddings()),
        storage=cast(Storage, storage),
        dense=cast(DenseRetrieval, dense),
        sparse=cast(SparseRetrieval, sparse),
        search_config=search_config,
        reranker=None,
    )
    return orchestration, storage, dense, sparse


def test_reindexing_same_citation_replaces_document_without_duplicate_counts(tmp_path: Path) -> None:
    orchestration, storage, _dense, _sparse = _make_orchestration(tmp_path)
    citation: dict[str, object] = {"citation_key": "same-key", "source_type": "text_file", "common": {}, "source_data": {}}

    _first_document_id, first_chunk_ids = orchestration.index_document("one two three four five six", citation, "docs/a.txt")
    second_document_id, second_chunk_ids = orchestration.index_document("one two three four five six", citation, "docs/a.txt")

    assert storage.corpus_stats() == (1, len(first_chunk_ids))
    assert len(second_chunk_ids) == len(first_chunk_ids)
    assert storage.get_document_id("same-key") == second_document_id


def test_reindexing_same_citation_removes_old_chunk_ids_from_indices(tmp_path: Path) -> None:
    orchestration, _storage, dense, sparse = _make_orchestration(tmp_path)
    citation: dict[str, object] = {"citation_key": "same-key", "source_type": "text_file", "common": {}, "source_data": {}}

    _first_document_id, first_chunk_ids = orchestration.index_document("one two three four five six", citation, "docs/a.txt")
    _second_document_id, second_chunk_ids = orchestration.index_document("one two three four five six", citation, "docs/a.txt")

    assert set(first_chunk_ids).isdisjoint(second_chunk_ids)
    assert dense.removed == [first_chunk_ids]
    assert sparse.removed == [first_chunk_ids]
    assert set(dense.indexed) == set(second_chunk_ids)
    assert set(sparse.indexed) == set(second_chunk_ids)


def test_reindexing_same_citation_evicts_superseded_document_from_cache(tmp_path: Path) -> None:
    orchestration, _storage, _dense, _sparse = _make_orchestration(tmp_path)
    citation: dict[str, object] = {"citation_key": "same-key", "source_type": "text_file", "common": {}, "source_data": {}}

    first_document_id, first_chunk_ids = orchestration.index_document("one two three four five six", citation, "docs/a.txt")
    orchestration.get_chunk(first_chunk_ids[0])

    assert first_document_id in orchestration._citation_key_cache

    orchestration.index_document("one two three four five six", citation, "docs/a.txt")

    assert first_document_id not in orchestration._citation_key_cache

"""Unit tests for orchestration coordination logic."""

import json
import re
from functools import partial
from typing import Any, Final, cast

import pytest

from minirag.config import (
    DenseSearchConfig,
    HybridConfig,
    RerankingConfig,
    SearchConfig,
    SparseSearchConfig,
)
from minirag.ingestion.chunker import chunk_text
from minirag.orchestration import Orchestration
from minirag.retrieval.dense_interface import DenseRetrieval
from minirag.retrieval.sparse_interface import SparseRetrieval
from minirag.search.embeddings_interface import Embeddings
from minirag.search.types import ScoredChunk, SearchResult
from minirag.storage.interface import ChunkRecord, ChunkWithDocument, CorpusStats, Storage


class FakeEmbeddings:
    """Fake embeddings provider."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]


class FakeStorage:
    """Fake storage backend."""

    def __init__(self) -> None:
        self.documents: dict[int, str] = {}
        self.source_paths: dict[int, str] = {}
        self.chunks: dict[int, tuple[int, str, int, int, int, int, int]] = {}
        self.citations: dict[str, tuple[int, str]] = {}
        self._citation_by_doc: dict[int, str] = {}
        self._next_document_id = 1
        self._next_chunk_id = 1

    def insert_document(self, content: str, source_path: str) -> int:
        document_id = self._next_document_id
        self._next_document_id = self._next_document_id + 1
        self.documents[document_id] = content
        self.source_paths[document_id] = source_path
        return document_id

    def insert_document_with_citation(self, content: str, citation: dict[str, object] | None, source_path: str) -> int:
        document_id = self.insert_document(content, source_path)
        if citation is None:
            citation_key = str(document_id)
            auto_citation = {
                "citation_key": citation_key,
                "source_type": "text_file",
                "common": {"title": str(document_id)},
                "source_data": {},
            }
            citation_json = json.dumps(auto_citation)
        else:
            citation_key_value = citation.get("citation_key")
            if not isinstance(citation_key_value, str):
                raise ValueError("citation_key must be a string")
            citation_key = citation_key_value
            citation_json = json.dumps(citation)
        self.insert_citation(citation_key=citation_key, document_id=document_id, citation_json=citation_json)
        return document_id

    def insert_chunk(
        self,
        document_id: int,
        content: str,
        chunk_index: int,
        char_start: int,
        char_end: int,
        line_from: int,
        line_to: int,
    ) -> int:
        chunk_id = self._next_chunk_id
        self._next_chunk_id = self._next_chunk_id + 1
        self.chunks[chunk_id] = (document_id, content, chunk_index, char_start, char_end, line_from, line_to)
        return chunk_id

    def insert_citation(self, citation_key: str, document_id: int, citation_json: str) -> None:
        self.citations[citation_key] = (document_id, citation_json)
        self._citation_by_doc[document_id] = citation_key

    def get_document(self, document_id: int) -> str:
        return self.documents[document_id]

    def get_chunk(self, chunk_id: int) -> ChunkWithDocument:
        entry = self.chunks.get(chunk_id)
        if entry is None:
            raise ValueError(f"chunk not found: {chunk_id}")
        document_id, content, chunk_index, char_start, char_end, line_from, line_to = entry
        return ChunkWithDocument(
            document_id=document_id,
            content=content,
            source_path=self.source_paths[document_id],
            chunk_index=chunk_index,
            char_start=char_start,
            char_end=char_end,
            line_from=line_from,
            line_to=line_to,
        )

    def get_citation_key(self, document_id: int) -> str | None:
        return self._citation_by_doc.get(document_id)

    def get_citation(self, citation_key: str) -> str | None:
        entry = self.citations.get(citation_key)
        if entry is None:
            return None
        return entry[1]

    def list_chunks(self, document_id: int) -> list[ChunkRecord]:
        return [ChunkRecord(chunk_id=chunk_id, content=entry[1]) for chunk_id, entry in self.chunks.items() if entry[0] == document_id]

    def corpus_stats(self) -> CorpusStats:
        return CorpusStats(document_count=len(self.documents), chunk_count=len(self.chunks))

    def close(self) -> None:
        pass

    def destroy(self) -> None:
        self.documents = {}
        self.source_paths = {}
        self.chunks = {}
        self.citations = {}
        self._citation_by_doc = {}


class FakeDense:
    """Fake dense retrieval backend."""

    def __init__(self) -> None:
        self.indexed: dict[int, list[float]] = {}

    def index(self, chunk_id: int, embedding: list[float]) -> None:
        self.indexed[chunk_id] = embedding

    def persist(self) -> None:
        pass

    def search(self, query_embedding: list[float], top_k: int) -> list[ScoredChunk]:
        del query_embedding
        sorted_ids = sorted(self.indexed.keys())
        return [ScoredChunk(chunk_id=chunk_id, score=1.0 - 0.1 * idx) for idx, chunk_id in enumerate(sorted_ids[:top_k])]

    def destroy(self) -> None:
        self.indexed = {}


class FakeSparse:
    """Fake sparse retrieval backend."""

    def __init__(self) -> None:
        self.indexed: dict[int, str] = {}

    def index(self, chunk_id: int, content: str) -> None:
        self.indexed[chunk_id] = content

    def persist(self) -> None:
        pass

    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        del query
        sorted_ids = sorted(self.indexed.keys(), reverse=True)
        return [ScoredChunk(chunk_id=chunk_id, score=1.0 - 0.1 * idx) for idx, chunk_id in enumerate(sorted_ids[:top_k])]

    def destroy(self) -> None:
        self.indexed = {}


def make_orchestration_with_backends() -> tuple[Orchestration, FakeStorage, FakeDense, FakeSparse]:
    """Create orchestration with fake dependencies, returning the fakes for assertions."""
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

    storage = FakeStorage()
    dense = FakeDense()
    sparse = FakeSparse()
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


def make_orchestration() -> Orchestration:
    """Create orchestration with fake dependencies."""
    return make_orchestration_with_backends()[0]


def test_orchestration_index_and_search() -> None:
    """Orchestration should index and execute all search modes."""
    orchestration = make_orchestration()
    text: Final[str] = "one two three four five six"

    document_id, chunk_ids = orchestration.index_document(text, citation=None, source_path="docs/sample.txt")

    assert document_id == 1
    assert len(chunk_ids) >= 2

    dense_results = orchestration.search_dense(query="one", top_k=5)
    sparse_results = orchestration.search_sparse(query="one", top_k=5)
    hybrid_results = orchestration.search_hybrid(query="one", top_k=5, alpha=None, use_reranking=None)

    assert len(dense_results) >= 1
    assert len(sparse_results) >= 1
    assert len(hybrid_results) >= 1
    assert isinstance(hybrid_results[0], SearchResult)
    assert hybrid_results[0].document_id == 1
    assert hybrid_results[0].citation_key == "1"


def test_orchestration_rejects_whitespace_document() -> None:
    """index_document rejects a whitespace-only document before any embedding."""
    orchestration = make_orchestration()

    with pytest.raises(ValueError, match="document text must not be empty"):
        orchestration.index_document("   ", citation=None, source_path="docs/sample.txt")


def test_orchestration_rejects_zero_width_space_document() -> None:
    """A blank video transcript (only zero-width spaces) is rejected before any storage write.

    Regression for indexed video document_id=25639, whose content was 233 zero-width spaces.
    `str.strip()` does not treat U+200B as whitespace, so the old empty-check let it through;
    fastText then returned a zero-norm vector and 500'd the whole ingest call.
    """
    orchestration, storage, _dense, _sparse = make_orchestration_with_backends()
    zero_width_transcript = "​​ ​​\n" * 40

    with pytest.raises(ValueError, match="document text must not be empty"):
        orchestration.index_document(zero_width_transcript, citation=None, source_path="videos/blank.txt")

    assert storage.documents == {}
    assert storage.chunks == {}


def test_orchestration_skips_chunk_without_word_characters() -> None:
    """A chunk of only zero-width spaces is skipped, not fatal, when the document has real content."""
    orchestration, storage, dense, _sparse = make_orchestration_with_backends()
    # With chunk_size=4/overlap=0.5 the trailing "​​ ​​" forms its own
    # word-less chunk that must be skipped rather than aborting the document.
    text = "one two three four ​​ ​​"

    document_id, chunk_ids = orchestration.index_document(text, citation=None, source_path="videos/mixed.txt")

    assert document_id == 1
    assert len(chunk_ids) >= 1
    # Every indexed chunk has embeddable content, and the skipped chunk was never indexed.
    for chunk_id in chunk_ids:
        content = storage.chunks[chunk_id][1]
        assert re.search(r"\w", content) is not None
    assert set(dense.indexed.keys()) == set(chunk_ids)


def test_orchestration_index_with_citation() -> None:
    """Orchestration should store provided citation."""
    orchestration = make_orchestration()
    citation: dict[str, object] = {"citation_key": "smith2026", "source_type": "journal", "common": {}, "source_data": {}}
    document_id, _chunk_ids = orchestration.index_document("one two three four five six", citation=citation, source_path="docs/sample.txt")

    results = orchestration.search_dense(query="one", top_k=5)
    assert len(results) >= 1
    assert results[0].citation_key == "smith2026"
    assert results[0].document_id == document_id


def test_orchestration_index_auto_generates_citation() -> None:
    """Orchestration should auto-generate citation when none provided."""
    orchestration = make_orchestration()
    document_id, _chunk_ids = orchestration.index_document("one two three four five six", citation=None, source_path="docs/sample.txt")

    results = orchestration.search_dense(query="one", top_k=5)
    assert len(results) >= 1
    assert results[0].citation_key == str(document_id)


def test_orchestration_get_citation_returns_stored_data() -> None:
    """get_citation should return parsed citation data after indexing."""
    orchestration = make_orchestration()
    citation: dict[str, object] = {
        "citation_key": "martinez2026",
        "source_type": "research_story",
        "common": {"title": "The Quantum Discovery", "author": "Dr. Elena Martinez"},
        "source_data": {"topic": "quantum_computing", "institution": "Stanford University"},
    }
    orchestration.index_document("one two three four five six", citation=citation, source_path="docs/sample.txt")

    result = orchestration.get_citation("martinez2026")
    assert result is not None
    assert result["citation_key"] == "martinez2026"
    assert result["source_type"] == "research_story"
    common = cast(dict[str, Any], result["common"])
    assert common["title"] == "The Quantum Discovery"
    assert common["author"] == "Dr. Elena Martinez"
    source_data = cast(dict[str, Any], result["source_data"])
    assert source_data["topic"] == "quantum_computing"
    assert source_data["institution"] == "Stanford University"


def test_orchestration_get_citation_returns_none_when_not_found() -> None:
    """get_citation should return None for an unknown citation_key."""
    orchestration = make_orchestration()
    assert orchestration.get_citation("nonexistent") is None


def test_orchestration_get_citation_returns_none_after_destroy() -> None:
    """get_citation should return None after destroy_index clears all data."""
    orchestration = make_orchestration()
    citation: dict[str, object] = {"citation_key": "key1", "source_type": "journal", "common": {}, "source_data": {}}
    orchestration.index_document("one two three four five six", citation=citation, source_path="docs/sample.txt")
    assert orchestration.get_citation("key1") is not None

    orchestration.destroy_index()
    assert orchestration.get_citation("key1") is None


def test_orchestration_get_citation_auto_generated() -> None:
    """get_citation should return auto-generated citation when none was provided."""
    orchestration = make_orchestration()
    document_id, _chunk_ids = orchestration.index_document("one two three four five six", citation=None, source_path="docs/sample.txt")

    result = orchestration.get_citation(str(document_id))
    assert result is not None
    assert result["citation_key"] == str(document_id)
    assert result["source_type"] == "text_file"
    common = cast(dict[str, Any], result["common"])
    assert common["title"] == str(document_id)
    assert result["source_data"] == {}


class FailOnSecondChunkStorage(FakeStorage):
    """Fake storage that raises on the second insert_chunk call."""

    def __init__(self) -> None:
        super().__init__()
        self._chunk_insert_count = 0

    def insert_chunk(
        self,
        document_id: int,
        content: str,
        chunk_index: int,
        char_start: int,
        char_end: int,
        line_from: int,
        line_to: int,
    ) -> int:
        self._chunk_insert_count += 1
        if self._chunk_insert_count == 2:
            raise RuntimeError("simulated storage failure on chunk 2")
        return super().insert_chunk(
            document_id=document_id,
            content=content,
            chunk_index=chunk_index,
            char_start=char_start,
            char_end=char_end,
            line_from=line_from,
            line_to=line_to,
        )


class StaleChunkStorage(FakeStorage):
    """Fake storage that raises ValueError for a specific chunk_id on get_chunk."""

    def __init__(self, stale_chunk_id: int) -> None:
        super().__init__()
        self._stale_chunk_id = stale_chunk_id

    def get_chunk(self, chunk_id: int) -> ChunkWithDocument:
        if chunk_id == self._stale_chunk_id:
            raise ValueError(f"chunk not found: {chunk_id}")
        return super().get_chunk(chunk_id)


def test_orchestration_partial_chunk_failure() -> None:
    """Partial chunk indexing failure should raise RuntimeError with first chunk stored."""
    storage = FailOnSecondChunkStorage()
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
        dense=cast(DenseRetrieval, FakeDense()),
        sparse=cast(SparseRetrieval, FakeSparse()),
        search_config=search_config,
        reranker=None,
    )

    with pytest.raises(RuntimeError, match="failed to index chunk"):
        orchestration.index_document("one two three four five six seven eight", citation=None, source_path="docs/sample.txt")

    assert len(storage.chunks) == 1


def test_orchestration_raises_on_stale_chunks() -> None:
    """Search should fail fast when chunks are missing from storage."""
    storage = StaleChunkStorage(stale_chunk_id=2)
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
        dense=cast(DenseRetrieval, FakeDense()),
        sparse=cast(SparseRetrieval, FakeSparse()),
        search_config=search_config,
        reranker=None,
    )

    orchestration.index_document("one two three four five six seven eight", citation=None, source_path="docs/sample.txt")

    with pytest.raises(RuntimeError, match="missing chunk_id"):
        orchestration.search_dense(query="one", top_k=10)


def test_orchestration_destroy_and_validation() -> None:
    """Destroy should clear backends and invalid inputs should fail."""
    orchestration = make_orchestration()
    orchestration.index_document("one two three four five", citation=None, source_path="docs/sample.txt")
    orchestration.destroy_index()

    assert orchestration.search_dense(query="q", top_k=3) == []

    with pytest.raises(ValueError):
        orchestration.index_document("  ", citation=None, source_path="docs/sample.txt")

    with pytest.raises(ValueError):
        orchestration.search_sparse(query="", top_k=1)

    with pytest.raises(ValueError):
        orchestration.search_hybrid(query="q", top_k=0, alpha=None, use_reranking=None)


def test_orchestration_index_rejects_empty_citation_key() -> None:
    """index_document should reject citation with empty citation_key."""
    orchestration = make_orchestration()
    citation: dict[str, object] = {
        "citation_key": "",
        "source_type": "journal",
        "common": {},
        "source_data": {},
    }
    with pytest.raises(ValueError, match="non-empty 'citation_key'"):
        orchestration.index_document("one two three four five six", citation=citation, source_path="docs/sample.txt")


def test_orchestration_index_rejects_missing_citation_key() -> None:
    """index_document should reject citation without citation_key."""
    orchestration = make_orchestration()
    citation: dict[str, object] = {"source_type": "journal", "common": {}, "source_data": {}}
    with pytest.raises(ValueError, match="non-empty 'citation_key'"):
        orchestration.index_document("one two three four five six", citation=citation, source_path="docs/sample.txt")


def test_orchestration_index_rejects_empty_source_type() -> None:
    """index_document should reject citation with empty source_type."""
    orchestration = make_orchestration()
    citation: dict[str, object] = {
        "citation_key": "k",
        "source_type": "",
        "common": {},
        "source_data": {},
    }
    with pytest.raises(ValueError, match="non-empty 'source_type'"):
        orchestration.index_document("one two three four five six", citation=citation, source_path="docs/sample.txt")


def test_orchestration_index_rejects_missing_source_type() -> None:
    """index_document should reject citation without source_type."""
    orchestration = make_orchestration()
    citation: dict[str, object] = {"citation_key": "k", "common": {}, "source_data": {}}
    with pytest.raises(ValueError, match="non-empty 'source_type'"):
        orchestration.index_document("one two three four five six", citation=citation, source_path="docs/sample.txt")


class CorruptCitationStorage(FakeStorage):
    """Fake storage that returns corrupt JSON from get_citation."""

    def get_citation(self, citation_key: str) -> str | None:
        if citation_key == "corrupt":
            return "{not valid json"
        return super().get_citation(citation_key)


def test_orchestration_get_citation_corrupt_json_raises() -> None:
    """get_citation should raise ValueError for corrupt stored JSON."""
    storage = CorruptCitationStorage()
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
        dense=cast(DenseRetrieval, FakeDense()),
        sparse=cast(SparseRetrieval, FakeSparse()),
        search_config=search_config,
        reranker=None,
    )

    with pytest.raises(ValueError, match="corrupt citation data for key: corrupt"):
        orchestration.get_citation("corrupt")


def test_orchestration_citation_cache_cleared_on_destroy() -> None:
    """After destroy and re-index, search should return the new citation key, not cached old one."""
    orchestration = make_orchestration()

    citation1: dict[str, object] = {"citation_key": "old_key", "source_type": "journal", "common": {}, "source_data": {}}
    orchestration.index_document("one two three four five six", citation=citation1, source_path="docs/sample.txt")
    results1 = orchestration.search_dense(query="one", top_k=5)
    assert results1[0].citation_key == "old_key"

    orchestration.destroy_index()

    citation2: dict[str, object] = {"citation_key": "new_key", "source_type": "blog", "common": {}, "source_data": {}}
    orchestration.index_document("one two three four five six", citation=citation2, source_path="docs/sample.txt")
    results2 = orchestration.search_dense(query="one", top_k=5)
    assert results2[0].citation_key == "new_key"


class MissingCitationStorage(FakeStorage):
    """Fake storage that returns None for get_citation_key."""

    def get_citation_key(self, document_id: int) -> str | None:
        return None


def test_orchestration_raises_on_missing_citation_record() -> None:
    """Search should fail fast when a citation record is missing."""
    storage = MissingCitationStorage()
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
        dense=cast(DenseRetrieval, FakeDense()),
        sparse=cast(SparseRetrieval, FakeSparse()),
        search_config=search_config,
        reranker=None,
    )

    citation: dict[str, object] = {"citation_key": "key1", "source_type": "journal", "common": {}, "source_data": {}}
    orchestration.index_document("one two three four five six", citation=citation, source_path="docs/sample.txt")

    with pytest.raises(RuntimeError, match="missing citation"):
        orchestration.search_dense(query="one", top_k=10)


def test_orchestration_stores_chunk_provenance() -> None:
    """index_document persists ordinal, char span, and line range for every chunk."""
    storage = FakeStorage()
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
        dense=cast(DenseRetrieval, FakeDense()),
        sparse=cast(SparseRetrieval, FakeSparse()),
        search_config=search_config,
        reranker=None,
    )
    text = "one two three\nfour five six\nseven eight"

    document_id, chunk_ids = orchestration.index_document(text, citation=None, source_path="docs/sample.txt")

    assert storage.source_paths[document_id] == "docs/sample.txt"
    assert storage.chunks[chunk_ids[0]] == (document_id, "one two three four", 0, 0, 18, 1, 2)
    assert [storage.chunks[chunk_id][2] for chunk_id in chunk_ids] == list(range(len(chunk_ids)))
    for chunk_id in chunk_ids:
        _, content, _, char_start, char_end, line_from, line_to = storage.chunks[chunk_id]
        assert text[char_start:char_end].split() == content.split()
        assert 1 <= line_from <= line_to
    assert storage.chunks[chunk_ids[-1]][6] == 3


def test_orchestration_search_results_carry_provenance() -> None:
    """Search results expose source path, chunk ordinal, char span, and line range."""
    orchestration = make_orchestration()
    text = "one two three\nfour five six\nseven eight"
    orchestration.index_document(text, citation=None, source_path="docs/sample.txt")

    results = orchestration.search_dense(query="one", top_k=5)

    assert len(results) >= 1
    first = results[0]
    assert first.source_path == "docs/sample.txt"
    assert first.char_end > first.char_start >= 0
    assert first.line_to >= first.line_from >= 1
    assert first.chunk_index >= 0
    assert text[first.char_start : first.char_end].split() == first.text.split()


def test_orchestration_get_chunk_returns_provenance_and_citation_key() -> None:
    """get_chunk returns the stored chunk record plus the document citation key."""
    orchestration = make_orchestration()
    text = "one two three\nfour five six\nseven eight"
    document_id, chunk_ids = orchestration.index_document(text, citation=None, source_path="docs/sample.txt")

    chunk_record, citation_key = orchestration.get_chunk(chunk_ids[0])

    assert citation_key == str(document_id)
    assert chunk_record.document_id == document_id
    assert chunk_record.source_path == "docs/sample.txt"
    assert chunk_record.content == "one two three four"
    assert (chunk_record.char_start, chunk_record.char_end) == (0, 18)
    assert (chunk_record.line_from, chunk_record.line_to) == (1, 2)


def test_orchestration_get_chunk_missing_raises() -> None:
    """get_chunk propagates ValueError for an unknown chunk_id."""
    orchestration = make_orchestration()
    with pytest.raises(ValueError, match="chunk not found"):
        orchestration.get_chunk(999)


def test_orchestration_index_rejects_empty_source_path() -> None:
    """index_document rejects a whitespace-only source_path before any storage write."""
    orchestration = make_orchestration()
    with pytest.raises(ValueError, match="source_path must not be empty"):
        orchestration.index_document("one two three", citation=None, source_path="   ")

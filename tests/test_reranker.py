"""Unit tests for reranking components and orchestration integration."""

import importlib
import math
from functools import partial
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from minirag.config import (
    DenseSearchConfig,
    HybridConfig,
    RerankingConfig,
    SearchConfig,
    SparseSearchConfig,
)
from minirag.ingestion.chunker import chunk_text
from minirag.orchestration import Orchestration
from minirag.reranking.cross_encoder import CrossEncoderReranker
from minirag.retrieval.dense_interface import DenseRetrieval
from minirag.retrieval.sparse_interface import SparseRetrieval
from minirag.search.embeddings_interface import Embeddings
from minirag.search.types import ScoredChunk, SearchResult
from minirag.storage.interface import ChunkRecord, ChunkWithDocument, CorpusStats, Storage


class FakeCrossEncoderModel:
    """Fake cross-encoder that returns deterministic scores."""

    def __init__(self, scores: list[float]) -> None:
        self._scores = scores
        self.calls: list[list[list[str]]] = []

    def predict(self, sentences: list[list[str]]) -> object:
        self.calls.append(sentences)
        return self._scores[: len(sentences)]


class FakeCrossEncoderModule:
    """Fake sentence_transformers module."""

    def __init__(self, model: FakeCrossEncoderModel) -> None:
        self._model = model
        self.calls: list[tuple[str, dict[str, str]]] = []

    def CrossEncoder(self, model_name: str, model_kwargs: dict[str, str]) -> FakeCrossEncoderModel:
        self.calls.append((model_name, model_kwargs))
        return self._model


class FakeCrossEncoderModuleNoCacheKwargs:
    """Fake sentence_transformers module whose constructor accepts no cache kwargs."""

    def __init__(self, model: FakeCrossEncoderModel) -> None:
        self._model = model
        self.calls: list[str] = []

    def CrossEncoder(self, model_name: str) -> FakeCrossEncoderModel:
        self.calls.append(model_name)
        return self._model


def _make_cross_encoder_reranker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scores: list[float]
) -> tuple[CrossEncoderReranker, FakeCrossEncoderModel, FakeCrossEncoderModule]:
    fake_model = FakeCrossEncoderModel(scores=scores)
    fake_module = FakeCrossEncoderModule(model=fake_model)

    def fake_import_module(name: str) -> object:
        if name == "sentence_transformers":
            return fake_module
        raise RuntimeError(f"unexpected module import: {name}")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    reranker = CrossEncoderReranker(
        model_name="cross-encoder/ms-marco-MiniLM-L12-v2",
        model_cache_dir=tmp_path / "models",
        candidate_multiplier=3,
    )
    return reranker, fake_model, fake_module


def test_reranker_logs_warning_when_cache_kwargs_are_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake_model = FakeCrossEncoderModel(scores=[0.1])
    fake_module = FakeCrossEncoderModuleNoCacheKwargs(model=fake_model)

    def fake_import_module(name: str) -> object:
        if name == "sentence_transformers":
            return fake_module
        raise RuntimeError(f"unexpected module import: {name}")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with caplog.at_level("WARNING"):
        CrossEncoderReranker(
            model_name="cross-encoder/ms-marco-MiniLM-L12-v2",
            model_cache_dir=tmp_path / "models",
            candidate_multiplier=2,
        )

    assert fake_module.calls == ["cross-encoder/ms-marco-MiniLM-L12-v2"]
    assert "loading without explicit cache directory" in caplog.text


def test_reranker_reranks_and_normalizes_scores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reranker, _, fake_module = _make_cross_encoder_reranker(monkeypatch=monkeypatch, tmp_path=tmp_path, scores=[0.0, 2.0, -2.0])
    results = [
        SearchResult(chunk_id=1, document_id=1, citation_key="k", text="alpha", score=0.4),
        SearchResult(chunk_id=2, document_id=1, citation_key="k", text="beta", score=0.4),
        SearchResult(chunk_id=3, document_id=1, citation_key="k", text="gamma", score=0.4),
    ]

    reranked = reranker.rerank(query="query", results=results, top_k=2)

    assert fake_module.calls[0][0] == "cross-encoder/ms-marco-MiniLM-L12-v2"
    assert len(reranked) == 2
    assert [result.chunk_id for result in reranked] == [2, 1]
    assert abs(reranked[0].score - (1.0 / (1.0 + math.exp(-2.0)))) < 1e-9
    assert abs(reranked[1].score - 0.5) < 1e-9
    assert all(0.0 <= result.score <= 1.0 for result in reranked)


def test_reranker_empty_results_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reranker, fake_model, _ = _make_cross_encoder_reranker(monkeypatch=monkeypatch, tmp_path=tmp_path, scores=[0.1])
    assert reranker.rerank(query="query", results=[], top_k=5) == []
    assert fake_model.calls == []


def test_reranker_rejects_empty_query(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reranker, _, _ = _make_cross_encoder_reranker(monkeypatch=monkeypatch, tmp_path=tmp_path, scores=[0.1])
    with pytest.raises(ValueError, match="query must not be empty"):
        reranker.rerank(query="   ", results=[SearchResult(chunk_id=1, document_id=1, citation_key="k", text="a", score=0.1)], top_k=1)


def test_reranker_rejects_invalid_top_k(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reranker, _, _ = _make_cross_encoder_reranker(monkeypatch=monkeypatch, tmp_path=tmp_path, scores=[0.1])
    with pytest.raises(ValueError, match="top_k must be greater than 0"):
        reranker.rerank(query="query", results=[SearchResult(chunk_id=1, document_id=1, citation_key="k", text="a", score=0.1)], top_k=0)


def test_reranker_rejects_empty_model_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="model_name must not be empty"):
        CrossEncoderReranker(
            model_name="   ",
            model_cache_dir=tmp_path / "models",
            candidate_multiplier=3,
        )


def test_reranker_rejects_invalid_candidate_multiplier(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="candidate_multiplier must be greater than 0"):
        CrossEncoderReranker(
            model_name="cross-encoder/ms-marco-MiniLM-L12-v2",
            model_cache_dir=tmp_path / "models",
            candidate_multiplier=0,
        )


def test_reranker_batch_scoring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reranker, fake_model, _ = _make_cross_encoder_reranker(monkeypatch=monkeypatch, tmp_path=tmp_path, scores=[0.1, 0.2, 0.3])
    results = [
        SearchResult(chunk_id=1, document_id=1, citation_key="k", text="one", score=0.4),
        SearchResult(chunk_id=2, document_id=1, citation_key="k", text="two", score=0.3),
        SearchResult(chunk_id=3, document_id=1, citation_key="k", text="three", score=0.2),
    ]

    reranker.rerank(query="query", results=results, top_k=3)

    assert len(fake_model.calls) == 1
    assert fake_model.calls[0] == [["query", "one"], ["query", "two"], ["query", "three"]]


def test_reranking_config_validation() -> None:
    config = RerankingConfig(
        enabled=True,
        model_name="cross-encoder/ms-marco-MiniLM-L12-v2",
        candidate_multiplier=3,
    )
    assert config.enabled is True
    assert config.candidate_multiplier == 3

    with pytest.raises(ValidationError, match="search.reranking.model_name must not be empty"):
        RerankingConfig(
            enabled=True,
            model_name=" ",
            candidate_multiplier=3,
        )

    with pytest.raises(ValidationError, match="search.reranking.candidate_multiplier must be greater than 0"):
        RerankingConfig(
            enabled=True,
            model_name="cross-encoder/ms-marco-MiniLM-L12-v2",
            candidate_multiplier=0,
        )


class FakeEmbeddings:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeStorage:
    def insert_document_with_citation(self, content: str, citation: dict[str, object] | None) -> int:
        del content, citation
        return 1

    def insert_document(self, content: str) -> int:
        del content
        return 1

    def insert_chunk(self, document_id: int, content: str) -> int:
        del document_id, content
        return 1

    def insert_citation(self, citation_key: str, document_id: int, citation_json: str) -> None:
        del citation_key, document_id, citation_json

    def get_document(self, document_id: int) -> str:
        return f"doc {document_id}"

    def get_chunk(self, chunk_id: int) -> ChunkWithDocument:
        return ChunkWithDocument(document_id=chunk_id, content=f"text {chunk_id}")

    def get_citation_key(self, document_id: int) -> str | None:
        return str(document_id)

    def get_citation(self, citation_key: str) -> str | None:
        del citation_key
        return None

    def list_chunks(self, document_id: int) -> list[ChunkRecord]:
        del document_id
        return []

    def corpus_stats(self) -> CorpusStats:
        return CorpusStats(document_count=0, chunk_count=0)

    def close(self) -> None:
        return None

    def destroy(self) -> None:
        return None


class FakeDense:
    def __init__(self, chunk_ids: list[int]) -> None:
        self._chunk_ids = chunk_ids
        self.last_top_k = 0

    def index(self, chunk_id: int, embedding: list[float]) -> None:
        del chunk_id, embedding
        return None

    def persist(self) -> None:
        return None

    def search(self, query_embedding: list[float], top_k: int) -> list[ScoredChunk]:
        del query_embedding
        self.last_top_k = top_k
        return [ScoredChunk(chunk_id=chunk_id, score=1.0 - 0.01 * idx) for idx, chunk_id in enumerate(self._chunk_ids[:top_k])]

    def destroy(self) -> None:
        return None


class FakeSparse:
    def __init__(self, chunk_ids: list[int]) -> None:
        self._chunk_ids = chunk_ids
        self.last_top_k = 0

    def index(self, chunk_id: int, content: str) -> None:
        del chunk_id, content
        return None

    def persist(self) -> None:
        return None

    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        del query
        self.last_top_k = top_k
        return [ScoredChunk(chunk_id=chunk_id, score=1.0 - 0.01 * idx) for idx, chunk_id in enumerate(self._chunk_ids[:top_k])]

    def destroy(self) -> None:
        return None


class FakeReranker:
    def __init__(self, candidate_multiplier: int) -> None:
        self._candidate_multiplier = candidate_multiplier
        self.last_query = ""
        self.last_results: list[SearchResult] = []
        self.last_top_k = 0
        self.last_candidate_count_top_k = 0

    def candidate_count(self, top_k: int) -> int:
        self.last_candidate_count_top_k = top_k
        return top_k * self._candidate_multiplier

    def rerank(self, query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]:
        self.last_query = query
        self.last_results = results
        self.last_top_k = top_k

        reranked = [
            SearchResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                citation_key=result.citation_key,
                text=result.text,
                score=1.0 - 0.01 * idx,
            )
            for idx, result in enumerate(results)
        ]
        return reranked[:top_k]


def _make_search_config(enabled: bool, candidate_multiplier: int) -> SearchConfig:
    return SearchConfig(
        hybrid=HybridConfig(alpha=0.5),
        dense=DenseSearchConfig(),
        sparse=SparseSearchConfig(),
        reranking=RerankingConfig(
            enabled=enabled,
            model_name="cross-encoder/ms-marco-MiniLM-L12-v2",
            candidate_multiplier=candidate_multiplier,
        ),
    )


def test_orchestration_hybrid_with_reranker() -> None:
    dense = FakeDense(chunk_ids=[1, 2, 3, 4, 5, 6, 7, 8])
    sparse = FakeSparse(chunk_ids=[101, 102, 103, 104, 105, 106, 107, 108])
    reranker = FakeReranker(candidate_multiplier=3)
    orchestration = Orchestration(
        chunker=partial(chunk_text, chunk_size=4, overlap=0.5),
        embeddings=cast(Embeddings, FakeEmbeddings()),
        storage=cast(Storage, FakeStorage()),
        dense=cast(DenseRetrieval, dense),
        sparse=cast(SparseRetrieval, sparse),
        search_config=_make_search_config(enabled=True, candidate_multiplier=3),
        reranker=reranker,
    )

    candidate_counts: list[int] = []

    results, trace = orchestration.search_hybrid_with_trace(
        query="query",
        top_k=2,
        alpha=None,
        use_reranking=None,
        reranking_candidate_callback=candidate_counts.append,
    )

    assert dense.last_top_k == 6
    assert sparse.last_top_k == 6
    assert reranker.last_candidate_count_top_k == 2
    assert reranker.last_query == "query"
    assert reranker.last_top_k == 2
    assert len(reranker.last_results) == 6
    assert len(results) == 2
    assert candidate_counts == [6]
    assert trace.reranking_active is True
    assert trace.retrieval_top_k == 6
    assert trace.dense_count == 6
    assert trace.sparse_count == 6
    assert trace.merged_candidate_count == 6
    assert trace.final_result_count == 2

    result_only = orchestration.search_hybrid(query="query", top_k=2, alpha=None, use_reranking=None)
    assert len(result_only) == 2


def test_orchestration_hybrid_without_reranker() -> None:
    dense = FakeDense(chunk_ids=[1, 2, 3, 4, 5])
    sparse = FakeSparse(chunk_ids=[101, 102, 103, 104, 105])
    orchestration = Orchestration(
        chunker=partial(chunk_text, chunk_size=4, overlap=0.5),
        embeddings=cast(Embeddings, FakeEmbeddings()),
        storage=cast(Storage, FakeStorage()),
        dense=cast(DenseRetrieval, dense),
        sparse=cast(SparseRetrieval, sparse),
        search_config=_make_search_config(enabled=False, candidate_multiplier=3),
        reranker=None,
    )

    candidate_counts: list[int] = []

    results, trace = orchestration.search_hybrid_with_trace(
        query="query",
        top_k=2,
        alpha=None,
        use_reranking=None,
        reranking_candidate_callback=candidate_counts.append,
    )

    assert dense.last_top_k == 2
    assert sparse.last_top_k == 2
    assert len(results) == 2
    assert candidate_counts == []
    assert trace.reranking_active is False
    assert trace.retrieval_top_k == 2
    assert trace.dense_count == 2
    assert trace.sparse_count == 2
    assert trace.merged_candidate_count == 2
    assert trace.final_result_count == 2


def test_orchestration_hybrid_trace_uses_actual_underpopulated_candidate_count() -> None:
    """Trace candidate counts should reflect returned candidates, not requested counts."""
    dense = FakeDense(chunk_ids=[1, 2])
    sparse = FakeSparse(chunk_ids=[2, 3])
    reranker = FakeReranker(candidate_multiplier=4)
    orchestration = Orchestration(
        chunker=partial(chunk_text, chunk_size=4, overlap=0.5),
        embeddings=cast(Embeddings, FakeEmbeddings()),
        storage=cast(Storage, FakeStorage()),
        dense=cast(DenseRetrieval, dense),
        sparse=cast(SparseRetrieval, sparse),
        search_config=_make_search_config(enabled=True, candidate_multiplier=4),
        reranker=reranker,
    )
    candidate_counts: list[int] = []

    results, trace = orchestration.search_hybrid_with_trace(
        query="query",
        top_k=5,
        alpha=None,
        use_reranking=True,
        reranking_candidate_callback=candidate_counts.append,
    )

    assert dense.last_top_k == 20
    assert sparse.last_top_k == 20
    assert candidate_counts == [3]
    assert trace.retrieval_top_k == 20
    assert trace.dense_count == 2
    assert trace.sparse_count == 2
    assert trace.merged_candidate_count == 3
    assert trace.final_result_count == 3
    assert len(reranker.last_results) == 3
    assert len(results) == 3

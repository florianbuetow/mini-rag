"""Orchestration layer coordinating indexing and search backends."""

import json
import logging
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from minirag.config import SearchConfig
from minirag.ingestion.chunker import ChunkSpan
from minirag.reranking.interface import Reranker
from minirag.retrieval.dense_interface import DenseRetrieval
from minirag.retrieval.sparse_interface import SparseRetrieval
from minirag.search.embeddings_interface import Embeddings
from minirag.search.hybrid import merge_hybrid_results
from minirag.search.types import ScoredChunk, SearchResult
from minirag.storage.interface import ChunkWithDocument, CorpusStats, Storage

logger = logging.getLogger(__name__)

_CITATION_KEY_CACHE_MAX = 1024


@dataclass(frozen=True)
class SearchTrace:
    """Internal search trace for status and tests without changing public API payloads."""

    reranking_active: bool
    retrieval_top_k: int
    dense_count: int
    sparse_count: int
    merged_candidate_count: int
    final_result_count: int


class Orchestration:
    """Coordinates indexing and query operations across all backend components."""

    def __init__(
        self,
        embeddings: Embeddings,
        storage: Storage,
        dense: DenseRetrieval,
        sparse: SparseRetrieval,
        search_config: SearchConfig,
        reranker: Reranker | None,
        chunker: Callable[[str], list[ChunkSpan]],
    ) -> None:
        """Initialize orchestration with all backend dependencies.

        ``chunker`` splits a document into chunks; the factory supplies a word-based
        chunker for fastText and a token-budget chunker for token-limited providers.
        """
        self._chunker = chunker
        self._embeddings = embeddings
        self._storage = storage
        self._dense = dense
        self._sparse = sparse
        self._search_config = search_config
        self._reranker = reranker
        self._citation_key_cache: OrderedDict[int, str] = OrderedDict()
        self._citation_key_cache_lock = threading.Lock()

    def index_document(self, text: str, citation: dict[str, object] | None, source_path: str) -> tuple[int, list[int]]:
        """Index one document through storage, chunking, embeddings, both indices, and citation storage."""
        if text.strip() == "":
            raise ValueError("document text must not be empty")

        if source_path.strip() == "":
            raise ValueError("source_path must not be empty")

        # Validate citation before any storage writes to fail fast on bad input.
        if citation is not None:
            citation_key_value = citation.get("citation_key")
            source_type = citation.get("source_type")
            if not isinstance(citation_key_value, str) or citation_key_value.strip() == "":
                raise ValueError("citation must contain a non-empty 'citation_key'")
            if not isinstance(source_type, str) or source_type.strip() == "":
                raise ValueError("citation must contain a non-empty 'source_type'")

        self._purge_existing_citation(citation)

        document_id = self._storage.insert_document_with_citation(text, citation, source_path)

        chunk_spans = self._chunker(text)

        chunk_ids: list[int] = []
        for chunk_index, chunk_span in enumerate(chunk_spans):
            try:
                line_from = text.count("\n", 0, chunk_span.char_start) + 1
                line_to = text.count("\n", 0, max(chunk_span.char_end - 1, chunk_span.char_start)) + 1
                chunk_id = self._storage.insert_chunk(
                    document_id=document_id,
                    content=chunk_span.text,
                    chunk_index=chunk_index,
                    char_start=chunk_span.char_start,
                    char_end=chunk_span.char_end,
                    line_from=line_from,
                    line_to=line_to,
                )
                chunk_ids.append(chunk_id)

                chunk_embedding = self._embeddings.embed([chunk_span.text])[0]
                self._dense.index(chunk_id=chunk_id, embedding=chunk_embedding)
                self._sparse.index(chunk_id=chunk_id, content=chunk_span.text)
            except Exception as exc:
                logger.error(
                    "Failed to index chunk %d of document_id=%s: %s",
                    chunk_index,
                    document_id,
                    exc,
                )
                raise RuntimeError(f"failed to index chunk {chunk_index} of document_id={document_id}") from exc

        self._dense.persist()
        self._sparse.persist()

        logger.info("Indexed document_id=%s with %s chunks", document_id, len(chunk_ids))
        return (document_id, chunk_ids)

    def _purge_existing_citation(self, citation: dict[str, object] | None) -> None:
        """Purge an already-indexed explicit citation before re-indexing it."""
        # A file already present means a previous run wrote it but did not finish: either it
        # was interrupted mid-document (chunk rows committed, vectors not yet persisted) or its
        # ledger entry was lost. Either way its indexed state is unproven, so purge every trace
        # and index it fresh rather than trusting it. This is what makes a crashed run safe to
        # re-run: re-indexing a file is idempotent, not an error.
        if citation is None:
            return

        existing_id = None
        if hasattr(self._storage, "get_document_id"):
            existing_id = self._storage.get_document_id(str(citation["citation_key"]))
        if existing_id is not None:
            self._purge_document(document_id=existing_id)

    def _purge_document(self, document_id: int) -> None:
        """Remove a document from storage and both retrieval indices."""
        chunk_ids = self._storage.delete_document(document_id=document_id)
        self._dense.remove_ids(chunk_ids)
        self._sparse.remove_ids(chunk_ids)
        with self._citation_key_cache_lock:
            self._citation_key_cache.pop(document_id, None)
        logger.info("Purged stale document_id=%s (%d chunks) before re-index", document_id, len(chunk_ids))

    def destroy_index(self) -> None:
        """Destroy storage and both retrieval indices."""
        self._storage.destroy()
        self._dense.destroy()
        self._sparse.destroy()
        with self._citation_key_cache_lock:
            self._citation_key_cache.clear()
        logger.info("Deleted storage and retrieval indices")

    def close_storage(self) -> None:
        """Close the storage connection."""
        self._storage.close()

    def corpus_stats(self) -> CorpusStats:
        """Return aggregate corpus counts from storage."""
        return self._storage.corpus_stats()

    def _get_citation_key_for_document(self, document_id: int) -> str:
        """Look up citation_key for a document, with cache for positive results only.

        Raises RuntimeError if no citation record exists (data integrity violation).
        """
        with self._citation_key_cache_lock:
            cached = self._citation_key_cache.get(document_id)
            if cached is not None:
                self._citation_key_cache.move_to_end(document_id)
                return cached

        citation_key = self._storage.get_citation_key(document_id)
        if citation_key is not None:
            with self._citation_key_cache_lock:
                self._citation_key_cache[document_id] = citation_key
                self._citation_key_cache.move_to_end(document_id)
                if len(self._citation_key_cache) > _CITATION_KEY_CACHE_MAX:
                    self._citation_key_cache.popitem(last=False)
            return citation_key

        raise RuntimeError(f"No citation record for document_id={document_id}; data integrity violation")

    def get_chunk(self, chunk_id: int) -> tuple[ChunkWithDocument, str]:
        """Return the chunk provenance record and its document's citation_key.

        Raises ValueError when the chunk does not exist.
        """
        chunk_record = self._storage.get_chunk(chunk_id=chunk_id)
        citation_key = self._get_citation_key_for_document(chunk_record.document_id)
        return (chunk_record, citation_key)

    def get_citation(self, citation_key: str) -> dict[str, object] | None:
        """Return parsed citation data for a citation_key, or None if not found."""
        citation_json = self._storage.get_citation(citation_key)
        if citation_json is None:
            return None
        try:
            parsed: dict[str, object] = json.loads(citation_json)
        except json.JSONDecodeError as exc:
            logger.error("Corrupt citation JSON for citation_key=%s: %s", citation_key, exc)
            raise ValueError(f"corrupt citation data for key: {citation_key}") from exc
        return parsed

    def _resolve_results(self, scored_chunk_ids: list[ScoredChunk], source: str) -> list[SearchResult]:
        """Resolve chunk IDs from retrieval engines into SearchResult payloads."""
        resolved_results: list[SearchResult] = []
        score_log: dict[str, dict[str, float | int]] = {}
        for chunk_id, score in scored_chunk_ids:
            try:
                chunk_record = self._storage.get_chunk(chunk_id=chunk_id)
            except ValueError as exc:
                logger.error("Data integrity violation during %s resolution: missing chunk_id=%s", source, chunk_id)
                raise RuntimeError(f"data integrity violation: missing chunk_id={chunk_id}") from exc

            document_id = chunk_record.document_id
            try:
                citation_key = self._get_citation_key_for_document(document_id)
            except RuntimeError as exc:
                logger.error(
                    "Data integrity violation during %s resolution: missing citation for document_id=%s",
                    source,
                    document_id,
                )
                raise RuntimeError(f"data integrity violation: missing citation for document_id={document_id}") from exc

            resolved_results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    citation_key=citation_key,
                    text=chunk_record.content,
                    score=score,
                    source_path=chunk_record.source_path,
                    chunk_index=chunk_record.chunk_index,
                    char_start=chunk_record.char_start,
                    char_end=chunk_record.char_end,
                    line_from=chunk_record.line_from,
                    line_to=chunk_record.line_to,
                )
            )
            score_log[str(chunk_id)] = {"score": round(score, 4), "doc_id": document_id}
        logger.debug("%s: %s", source, json.dumps(score_log))
        return resolved_results

    def _validate_search_params(self, query: str, top_k: int) -> None:
        """Validate shared query-time parameters for all search modes."""
        if query.strip() == "":
            raise ValueError("query must not be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

    def search_dense(self, query: str, top_k: int) -> list[SearchResult]:
        """Run dense search and resolve chunk texts."""
        self._validate_search_params(query=query, top_k=top_k)

        query_embedding = self._embeddings.embed([query])[0]
        dense_matches = self._dense.search(query_embedding=query_embedding, top_k=top_k)
        return self._resolve_results(scored_chunk_ids=dense_matches, source="dense")

    def search_sparse(self, query: str, top_k: int) -> list[SearchResult]:
        """Run sparse search and resolve chunk texts."""
        self._validate_search_params(query=query, top_k=top_k)

        sparse_matches = self._sparse.search(query=query, top_k=top_k)
        return self._resolve_results(scored_chunk_ids=sparse_matches, source="sparse")

    def search_hybrid(
        self,
        query: str,
        top_k: int,
        alpha: float | None,
        use_reranking: bool | None,
    ) -> list[SearchResult]:
        """Run hybrid search by merging dense and sparse result sets.

        Args:
            query: Search query string.
            top_k: Number of results to return.
            alpha: Dense/sparse weighting override. If None, uses config value.
            use_reranking: Reranking override. If None, uses reranker availability.
                If False, skips reranking even when a reranker is loaded.
        """
        results, _trace = self.search_hybrid_with_trace(
            query=query,
            top_k=top_k,
            alpha=alpha,
            use_reranking=use_reranking,
            reranking_candidate_callback=None,
        )
        return results

    def search_hybrid_with_trace(
        self,
        query: str,
        top_k: int,
        alpha: float | None,
        use_reranking: bool | None,
        reranking_candidate_callback: Callable[[int], None] | None,
    ) -> tuple[list[SearchResult], SearchTrace]:
        """Run hybrid search and return internal trace metrics.

        The trace is intentionally not used by public query endpoints. Chat
        streaming can use it for exact status messages without changing the
        non-chat search response contract.
        """
        self._validate_search_params(query=query, top_k=top_k)

        should_rerank = self._reranker is not None if use_reranking is None else (use_reranking and self._reranker is not None)
        retrieval_top_k = self._reranker.candidate_count(top_k=top_k) if should_rerank and self._reranker is not None else top_k

        dense_results = self.search_dense(query=query, top_k=retrieval_top_k)
        sparse_results = self.search_sparse(query=query, top_k=retrieval_top_k)

        effective_alpha = alpha if alpha is not None else self._search_config.hybrid.alpha
        merged_results = merge_hybrid_results(
            dense_results=dense_results,
            sparse_results=sparse_results,
            alpha=effective_alpha,
            top_k=retrieval_top_k,
        )

        if should_rerank and self._reranker is not None:
            if reranking_candidate_callback is not None:
                reranking_candidate_callback(len(merged_results))
            final_results = self._reranker.rerank(query=query, results=merged_results, top_k=top_k)
        else:
            final_results = merged_results

        trace = SearchTrace(
            reranking_active=should_rerank,
            retrieval_top_k=retrieval_top_k,
            dense_count=len(dense_results),
            sparse_count=len(sparse_results),
            merged_candidate_count=len(merged_results),
            final_result_count=len(final_results),
        )
        return final_results, trace

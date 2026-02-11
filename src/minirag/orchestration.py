"""Orchestration layer coordinating indexing and search backends."""

import json
import logging
from functools import lru_cache

from minirag.config import ChunkingConfig, SearchConfig
from minirag.ingestion.chunker import chunk_text
from minirag.reranking.interface import Reranker
from minirag.retrieval.dense_interface import DenseRetrieval
from minirag.retrieval.sparse_interface import SparseRetrieval
from minirag.search.embeddings_interface import Embeddings
from minirag.search.hybrid import merge_hybrid_results
from minirag.search.types import ScoredChunk, SearchResult
from minirag.storage.interface import Storage

logger = logging.getLogger(__name__)


class Orchestration:
    """Coordinates indexing and query operations across all backend components."""

    def __init__(
        self,
        chunking_config: ChunkingConfig,
        embeddings: Embeddings,
        storage: Storage,
        dense: DenseRetrieval,
        sparse: SparseRetrieval,
        search_config: SearchConfig,
        reranker: Reranker | None,
    ) -> None:
        """Initialize orchestration with all backend dependencies."""
        self._chunking_config = chunking_config
        self._embeddings = embeddings
        self._storage = storage
        self._dense = dense
        self._sparse = sparse
        self._search_config = search_config
        self._reranker = reranker
        self._get_citation_key_for_document = lru_cache(maxsize=1024)(self._get_citation_key_impl)

    def index_document(self, text: str, citation: dict[str, object] | None) -> tuple[int, list[int]]:
        """Index one document through storage, chunking, embeddings, and both indices."""
        if text.strip() == "":
            raise ValueError("document text must not be empty")

        document_id = self._storage.insert_document(text)
        chunks = chunk_text(
            text=text,
            chunk_size=self._chunking_config.chunk_size,
            overlap=self._chunking_config.overlap,
        )

        chunk_ids: list[int] = []
        for chunk_index, chunk in enumerate(chunks):
            try:
                chunk_id = self._storage.insert_chunk(document_id=document_id, content=chunk)
                chunk_ids.append(chunk_id)

                chunk_embedding = self._embeddings.embed([chunk])[0]
                self._dense.index(chunk_id=chunk_id, embedding=chunk_embedding)
                self._sparse.index(chunk_id=chunk_id, content=chunk)
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

        if citation is not None:
            citation_key = citation.get("citation_key")
            source_type = citation.get("source_type")
            if not isinstance(citation_key, str) or citation_key.strip() == "":
                raise ValueError("citation must contain a non-empty 'citation_key'")
            if not isinstance(source_type, str) or source_type.strip() == "":
                raise ValueError("citation must contain a non-empty 'source_type'")
            citation_json = json.dumps(citation)
            self._storage.insert_citation(citation_key=citation_key, document_id=document_id, citation_json=citation_json)
        else:
            auto_citation = {
                "citation_key": str(document_id),
                "source_type": "text_file",
                "common": {"title": str(document_id)},
                "source_data": {},
            }
            citation_json = json.dumps(auto_citation)
            self._storage.insert_citation(citation_key=str(document_id), document_id=document_id, citation_json=citation_json)

        logger.info("Indexed document_id=%s with %s chunks", document_id, len(chunk_ids))
        return (document_id, chunk_ids)

    def destroy_index(self) -> None:
        """Destroy storage and both retrieval indices."""
        self._storage.destroy()
        self._dense.destroy()
        self._sparse.destroy()
        self._get_citation_key_for_document.cache_clear()
        logger.info("Deleted storage and retrieval indices")

    def close_storage(self) -> None:
        """Close the storage connection."""
        self._storage.close()

    def _get_citation_key_impl(self, document_id: int) -> str:
        """Look up citation_key for a document, falling back to str(document_id)."""
        citation_key = self._storage.get_citation_key(document_id)
        if citation_key is not None:
            return citation_key
        return str(document_id)

    def get_citation(self, citation_key: str) -> dict[str, object] | None:
        """Return parsed citation data for a citation_key, or None if not found."""
        citation_json = self._storage.get_citation(citation_key)
        if citation_json is None:
            return None
        parsed: dict[str, object] = json.loads(citation_json)
        return parsed

    def _resolve_results(self, scored_chunk_ids: list[ScoredChunk], source: str) -> list[SearchResult]:
        """Resolve chunk IDs from retrieval engines into SearchResult payloads."""
        resolved_results: list[SearchResult] = []
        score_log: dict[str, dict[str, float | int]] = {}
        skipped_count = 0
        for chunk_id, score in scored_chunk_ids:
            try:
                document_id, chunk_text_value = self._storage.get_chunk(chunk_id=chunk_id)
            except ValueError:
                logger.warning("Skipping stale chunk_id=%s: not found in storage", chunk_id)
                skipped_count += 1
                continue
            citation_key = self._get_citation_key_for_document(document_id)
            resolved_results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    citation_key=citation_key,
                    text=chunk_text_value,
                    score=score,
                )
            )
            score_log[str(chunk_id)] = {"score": round(score, 4), "doc_id": document_id}
        if skipped_count > 0:
            logger.warning("Skipped %d stale chunk(s) during result resolution", skipped_count)
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

    def search_hybrid(self, query: str, top_k: int) -> list[SearchResult]:
        """Run hybrid search by merging dense and sparse result sets."""
        self._validate_search_params(query=query, top_k=top_k)

        retrieval_top_k = self._reranker.candidate_count(top_k=top_k) if self._reranker is not None else top_k

        dense_results = self.search_dense(query=query, top_k=retrieval_top_k)
        sparse_results = self.search_sparse(query=query, top_k=retrieval_top_k)

        alpha = self._search_config.hybrid.alpha
        merged_results = merge_hybrid_results(
            dense_results=dense_results,
            sparse_results=sparse_results,
            alpha=alpha,
            top_k=retrieval_top_k,
        )

        if self._reranker is not None:
            return self._reranker.rerank(query=query, results=merged_results, top_k=top_k)

        return merged_results

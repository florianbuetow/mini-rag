"""Orchestration layer coordinating indexing and search backends."""

import logging

from minirag.config import ChunkingConfig, SearchConfig
from minirag.ingestion.chunker import chunk_text
from minirag.retrieval.dense_interface import DenseRetrieval
from minirag.retrieval.sparse_interface import SparseRetrieval
from minirag.search.embeddings import FastTextEmbeddings
from minirag.search.hybrid import merge_hybrid_results
from minirag.search.types import ScoredChunk, SearchResult
from minirag.storage.interface import Storage

logger = logging.getLogger(__name__)


class Orchestration:
    """Coordinates indexing and query operations across all backend components."""

    def __init__(
        self,
        chunking_config: ChunkingConfig,
        embeddings: FastTextEmbeddings,
        storage: Storage,
        dense: DenseRetrieval,
        sparse: SparseRetrieval,
        search_config: SearchConfig,
    ) -> None:
        """Initialize orchestration with all backend dependencies."""
        self._chunking_config = chunking_config
        self._embeddings = embeddings
        self._storage = storage
        self._dense = dense
        self._sparse = sparse
        self._search_config = search_config

    def index_document(self, text: str) -> tuple[int, list[int]]:
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

        logger.info("Indexed document_id=%s with %s chunks", document_id, len(chunk_ids))
        return (document_id, chunk_ids)

    def destroy_index(self) -> None:
        """Destroy storage and both retrieval indices."""
        self._storage.destroy()
        self._dense.destroy()
        self._sparse.destroy()
        logger.info("Destroyed full mini-rag index")

    def _resolve_results(self, scored_chunk_ids: list[ScoredChunk]) -> list[SearchResult]:
        """Resolve chunk IDs from retrieval engines into SearchResult payloads."""
        resolved_results: list[SearchResult] = []
        for chunk_id, score in scored_chunk_ids:
            try:
                _, chunk_text_value = self._storage.get_chunk(chunk_id=chunk_id)
            except ValueError:
                logger.warning("Skipping stale chunk_id=%s: not found in storage", chunk_id)
                continue
            resolved_results.append(SearchResult(chunk_id=chunk_id, text=chunk_text_value, score=score))
        return resolved_results

    def search_dense(self, query: str, top_k: int) -> list[SearchResult]:
        """Run dense search and resolve chunk texts."""
        if query.strip() == "":
            raise ValueError("query must not be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        query_embedding = self._embeddings.embed([query])[0]
        dense_matches = self._dense.search(query_embedding=query_embedding, top_k=top_k)
        return self._resolve_results(scored_chunk_ids=dense_matches)

    def search_sparse(self, query: str, top_k: int) -> list[SearchResult]:
        """Run sparse search and resolve chunk texts."""
        if query.strip() == "":
            raise ValueError("query must not be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        sparse_matches = self._sparse.search(query=query, top_k=top_k)
        return self._resolve_results(scored_chunk_ids=sparse_matches)

    def search_hybrid(self, query: str, top_k: int) -> list[SearchResult]:
        """Run hybrid search by merging dense and sparse result sets."""
        if query.strip() == "":
            raise ValueError("query must not be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        dense_results = self.search_dense(query=query, top_k=top_k)
        sparse_results = self.search_sparse(query=query, top_k=top_k)

        alpha = self._search_config.hybrid.alpha
        return merge_hybrid_results(
            dense_results=dense_results,
            sparse_results=sparse_results,
            alpha=alpha,
            top_k=top_k,
        )

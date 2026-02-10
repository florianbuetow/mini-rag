"""Reranker abstraction used by hybrid search post-processing."""

from typing import Protocol

from minirag.search.types import SearchResult


class Reranker(Protocol):
    """Contract for reranking search results by query relevance."""

    def candidate_count(self, top_k: int) -> int:
        """Return how many merged candidates are needed before final reranking."""
        ...

    def rerank(self, query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]:
        """Re-score and re-rank search results, returning the top-k."""
        ...

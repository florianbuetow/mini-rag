"""Sparse retrieval abstraction interface."""

from abc import ABC, abstractmethod

from minirag.search.types import ScoredChunk


class SparseRetrieval(ABC):
    """Contract for sparse lexical indexing and search."""

    @abstractmethod
    def index(self, chunk_id: int, content: str) -> None:
        """Index one chunk text with its chunk ID."""

    @abstractmethod
    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        """Search by query text and return scored chunk IDs."""

    @abstractmethod
    def persist(self) -> None:
        """Persist the in-memory index to disk."""

    @abstractmethod
    def destroy(self) -> None:
        """Destroy the sparse index contents."""

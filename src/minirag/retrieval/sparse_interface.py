"""Sparse retrieval abstraction interface."""

from abc import ABC, abstractmethod


class SparseRetrieval(ABC):
    """Contract for sparse lexical indexing and search."""

    @abstractmethod
    def index(self, chunk_id: int, content: str) -> None:
        """Index one chunk text with its chunk ID."""

    @abstractmethod
    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """Search by query text and return scored chunk IDs."""

    @abstractmethod
    def destroy(self) -> None:
        """Destroy the sparse index contents."""

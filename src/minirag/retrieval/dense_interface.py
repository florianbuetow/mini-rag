"""Dense retrieval abstraction interface."""

from abc import ABC, abstractmethod

from minirag.search.types import ScoredChunk


class DenseRetrieval(ABC):
    """Contract for dense vector indexing and search."""

    @abstractmethod
    def index(self, chunk_id: int, embedding: list[float]) -> None:
        """Index one chunk embedding with its chunk ID."""

    @abstractmethod
    def remove_ids(self, chunk_ids: list[int]) -> int:
        """Remove vectors by chunk ID. Return the number removed."""

    @abstractmethod
    def search(self, query_embedding: list[float], top_k: int) -> list[ScoredChunk]:
        """Search by query embedding and return scored chunk IDs."""

    @abstractmethod
    def persist(self) -> None:
        """Persist the in-memory index to disk."""

    @abstractmethod
    def destroy(self) -> None:
        """Destroy the dense index contents."""

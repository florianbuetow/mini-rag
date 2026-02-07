"""Dense retrieval abstraction interface."""

from abc import ABC, abstractmethod


class DenseRetrieval(ABC):
    """Contract for dense vector indexing and search."""

    @abstractmethod
    def index(self, chunk_id: int, embedding: list[float]) -> None:
        """Index one chunk embedding with its chunk ID."""

    @abstractmethod
    def search(self, query_embedding: list[float], top_k: int) -> list[tuple[int, float]]:
        """Search by query embedding and return scored chunk IDs."""

    @abstractmethod
    def destroy(self) -> None:
        """Destroy the dense index contents."""

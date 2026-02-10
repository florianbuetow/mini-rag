"""Storage abstraction interface."""

from abc import ABC, abstractmethod


class StorageReader(ABC):
    """Read-only contract for persisted documents and chunks."""

    @abstractmethod
    def get_document(self, document_id: int) -> str:
        """Return document content for the given ID."""

    @abstractmethod
    def get_chunk(self, chunk_id: int) -> tuple[int, str]:
        """Return (document_id, chunk_content) for the given chunk ID."""

    @abstractmethod
    def list_chunks(self, document_id: int) -> list[tuple[int, str]]:
        """Return all (chunk_id, chunk_content) tuples for one document."""


class StorageWriter(ABC):
    """Write contract for persisted documents and chunks."""

    @abstractmethod
    def insert_document(self, content: str) -> int:
        """Store a full document and return its ID."""

    @abstractmethod
    def insert_chunk(self, document_id: int, content: str) -> int:
        """Store a chunk and return its ID."""


class StorageLifecycle(ABC):
    """Lifecycle and destructive operations for storage backends."""

    @abstractmethod
    def close(self) -> None:
        """Close the storage connection."""

    @abstractmethod
    def destroy(self) -> None:
        """Destroy all stored data."""


class Storage(StorageReader, StorageWriter, StorageLifecycle, ABC):
    """Full storage contract used by indexing orchestration."""

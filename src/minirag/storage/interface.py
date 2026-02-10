"""Storage abstraction interface."""

from abc import ABC, abstractmethod
from typing import NamedTuple


class ChunkWithDocument(NamedTuple):
    """Chunk payload paired with owning document ID."""

    document_id: int
    content: str


class ChunkRecord(NamedTuple):
    """Persisted chunk row containing chunk ID and content."""

    chunk_id: int
    content: str


class StorageReader(ABC):
    """Read-only contract for persisted documents and chunks."""

    @abstractmethod
    def get_document(self, document_id: int) -> str:
        """Return document content for the given ID."""

    @abstractmethod
    def get_chunk(self, chunk_id: int) -> ChunkWithDocument:
        """Return (document_id, chunk_content) for the given chunk ID."""

    @abstractmethod
    def list_chunks(self, document_id: int) -> list[ChunkRecord]:
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
    """Lifecycle operations for storage backends."""

    @abstractmethod
    def close(self) -> None:
        """Close the storage connection without deleting data."""

    @abstractmethod
    def destroy(self) -> None:
        """Destroy all stored data while keeping the connection usable."""


class Storage(StorageReader, StorageWriter, StorageLifecycle, ABC):
    """Full storage contract combining read, write, and lifecycle behavior."""

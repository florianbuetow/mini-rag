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


class CorpusStats(NamedTuple):
    """Aggregate corpus storage counts used for query-time status."""

    document_count: int
    chunk_count: int


class StorageReader(ABC):
    """Read-only contract for persisted documents and chunks."""

    @abstractmethod
    def get_document(self, document_id: int) -> str:
        """Return document content for the given ID."""

    @abstractmethod
    def get_chunk(self, chunk_id: int) -> ChunkWithDocument:
        """Return chunk content and owning document ID for the given chunk ID."""

    @abstractmethod
    def list_chunks(self, document_id: int) -> list[ChunkRecord]:
        """Return all chunk records for one document."""

    @abstractmethod
    def corpus_stats(self) -> CorpusStats:
        """Return aggregate document and chunk counts for the corpus."""

    @abstractmethod
    def get_citation_key(self, document_id: int) -> str | None:
        """Return the citation_key for a document, or None if not found."""

    @abstractmethod
    def get_citation(self, citation_key: str) -> str | None:
        """Return raw citation JSON string for a citation_key, or None if not found."""

    @abstractmethod
    def get_document_id(self, citation_key: str) -> int | None:
        """Return the document ID owning a citation_key, or None if not found."""


class StorageWriter(ABC):
    """Write contract for persisted documents and chunks."""

    @abstractmethod
    def insert_document_with_citation(self, content: str, citation: dict[str, object] | None) -> int:
        """Store a document and citation atomically and return the document ID."""

    @abstractmethod
    def insert_document(self, content: str) -> int:
        """Store a full document and return its ID."""

    @abstractmethod
    def insert_chunk(self, document_id: int, content: str) -> int:
        """Store a chunk and return its ID."""

    @abstractmethod
    def insert_citation(self, citation_key: str, document_id: int, citation_json: str) -> None:
        """Store a citation record for a document."""

    @abstractmethod
    def delete_document(self, document_id: int) -> list[int]:
        """Delete a document, its chunks, and its citation. Return the deleted chunk IDs."""


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

"""Shared search result types."""

from dataclasses import dataclass
from typing import NamedTuple


class ScoredChunk(NamedTuple):
    """Retrieval result pairing a chunk ID with its relevance score."""

    chunk_id: int
    score: float


@dataclass(frozen=True)
class SearchResult:
    """Search result payload with chunk ID, text, and normalized score."""

    chunk_id: int
    document_id: int
    citation_key: str
    text: str
    score: float

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        if self.chunk_id <= 0:
            raise ValueError("chunk_id must be greater than 0")
        if self.document_id <= 0:
            raise ValueError("document_id must be greater than 0")
        if self.citation_key.strip() == "":
            raise ValueError("citation_key must not be empty")
        if self.text.strip() == "":
            raise ValueError("text must not be empty")
        if self.score < 0.0:
            raise ValueError("score must be greater than or equal to 0.0")
        if self.score > 1.0:
            raise ValueError("score must be less than or equal to 1.0")

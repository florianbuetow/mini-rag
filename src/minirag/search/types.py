"""Shared search result types."""

from dataclasses import dataclass
from typing import NamedTuple


class ScoredChunk(NamedTuple):
    """Retrieval result pairing a chunk ID with its relevance score."""

    chunk_id: int
    score: float


@dataclass(frozen=True)
class SearchResult:
    """Search result payload with chunk ID, text, normalized score, and source provenance."""

    chunk_id: int
    document_id: int
    citation_key: str
    text: str
    score: float
    source_path: str
    chunk_index: int
    char_start: int
    char_end: int
    line_from: int
    line_to: int

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        self._validate_result_fields()
        self._validate_provenance_fields()

    def _validate_result_fields(self) -> None:
        """Validate chunk identity, text, and score fields."""
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

    def _validate_provenance_fields(self) -> None:
        """Validate source path, chunk ordinal, char span, and line range fields."""
        if self.source_path.strip() == "":
            raise ValueError("source_path must not be empty")
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be greater than or equal to 0")
        if self.char_start < 0:
            raise ValueError("char_start must be greater than or equal to 0")
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if self.line_from < 1:
            raise ValueError("line_from must be greater than or equal to 1")
        if self.line_to < self.line_from:
            raise ValueError("line_to must be greater than or equal to line_from")

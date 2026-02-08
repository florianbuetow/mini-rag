"""Shared search result types."""

from dataclasses import dataclass


@dataclass
class SearchResult:
    """Search result payload with chunk ID, text, and normalized score."""

    chunk_id: int
    text: str
    score: float

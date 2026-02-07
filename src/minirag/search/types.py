"""Shared search result types."""

from dataclasses import dataclass


@dataclass
class SearchResult:
    """Search result payload with text and normalized score."""

    text: str
    score: float

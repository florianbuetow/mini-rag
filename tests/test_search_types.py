"""Unit tests for SearchResult validation."""

import pytest

from minirag.search.types import SearchResult


def test_search_result_valid_construction() -> None:
    """SearchResult should accept valid chunk_id, text, and score."""
    result = SearchResult(chunk_id=1, text="hello world", score=0.5)
    assert result.chunk_id == 1
    assert result.text == "hello world"
    assert result.score == 0.5


def test_search_result_boundary_scores() -> None:
    """SearchResult should accept scores at boundaries 0.0 and 1.0."""
    zero = SearchResult(chunk_id=1, text="a", score=0.0)
    assert zero.score == 0.0

    one = SearchResult(chunk_id=1, text="a", score=1.0)
    assert one.score == 1.0


def test_search_result_invalid_chunk_id_zero() -> None:
    """SearchResult should reject chunk_id of 0."""
    with pytest.raises(ValueError, match="chunk_id must be greater than 0"):
        SearchResult(chunk_id=0, text="hello", score=0.5)


def test_search_result_invalid_chunk_id_negative() -> None:
    """SearchResult should reject negative chunk_id."""
    with pytest.raises(ValueError, match="chunk_id must be greater than 0"):
        SearchResult(chunk_id=-1, text="hello", score=0.5)


def test_search_result_empty_text() -> None:
    """SearchResult should reject empty text."""
    with pytest.raises(ValueError, match="text must not be empty"):
        SearchResult(chunk_id=1, text="", score=0.5)


def test_search_result_whitespace_only_text() -> None:
    """SearchResult should reject whitespace-only text."""
    with pytest.raises(ValueError, match="text must not be empty"):
        SearchResult(chunk_id=1, text="   ", score=0.5)


def test_search_result_score_negative() -> None:
    """SearchResult should reject negative score."""
    with pytest.raises(ValueError, match="score must be greater than or equal to 0.0"):
        SearchResult(chunk_id=1, text="hello", score=-0.1)


def test_search_result_score_above_one() -> None:
    """SearchResult should reject score above 1.0."""
    with pytest.raises(ValueError, match="score must be less than or equal to 1.0"):
        SearchResult(chunk_id=1, text="hello", score=1.1)

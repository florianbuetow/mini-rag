"""Unit tests for Tantivy sparse retrieval backend."""

from pathlib import Path

import pytest

from minirag.retrieval.errors import IndexConfigurationError
from minirag.retrieval.tantivy_sparse import TantivySparse


def test_tantivy_sparse_index_search_and_destroy(tmp_path: Path) -> None:
    """Tantivy backend should index, search, and clear documents."""
    index_dir = tmp_path / "tantivy"
    sparse = TantivySparse(index_dir=index_dir, language="en", stemming=True)

    assert sparse.search(query="hello", top_k=5) == []

    sparse.index(chunk_id=1, content="hello world")
    sparse.index(chunk_id=2, content="world value")
    sparse.persist()

    results = sparse.search(query="hello", top_k=5)
    assert len(results) >= 1
    assert results[0][0] == 1
    assert 0.0 <= results[0][1] <= 1.0

    sparse.destroy()
    assert sparse.search(query="hello", top_k=5) == []


def test_tantivy_sparse_invalid_values_raise(tmp_path: Path) -> None:
    """Tantivy backend should validate constructor and query/index inputs."""
    with pytest.raises(ValueError):
        TantivySparse(index_dir=tmp_path / "tantivy", language="", stemming=True)

    with pytest.raises(ValueError, match="unsupported Tantivy language"):
        TantivySparse(index_dir=tmp_path / "unsupported", language="xx", stemming=True)

    sparse = TantivySparse(index_dir=tmp_path / "tantivy2", language="en", stemming=True)

    with pytest.raises(ValueError):
        sparse.index(chunk_id=0, content="hello")

    with pytest.raises(ValueError):
        sparse.index(chunk_id=1, content="  ")

    with pytest.raises(ValueError):
        sparse.search(query="", top_k=1)

    with pytest.raises(ValueError):
        sparse.search(query="hello", top_k=0)


def test_english_stemming_is_applied_to_indexing_and_query_parsing(tmp_path: Path) -> None:
    """English stemming should normalize terms on both sides of a search."""
    sparse = TantivySparse(index_dir=tmp_path / "tantivy", language="en", stemming=True)
    sparse.index(chunk_id=1, content="running")
    sparse.index(chunk_id=2, content="run")
    sparse.persist()

    assert {result.chunk_id for result in sparse.search(query="run", top_k=10)} == {1, 2}
    assert {result.chunk_id for result in sparse.search(query="running", top_k=10)} == {1, 2}


def test_disabling_stemming_preserves_distinct_english_terms(tmp_path: Path) -> None:
    """Stemming=false should leave inflected forms as distinct indexed terms."""
    sparse = TantivySparse(index_dir=tmp_path / "tantivy", language="en", stemming=False)
    sparse.index(chunk_id=1, content="running")
    sparse.index(chunk_id=2, content="run")
    sparse.persist()

    assert [result.chunk_id for result in sparse.search(query="run", top_k=10)] == [2]
    assert [result.chunk_id for result in sparse.search(query="running", top_k=10)] == [1]


def test_french_stemming_is_applied_to_indexing_and_query_parsing(tmp_path: Path) -> None:
    """Configured non-English stemming should normalize index and query terms."""
    sparse = TantivySparse(index_dir=tmp_path / "tantivy", language="fr", stemming=True)
    sparse.index(chunk_id=1, content="chevaux")
    sparse.index(chunk_id=2, content="cheval")
    sparse.persist()

    assert {result.chunk_id for result in sparse.search(query="cheval", top_k=10)} == {1, 2}
    assert {result.chunk_id for result in sparse.search(query="chevaux", top_k=10)} == {1, 2}


def test_tokenizer_settings_survive_reopen_and_destroy(tmp_path: Path) -> None:
    """Reopened and cleared indexes should keep using their configured analyzer."""
    index_dir = tmp_path / "tantivy"
    sparse = TantivySparse(index_dir=index_dir, language="en", stemming=True)
    sparse.index(chunk_id=1, content="running")
    sparse.persist()

    reopened = TantivySparse(index_dir=index_dir, language="English", stemming=True)
    assert [result.chunk_id for result in reopened.search(query="run", top_k=10)] == [1]

    reopened.destroy()
    after_destroy = TantivySparse(index_dir=index_dir, language="en", stemming=True)
    assert after_destroy.search(query="run", top_k=10) == []


@pytest.mark.parametrize(
    ("language", "stemming"),
    [("fr", True), ("en", False)],
)
def test_reopen_rejects_mismatched_tokenizer_settings(
    tmp_path: Path,
    language: str,
    stemming: bool,
) -> None:
    """An existing index must never silently use different analyzer settings."""
    index_dir = tmp_path / "tantivy"
    TantivySparse(index_dir=index_dir, language="en", stemming=True)

    with pytest.raises(IndexConfigurationError, match="do not match"):
        TantivySparse(index_dir=index_dir, language=language, stemming=stemming)


def test_reopen_rejects_index_without_tokenizer_settings(tmp_path: Path) -> None:
    """Legacy indexes without analyzer metadata should require an explicit rebuild."""
    index_dir = tmp_path / "tantivy"
    TantivySparse(index_dir=index_dir, language="en", stemming=True)
    (index_dir / "minirag-tantivy-settings.json").unlink()

    with pytest.raises(IndexConfigurationError, match="has no tokenizer settings"):
        TantivySparse(index_dir=index_dir, language="en", stemming=True)

"""Unit tests for Tantivy sparse retrieval backend."""

from pathlib import Path

import pytest

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

    sparse = TantivySparse(index_dir=tmp_path / "tantivy2", language="en", stemming=True)

    with pytest.raises(ValueError):
        sparse.index(chunk_id=0, content="hello")

    with pytest.raises(ValueError):
        sparse.index(chunk_id=1, content="  ")

    with pytest.raises(ValueError):
        sparse.search(query="", top_k=1)

    with pytest.raises(ValueError):
        sparse.search(query="hello", top_k=0)

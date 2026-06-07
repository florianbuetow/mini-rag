"""Unit tests for FAISS dense retrieval backend."""

from pathlib import Path

import pytest

from minirag.retrieval.faiss_dense import FAISSDense


def test_faiss_dense_index_search_and_destroy(tmp_path: Path) -> None:
    """FAISS backend should index, search, persist, and destroy vectors."""
    index_dir = tmp_path / "faiss"
    dense = FAISSDense(dimension=3, index_dir=index_dir, nprobe=1)

    dense.index(chunk_id=1, embedding=[1.0, 0.0, 0.0])
    dense.index(chunk_id=2, embedding=[0.0, 1.0, 0.0])
    dense.persist()

    results = dense.search(query_embedding=[1.0, 0.0, 0.0], top_k=2)
    assert len(results) >= 1
    assert results[0][0] == 1
    assert 0.0 <= results[0][1] <= 1.0

    reloaded = FAISSDense(dimension=3, index_dir=index_dir, nprobe=1)
    reloaded_results = reloaded.search(query_embedding=[0.0, 1.0, 0.0], top_k=2)
    assert len(reloaded_results) >= 1
    assert reloaded_results[0][0] == 2

    reloaded.destroy()
    assert reloaded.search(query_embedding=[1.0, 0.0, 0.0], top_k=3) == []


def test_faiss_dense_invalid_parameters_raise(tmp_path: Path) -> None:
    """FAISS backend should validate parameters and vectors."""
    with pytest.raises(ValueError):
        FAISSDense(dimension=0, index_dir=tmp_path / "x", nprobe=1)

    with pytest.raises(ValueError):
        FAISSDense(dimension=3, index_dir=tmp_path / "x", nprobe=0)

    dense = FAISSDense(dimension=3, index_dir=tmp_path / "faiss", nprobe=1)

    with pytest.raises(ValueError):
        dense.index(chunk_id=0, embedding=[1.0, 0.0, 0.0])

    with pytest.raises(ValueError):
        dense.index(chunk_id=1, embedding=[1.0, 0.0])

    with pytest.raises(ValueError):
        dense.search(query_embedding=[1.0, 0.0, 0.0], top_k=0)


def test_faiss_dense_rejects_dimension_mismatch_on_reload(tmp_path: Path) -> None:
    """Reloading a persisted index under a different dimension raises a re-index error."""
    index_dir = tmp_path / "faiss"
    dense = FAISSDense(dimension=3, index_dir=index_dir, nprobe=1)
    dense.index(chunk_id=1, embedding=[1.0, 0.0, 0.0])
    dense.persist()

    with pytest.raises(ValueError, match="re-index"):
        FAISSDense(dimension=5, index_dir=index_dir, nprobe=1)

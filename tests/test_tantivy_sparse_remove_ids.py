"""Regression tests for Tantivy per-chunk removal."""

from pathlib import Path

from minirag.retrieval.tantivy_sparse import TantivySparse


def test_remove_ids_drops_chunk_from_sparse_results(tmp_path: Path) -> None:
    sparse = TantivySparse(index_dir=tmp_path / "tantivy", language="en", stemming=True)
    sparse.index(chunk_id=101, content="needle first")
    sparse.index(chunk_id=102, content="needle second")
    sparse.persist()

    assert {result.chunk_id for result in sparse.search(query="needle", top_k=10)} == {101, 102}

    sparse.remove_ids([102])
    sparse.persist()

    assert {result.chunk_id for result in sparse.search(query="needle", top_k=10)} == {101}


def test_remove_ids_empty_list_is_noop(tmp_path: Path) -> None:
    sparse = TantivySparse(index_dir=tmp_path / "tantivy", language="en", stemming=True)
    sparse.index(chunk_id=101, content="needle")
    sparse.persist()

    sparse.remove_ids([])
    sparse.persist()

    assert sparse.search(query="needle", top_k=10)[0].chunk_id == 101


def test_remove_ids_ignores_missing_ids(tmp_path: Path) -> None:
    sparse = TantivySparse(index_dir=tmp_path / "tantivy", language="en", stemming=True)
    sparse.index(chunk_id=101, content="needle")
    sparse.persist()

    sparse.remove_ids([999])
    sparse.persist()

    assert sparse.search(query="needle", top_k=10)[0].chunk_id == 101

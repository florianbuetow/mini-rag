"""Regression tests for FAISS per-chunk removal."""

from pathlib import Path

from minirag.retrieval.faiss_dense import FAISSDense


def test_remove_ids_drops_vectors_from_search_results(tmp_path: Path) -> None:
    dense = FAISSDense(dimension=3, index_dir=tmp_path / "faiss", index_type="IndexFlatIP", nprobe=1)
    dense.index(chunk_id=101, embedding=[1.0, 0.0, 0.0])
    dense.index(chunk_id=102, embedding=[0.0, 1.0, 0.0])
    dense.index(chunk_id=103, embedding=[0.0, 0.0, 1.0])

    assert dense.remove_ids([102]) == 1

    results = dense.search(query_embedding=[0.0, 1.0, 0.0], top_k=3)
    assert {result.chunk_id for result in results} == {101, 103}


def test_remove_ids_empty_list_is_noop(tmp_path: Path) -> None:
    dense = FAISSDense(dimension=3, index_dir=tmp_path / "faiss", index_type="IndexFlatIP", nprobe=1)
    dense.index(chunk_id=101, embedding=[1.0, 0.0, 0.0])

    assert dense.remove_ids([]) == 0
    assert dense.search(query_embedding=[1.0, 0.0, 0.0], top_k=1)[0].chunk_id == 101


def test_remove_ids_ignores_missing_ids(tmp_path: Path) -> None:
    dense = FAISSDense(dimension=3, index_dir=tmp_path / "faiss", index_type="IndexFlatIP", nprobe=1)
    dense.index(chunk_id=101, embedding=[1.0, 0.0, 0.0])

    assert dense.remove_ids([999]) == 0
    assert dense.search(query_embedding=[1.0, 0.0, 0.0], top_k=1)[0].chunk_id == 101


def test_remove_ids_handles_pending_and_trained_ivf_vectors(tmp_path: Path) -> None:
    index_dir = tmp_path / "ivf"
    pending = FAISSDense(dimension=3, index_dir=index_dir, index_type="IVF1,Flat", nprobe=1)
    pending.index(chunk_id=101, embedding=[1.0, 0.0, 0.0])
    pending.index(chunk_id=102, embedding=[0.0, 1.0, 0.0])
    assert pending.remove_ids([102]) == 1
    pending.persist()

    reopened = FAISSDense(dimension=3, index_dir=index_dir, index_type="IVF1,Flat", nprobe=1)
    for chunk_id in range(102, 140):
        reopened.index(chunk_id=chunk_id, embedding=[0.0, 1.0, 0.0])
    reopened.persist()
    assert reopened.remove_ids([101]) == 1
    reopened.persist()

    final = FAISSDense(dimension=3, index_dir=index_dir, index_type="IVF1,Flat", nprobe=1)
    result_ids = {result.chunk_id for result in final.search([1.0, 1.0, 0.0], top_k=50)}
    assert 101 not in result_ids
    assert {102, 139}.issubset(result_ids)

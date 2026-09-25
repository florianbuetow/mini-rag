"""Unit tests for FAISS dense retrieval backend."""

from pathlib import Path

import pytest

from minirag.retrieval.faiss_dense import FAISSDense


def test_faiss_dense_index_search_and_destroy(tmp_path: Path) -> None:
    """FAISS backend should index, search, persist, and destroy vectors."""
    index_dir = tmp_path / "faiss"
    dense = FAISSDense(dimension=3, index_dir=index_dir, index_type="IndexFlatIP", nprobe=1)

    dense.index(chunk_id=1, embedding=[1.0, 0.0, 0.0])
    dense.index(chunk_id=2, embedding=[0.0, 1.0, 0.0])
    dense.persist()

    results = dense.search(query_embedding=[1.0, 0.0, 0.0], top_k=2)
    assert len(results) >= 1
    assert results[0][0] == 1
    assert 0.0 <= results[0][1] <= 1.0

    reloaded = FAISSDense(dimension=3, index_dir=index_dir, index_type="IndexFlatIP", nprobe=1)
    reloaded_results = reloaded.search(query_embedding=[0.0, 1.0, 0.0], top_k=2)
    assert len(reloaded_results) >= 1
    assert reloaded_results[0][0] == 2

    reloaded.destroy()
    assert reloaded.search(query_embedding=[1.0, 0.0, 0.0], top_k=3) == []


def test_faiss_dense_invalid_parameters_raise(tmp_path: Path) -> None:
    """FAISS backend should validate parameters and vectors."""
    with pytest.raises(ValueError):
        FAISSDense(dimension=0, index_dir=tmp_path / "x", index_type="IndexFlatIP", nprobe=1)

    with pytest.raises(ValueError):
        FAISSDense(dimension=3, index_dir=tmp_path / "x", index_type="IndexFlatIP", nprobe=0)

    dense = FAISSDense(dimension=3, index_dir=tmp_path / "faiss", index_type="IndexFlatIP", nprobe=1)

    with pytest.raises(ValueError):
        dense.index(chunk_id=0, embedding=[1.0, 0.0, 0.0])

    with pytest.raises(ValueError):
        dense.index(chunk_id=1, embedding=[1.0, 0.0])

    with pytest.raises(ValueError):
        dense.search(query_embedding=[1.0, 0.0, 0.0], top_k=0)


def test_faiss_dense_rejects_dimension_mismatch_on_reload(tmp_path: Path) -> None:
    """Reloading a persisted index under a different dimension raises a re-index error."""
    index_dir = tmp_path / "faiss"
    dense = FAISSDense(dimension=3, index_dir=index_dir, index_type="IndexFlatIP", nprobe=1)
    dense.index(chunk_id=1, embedding=[1.0, 0.0, 0.0])
    dense.persist()

    with pytest.raises(ValueError, match="re-index"):
        FAISSDense(dimension=5, index_dir=index_dir, index_type="IndexFlatIP", nprobe=1)


def test_ivf_buffers_searchable_vectors_until_recommended_training_size_then_persists(tmp_path: Path) -> None:
    """Small IVF corpora remain searchable and train at FAISS's recommended sample size."""
    index_dir = tmp_path / "ivf"
    dense = FAISSDense(dimension=3, index_dir=index_dir, index_type="IVF1,Flat", nprobe=1)
    dense.index(chunk_id=11, embedding=[1.0, 0.0, 0.0])
    dense.index(chunk_id=12, embedding=[0.0, 1.0, 0.0])
    dense.persist()

    assert dense.search(query_embedding=[0.0, 1.0, 0.0], top_k=2)[0].chunk_id == 12

    pending_reload = FAISSDense(dimension=3, index_dir=index_dir, index_type="IVF1,Flat", nprobe=1)
    assert pending_reload.search(query_embedding=[1.0, 0.0, 0.0], top_k=2)[0].chunk_id == 11
    for chunk_id in range(13, 50):
        pending_reload.index(chunk_id=chunk_id, embedding=[0.0, 0.0, 1.0])
    pending_reload.persist()

    assert not (index_dir / "pending.npz").exists()
    trained_reload = FAISSDense(dimension=3, index_dir=index_dir, index_type="IVF1,Flat", nprobe=1)
    assert trained_reload.search([1.0, 0.0, 0.0], top_k=1)[0].chunk_id == 11


def test_ivf_adds_after_training_and_reopens_with_external_ids(tmp_path: Path) -> None:
    """Vectors added after IVF training retain their caller-provided IDs."""
    index_dir = tmp_path / "ivf"
    dense = FAISSDense(dimension=2, index_dir=index_dir, index_type="IVF1,Flat", nprobe=1)
    for chunk_id in range(101, 140):
        dense.index(chunk_id=chunk_id, embedding=[1.0, 0.0])
    dense.persist()
    assert dense.remove_ids([102]) == 1
    dense.index(chunk_id=202, embedding=[0.0, 1.0])
    dense.persist()

    reloaded = FAISSDense(dimension=2, index_dir=index_dir, index_type="IVF1,Flat", nprobe=1)
    assert reloaded.search([0.0, 1.0], top_k=2)[0].chunk_id == 202
    assert 102 not in {result.chunk_id for result in reloaded.search([1.0, 0.0], top_k=50)}


def test_rejects_persisted_index_type_mismatch(tmp_path: Path) -> None:
    """Changing the configured index structure requires a corpus rebuild."""
    index_dir = tmp_path / "faiss"
    dense = FAISSDense(dimension=3, index_dir=index_dir, index_type="IndexFlatIP", nprobe=1)
    dense.persist()

    with pytest.raises(ValueError, match="does not match configured type"):
        FAISSDense(dimension=3, index_dir=index_dir, index_type="IVF2,Flat", nprobe=1)


def test_rejects_corrupt_pending_ivf_snapshot(tmp_path: Path) -> None:
    """A partial pending-vector snapshot fails clearly instead of losing vectors."""
    index_dir = tmp_path / "ivf"
    dense = FAISSDense(dimension=3, index_dir=index_dir, index_type="IVF2,Flat", nprobe=1)
    dense.index(chunk_id=11, embedding=[1.0, 0.0, 0.0])
    dense.persist()
    (index_dir / "pending.npz").write_bytes(b"partial snapshot")

    with pytest.raises(ValueError, match="invalid pending FAISS vectors"):
        FAISSDense(dimension=3, index_dir=index_dir, index_type="IVF2,Flat", nprobe=1)


def test_rejects_corrupt_index_and_metadata_snapshots(tmp_path: Path) -> None:
    """Corrupt snapshot components request a rebuild through the shared error path."""
    corrupt_index_dir = tmp_path / "corrupt-index"
    FAISSDense(dimension=3, index_dir=corrupt_index_dir, index_type="IndexFlatIP", nprobe=1)
    (corrupt_index_dir / "index.faiss").write_bytes(b"partial index")
    with pytest.raises(ValueError, match="invalid FAISS index"):
        FAISSDense(dimension=3, index_dir=corrupt_index_dir, index_type="IndexFlatIP", nprobe=1)

    corrupt_metadata_dir = tmp_path / "corrupt-metadata"
    FAISSDense(dimension=3, index_dir=corrupt_metadata_dir, index_type="IndexFlatIP", nprobe=1)
    (corrupt_metadata_dir / "index.meta.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid FAISS metadata"):
        FAISSDense(dimension=3, index_dir=corrupt_metadata_dir, index_type="IndexFlatIP", nprobe=1)


def test_ivf_nprobe_applies_on_create_reload_and_destroy(tmp_path: Path) -> None:
    """Configured nprobe controls how many IVF partitions participate in search."""
    index_dir = tmp_path / "ivf"
    single_probe = FAISSDense(dimension=2, index_dir=index_dir, index_type="IVF2,Flat", nprobe=1)
    for chunk_id in range(1, 40):
        single_probe.index(chunk_id=chunk_id, embedding=[1.0, 0.0])
    for chunk_id in range(40, 79):
        single_probe.index(chunk_id=chunk_id, embedding=[0.0, 1.0])
    single_probe.persist()

    assert len(single_probe.search([1.0, 1.0], top_k=78)) == 39

    two_probes = FAISSDense(dimension=2, index_dir=index_dir, index_type="IVF2,Flat", nprobe=2)
    assert len(two_probes.search([1.0, 1.0], top_k=78)) == 78

    two_probes.destroy()
    for chunk_id in range(101, 140):
        two_probes.index(chunk_id=chunk_id, embedding=[1.0, 0.0])
    for chunk_id in range(140, 179):
        two_probes.index(chunk_id=chunk_id, embedding=[0.0, 1.0])
    two_probes.persist()
    assert len(two_probes.search([1.0, 1.0], top_k=78)) == 78

"""Unit tests for corpus name validation and CorpusManager."""

import threading
from pathlib import Path

import pytest

from minirag.backend_factory import build_orchestration
from minirag.config import Config, IndexConfig
from minirag.corpus import CorpusManager, validate_corpus_name
from minirag.corpus_description import NO_DESCRIPTION_AVAILABLE, description_path
from minirag.retrieval.errors import IndexConfigurationError
from minirag.storage.interface import CorpusStats


class FakeIndexConfig:
    pass


class FakeSearchConfig:
    pass


class FakeEmbeddings:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def fake_backend_factory(**kwargs: object) -> object:
    del kwargs
    return FakeOrchestration()


class TestValidateCorpusName:
    """Tests for validate_corpus_name()."""

    @pytest.mark.parametrize(
        "name",
        ["books", "my-corpus", "test_data", "A123", "corpusX-2"],
    )
    def test_valid_names(self, name: str) -> None:
        assert validate_corpus_name(name) == name

    @pytest.mark.parametrize(
        "name",
        ["", "123bad", "-start", "_start", "has space", "no.dot", "a/b", "a@b"],
    )
    def test_invalid_names(self, name: str) -> None:
        with pytest.raises(ValueError, match="invalid corpus name"):
            validate_corpus_name(name)


class FakeOrchestration:
    """Lightweight stand-in returned by _create_orchestration."""

    def __init__(self) -> None:
        self.destroyed = False
        self.closed = False
        self.stats_call_count = 0

    def destroy_index(self) -> None:
        self.destroyed = True

    def close_storage(self) -> None:
        self.closed = True

    def corpus_stats(self) -> CorpusStats:
        self.stats_call_count += 1
        return CorpusStats(document_count=2, chunk_count=5)


class TestCorpusManager:
    """Tests for CorpusManager."""

    @pytest.fixture()
    def manager(self, tmp_path: Path) -> CorpusManager:
        mgr = CorpusManager(
            data_dir=tmp_path,
            index_config=FakeIndexConfig(),  # type: ignore[arg-type]
            search_config=FakeSearchConfig(),  # type: ignore[arg-type]
            embeddings=FakeEmbeddings(),  # type: ignore[arg-type]
            backend_factory=fake_backend_factory,  # type: ignore[arg-type]
            reranker=None,
        )
        return mgr

    def test_get_creates_and_caches(self, manager: CorpusManager) -> None:
        orch1 = manager.get("books")
        orch2 = manager.get("books")
        assert orch1 is orch2

    def test_get_different_corpora(self, manager: CorpusManager) -> None:
        orch_a = manager.get("alpha")
        orch_b = manager.get("beta")
        assert orch_a is not orch_b

    def test_get_validates_name(self, manager: CorpusManager) -> None:
        with pytest.raises(ValueError, match="invalid corpus name"):
            manager.get("123bad")

    def test_corpus_stats_loads_once_and_caches_until_destroy(self, manager: CorpusManager) -> None:
        """Corpus stats should be cached in-process and invalidated only when destroying the corpus."""
        stats_one = manager.corpus_stats("books")
        orch = manager.get("books")
        stats_two = manager.corpus_stats("books")

        assert stats_one == CorpusStats(document_count=2, chunk_count=5)
        assert stats_two == stats_one
        assert isinstance(orch, FakeOrchestration)
        assert orch.stats_call_count == 1

        manager.destroy("books")
        fresh = manager.get("books")
        stats_three = manager.corpus_stats("books")

        assert isinstance(fresh, FakeOrchestration)
        assert fresh.stats_call_count == 1
        assert stats_three == stats_one

    def test_destroy_evicts_cached(self, manager: CorpusManager) -> None:
        orch = manager.get("books")
        assert isinstance(orch, FakeOrchestration)
        manager.destroy("books")
        assert orch.destroyed
        assert orch.closed
        # Next get should create a fresh instance
        orch2 = manager.get("books")
        assert orch2 is not orch

    def test_destroy_uncached_corpus(self, manager: CorpusManager) -> None:
        """Destroying a corpus not in cache should still work."""
        manager.destroy("newcorpus")

    def test_destroy_rebuilds_incompatible_indexes_only_on_explicit_destroy(
        self, manager: CorpusManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        index_dir = tmp_path / "index" / "books"
        index_dir.mkdir(parents=True)
        old_index = index_dir / "old-index"
        old_index.write_text("incompatible")
        unrelated = tmp_path / "index" / "other"
        unrelated.mkdir()
        marker = unrelated / "keep"
        marker.write_text("untouched")
        description = description_path(tmp_path, "books")
        description.parent.mkdir(parents=True, exist_ok=True)
        description.write_text("Keep the corpus description")
        fresh = FakeOrchestration()

        def factory(**kwargs: object) -> FakeOrchestration:
            del kwargs
            if old_index.exists():
                raise IndexConfigurationError("rebuild required")
            return fresh

        monkeypatch.setattr(manager, "_backend_factory", factory)
        with pytest.raises(IndexConfigurationError):
            manager.get("books")
        assert old_index.exists()
        manager.destroy("books")
        assert fresh.destroyed and fresh.closed
        assert not old_index.exists()
        assert marker.read_text() == "untouched"
        assert description.read_text() == "Keep the corpus description"

    def test_destroy_does_not_remove_indexes_on_unrelated_errors(
        self, manager: CorpusManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        index_dir = tmp_path / "index" / "books"
        index_dir.mkdir(parents=True)
        marker = index_dir / "keep"
        marker.write_text("untouched")

        def factory(**kwargs: object) -> FakeOrchestration:
            del kwargs
            raise ValueError("invalid settings")

        monkeypatch.setattr(manager, "_backend_factory", factory)
        with pytest.raises(ValueError, match="invalid settings"):
            manager.destroy("books")
        assert marker.read_text() == "untouched"

    @pytest.mark.parametrize("setting", ["faiss", "tantivy"])
    def test_real_backends_can_reindex_after_configuration_change(self, tmp_path: Path, setting: str) -> None:
        config = Config.from_yaml(Path(__file__).parents[1] / "config.yaml.template")
        index_config = IndexConfig.model_validate(
            {**config.index.model_dump(), "embeddings": {**config.index.embeddings.model_dump(), "dimension": 2}}
        )

        def manager_for(settings: IndexConfig) -> CorpusManager:
            return CorpusManager(
                data_dir=tmp_path,
                index_config=settings,
                search_config=config.search,
                embeddings=FakeEmbeddings(),
                backend_factory=build_orchestration,
                reranker=None,
            )

        original = manager_for(index_config)
        original.get("books").index_document("running swiftly", None, "original.txt")
        original.close_all()
        if setting == "faiss":
            changed = IndexConfig.model_validate(
                {**index_config.model_dump(), "faiss": {**index_config.faiss.model_dump(), "index_type": "IVF2,Flat"}}
            )
        else:
            changed = IndexConfig.model_validate(
                {**index_config.model_dump(), "tantivy": {**index_config.tantivy.model_dump(), "stemming": False}}
            )
        updated = manager_for(changed)
        with pytest.raises(IndexConfigurationError):
            updated.get("books")
        updated.destroy("books")
        rebuilt = updated.get("books")
        try:
            assert rebuilt.corpus_stats() == CorpusStats(document_count=0, chunk_count=0)
            rebuilt.index_document("walking slowly", None, "replacement.txt")
            assert len(rebuilt.search_dense("walking", top_k=5)) == 1
            assert len(rebuilt.search_sparse("walking", top_k=5)) == 1
            assert rebuilt.search_sparse("running", top_k=5) == []
        finally:
            updated.close_all()

    @pytest.mark.parametrize("link_parent", [False, True])
    def test_incompatible_reset_refuses_symlinked_index_paths(
        self, manager: CorpusManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link_parent: bool
    ) -> None:
        target = tmp_path / "untouched"
        target.mkdir()
        marker = target / "keep"
        marker.write_text("untouched")
        index_root = tmp_path / "index"
        if link_parent:
            index_root.symlink_to(target, target_is_directory=True)
        else:
            index_root.mkdir()
            (index_root / "books").symlink_to(target, target_is_directory=True)

        def factory(**kwargs: object) -> FakeOrchestration:
            del kwargs
            raise IndexConfigurationError("rebuild required")

        monkeypatch.setattr(manager, "_backend_factory", factory)
        with pytest.raises(ValueError, match="symbolic link"):
            manager.destroy("books")
        assert marker.read_text() == "untouched"

    def test_destroy_validates_name(self, manager: CorpusManager) -> None:
        with pytest.raises(ValueError, match="invalid corpus name"):
            manager.destroy("123bad")

    def test_close_all(self, manager: CorpusManager) -> None:
        orch_a = manager.get("alpha")
        orch_b = manager.get("beta")
        assert isinstance(orch_a, FakeOrchestration)
        assert isinstance(orch_b, FakeOrchestration)
        manager.close_all()
        assert orch_a.closed
        assert orch_b.closed

    def test_thread_safety_returns_same_instance(self, manager: CorpusManager) -> None:
        results: list[object] = []

        def worker() -> None:
            results.append(manager.get("shared"))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert all(r is results[0] for r in results)

    def test_close_all_clears_cache_on_error(self, manager: CorpusManager) -> None:
        """close_all() should clear cache even when close_storage raises."""
        orch_a = manager.get("alpha")
        orch_b = manager.get("beta")
        assert isinstance(orch_a, FakeOrchestration)
        assert isinstance(orch_b, FakeOrchestration)

        # Make one close_storage raise
        def failing_close() -> None:
            raise RuntimeError("disk error")

        orch_a.close_storage = failing_close  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="failed to close storage for corpora: alpha"):
            manager.close_all()

        # Cache must still be cleared — next get() returns a fresh instance
        assert manager.get("alpha") is not orch_a
        # The non-failing one should still have been closed
        assert orch_b.closed

    def test_destroy_calls_close_even_on_destroy_error(self, manager: CorpusManager) -> None:
        """destroy() should call close_storage even when destroy_index raises."""
        orch = manager.get("books")
        assert isinstance(orch, FakeOrchestration)

        def failing_destroy() -> None:
            raise RuntimeError("destroy failed")

        orch.destroy_index = failing_destroy  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="destroy failed"):
            manager.destroy("books")

        assert orch.closed
        # Cache should no longer hold the old instance
        assert manager.get("books") is not orch

    def test_destroy_uncached_calls_cleanup(self, manager: CorpusManager) -> None:
        """destroy() on uncached corpus should still destroy and close."""
        manager.destroy("fresh")
        # No error means the code path succeeded (create → destroy → close)
        # get() after destroy should return a fresh instance
        orch = manager.get("fresh")
        assert isinstance(orch, FakeOrchestration)
        assert not orch.destroyed

    def test_destroy_preserves_destroy_and_close_errors(self, manager: CorpusManager) -> None:
        """destroy() should raise ExceptionGroup when destroy and close both fail."""
        orch = manager.get("books")
        assert isinstance(orch, FakeOrchestration)

        def failing_destroy() -> None:
            raise RuntimeError("destroy failed")

        def failing_close() -> None:
            raise RuntimeError("close failed")

        orch.destroy_index = failing_destroy  # type: ignore[assignment]
        orch.close_storage = failing_close  # type: ignore[assignment]

        with pytest.raises(ExceptionGroup) as exc_info:
            manager.destroy("books")

        messages = [str(err) for err in exc_info.value.exceptions]
        assert any("destroy failed" in message for message in messages)
        assert any("close failed" in message for message in messages)

    def test_list_corpora_returns_sorted_valid_names(self, manager: CorpusManager, tmp_path: Path) -> None:
        """list_corpora should return sorted valid corpus names on disk."""
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        (storage_dir / "beta").mkdir()
        (storage_dir / "alpha").mkdir()
        (storage_dir / "123bad").mkdir()
        (storage_dir / "has space").mkdir()
        (storage_dir / "link").symlink_to(storage_dir / "alpha")
        (storage_dir / "not_a_dir.txt").write_text("x", encoding="utf-8")

        assert manager.list_corpora() == ["alpha", "beta"]

    def test_corpus_exists_uses_valid_storage_dirs(self, manager: CorpusManager, tmp_path: Path) -> None:
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        (storage_dir / "books").mkdir()
        (storage_dir / "link").symlink_to(storage_dir / "books")

        assert manager.corpus_exists("books") is True
        assert manager.corpus_exists("missing") is False
        assert manager.corpus_exists("link") is False
        with pytest.raises(ValueError, match="invalid corpus name"):
            manager.corpus_exists("123bad")

    def test_corpus_description_requires_existing_corpus(self, manager: CorpusManager) -> None:
        with pytest.raises(FileNotFoundError, match="Corpus not found"):
            manager.corpus_description("books")

    def test_corpus_description_returns_placeholder_for_loaded_corpus(self, manager: CorpusManager, tmp_path: Path) -> None:
        (tmp_path / "storage" / "books").mkdir(parents=True)

        assert manager.corpus_description("books") == NO_DESCRIPTION_AVAILABLE

    def test_corpus_description_reflects_disk_without_cache(self, manager: CorpusManager, tmp_path: Path) -> None:
        (tmp_path / "storage" / "books").mkdir(parents=True)
        path = description_path(tmp_path, "books")
        path.write_text("one", encoding="utf-8")

        assert manager.corpus_description("books") == "one"

        path.write_text("two", encoding="utf-8")
        assert manager.corpus_description("books") == "two"

    def test_corpus_descriptions_returns_complete_map(self, manager: CorpusManager, tmp_path: Path) -> None:
        storage_dir = tmp_path / "storage"
        (storage_dir / "alpha").mkdir(parents=True)
        (storage_dir / "beta").mkdir()
        description_path(tmp_path, "beta").write_text("# Beta\n", encoding="utf-8")

        assert manager.corpus_descriptions(["alpha", "beta"]) == {
            "alpha": NO_DESCRIPTION_AVAILABLE,
            "beta": "# Beta\n",
        }

    def test_destroy_preserves_corpus_description(self, manager: CorpusManager, tmp_path: Path) -> None:
        (tmp_path / "storage" / "books").mkdir(parents=True)
        description_path(tmp_path, "books").write_text("# Books", encoding="utf-8")

        manager.destroy("books")

        assert manager.corpus_description("books") == "# Books"

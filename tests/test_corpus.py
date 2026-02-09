"""Unit tests for corpus name validation and CorpusManager."""

import threading
from pathlib import Path

import pytest

from minirag.corpus import CorpusManager, validate_corpus_name


class FakeIndexConfig:
    pass


class FakeSearchConfig:
    pass


class FakeEmbeddings:
    pass


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

    def destroy_index(self) -> None:
        self.destroyed = True

    def close_storage(self) -> None:
        self.closed = True


class TestCorpusManager:
    """Tests for CorpusManager."""

    @pytest.fixture()
    def manager(self, tmp_path: Path) -> CorpusManager:
        mgr = CorpusManager(
            data_dir=tmp_path,
            index_config=FakeIndexConfig(),  # type: ignore[arg-type]
            search_config=FakeSearchConfig(),  # type: ignore[arg-type]
            embeddings=FakeEmbeddings(),  # type: ignore[arg-type]
        )
        mgr._create_orchestration = lambda corpus: FakeOrchestration()  # type: ignore[assignment]
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

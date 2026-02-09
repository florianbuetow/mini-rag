"""Unit tests for corpus name validation and CorpusManager."""

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from minirag.corpus import CorpusManager, validate_corpus_name


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
            index_config=MagicMock(),
            search_config=MagicMock(),
            embeddings=MagicMock(),
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

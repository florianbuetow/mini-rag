"""Corpus manager for multi-corpus document collections."""

import logging
import re
import threading
from pathlib import Path
from typing import Protocol

from minirag.config import IndexConfig, SearchConfig
from minirag.orchestration import Orchestration
from minirag.reranking.interface import Reranker
from minirag.search.embeddings_interface import Embeddings
from minirag.storage.interface import CorpusStats

logger = logging.getLogger(__name__)

_CORPUS_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")


class OrchestrationFactory(Protocol):
    """Factory contract for creating corpus-scoped orchestration instances."""

    def __call__(
        self,
        *,
        corpus: str,
        data_dir: Path,
        index_config: IndexConfig,
        search_config: SearchConfig,
        embeddings: Embeddings,
        reranker: Reranker | None,
    ) -> Orchestration:
        """Create an orchestration instance for one corpus."""
        ...


def validate_corpus_name(name: str) -> str:
    """Validate a corpus name and return it if valid.

    Valid names must start with a letter and contain only letters, digits,
    underscores, or dashes (pattern: ``^[a-zA-Z][a-zA-Z0-9_-]*$``).

    Raises:
        ValueError: If the name does not match the required pattern.
    """
    if not _CORPUS_NAME_PATTERN.match(name):
        raise ValueError(f"invalid corpus name: {name!r} (must start with a letter, then alphanumeric, underscore, or dash)")
    return name


class CorpusManager:
    """Lazily creates and caches per-corpus Orchestration instances."""

    def __init__(
        self,
        data_dir: Path,
        index_config: IndexConfig,
        search_config: SearchConfig,
        embeddings: Embeddings,
        backend_factory: OrchestrationFactory,
        reranker: Reranker | None,
    ) -> None:
        self._data_dir = data_dir
        self._index_config = index_config
        self._search_config = search_config
        self._embeddings = embeddings
        self._backend_factory = backend_factory
        self._reranker = reranker
        self._cache: dict[str, Orchestration] = {}
        self._stats_cache: dict[str, CorpusStats] = {}
        self._lock = threading.Lock()

    def get(self, corpus: str) -> Orchestration:
        """Return the Orchestration for a corpus, creating it on first access."""
        validate_corpus_name(corpus)
        with self._lock:
            if corpus not in self._cache:
                self._cache[corpus] = self._create_orchestration(corpus)
            return self._cache[corpus]

    def destroy(self, corpus: str) -> None:
        """Clear a corpus's storage and index contents, then evict from cache."""
        validate_corpus_name(corpus)
        with self._lock:
            orch = self._cache.pop(corpus, None)
            self._stats_cache.pop(corpus, None)
            if orch is None:
                orch = self._create_orchestration(corpus)

        destroy_error: Exception | None = None
        try:
            orch.destroy_index()
        except Exception as exc:
            logger.exception("Failed to destroy index for corpus %r", corpus)
            destroy_error = exc

        close_error: Exception | None = None
        try:
            orch.close_storage()
        except Exception as exc:
            logger.exception("Failed to close storage while destroying corpus %r", corpus)
            close_error = exc

        if destroy_error is not None and close_error is not None:
            raise ExceptionGroup(
                f"failed to destroy and close corpus={corpus}",
                [destroy_error, close_error],
            ) from destroy_error
        if destroy_error is not None:
            raise destroy_error
        if close_error is not None:
            raise close_error

    def close_all(self) -> None:
        """Close all cached storage connections and clear the cache.

        Raises RuntimeError if any corpus fails to close, after attempting
        to close all remaining corpora.
        """
        with self._lock:
            items = list(self._cache.items())
            self._cache.clear()

        errors: list[tuple[str, Exception]] = []
        for name, orch in items:
            try:
                orch.close_storage()
            except Exception as exc:
                logger.error("Failed to close storage for corpus %r: %s", name, exc)
                errors.append((name, exc))

        if errors:
            names = ", ".join(n for n, _ in errors)
            raise RuntimeError(f"failed to close storage for corpora: {names}")

    def corpus_stats(self, corpus: str) -> CorpusStats:
        """Return cached aggregate corpus counts, loading them on first query."""
        validate_corpus_name(corpus)
        with self._lock:
            cached = self._stats_cache.get(corpus)
            if cached is not None:
                return cached
            orch = self._cache.get(corpus)
            if orch is None:
                orch = self._create_orchestration(corpus)
                self._cache[corpus] = orch
            stats = orch.corpus_stats()
            self._stats_cache[corpus] = stats
            return stats

    def corpus_exists(self, corpus: str) -> bool:
        """Return whether a valid corpus has storage on disk."""
        validate_corpus_name(corpus)
        storage_dir = self._data_dir / "storage" / corpus
        return storage_dir.is_dir() and not storage_dir.is_symlink()

    def list_corpora(self) -> list[str]:
        """Return sorted list of corpus names that have storage on disk."""
        storage_dir = self._data_dir / "storage"
        if not storage_dir.is_dir():
            return []
        return sorted(
            entry.name
            for entry in storage_dir.iterdir()
            if entry.is_dir() and not entry.is_symlink() and _CORPUS_NAME_PATTERN.match(entry.name)
        )

    def corpus_description(self, corpus: str) -> str:
        """Return the corpus description or the standard missing-description text."""
        if not self.corpus_exists(corpus):
            raise FileNotFoundError(f"Corpus not found: {corpus}")

        from minirag.corpus_description import read_corpus_description

        return read_corpus_description(self._data_dir, corpus)

    def corpus_descriptions(self, corpora: list[str] | None = None) -> dict[str, str]:
        """Return descriptions for the given corpora, or every loaded corpus."""
        from minirag.corpus_description import read_corpus_descriptions

        names = self.list_corpora() if corpora is None else corpora
        return read_corpus_descriptions(self._data_dir, names)

    def _create_orchestration(self, corpus: str) -> Orchestration:
        """Build backends for a corpus using the configured factory."""
        return self._backend_factory(
            corpus=corpus,
            data_dir=self._data_dir,
            index_config=self._index_config,
            search_config=self._search_config,
            embeddings=self._embeddings,
            reranker=self._reranker,
        )

"""Corpus manager for multi-corpus document collections."""

import logging
import re
import threading
from pathlib import Path

from minirag.config import IndexConfig, SearchConfig
from minirag.orchestration import Orchestration
from minirag.retrieval.faiss_dense import FAISSDense
from minirag.retrieval.tantivy_sparse import TantivySparse
from minirag.search.embeddings import FastTextEmbeddings
from minirag.storage.sqlite import SQLiteStorage

logger = logging.getLogger(__name__)

_CORPUS_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")


def validate_corpus_name(name: str) -> str:
    """Validate a corpus name and return it if valid.

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
        embeddings: FastTextEmbeddings,
    ) -> None:
        self._data_dir = data_dir
        self._index_config = index_config
        self._search_config = search_config
        self._embeddings = embeddings
        self._cache: dict[str, Orchestration] = {}
        self._lock = threading.Lock()

    def get(self, corpus: str) -> Orchestration:
        """Return the Orchestration for a corpus, creating it on first access."""
        validate_corpus_name(corpus)
        with self._lock:
            if corpus not in self._cache:
                self._cache[corpus] = self._create_orchestration(corpus)
            return self._cache[corpus]

    def destroy(self, corpus: str) -> None:
        """Destroy a corpus's backends on disk and evict from cache."""
        validate_corpus_name(corpus)
        with self._lock:
            orch = self._cache.get(corpus)
            if orch is None:
                orch = self._create_orchestration(corpus)
            try:
                orch.destroy_index()
            finally:
                try:
                    orch.close_storage()
                finally:
                    self._cache.pop(corpus, None)

    def close_all(self) -> None:
        """Close all cached storage connections."""
        with self._lock:
            errors: list[tuple[str, Exception]] = []
            try:
                for name, orch in self._cache.items():
                    try:
                        orch.close_storage()
                    except Exception as exc:
                        logger.error("Failed to close storage for corpus %r: %s", name, exc)
                        errors.append((name, exc))
            finally:
                self._cache.clear()
            if errors:
                names = ", ".join(n for n, _ in errors)
                raise RuntimeError(f"failed to close storage for corpora: {names}")

    def _create_orchestration(self, corpus: str) -> Orchestration:
        """Build backends at corpus-namespaced paths and return an Orchestration."""
        ic = self._index_config

        storage = SQLiteStorage(
            database_path=self._data_dir / "storage" / corpus / ic.storage.db_filename,
        )
        try:
            dense = FAISSDense(
                dimension=ic.embeddings.dimension,
                index_dir=self._data_dir / "index" / corpus / "faiss",
                nprobe=ic.faiss.nprobe,
            )
        except Exception:
            storage.close()
            raise
        try:
            sparse = TantivySparse(
                index_dir=self._data_dir / "index" / corpus / "tantivy",
                language=ic.tantivy.language,
                stemming=ic.tantivy.stemming,
            )
        except Exception:
            storage.close()
            raise

        logger.info("Created backends for corpus=%s", corpus)
        return Orchestration(
            chunking_config=ic.chunking,
            embeddings=self._embeddings,
            storage=storage,
            dense=dense,
            sparse=sparse,
            search_config=self._search_config,
        )

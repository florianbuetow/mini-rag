"""Backend composition helpers for per-corpus orchestration instances."""

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from minirag.config import IndexConfig, SearchConfig
from minirag.orchestration import Orchestration
from minirag.reranking.interface import Reranker
from minirag.retrieval.faiss_dense import FAISSDense
from minirag.retrieval.tantivy_sparse import TantivySparse
from minirag.search.embeddings_interface import Embeddings
from minirag.storage.sqlite import SQLiteStorage

logger = logging.getLogger(__name__)


@runtime_checkable
class SupportsClose(Protocol):
    """Protocol for backends that expose non-destructive close()."""

    def close(self) -> None:
        """Release resources without deleting persisted data."""
        ...


def _optional_close(resource: object, cleanup_errors: list[Exception], *, resource_name: str, corpus: str) -> None:
    """Close a resource when it exposes a callable close() hook."""
    if not isinstance(resource, SupportsClose):
        return
    try:
        resource.close()
    except Exception as cleanup_exc:
        logger.exception("Failed to close %s for corpus=%s", resource_name, corpus)
        cleanup_errors.append(cleanup_exc)


def build_orchestration(
    *,
    corpus: str,
    data_dir: Path,
    index_config: IndexConfig,
    search_config: SearchConfig,
    embeddings: Embeddings,
    reranker: Reranker | None,
) -> Orchestration:
    """Build an orchestration instance and perform cascading cleanup on init failures."""
    storage = SQLiteStorage(
        database_path=data_dir / "storage" / corpus / index_config.storage.db_filename,
    )
    try:
        dense = FAISSDense(
            dimension=index_config.embeddings.dimension,
            index_dir=data_dir / "index" / corpus / "faiss",
            nprobe=index_config.faiss.nprobe,
        )
    except Exception as exc:
        logger.exception("Failed to initialize FAISS backend for corpus=%s", corpus)
        cleanup_errors: list[Exception] = []
        _optional_close(
            resource=storage,
            cleanup_errors=cleanup_errors,
            resource_name="storage",
            corpus=corpus,
        )
        if len(cleanup_errors) > 0:
            raise ExceptionGroup(
                f"failed to initialize FAISS backend and cleanup for corpus={corpus}",
                [exc, *cleanup_errors],
            ) from exc
        raise
    try:
        sparse = TantivySparse(
            index_dir=data_dir / "index" / corpus / "tantivy",
            language=index_config.tantivy.language,
            stemming=index_config.tantivy.stemming,
        )
    except Exception as exc:
        logger.exception("Failed to initialize Tantivy backend for corpus=%s", corpus)
        sparse_cleanup_errors: list[Exception] = []
        _optional_close(
            resource=dense,
            cleanup_errors=sparse_cleanup_errors,
            resource_name="FAISS backend",
            corpus=corpus,
        )
        _optional_close(
            resource=storage,
            cleanup_errors=sparse_cleanup_errors,
            resource_name="storage",
            corpus=corpus,
        )
        if len(sparse_cleanup_errors) > 0:
            raise ExceptionGroup(
                f"failed to initialize Tantivy backend and cleanup for corpus={corpus}",
                [exc, *sparse_cleanup_errors],
            ) from exc
        raise

    logger.info("Created backends for corpus=%s", corpus)
    return Orchestration(
        chunking_config=index_config.chunking,
        embeddings=embeddings,
        storage=storage,
        dense=dense,
        sparse=sparse,
        search_config=search_config,
        reranker=reranker,
    )

"""Backend composition helpers for per-corpus orchestration instances."""

import logging
from pathlib import Path

from minirag.config import IndexConfig, SearchConfig
from minirag.orchestration import Orchestration
from minirag.retrieval.faiss_dense import FAISSDense
from minirag.retrieval.tantivy_sparse import TantivySparse
from minirag.search.embeddings_interface import Embeddings
from minirag.storage.sqlite import SQLiteStorage

logger = logging.getLogger(__name__)


def build_orchestration(
    *,
    corpus: str,
    data_dir: Path,
    index_config: IndexConfig,
    search_config: SearchConfig,
    embeddings: Embeddings,
) -> Orchestration:
    """Build an orchestration instance from concrete backend implementations."""
    storage = SQLiteStorage(
        database_path=data_dir / "storage" / corpus / index_config.storage.db_filename,
    )
    try:
        dense = FAISSDense(
            dimension=index_config.embeddings.dimension,
            index_dir=data_dir / "index" / corpus / "faiss",
            nprobe=index_config.faiss.nprobe,
        )
    except Exception:
        storage.close()
        raise
    try:
        sparse = TantivySparse(
            index_dir=data_dir / "index" / corpus / "tantivy",
            language=index_config.tantivy.language,
            stemming=index_config.tantivy.stemming,
        )
    except Exception:
        storage.close()
        raise

    logger.info("Created backends for corpus=%s", corpus)
    return Orchestration(
        chunking_config=index_config.chunking,
        embeddings=embeddings,
        storage=storage,
        dense=dense,
        sparse=sparse,
        search_config=search_config,
    )

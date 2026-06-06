"""Backfill the ingestion ledger for an already-indexed corpus without re-indexing.

For each input text file, derive its citation key (identical to the ingestion
pipeline) and check whether that citation already exists in the corpus index.
Files that are already indexed are recorded in the ledger; the rest are left for
the next ``just update``. This seeds the ledger for corpora that were indexed
before the ledger existed, so incremental updates can skip them.
"""

import argparse
import logging
from collections.abc import Callable
from pathlib import Path

from minirag.config import Config
from minirag.ingestion import ledger
from minirag.ingestion.citations import load_citation, resolve_input_dir
from minirag.storage.sqlite import SQLiteStorage

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure script logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def backfill(corpus: str, input_dir: Path, data_dir: Path, citation_exists: Callable[[str], bool]) -> tuple[int, int]:
    """Rebuild the ledger from the existing index, recording only already-indexed files.

    The ledger is cleared first, then every input file whose citation key already
    exists (per ``citation_exists``) is recorded. Returns a tuple of
    ``(recorded, not_indexed)`` counts.
    """
    ledger.clear(data_dir, corpus)

    text_files = sorted(
        [f for f in input_dir.rglob("*.txt") if not f.is_symlink() and not f.name.startswith("._")],
        key=lambda file_path: file_path.name,
    )
    logger.info("Found %d text file(s) in %s for corpus=%s", len(text_files), input_dir, corpus)

    recorded = 0
    not_indexed = 0
    for file_path in text_files:
        citation_key = str(load_citation(file_path, input_dir)["citation_key"])
        if citation_exists(citation_key):
            ledger.record_indexed(data_dir, corpus, file_path.relative_to(input_dir).as_posix())
            recorded += 1
        else:
            not_indexed += 1

    ledger.commit(data_dir, corpus)
    return (recorded, not_indexed)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Backfill the ingestion ledger from an existing index without re-indexing")
    parser.add_argument("--corpus", required=True, help="Name of the corpus to backfill")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in project root)")
    return parser.parse_args()


def main() -> None:
    """Load config, open the corpus index read path, and backfill the ledger."""
    configure_logging()
    args = parse_args()
    corpus: str = args.corpus

    project_root = Path(__file__).resolve().parent.parent
    config_path = Path(args.config).resolve() if args.config else project_root / "config.yaml"
    config = Config.from_yaml(config_path)
    data_dir = config.resolve_data_dir(project_root)
    input_dir = resolve_input_dir(data_dir, corpus)

    db_filename = config.get_index_config().storage.db_filename
    db_path = data_dir / "storage" / corpus / db_filename
    if not db_path.exists():
        raise SystemExit(f"no index database for corpus {corpus!r} at {db_path}; run 'just ingest {corpus}' first")

    storage = SQLiteStorage(database_path=db_path)
    try:
        recorded, not_indexed = backfill(corpus, input_dir, data_dir, lambda key: storage.get_citation(key) is not None)
    finally:
        storage.close()

    logger.info(
        "Backfill for corpus=%s: recorded %d already-indexed file(s); %d file(s) not yet indexed (run 'just update %s')",
        corpus,
        recorded,
        not_indexed,
        corpus,
    )


if __name__ == "__main__":
    main()

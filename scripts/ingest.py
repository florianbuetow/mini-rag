"""Ingest all text files from a corpus input directory into mini-rag."""

import argparse
import logging
from pathlib import Path

from minirag.clients.indexing import IndexingClient
from minirag.config import Config
from minirag.ingestion import ledger
from minirag.ingestion.citations import load_citation, resolve_input_dir

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure script logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def ingest_files(client: IndexingClient, corpus: str, input_dir: Path, data_dir: Path, *, incremental: bool = False) -> None:
    """Ingest .txt files in sorted order, recording each in the ingestion ledger.

    In full mode (``incremental=False``) the existing index and ledger are
    destroyed first and every file is re-indexed. In incremental mode
    (``incremental=True``) the index is left intact and files already recorded
    in the ledger are skipped, so only new documents are indexed.

    Fails immediately if any file fails to index. Files indexed before a failure
    stay recorded in the ledger log, so a re-run skips them rather than failing
    on the duplicate citation key.
    """
    text_files = sorted(
        [f for f in input_dir.rglob("*.txt") if not f.is_symlink() and not f.name.startswith("._")],
        key=lambda file_path: file_path.name,
    )

    logger.info("Found %d text file(s) in %s for corpus=%s", len(text_files), input_dir, corpus)

    if len(text_files) == 0:
        logger.warning("No .txt files found, nothing to ingest")
        return

    if incremental:
        already_indexed = ledger.load_indexed(data_dir, corpus)
        logger.info("Incremental update for corpus=%s: %d file(s) already indexed", corpus, len(already_indexed))
    else:
        logger.info("Destroying existing index and ledger for corpus=%s before ingestion", corpus)
        ledger.clear(data_dir, corpus)
        client.destroy_index(corpus)
        already_indexed: set[str] = set()

    total_chunks = 0
    indexed_count = 0
    skipped_empty = 0
    skipped_existing = 0
    num_files = len(text_files)
    for i, file_path in enumerate(text_files, start=1):
        relative_to_data = file_path.relative_to(data_dir)
        relative_to_input = file_path.relative_to(input_dir).as_posix()
        try:
            if relative_to_input in already_indexed:
                skipped_existing += 1
                logger.info("[%d/%d] Skipping %s (already indexed)", i, num_files, relative_to_input)
                continue
            file_size = file_path.stat().st_size
            file_text = file_path.read_text(encoding="utf-8")
            if not file_text.strip():
                skipped_empty += 1
                logger.warning("[%d/%d] Skipping %s (empty content)", i, num_files, relative_to_data)
                continue
            citation = load_citation(file_path, input_dir)
            _document_id, chunk_ids = client.index_document(corpus, file_text, citation=citation)
            ledger.record_indexed(data_dir, corpus, relative_to_input)
            indexed_count += 1
            total_chunks += len(chunk_ids)
            logger.info(
                "[%d/%d] Indexed %s (%d bytes, %d chunks) — %d indexed this run",
                i,
                num_files,
                relative_to_data,
                file_size,
                len(chunk_ids),
                indexed_count,
            )
        except Exception:
            logger.exception("[%d/%d] Failed to index %s", i, num_files, relative_to_data)
            raise

    ledger.commit(data_dir, corpus)
    logger.info(
        "Summary: %d indexed, %d skipped (empty), %d skipped (already indexed), %d chunk(s) total",
        indexed_count,
        skipped_empty,
        skipped_existing,
        total_chunks,
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Ingest text files into a mini-rag corpus")
    parser.add_argument("--corpus", required=True, help="Name of the corpus to ingest into")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in project root)")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Incremental mode: keep the existing index and only ingest files not already recorded in the ledger",
    )
    return parser.parse_args()


def main() -> None:
    """Load config and run ingestion."""
    configure_logging()
    args = parse_args()
    corpus: str = args.corpus

    project_root = Path(__file__).resolve().parent.parent
    config_path = Path(args.config).resolve() if args.config else project_root / "config.yaml"
    config = Config.from_yaml(config_path)
    data_dir = config.resolve_data_dir(project_root)
    input_dir = resolve_input_dir(data_dir, corpus)

    service_config = config.get_service_config()
    client = IndexingClient(host=service_config.host, port=service_config.port, http_client=None)

    ingest_files(client=client, corpus=corpus, input_dir=input_dir, data_dir=data_dir, incremental=args.update)
    logger.info("Ingestion completed for corpus=%s (mode=%s)", corpus, "update" if args.update else "full")


if __name__ == "__main__":
    main()

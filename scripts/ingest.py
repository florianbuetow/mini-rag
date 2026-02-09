"""Ingest all text files from a corpus input directory into mini-rag."""

import argparse
import logging
from pathlib import Path

from minirag.clients.indexing import IndexingClient
from minirag.config import Config

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure script logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def resolve_input_dir(data_dir: Path, corpus: str) -> Path:
    """Resolve and validate input text directory for a corpus."""
    input_dir = data_dir / "input" / corpus / "txt"
    if not input_dir.exists():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    if not input_dir.is_dir():
        raise ValueError(f"input path is not a directory: {input_dir}")

    return input_dir


def ingest_files(client: IndexingClient, corpus: str, input_dir: Path, data_dir: Path) -> None:
    """Destroy existing index and ingest all .txt files in sorted order.

    Fails immediately if any file fails to index.
    """
    text_files = sorted(
        [f for f in input_dir.rglob("*.txt") if not f.is_symlink() and not f.name.startswith("._")],
        key=lambda file_path: file_path.name,
    )

    logger.info("Found %d text file(s) in %s for corpus=%s", len(text_files), input_dir, corpus)

    if len(text_files) == 0:
        logger.warning("No .txt files found, nothing to ingest")
        return

    logger.info("Destroying existing index for corpus=%s before ingestion", corpus)
    client.destroy_index(corpus)

    total_chunks = 0
    indexed_count = 0
    skipped_count = 0
    num_files = len(text_files)
    for i, file_path in enumerate(text_files, start=1):
        relative_path = file_path.relative_to(data_dir)
        try:
            file_size = file_path.stat().st_size
            file_text = file_path.read_text(encoding="utf-8")
            if not file_text.strip():
                skipped_count += 1
                remaining = num_files - indexed_count - skipped_count
                logger.warning(
                    "[%d/%d] Skipping %s (empty content) — %d indexed, %d remaining", i, num_files, relative_path, indexed_count, remaining
                )
                continue
            _document_id, chunk_ids = client.index_document(corpus, file_text)
            indexed_count += 1
            total_chunks += len(chunk_ids)
            remaining = num_files - indexed_count - skipped_count
            logger.info(
                "[%d/%d] Indexed %s (%d bytes, %d chunks) — %d indexed, %d remaining",
                i,
                num_files,
                relative_path,
                file_size,
                len(chunk_ids),
                indexed_count,
                remaining,
            )
        except Exception:
            logger.exception("[%d/%d] Failed to index %s", i, num_files, relative_path)
            raise

    logger.info("Summary: %d file(s) indexed, %d skipped, %d chunk(s) total", indexed_count, skipped_count, total_chunks)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Ingest text files into a mini-rag corpus")
    parser.add_argument("--corpus", required=True, help="Name of the corpus to ingest into")
    return parser.parse_args()


def main() -> None:
    """Load config and run ingestion."""
    configure_logging()
    args = parse_args()
    corpus: str = args.corpus

    project_root = Path(__file__).resolve().parent.parent
    config = Config.from_yaml(project_root / "config.yaml")
    data_dir = config.resolve_data_dir(project_root)
    input_dir = resolve_input_dir(data_dir, corpus)

    service_config = config.get_service_config()
    client = IndexingClient(host=service_config.host, port=service_config.port)

    ingest_files(client=client, corpus=corpus, input_dir=input_dir, data_dir=data_dir)
    logger.info("Ingestion completed for corpus=%s", corpus)


if __name__ == "__main__":
    main()

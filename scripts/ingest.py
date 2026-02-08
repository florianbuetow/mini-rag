"""Ingest all text files from configured input directory into mini-rag."""

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


def resolve_input_dir(data_dir: Path) -> Path:
    """Resolve and validate input text directory."""
    input_dir = data_dir / "input" / "txt"
    if not input_dir.exists():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    if not input_dir.is_dir():
        raise ValueError(f"input path is not a directory: {input_dir}")

    return input_dir


def ingest_files(client: IndexingClient, input_dir: Path) -> None:
    """Destroy existing index and ingest all .txt files in sorted order."""
    text_files = sorted(
        [f for f in input_dir.rglob("*.txt") if not f.is_symlink()],
        key=lambda file_path: file_path.name,
    )

    logger.info("Found %d text file(s) in %s", len(text_files), input_dir)
    for file_path in text_files:
        logger.info("  - %s (%d bytes)", file_path.name, file_path.stat().st_size)

    if len(text_files) == 0:
        logger.warning("No .txt files found, nothing to ingest")
        return

    logger.info("Destroying existing index before ingestion")
    client.destroy_index()

    total_chunks = 0
    for i, file_path in enumerate(text_files, start=1):
        file_size = file_path.stat().st_size
        logger.info("[%d/%d] Sending %s (%d bytes)", i, len(text_files), file_path.name, file_size)
        file_text = file_path.read_text(encoding="utf-8")
        document_id, chunk_ids = client.index_document(file_text)
        total_chunks += len(chunk_ids)
        logger.info(
            "[%d/%d] Response: document_id=%s chunk_ids=%s",
            i,
            len(text_files),
            document_id,
            chunk_ids,
        )

    logger.info(
        "Summary: %d file(s) ingested, %d document(s) created, %d chunk(s) indexed",
        len(text_files),
        len(text_files),
        total_chunks,
    )


def main() -> None:
    """Load config and run fail-hard ingestion."""
    configure_logging()

    project_root = Path(__file__).resolve().parent.parent
    config = Config.from_yaml(project_root / "config.yaml")
    data_dir = config.resolve_data_dir(project_root)
    input_dir = resolve_input_dir(data_dir)

    service_config = config.get_service_config()
    client = IndexingClient(host=service_config.host, port=service_config.port)

    ingest_files(client=client, input_dir=input_dir)
    logger.info("Ingestion completed")


if __name__ == "__main__":
    main()

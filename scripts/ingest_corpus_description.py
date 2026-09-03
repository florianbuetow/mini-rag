"""Read or ingest a Markdown description for a mini-rag corpus."""

import argparse
import logging
from pathlib import Path

from minirag.config import Config
from minirag.corpus_description import (
    CorpusDescriptionError,
    ingest_corpus_description,
    read_corpus_description,
)

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure script logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Read or ingest a Markdown description for a mini-rag corpus")
    parser.add_argument("--corpus", required=True, help="Name of the loaded corpus to describe")
    parser.add_argument("--file", type=Path, help="Optional Markdown description file to ingest")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in project root)")
    return parser.parse_args()


def main() -> None:
    """Print the current description or replace it from a Markdown file."""
    configure_logging()
    args = parse_args()
    project_root = Path(__file__).resolve().parent.parent
    config_path = Path(args.config).resolve() if args.config else project_root / "config.yaml"
    config = Config.from_yaml(config_path)
    data_dir = config.resolve_data_dir(project_root)

    try:
        if args.file is None:
            description = read_corpus_description(data_dir, args.corpus)
            print(description, end="" if description.endswith("\n") else "\n")
            return
        target = ingest_corpus_description(data_dir, args.corpus, args.file)
    except (CorpusDescriptionError, FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        raise SystemExit(2) from exc

    logger.info("Stored description for corpus=%s at %s", args.corpus, target)


if __name__ == "__main__":
    main()

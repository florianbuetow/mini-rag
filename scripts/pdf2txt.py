"""Convert PDF files to plain-text UTF-8 files using LiteParse."""

import argparse
import logging
import shutil
import sys
from pathlib import Path

from liteparse import LiteParse

from minirag.config import Config

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Convert PDF files to plain text using LiteParse")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in project root)")
    return parser.parse_args()


def convert_file(parser: LiteParse, pdf_path: Path, txt_path: Path) -> None:
    """Convert a single PDF file to plain text UTF-8."""
    try:
        result = parser.parse(pdf_path, ocr_enabled=True)
        txt_path.write_text(result.text, encoding="utf-8")
    except Exception:
        logger.exception("Error converting %s", pdf_path.name)
        raise


def convert_corpus(parser: LiteParse, pdf_dir: Path, txt_dir: Path) -> int:
    """Convert all .pdf files in pdf_dir to .txt files in txt_dir. Returns count."""
    pdf_files = sorted(
        [f for f in pdf_dir.rglob("*.pdf") if not f.is_symlink() and not f.name.startswith("._")],
        key=lambda file_path: file_path.name,
    )
    if not pdf_files:
        return 0

    txt_dir.mkdir(parents=True, exist_ok=True)

    for pdf_file in pdf_files:
        relative = pdf_file.relative_to(pdf_dir)
        txt_relative = relative.with_suffix(".txt")
        txt_file = txt_dir / txt_relative

        txt_file.parent.mkdir(parents=True, exist_ok=True)

        convert_file(parser, pdf_file, txt_file)
        logger.info("  OK: %s -> %s", relative, txt_relative)

        json_source = pdf_file.with_suffix(".json")
        if json_source.exists():
            json_dest = txt_file.with_suffix(".json")
            json_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(json_source, json_dest)
            logger.info("  OK: %s -> %s (citation)", relative.with_suffix(".json"), txt_relative.with_suffix(".json"))

    return len(pdf_files)


def main() -> None:
    """Convert .pdf files to .txt for each corpus subfolder in data/input/."""
    args = parse_args()
    config_path = Path(args.config).resolve() if args.config else PROJECT_ROOT / "config.yaml"
    config = Config.from_yaml(config_path)
    input_base = config.resolve_data_dir(PROJECT_ROOT) / "input"

    if not input_base.is_dir():
        logger.error("Input directory does not exist: %s", input_base)
        sys.exit(1)

    corpus_dirs = sorted(d for d in input_base.iterdir() if d.is_dir() and not d.name.startswith("."))
    if not corpus_dirs:
        logger.info("No corpus subfolders found in %s", input_base)
        sys.exit(0)

    parser = LiteParse()
    total = 0
    for corpus_dir in corpus_dirs:
        pdf_dir = corpus_dir / "pdf"
        txt_dir = corpus_dir / "txt"
        if not pdf_dir.is_dir():
            logger.info("Skipping %s (no pdf/ subfolder)", corpus_dir.name)
            continue

        logger.info("[%s]", corpus_dir.name)
        count = convert_corpus(parser, pdf_dir, txt_dir)
        if count == 0:
            logger.info("  No .pdf files found")
        total += count
        logger.info("")

    logger.info("Done: %d files converted across %d corpora", total, len(corpus_dirs))


if __name__ == "__main__":
    main()

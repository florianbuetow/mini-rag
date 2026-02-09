"""Convert markdown files to plain-text UTF-8 files with Unicode escapes decoded."""

import argparse
import logging
import re
import sys
from pathlib import Path

from minirag.config import Config

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Convert markdown files to plain text")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in project root)")
    return parser.parse_args()


def decode_unicode_escapes(text: str) -> str:
    r"""Replace \\uXXXX and \\UXXXXXXXX escape sequences with actual Unicode characters."""
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"\\U([0-9a-fA-F]{8})", lambda m: chr(int(m.group(1), 16)), text)
    return text


def strip_markdown(text: str) -> str:
    """Strip common markdown formatting to produce plain text."""
    # Remove images: ![alt](url)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Convert links: [text](url) -> text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # Remove heading markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"___(.+?)___", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    # Remove inline code backticks
    text = re.sub(r"`([^`]*)`", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    # Remove unordered list markers
    text = re.sub(r"^(\s*)[-*+]\s+", r"\1", text, flags=re.MULTILINE)
    # Remove ordered list markers
    text = re.sub(r"^(\s*)\d+\.\s+", r"\1", text, flags=re.MULTILINE)
    return text


def convert_file(md_path: Path, txt_path: Path) -> None:
    """Convert a single markdown file to plain text UTF-8."""
    try:
        content = md_path.read_text(encoding="utf-8")
        content = strip_markdown(content)
        content = decode_unicode_escapes(content)
        txt_path.write_text(content, encoding="utf-8")
    except Exception:
        logger.exception("Error converting %s", md_path.name)
        raise


def convert_corpus(md_dir: Path, txt_dir: Path) -> int:
    """Convert all .md files in md_dir to .txt files in txt_dir. Returns count."""
    md_files = sorted(
        [f for f in md_dir.rglob("*.md") if not f.is_symlink() and not f.name.startswith("._")],
        key=lambda file_path: file_path.name,
    )
    if not md_files:
        return 0

    txt_dir.mkdir(parents=True, exist_ok=True)

    for md_file in md_files:
        relative = md_file.relative_to(md_dir)
        txt_relative = relative.with_suffix(".txt")
        txt_file = txt_dir / txt_relative

        txt_file.parent.mkdir(parents=True, exist_ok=True)

        convert_file(md_file, txt_file)
        logger.info("  OK: %s -> %s", relative, txt_relative)

    return len(md_files)


def main() -> None:
    """Convert .md files to .txt for each corpus subfolder in data/input/."""
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

    total = 0
    for corpus_dir in corpus_dirs:
        md_dir = corpus_dir / "md"
        txt_dir = corpus_dir / "txt"
        if not md_dir.is_dir():
            logger.info("Skipping %s (no md/ subfolder)", corpus_dir.name)
            continue

        logger.info("[%s]", corpus_dir.name)
        count = convert_corpus(md_dir, txt_dir)
        if count == 0:
            logger.info("  No .md files found")
        total += count
        logger.info("")

    logger.info("Done: %d files converted across %d corpora", total, len(corpus_dirs))


if __name__ == "__main__":
    main()

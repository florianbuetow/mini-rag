"""Convert markdown files to plain-text UTF-8 files with Unicode escapes decoded."""

import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = SCRIPT_DIR.parent / "data" / "input" / "md"
OUTPUT_DIR = SCRIPT_DIR.parent / "data" / "input" / "txt"


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


def main() -> None:
    """Convert all .md files in INPUT_DIR to .txt files in OUTPUT_DIR."""
    if not INPUT_DIR.is_dir():
        logger.error("Input directory does not exist: %s", INPUT_DIR)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    md_files = sorted(
        [f for f in INPUT_DIR.rglob("*.md") if not f.is_symlink()],
        key=lambda file_path: file_path.name,
    )
    if not md_files:
        logger.info("No .md files found in %s", INPUT_DIR)
        sys.exit(0)

    for md_file in md_files:
        relative = md_file.relative_to(INPUT_DIR)
        txt_relative = relative.with_suffix(".txt")
        txt_file = OUTPUT_DIR / txt_relative

        txt_file.parent.mkdir(parents=True, exist_ok=True)

        convert_file(md_file, txt_file)
        logger.info("  OK: %s -> %s", relative, txt_relative)

    logger.info("")
    logger.info("Done: %d converted", len(md_files))


if __name__ == "__main__":
    main()

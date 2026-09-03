"""Filesystem storage for corpus Markdown descriptions."""

import os
import tempfile
from pathlib import Path

from minirag.corpus import validate_corpus_name

DESCRIPTION_FILENAME = "description.md"
NO_DESCRIPTION_AVAILABLE = "No description available."
MAX_DESCRIPTION_BYTES = 64 * 1024


class CorpusDescriptionError(OSError):
    """Raised when corpus description storage cannot be read or written."""


class CorpusDescriptionNotFoundError(FileNotFoundError):
    """Raised when a description operation targets an unknown corpus."""


def description_path(data_dir: Path, corpus: str) -> Path:
    """Return the canonical Markdown description path for a corpus."""
    validated = validate_corpus_name(corpus)
    return data_dir / "storage" / validated / DESCRIPTION_FILENAME


def corpus_storage_dir(data_dir: Path, corpus: str) -> Path:
    """Return the canonical storage directory for a validated corpus."""
    validated = validate_corpus_name(corpus)
    return data_dir / "storage" / validated


def read_corpus_description(data_dir: Path, corpus: str) -> str:
    """Read a corpus description, or return the shared placeholder if absent."""
    storage_dir = corpus_storage_dir(data_dir, corpus)
    if not storage_dir.is_dir() or storage_dir.is_symlink():
        raise CorpusDescriptionNotFoundError(f"corpus not found: {corpus}")
    path = description_path(data_dir, corpus)
    if path.is_symlink():
        raise CorpusDescriptionError(f"corpus description path must not be a symlink: {path}")
    if not path.exists():
        return NO_DESCRIPTION_AVAILABLE
    if not path.is_file():
        raise CorpusDescriptionError(f"corpus description path is not a file: {path}")
    if path.stat().st_size > MAX_DESCRIPTION_BYTES:
        raise CorpusDescriptionError(f"corpus description exceeds {MAX_DESCRIPTION_BYTES} bytes: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusDescriptionError(f"failed to read corpus description: {path}") from exc
    if len(raw) > MAX_DESCRIPTION_BYTES:
        raise CorpusDescriptionError(f"corpus description exceeds {MAX_DESCRIPTION_BYTES} bytes: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusDescriptionError(f"corpus description must be valid UTF-8: {path}") from exc
    if not text.strip():
        raise CorpusDescriptionError(f"corpus description must not be empty or whitespace-only: {path}")
    return text


def read_corpus_descriptions(data_dir: Path, corpora: list[str]) -> dict[str, str]:
    """Read descriptions for the provided corpus names."""
    return {corpus: read_corpus_description(data_dir, corpus) for corpus in corpora}


def _read_valid_source(source_path: Path) -> str:
    """Read and validate a source Markdown file before replacing storage."""
    source = source_path.expanduser()
    if source.is_symlink():
        raise ValueError(f"description source must not be a symlink: {source}")
    if not source.is_file():
        raise ValueError(f"description source must be a regular file: {source}")
    if source.suffix.lower() != ".md":
        raise ValueError(f"description source must be a .md file: {source}")

    try:
        byte_count = source.stat().st_size
    except OSError as exc:
        raise ValueError(f"failed to stat description source: {source}") from exc
    if byte_count > MAX_DESCRIPTION_BYTES:
        raise ValueError(f"description source exceeds {MAX_DESCRIPTION_BYTES} bytes: {source}")

    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise ValueError(f"failed to read description source: {source}") from exc
    if len(raw) > MAX_DESCRIPTION_BYTES:
        raise ValueError(f"description source exceeds {MAX_DESCRIPTION_BYTES} bytes: {source}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"description source must be valid UTF-8: {source}") from exc
    if not text.strip():
        raise ValueError(f"description source must not be empty or whitespace-only: {source}")
    return text


def ingest_corpus_description(data_dir: Path, corpus: str, source_path: Path) -> Path:
    """Install a Markdown description for an existing corpus and return its path."""
    storage_dir = corpus_storage_dir(data_dir, corpus)
    if not storage_dir.is_dir() or storage_dir.is_symlink():
        raise CorpusDescriptionNotFoundError(f"corpus not found: {corpus}")

    text = _read_valid_source(source_path)
    target = description_path(data_dir, corpus)
    if target.is_symlink():
        raise CorpusDescriptionError(f"corpus description path must not be a symlink: {target}")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{DESCRIPTION_FILENAME}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(target)
    except OSError as exc:
        raise CorpusDescriptionError(f"failed to store corpus description: {target}") from exc
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    return target

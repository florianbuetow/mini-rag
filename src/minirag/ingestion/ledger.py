"""Per-corpus ingestion ledger tracking which input files are already indexed.

The ledger lets incremental ingestion (``just update``) skip documents that
have already been indexed, identified by their path relative to the corpus
``txt`` inbox. Two files are maintained under ``{data_dir}/storage/{corpus}/``:

- ``indexed.log`` — an append-only journal written during a run, one relative
  path per line, flushed immediately after each document is indexed. This is
  the crash-safe record: if a run aborts partway, the log still names every
  file that was successfully indexed.
- ``indexed.txt`` — the committed ledger, rewritten at the end of a run as the
  union of the previous ledger and the run's log, after which the log is
  cleared.

The effective "already indexed" set is the union of both files, so an
interrupted run never causes a document to be re-indexed (which would otherwise
fail on the duplicate citation key).

Neither file is touched by the service-side index destroy (which only clears
table rows and index contents), so callers must clear the ledger explicitly
whenever the index is wiped.
"""

import argparse
import logging
from pathlib import Path

from minirag.config import Config

logger = logging.getLogger(__name__)


def _corpus_storage_dir(data_dir: Path, corpus: str) -> Path:
    """Return the per-corpus storage directory holding the ledger files."""
    return data_dir / "storage" / corpus


def committed_path(data_dir: Path, corpus: str) -> Path:
    """Return the path to the committed ledger file for a corpus."""
    return _corpus_storage_dir(data_dir, corpus) / "indexed.txt"


def log_path(data_dir: Path, corpus: str) -> Path:
    """Return the path to the append-only ingestion log for a corpus."""
    return _corpus_storage_dir(data_dir, corpus) / "indexed.log"


def stop_file_paths(data_dir: Path, corpus: str) -> list[Path]:
    """Return the global and per-corpus poison-pill paths, in precedence order."""
    return [data_dir / "STOP", data_dir / "storage" / corpus / "STOP"]


def stop_requested(data_dir: Path, corpus: str) -> Path | None:
    """Return the first existing STOP file, or None."""
    return next((path for path in stop_file_paths(data_dir, corpus) if path.is_file()), None)


def _read_lines(path: Path) -> set[str]:
    """Return the set of non-empty, stripped lines in a file, or empty if absent."""
    if not path.exists():
        return set()
    return {stripped for line in path.read_text(encoding="utf-8").splitlines() if (stripped := line.strip())}


def load_indexed(data_dir: Path, corpus: str) -> set[str]:
    """Return the set of already-indexed relative paths for a corpus.

    The result is the union of the committed ledger and the append-only log, so
    a previously interrupted run does not cause re-indexing. An empty set means
    nothing has been indexed yet.
    """
    return _read_lines(committed_path(data_dir, corpus)) | _read_lines(log_path(data_dir, corpus))


def record_indexed(data_dir: Path, corpus: str, relative_path: str) -> None:
    """Append a successfully-indexed relative path to the corpus log."""
    log = log_path(data_dir, corpus)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"{relative_path}\n")


def commit(data_dir: Path, corpus: str) -> None:
    """Fold the append log into the committed ledger, then clear the log.

    Writes the ledger atomically (temp file + rename) as the union of the
    current ledger and log, then removes the log. The ledger is written before
    the log is cleared so the data stays durable across a crash: until the
    ledger is safely on disk, the log remains the source of truth.
    """
    storage_dir = _corpus_storage_dir(data_dir, corpus)
    storage_dir.mkdir(parents=True, exist_ok=True)
    indexed = load_indexed(data_dir, corpus)

    committed = committed_path(data_dir, corpus)
    temp = committed.parent / f"{committed.name}.tmp"
    temp.write_text("".join(f"{path}\n" for path in sorted(indexed)), encoding="utf-8")
    temp.replace(committed)

    log_path(data_dir, corpus).unlink(missing_ok=True)
    logger.info("Committed ledger for corpus=%s with %d indexed file(s)", corpus, len(indexed))


def clear(data_dir: Path, corpus: str) -> None:
    """Remove the committed ledger and append log for a corpus, if present."""
    committed_path(data_dir, corpus).unlink(missing_ok=True)
    log_path(data_dir, corpus).unlink(missing_ok=True)
    logger.info("Cleared ingestion ledger for corpus=%s", corpus)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for ledger maintenance."""
    parser = argparse.ArgumentParser(description="Manage a corpus ingestion ledger")
    parser.add_argument("--corpus", required=True, help="Name of the corpus whose ledger to manage")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in current directory)")
    parser.add_argument("--clear", action="store_true", help="Clear the committed ledger and append log for the corpus")
    return parser.parse_args()


def main() -> None:
    """CLI entry point for ledger maintenance (currently only ``--clear``)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = _parse_args()
    if not args.clear:
        raise SystemExit("no action requested; pass --clear")

    project_root = Path.cwd()
    config_path = Path(args.config).resolve() if args.config else project_root / "config.yaml"
    config = Config.from_yaml(config_path)
    data_dir = config.resolve_data_dir(project_root)
    clear(data_dir, args.corpus)


if __name__ == "__main__":
    main()

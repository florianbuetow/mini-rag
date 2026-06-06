"""Unit tests for the per-corpus ingestion ledger."""

from pathlib import Path

from minirag.ingestion import ledger

CORPUS = "testcorpus"


def test_load_indexed_empty_when_nothing_exists(tmp_path: Path) -> None:
    """load_indexed returns an empty set when no ledger files exist."""
    assert ledger.load_indexed(tmp_path, CORPUS) == set()


def test_committed_and_log_paths_live_under_storage(tmp_path: Path) -> None:
    """Ledger files live next to the SQLite DB under storage/{corpus}/."""
    assert ledger.committed_path(tmp_path, CORPUS) == tmp_path / "storage" / CORPUS / "indexed.txt"
    assert ledger.log_path(tmp_path, CORPUS) == tmp_path / "storage" / CORPUS / "indexed.log"


def test_record_indexed_creates_dir_and_appends(tmp_path: Path) -> None:
    """record_indexed creates the storage dir and appends to the log."""
    ledger.record_indexed(tmp_path, CORPUS, "a.txt")
    ledger.record_indexed(tmp_path, CORPUS, "sub/b.txt")

    assert ledger.log_path(tmp_path, CORPUS).exists()
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt", "sub/b.txt"}


def test_load_indexed_reads_committed_only(tmp_path: Path) -> None:
    """load_indexed reads paths from the committed ledger when no log exists."""
    committed = ledger.committed_path(tmp_path, CORPUS)
    committed.parent.mkdir(parents=True)
    committed.write_text("x.txt\ny.txt\n", encoding="utf-8")

    assert ledger.load_indexed(tmp_path, CORPUS) == {"x.txt", "y.txt"}


def test_load_indexed_unions_committed_and_log_and_ignores_blanks(tmp_path: Path) -> None:
    """load_indexed unions committed + log, dedupes, and ignores blank lines."""
    committed = ledger.committed_path(tmp_path, CORPUS)
    committed.parent.mkdir(parents=True)
    committed.write_text("a.txt\nb.txt\n\n", encoding="utf-8")
    ledger.log_path(tmp_path, CORPUS).write_text("b.txt\nc.txt\n  \n", encoding="utf-8")

    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt", "b.txt", "c.txt"}


def test_commit_folds_log_into_committed_and_clears_log(tmp_path: Path) -> None:
    """commit writes the union to the committed ledger and removes the log."""
    committed = ledger.committed_path(tmp_path, CORPUS)
    committed.parent.mkdir(parents=True)
    committed.write_text("a.txt\n", encoding="utf-8")
    ledger.record_indexed(tmp_path, CORPUS, "b.txt")

    ledger.commit(tmp_path, CORPUS)

    assert not ledger.log_path(tmp_path, CORPUS).exists()
    # Committed file is the sorted union, and no temp file is left behind.
    assert committed.read_text(encoding="utf-8") == "a.txt\nb.txt\n"
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt", "b.txt"}


def test_commit_with_no_log_is_safe(tmp_path: Path) -> None:
    """commit succeeds and is idempotent when there is no pending log."""
    ledger.record_indexed(tmp_path, CORPUS, "a.txt")
    ledger.commit(tmp_path, CORPUS)
    ledger.commit(tmp_path, CORPUS)

    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt"}


def test_clear_removes_both_files(tmp_path: Path) -> None:
    """clear removes the committed ledger and the log."""
    ledger.record_indexed(tmp_path, CORPUS, "a.txt")
    ledger.commit(tmp_path, CORPUS)
    ledger.record_indexed(tmp_path, CORPUS, "b.txt")

    ledger.clear(tmp_path, CORPUS)

    assert not ledger.committed_path(tmp_path, CORPUS).exists()
    assert not ledger.log_path(tmp_path, CORPUS).exists()
    assert ledger.load_indexed(tmp_path, CORPUS) == set()


def test_clear_is_safe_when_absent(tmp_path: Path) -> None:
    """clear does not raise when no ledger files exist."""
    ledger.clear(tmp_path, CORPUS)
    assert ledger.load_indexed(tmp_path, CORPUS) == set()

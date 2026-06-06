"""Unit tests for the ingestion ledger backfill."""

import json
from pathlib import Path

from minirag.ingestion import ledger
from scripts.backfill_ledger import backfill

CORPUS = "testcorpus"


def _make_input(data_dir: Path) -> Path:
    """Create and return the txt inbox for the test corpus."""
    input_dir = data_dir / "input" / CORPUS / "txt"
    input_dir.mkdir(parents=True)
    return input_dir


def test_backfill_records_only_already_indexed(tmp_path: Path) -> None:
    """Files whose citation key exists are recorded; others are left for update."""
    input_dir = _make_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    (input_dir / "b.txt").write_text("beta", encoding="utf-8")
    (input_dir / "c.txt").write_text("gamma", encoding="utf-8")

    # Auto citation keys are "a"/"b"/"c"; pretend a and b are already in the index.
    recorded, not_indexed = backfill(CORPUS, input_dir, tmp_path, lambda key: key in {"a", "b"})

    assert (recorded, not_indexed) == (2, 1)
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt", "b.txt"}


def test_backfill_uses_sidecar_citation_key(tmp_path: Path) -> None:
    """Backfill matches on the sidecar's citation key, not the filename."""
    input_dir = _make_input(tmp_path)
    (input_dir / "doc.txt").write_text("content", encoding="utf-8")
    citation: dict[str, object] = {"citation_key": "custom_key", "source_type": "blog", "common": {}, "source_data": {}}
    (input_dir / "doc.json").write_text(json.dumps(citation), encoding="utf-8")

    recorded, not_indexed = backfill(CORPUS, input_dir, tmp_path, lambda key: key == "custom_key")

    assert (recorded, not_indexed) == (1, 0)
    assert ledger.load_indexed(tmp_path, CORPUS) == {"doc.txt"}


def test_backfill_uses_subdirectory_relative_path(tmp_path: Path) -> None:
    """Recorded ledger entry is the inbox-relative path; key uses the same relative path."""
    input_dir = _make_input(tmp_path)
    sub = input_dir / "topic"
    sub.mkdir()
    (sub / "a.txt").write_text("alpha", encoding="utf-8")

    recorded, not_indexed = backfill(CORPUS, input_dir, tmp_path, lambda key: key == "topic/a")

    assert (recorded, not_indexed) == (1, 0)
    assert ledger.load_indexed(tmp_path, CORPUS) == {"topic/a.txt"}


def test_backfill_clears_stale_ledger_first(tmp_path: Path) -> None:
    """Backfill rebuilds from the index, dropping stale ledger entries."""
    input_dir = _make_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    ledger.record_indexed(tmp_path, CORPUS, "gone.txt")
    ledger.commit(tmp_path, CORPUS)

    backfill(CORPUS, input_dir, tmp_path, lambda key: key == "a")

    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt"}


def test_backfill_records_nothing_when_index_empty(tmp_path: Path) -> None:
    """When no citation exists, nothing is recorded and the ledger is empty."""
    input_dir = _make_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")

    recorded, not_indexed = backfill(CORPUS, input_dir, tmp_path, lambda key: False)

    assert (recorded, not_indexed) == (0, 1)
    assert ledger.load_indexed(tmp_path, CORPUS) == set()

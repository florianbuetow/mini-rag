"""Unit tests for the ingestion script."""

from pathlib import Path

import pytest

from scripts.ingest import ingest_files, resolve_input_dir


class FakeIndexingClient:
    """Fake IndexingClient tracking calls and optionally raising."""

    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.destroyed = False
        self.indexed: list[str] = []
        self._fail_on = fail_on or set()

    def destroy_index(self) -> None:
        self.destroyed = True

    def index_document(self, text: str) -> tuple[int, list[int]]:
        if text.strip() in self._fail_on:
            raise RuntimeError(f"simulated failure for: {text.strip()}")
        self.indexed.append(text)
        doc_id = len(self.indexed)
        return (doc_id, [doc_id * 10 + 1])


def test_resolve_input_dir_valid(tmp_path: Path) -> None:
    """resolve_input_dir should return path when directory exists."""
    input_dir = tmp_path / "input" / "txt"
    input_dir.mkdir(parents=True)

    result = resolve_input_dir(tmp_path)
    assert result == input_dir


def test_resolve_input_dir_missing_raises(tmp_path: Path) -> None:
    """resolve_input_dir should raise when directory is missing."""
    with pytest.raises(FileNotFoundError):
        resolve_input_dir(tmp_path)


def test_resolve_input_dir_not_a_directory(tmp_path: Path) -> None:
    """resolve_input_dir should raise when path is not a directory."""
    input_path = tmp_path / "input" / "txt"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("not a dir", encoding="utf-8")

    with pytest.raises(ValueError):
        resolve_input_dir(tmp_path)


def test_ingest_empty_directory(tmp_path: Path) -> None:
    """Empty directory should log warning and not destroy index."""
    client = FakeIndexingClient()
    ingest_files(client=client, input_dir=tmp_path, data_dir=tmp_path)  # type: ignore[arg-type]
    assert not client.destroyed
    assert client.indexed == []


def test_ingest_successful(tmp_path: Path) -> None:
    """All files should be ingested with correct counts."""
    (tmp_path / "a.txt").write_text("alpha content", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta content", encoding="utf-8")

    client = FakeIndexingClient()
    ingest_files(client=client, input_dir=tmp_path, data_dir=tmp_path)  # type: ignore[arg-type]

    assert client.destroyed
    assert len(client.indexed) == 2


def test_ingest_fails_fast_on_first_error(tmp_path: Path) -> None:
    """Failure should propagate immediately without processing remaining files."""
    (tmp_path / "a.txt").write_text("good", encoding="utf-8")
    (tmp_path / "b.txt").write_text("bad", encoding="utf-8")
    (tmp_path / "c.txt").write_text("also good", encoding="utf-8")

    client = FakeIndexingClient(fail_on={"bad"})

    with pytest.raises(RuntimeError, match="simulated failure for: bad"):
        ingest_files(client=client, input_dir=tmp_path, data_dir=tmp_path)  # type: ignore[arg-type]

    assert client.destroyed
    assert len(client.indexed) == 1  # only a.txt; c.txt was never reached


def test_ingest_skips_empty_files(tmp_path: Path) -> None:
    """Files with empty or whitespace-only content should be skipped."""
    (tmp_path / "a.txt").write_text("real content", encoding="utf-8")
    (tmp_path / "b.txt").write_text("", encoding="utf-8")
    (tmp_path / "c.txt").write_text("   \n\t  \n", encoding="utf-8")
    (tmp_path / "d.txt").write_text("also real", encoding="utf-8")

    client = FakeIndexingClient()
    ingest_files(client=client, input_dir=tmp_path, data_dir=tmp_path)  # type: ignore[arg-type]

    assert client.destroyed
    assert len(client.indexed) == 2

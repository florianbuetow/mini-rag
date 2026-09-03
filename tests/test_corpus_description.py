"""Tests for corpus Markdown description storage."""

import sys
from pathlib import Path

import pytest

from minirag.corpus_description import (
    MAX_DESCRIPTION_BYTES,
    NO_DESCRIPTION_AVAILABLE,
    CorpusDescriptionError,
    CorpusDescriptionNotFoundError,
    description_path,
    ingest_corpus_description,
    read_corpus_description,
)
from scripts import ingest_corpus_description as description_cli


def _make_corpus(data_dir: Path, corpus: str = "books") -> Path:
    storage_dir = data_dir / "storage" / corpus
    storage_dir.mkdir(parents=True)
    return storage_dir


def _source(tmp_path: Path, text: str, name: str = "description.md") -> Path:
    source = tmp_path / name
    source.write_text(text, encoding="utf-8")
    return source


def test_ingest_and_read_round_trip(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    text = "# Books\n\nReference notes.\n"

    target = ingest_corpus_description(tmp_path, "books", _source(tmp_path, text))

    assert target == description_path(tmp_path, "books")
    assert target.read_text(encoding="utf-8") == text
    assert read_corpus_description(tmp_path, "books") == text


def test_missing_description_returns_placeholder(tmp_path: Path) -> None:
    _make_corpus(tmp_path)

    assert read_corpus_description(tmp_path, "books") == NO_DESCRIPTION_AVAILABLE


def test_cli_without_file_prints_current_description(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "data"
    _make_corpus(data_dir)
    description_path(data_dir, "books").write_text("# Books\n\nReference notes.\n", encoding="utf-8")

    class FakeConfig:
        def resolve_data_dir(self, project_root: Path) -> Path:
            del project_root
            return data_dir

    monkeypatch.setattr(description_cli.Config, "from_yaml", staticmethod(lambda _path: FakeConfig()))
    monkeypatch.setattr(sys, "argv", ["describe-corpus", "--corpus", "books"])

    description_cli.main()

    assert capsys.readouterr().out == "# Books\n\nReference notes.\n"


def test_reingest_replaces_existing_description(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    ingest_corpus_description(tmp_path, "books", _source(tmp_path, "old", "old.md"))

    ingest_corpus_description(tmp_path, "books", _source(tmp_path, "new", "new.md"))

    assert read_corpus_description(tmp_path, "books") == "new"


@pytest.mark.parametrize("corpus", ["", "123bad", "has space", "a/b"])
def test_rejects_invalid_corpus_names(tmp_path: Path, corpus: str) -> None:
    source = _source(tmp_path, "valid")

    with pytest.raises(ValueError, match="invalid corpus name"):
        ingest_corpus_description(tmp_path, corpus, source)


def test_rejects_unknown_corpus(tmp_path: Path) -> None:
    source = _source(tmp_path, "valid")

    with pytest.raises(CorpusDescriptionNotFoundError, match="corpus not found"):
        ingest_corpus_description(tmp_path, "books", source)


@pytest.mark.parametrize(
    ("name", "text", "match"),
    [
        ("description.txt", "valid", r"\.md file"),
        ("empty.md", "   \n\t", "must not be empty"),
    ],
)
def test_validation_failures_preserve_existing_description(tmp_path: Path, name: str, text: str, match: str) -> None:
    _make_corpus(tmp_path)
    ingest_corpus_description(tmp_path, "books", _source(tmp_path, "old", "old.md"))

    with pytest.raises(ValueError, match=match):
        ingest_corpus_description(tmp_path, "books", _source(tmp_path, text, name))

    assert read_corpus_description(tmp_path, "books") == "old"


def test_rejects_directory_source_without_replacing_existing(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    ingest_corpus_description(tmp_path, "books", _source(tmp_path, "old"))
    directory = tmp_path / "description.md"
    directory.unlink()
    directory.mkdir()

    with pytest.raises(ValueError, match="regular file"):
        ingest_corpus_description(tmp_path, "books", directory)

    assert read_corpus_description(tmp_path, "books") == "old"


def test_rejects_symlink_source_without_replacing_existing(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    ingest_corpus_description(tmp_path, "books", _source(tmp_path, "old", "old.md"))
    real_source = _source(tmp_path, "new", "real.md")
    symlink = tmp_path / "link.md"
    symlink.symlink_to(real_source)

    with pytest.raises(ValueError, match="must not be a symlink"):
        ingest_corpus_description(tmp_path, "books", symlink)

    assert read_corpus_description(tmp_path, "books") == "old"


def test_rejects_oversized_source_without_replacing_existing(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    ingest_corpus_description(tmp_path, "books", _source(tmp_path, "old", "old.md"))
    oversized = tmp_path / "description.md"
    oversized.write_bytes(b"x" * (MAX_DESCRIPTION_BYTES + 1))

    with pytest.raises(ValueError, match="exceeds"):
        ingest_corpus_description(tmp_path, "books", oversized)

    assert read_corpus_description(tmp_path, "books") == "old"


def test_rejects_invalid_utf8_source_without_replacing_existing(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    ingest_corpus_description(tmp_path, "books", _source(tmp_path, "old", "old.md"))
    invalid = tmp_path / "description.md"
    invalid.write_bytes(b"\xff")

    with pytest.raises(ValueError, match="valid UTF-8"):
        ingest_corpus_description(tmp_path, "books", invalid)

    assert read_corpus_description(tmp_path, "books") == "old"


def test_rejects_unreadable_source_without_replacing_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_corpus(tmp_path)
    ingest_corpus_description(tmp_path, "books", _source(tmp_path, "old", "old.md"))
    source = _source(tmp_path, "new", "new.md")
    original_read_bytes = Path.read_bytes

    def fail_for_source(path: Path) -> bytes:
        if path == source:
            raise PermissionError("denied")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_for_source)

    with pytest.raises(ValueError, match="failed to read"):
        ingest_corpus_description(tmp_path, "books", source)

    assert description_path(tmp_path, "books").read_text(encoding="utf-8") == "old"


def test_read_rejects_stored_symlink(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    target = description_path(tmp_path, "books")
    target.symlink_to(_source(tmp_path, "# Outside\n", "outside.md"))

    with pytest.raises(CorpusDescriptionError, match="must not be a symlink"):
        read_corpus_description(tmp_path, "books")


def test_ingest_rejects_existing_target_symlink_without_following_it(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    outside = _source(tmp_path, "outside", "outside.md")
    target = description_path(tmp_path, "books")
    target.symlink_to(outside)

    with pytest.raises(CorpusDescriptionError, match="must not be a symlink"):
        ingest_corpus_description(tmp_path, "books", _source(tmp_path, "new", "new.md"))

    assert outside.read_text(encoding="utf-8") == "outside"


def test_ingest_rejects_broken_target_symlink(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    target = description_path(tmp_path, "books")
    target.symlink_to(tmp_path / "missing.md")

    with pytest.raises(CorpusDescriptionError, match="must not be a symlink"):
        ingest_corpus_description(tmp_path, "books", _source(tmp_path, "new", "new.md"))


def test_read_rejects_stored_whitespace_description(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    description_path(tmp_path, "books").write_text("  \n\t", encoding="utf-8")

    with pytest.raises(CorpusDescriptionError, match="must not be empty"):
        read_corpus_description(tmp_path, "books")


def test_read_rejects_invalid_utf8_description(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    description_path(tmp_path, "books").write_bytes(b"\xff")

    with pytest.raises(CorpusDescriptionError, match="valid UTF-8"):
        read_corpus_description(tmp_path, "books")


def test_read_rejects_oversized_description(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    description_path(tmp_path, "books").write_bytes(b"x" * (MAX_DESCRIPTION_BYTES + 1))

    with pytest.raises(CorpusDescriptionError, match="exceeds"):
        read_corpus_description(tmp_path, "books")


def test_rejects_storage_directory_symlink(tmp_path: Path) -> None:
    real_storage = tmp_path / "real-storage"
    real_storage.mkdir()
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "books").symlink_to(real_storage)

    with pytest.raises(CorpusDescriptionNotFoundError, match="corpus not found"):
        read_corpus_description(tmp_path, "books")

    with pytest.raises(CorpusDescriptionNotFoundError, match="corpus not found"):
        ingest_corpus_description(tmp_path, "books", _source(tmp_path, "new", "new.md"))

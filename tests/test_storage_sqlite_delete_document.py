"""Regression tests for SQLite per-document deletion."""

from pathlib import Path

import pytest

from minirag.storage.sqlite import SQLiteStorage


def _insert_document_with_chunks(storage: SQLiteStorage, citation_key: str) -> tuple[int, list[int]]:
    document_id = storage.insert_document_with_citation(
        content="alpha chunk\nbeta chunk",
        citation={
            "citation_key": citation_key,
            "source_type": "text_file",
            "common": {"title": citation_key},
            "source_data": {},
        },
        source_path=f"docs/{citation_key}.txt",
    )
    chunk_ids = [
        storage.insert_chunk(
            document_id=document_id,
            content="alpha chunk",
            chunk_index=0,
            char_start=0,
            char_end=11,
            line_from=1,
            line_to=1,
        ),
        storage.insert_chunk(
            document_id=document_id,
            content="beta chunk",
            chunk_index=1,
            char_start=12,
            char_end=22,
            line_from=2,
            line_to=2,
        ),
    ]
    return document_id, chunk_ids


def test_delete_document_returns_chunk_ids_and_removes_document_rows(tmp_path: Path) -> None:
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "delete.db")
    document_id, chunk_ids = _insert_document_with_chunks(storage, "delete-me")

    assert storage.delete_document(document_id) == chunk_ids

    with pytest.raises(ValueError, match="document not found"):
        storage.get_document(document_id)
    for chunk_id in chunk_ids:
        with pytest.raises(ValueError, match="chunk not found"):
            storage.get_chunk(chunk_id)
    assert storage.get_citation_key(document_id) is None
    assert storage.get_citation("delete-me") is None


def test_delete_document_unknown_id_returns_empty_list(tmp_path: Path) -> None:
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "unknown.db")

    assert storage.delete_document(999) == []


def test_delete_document_rejects_invalid_id(tmp_path: Path) -> None:
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "invalid.db")

    with pytest.raises(ValueError, match="document_id must be greater than 0"):
        storage.delete_document(0)


def test_delete_document_updates_corpus_stats(tmp_path: Path) -> None:
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "stats.db")
    deleted_document_id, _ = _insert_document_with_chunks(storage, "delete-me")
    retained_document_id, _ = _insert_document_with_chunks(storage, "keep-me")

    assert storage.corpus_stats() == (2, 4)

    storage.delete_document(deleted_document_id)

    assert storage.corpus_stats() == (1, 2)
    assert storage.get_document(retained_document_id) == "alpha chunk\nbeta chunk"


def test_get_document_id_round_trips_citation_key(tmp_path: Path) -> None:
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "citation.db")
    document_id, _ = _insert_document_with_chunks(storage, "round-trip")

    citation_key = storage.get_citation_key(document_id)

    assert citation_key == "round-trip"
    assert storage.get_document_id(citation_key) == document_id
    assert storage.get_document_id("absent") is None

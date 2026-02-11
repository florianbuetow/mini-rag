"""Unit tests for SQLite storage backend."""

import sqlite3
from pathlib import Path

import pytest

from minirag.storage.sqlite import SQLiteStorage


def test_sqlite_storage_crud_and_destroy(tmp_path: Path) -> None:
    """SQLite storage should insert, fetch, and destroy records."""
    database_path = tmp_path / "storage" / "test.db"
    storage = SQLiteStorage(database_path=database_path)

    document_id = storage.insert_document("hello world document")
    chunk_id = storage.insert_chunk(document_id=document_id, content="hello world")
    chunk_id_two = storage.insert_chunk(document_id=document_id, content="goodbye world")

    assert storage.get_document(document_id) == "hello world document"
    assert storage.get_chunk(chunk_id) == (document_id, "hello world")
    assert storage.list_chunks(document_id) == [
        (chunk_id, "hello world"),
        (chunk_id_two, "goodbye world"),
    ]

    storage.destroy()

    with pytest.raises(ValueError):
        storage.get_document(document_id)

    with pytest.raises(ValueError):
        storage.get_chunk(chunk_id)


def test_sqlite_storage_rejects_invalid_values(tmp_path: Path) -> None:
    """Storage should reject invalid IDs and empty text values."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "invalid.db")

    with pytest.raises(ValueError):
        storage.insert_document("  ")

    with pytest.raises(ValueError):
        storage.insert_chunk(document_id=0, content="chunk")

    with pytest.raises(ValueError):
        storage.insert_chunk(document_id=1, content="  ")

    with pytest.raises(ValueError):
        storage.get_document(0)

    with pytest.raises(ValueError):
        storage.get_chunk(0)

    with pytest.raises(ValueError):
        storage.list_chunks(0)


def test_sqlite_storage_list_chunks_returns_empty_for_missing_document(tmp_path: Path) -> None:
    """list_chunks should return empty list when document does not exist."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "missing.db")
    assert storage.list_chunks(999) == []


def test_sqlite_storage_list_chunks_isolated_by_document(tmp_path: Path) -> None:
    """list_chunks should only return chunks for the requested document ID."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "isolated.db")
    document_one = storage.insert_document("doc one")
    document_two = storage.insert_document("doc two")

    chunk_one = storage.insert_chunk(document_id=document_one, content="one-a")
    chunk_two = storage.insert_chunk(document_id=document_two, content="two-a")

    assert storage.list_chunks(document_one) == [(chunk_one, "one-a")]
    assert storage.list_chunks(document_two) == [(chunk_two, "two-a")]


def test_sqlite_storage_insert_and_get_citation(tmp_path: Path) -> None:
    """insert_citation should store and get_citation should retrieve citation data."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "citation.db")
    document_id = storage.insert_document("some document")

    citation_json = '{"citation_key": "smith2026", "source_type": "journal"}'
    storage.insert_citation(citation_key="smith2026", document_id=document_id, citation_json=citation_json)

    assert storage.get_citation_key(document_id) == "smith2026"
    assert storage.get_citation("smith2026") == citation_json


def test_sqlite_storage_get_citation_key_returns_none_for_missing(tmp_path: Path) -> None:
    """get_citation_key should return None when no citation exists for document."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "no_citation.db")
    assert storage.get_citation_key(999) is None


def test_sqlite_storage_get_citation_returns_none_for_missing(tmp_path: Path) -> None:
    """get_citation should return None when citation_key does not exist."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "no_citation2.db")
    assert storage.get_citation("nonexistent") is None


def test_sqlite_storage_insert_citation_rejects_invalid_values(tmp_path: Path) -> None:
    """insert_citation should reject empty keys, invalid IDs, and empty JSON."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "invalid_citation.db")

    with pytest.raises(ValueError, match="citation_key must not be empty"):
        storage.insert_citation(citation_key="", document_id=1, citation_json='{"k": "v"}')

    with pytest.raises(ValueError, match="citation_key must not be empty"):
        storage.insert_citation(citation_key="  ", document_id=1, citation_json='{"k": "v"}')

    with pytest.raises(ValueError, match="document_id must be greater than 0"):
        storage.insert_citation(citation_key="key", document_id=0, citation_json='{"k": "v"}')

    with pytest.raises(ValueError, match="citation_json must not be empty"):
        storage.insert_citation(citation_key="key", document_id=1, citation_json="")

    with pytest.raises(ValueError, match="citation_json must not be empty"):
        storage.insert_citation(citation_key="key", document_id=1, citation_json="  ")


def test_sqlite_storage_get_citation_key_rejects_invalid_id(tmp_path: Path) -> None:
    """get_citation_key should reject non-positive document_id."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "invalid_id.db")
    with pytest.raises(ValueError, match="document_id must be greater than 0"):
        storage.get_citation_key(0)


def test_sqlite_storage_get_citation_rejects_empty_key(tmp_path: Path) -> None:
    """get_citation should reject empty citation_key."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "empty_key.db")
    with pytest.raises(ValueError, match="citation_key must not be empty"):
        storage.get_citation("")


def test_sqlite_storage_duplicate_citation_key_raises(tmp_path: Path) -> None:
    """Inserting a duplicate citation_key should raise IntegrityError."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "dup_citation.db")
    doc1 = storage.insert_document("doc one")
    doc2 = storage.insert_document("doc two")

    storage.insert_citation(citation_key="same_key", document_id=doc1, citation_json='{"k": "v"}')

    with pytest.raises(sqlite3.IntegrityError):
        storage.insert_citation(citation_key="same_key", document_id=doc2, citation_json='{"k": "v2"}')


def test_sqlite_storage_destroy_clears_citations(tmp_path: Path) -> None:
    """destroy should clear citation records."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "destroy_citations.db")
    document_id = storage.insert_document("doc")
    storage.insert_citation(citation_key="key1", document_id=document_id, citation_json='{"k": "v"}')

    assert storage.get_citation("key1") is not None

    storage.destroy()

    assert storage.get_citation_key(document_id) is None
    assert storage.get_citation("key1") is None

"""Unit tests for SQLite storage backend."""

from pathlib import Path

import pytest

from minirag.storage.sqlite import SQLiteStorage


def test_sqlite_storage_crud_and_destroy(tmp_path: Path) -> None:
    """SQLite storage should insert, fetch, and destroy records."""
    database_path = tmp_path / "storage" / "test.db"
    storage = SQLiteStorage(database_path=database_path)

    document_id = storage.insert_document("hello world document")
    chunk_id = storage.insert_chunk(document_id=document_id, content="hello world")

    assert storage.get_document(document_id) == "hello world document"
    assert storage.get_chunk(chunk_id) == (document_id, "hello world")

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

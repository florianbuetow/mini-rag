"""Unit tests for SQLite storage backend."""

import sqlite3
from pathlib import Path

import pytest

from minirag.storage.interface import ChunkWithDocument
from minirag.storage.sqlite import SQLiteStorage


def test_sqlite_storage_crud_and_destroy(tmp_path: Path) -> None:
    """SQLite storage should insert, fetch, and destroy records."""
    database_path = tmp_path / "storage" / "test.db"
    storage = SQLiteStorage(database_path=database_path)

    document_id = storage.insert_document("hello world\ngoodbye world", source_path="docs/hello.txt")
    chunk_id = storage.insert_chunk(
        document_id=document_id,
        content="hello world",
        chunk_index=0,
        char_start=0,
        char_end=11,
        line_from=1,
        line_to=1,
    )
    chunk_id_two = storage.insert_chunk(
        document_id=document_id,
        content="goodbye world",
        chunk_index=1,
        char_start=12,
        char_end=25,
        line_from=2,
        line_to=2,
    )

    assert storage.get_document(document_id) == "hello world\ngoodbye world"
    assert storage.get_chunk(chunk_id) == ChunkWithDocument(
        document_id=document_id,
        content="hello world",
        source_path="docs/hello.txt",
        chunk_index=0,
        char_start=0,
        char_end=11,
        line_from=1,
        line_to=1,
    )
    assert storage.get_chunk(chunk_id_two).source_path == "docs/hello.txt"
    assert storage.get_chunk(chunk_id_two).chunk_index == 1
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
        storage.insert_document("  ", source_path="docs/a.txt")

    with pytest.raises(ValueError):
        storage.insert_document("content", source_path="  ")

    with pytest.raises(ValueError):
        storage.insert_chunk(document_id=0, content="chunk", chunk_index=0, char_start=0, char_end=5, line_from=1, line_to=1)

    with pytest.raises(ValueError):
        storage.insert_chunk(document_id=1, content="  ", chunk_index=0, char_start=0, char_end=5, line_from=1, line_to=1)

    with pytest.raises(ValueError):
        storage.get_document(0)

    with pytest.raises(ValueError):
        storage.get_chunk(0)

    with pytest.raises(ValueError):
        storage.list_chunks(0)


def test_sqlite_storage_insert_chunk_rejects_invalid_provenance(tmp_path: Path) -> None:
    """insert_chunk should reject inconsistent span, line, and ordinal values."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "invalid_prov.db")
    document_id = storage.insert_document("some content", source_path="docs/a.txt")

    with pytest.raises(ValueError, match="chunk_index"):
        storage.insert_chunk(document_id=document_id, content="c", chunk_index=-1, char_start=0, char_end=1, line_from=1, line_to=1)

    with pytest.raises(ValueError, match="char_start"):
        storage.insert_chunk(document_id=document_id, content="c", chunk_index=0, char_start=-1, char_end=1, line_from=1, line_to=1)

    with pytest.raises(ValueError, match="char_end"):
        storage.insert_chunk(document_id=document_id, content="c", chunk_index=0, char_start=5, char_end=5, line_from=1, line_to=1)

    with pytest.raises(ValueError, match="line_from"):
        storage.insert_chunk(document_id=document_id, content="c", chunk_index=0, char_start=0, char_end=1, line_from=0, line_to=1)

    with pytest.raises(ValueError, match="line_to"):
        storage.insert_chunk(document_id=document_id, content="c", chunk_index=0, char_start=0, char_end=1, line_from=3, line_to=2)


def test_sqlite_storage_list_chunks_returns_empty_for_missing_document(tmp_path: Path) -> None:
    """list_chunks should return empty list when document does not exist."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "missing.db")
    assert storage.list_chunks(999) == []


def test_sqlite_storage_list_chunks_isolated_by_document(tmp_path: Path) -> None:
    """list_chunks should only return chunks for the requested document ID."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "isolated.db")
    document_one = storage.insert_document("doc one", source_path="docs/one.txt")
    document_two = storage.insert_document("doc two", source_path="docs/two.txt")

    chunk_one = storage.insert_chunk(
        document_id=document_one, content="one-a", chunk_index=0, char_start=0, char_end=5, line_from=1, line_to=1
    )
    chunk_two = storage.insert_chunk(
        document_id=document_two, content="two-a", chunk_index=0, char_start=0, char_end=5, line_from=1, line_to=1
    )

    assert storage.list_chunks(document_one) == [(chunk_one, "one-a")]
    assert storage.list_chunks(document_two) == [(chunk_two, "two-a")]


def test_sqlite_storage_corpus_stats_tracks_documents_and_chunks(tmp_path: Path) -> None:
    """corpus_stats should read stored metadata maintained by SQLite triggers."""
    database_path = tmp_path / "storage" / "stats.db"
    storage = SQLiteStorage(database_path=database_path)
    document_one = storage.insert_document("doc one", source_path="docs/one.txt")
    document_two = storage.insert_document("doc two", source_path="docs/two.txt")
    storage.insert_chunk(document_id=document_one, content="one-a", chunk_index=0, char_start=0, char_end=5, line_from=1, line_to=1)
    storage.insert_chunk(document_id=document_one, content="one-b", chunk_index=1, char_start=6, char_end=11, line_from=1, line_to=1)
    storage.insert_chunk(document_id=document_two, content="two-a", chunk_index=0, char_start=0, char_end=5, line_from=1, line_to=1)

    assert storage.corpus_stats() == (2, 3)

    storage.close()
    reopened = SQLiteStorage(database_path=database_path)
    assert reopened.corpus_stats() == (2, 3)

    reopened.destroy()
    assert reopened.corpus_stats() == (0, 0)


def test_sqlite_storage_upgrades_legacy_schema_without_provenance(tmp_path: Path) -> None:
    """Opening a pre-provenance database should rebuild the schema with the new columns."""
    database_path = tmp_path / "storage" / "legacy.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_connection = sqlite3.connect(str(database_path))
    legacy_connection.execute("CREATE TABLE documents (document_id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL)")
    legacy_connection.execute(
        "CREATE TABLE chunks (chunk_id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL, content TEXT NOT NULL, "
        "FOREIGN KEY (document_id) REFERENCES documents(document_id))"
    )
    legacy_connection.execute("INSERT INTO documents(content) VALUES ('legacy doc')")
    legacy_connection.execute("INSERT INTO chunks(document_id, content) VALUES (1, 'legacy chunk')")
    legacy_connection.commit()
    legacy_connection.close()

    storage = SQLiteStorage(database_path=database_path)

    # Legacy rows are dropped with the legacy tables; the corpus requires re-ingestion.
    assert storage.corpus_stats() == (0, 0)
    document_id = storage.insert_document("fresh doc", source_path="docs/fresh.txt")
    chunk_id = storage.insert_chunk(
        document_id=document_id, content="fresh chunk", chunk_index=0, char_start=0, char_end=11, line_from=1, line_to=1
    )
    assert storage.get_chunk(chunk_id).source_path == "docs/fresh.txt"


def test_sqlite_storage_insert_and_get_citation(tmp_path: Path) -> None:
    """insert_citation should store and get_citation should retrieve citation data."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "citation.db")
    document_id = storage.insert_document("some document", source_path="docs/some.txt")

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
    doc1 = storage.insert_document("doc one", source_path="docs/one.txt")
    doc2 = storage.insert_document("doc two", source_path="docs/two.txt")

    storage.insert_citation(citation_key="same_key", document_id=doc1, citation_json='{"k": "v"}')

    with pytest.raises(sqlite3.IntegrityError):
        storage.insert_citation(citation_key="same_key", document_id=doc2, citation_json='{"k": "v2"}')


def test_sqlite_storage_destroy_clears_citations(tmp_path: Path) -> None:
    """destroy should clear citation records."""
    storage = SQLiteStorage(database_path=tmp_path / "storage" / "destroy_citations.db")
    document_id = storage.insert_document("doc", source_path="docs/doc.txt")
    storage.insert_citation(citation_key="key1", document_id=document_id, citation_json='{"k": "v"}')

    assert storage.get_citation("key1") is not None

    storage.destroy()

    assert storage.get_citation_key(document_id) is None
    assert storage.get_citation("key1") is None

"""SQLite storage implementation."""

import json
import logging
import sqlite3
import threading
from pathlib import Path

from minirag.storage.interface import ChunkRecord, ChunkWithDocument, CorpusStats, Storage

logger = logging.getLogger(__name__)


class SQLiteStorage(Storage):
    """SQLite-backed storage for documents and chunks."""

    def __init__(self, database_path: Path) -> None:
        """Create or open the SQLite database.

        Args:
            database_path: Path to the SQLite database file.
        """
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._database_path = database_path
        self._connection = sqlite3.connect(
            database=str(database_path),
            timeout=5.0,
            detect_types=0,
            isolation_level="DEFERRED",
            check_same_thread=False,
        )
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
        """Create required tables when missing."""
        with self._lock:
            cursor = self._connection.cursor()
            self._drop_legacy_tables_if_needed(cursor)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source_path TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    char_start INTEGER NOT NULL,
                    char_end INTEGER NOT NULL,
                    line_from INTEGER NOT NULL,
                    line_to INTEGER NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(document_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS document_citations (
                    citation_key TEXT PRIMARY KEY,
                    document_id INTEGER NOT NULL,
                    citation_json TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(document_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS corpus_stats (
                    table_name TEXT PRIMARY KEY,
                    row_count INTEGER NOT NULL CHECK(row_count >= 0)
                )
                """
            )
            self._initialize_corpus_stats(cursor)
            self._create_corpus_stats_triggers(cursor)
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_citations_document_id
                    ON document_citations(document_id)
                """
            )
            self._connection.commit()

    def _drop_legacy_tables_if_needed(self, cursor: sqlite3.Cursor) -> None:
        """Drop pre-provenance tables so the schema can be rebuilt.

        The database is a derived index rebuilt from the source text files, so a
        schema upgrade may discard rows; the corpus must be re-ingested afterwards.
        """
        chunks_missing_provenance = self._table_missing_column(cursor, table_name="chunks", column_name="char_start")
        documents_missing_source_path = self._table_missing_column(cursor, table_name="documents", column_name="source_path")
        legacy = chunks_missing_provenance
        if not legacy:
            legacy = documents_missing_source_path
        if not legacy:
            return

        logger.warning(
            "Legacy schema without chunk provenance detected at %s; dropping index tables — re-ingest required",
            self._database_path,
        )
        for table_name in ("document_citations", "chunks", "documents", "corpus_stats"):
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        self._connection.commit()

    def _table_missing_column(self, cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
        """Return True when the table exists but lacks the given column."""
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        if cursor.fetchone() is None:
            return False
        cursor.execute(f"PRAGMA table_info({table_name})")
        column_names = {row[1] for row in cursor.fetchall()}
        return column_name not in column_names

    def _initialize_corpus_stats(self, cursor: sqlite3.Cursor) -> None:
        """Initialize missing stats rows, backfilling only during schema setup."""
        cursor.execute(
            "SELECT COUNT(*) FROM corpus_stats WHERE table_name IN ('documents', 'chunks')",
        )
        row = cursor.fetchone()
        existing_stats_rows = _count_row_value(row, "corpus_stats")
        if existing_stats_rows == 2:
            return
        cursor.execute("DELETE FROM corpus_stats")
        cursor.execute(
            """
            INSERT INTO corpus_stats(table_name, row_count)
            VALUES
                ('documents', (SELECT COUNT(*) FROM documents)),
                ('chunks', (SELECT COUNT(*) FROM chunks))
            """
        )

    def _create_corpus_stats_triggers(self, cursor: sqlite3.Cursor) -> None:
        """Maintain corpus stats rows as documents and chunks change."""
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_documents_stats_insert
            AFTER INSERT ON documents
            BEGIN
                UPDATE corpus_stats
                SET row_count = row_count + 1
                WHERE table_name = 'documents';
            END
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_documents_stats_delete
            AFTER DELETE ON documents
            BEGIN
                UPDATE corpus_stats
                SET row_count = row_count - 1
                WHERE table_name = 'documents';
            END
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_chunks_stats_insert
            AFTER INSERT ON chunks
            BEGIN
                UPDATE corpus_stats
                SET row_count = row_count + 1
                WHERE table_name = 'chunks';
            END
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_chunks_stats_delete
            AFTER DELETE ON chunks
            BEGIN
                UPDATE corpus_stats
                SET row_count = row_count - 1
                WHERE table_name = 'chunks';
            END
            """
        )

    def insert_document_with_citation(self, content: str, citation: dict[str, object] | None, source_path: str) -> int:
        """Store a document, its citation, and its source path in one transaction."""
        if content.strip() == "":
            raise ValueError("document content must not be empty")

        if source_path.strip() == "":
            raise ValueError("source_path must not be empty")

        with self._lock:
            cursor = self._connection.cursor()
            try:
                cursor.execute("BEGIN")
                cursor.execute("INSERT INTO documents(content, source_path) VALUES (?, ?)", (content, source_path))
                row_id = cursor.lastrowid
                if row_id is None:
                    raise ValueError("failed to retrieve inserted document ID")
                document_id = int(row_id)

                if citation is None:
                    auto_citation = {
                        "citation_key": str(document_id),
                        "source_type": "text_file",
                        "common": {"title": str(document_id)},
                        "source_data": {},
                    }
                    citation_key = auto_citation["citation_key"]
                    citation_json = json.dumps(auto_citation)
                else:
                    citation_key_value = citation.get("citation_key")
                    if not isinstance(citation_key_value, str) or citation_key_value.strip() == "":
                        raise ValueError("citation must contain a non-empty 'citation_key'")
                    source_type = citation.get("source_type")
                    if not isinstance(source_type, str) or source_type.strip() == "":
                        raise ValueError("citation must contain a non-empty 'source_type'")
                    citation_key = citation_key_value
                    citation_json = json.dumps(citation)

                cursor.execute(
                    "INSERT INTO document_citations(citation_key, document_id, citation_json) VALUES (?, ?, ?)",
                    (citation_key, document_id, citation_json),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

        logger.debug("Inserted document with ID %s and citation key=%s", document_id, citation_key)
        return document_id

    def insert_document(self, content: str, source_path: str) -> int:
        """Store a document with its source path and return its generated ID."""
        if content.strip() == "":
            raise ValueError("document content must not be empty")

        if source_path.strip() == "":
            raise ValueError("source_path must not be empty")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("INSERT INTO documents(content, source_path) VALUES (?, ?)", (content, source_path))
            self._connection.commit()

            row_id = cursor.lastrowid
            if row_id is None:
                raise ValueError("failed to retrieve inserted document ID")

        logger.debug("Inserted document with ID %s", row_id)
        return int(row_id)

    def insert_chunk(
        self,
        document_id: int,
        content: str,
        chunk_index: int,
        char_start: int,
        char_end: int,
        line_from: int,
        line_to: int,
    ) -> int:
        """Store a chunk with its span provenance and return its generated ID."""
        if document_id <= 0:
            raise ValueError("document_id must be greater than 0")

        if content.strip() == "":
            raise ValueError("chunk content must not be empty")

        if chunk_index < 0:
            raise ValueError("chunk_index must be greater than or equal to 0")

        if char_start < 0:
            raise ValueError("char_start must be greater than or equal to 0")

        if char_end <= char_start:
            raise ValueError("char_end must be greater than char_start")

        if line_from < 1:
            raise ValueError("line_from must be greater than or equal to 1")

        if line_to < line_from:
            raise ValueError("line_to must be greater than or equal to line_from")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                INSERT INTO chunks(document_id, content, chunk_index, char_start, char_end, line_from, line_to)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (document_id, content, chunk_index, char_start, char_end, line_from, line_to),
            )
            self._connection.commit()

            row_id = cursor.lastrowid
            if row_id is None:
                raise ValueError("failed to retrieve inserted chunk ID")

        logger.debug("Inserted chunk with ID %s for document ID %s", row_id, document_id)
        return int(row_id)

    def insert_citation(self, citation_key: str, document_id: int, citation_json: str) -> None:
        """Store a citation record for a document."""
        if citation_key.strip() == "":
            raise ValueError("citation_key must not be empty")

        if document_id <= 0:
            raise ValueError("document_id must be greater than 0")

        if citation_json.strip() == "":
            raise ValueError("citation_json must not be empty")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                "INSERT INTO document_citations(citation_key, document_id, citation_json) VALUES (?, ?, ?)",
                (citation_key, document_id, citation_json),
            )
            self._connection.commit()

        logger.debug("Inserted citation key=%s for document_id=%s", citation_key, document_id)

    def delete_document(self, document_id: int) -> list[int]:
        """Delete a document, its chunks, and its citation. Return deleted chunk IDs."""
        if document_id <= 0:
            raise ValueError("document_id must be greater than 0")

        with self._lock:
            cursor = self._connection.cursor()
            try:
                cursor.execute("BEGIN")
                cursor.execute(
                    "SELECT chunk_id FROM chunks WHERE document_id = ? ORDER BY chunk_id",
                    (document_id,),
                )
                chunk_ids = [int(row[0]) for row in cursor.fetchall()]
                cursor.execute(
                    "DELETE FROM document_citations WHERE document_id = ?",
                    (document_id,),
                )
                cursor.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
                cursor.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

        logger.debug("Deleted document ID %s with %d chunks", document_id, len(chunk_ids))
        return chunk_ids

    def get_document(self, document_id: int) -> str:
        """Return document content by ID."""
        if document_id <= 0:
            raise ValueError("document_id must be greater than 0")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("SELECT content FROM documents WHERE document_id = ?", (document_id,))
            row = cursor.fetchone()

        if row is None:
            raise ValueError(f"document not found: {document_id}")

        content_value = row[0]
        if not isinstance(content_value, str):
            raise ValueError(f"document content is not text for ID: {document_id}")

        return content_value

    def get_chunk(self, chunk_id: int) -> ChunkWithDocument:
        """Return chunk content, owning document ID, and source provenance by chunk ID."""
        if chunk_id <= 0:
            raise ValueError("chunk_id must be greater than 0")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                SELECT chunks.document_id, chunks.content, documents.source_path,
                       chunks.chunk_index, chunks.char_start, chunks.char_end,
                       chunks.line_from, chunks.line_to
                FROM chunks
                JOIN documents ON documents.document_id = chunks.document_id
                WHERE chunks.chunk_id = ?
                """,
                (chunk_id,),
            )
            row = cursor.fetchone()

        if row is None:
            raise ValueError(f"chunk not found: {chunk_id}")

        document_id_value = row[0]
        content_value = row[1]
        source_path_value = row[2]
        int_values = row[3:8]

        if not isinstance(document_id_value, int):
            raise ValueError(f"chunk document_id is not int for chunk ID: {chunk_id}")

        if not isinstance(content_value, str):
            raise ValueError(f"chunk content is not text for chunk ID: {chunk_id}")

        if not isinstance(source_path_value, str):
            raise ValueError(f"document source_path is not text for chunk ID: {chunk_id}")

        for value in int_values:
            if not isinstance(value, int):
                raise ValueError(f"chunk provenance value is not int for chunk ID: {chunk_id}")

        return ChunkWithDocument(
            document_id=document_id_value,
            content=content_value,
            source_path=source_path_value,
            chunk_index=int_values[0],
            char_start=int_values[1],
            char_end=int_values[2],
            line_from=int_values[3],
            line_to=int_values[4],
        )

    def list_chunks(self, document_id: int) -> list[ChunkRecord]:
        """Return all chunk records for one document."""
        if document_id <= 0:
            raise ValueError("document_id must be greater than 0")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT chunk_id, content FROM chunks WHERE document_id = ? ORDER BY chunk_id",
                (document_id,),
            )
            rows = cursor.fetchall()

        chunks: list[ChunkRecord] = []
        for row in rows:
            chunk_id_value = row[0]
            content_value = row[1]
            if not isinstance(chunk_id_value, int):
                raise ValueError(f"chunk_id is not int for document ID: {document_id}")
            if not isinstance(content_value, str):
                raise ValueError(f"chunk content is not text for document ID: {document_id}")
            chunks.append(ChunkRecord(chunk_id=chunk_id_value, content=content_value))

        return chunks

    def corpus_stats(self) -> CorpusStats:
        """Return stored document and chunk counts without scanning corpus rows."""
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                SELECT table_name, row_count
                FROM corpus_stats
                WHERE table_name IN ('documents', 'chunks')
                """
            )
            rows = cursor.fetchall()

        counts = _corpus_stats_from_rows(rows)
        return CorpusStats(
            document_count=counts["documents"],
            chunk_count=counts["chunks"],
        )

    def get_citation_key(self, document_id: int) -> str | None:
        """Return the citation_key for a document, or None if not found."""
        if document_id <= 0:
            raise ValueError("document_id must be greater than 0")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT citation_key FROM document_citations WHERE document_id = ?",
                (document_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        citation_key_value = row[0]
        if not isinstance(citation_key_value, str):
            raise ValueError(f"citation_key is not text for document ID: {document_id}")

        return citation_key_value

    def get_citation(self, citation_key: str) -> str | None:
        """Return raw citation JSON string for a citation_key, or None if not found."""
        if citation_key.strip() == "":
            raise ValueError("citation_key must not be empty")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT citation_json FROM document_citations WHERE citation_key = ?",
                (citation_key,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        citation_json_value = row[0]
        if not isinstance(citation_json_value, str):
            raise ValueError(f"citation_json is not text for citation_key: {citation_key}")

        return citation_json_value

    def get_document_id(self, citation_key: str) -> int | None:
        """Return the document ID owning a citation_key, or None if not found."""
        if citation_key.strip() == "":
            raise ValueError("citation_key must not be empty")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT document_id FROM document_citations WHERE citation_key = ?",
                (citation_key,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        document_id_value = row[0]
        if not isinstance(document_id_value, int):
            raise ValueError(f"document_id is not int for citation_key: {citation_key}")

        return document_id_value

    def close(self) -> None:
        """Close the SQLite database connection."""
        with self._lock:
            self._connection.close()

    def destroy(self) -> None:
        """Delete all rows from documents, chunks, and citations."""
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("DELETE FROM document_citations")
            cursor.execute("DELETE FROM chunks")
            cursor.execute("DELETE FROM documents")
            self._connection.commit()
        logger.info("Destroyed SQLite storage contents at %s", self._database_path)


def _count_row_value(row: tuple[object, ...] | None, table_name: str) -> int:
    """Extract a non-negative SQLite count result."""
    if row is None:
        raise ValueError(f"failed to count rows in {table_name}")
    value = row[0]
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid row count for {table_name}: {value!r}")
    return value


def _corpus_stats_from_rows(rows: list[tuple[object, ...]]) -> dict[str, int]:
    """Convert stored stats rows into validated document and chunk counts."""
    counts: dict[str, int] = {}
    for row in rows:
        if len(row) != 2:
            raise ValueError(f"invalid corpus stats row: {row!r}")
        table_name = row[0]
        row_count = row[1]
        if not isinstance(table_name, str) or table_name not in {"documents", "chunks"}:
            raise ValueError(f"unexpected corpus stats table name: {table_name!r}")
        if not isinstance(row_count, int) or row_count < 0:
            raise ValueError(f"invalid corpus stats count for {table_name}: {row_count!r}")
        counts[table_name] = row_count
    if "documents" not in counts or "chunks" not in counts:
        raise ValueError("missing corpus stats rows")
    return counts

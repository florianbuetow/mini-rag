"""SQLite storage implementation."""

import logging
import sqlite3
import threading
from pathlib import Path

from minirag.storage.interface import Storage

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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(document_id)
                )
                """
            )
            self._connection.commit()

    def insert_document(self, content: str) -> int:
        """Store a document and return its generated ID."""
        if content.strip() == "":
            raise ValueError("document content must not be empty")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("INSERT INTO documents(content) VALUES (?)", (content,))
            self._connection.commit()

            row_id = cursor.lastrowid
            if row_id is None:
                raise ValueError("failed to retrieve inserted document ID")

        logger.debug("Inserted document with ID %s", row_id)
        return int(row_id)

    def insert_chunk(self, document_id: int, content: str) -> int:
        """Store a chunk and return its generated ID."""
        if document_id <= 0:
            raise ValueError("document_id must be greater than 0")

        if content.strip() == "":
            raise ValueError("chunk content must not be empty")

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(
                "INSERT INTO chunks(document_id, content) VALUES (?, ?)",
                (document_id, content),
            )
            self._connection.commit()

            row_id = cursor.lastrowid
            if row_id is None:
                raise ValueError("failed to retrieve inserted chunk ID")

        logger.debug("Inserted chunk with ID %s for document ID %s", row_id, document_id)
        return int(row_id)

    def get_document(self, document_id: int) -> str:
        """Return document content by ID."""
        if document_id <= 0:
            raise ValueError("document_id must be greater than 0")

        cursor = self._connection.cursor()
        cursor.execute("SELECT content FROM documents WHERE document_id = ?", (document_id,))
        row = cursor.fetchone()

        if row is None:
            raise ValueError(f"document not found: {document_id}")

        content_value = row[0]
        if not isinstance(content_value, str):
            raise ValueError(f"document content is not text for ID: {document_id}")

        return content_value

    def get_chunk(self, chunk_id: int) -> tuple[int, str]:
        """Return (document_id, chunk_content) by chunk ID."""
        if chunk_id <= 0:
            raise ValueError("chunk_id must be greater than 0")

        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT document_id, content FROM chunks WHERE chunk_id = ?",
            (chunk_id,),
        )
        row = cursor.fetchone()

        if row is None:
            raise ValueError(f"chunk not found: {chunk_id}")

        document_id_value = row[0]
        content_value = row[1]

        if not isinstance(document_id_value, int):
            raise ValueError(f"chunk document_id is not int for chunk ID: {chunk_id}")

        if not isinstance(content_value, str):
            raise ValueError(f"chunk content is not text for chunk ID: {chunk_id}")

        return (document_id_value, content_value)

    def close(self) -> None:
        """Close the SQLite database connection."""
        with self._lock:
            self._connection.close()

    def destroy(self) -> None:
        """Delete all rows from documents and chunks."""
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("DELETE FROM chunks")
            cursor.execute("DELETE FROM documents")
            self._connection.commit()
        logger.info("Destroyed SQLite storage contents at %s", self._database_path)

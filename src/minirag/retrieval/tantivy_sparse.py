"""Tantivy sparse retrieval implementation."""

import importlib
import logging
from pathlib import Path
from typing import Protocol, cast

from minirag.retrieval.sparse_interface import SparseRetrieval
from minirag.search.types import ScoredChunk

logger = logging.getLogger(__name__)


class TantivyDocument(Protocol):
    """Subset of Tantivy document methods used by this adapter."""

    def add_integer(self, field_name: str, value: int) -> None:
        """Add an integer field value."""
        ...

    def add_text(self, field_name: str, value: str) -> None:
        """Add a text field value."""
        ...

    def to_dict(self) -> dict[str, object]:
        """Return document values as dictionary."""
        ...


class TantivySearchResult(Protocol):
    """Subset of Tantivy search result fields used by this adapter."""

    hits: list[tuple[float, object]]


class TantivySearcher(Protocol):
    """Subset of Tantivy searcher methods used by this adapter."""

    num_docs: int

    def search(self, query: object, limit: int) -> TantivySearchResult:
        """Search query and return hits."""
        ...

    def doc(self, address: object) -> TantivyDocument:
        """Load a document by address."""
        ...


class TantivyIndexWriter(Protocol):
    """Subset of Tantivy writer methods used by this adapter."""

    def add_document(self, document: TantivyDocument) -> int:
        """Add one document to index."""
        ...

    def commit(self) -> int:
        """Commit pending index operations."""
        ...

    def wait_merging_threads(self) -> None:
        """Wait for merge threads to complete."""
        ...

    def delete_all_documents(self) -> int:
        """Delete all indexed documents."""
        ...

    def delete_documents_by_term(self, field_name: str, field_value: object) -> int:
        """Delete indexed documents containing one field term."""
        ...


class TantivyIndex(Protocol):
    """Subset of Tantivy index methods used by this adapter."""

    def writer(self, heap_size: int, num_threads: int) -> TantivyIndexWriter:
        """Create an index writer."""
        ...

    def parse_query(self, query: str, default_field_names: list[str]) -> object:
        """Parse a query string."""
        ...

    def searcher(self) -> TantivySearcher:
        """Return a searcher instance."""
        ...

    def reload(self) -> None:
        """Reload index readers."""
        ...


class TantivySchemaBuilder(Protocol):
    """Subset of Tantivy schema builder methods used by this adapter."""

    def add_integer_field(self, name: str, stored: bool, indexed: bool, fast: bool) -> object:
        """Add integer field to schema."""
        ...

    def add_text_field(self, name: str, stored: bool) -> object:
        """Add text field to schema."""
        ...

    def build(self) -> object:
        """Build schema instance."""
        ...


class TantivySchemaBuilderClass(Protocol):
    """Constructor for Tantivy schema builder objects."""

    def __call__(self) -> TantivySchemaBuilder:
        """Instantiate a schema builder."""
        ...


class TantivyDocumentClass(Protocol):
    """Constructor for Tantivy document objects."""

    def __call__(self) -> TantivyDocument:
        """Instantiate a document."""
        ...


class TantivyIndexClass(Protocol):
    """Subset of Tantivy Index class methods used by this adapter."""

    def __call__(self, schema: object, path: str, reuse: bool) -> TantivyIndex:
        """Instantiate a new index."""
        ...

    def exists(self, path: str) -> bool:
        """Check whether index exists."""
        ...

    def open(self, path: str) -> TantivyIndex:
        """Open existing index."""
        ...


class TantivySparse(SparseRetrieval):
    """Tantivy-backed sparse retrieval with BM25 score normalization."""

    def __init__(self, index_dir: Path, language: str, stemming: bool) -> None:
        """Initialize and load or create Tantivy index.

        Args:
            index_dir: Directory for Tantivy index persistence.
            language: Stored from config for future tokenizer customization (not yet used).
            stemming: Stored from config for future tokenizer customization (not yet used).
        """
        if language.strip() == "":
            raise ValueError("language must not be empty")

        self._index_dir = index_dir
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._language = language
        self._stemming = stemming

        self._tantivy_module = importlib.import_module("tantivy")
        self._index = self._open_or_create_index()
        self._writer: TantivyIndexWriter | None = None

        logger.info(
            "Initialized Tantivy sparse index at %s with language=%s stemming=%s",
            self._index_dir,
            self._language,
            self._stemming,
        )

    def _new_writer(self) -> TantivyIndexWriter:
        """Create a fresh Tantivy writer instance."""
        return self._index.writer(heap_size=50000000, num_threads=1)

    def _module_attribute(self, attribute_name: str) -> object:
        """Get a required attribute from tantivy module."""
        if not hasattr(self._tantivy_module, attribute_name):
            raise RuntimeError(f"tantivy.{attribute_name} is not available")
        return getattr(self._tantivy_module, attribute_name)

    def _open_or_create_index(self) -> TantivyIndex:
        """Open existing index, otherwise create a new one."""
        index_class = cast(TantivyIndexClass, self._module_attribute("Index"))
        index_path = str(self._index_dir)

        if index_class.exists(index_path):
            return index_class.open(index_path)

        schema_builder_class = self._module_attribute("SchemaBuilder")
        schema_builder_constructor = cast(TantivySchemaBuilderClass, schema_builder_class)
        schema_builder = schema_builder_constructor()

        schema_builder.add_integer_field("chunk_id", stored=True, indexed=True, fast=True)
        schema_builder.add_text_field("content", stored=True)
        schema = schema_builder.build()

        return index_class(schema, index_path, True)

    def _create_document(self, chunk_id: int, content: str) -> TantivyDocument:
        """Create a Tantivy document for one indexed chunk."""
        document_class = self._module_attribute("Document")
        document_constructor = cast(TantivyDocumentClass, document_class)
        document = document_constructor()
        document.add_integer("chunk_id", chunk_id)
        document.add_text("content", content)
        return document

    def index(self, chunk_id: int, content: str) -> None:
        """Index one chunk for sparse search."""
        if chunk_id <= 0:
            raise ValueError("chunk_id must be greater than 0")

        if content.strip() == "":
            raise ValueError("content must not be empty")

        document = self._create_document(chunk_id, content)
        if self._writer is None:
            self._writer = self._new_writer()
        self._writer.add_document(document)

    def remove_ids(self, chunk_ids: list[int]) -> None:
        """Remove indexed chunks by chunk ID."""
        if len(chunk_ids) == 0:
            return
        if self._writer is None:
            self._writer = self._new_writer()
        for chunk_id in chunk_ids:
            self._writer.delete_documents_by_term("chunk_id", chunk_id)

    def persist(self) -> None:
        """Commit pending writes and reload the index."""
        if self._writer is None:
            return
        self._writer.commit()
        self._writer.wait_merging_threads()
        self._writer = None
        self._index.reload()

    def _extract_chunk_id(self, document: TantivyDocument) -> int:
        """Extract chunk_id from a Tantivy document."""
        document_data = document.to_dict()

        if "chunk_id" not in document_data:
            raise ValueError("tantivy document missing chunk_id field")

        chunk_values_object = document_data["chunk_id"]
        if not isinstance(chunk_values_object, list):
            raise ValueError("tantivy chunk_id field is not a list")

        chunk_values = cast(list[object], chunk_values_object)
        if len(chunk_values) == 0:
            raise ValueError("tantivy chunk_id field is empty")

        chunk_id_value = chunk_values[0]
        if not isinstance(chunk_id_value, int):
            raise ValueError("tantivy chunk_id value is not an integer")

        return chunk_id_value

    def _normalize_score(self, raw_score: float, max_score: float) -> float:
        """Normalize a BM25 score to [0, 1]."""
        normalized_score = 0.0
        if max_score > 0.0:
            normalized_score = raw_score / max_score

        if normalized_score < 0.0:
            return 0.0

        if normalized_score > 1.0:
            return 1.0

        return normalized_score

    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        """Search lexical matches and normalize BM25 scores to [0, 1]."""
        if query.strip() == "":
            raise ValueError("query must not be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        searcher = self._index.searcher()
        if searcher.num_docs == 0:
            return []

        parsed_query = self._index.parse_query(query, ["content"])
        search_result = searcher.search(parsed_query, limit=top_k)

        hits = search_result.hits
        if len(hits) == 0:
            return []

        max_score = max(score for score, _ in hits)
        results: list[ScoredChunk] = []

        for raw_score, document_address in hits:
            document = searcher.doc(document_address)
            chunk_id_value = self._extract_chunk_id(document)
            normalized_score = self._normalize_score(raw_score, max_score)
            results.append(ScoredChunk(chunk_id=chunk_id_value, score=normalized_score))

        return results

    def destroy(self) -> None:
        """Remove all indexed sparse documents."""
        self._writer = None
        writer = self._new_writer()
        writer.delete_all_documents()
        writer.commit()
        writer.wait_merging_threads()
        self._index.reload()
        logger.info("Destroyed Tantivy index contents at %s", self._index_dir)

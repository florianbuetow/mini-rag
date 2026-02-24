# Document Citations — Design

**Date:** 2026-02-10
**Branch:** feature-metadata
**Status:** Approved

## 1. Overview & Terminology

**Feature name**: Document Citations

**Purpose**: Enable source attribution in RAG pipelines by associating citation metadata with every ingested document. Search results include a `citation_key` that consumers can use to retrieve full citation data for proper source attribution.

**Key terms**:
- **Citation**: A JSON record describing the source of a document (author, title, year, URL, etc.)
- **citation_key**: A unique string identifier for a citation (e.g., `"smith2026quantum"`). Follows BibTeX naming conventions. Present in every search result.
- **source_type**: Discriminator that determines the shape of type-specific citation fields (e.g., `"journal"`, `"youtube"`, `"blog"`, `"text_file"`)
- **Auto-generated citation**: A minimal citation record created at ingestion time when no `.json` file accompanies the document. Uses the filename as `citation_key` and `"text_file"` as `source_type`.

**What's in scope**: Document-level citation metadata, new API endpoint, search result enrichment with citation_key, citation storage in SQLite.

**What's out of scope**: Chunk-level location metadata (page numbers, section headings, timestamps). Future enhancement.

## 2. Citation JSON Schema

**File convention**: For a document `foo.md` (or `foo.txt`), the citation file is `foo.json` in the same directory. The `md2txt` pipeline copies `.json` files alongside converted `.txt` files.

**Structure**: Polymorphic nested JSON using a discriminated union pattern. The `source_type` field determines the shape of `source_data`.

```json
{
  "citation_key": "string (required, unique identifier)",
  "source_type": "string (required, discriminator)",
  "common": {
    "author": "string (optional)",
    "title": "string (optional)",
    "year": "integer (optional)",
    "month": "string (optional)",
    "day": "integer (optional)",
    "url": "string (optional)",
    "urldate": "string (optional, ISO date of access)",
    "note": "string (optional)"
  },
  "source_data": {
    "...fields vary by source_type..."
  }
}
```

**Required fields**: Only `citation_key` and `source_type`. Everything else is optional — different source types populate different fields.

**Supported source types and their `source_data` fields**:

| source_type | source_data fields |
|---|---|
| `journal` | journal_name, volume, issue, pages, doi |
| `book` | publisher, edition, isbn, chapter, pages |
| `youtube` | platform, channel, timestamp, duration, howpublished |
| `blog` / `engineering_blog` | blog_name, platform |
| `podcast` | podcast_name, episode, timestamp, duration |
| `conference` | conference_name, location, speaker |
| `arxiv` | arxiv_id, journal_name, journal, volume, pages, doi |
| `documentation` | project, version, section |
| `report` | organization, report_number |
| `text_file` | *(empty — auto-generated citations only)* |

**Auto-generated citation** (when no `.json` file exists):

```json
{
  "citation_key": "the_quantum_discovery",
  "source_type": "text_file",
  "common": {
    "title": "the_quantum_discovery.txt"
  },
  "source_data": {}
}
```

### Example: YouTube source

```json
{
  "citation_key": "husain2024hamel-6",
  "source_type": "youtube",
  "common": {
    "author": "Husain, Hamel",
    "title": "LLM Engineering in 2024",
    "year": 2024,
    "url": "https://www.youtube.com/watch?v=example",
    "urldate": "2026-02-10"
  },
  "source_data": {
    "platform": "YouTube",
    "channel": "Hamel Husain",
    "timestamp": "00:15:30",
    "howpublished": "YouTube video",
    "duration": "45:00"
  }
}
```

### Example: Journal source

```json
{
  "citation_key": "smith2026quantum",
  "source_type": "journal",
  "common": {
    "author": "Smith, John",
    "title": "Quantum Gradients",
    "year": 2026,
    "url": "https://doi.org/10.1000/123"
  },
  "source_data": {
    "journal_name": "Physical Review Letters",
    "volume": "102",
    "issue": "4",
    "pages": "115--120",
    "doi": "10.1000/123"
  }
}
```

## 3. Storage — SQLite Schema

**New table**: `document_citations` in the existing per-corpus SQLite database.

```sql
CREATE TABLE document_citations (
    citation_key  TEXT PRIMARY KEY,
    document_id   INTEGER NOT NULL,
    citation_json TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

CREATE INDEX idx_citations_document_id ON document_citations(document_id);
```

**Design decisions**:
- **`citation_key` is the primary key**: Each citation_key is unique within a corpus. Even when a book is split into chapters, each chapter gets its own citation_key with chapter-specific fields.
- **Index on `document_id`**: The `get_citation_key(document_id)` lookup is called during every search query, so it needs an index.
- **`citation_json`** stores the full citation JSON as text. No need to decompose into columns — the service parses it on read.
- **Foreign key** to `documents(document_id)` ensures referential integrity.
- **Destroyed with the index**: When `destroy_index()` is called, this table is dropped/cleared along with the other tables.
- **Corpus isolation**: Each corpus has its own SQLite database, so citation_keys are scoped per corpus with no cross-corpus collision.

**Storage interface additions**:

- `insert_citation(citation_key: str, document_id: int, citation_json: str) -> None` — stores a citation record.
- `get_citation_key(document_id: int) -> str | None` — returns the citation_key for a document. Used during search result construction.
- `get_citation(citation_key: str) -> str | None` — returns the raw citation JSON string. The orchestration layer parses it before returning to route handlers.

## 4. Search Result Changes

**SearchResult dataclass** gains two new fields:

```python
@dataclass
class SearchResult:
    chunk_id: int
    document_id: int       # NEW
    citation_key: str      # NEW
    text: str
    score: float
```

**QueryResult API model** (Pydantic) mirrors this:

```python
class QueryResult(BaseModel):
    chunk_id: int
    document_id: int       # NEW
    citation_key: str      # NEW
    text: str
    score: float
```

**Resolution flow in the orchestration layer** (for all three search modes: dense, sparse, hybrid):

1. Retrieval returns `list[ScoredChunk(chunk_id, score)]` — unchanged
2. For each chunk_id, call `storage.get_chunk(chunk_id)` -> `(document_id, text)` — unchanged
3. For each unique document_id, call `get_citation_key(document_id)` -> `citation_key` — **new step, LRU cached**
4. Build `SearchResult(chunk_id, document_id, citation_key, text, score)`

**API response example** (applies to all three search endpoints):

```json
{
  "status": 200,
  "data": {
    "results": [
      {
        "chunk_id": 42,
        "document_id": 3,
        "citation_key": "smith2026quantum",
        "text": "matched chunk text...",
        "score": 0.87
      },
      {
        "chunk_id": 58,
        "document_id": 3,
        "citation_key": "smith2026quantum",
        "text": "another chunk from same doc...",
        "score": 0.74
      },
      {
        "chunk_id": 15,
        "document_id": 7,
        "citation_key": "husain2024hamel-6",
        "text": "chunk from different doc...",
        "score": 0.69
      }
    ]
  }
}
```

## 5. Citation API Endpoint

**New endpoint**: `GET /v1/corpus/{corpus}/citation/{citation_key}`

Returns the full citation data for a given citation_key within a corpus.

**Request**: No body. The citation_key is in the URL path.

**Success response**:

```json
{
  "status": 200,
  "data": {
    "citation_key": "smith2026quantum",
    "source_type": "journal",
    "common": {
      "author": "Smith, John",
      "title": "Quantum Gradients",
      "year": 2026,
      "url": "https://doi.org/10.1000/123"
    },
    "source_data": {
      "journal_name": "Physical Review Letters",
      "volume": "102",
      "issue": "4",
      "pages": "115--120",
      "doi": "10.1000/123"
    }
  }
}
```

**Not found response**:

```json
{
  "status": 404,
  "error": "citation not found: smith2026quantum"
}
```

**Design notes**:
- Guarded by `ensure_healthy()`, consistent with all other data endpoints.
- Lives in a new route file: `api/routes_citation.py`.

**Pydantic response model** in `api/models/citation.py`:

```python
class CitationResponse(BaseModel):
    citation_key: str
    source_type: str
    common: dict
    source_data: dict
```

## 6. Ingestion Pipeline Changes

**Current flow**: Read `.txt` file -> POST document text to service -> service stores, chunks, embeds, indexes.

**New flow**: Read `.txt` file -> check for matching `.json` file -> POST document text + citation to service -> service stores, chunks, embeds, indexes -> store citation record.

**Changes to `scripts/ingest.py`**:

For each `.txt` file being ingested:
1. Check if a `.json` file with the same base name exists in the same directory (e.g., `foo.txt` -> `foo.json`).
2. If found, read and parse the JSON. Validate that `citation_key` and `source_type` are present. Fail fast if malformed.
3. If not found, auto-generate a minimal citation:
   ```json
   {
     "citation_key": "foo",
     "source_type": "text_file",
     "common": { "title": "foo.txt" },
     "source_data": {}
   }
   ```
4. Send the citation data alongside the document text to the service.

**Changes to the index endpoint** (`POST /v1/corpus/{corpus}/index`):

The request body gains an optional `citation` field:

```json
{
  "document": "full text content...",
  "citation": {
    "citation_key": "smith2026quantum",
    "source_type": "journal",
    "common": { "..." },
    "source_data": { "..." }
  }
}
```

The ingestion script always provides `citation` (either from the `.json` file or auto-generated). The field is optional at the API level — if omitted, the service auto-generates one using the document_id as the citation_key (fallback for direct API callers who don't use the ingestion script).

**Changes to the orchestration layer** (`orchestration.py`):

`index_document(text, citation)` gains the citation parameter. After storing the document (and before chunking):
1. Call `storage.insert_citation(citation_key, document_id, citation_json)`.
2. If a duplicate `citation_key` is detected (UNIQUE constraint violation), fail fast with a descriptive error.

**Changes to `scripts/md2txt.py`**:

When converting `.md` files to `.txt`, also copy any matching `.json` files from the source directory to the target directory, preserving the relative path structure.

## 7. MCP Server Changes

**Existing tool**: `search` — performs hybrid search, returns results as-is from the REST API. All three search endpoints now include `document_id` and `citation_key` in every chunk result. The MCP search tool passes this through unchanged.

**New tool**: `get_citation` — retrieves citation data by citation_key.

```typescript
{
  name: "get_citation",
  description: "Get citation/source metadata for a document by its citation key",
  inputSchema: {
    type: "object",
    properties: {
      corpus: { type: "string", description: "Name of the corpus" },
      citation_key: { type: "string", description: "Citation key from search results" }
    },
    required: ["corpus", "citation_key"]
  }
}
```

**Behavior**:
1. Health check (same as the search tool — 3-second timeout, return "Search system is currently offline" if unreachable).
2. Call `GET /v1/corpus/{corpus}/citation/{citation_key}`.
3. Return the citation JSON as formatted text.
4. If 404, return a clear message: "No citation found for key: {citation_key}".

**Typical LLM workflow**:
1. Call `search` tool -> get results with `citation_key` per chunk
2. Identify unique `citation_key` values of interest
3. Call `get_citation` for each -> get full source metadata
4. Use citation data to attribute sources in the generated answer

## 8. Caching Strategy

**Problem**: Every search query now needs to resolve `document_id -> citation_key` for each result chunk. Without caching, this adds one SQLite query per unique document_id per search request.

**Solution**: Explicit LRU cache in the orchestration layer (max 1024 entries).

```python
_CITATION_KEY_CACHE_MAX = 1024
self._citation_key_cache: OrderedDict[int, str] = OrderedDict()

def _get_citation_key_for_document(self, document_id: int) -> str:
    cached = self._citation_key_cache.get(document_id)
    if cached is not None:
        self._citation_key_cache.move_to_end(document_id)
        return cached
    citation_key = self._storage.get_citation_key(document_id)
    if citation_key is not None:
        self._citation_key_cache[document_id] = citation_key
        self._citation_key_cache.move_to_end(document_id)
        if len(self._citation_key_cache) > _CITATION_KEY_CACHE_MAX:
            self._citation_key_cache.popitem(last=False)
        return citation_key
    raise RuntimeError("missing citation")
```

**Why this works well**:
- `top_k` is typically 5-10, so at most 10 unique document_ids per query
- After a few queries, most document_ids are warm in cache — nearly all hits
- 1024 entries covers corpora with hundreds of documents without eviction pressure

**Cache invalidation**: When `destroy_index()` is called, clear the cache. This is the only mutation that removes citations.

## 9. File Change Summary

### New files
- `src/minirag/api/models/citation.py` — `CitationResponse` Pydantic model
- `src/minirag/api/routes_citation.py` — `GET /v1/corpus/{corpus}/citation/{citation_key}` route

### Modified files

| File | Change |
|---|---|
| `src/minirag/search/types.py` | Add `document_id: int` and `citation_key: str` to `SearchResult` |
| `src/minirag/search/hybrid.py` | Carry `document_id` and `citation_key` through merge |
| `src/minirag/api/models/query.py` | Add `document_id` and `citation_key` to `QueryResult` |
| `src/minirag/api/models/index.py` | Add optional `citation` field to `IndexRequest` |
| `src/minirag/api/routes_query.py` | Update `_build_query_response()` to include new fields |
| `src/minirag/api/routes_index.py` | Pass citation data through to orchestration |
| `src/minirag/api/app.py` | Register citation route |
| `src/minirag/storage/interface.py` | Add citation storage methods |
| `src/minirag/storage/sqlite.py` | Implement citation storage, create `document_citations` table with index |
| `src/minirag/orchestration.py` | Add citation parameter to `index_document()`, add cached `_get_citation_key_for_document()`, enrich search results |
| `src/minirag/reranking/cross_encoder.py` | Preserve new `SearchResult` fields through reranking |
| `src/minirag/clients/indexing.py` | Pass citation data in `index_document()` |
| `src/minirag/clients/query.py` | Parse `document_id` and `citation_key` from API responses |
| `src/minirag/corpus.py` | Add `list_corpora()` for available corpora |
| `src/minirag/api/routes_info.py` | Add `/v1/corpora` endpoint |
| `scripts/ingest.py` | Load `.json` citation files, auto-generate when missing |
| `scripts/md2txt.py` | Copy `.json` files alongside converted `.txt` files |
| `scripts/search.py` | Display new fields in interactive search |
| `mcp/mini-rag.ts` | Add `get_citation` tool |
| `config.yaml.template` | Update service/index defaults |
| `justfile` | Add new corpus helper targets |
| `pyproject.toml` | Add new dependencies for tooling |

### Unchanged files

| File | Why unchanged |
|---|---|
| `src/main.py` | Entry point, just starts uvicorn |
| `src/minirag/__init__.py` | Package init |
| `src/minirag/config.py` | No new configuration settings |
| `src/minirag/backend_factory.py` | Creates backend instances, citations go through storage |
| `src/minirag/startup_validation.py` | Validates config at startup, no new config |
| `src/minirag/api/__init__.py` | Package init |
| `src/minirag/api/utils.py` | Response envelope helpers — unchanged |
| `src/minirag/api/responses.py` | Response utilities — unchanged |
| `src/minirag/api/models/__init__.py` | Package init |
| `src/minirag/api/models/info.py` | Health/info/shutdown models — unrelated |
| `src/minirag/search/__init__.py` | Package init |
| `src/minirag/search/embeddings.py` | FastText embedding generation — unrelated |
| `src/minirag/search/embeddings_interface.py` | Embeddings interface — unrelated |
| `src/minirag/storage/__init__.py` | Package init |
| `src/minirag/retrieval/__init__.py` | Package init |
| `src/minirag/retrieval/dense_interface.py` | DenseRetrieval interface — unrelated |
| `src/minirag/retrieval/sparse_interface.py` | SparseRetrieval interface — unrelated |
| `src/minirag/retrieval/faiss_dense.py` | FAISS implementation — unrelated |
| `src/minirag/retrieval/tantivy_sparse.py` | Tantivy implementation — unrelated |
| `src/minirag/reranking/__init__.py` | Package init |
| `src/minirag/reranking/interface.py` | Reranking interface — unrelated |
| `src/minirag/ingestion/__init__.py` | Package init |
| `src/minirag/ingestion/chunker.py` | Word-based chunking — unrelated |
| `src/minirag/clients/__init__.py` | Package init |
| `src/minirag/clients/base.py` | Shared HTTP logic — unrelated |
| `scripts/evaluate.py` | Evaluation uses ROUGE-L on text, ignores extra fields |
| `scripts/export_chunks.py` | Chunk export utility — unrelated |

# mini-rag Specification

**Version:** 3.0
**Status:** Draft
**Date:** 2026-02-10

## 1. Overview

mini-rag is a minimalist Retrieval-Augmented Generation (RAG) system implemented as a FastAPI service. It provides document indexing and retrieval through three search modes: dense vector search (semantic similarity), sparse lexical search (BM25 keyword matching), and hybrid search combining both approaches with configurable weighting. Hybrid search results can optionally be reranked using a cross-encoder model for improved relevance.

Every indexed document carries citation metadata, enabling RAG consumers to attribute retrieved content to its source. Citations are either provided via JSON sidecar files during ingestion or auto-generated from file metadata.

The system is fully configuration-driven, with no hardcoded default values anywhere in the codebase. All backend components are accessed through abstraction interfaces, making them independently swappable.

In its first iteration, mini-rag focuses exclusively on retrieval. The generation layer (sending retrieved chunks to an LLM for answer synthesis) is planned for a future iteration.

## 2. Architecture

### 2.1 High-Level Design

mini-rag follows a modular client-server architecture:

- A **FastAPI service** acts as the core, owning the index, handling chunking, embedding, storage, and search.
- **Python clients** (`IndexingClient`, `QueryClient`) communicate with the service over HTTP, providing a clean programmatic interface for external scripts and tools.
- **Helper scripts** (e.g., the ingestion script) use the clients to interact with the system.

### 2.2 Backend Components

The service layer is built on three independent backend components, each accessed through an abstraction interface:

- **Storage** (interface) — document, chunk, and citation persistence. Implemented by `SQLiteStorage`.
- **DenseRetrieval** (interface) — vector similarity search using embeddings. Implemented by `FAISSDense`.
- **SparseRetrieval** (interface) — lexical full-text search using BM25 scoring. Implemented by `TantivySparse`.

Each interface defines a contract for indexing, searching, and destroying data. The concrete implementations (SQLite, FAISS, Tantivy) can be swapped out independently without affecting the rest of the system.

An optional **Reranker** component (Protocol-based interface) post-processes hybrid search results using a cross-encoder model for improved relevance ranking.

### 2.3 Multi-Corpus Management

A **CorpusManager** (`corpus.py`) lazily creates and caches per-corpus `Orchestration` instances. Each corpus gets its own isolated set of backends (Storage, DenseRetrieval, SparseRetrieval). Corpus names must match `^[a-zA-Z][a-zA-Z0-9_-]*$`.

At startup, the `Config` and `CorpusManager` are created once and stored on `app.state`. All API endpoints are scoped to a corpus via the URL path: `/v1/corpus/{corpus}/...`. Route handlers access the corpus-scoped orchestration via `corpus_manager.get(corpus)`.

### 2.4 Orchestration Layer

A single **Orchestration** class (`orchestration.py` at the `minirag/` package root) coordinates all operations across the backend components for one corpus:

**Indexing operations:**

- `index_document(text, citation)` — the full pipeline: store document in Storage → chunk text → store chunks in Storage → generate embeddings → index in DenseRetrieval → index in SparseRetrieval → store citation in Storage. Returns document ID and list of chunk IDs.
- `destroy_index()` — wipes all backends (Storage, DenseRetrieval, SparseRetrieval) and clears the citation key cache.

**Search operations:**

- `search_dense(query, top_k)` — embed query → search DenseRetrieval → look up chunk text and citation key from Storage.
- `search_sparse(query, top_k)` — search SparseRetrieval → look up chunk text and citation key from Storage.
- `search_hybrid(query, top_k)` — run both dense and sparse search → merge results → optionally rerank with cross-encoder → return final results.

**Citation operations:**

- `get_citation(citation_key)` — delegates to Storage to retrieve raw citation JSON.

The orchestration layer does not contain search logic or merge logic. It delegates to the appropriate components and pipes data between them. Citation key lookups are cached per-instance using a thread-safe LRU cache (max 1024 entries) that only stores positive results (found citation keys), avoiding caching of fallback values for missing data.

### 2.5 Other Key Components

- **Config** — Pydantic-based configuration loader, parsing `config.yaml` with strict validation and no optional values.
- **FastAPI Service** — REST API with versioned endpoints (`/v1/...`), running on Uvicorn with configurable reload.
- **FastText Embeddings** — Generates dense vector embeddings using Facebook's FastText library. Vectors are normalized to unit length so that inner product equals cosine similarity.
- **Chunker** — Word-based text chunking with configurable chunk size and overlap.
- **Hybrid Merge** — A pure function in `search/hybrid.py` that takes dense and sparse result sets, normalizes scores, applies alpha weighting, and re-ranks.
- **Cross-Encoder Reranker** — Optional post-processing step for hybrid search. Uses a sentence-transformers cross-encoder model to re-score candidate results by query relevance, applying sigmoid normalization. Controlled by `search.reranking` config.
- **API Models** — Pydantic request and response models in `api/models/`, used for input validation and serialization on all endpoints.
- **Clients** — HTTP clients (`IndexingClient`, `QueryClient`) with health-check-before-operation behavior.
- **MCP Server** — A Model Context Protocol server (`mcp/mini-rag.ts`) exposing search and citation tools for integration with LLM agents.

### 2.6 Technology Stack

- Python 3.12+
- FastAPI + Uvicorn (ASGI server)
- Pydantic (configuration validation and API request/response models)
- SQLite (document and chunk storage)
- FAISS (dense vector index with flat inner product search)
- Tantivy via tantivy-py (sparse lexical index with BM25 scoring, stemming, tokenization)
- FastText (`cc.en.300.bin` — 300-dimensional Common Crawl embeddings)
- PyYAML (configuration file parsing)
- sentence-transformers (cross-encoder reranking models, optional)
- httpx (HTTP client library)
- uv (package manager)
- just (task runner)
- Node.js + TypeScript (MCP server)

### 2.7 Component Interaction Diagram

```
FastAPI Routes (api/)
    │
    ├──► API Models (api/models/) — Pydantic request/response validation
    │
    ▼
  CorpusManager (minirag/corpus.py) — per-corpus orchestration cache
    │
    ▼
  Orchestration (minirag/orchestration.py)
    │
    ├──► Chunker (text → chunks)
    ├──► Embeddings (text → vectors, normalized to unit length)
    │
    ├──► Storage (interface)           ──► SQLiteStorage
    │       insert_document / insert_chunk / get_chunk
    │       insert_citation / get_citation_key / get_citation / destroy
    │
    ├──► DenseRetrieval (interface)    ──► FAISSDense
    │       index / search / destroy
    │
    ├──► SparseRetrieval (interface)   ──► TantivySparse
    │       index / search / destroy
    │
    ├──► HybridMerge (pure function)
    │       normalize + alpha-weight + re-rank
    │
    └──► Reranker (protocol, optional) ──► CrossEncoderReranker
            re-score candidates by query relevance + sigmoid normalize
```

## 3. Project Structure

```
src/
├── main.py                            # Entry point (starts uvicorn)
└── minirag/
    ├── __init__.py
    ├── config.py                      # Config class — parses config.yaml, model_dump()
    ├── corpus.py                      # CorpusManager — per-corpus orchestration cache
    ├── orchestration.py               # Orchestration layer for indexing and search
    ├── backend_factory.py             # Factory for creating corpus-scoped backends
    ├── startup_validation.py          # Startup environment checks
    ├── api/                           # FastAPI service layer
    │   ├── __init__.py
    │   ├── app.py                     # FastAPI app creation & lifecycle
    │   ├── routes_index.py            # POST /corpus/{corpus}/index, DELETE
    │   ├── routes_query.py            # POST /corpus/{corpus}/query/dense|sparse|hybrid
    │   ├── routes_citation.py         # GET /corpus/{corpus}/citation/{citation_key}
    │   ├── routes_info.py             # GET /health, GET /info, POST /shutdown
    │   ├── utils.py                   # Response envelope helpers + ensure_healthy() guard
    │   ├── responses.py               # Response construction helpers
    │   └── models/                    # Pydantic request/response models
    │       ├── __init__.py
    │       ├── index.py               # IndexRequest, IndexResponse
    │       ├── query.py               # QueryRequest, QueryResponse, QueryResult
    │       ├── citation.py            # CitationResponse
    │       └── info.py                # HealthResponse, InfoResponse, ShutdownResponse
    ├── search/                        # Search utilities
    │   ├── __init__.py
    │   ├── hybrid.py                  # Score normalization & re-ranking (pure function)
    │   ├── embeddings.py              # FastText embedding generation + unit normalization
    │   ├── embeddings_interface.py    # Embeddings protocol
    │   └── types.py                   # SearchResult, ScoredChunk dataclasses
    ├── storage/                       # Storage abstraction
    │   ├── __init__.py
    │   ├── interface.py               # Storage interface definition (Reader/Writer/Lifecycle)
    │   └── sqlite.py                  # SQLiteStorage implementation
    ├── retrieval/                     # Retrieval abstractions
    │   ├── __init__.py
    │   ├── dense_interface.py         # DenseRetrieval interface definition
    │   ├── sparse_interface.py        # SparseRetrieval interface definition
    │   ├── faiss_dense.py             # FAISSDense implementation
    │   └── tantivy_sparse.py          # TantivySparse implementation
    ├── reranking/                     # Reranking abstraction
    │   ├── __init__.py
    │   ├── interface.py               # Reranker protocol
    │   └── cross_encoder.py           # CrossEncoderReranker (sentence-transformers)
    ├── ingestion/                     # Document processing
    │   ├── __init__.py
    │   └── chunker.py                 # Word-based chunking
    └── clients/                       # HTTP clients for external consumers
        ├── __init__.py
        ├── base.py                    # Shared HTTP logic (host, port, error handling)
        ├── indexing.py                # IndexingClient (index doc, destroy index)
        └── query.py                   # QueryClient (dense, sparse, hybrid search)

scripts/
├── ingest.py                          # Reads data/input/{corpus}/txt/, uses IndexingClient
├── md2txt.py                          # Converts markdown to text, copies JSON sidecars
├── search.py                          # CLI search tool
└── evaluate.py                        # ROUGE-L evaluation against Q&A pairs

mcp/
└── mini-rag.ts                        # MCP server (search + citation tools)

config.yaml.template                   # Committed config template (ready-to-go defaults)
config.yaml                            # Local config (gitignored, created by just init)
```

## 4. Configuration

### 4.1 Design Principles

- All configuration lives in `config.yaml` at the project root.
- A `config.yaml.template` with working defaults is committed to git.
- `config.yaml` is added to `.gitignore` — developers maintain their own local copy.
- `just init` copies the template to `config.yaml` only if it does not already exist.
- The `Config` class in `config.py` uses nested Pydantic models with no optional values — every field is required.
- Components access only their relevant sub-config via typed getter methods (e.g., `config.get_service_config()` returns a `ServiceConfig` object).
- The `Config` class exposes the full configuration as a dictionary via Pydantic's `model_dump()` method, used by the `/v1/info` endpoint.

### 4.2 Configuration Structure

```yaml
service:
  host: "127.0.0.1"
  port: 7001
  reload: false
  log_level: "INFO"

data:
  data_dir: "data"

index:
  chunking:
    chunk_size: 500
    overlap: 0.3

  embeddings:
    model_name: "cc.en.300.bin"
    dimension: 300

  storage:
    db_filename: "minirag.db"

  faiss:
    index_type: "IndexFlatIP"
    nprobe: 1

  tantivy:
    language: "en"
    stemming: true

search:
  hybrid:
    alpha: 0.5

  dense: {}

  sparse: {}

  reranking:
    enabled: false
    model_name: "cross-encoder/ms-marco-MiniLM-L12-v2"
    candidate_multiplier: 3
```

### 4.3 Pydantic Model Hierarchy

The configuration is parsed into the following nested Pydantic models:

- `Config` (root)
  - `ServiceConfig` — host, port, reload, log_level
  - `DataConfig` — data_dir
  - `IndexConfig`
    - `ChunkingConfig` — chunk_size, overlap
    - `EmbeddingsConfig` — model_name, dimension
    - `StorageConfig` — db_filename
    - `FAISSConfig` — index_type, nprobe
    - `TantivyConfig` — language, stemming
  - `SearchConfig`
    - `HybridConfig` — alpha
    - `DenseSearchConfig` — (reserved for future query-time settings)
    - `SparseSearchConfig` — (reserved for future query-time settings)
    - `RerankingConfig` — enabled, model_name, candidate_multiplier

### 4.4 Path Resolution

The `data_dir` in the `DataConfig` serves as the base path. Other components derive their paths from it:

- Input text files: `{data_dir}/input/{corpus}/txt/`
- FastText model: `{data_dir}/models/{model_name}`
- SQLite database: `{data_dir}/storage/{corpus}/{db_filename}`
- FAISS index: `{data_dir}/index/{corpus}/faiss/`
- Tantivy index: `{data_dir}/index/{corpus}/tantivy/`

Components only know their own subdirectory conventions (e.g., the ingestion module knows about `input/{corpus}/txt/`, the embeddings module knows about `models/`). The base `data_dir` comes from the config.

### 4.5 Data Directory Layout

```
data/
├── input/
│   └── {corpus}/
│       ├── md/               # Markdown source files
│       │   ├── doc.md
│       │   └── doc.json      # Citation JSON sidecar (optional)
│       ├── txt/              # Plain text files for ingestion (from md2txt or manual)
│       │   ├── doc.txt
│       │   └── doc.json      # Copied from md/ by md2txt
│       └── evals/            # Evaluation Q&A pairs (optional)
├── models/                   # Embedding and reranking models
│   └── cc.en.300.bin
├── storage/
│   └── {corpus}/
│       └── minirag.db        # SQLite database per corpus
└── index/
    └── {corpus}/
        ├── faiss/            # FAISS vector index files
        └── tantivy/          # Tantivy lexical index files
```

### 4.6 Startup Validation

At service startup, the `Config` class performs full validation:

- All required keys are present and have correct types (enforced by Pydantic).
- The FastText model file exists at the configured path.
- The `data_dir` is accessible and writable.
- If any validation fails, the service refuses to start with a clear error message (fail-fast).

## 5. REST API

### 5.1 General Design

- All endpoints are prefixed with `/v1`.
- All endpoints are synchronous (query-and-wait) — the response is returned only after the operation completes.
- All request bodies are JSON, validated by Pydantic request models defined in `api/models/`.
- All responses follow a uniform envelope format.
- HTTP status codes are used correctly and mirrored inside the JSON response body.

### 5.2 Response Envelope

**Success response:**

```json
{
  "status": 200,
  "data": { ... }
}
```

**Error response:**

```json
{
  "status": 422,
  "error": "field 'top_k' is required"
}
```

Every response contains `status`. Successful responses contain `data`. Error responses contain `error` instead. The `error` string is the internal exception message — no sanitization or rewriting.

Response construction happens exclusively in route handlers, never in business logic. Helper methods in `api/utils.py` provide `success_response(status, data)` and `error_response(status, message)` for uniform construction.

### 5.3 HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200  | Successful operation |
| 400  | Malformed JSON or unparseable request body |
| 422  | Valid JSON but missing or invalid fields |
| 500  | Internal server error (FAISS failure, Tantivy failure, embedding failure, etc.) |
| 503  | Service unavailable (app state is not healthy) |

### 5.4 Endpoints

#### GET /v1/health

Returns the current app state. This endpoint is always available, regardless of app state.

**Request:** No body.

**Response when healthy:**

```json
{
  "status": 200,
  "data": { "status": "healthy" }
}
```

**Response when shutting down:**

```json
{
  "status": 503,
  "data": { "status": "shutting_down" }
}
```

#### GET /v1/info

Returns the complete service configuration. This endpoint is always available, regardless of app state.

**Request:** No body.

**Response:**

```json
{
  "status": 200,
  "data": {
    "config": { ... full nested config object ... }
  }
}
```

#### GET /v1/corpora

Returns the list of available corpora discovered on disk and a parallel description map.

**Request:** No body.

**Response:**

```json
{
  "status": 200,
  "data": {
    "corpora": ["books", "notes"],
    "descriptions": {
      "books": "# Books\nReference material.",
      "notes": "No description available."
    }
  }
}
```

The `corpora` array remains sorted alphabetically. The `descriptions` object contains exactly one string value for each corpus in `corpora`; clients that only read `data.corpora` remain compatible. Missing description files use the exact placeholder `No description available.`. Description read failures return HTTP 500 instead of silently using the placeholder.

#### GET /v1/corpus/{corpus}/description

Returns the resolved Markdown description for one loaded corpus.

**Request:** No body.

**Response:**

```json
{
  "status": 200,
  "data": {
    "corpus": "books",
    "description": "# Books\nReference material."
  }
}
```

A valid loaded corpus without `description.md` returns HTTP 200 with `No description available.`. An invalid corpus name returns HTTP 400. A valid but unknown corpus returns HTTP 404. An unreadable, non-file, symlinked, or invalid UTF-8 stored description returns HTTP 500.

#### POST /v1/shutdown

Initiates a graceful shutdown. Sets `app.state.app_status` to `"shutting_down"` before scheduling the process exit. Once the app state changes, all guarded endpoints reject requests with HTTP 503.

**Request:** No body.

**Response:**

```json
{
  "status": 200,
  "data": { "message": "shutdown initiated" }
}
```

#### POST /v1/corpus/{corpus}/index

Indexes a single document into the specified corpus. The service handles the full pipeline: store document → chunk → store chunks → embed → index in dense and sparse indices → store citation. The response is returned only after all steps complete.

Empty or whitespace-only document text is rejected with HTTP 422 before any processing begins.

If any step in the indexing pipeline fails, the service returns an error immediately. No rollback is performed; partial state may remain. Use `DELETE /v1/corpus/{corpus}/index` to clean up before re-indexing.

**Request:**

```json
{
  "document": "the full text content of the document...",
  "citation": {
    "citation_key": "smith2026",
    "source_type": "journal",
    "common": { "title": "Paper Title", "author": "Smith et al." },
    "source_data": { "doi": "10.1234/example" }
  }
}
```

The `citation` field is optional. If omitted or null, a citation record is auto-generated using the document ID as the citation key and `"text_file"` as the source type.

**Response:**

```json
{
  "status": 200,
  "data": {
    "document_id": 1,
    "chunks_indexed": 5,
    "chunk_ids": [1, 2, 3, 4, 5]
  }
}
```

The `chunk_ids` field returns all chunk IDs assigned by the storage layer during indexing. This aids debugging and enables integration tests to verify that chunks were stored correctly. `chunks_indexed` equals `len(chunk_ids)`.

#### DELETE /v1/corpus/{corpus}/index

Destroys the entire index for a corpus across all backends (Storage, DenseRetrieval, SparseRetrieval), including all citation records.

**Request:** No body.

**Response:**

```json
{
  "status": 200,
  "data": { "message": "index destroyed" }
}
```

#### POST /v1/corpus/{corpus}/query/dense

Performs dense vector similarity search using FastText embeddings and FAISS.

**Request:**

```json
{
  "query": "search terms here",
  "top_k": 5
}
```

**Response (with results):**

```json
{
  "status": 200,
  "data": {
    "results": [
      { "chunk_id": 1, "document_id": 1, "citation_key": "smith2026", "text": "matched chunk text...", "score": 0.87 },
      { "chunk_id": 2, "document_id": 1, "citation_key": "smith2026", "text": "another chunk...", "score": 0.74 }
    ]
  }
}
```

**Response (no results):**

```json
{
  "status": 200,
  "data": {
    "results": []
  }
}
```

Each result includes `chunk_id`, `document_id`, `citation_key`, `text`, and `score`. The `citation_key` can be used to fetch full citation metadata via the citation endpoint.

Scores are normalized between 0 and 1, with higher values indicating greater relevance. For dense search, scores are cosine similarities computed via inner product on unit-normalized embeddings. An empty results list is returned when no matches are found or when the index is empty — this is not an error.

#### POST /v1/corpus/{corpus}/query/sparse

Performs sparse lexical search using Tantivy's BM25 scoring. Same request and response format as the dense query endpoint.

Scores are BM25 relevance scores normalized to [0, 1] by dividing by the maximum score in the result set.

#### POST /v1/corpus/{corpus}/query/hybrid

Performs hybrid search combining dense and sparse results with score normalization, alpha-weighted merging, and optional cross-encoder reranking. Same request and response format as the dense query endpoint.

The balance between dense and sparse results is controlled by the `search.hybrid.alpha` configuration parameter (0.0 = pure sparse/lexical, 1.0 = pure dense/vector).

When reranking is enabled (`search.reranking.enabled: true`), the hybrid search retrieves `top_k * candidate_multiplier` candidates from each retrieval backend before merging. The merged candidates are then re-scored by the cross-encoder model, and the final top-k results are returned. Reranking scores are raw cross-encoder logits passed through a sigmoid function, producing values in [0, 1].

**Hybrid merge behavior for edge cases:**

- If a chunk appears in only one result set (dense or sparse but not both), its missing score is treated as 0.0.
- If a result set is empty, only the other set's scores contribute (scaled by the respective alpha weight).
- If both result sets are empty, an empty results list is returned.
- Querying an empty index returns an empty results list (not an error).

#### GET /v1/corpus/{corpus}/citation/{citation_key}

Returns full citation metadata for a given citation key.

**Request:** No body.

**Response (found):**

```json
{
  "status": 200,
  "data": {
    "citation_key": "smith2026",
    "source_type": "journal",
    "common": { "title": "Paper Title", "author": "Smith et al." },
    "source_data": { "doi": "10.1234/example" }
  }
}
```

**Response (not found):**

```json
{
  "status": 404,
  "error": "citation not found: unknown_key"
}
```

### 5.5 Pydantic API Models

All API request and response payloads are defined as Pydantic models in `api/models/`. Each file maps to a route group:

- `api/models/index.py` — `IndexRequest` (document field, optional citation dict), `IndexResponse` (document_id, chunks_indexed, chunk_ids).
- `api/models/query.py` — `QueryRequest` (query string, top_k as positive integer), `QueryResponse` (results list), `QueryResult` (chunk_id, document_id, citation_key, text, score).
- `api/models/citation.py` — `CitationResponse` (citation_key, source_type, common, source_data).
- `api/models/info.py` — `HealthResponse`, `InfoResponse`, `CorporaResponse`, `CorpusDescriptionResponse`, `ShutdownResponse`.

FastAPI uses these models to automatically validate incoming JSON. Invalid payloads are rejected with HTTP 422 and the Pydantic validation error message is included in the error response envelope.

### 5.6 App State Management

The service maintains a formal app state stored on `app.state.app_status`. The possible values are:

- `"healthy"` — the service is running normally and accepting all requests.
- `"shutting_down"` — a shutdown has been initiated; only informational endpoints remain available.

**Guard function:** A helper function `ensure_healthy(request)` in `api/utils.py` checks `request.app.state.app_status`. If the state is not `"healthy"`, it immediately returns an error response:

```json
{
  "status": 503,
  "error": "service is shutting_down"
}
```

**Guarded endpoints** — every route handler for these endpoints calls `ensure_healthy()` as its first action:

- POST /v1/corpus/{corpus}/index
- DELETE /v1/corpus/{corpus}/index
- POST /v1/corpus/{corpus}/query/dense
- POST /v1/corpus/{corpus}/query/sparse
- POST /v1/corpus/{corpus}/query/hybrid
- GET /v1/corpus/{corpus}/citation/{citation_key}
- GET /v1/corpora
- GET /v1/corpus/{corpus}/description
- POST /v1/shutdown

**Unguarded endpoints** — these are always available regardless of app state:

- GET /v1/health (reports the current app state)
- GET /v1/info (returns the configuration)

The health endpoint reflects the current app state in its response. When the state is `"healthy"`, it returns HTTP 200. When the state is `"shutting_down"`, it returns HTTP 503 with the state value in the response body.

## 6. Storage Layer

### 6.1 Storage Interface

The Storage interface (`storage/interface.py`) is split into three ABCs — `StorageReader`, `StorageWriter`, and `StorageLifecycle` — combined into a single `Storage` ABC:

**Writer methods:**

- `insert_document_with_citation(content: str, citation: dict | None) -> int` — stores a document and citation atomically and returns the document ID.
- `insert_document(content: str) -> int` — stores the full document text and returns an auto-assigned document ID.
- `insert_chunk(document_id: int, content: str) -> int` — stores a chunk with a foreign key reference to its document and returns an auto-assigned chunk ID.
- `insert_citation(citation_key: str, document_id: int, citation_json: str) -> None` — stores a citation record keyed by citation_key. Fails fast on duplicate keys.

**Reader methods:**

- `get_document(document_id: int) -> str` — retrieves document content by ID.
- `get_chunk(chunk_id: int) -> ChunkWithDocument` — retrieves a chunk by ID, returning a named tuple of (document_id, content).
- `get_citation_key(document_id: int) -> str | None` — returns the citation key for a document, or None if not found.
- `get_citation(citation_key: str) -> str | None` — returns the raw citation JSON string, or None if not found.

**Lifecycle methods:**

- `close() -> None` — closes the underlying database connection.
- `destroy() -> None` — wipes all stored data including citations.

### 6.2 SQLite Implementation

`storage/sqlite.py` implements the Storage interface using SQLite:

**Documents table:**

| Column | Type | Constraint |
|--------|------|------------|
| `document_id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `content` | TEXT | NOT NULL |

**Chunks table:**

| Column | Type | Constraint |
|--------|------|------------|
| `chunk_id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `document_id` | INTEGER | FOREIGN KEY → documents(document_id), NOT NULL |
| `content` | TEXT | NOT NULL |

**Document citations table:**

| Column | Type | Constraint |
|--------|------|------------|
| `citation_key` | TEXT | PRIMARY KEY |
| `document_id` | INTEGER | FOREIGN KEY → documents(document_id), NOT NULL |
| `citation_json` | TEXT | NOT NULL |

An index `idx_citations_document_id` exists on `document_citations(document_id)` for efficient reverse lookups.

The SQLite database file is stored at `{data_dir}/storage/{corpus}/{db_filename}`.

Document and chunk IDs are assigned automatically by SQLite's autoincrement mechanism. ID assignment is fully internal to the service and transparent to clients.

### 6.3 Corpus Description Metadata

Each loaded corpus can have one optional Markdown description stored at `{data_dir}/storage/{corpus}/description.md`. With no file argument the command prints the current description; providing a file installs or replaces it:

```bash
just describe-corpus <corpus> [markdown-file]
```

When provided, the source description must be a regular, non-symlink UTF-8 `.md` file, must contain non-whitespace text, and must be at most 64 KiB. Ingestion requires an existing corpus storage directory and writes the canonical file atomically, so readers observe either the old complete description or the new complete description.

Corpus descriptions are not documents. They are never passed through document ingestion, chunking, embeddings, FAISS, Tantivy, SQLite document/chunk tables, or the ingestion ledger. Index rebuilds and `just delete <corpus>` clear search data and ledger state but preserve `description.md` with the corpus storage directory.

## 7. Dense Retrieval (Vector Search)

### 7.1 DenseRetrieval Interface

The DenseRetrieval interface (`retrieval/dense_interface.py`) defines the contract for vector search:

- `index(chunk_id: int, embedding: list[float]) -> None` — adds a vector to the index, associated with a chunk ID.
- `search(query_embedding: list[float], top_k: int) -> list[ScoredChunk]` — returns a list of `ScoredChunk(chunk_id, score)` tuples, sorted by score descending.
- `persist() -> None` — flushes the in-memory index to disk.
- `destroy() -> None` — wipes the entire vector index.

The interface guarantees scores in [0, 1] with higher = more relevant.

### 7.2 FAISS Implementation

`retrieval/faiss_dense.py` implements DenseRetrieval using Facebook's FAISS library:

- Uses `IndexIDMap` wrapping `IndexFlatIP` (inner product) as the base index.
- All input embeddings are expected to be unit-normalized (done by the embeddings module), so inner product equals cosine similarity and scores are naturally in [0, 1].
- Chunk IDs are mapped directly to FAISS's ID system via `IndexIDMap`.
- The FAISS index is persisted to `{data_dir}/index/faiss/` and loaded on service startup.

### 7.3 FastText Embeddings

Dense embeddings are generated using Facebook's FastText library with the `cc.en.300.bin` model (300-dimensional, trained on Common Crawl, English).

The embeddings module (`search/embeddings.py`):

- Loads the FastText model from `{data_dir}/models/{model_name}`.
- **Validates at load time** that the model's output dimension matches the configured `index.embeddings.dimension`. Raises an error on mismatch (fail-fast).
- Generates sentence vectors for input text.
- **Normalizes all vectors to unit length** before returning, ensuring that FAISS inner product computes cosine similarity directly.
- Is used for both indexing (chunk embeddings) and querying (query embedding).

### 7.4 Model Download

The FastText model is downloaded during `just init` and stored at `{data_dir}/models/{model_name}`.

Download URL: `https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.en.300.bin.gz`

The `just init` recipe downloads the compressed model via `wget` (or `curl` as fallback) and decompresses it with `gunzip`. If the uncompressed model file already exists, the download is skipped.

## 8. Sparse Retrieval (Lexical Search)

### 8.1 SparseRetrieval Interface

The SparseRetrieval interface (`retrieval/sparse_interface.py`) defines the contract for lexical search:

- `index(chunk_id: int, content: str) -> None` — adds text content to the lexical index, associated with a chunk ID.
- `search(query: str, top_k: int) -> list[ScoredChunk]` — returns a list of `ScoredChunk(chunk_id, score)` tuples, sorted by score descending.
- `persist() -> None` — flushes the in-memory index to disk.
- `destroy() -> None` — wipes the entire lexical index.

The interface guarantees scores in [0, 1] with higher = more relevant.

### 8.2 Tantivy Implementation

`retrieval/tantivy_sparse.py` implements SparseRetrieval using the Tantivy full-text search engine (via tantivy-py):

- Uses BM25 scoring for relevance ranking.
- Performs tokenization, stemming (configurable, English by default), and stopword removal as part of the Tantivy pipeline.
- A `chunk_id` field is stored in the Tantivy schema as a unique identifier for deletion support.
- Scores are normalized to [0, 1] by dividing by the maximum score in the result set. A single result normalizes to 1.0.
- The Tantivy index is persisted to `{data_dir}/index/tantivy/` and loaded on service startup.

## 9. Hybrid Search Merge

The hybrid merge function (`search/hybrid.py`) is a pure function that combines dense and sparse result sets:

1. Accept two result sets: `dense_results` and `sparse_results`, each as `list[SearchResult]`.
2. Both sets are already normalized to [0, 1] by their respective retrieval implementations.
3. Build a combined score for each chunk: `final_score = alpha * dense_score + (1 - alpha) * sparse_score`.
4. If a chunk appears in only one set, its missing score is 0.0.
5. Re-rank all chunks by `final_score` descending.
6. Return the top-K results.

**Edge cases:**

- `alpha` must be in [0.0, 1.0] — values outside this range raise a `ValueError`.
- `top_k` must be a positive integer.
- Empty result sets are handled gracefully — the other set's scores contribute alone.
- Both sets empty returns an empty list.
- All scores identical within a set: normalization preserves them as-is (they were already normalized by the retrieval layer).

## 10. Reranking

### 10.1 Reranker Interface

The Reranker interface (`reranking/interface.py`) is a Python `Protocol` defining the contract for post-processing search results:

- `candidate_count(top_k: int) -> int` — returns how many merged candidates should be retrieved before reranking. Typically `top_k * candidate_multiplier`.
- `rerank(query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]` — re-scores and re-ranks results by query relevance, returning the top-k.

### 10.2 Cross-Encoder Implementation

`reranking/cross_encoder.py` implements the Reranker interface using sentence-transformers:

- Uses a cross-encoder model (default: `cross-encoder/ms-marco-MiniLM-L12-v2`) that scores query-passage pairs jointly.
- Model is loaded via `importlib.import_module("sentence_transformers")` with cache directory support.
- Scoring: all candidate results are paired with the query as `[query, chunk_text]` and scored in a single batch via `model.predict()`.
- Raw cross-encoder logits are normalized to [0, 1] via sigmoid: `score = 1 / (1 + exp(-logit))`.
- Results are re-sorted by the normalized score descending and truncated to `top_k`.

### 10.3 Configuration

Reranking is controlled by `search.reranking` in the config:

- `enabled` (bool) — whether to apply reranking to hybrid search results.
- `model_name` (str) — cross-encoder model identifier (must not be empty).
- `candidate_multiplier` (int) — multiplier for how many candidates to retrieve before reranking (must be > 0).

When `enabled: false`, no reranker is instantiated at startup and hybrid search returns merged results directly.

### 10.4 Integration with Hybrid Search

When reranking is enabled, the hybrid search flow becomes:

1. Compute `retrieval_top_k = reranker.candidate_count(top_k)` (= `top_k * candidate_multiplier`).
2. Run dense and sparse search each with `retrieval_top_k`.
3. Merge results via hybrid merge (alpha-weighted).
4. Pass merged candidates to `reranker.rerank(query, merged, top_k)`.
5. Return the reranked top-k results.

## 11. Ingestion Pipeline

### 11.1 Document Flow

1. Markdown files are placed in `{data_dir}/input/{corpus}/md/` with optional `.json` citation sidecars.
2. `scripts/md2txt.py` converts `.md` files to `.txt` and copies `.json` sidecars to `{data_dir}/input/{corpus}/txt/`.
3. `scripts/ingest.py` reads all `.txt` files from the `txt/` directory.
4. For each file, the script loads the citation (from `.json` sidecar or auto-generated), then uses the `IndexingClient` to POST the document text and citation to the service.
5. The service receives the text and citation, and the orchestration layer runs the full indexing pipeline:
   a. Store the full document in Storage → get `document_id`.
   b. Store the citation record in Storage (from request or auto-generated). Fails fast on duplicate `citation_key`.
   c. Chunk the text (word-based, configurable size and overlap) → get list of chunks.
   d. Store each chunk in Storage → get `chunk_id` for each.
   e. Generate embeddings for all chunks (FastText, unit-normalized).
   f. Index each chunk in DenseRetrieval (chunk_id + embedding).
   g. Index each chunk in SparseRetrieval (chunk_id + chunk text).
   h. Return `document_id` and list of `chunk_ids`.

### 11.2 Citation Sidecar Files

Citation metadata can be provided as a JSON file with the same stem as the `.txt` file (e.g., `doc.json` for `doc.txt`). The JSON must contain at minimum:

- `citation_key` (str) — unique identifier for this citation.
- `source_type` (str) — category of the source (e.g., `"journal"`, `"blog"`, `"text_file"`).
- `common` (object) — shared metadata fields (title, author, date, etc.).
- `source_data` (object) — source-type-specific metadata.

If no `.json` sidecar exists, the ingestion script auto-generates a minimal citation:

```json
{
  "citation_key": "{file_stem}",
  "source_type": "text_file",
  "common": { "title": "{filename}" },
  "source_data": {}
}
```

### 11.3 Chunking Strategy

Word-based chunking is implemented in `ingestion/chunker.py`:

- **Chunk size:** 500 words (configurable via `index.chunking.chunk_size`).
- **Overlap:** 30% (configurable via `index.chunking.overlap`).
- Words are counted by whitespace splitting.
- Empty or whitespace-only input text is rejected with a `ValueError`.
- Invalid chunk parameters (non-positive chunk size, overlap outside [0.0, 1.0), overlap yielding non-positive step) are rejected with a `ValueError`.

### 11.4 Ingestion Behavior

- The `just ingest` target destroys the existing index before indexing.
- Files are sorted alphanumerically by filename for deterministic, reproducible ordering.
- Files are indexed one at a time, with progress reported to the console (including the filename being indexed).
- If any file fails to index, the script fails immediately with the original error. No further files are processed.
- There are no update or deduplication operations — only index, destroy, and query.

### 11.5 Indexing Error Behavior

The ingestion script (`scripts/ingest.py`) follows a fail-fast approach. If any file fails to index, the error propagates immediately and the script aborts. Partial state from the failed file may remain — use `DELETE /v1/corpus/{corpus}/index` to clean up before re-indexing.

## 12. Clients

### 12.1 Base Client

`clients/base.py` provides shared HTTP logic:

- Reads host and port from the service config.
- Checks the `/v1/health` endpoint before any operation — if the service is not healthy, the client aborts with an exception.
- Handles HTTP errors and surfaces them as exceptions.

### 12.2 IndexingClient

`clients/indexing.py` provides:

- `index_document(corpus, text, citation)` — POSTs a document with optional citation to `/v1/corpus/{corpus}/index`.
- `destroy_index(corpus)` — sends DELETE to `/v1/corpus/{corpus}/index`.

### 12.3 QueryClient

`clients/query.py` provides:

- `search_dense(corpus, query, top_k)` — sends POST to `/v1/corpus/{corpus}/query/dense`.
- `search_sparse(corpus, query, top_k)` — sends POST to `/v1/corpus/{corpus}/query/sparse`.
- `search_hybrid(corpus, query, top_k)` — sends POST to `/v1/corpus/{corpus}/query/hybrid`.
- `get_citation(corpus, citation_key)` — sends GET to `/v1/corpus/{corpus}/citation/{citation_key}`.

All three methods return `list[SearchResult]` with `chunk_id`, `document_id`, `citation_key`, `text`, and `score` fields.

## 13. SearchResult Type

All search results throughout the system use a consistent `SearchResult` type defined as a frozen dataclass in a shared location (`search/types.py`):

```python
@dataclass(frozen=True)
class SearchResult:
    chunk_id: int       # storage chunk identifier
    document_id: int    # parent document identifier
    citation_key: str   # citation key for source attribution
    text: str           # chunk text content
    score: float        # normalized relevance score in [0.0, 1.0]
```

Validation in `__post_init__`: `chunk_id > 0`, `document_id > 0`, `citation_key` non-empty after strip, `text` non-empty after strip, `score` in [0.0, 1.0].

This type is used by:

- The orchestration layer's search methods (return `list[SearchResult]`).
- The hybrid merge function (accepts and returns `list[SearchResult]`).
- The reranker (accepts and returns `list[SearchResult]`).
- The client methods (return `list[SearchResult]` parsed from JSON).
- The API response serialization (converts to `{"chunk_id": ..., "document_id": ..., "citation_key": ..., "text": ..., "score": ...}`).

Retrieval interfaces return `list[ScoredChunk]` (chunk_id, score). The orchestration layer resolves chunk IDs to text and citation keys via the Storage layer and constructs `SearchResult` objects.

## 14. Just Targets

| Target | Description |
|--------|-------------|
| `just init` | Initialize environment: create directories, install dependencies via `uv sync`, download FastText model to `{data_dir}/models/`, copy `config.yaml.template` to `config.yaml` if it does not exist |
| `just start` | Start the FastAPI service in the foreground (Ctrl+C to stop). Uvicorn binds to the configured host and port with reload behavior controlled by config |
| `just stop` | Shut down the running service by calling the `/v1/shutdown` endpoint |
| `just status` | Check if the service is running by hitting `/v1/health`. If running, display the full configuration from `/v1/info`. If not, display "service is not running" |
| `just ingest` | Destroy the existing index, then ingest all `.txt` files from `{data_dir}/input/{corpus}/txt/` via the `IndexingClient`. Shows progress per file. Fails hard on any error |
| `just describe-corpus` | Show the current corpus description, or store/replace it from a validated Markdown file without indexing it |
| `just md2txt` | Convert `{data_dir}/input/{corpus}/md/` files to `.txt` and copy `.json` sidecars to `{data_dir}/input/{corpus}/txt/` |
| `just delete` | Destroy corpus index contents and ledger state by calling `DELETE /v1/corpus/{corpus}/index`; corpus metadata such as `description.md` is preserved |
| `just search` | Interactive search loop for a corpus |
| `just evaluate` | Evaluate retrieval quality for a corpus |
| `just citation` | Fetch citation metadata for one or more citation keys in a corpus |
| `just inspect` | Inspect chunks for a document ID in a corpus |
| `just destroy` | Remove the virtual environment |
| `just help` | Show all available commands |

The existing `just run` target is replaced by `just start` for the service. Existing CI targets (`just ci`, `just ci-quiet`, etc.) remain unchanged.

## 15. Error Handling

### 15.1 Principles

- **Fail fast** — if something is wrong, report it immediately and stop.
- **No error masking** — no degraded states, no silent fallbacks, no default values.
- **Exceptions bubble up** — business logic raises exceptions with descriptive messages. Route handlers catch them and wrap them in the error response envelope.
- **Internal error messages are exposed as-is** — no sanitization or rewriting for the client. This is a minimalist system.
- **No automatic rollback** — if an indexing step fails partway through, partial state may remain. Use `DELETE /v1/corpus/{corpus}/index` to clean up.

### 15.2 Startup Failures

The service refuses to start if:

- `config.yaml` is missing.
- Configuration validation fails (missing keys, wrong types).
- The FastText model file does not exist.
- SQLite database cannot be initialized.
- FAISS index cannot be initialized.
- Tantivy index cannot be initialized.

### 15.3 Runtime Errors

All runtime errors (FAISS failures, Tantivy failures, SQLite failures, embedding failures, etc.) are caught by route handlers and returned as error responses with HTTP 500 and the exception message.

## 16. Logging

- All logging goes through Python's standard `logging` module — never `print()`. This applies to both `src/` and `scripts/`.
- The log level is configurable via `service.log_level` in `config.yaml`.
- The committed template defaults to `INFO`. Developers can switch to `DEBUG` locally.
- All errors, warnings, info, and debug messages use the logger.

## 17. Testing

### 17.1 Current Requirements

- Foundational components must have unit tests from the start: config parsing, chunker, hybrid merge logic, response utilities.
- The CI pipeline enforces 80% test coverage.
- Tests run with `just test` (unit tests) and `just test-coverage` (with threshold enforcement).

### 17.2 Test Configuration

- pytest with randomized test order (pytest-randomly).
- 30-second timeout per test (pytest-timeout).
- Async support via pytest-asyncio.

## 18. CI Pipeline

The CI pipeline is set in stone and runs the following steps in order:

1. `init` — Initialize environment
2. `code-format` — Auto-format code
3. `code-style` — Verify formatting
4. `code-typecheck` — Type checking (mypy, strict)
5. `code-security` — Security scan (bandit)
6. `code-deptry` — Dependency hygiene
7. `code-spell` — Spell checking
8. `code-semgrep` — Custom static analysis (no defaults, no fallbacks, no type suppression)
9. `code-audit` — Vulnerability scanning (pip-audit)
10. `test` — Unit tests
11. `code-lspchecks` — Strict type checking (pyright)

## 19. MCP Server

The `mcp/` directory contains a Model Context Protocol server (`mini-rag.ts`) that exposes mini-rag functionality as tools for LLM agents:

**Tools:**

- `search` — performs hybrid search (dense + sparse) against a corpus and returns results with citation keys.
- `get_citation` — retrieves full citation metadata by corpus and citation key.
- `list_corpora` — returns the machine-readable API JSON envelope with a `data.corpora` array and parallel `data.descriptions` object keyed by corpus name.

The MCP server communicates with the mini-rag service over HTTP (same host/port as configured in `config.yaml`). It includes health checking before each operation and returns structured JSON results.

## 20. Future To-Do

The following items are out of scope for the first iteration but planned for future work:

1. **LLM generation layer** — Send retrieved chunks along with the user's query to an LLM to produce synthesized answers (completing the "G" in RAG).
2. **Markdown file support** — Support `.md` files in addition to `.txt` for ingestion (from `{data_dir}/input/{corpus}/md/`).
3. **Increase test coverage to 90%** — Tighten test coverage requirements once the design stabilizes.
4. **Index lifecycle management** — Detect configuration changes that invalidate the existing index (e.g., embedding model, chunk size) and trigger or recommend a rebuild.
5. **CORS middleware** — Add configurable Cross-Origin Resource Sharing middleware for browser-based clients.
6. **Uvicorn config file watching** — Optionally watch `config.yaml` for changes and auto-restart the service (with awareness that index invalidation may be required).
7. **Per-document rollback** — On indexing failure, automatically roll back partial state across all three backends.
8. **Idempotent indexing** — Detect duplicate documents via content hashing and skip re-indexing.

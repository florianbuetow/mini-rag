# mini-rag Specification

**Version:** 2.2
**Status:** Draft
**Date:** 2026-02-07

## 1. Overview

mini-rag is a minimalist Retrieval-Augmented Generation (RAG) system implemented as a FastAPI service. It provides document indexing and retrieval through three search modes: dense vector search (semantic similarity), sparse lexical search (BM25 keyword matching), and hybrid search combining both approaches with configurable weighting.

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

- **Storage** (interface) — document and chunk persistence. Implemented by `SQLiteStorage`.
- **DenseRetrieval** (interface) — vector similarity search using embeddings. Implemented by `FAISSDense`.
- **SparseRetrieval** (interface) — lexical full-text search using BM25 scoring. Implemented by `TantivySparse`.

Each interface defines a contract for indexing, searching, and destroying data. The concrete implementations (SQLite, FAISS, Tantivy) can be swapped out independently without affecting the rest of the system.

### 2.3 Orchestration Layer

A single **Orchestration** class (`orchestration.py` at the `minirag/` package root) coordinates all operations across the three backend components:

**Indexing operations:**

- `index_document(text)` — the full pipeline: store document in Storage → chunk text → store chunks in Storage → generate embeddings → index in DenseRetrieval → index in SparseRetrieval. Returns document ID and list of chunk IDs.
- `destroy_index()` — wipes all three backends (Storage, DenseRetrieval, SparseRetrieval).

**Search operations:**

- `search_dense(query, top_k)` — embed query → search DenseRetrieval → look up chunk text from Storage.
- `search_sparse(query, top_k)` — search SparseRetrieval → look up chunk text from Storage.
- `search_hybrid(query, top_k)` — run both dense and sparse search → pass results to the hybrid merge function → return merged results.

The orchestration layer does not contain search logic or merge logic. It delegates to the appropriate components and pipes data between them.

At startup, the `Config` and `Orchestration` instances are created once and stored on `app.state` (`app.state.config`, `app.state.orchestration`). Route handlers access them via `request.app.state`. This is FastAPI's built-in mechanism for sharing application-wide singletons with route handlers without global variables.

### 2.4 Other Key Components

- **Config** — Pydantic-based configuration loader, parsing `config.yaml` with strict validation and no optional values.
- **FastAPI Service** — REST API with versioned endpoints (`/v1/...`), running on Uvicorn with configurable reload.
- **FastText Embeddings** — Generates dense vector embeddings using Facebook's FastText library. Vectors are normalized to unit length so that inner product equals cosine similarity.
- **Chunker** — Word-based text chunking with configurable chunk size and overlap.
- **Hybrid Merge** — A pure function in `search/hybrid.py` that takes dense and sparse result sets, normalizes scores, applies alpha weighting, and re-ranks.
- **API Models** — Pydantic request and response models in `api/models/`, used for input validation and serialization on all endpoints.
- **Clients** — HTTP clients (`IndexingClient`, `QueryClient`) with health-check-before-operation behavior.

### 2.5 Technology Stack

- Python 3.12+
- FastAPI + Uvicorn (ASGI server)
- Pydantic (configuration validation and API request/response models)
- SQLite (document and chunk storage)
- FAISS (dense vector index with flat inner product search)
- Tantivy via tantivy-py (sparse lexical index with BM25 scoring, stemming, tokenization)
- FastText (`cc.en.300.bin` — 300-dimensional Common Crawl embeddings)
- PyYAML (configuration file parsing)
- httpx (HTTP client library)
- uv (package manager)
- just (task runner)

### 2.6 Component Interaction Diagram

```
FastAPI Routes (api/)
    │
    ├──► API Models (api/models/) — Pydantic request/response validation
    │
    ▼
  Orchestration (minirag/orchestration.py)
    │
    ├──► Chunker (text → chunks)
    ├──► Embeddings (text → vectors, normalized to unit length)
    │
    ├──► Storage (interface)           ──► SQLiteStorage
    │       insert_document / insert_chunk / get_chunk / destroy
    │
    ├──► DenseRetrieval (interface)    ──► FAISSDense
    │       index / search / destroy
    │
    ├──► SparseRetrieval (interface)   ──► TantivySparse
    │       index / search / destroy
    │
    └──► HybridMerge (pure function)
            normalize + alpha-weight + re-rank
```

## 3. Project Structure

```
src/
├── main.py                            # Entry point (starts uvicorn)
└── minirag/
    ├── __init__.py
    ├── config.py                      # Config class — parses config.yaml, model_dump()
    ├── orchestration.py               # Orchestration layer for indexing and search
    ├── api/                           # FastAPI service layer
    │   ├── __init__.py
    │   ├── app.py                     # FastAPI app creation & lifecycle
    │   ├── routes_index.py            # POST /index, DELETE /index
    │   ├── routes_query.py            # POST /query/dense, /query/sparse, /query/hybrid
    │   ├── routes_info.py            # GET /health, GET /info, POST /shutdown
    │   ├── utils.py                   # Response envelope helpers + ensure_healthy() guard
    │   └── models/                    # Pydantic request/response models
    │       ├── __init__.py
    │       ├── index.py               # IndexRequest, IndexResponse
    │       ├── query.py               # QueryRequest, QueryResponse
    │       └── info.py                # HealthResponse, InfoResponse, ShutdownResponse
    ├── search/                        # Search utilities
    │   ├── __init__.py
    │   ├── hybrid.py                  # Score normalization & re-ranking (pure function)
    │   ├── embeddings.py              # FastText embedding generation + unit normalization
    │   └── types.py                   # SearchResult dataclass
    ├── storage/                       # Storage abstraction
    │   ├── __init__.py
    │   ├── interface.py               # Storage interface definition
    │   └── sqlite.py                  # SQLiteStorage implementation
    ├── retrieval/                     # Retrieval abstractions
    │   ├── __init__.py
    │   ├── dense_interface.py         # DenseRetrieval interface definition
    │   ├── sparse_interface.py        # SparseRetrieval interface definition
    │   ├── faiss_dense.py             # FAISSDense implementation
    │   └── tantivy_sparse.py          # TantivySparse implementation
    ├── ingestion/                     # Document processing
    │   ├── __init__.py
    │   └── chunker.py                 # Word-based chunking
    └── clients/                       # HTTP clients for external consumers
        ├── __init__.py
        ├── base.py                    # Shared HTTP logic (host, port, error handling)
        ├── indexing.py                # IndexingClient (index doc, destroy index)
        └── query.py                   # QueryClient (dense, sparse, hybrid search)

scripts/
└── ingest.py                          # Reads data/input/txt/, uses IndexingClient

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
  reload: true
  log_level: "INFO"

data:
  data_dir: "data"

index:
  chunking:
    chunk_size: 300
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

### 4.4 Path Resolution

The `data_dir` in the `DataConfig` serves as the base path. Other components derive their paths from it:

- Input text files: `{data_dir}/input/txt/`
- FastText model: `{data_dir}/models/{model_name}`
- SQLite database: `{data_dir}/storage/{db_filename}`
- FAISS index: `{data_dir}/index/faiss/`
- Tantivy index: `{data_dir}/index/tantivy/`

Components only know their own subdirectory conventions (e.g., the ingestion module knows about `input/txt/`, the embeddings module knows about `models/`). The base `data_dir` comes from the config.

### 4.5 Data Directory Layout

```
data/
├── input/
│   ├── txt/                  # Plain text files for ingestion
│   └── md/                   # Markdown files (future)
├── models/                   # FastText embedding models
│   └── cc.en.300.bin
├── storage/                  # SQLite document/chunk database
│   └── minirag.db
└── index/
    ├── faiss/                # FAISS vector index files
    └── tantivy/              # Tantivy lexical index files
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

#### POST /v1/index

Indexes a single document. The service handles the full pipeline: store document → chunk → store chunks → embed → index in dense and sparse indices. The response is returned only after all steps complete.

Empty or whitespace-only document text is rejected with HTTP 422 before any processing begins.

If any step in the indexing pipeline fails, the service returns an error immediately. No rollback is performed; partial state may remain. Use `DELETE /v1/index` to clean up before re-indexing.

**Request:**

```json
{
  "document": "the full text content of the document..."
}
```

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

#### DELETE /v1/index

Destroys the entire index across all three backends (Storage, DenseRetrieval, SparseRetrieval).

**Request:** No body.

**Response:**

```json
{
  "status": 200,
  "data": { "message": "index destroyed" }
}
```

#### POST /v1/query/dense

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
      { "text": "matched chunk text...", "score": 0.87 },
      { "text": "another chunk...", "score": 0.74 }
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

Scores are normalized between 0 and 1, with higher values indicating greater relevance. For dense search, scores are cosine similarities computed via inner product on unit-normalized embeddings. An empty results list is returned when no matches are found or when the index is empty — this is not an error.

#### POST /v1/query/sparse

Performs sparse lexical search using Tantivy's BM25 scoring. Same request and response format as `/v1/query/dense`.

Scores are BM25 relevance scores normalized to [0, 1] by dividing by the maximum score in the result set.

#### POST /v1/query/hybrid

Performs hybrid search combining dense and sparse results with score normalization, alpha-weighted merging, and re-ranking. Same request and response format as `/v1/query/dense`.

The balance between dense and sparse results is controlled by the `search.hybrid.alpha` configuration parameter (0.0 = pure sparse/lexical, 1.0 = pure dense/vector).

**Hybrid merge behavior for edge cases:**

- If a chunk appears in only one result set (dense or sparse but not both), its missing score is treated as 0.0.
- If a result set is empty, only the other set's scores contribute (scaled by the respective alpha weight).
- If both result sets are empty, an empty results list is returned.
- Querying an empty index returns an empty results list (not an error).

### 5.5 Pydantic API Models

All API request and response payloads are defined as Pydantic models in `api/models/`. Each file maps to a route group:

- `api/models/index.py` — `IndexRequest` (document field, validates non-empty text), `IndexResponse` (document_id, chunks_indexed, chunk_ids).
- `api/models/query.py` — `QueryRequest` (query string, top_k as positive integer), `QueryResponse` (results list).
- `api/models/info.py` — `HealthResponse`, `InfoResponse`, `ShutdownResponse`.

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

- POST /v1/index
- DELETE /v1/index
- POST /v1/query/dense
- POST /v1/query/sparse
- POST /v1/query/hybrid
- POST /v1/shutdown

**Unguarded endpoints** — these are always available regardless of app state:

- GET /v1/health (reports the current app state)
- GET /v1/info (returns the configuration)

The health endpoint reflects the current app state in its response. When the state is `"healthy"`, it returns HTTP 200. When the state is `"shutting_down"`, it returns HTTP 503 with the state value in the response body.

## 6. Storage Layer

### 6.1 Storage Interface

The Storage interface (`storage/interface.py`) defines the contract for document and chunk persistence:

- `insert_document(content: str) -> int` — stores the full document text and returns an auto-assigned document ID.
- `insert_chunk(document_id: int, content: str) -> int` — stores a chunk with a foreign key reference to its document and returns an auto-assigned chunk ID.
- `get_document(document_id: int) -> str` — retrieves document content by ID.
- `get_chunk(chunk_id: int) -> tuple[int, str]` — retrieves a chunk by ID, returning (document_id, chunk_content).
- `close() -> None` — closes the underlying database connection.
- `destroy() -> None` — wipes all stored data.

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

The SQLite database file is stored at `{data_dir}/storage/{db_filename}`.

Document and chunk IDs are assigned automatically by SQLite's autoincrement mechanism. ID assignment is fully internal to the service and transparent to clients.

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

1. Accept two result sets: `dense_results` and `sparse_results`, each as `list[tuple[chunk_id, score]]`.
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

## 10. Ingestion Pipeline

### 10.1 Document Flow

1. Text files are placed in `{data_dir}/input/txt/`.
2. The `scripts/ingest.py` helper script reads all `.txt` files from that directory.
3. For each file, the script uses the `IndexingClient` to POST the document text to the service.
4. The service receives the text and the orchestration layer runs the full indexing pipeline:
   a. Store the full document in Storage → get `document_id`.
   b. Chunk the text (word-based, configurable size and overlap) → get list of chunks.
   c. Store each chunk in Storage → get `chunk_id` for each.
   d. Generate embeddings for all chunks (FastText, unit-normalized).
   e. Index each chunk in DenseRetrieval (chunk_id + embedding).
   f. Index each chunk in SparseRetrieval (chunk_id + chunk text).
   g. Return `document_id` and list of `chunk_ids`.

### 10.2 Chunking Strategy

Word-based chunking is implemented in `ingestion/chunker.py`:

- **Chunk size:** 300 words (configurable via `index.chunking.chunk_size`).
- **Overlap:** 30% (configurable via `index.chunking.overlap`).
- Words are counted by whitespace splitting.
- Empty or whitespace-only input text is rejected with a `ValueError`.
- Invalid chunk parameters (non-positive chunk size, overlap outside [0.0, 1.0), overlap yielding non-positive step) are rejected with a `ValueError`.

### 10.3 Ingestion Behavior

- The `just ingest` target destroys the existing index before indexing.
- Files are sorted alphanumerically by filename for deterministic, reproducible ordering.
- Files are indexed one at a time, with progress reported to the console (which file is currently being indexed).
- If any file fails to index, the script continues processing remaining files and tracks the failure count. At the end, it exits with code 1 if any files failed.
- If any step within the indexing pipeline fails for a single file, the error is logged and the script moves on to the next file. No automatic rollback of partial state is performed.
- There are no update or deduplication operations — only index, destroy, and query.

### 10.4 Indexing Error Behavior

The ingestion script (`scripts/ingest.py`) continues processing all files even when individual files fail. It tracks success and failure counts, reports a summary at the end, and exits with code 1 if any files failed. This follows the general "continue and count failures" pattern: the user can inspect the log to see which files failed and why, then fix the issues and re-run `just ingest`.

## 11. Clients

### 11.1 Base Client

`clients/base.py` provides shared HTTP logic:

- Reads host and port from the service config.
- Checks the `/v1/health` endpoint before any operation — if the service is not healthy, the client aborts with an exception.
- Handles HTTP errors and surfaces them as exceptions.

### 11.2 IndexingClient

`clients/indexing.py` provides:

- `index_document(text)` — POSTs a document to `/v1/index`.
- `destroy_index()` — sends DELETE to `/v1/index`.

### 11.3 QueryClient

`clients/query.py` provides:

- `search_dense(query, top_k)` — sends POST to `/v1/query/dense`.
- `search_sparse(query, top_k)` — sends POST to `/v1/query/sparse`.
- `search_hybrid(query, top_k)` — sends POST to `/v1/query/hybrid`.

All three methods return results in the same format.

## 12. SearchResult Type

All search results throughout the system use a consistent `SearchResult` type defined as a dataclass in a shared location (`search/types.py`):

```python
@dataclass
class SearchResult:
    chunk_id: int
    text: str
    score: float
```

This type is used by:

- The orchestration layer's search methods (return `list[SearchResult]`).
- The hybrid merge function (accepts and returns `list[SearchResult]`).
- The client methods (return `list[SearchResult]` parsed from JSON).
- The API response serialization (converts to `{"text": ..., "score": ...}`).

Retrieval interfaces return `list[tuple[int, float]]` (chunk_id, score). The orchestration layer resolves chunk IDs to text via the Storage layer and constructs `SearchResult` objects.

## 13. Just Targets

| Target | Description |
|--------|-------------|
| `just init` | Initialize environment: create directories, install dependencies via `uv sync`, download FastText model to `{data_dir}/models/`, copy `config.yaml.template` to `config.yaml` if it does not exist |
| `just start` | Start the FastAPI service in the foreground (Ctrl+C to stop). Uvicorn binds to the configured host and port with reload behavior controlled by config |
| `just stop` | Shut down the running service by calling the `/v1/shutdown` endpoint |
| `just status` | Check if the service is running by hitting `/v1/health`. If running, display the full configuration from `/v1/info`. If not, display "service is not running" |
| `just ingest` | Destroy the existing index, then ingest all `.txt` files from `{data_dir}/input/txt/` via the `IndexingClient`. Shows progress per file. Fails hard on any error |
| `just destroy` | Remove the virtual environment |
| `just help` | Show all available commands |

The existing `just run` target is replaced by `just start` for the service. Existing CI targets (`just ci`, `just ci-quiet`, etc.) remain unchanged.

## 14. Error Handling

### 14.1 Principles

- **Fail fast** — if something is wrong, report it immediately and stop.
- **No error masking** — no degraded states, no silent fallbacks, no default values.
- **Exceptions bubble up** — business logic raises exceptions with descriptive messages. Route handlers catch them and wrap them in the error response envelope.
- **Internal error messages are exposed as-is** — no sanitization or rewriting for the client. This is a minimalist system.
- **No automatic rollback** — if an indexing step fails partway through, partial state may remain. Use `DELETE /v1/index` to clean up.

### 14.2 Startup Failures

The service refuses to start if:

- `config.yaml` is missing.
- Configuration validation fails (missing keys, wrong types).
- The FastText model file does not exist.
- SQLite database cannot be initialized.
- FAISS index cannot be initialized.
- Tantivy index cannot be initialized.

### 14.3 Runtime Errors

All runtime errors (FAISS failures, Tantivy failures, SQLite failures, embedding failures, etc.) are caught by route handlers and returned as error responses with HTTP 500 and the exception message.

## 15. Logging

- All logging goes through Python's standard `logging` module — never `print()`. This applies to both `src/` and `scripts/`.
- The log level is configurable via `service.log_level` in `config.yaml`.
- The committed template defaults to `INFO`. Developers can switch to `DEBUG` locally.
- All errors, warnings, info, and debug messages use the logger.

## 16. Testing

### 16.1 Current Requirements

- Foundational components must have unit tests from the start: config parsing, chunker, hybrid merge logic, response utilities.
- The CI pipeline enforces 80% test coverage.
- Tests run with `just test` (unit tests) and `just test-coverage` (with threshold enforcement).

### 16.2 Test Configuration

- pytest with randomized test order (pytest-randomly).
- 30-second timeout per test (pytest-timeout).
- Async support via pytest-asyncio.

## 17. CI Pipeline

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

## 18. Future To-Do

The following items are out of scope for the first iteration but planned for future work:

1. **LLM generation layer** — Send retrieved chunks along with the user's query to an LLM to produce synthesized answers (completing the "G" in RAG).
2. **Markdown file support** — Support `.md` files in addition to `.txt` for ingestion (from `{data_dir}/input/md/`).
3. **Increase test coverage to 90%** — Tighten test coverage requirements once the design stabilizes.
4. **Index lifecycle management** — Detect configuration changes that invalidate the existing index (e.g., embedding model, chunk size) and trigger or recommend a rebuild.
5. **CORS middleware** — Add configurable Cross-Origin Resource Sharing middleware for browser-based clients.
6. **Uvicorn config file watching** — Optionally watch `config.yaml` for changes and auto-restart the service (with awareness that index invalidation may be required).
7. **Per-document rollback** — On indexing failure, automatically roll back partial state across all three backends.
8. **Idempotent indexing** — Detect duplicate documents via content hashing and skip re-indexing.

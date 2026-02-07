# mini-rag Specification

**Version:** 1.0
**Status:** Draft
**Date:** 2026-02-07

## 1. Overview

mini-rag is a minimalist Retrieval-Augmented Generation (RAG) system implemented as a FastAPI service. It provides document indexing and retrieval through vector similarity search, lexical (full-text) search, and hybrid search combining both approaches. The system is fully configuration-driven, with no hardcoded default values anywhere in the codebase.

In its first iteration, mini-rag focuses exclusively on retrieval. The generation layer (sending retrieved chunks to an LLM for answer synthesis) is planned for a future iteration.

## 2. Architecture

### 2.1 High-Level Design

mini-rag follows a modular client-server architecture:

- A **FastAPI service** acts as the core, owning the index, handling chunking, embedding, storage, and search.
- **Python clients** (`IndexingClient`, `QueryClient`) communicate with the service over HTTP, providing a clean programmatic interface for external scripts and tools.
- **Helper scripts** (e.g., the ingestion script) use the clients to interact with the system.

### 2.2 Key Components

- **Config** — Pydantic-based configuration loader, parsing `config.yaml` with strict validation and no optional values.
- **FastAPI Service** — REST API with versioned endpoints (`/v1/...`), running on Uvicorn with configurable reload.
- **ChromaDB Facade** — Wraps ChromaDB using the facade pattern, delegating vector and lexical queries directly and implementing hybrid search merge logic.
- **FastText Embeddings** — Custom `EmbeddingFunction` wrapper for ChromaDB using Facebook's FastText library for local, portable dense embeddings.
- **Chunker** — Word-based text chunking with configurable chunk size and overlap.
- **Hybrid Merge** — Score normalization and re-ranking logic for combining vector and lexical search results using a configurable alpha weight.
- **Clients** — HTTP clients (`IndexingClient`, `QueryClient`) with health-check-before-operation behavior.

### 2.3 Technology Stack

- Python 3.12+
- FastAPI + Uvicorn (ASGI server)
- Pydantic (configuration validation)
- ChromaDB with `PersistentClient` (local, in-process, no external server)
- FastText (`cc.en.300.bin` — 300-dimensional Common Crawl embeddings)
- PyYAML (configuration file parsing)
- uv (package manager)
- just (task runner)

## 3. Project Structure

```
src/
├── main.py                            # Entry point (starts uvicorn)
└── minirag/
    ├── __init__.py
    ├── config.py                      # Config class — parses config.yaml
    ├── server/                        # FastAPI service layer
    │   ├── __init__.py
    │   ├── app.py                     # FastAPI app creation & lifecycle
    │   ├── routes_index.py            # POST /index, DELETE /index
    │   ├── routes_query.py            # POST /query/vector, /query/lexical, /query/hybrid
    │   ├── routes_admin.py            # GET /health, GET /info, POST /shutdown
    │   └── utils.py                   # Response envelope helper methods
    ├── search/                        # Search & retrieval layer
    │   ├── __init__.py
    │   ├── facade.py                  # ChromaDB facade (delegates + hybrid merge)
    │   ├── hybrid.py                  # Score normalization & re-ranking logic
    │   └── embeddings.py              # FastText EmbeddingFunction wrapper
    ├── ingestion/                     # Document processing
    │   ├── __init__.py
    │   └── chunker.py                 # Word-based chunking
    └── clients/                       # HTTP clients for external consumers
        ├── __init__.py
        ├── base.py                    # Shared HTTP logic (host, port, error handling)
        ├── indexing.py                # IndexingClient (index doc, destroy index)
        └── query.py                   # QueryClient (vector, lexical, hybrid search)

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

  chromadb:
    persist_dir: "chroma"
    collection_name: "minirag"
    distance_metric: "cosine"
    hnsw_m: 16
    hnsw_construction_ef: 100
    hnsw_search_ef: 10
    hnsw_num_threads: 4
    hnsw_batch_size: 100

search:
  chromadb:
    hybrid_alpha: 0.5
```

### 4.3 Pydantic Model Hierarchy

The configuration is parsed into the following nested Pydantic models:

- `Config` (root)
  - `ServiceConfig` — host, port, reload, log_level
  - `DataConfig` — data_dir
  - `IndexConfig`
    - `ChunkingConfig` — chunk_size, overlap
    - `EmbeddingsConfig` — model_name, dimension
    - `IndexChromaDBConfig` — persist_dir, collection_name, distance_metric, HNSW parameters
  - `SearchConfig`
    - `SearchChromaDBConfig` — hybrid_alpha

### 4.4 Path Resolution

The `data_dir` in the `DataConfig` serves as the base path. Other components derive their paths from it:

- Input text files: `{data_dir}/input/txt/`
- FastText model: `{data_dir}/models/{model_name}`
- ChromaDB persistence: `{data_dir}/{persist_dir}/`

Components only know their own subdirectory conventions (e.g., the ingestion module knows about `input/txt/`, the embeddings module knows about `models/`). The base `data_dir` comes from the config.

### 4.5 Startup Validation

At service startup, the `Config` class performs full validation:

- All required keys are present and have correct types (enforced by Pydantic).
- The FastText model file exists at the configured path.
- The `data_dir` is accessible and writable.
- If any validation fails, the service refuses to start with a clear error message (fail-fast).

## 5. REST API

### 5.1 General Design

- All endpoints are prefixed with `/v1`.
- All endpoints are synchronous (query-and-wait) — the response is returned only after the operation completes.
- All request bodies are JSON.
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

Response construction happens exclusively in route handlers, never in business logic. Helper methods in `server/utils.py` provide `success_response(status, data)` and `error_response(status, message)` for uniform construction.

### 5.3 HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200  | Successful operation |
| 400  | Malformed JSON or unparseable request body |
| 422  | Valid JSON but missing or invalid fields |
| 500  | Internal server error (ChromaDB failure, FastText failure, etc.) |
| 503  | Service is shutting down |

### 5.4 Endpoints

#### GET /v1/health

Returns the health status of the service.

**Request:** No body.

**Response:**

```json
{
  "status": 200,
  "data": { "status": "healthy" }
}
```

During shutdown:

```json
{
  "status": 503,
  "data": { "status": "shutting_down" }
}
```

#### GET /v1/info

Returns the complete service configuration.

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

Initiates a graceful shutdown. The health status changes to `"shutting_down"` before the process exits. Any endpoint hit during shutdown returns HTTP 503.

**Request:** No body.

**Response:**

```json
{
  "status": 200,
  "data": { "message": "shutdown initiated" }
}
```

#### POST /v1/index

Indexes a single document. The service handles chunking, embedding, and storing in ChromaDB. The response is returned only after all chunks are indexed.

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
  "data": { "chunks_indexed": 5 }
}
```

#### DELETE /v1/index

Destroys the entire index.

**Request:** No body.

**Response:**

```json
{
  "status": 200,
  "data": { "message": "index destroyed" }
}
```

#### POST /v1/query/vector

Performs vector similarity search using dense embeddings.

**Request:**

```json
{
  "query": "search terms here",
  "top_k": 5
}
```

**Response:**

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

Scores are normalized between 0 and 1, with higher values indicating greater relevance.

#### POST /v1/query/lexical

Performs full-text lexical search. Same request and response format as `/v1/query/vector`.

#### POST /v1/query/hybrid

Performs hybrid search combining vector and lexical results with score normalization, alpha-weighted merging, and re-ranking. Same request and response format as `/v1/query/vector`.

The balance between vector and lexical results is controlled by the `hybrid_alpha` configuration parameter (0.0 = pure lexical, 1.0 = pure vector).

## 6. Search Architecture

### 6.1 ChromaDB Integration

mini-rag uses ChromaDB in `PersistentClient` mode — fully local, in-process, no external server required. Data persists to disk between service restarts.

ChromaDB provides:

- **Vector search** via `collection.query()` — uses HNSW index with cosine distance for dense retrieval.
- **Full-text search** via `collection.get()` with `where_document` — uses SQLite FTS5 for lexical retrieval.

### 6.2 ChromaDB Facade

The facade pattern (`search/facade.py`) provides a clean interface between the FastAPI routes and ChromaDB:

- `search_vector(query, top_k)` — delegates directly to ChromaDB's `collection.query()`.
- `search_lexical(query, top_k)` — delegates directly to ChromaDB's `collection.get()` with `where_document`.
- `search_hybrid(query, top_k)` — calls both vector and lexical search, then invokes the hybrid merge logic to combine results.

All three methods return results in the same format, so upstream consumers handle them uniformly.

### 6.3 Hybrid Search Merge

Since ChromaDB's local `PersistentClient` does not provide native hybrid search with result fusion, mini-rag implements its own merge in `search/hybrid.py`:

1. Execute vector search and lexical search independently.
2. Normalize scores from both result sets to a 0–1 range.
3. Apply alpha weighting: `final_score = alpha * vector_score + (1 - alpha) * lexical_score`.
4. Re-rank by final score.
5. Return the top-K results.

### 6.4 FastText Embeddings

Dense embeddings are generated using Facebook's FastText library with the `cc.en.300.bin` model (300-dimensional, trained on Common Crawl, English). The embedding wrapper (`search/embeddings.py`) implements ChromaDB's `EmbeddingFunction` interface, allowing ChromaDB to use FastText for both indexing and query embedding.

The FastText model is downloaded during `just init` and stored at `{data_dir}/models/{model_name}`.

## 7. Ingestion Pipeline

### 7.1 Document Flow

1. Text files are placed in `{data_dir}/input/txt/`.
2. The `scripts/ingest.py` helper script reads all `.txt` files from that directory.
3. For each file, the script uses the `IndexingClient` to POST the document text to the service.
4. The service receives the text, chunks it (word-based, 300 words, 30% overlap), generates embeddings, and stores the chunks in ChromaDB.

### 7.2 Chunking Strategy

Word-based chunking is implemented in `ingestion/chunker.py`:

- **Chunk size:** 300 words (configurable via `index.chunking.chunk_size`).
- **Overlap:** 30% (configurable via `index.chunking.overlap`).
- Words are counted by whitespace splitting.

### 7.3 Ingestion Behavior

- The `just ingest` target destroys the existing index before indexing.
- Files are indexed one at a time, with progress reported to the console (which file is currently being indexed).
- If any file fails to index, the process stops immediately (fail-hard) — no continuing with remaining files.
- There are no update operations — only index, destroy, and query.

## 8. Clients

### 8.1 Base Client

`clients/base.py` provides shared HTTP logic:

- Reads host and port from the service config.
- Checks the `/v1/health` endpoint before any operation — if the service is not healthy, the client aborts with an exception.
- Handles HTTP errors and surfaces them as exceptions.

### 8.2 IndexingClient

`clients/indexing.py` provides:

- `index_document(text)` — POSTs a document to `/v1/index`.
- `destroy_index()` — sends DELETE to `/v1/index`.

### 8.3 QueryClient

`clients/query.py` provides:

- `search_vector(query, top_k)` — POSTs to `/v1/query/vector`.
- `search_lexical(query, top_k)` — POSTs to `/v1/query/lexical`.
- `search_hybrid(query, top_k)` — POSTs to `/v1/query/hybrid`.

All three methods return results in the same format.

## 9. Just Targets

| Target | Description |
|--------|-------------|
| `just init` | Initialize environment: create directories, install dependencies via `uv sync`, download FastText model to `{data_dir}/models/`, copy `config.yaml.template` to `config.yaml` if it does not exist |
| `just start` | Start the FastAPI service in the foreground (Ctrl+C to stop). Uvicorn binds to the configured host and port with reload behavior controlled by config |
| `just stop` | Shut down the running service by calling the `/v1/shutdown` endpoint |
| `just status` | Check if the service is running by hitting `/v1/health`. If running, display the full configuration from `/v1/info`. If not, display "service is not running" |
| `just ingest` | Destroy the existing index, then ingest all `.txt` files from `{data_dir}/input/txt/` via the `IndexingClient`. Shows progress per file. Fails hard on any error |
| `just destroy` | Remove the virtual environment |
| `just help` | Show all available commands |

Existing CI targets (`just ci`, `just ci-quiet`, etc.) remain unchanged.

## 10. Error Handling

### 10.1 Principles

- **Fail fast** — if something is wrong, report it immediately and stop.
- **No error masking** — no degraded states, no silent fallbacks, no default values.
- **Exceptions bubble up** — business logic raises exceptions with descriptive messages. Route handlers catch them and wrap them in the error response envelope.
- **Internal error messages are exposed as-is** — no sanitization or rewriting for the client. This is a minimalist system.

### 10.2 Startup Failures

The service refuses to start if:

- `config.yaml` is missing.
- Configuration validation fails (missing keys, wrong types).
- The FastText model file does not exist.
- ChromaDB cannot be initialized.

### 10.3 Runtime Errors

All runtime errors (ChromaDB failures, embedding failures, etc.) are caught by route handlers and returned as error responses with HTTP 500 and the exception message.

## 11. Logging

- All logging goes through Python's standard `logging` module — never `print()`.
- The log level is configurable via `service.log_level` in `config.yaml`.
- The committed template defaults to `INFO`. Developers can switch to `DEBUG` locally.
- All errors, warnings, info, and debug messages use the logger.

## 12. Testing

### 12.1 Current Requirements

- Foundational components must have unit tests from the start: config parsing, chunker, hybrid merge logic, response utilities.
- The CI pipeline enforces 80% test coverage.
- Tests run with `just test` (unit tests) and `just test-coverage` (with threshold enforcement).

### 12.2 Test Configuration

- pytest with randomized test order (pytest-randomly).
- 30-second timeout per test (pytest-timeout).
- Async support via pytest-asyncio.

## 13. CI Pipeline

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

## 14. Future To-Do

The following items are out of scope for the first iteration but planned for future work:

1. **Custom document IDs for traceability** — Provide our own document IDs during indexing to enable tracing chunks back to source files.
2. **LLM generation layer** — Send retrieved chunks along with the user's query to an LLM to produce synthesized answers (completing the "G" in RAG).
3. **Markdown file support** — Support `.md` files in addition to `.txt` for ingestion (from `{data_dir}/input/md/`).
4. **Increase test coverage to 90%** — Tighten test coverage requirements once the design stabilizes.
5. **Index lifecycle management** — Detect configuration changes that invalidate the existing index (e.g., embedding model, chunk size) and trigger or recommend a rebuild.
6. **CORS middleware** — Add configurable Cross-Origin Resource Sharing middleware for browser-based clients.
7. **Uvicorn config file watching** — Optionally watch `config.yaml` for changes and auto-restart the service (with awareness that index invalidation may be required).

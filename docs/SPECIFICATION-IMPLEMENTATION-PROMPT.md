 Prompt for AI Coding Agent

  Read and internalize every file in this repository before doing anything:

  1. CLAUDE.md (development rules — symlinked to AGENTS.md)
  2. README.md (project overview, usage, API summary)
  3. docs/SPECIFICATION.md (full technical spec v2.2)
  4. docs/SPECIFICATION-DATA-FLOW.md (data flow, sequence diagrams, type contracts)
  5. pyproject.toml (dependencies, tool config)
  6. justfile (build targets)
  7. config.yaml.template (if it exists) or the config structure from the spec

  Then implement the mini-rag application according to the specifications. The repo
  has full tooling already set up but only a stub main.py — all application code
  needs to be written.

  ## Implementation order

  Work bottom-up, one layer at a time. After each layer, run `just ci-quiet` and
  fix any issues before proceeding. Commit after each passing layer.

  ### Layer 1: Foundation
  - config.yaml.template (from spec section 4.2)
  - src/minirag/config.py (Pydantic config hierarchy from spec section 4.3)
  - Update justfile: add `init` model download, `start`, `stop`, `status`, `ingest`
    targets per spec section 13
  - Update pyproject.toml: add runtime dependencies (fastapi, uvicorn, pydantic,
    pyyaml, httpx, faiss-cpu, tantivy, fasttext-wheel)

  ### Layer 2: Core components (no dependencies between them)
  - src/minirag/ingestion/chunker.py (word-based chunking, spec section 10.2)
  - src/minirag/search/types.py (SearchResult dataclass, spec section 12)
  - src/minirag/search/hybrid.py (pure merge function, spec section 9)
  - src/minirag/search/embeddings.py (FastText wrapper, spec section 7.3)
  - src/minirag/api/utils.py (response envelope + ensure_healthy guard, spec 5.2/5.6)

  ### Layer 3: Storage and retrieval (depend on interfaces)
  - src/minirag/storage/interface.py (Storage ABC, spec section 6.1)
  - src/minirag/storage/sqlite.py (SQLiteStorage, spec section 6.2)
  - src/minirag/retrieval/dense_interface.py (DenseRetrieval ABC, spec section 7.1)
  - src/minirag/retrieval/faiss_dense.py (FAISSDense, spec section 7.2)
  - src/minirag/retrieval/sparse_interface.py (SparseRetrieval ABC, spec section 8.1)
  - src/minirag/retrieval/tantivy_sparse.py (TantivySparse, spec section 8.2)

  ### Layer 4: Orchestration
  - src/minirag/orchestration.py (coordinates all backends, spec section 2.3)

  ### Layer 5: API layer
  - src/minirag/api/models/index.py (IndexRequest/IndexResponse)
  - src/minirag/api/models/query.py (QueryRequest/QueryResponse)
  - src/minirag/api/models/info.py (HealthResponse/InfoResponse/ShutdownResponse)
  - src/minirag/api/routes_info.py (health, info, shutdown)
  - src/minirag/api/routes_index.py (POST/DELETE /v1/index)
  - src/minirag/api/routes_query.py (GET dense/sparse/hybrid)
  - src/minirag/api/app.py (FastAPI app factory + lifecycle)
  - src/main.py (uvicorn entry point)

  ### Layer 6: Clients and scripts
  - src/minirag/clients/base.py (shared HTTP client logic)
  - src/minirag/clients/indexing.py (IndexingClient)
  - src/minirag/clients/query.py (QueryClient)
  - scripts/ingest.py (file ingestion script)

  ### Layer 7: Tests
  - Unit tests for: config parsing, chunker, hybrid merge, response utilities
  - Target 80% coverage as required by spec section 16

  ## Critical rules (from CLAUDE.md)
  - Never assume default values — be explicit everywhere
  - All Python execution via `uv run` only
  - Dependencies via `uv sync` / pyproject.toml only
  - Never create Python files in the project root
  - Run `just ci-quiet` after every layer to validate
  - All logging via Python logging module, never print()
  - No AI attribution in commits
  - Stage files explicitly (never `git add -A` or `git add .`)
  - Push after every commit

  ## Key spec constraints to watch for
  - Config: every Pydantic field is required, no optionals anywhere
  - Embeddings: must validate dimension at load time (fail-fast)
  - FAISS: uses IndexIDMap wrapping IndexFlatIP, all vectors unit-normalized
  - Tantivy: BM25 scores normalized to [0,1] by dividing by max score
  - Hybrid merge: alpha must be validated in [0.0, 1.0]
  - API responses: uniform envelope format {"status": N, "data": {...}}
  - Error responses: raw exception messages, no sanitization
  - Ingestion: fail immediately on first error, log the error before propagating
  - Startup: fail-fast on any initialization error
  - All __init__.py files needed for every package


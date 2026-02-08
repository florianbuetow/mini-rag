# MiniRAG + MCP

A minimalistic hybrid search engine for your `.md` and `.txt` documents that runs locally without any cloud services and provides a fast MCP server for searching your documents with hybrid search (lexical + vector) for great search quality. This gives your AI agents super fast access to custom knowledge. Think books on refactoring, prompting, system architecture, or information that you want a personal assistant (like Claude) to have access to when generating stuff for you. Unlimited possibilities.

Under the hood, MiniRAG uses Facebook's FastText for local embeddings, FAISS for dense vector search, Tantivy for BM25 lexical search, and SQLite for document and chunk storage — all running in-process with no external services required. The system is fully configuration-driven with no hardcoded defaults.

| Document | Description |
|----------|-------------|
| [Specification](docs/SPECIFICATION.md) | Full technical specification |
| [Data Flow](docs/SPECIFICATION-DATA-FLOW.md) | Indexing and search data flow |
| [MCP Server](mcp/README.md) | MCP server setup and client configuration |

## Prerequisites

- **Python 3.12+**
- **uv** — Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **just** — Command runner ([install](https://github.com/casey/just#installation))

## Project Structure

```
.
├── src/                    # Application source code
│   └── minirag/
├── tests/                  # Unit tests
├── tests_e2e/              # End-to-end tests
├── scripts/                # Utility scripts (md2txt, ingest, search)
├── prompts/                # Prompt templates
├── docs/                   # Specification and data flow docs
├── config/                 # Semgrep rules
├── data/
│   ├── input/
│   │   ├── md/             # Markdown source documents
│   │   └── txt/            # Plain text files (ingested by the service)
│   ├── models/             # FastText embedding model
│   ├── storage/            # SQLite document/chunk store
│   └── index/
│       ├── faiss/          # Dense vector index
│       └── tantivy/        # Sparse lexical index
├── config.yaml             # Local configuration (gitignored)
├── config.yaml.template    # Configuration template
├── justfile                # Command recipes
└── pyproject.toml          # Project metadata and dependencies
```

## Setup

```bash
just init
```

Creates all directories shown above, installs dependencies via `uv sync --all-extras`, downloads the FastText model to `data/models/`, and copies `config.yaml.template` to `config.yaml` if it does not already exist.

## Configuration

All configuration lives in `config.yaml` at the project root. A template (`config.yaml.template`) is provided and copied during `just init`. The file is gitignored.

Key sections: **service** (host, port, log level), **data** (base directory), **index** (chunking, embeddings, SQLite, FAISS, Tantivy), **search** (hybrid alpha weighting).

## Usage

| Command | Description |
|---------|-------------|
| `just start` | Start the service (foreground, Ctrl+C to stop) |
| `just stop` | Stop the running service |
| `just status` | Show service configuration or "not running" |
| `just md2txt` | Convert markdown files to plain text |
| `just ingest` | Destroy index and re-ingest all text files |
| `just search` | Interactive search query loop |
| `just destroy` | Remove virtual environment |

### Document Pipeline

1. Place `.md` files in `data/input/md/` (subdirectories supported)
2. Run `just md2txt` — converts to `.txt` in `data/input/txt/`, mirroring the subdirectory structure
3. Run `just start` to start the service
4. Run `just ingest` — recursively finds all `.txt` files under `data/input/txt/` and indexes them
5. Run `just search` to query the index interactively

Both `md2txt` and `ingest` scan subdirectories recursively and skip symbolic links.

## API

FastAPI auto-generates interactive docs at `/docs` (Swagger) and `/redoc` (ReDoc) when the service is running.

All endpoints are prefixed with `/v1` and accept/return JSON.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/health` | Health check |
| GET | `/v1/info` | Full service configuration |
| POST | `/v1/shutdown` | Graceful shutdown |
| POST | `/v1/index` | Index a single document |
| DELETE | `/v1/index` | Destroy the entire index |
| GET | `/v1/query/dense` | Dense vector similarity search |
| GET | `/v1/query/sparse` | Sparse lexical (BM25) search |
| GET | `/v1/query/hybrid` | Hybrid search (dense + sparse) |

## Search Architecture

MiniRAG uses three backend components, each accessible through an abstraction interface:

- **SQLite** — Document and chunk persistence
- **FAISS** — Dense vector index using `IndexFlatIP` with unit-normalized embeddings (cosine similarity, scores in [0, 1])
- **Tantivy** — Sparse lexical index with BM25 scoring, stemming, and tokenization (scores normalized to [0, 1])

All three persist under `data/` and are loaded on startup.

### Hybrid Search Tuning

The `alpha` parameter under `search.hybrid` controls the dense/sparse balance:

- `0.0` — Pure sparse (BM25 only)
- `0.5` — Equal weight (default)
- `1.0` — Pure dense (semantic only)

## Development

### Code Quality

| Command | Description |
|---------|-------------|
| `just code-style` | Check code style (read-only) |
| `just code-format` | Auto-fix code style |
| `just code-typecheck` | Type checking (mypy) |
| `just code-lspchecks` | Strict type checking (pyright) |
| `just code-security` | Security checks (bandit) |
| `just code-deptry` | Dependency hygiene |
| `just code-spell` | Spell checking |
| `just code-audit` | Vulnerability scanning |
| `just code-semgrep` | Custom static analysis (semgrep) |
| `just code-stats` | Code statistics |

### Testing

| Command | Description |
|---------|-------------|
| `just test` | Unit tests |
| `just test-e2e` | End-to-end tests (starts service, indexes, searches) |
| `just test-coverage` | Unit tests with coverage (80% threshold) |

### CI

- `just ci` — Run all checks (verbose)
- `just ci-quiet` — Run all checks (silent, fail-fast)

## Resources

- [FastText Common Crawl vectors](https://fasttext.cc/docs/en/crawl-vectors.html) — Pre-trained word embeddings
- [FAISS](https://github.com/facebookresearch/faiss) — Dense vector search library
- [Tantivy](https://github.com/quickwit-oss/tantivy) — Full-text search engine (Rust)
- [tantivy-py](https://github.com/quickwit-oss/tantivy-py) — Python bindings for Tantivy

## License

<!-- Add your license here -->

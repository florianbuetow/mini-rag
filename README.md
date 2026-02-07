# mini-rag

A minimalist Retrieval-Augmented Generation (RAG) system built as a FastAPI service. mini-rag provides document indexing and retrieval through three search modes: dense vector search (semantic similarity via FAISS), sparse lexical search (BM25 keyword matching via Tantivy), and hybrid search combining both with configurable weighting.

The system is fully configuration-driven — no hardcoded default values anywhere. It uses Facebook's FastText for local, portable embeddings, FAISS for dense vector search, Tantivy for BM25 lexical search, and SQLite for document and chunk storage — all running in-process with no external services required.

For the full technical specification, see [docs/SPECIFICATION.md](docs/SPECIFICATION.md).

## Prerequisites

- **Python 3.12+** — Programming language
- **uv** — Python package manager ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
- **just** — Command runner ([installation guide](https://github.com/casey/just#installation))

## Setup

Initialize the project environment:

```bash
just init
```

This will:

- Create necessary directories (reports/, data/models/, etc.)
- Install all dependencies via `uv sync --all-extras`
- Download the FastText embedding model to `data/models/`
- Copy `config.yaml.template` to `config.yaml` if it does not already exist

## Configuration

All configuration lives in `config.yaml` at the project root. A ready-to-go template (`config.yaml.template`) is provided and copied during `just init`. The template contains sensible defaults for all parameters.

The `config.yaml` file is gitignored so you can maintain your own local configuration without affecting others. See the template for all available parameters.

Key configuration sections:

- **service** — Host, port, reload behavior, log level
- **data** — Base data directory
- **index** — Chunking, embeddings, storage (SQLite), FAISS, and Tantivy settings
- **search** — Search behavior including hybrid search alpha weighting

## Usage

### Starting the Service

```bash
just start
```

This starts the FastAPI service in the foreground on the configured host and port (default: `127.0.0.1:7001`). Press Ctrl+C to stop, or use `just stop` from another terminal.

### Checking Service Status

```bash
just status
```

Displays the full service configuration if running, or "service is not running" if not.

### Stopping the Service

```bash
just stop
```

Sends a shutdown request to the running service via the `/v1/shutdown` endpoint.

### Ingesting Documents

Place `.txt` files in `data/input/txt/`, then:

```bash
just ingest
```

This destroys any existing index and re-indexes all text files. Progress is reported per file.

### Available Commands

- `just init` — Initialize development environment
- `just start` — Start the mini-rag service
- `just stop` — Stop the running service
- `just status` — Check service status and configuration
- `just ingest` — Ingest all text files into the index
- `just destroy` — Remove virtual environment
- `just help` — Show all available commands

## API Endpoints

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

## Network Configuration

By default, the service binds to `127.0.0.1` (localhost only), meaning it is only accessible from the local machine. This is the recommended setting for development.

To make the service accessible from other machines on your local network, change the `host` parameter in `config.yaml`:

```yaml
service:
  host: "0.0.0.0"
```

When bound to `0.0.0.0`, the service accepts connections from any network interface. Other machines can reach it using your machine's IP address (e.g., `http://192.168.1.100:7001`). Be aware that this exposes the service to your entire network — there is currently no authentication or CORS middleware.

## Search Architecture

mini-rag uses three independent backend components for storage and retrieval, each accessible through an abstraction interface:

- **SQLite** — Document and chunk persistence (`index.storage` in config)
- **FAISS** — Dense vector index using `IndexFlatIP` with unit-normalized embeddings for cosine similarity (`index.faiss` in config)
- **Tantivy** — Sparse lexical index with BM25 scoring, stemming, and tokenization (`index.tantivy` in config)

All three components persist their data under the `data/` directory and are loaded on service startup.

### Dense Search (FAISS)

FAISS uses `IndexIDMap` wrapping `IndexFlatIP` (inner product). All embeddings are unit-normalized by the FastText embedding module, so inner product equals cosine similarity and scores are naturally in [0, 1]. The FAISS index is configured under `index.faiss` in `config.yaml`.

### Sparse Search (Tantivy)

Tantivy provides BM25-scored full-text search with stemming (English by default) and tokenization. Scores are normalized to [0, 1] by dividing by the maximum score in the result set. Configuration lives under `index.tantivy` in `config.yaml`.

### Hybrid Search Tuning

The `alpha` parameter under `search.hybrid` controls the balance between dense and sparse search in hybrid mode:

- `0.0` — Pure sparse search (BM25 keyword matching only)
- `0.5` — Equal weight to both (default)
- `1.0` — Pure dense search (semantic similarity only)

Start with 0.5 and adjust based on your data and query patterns. Text-heavy queries with specific terms may benefit from a lower alpha, while conceptual or paraphrased queries benefit from a higher alpha.

## Development

### Code Quality

- `just code-style` — Check code style (read-only)
- `just code-format` — Auto-fix code style
- `just code-typecheck` — Run type checking (mypy)
- `just code-lspchecks` — Run strict type checking (pyright)
- `just code-security` — Run security checks (bandit)
- `just code-deptry` — Check dependency hygiene
- `just code-stats` — Generate code statistics
- `just code-spell` — Check spelling
- `just code-audit` — Scan for vulnerabilities
- `just code-semgrep` — Run custom static analysis

### Testing

- `just test` — Run unit tests
- `just test-coverage` — Run tests with coverage (80% threshold)

### CI Pipeline

- `just ci` — Run all validation checks (verbose)
- `just ci-quiet` — Run all checks (silent, fail-fast)

The CI pipeline runs the following steps in order:

1. `init` — Initialize environment
2. `code-format` — Auto-format code
3. `code-style` — Verify formatting
4. `code-typecheck` — Type checking (mypy)
5. `code-security` — Security scan (bandit)
6. `code-deptry` — Dependency hygiene
7. `code-spell` — Spell checking
8. `code-semgrep` — Custom static analysis
9. `code-audit` — Vulnerability scanning
10. `test` — Unit tests
11. `code-lspchecks` — Strict type checking (pyright)

## Project Rules

See [AGENTS.md](AGENTS.md) for detailed development guidelines including:

- Python execution rules (use `uv run` exclusively)
- Git commit guidelines
- Testing requirements
- Project structure conventions

## Resources

- [FastText English word vectors](https://fasttext.cc/docs/en/english-vectors.html) — Pre-trained embeddings documentation
- [FastText Common Crawl vectors](https://fasttext.cc/docs/en/crawl-vectors.html) — Download page for `cc.en.300.bin`
- [FAISS](https://github.com/facebookresearch/faiss) — Dense vector search library
- [Tantivy](https://github.com/quickwit-oss/tantivy) — Full-text search engine (Rust)
- [tantivy-py](https://github.com/quickwit-oss/tantivy-py) — Python bindings for Tantivy

## License

<!-- Add your license here -->

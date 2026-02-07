# mini-rag

A minimalist Retrieval-Augmented Generation (RAG) system built as a FastAPI service. mini-rag provides document indexing and retrieval through three search modes: vector similarity search (dense retrieval), full-text search (sparse retrieval), and hybrid search combining both with configurable weighting.

The system is fully configuration-driven — no hardcoded default values anywhere. It uses Facebook's FastText for local, portable embeddings and ChromaDB for persistent vector and full-text storage, all running in-process with no external services required.

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
- **index** — Chunking, embeddings, and ChromaDB index settings (including HNSW tuning)
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
| POST | `/v1/query/vector` | Vector similarity search |
| POST | `/v1/query/lexical` | Full-text lexical search |
| POST | `/v1/query/hybrid` | Hybrid search (vector + lexical) |

## Network Configuration

By default, the service binds to `127.0.0.1` (localhost only), meaning it is only accessible from the local machine. This is the recommended setting for development.

To make the service accessible from other machines on your local network, change the `host` parameter in `config.yaml`:

```yaml
service:
  host: "0.0.0.0"
```

When bound to `0.0.0.0`, the service accepts connections from any network interface. Other machines can reach it using your machine's IP address (e.g., `http://192.168.1.100:7001`). Be aware that this exposes the service to your entire network — there is currently no authentication or CORS middleware.

## Index Tuning

mini-rag uses ChromaDB with an HNSW (Hierarchical Navigable Small World) index for vector search. The HNSW parameters can be tuned in `config.yaml` under `index.chromadb` to balance search accuracy, speed, and memory usage.

### HNSW Parameters

**`hnsw_m`** (default: 16) — Maximum number of neighbor connections per node in the graph. Higher values improve search recall (accuracy) but increase memory usage and indexing time. Typical range: 12–48. For small datasets, 16 is usually sufficient. For large datasets where recall is critical, consider 32 or higher.

**`hnsw_construction_ef`** (default: 100) — Number of neighbors explored when adding a new vector during index construction. Higher values produce a better-quality graph but slow down indexing. Should be at least `2 * hnsw_m`. Typical range: 100–500. Increase this if you need higher recall and can tolerate slower index builds.

**`hnsw_search_ef`** (default: 10) — Number of neighbors explored during search. Higher values improve recall at the cost of query latency. This is the most useful parameter to tune at query time. Typical range: 10–500. Start low for fast queries and increase if results are not relevant enough.

**`hnsw_num_threads`** (default: 4) — Number of threads used by the HNSW algorithm. Set this based on your available CPU cores. More threads speed up both indexing and search on multi-core machines.

**`hnsw_batch_size`** (default: 100) — Number of vectors held in the brute-force buffer before being transferred to the HNSW index. Smaller values mean vectors are searchable sooner; larger values may improve bulk indexing throughput.

**`distance_metric`** (default: cosine) — The distance function used for vector comparison. Options include `cosine`, `l2` (Euclidean), and `ip` (inner product). Cosine distance is the standard choice for text embeddings. This cannot be changed after index creation — changing it requires destroying and rebuilding the index.

### Hybrid Search Tuning

The `hybrid_alpha` parameter under `search.chromadb` controls the balance between vector and lexical search in hybrid mode:

- `0.0` — Pure lexical search (keyword matching only)
- `0.5` — Equal weight to both (default)
- `1.0` — Pure vector search (semantic similarity only)

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

## License

<!-- Add your license here -->

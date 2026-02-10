# MiniRAG + MCP

A minimalistic hybrid search engine for your `.md` and `.txt` documents that runs locally without any cloud services and provides a fast MCP server for searching your documents with hybrid search (lexical + vector) for great search quality. This gives your AI agents super fast access to custom knowledge. Think books on refactoring, prompting, system architecture, or information that you want a personal assistant (like Claude) to have access to when generating stuff for you. Unlimited possibilities.

### Features

| Feature | Description |
|---------|-------------|
| Lexical Search | Super fast keyword-based search powered by BM25 |
| Semantic Search | Meaning-aware retrieval using dense vector embeddings |
| Hybrid Search | Combines lexical and semantic results with tunable balance |
| Reranking | Superior relevance scoring for hybrid search via cross-encoder models |
| Evaluation | Out-of-the-box support for measuring search quality using your own documents |
| MCP Support | Ships with a ready-to-use MCP server to connect your AI to MiniRAG |

Under the hood, MiniRAG uses Facebook's FastText for local embeddings, FAISS for dense vector search, Tantivy for BM25 lexical search, and SQLite for document and chunk storage — all running in-process with no external services required. The system is fully configuration-driven with no hardcoded defaults.

| Document | Description |
|----------|-------------|
| [Specification](docs/SPECIFICATION.md) | Full technical specification |
| [Data Flow](docs/SPECIFICATION-DATA-FLOW.md) | Indexing and search data flow |
| [MCP Server](mcp/README.md) | MCP server setup and client configuration |

## Design Principles

MiniRAG is a lightweight, text-based search and indexing system. To reduce complexity, deletion of individual documents is not supported. Instead, all ingestible documents are stored in the input folders so they can be re-ingested at any time — whether after editing content, changing the embedding model, or adjusting chunking parameters. Re-indexing is fast: 10,000 documents typically takes less than 10 minutes on a modern laptop.

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
├── docs/                   # Specification and data flow docs
├── config/                 # Semgrep rules
├── data/
│   ├── input/<corpus>/
│   │   ├── md/             # Markdown source documents
│   │   ├── txt/            # Plain text files (ingested by the service)
│   │   └── evals/          # Q&A pairs for retrieval evaluation
│   ├── models/             # FastText embedding model
│   ├── storage/<corpus>/   # SQLite document/chunk store
│   └── index/<corpus>/
│       ├── faiss/          # Dense vector index
│       └── tantivy/        # Sparse lexical index
├── config.yaml             # Local configuration (gitignored)
├── config.yaml.template    # Configuration template
├── justfile                # Command recipes
└── pyproject.toml          # Project metadata and dependencies
```

Each corpus gets its own isolated storage, index, and input directories under `data/`.

## Setup

```bash
just init
```

Creates all directories shown above, installs dependencies via `uv sync --all-extras`, downloads the FastText model to `data/models/`, and copies `config.yaml.template` to `config.yaml` if it does not already exist.

## Configuration

All configuration lives in `config.yaml` at the project root. A template (`config.yaml.template`) is provided and copied during `just init`. The file is gitignored.

Key sections: **service** (host, port, log level), **data** (base directory), **index** (chunking, embeddings, SQLite, FAISS, Tantivy), **search** (hybrid alpha weighting, reranking).

Reranking is disabled by default. To enable it, set `search.reranking.enabled: true` in `config.yaml`. You can also configure the cross-encoder model and the candidate multiplier (how many extra candidates to fetch before reranking).

## Usage

| Command | Description |
|---------|-------------|
| `just start` | Start the service (foreground, Ctrl+C to stop) |
| `just stop` | Stop the running service |
| `just status` | Show service configuration or "not running" |
| `just md2txt` | Convert markdown files to plain text |
| `just ingest <corpus>` | Delete and re-ingest all text files for a corpus |
| `just search <corpus>` | Interactive search query loop for a corpus |
| `just delete <corpus>` | Delete a corpus index and storage |
| `just evaluate <corpus>` | Evaluate retrieval quality using Q&A pairs |
| `just inspect <corpus>` | Inspect document chunks for a corpus |
| `just destroy` | Remove virtual environment |

Corpus names must start with a letter and contain only alphanumeric characters, underscores, or dashes (e.g. `books`, `my-corpus`, `test_data`).

### Document Pipeline

1. Place `.md` files in `data/input/<corpus>/md/` (subdirectories supported)
2. Run `just md2txt` — converts to `.txt` in `data/input/<corpus>/txt/`, mirroring the subdirectory structure
3. Run `just start` to start the service
4. Run `just ingest <corpus>` — recursively finds all `.txt` files under `data/input/<corpus>/txt/` and indexes them
5. Run `just search <corpus>` to query the corpus interactively

Both `md2txt` and `ingest` scan subdirectories recursively and skip symbolic links.

## API

FastAPI auto-generates interactive docs at `/docs` (Swagger) and `/redoc` (ReDoc) when the service is running.

All endpoints accept/return JSON. Data operations are scoped to a corpus via `/v1/corpus/{corpus}/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/health` | Health check |
| GET | `/v1/info` | Full service configuration |
| POST | `/v1/shutdown` | Graceful shutdown |
| POST | `/v1/corpus/{corpus}/index` | Index a single document |
| DELETE | `/v1/corpus/{corpus}/index` | Delete the corpus index |
| POST | `/v1/corpus/{corpus}/query/dense` | Dense vector similarity search |
| POST | `/v1/corpus/{corpus}/query/sparse` | Sparse lexical (BM25) search |
| POST | `/v1/corpus/{corpus}/query/hybrid` | Hybrid search (dense + sparse) |

## Search Architecture

MiniRAG uses three backend components, each accessible through an abstraction interface:

- **SQLite** — Document and chunk persistence
- **FAISS** — Dense vector index using `IndexFlatIP` with unit-normalized embeddings (cosine similarity, scores in [0, 1])
- **Tantivy** — Sparse lexical index with BM25 scoring, stemming, and tokenization (scores normalized to [0, 1])

Each corpus gets its own set of backends, persisted under `data/storage/<corpus>/` and `data/index/<corpus>/`. Backends are created lazily on first access.

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
| `just test-e2e` | End-to-end tests (starts service, indexes, searches, evaluates) |
| `just test-integration` | Integration tests (in-process, requires FastText model) |
| `just test-coverage` | Unit tests with coverage (80% threshold) |

### End-to-End Tests

The e2e test suite (`just test-e2e`) exercises the full pipeline as a real user would:

1. Starts a fresh service instance on a temporary data directory (port 7098).
2. Converts markdown to text via `scripts/md2txt.py`.
3. Verifies that search returns empty results before indexing.
4. Ingests the `test` corpus via `scripts/ingest.py`.
5. Verifies that search returns results in all three modes (sparse, dense, hybrid).
6. Runs evaluation via `scripts/evaluate.py` against Q&A pairs.
7. Asserts that average ROUGE-L recall meets minimum thresholds per mode.
8. Deletes the corpus index and verifies search returns empty results again.

The test is fully self-contained — it creates an isolated temp directory, symlinks the FastText model from your local `data/models/`, and cleans up after itself. No running service is required; the test starts and stops its own.

**Prerequisites:** Run `just init` at least once so the FastText model is downloaded.

```bash
just test-e2e
```

### Retrieval Evaluation

MiniRAG includes a retrieval quality evaluation system that measures how well search results match expected answers using ROUGE-L recall. You can evaluate any corpus that has an evaluation file.

#### Running Evaluation

With the service running:

```bash
just evaluate <corpus>
```

This runs all queries from the evaluation file against the three search modes (sparse, dense, hybrid), computes ROUGE-L recall for each, and writes a JSON report to `reports/<corpus>/evaluation.json`.

#### Creating Evaluations for a New Corpus

To create evaluations for a corpus, create an `evals/` directory inside the corpus input directory and add a `question_answer_pairs.json` file:

```
data/input/<corpus>/evals/question_answer_pairs.json
```

The file must follow this format:

```json
{
  "qa_pairs": [
    {
      "question": "What is the capital of France?",
      "answer": "The capital of France is Paris."
    },
    {
      "question": "Who wrote Romeo and Juliet?",
      "answer": "William Shakespeare wrote Romeo and Juliet."
    }
  ]
}
```

Each entry has:
- **question** — the search query to send to the retrieval system.
- **answer** — the expected reference answer. The retrieved chunks are concatenated and compared to this answer using ROUGE-L recall, which measures how much of the reference answer's content appears in the retrieved text.

**Tips for writing good Q&A pairs:**
- Write questions that a user would naturally ask about the documents.
- Answers should contain the key facts that you expect the retrieval system to surface.
- Include a mix of factual questions (names, dates, numbers) and broader questions (explanations, descriptions).
- Aim for at least 10-20 Q&A pairs per corpus for meaningful evaluation.

#### Evaluation Report

After running `just evaluate <corpus>`, the report at `reports/<corpus>/evaluation.json` contains:

- Per-mode average ROUGE-L recall scores.
- Per-query breakdown with individual scores and result counts.
- Corpus name, timestamp, and top_k setting used.

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

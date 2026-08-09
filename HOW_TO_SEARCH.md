# How to Search with Just

This guide describes the search workflow using the repository's root `justfile` only. Run every command from the MiniRAG project root. You do not need to call the REST API or run the Python scripts directly.

## Quick Start

Check if miniRag MCP is currently running  with

```bash
just status
```

If it isn't running you can start it with.

```bash
just start
```

Note that this can take a minute or two because it loads a large embedding model from disk into memory.

Run `just start` in a terminal that can remain attached to the service. Before starting it, check whether the service is already running with `just status`. The `start` target stops a healthy existing service before starting a new instance.

Prepare and index documents:

```bash
just md2txt
just ingest books
```

`ingest` asks for confirmation because it destroys and rebuilds the selected corpus index. For later additions, use incremental indexing instead:

```bash
just update books
```

Then choose one of these search workflows:

```bash
# Interactive search with dense, sparse, and hybrid modes
just search books

# One-shot hybrid search
just hybrid-search books "how do I configure the service?"
```

## Parameters At A Glance

The parameter syntax below matches the Justfile. Parameters with a default value are optional. Targets that accept `corpus=""` list available corpora and prompt for a corpus when the argument is omitted.

| Target | Required parameters | Optional parameters | Purpose |
| --- | --- | --- | --- |
| `just search [corpus]` | None | `corpus` | Interactive dense, sparse, or hybrid search |
| `just hybrid-search <corpus> <query> [alpha] [k]` | `corpus`, `query` | `alpha`, `k` | One-shot hybrid search and JSON output |
| `just evaluate [corpus]` | None | `corpus` | Evaluate sparse, dense, and hybrid retrieval |
| `just citation <corpus> <key>...` | `corpus`, one or more citation keys | None | Fetch citation metadata for search results |
| `just inspect [corpus] [document_id]` | None | `corpus`, `document_id` | Inspect chunks for a document found in search |
| `just md2txt` | None | None | Convert Markdown input files to text for indexing |
| `just pdf2txt` | None | None | Convert PDF input files to text for indexing |
| `just ingest [corpus]` | None | `corpus` | Destroy and rebuild a corpus index from text files |
| `just update [corpus]` | None | `corpus` | Incrementally index new text files |
| `just backfill-ledger [corpus]` | None | `corpus` | Seed the ingestion ledger for an existing index |
| `just delete [corpus]` | None | `corpus` | Delete a corpus index and its storage |
| `just stop [corpus]` | None | `corpus` | Stop all ingestion or ingestion for one corpus |
| `just resume [corpus]` | None | `corpus` | Remove an ingestion stop request |

## Choose A Search Method

### Interactive search: `just search [corpus]`

Parameters:

- `corpus`: optional. If omitted, Just runs the corpus selector, lists available corpora, and prompts for a name.
- There are no Justfile parameters for the initial mode or result count. The session starts in `hybrid` mode with `top_k=15`.

Example:

```bash
just search books
```

After the target starts, enter a normal query at the prompt. The following commands are available inside the search session:

```text
/mode dense       Switch to semantic vector search
/mode sparse      Switch to lexical BM25 search
/mode hybrid      Switch to combined lexical and vector search
/topk 10          Return 10 results for subsequent queries
/citation KEY     Fetch citation metadata for a result key
/help             Show the interactive commands
/quit             Exit the search session
```

The initial `hybrid` mode combines the dense and sparse result scores. Results are printed as a JSON array. `dense`, `sparse`, and `hybrid` are modes of this one target; there are no separate `just dense` or `just sparse` targets.

### One-shot hybrid search: `just hybrid-search <corpus> <query> [alpha] [k]`

Required parameters:

- `corpus`: the corpus to search.
- `query`: the query text. Quote queries containing spaces or shell characters.

Optional parameters:

- `alpha`: a dense-search weight from `0.0` through `1.0`. `0.0` gives the sparse score full weight, `1.0` gives the dense score full weight, and values between them blend both. If omitted, the service's configured hybrid alpha is used.
- `k`: the maximum number of results. It defaults to `10` and must be a positive integer.

Examples:

```bash
# Use the service alpha and return the default 10 results
just hybrid-search books "how do I configure the service?"

# Use alpha 0.25 and the default k=10
just hybrid-search books "how do I configure the service?" 0.25

# Use alpha 0.25 and return 5 results
just hybrid-search books "how do I configure the service?" 0.25 5

# Keep the service alpha and set k=20; the empty argument preserves alpha's position
just hybrid-search books "how do I configure the service?" "" 20
```

This target prints the unchanged API JSON envelope to standard output, including the top-level `status` and `data.results` fields. It is the same result shape used by the regular MCP search call.

### Retrieval evaluation: `just evaluate [corpus]`

Parameters:

- `corpus`: optional. If omitted, available corpora are listed and Just prompts for one.
- There are no parameters for the evaluation query set or `k`. The target reads `evals/question_answer_pairs.json` from the selected corpus and evaluates all three modes with `top_k=15`.

Example:

```bash
just evaluate books
```

The evaluation prints progress and writes the report to `reports/books/evaluation.json`.

## Prepare A Corpus For Search

All query targets require an indexed corpus. The service must be healthy for `ingest`, `update`, `evaluate`, `search`, `hybrid-search`, and `delete`.

### Convert source files: `just md2txt` and `just pdf2txt`

Both targets take no parameters:

```bash
just md2txt
just pdf2txt
```

Use them when your source documents are Markdown or PDF files and the corpus ingest workflow expects generated text files. They do not run a search or contact the service.

### Full rebuild: `just ingest [corpus]`

Parameters:

- `corpus`: optional. If omitted, Just lists and prompts for a corpus.

Example:

```bash
just ingest books
```

This is a destructive rebuild of the selected index and ingestion ledger. Confirm the prompt with `y` or `Y` to continue. Use it after changing source content, chunking settings, or embedding settings.

### Incremental indexing: `just update [corpus]`

Parameters:

- `corpus`: optional. If omitted, Just lists and prompts for a corpus.

Example:

```bash
just update books
```

This indexes only new text files and skips files already recorded in the ingestion ledger. It is the normal command for adding documents without rebuilding the entire corpus.

### Ledger migration: `just backfill-ledger [corpus]`

Parameters:

- `corpus`: optional. If omitted, Just lists and prompts for a corpus.

Example:

```bash
just backfill-ledger books
```

Use this one-time command when a corpus was indexed before the ingestion ledger existed. It records the existing index contents without re-indexing documents.

### Pause or resume ingestion: `just stop [corpus]` and `just resume [corpus]`

Parameters for both targets:

- `corpus`: optional. Without a corpus, the stop request applies to all ingestion. With a corpus, it applies only to that corpus.

Examples:

```bash
just stop books
just resume books

# Stop or resume all ingestion
just stop
just resume
```

These targets control ingestion and do not perform searches. A stop request can prevent indexing work needed before a query sees new documents.

## Inspect Search Results

### Citation lookup: `just citation <corpus> <key>...`

Required parameters:

- `corpus`: the corpus containing the result.
- `key...`: one or more citation keys returned by a search result.

Example:

```bash
just citation books doc_abc123
just citation books doc_abc123 doc_def456
```

The target prints one JSON object per citation key. In an interactive search session, the equivalent command is `/citation <key>`.

### Chunk inspection: `just inspect [corpus] [document_id]`

Parameters:

- `corpus`: optional. If omitted, Just lists and prompts for a corpus.
- `document_id`: optional. If omitted, Just prompts for the document ID.

Examples:

```bash
just inspect books 42
just inspect books
```

Use the document ID from a search result to inspect the stored chunks across the document stores.

## Corpus Maintenance

### Delete a corpus: `just delete [corpus]`

Parameters:

- `corpus`: optional. If omitted, Just lists and prompts for a corpus.

Example:

```bash
just delete books
```

This deletes the corpus index and storage after an explicit confirmation. It is not needed for normal searching and cannot be undone by the Justfile.

## Service And Help Targets

These targets support the search workflow but do not query documents:

```bash
just init       # First-time environment and model setup; no parameters
just status     # Check whether the service is healthy; no parameters
just stop-service # Stop the running service; no parameters
just help       # Show the Justfile help; no parameters
just mcp-help   # Print MCP setup instructions; no parameters
```

`just start` also takes no parameters and starts the local service. It stops a healthy existing instance first, so use `just status` before running it. The `mcp-help` target only prints integration instructions; the commands in this guide execute searches directly through Justfile targets.

## Corpus Names And Omitted Arguments

For targets that use the shared corpus selector:

- A corpus name must start with a letter.
- The remaining characters may be letters, numbers, `_`, or `-`.
- The corpus input directory must already exist.
- Omitting the corpus lists directories under the configured data input directory and prompts for a name.

For `hybrid-search`, both `corpus` and `query` are required by the Justfile and are not prompted interactively. Quote the query when it contains spaces.

## Typical Workflows

### New corpus

```bash
just md2txt
just ingest books
just search books
```

### Add documents

```bash
just md2txt
just update books
just hybrid-search books "new document topic"
```

### Compare search modes interactively

```bash
just search books
```

Then run the same query after `/mode sparse`, `/mode dense`, and `/mode hybrid`.

### Validate retrieval quality

```bash
just evaluate books
```

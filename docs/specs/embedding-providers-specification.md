# Embedding Providers - Behavioral Specification

## Objective

Mini-rag currently embeds all text with a single hard-wired fastText model
(`cc.en.300.bin`, 300 dimensions). This feature lets an operator choose, through
configuration alone, which embedding provider the system uses: the existing
fastText model, or a BGE model served locally by LM Studio
(`text-embedding-bge-large-en-v1.5@f16`, 1024 dimensions, 512-token input limit).
The BGE provider must guarantee that no document text is silently lost to the
model's 512-token limit, since the LM Studio endpoint truncates over-long input
without reporting an error. The problem this solves: enabling higher-quality
1024-dimensional BGE retrieval without code changes, while preserving complete,
lossless indexing of every document.

## Definitions

- **Provider** — a concrete embedding implementation satisfying the existing
  `Embeddings` contract (`embed(texts: list[str]) -> list[list[float]]`).
  Two providers exist after this feature: `fasttext` and `lmstudio`.
- **Token window** — the maximum number of input tokens the active embedding
  model accepts. For `text-embedding-bge-large-en-v1.5@f16` this is **512**
  (confirmed from LM Studio `/api/v0/models` `max_context_length`).
- **Token budget** — the per-chunk ceiling the chunker targets, defined as a
  configurable safety fraction of the token window. Default fraction **0.80**
  (≤ 409 tokens for a 512-token window).
- **Active provider** — the single provider selected by configuration for the
  running service instance.

## User Stories & Acceptance Criteria

### US-1: Select the embedding provider via configuration

As an operator, I want to select the embedding provider in `config.yaml`, so I
can switch between fastText and LM Studio BGE without modifying code.

Acceptance Criteria:
- **AC-1.1**: Configuration exposes a provider selector whose only valid values
  are `fasttext` and `lmstudio`. Any other value causes a configuration
  validation error at startup that names the offending field and value.
- **AC-1.2**: When the selector is `fasttext`, the provider produces identical
  embeddings for identical input as the current system (regression-locked): model
  `cc.en.300.bin`, 300 dimensions, unit-normalized vectors, no LM Studio interaction.
- **AC-1.3**: When the selector is `lmstudio`, document and query text are
  embedded by calling the configured LM Studio embeddings endpoint with the
  configured model, producing 1024-dimensional unit-normalized vectors.
- **AC-1.4**: A dedicated configuration section holds the LM Studio embedding
  settings: at minimum the endpoint base URL, model name, embedding dimension,
  token window, and safety fraction.
- **AC-1.5**: The new configuration section is validated with the project's
  existing strict rules: unknown keys are rejected, dimension must be a positive
  integer, token window must be a positive integer, safety fraction must be in
  the open-closed range (0.0, 1.0].
- **AC-1.6**: When the selector is `lmstudio` but the LM Studio configuration
  section is absent, startup fails with a validation error that names the missing
  section.
- **AC-1.7**: When `fasttext` is active, startup validation requires the local
  model file (`<data_dir>/models/<model_name>`) to exist and be a file — current
  behavior is preserved.
- **AC-1.8**: When `lmstudio` is active, startup validation does **not** require a
  local model file. It validates that the LM Studio embedding configuration is
  present and well-formed. LM Studio reachability is **not** checked at startup;
  connection or availability failures surface at embed time per AC-4.1, so that
  booting the service is not coupled to an external service being online.

### US-2: Size chunks to the active model's token window so no text is lost

As an operator, I want chunks sized to the active model's token window, so that
every part of every document is embedded and no content is silently truncated.

Acceptance Criteria:
- **AC-2.1**: For the `lmstudio` provider, every chunk submitted to the embeddings
  endpoint has a token count, measured by `tiktoken`, that is less than or equal
  to the configured token budget (token window × safety fraction).
- **AC-2.2**: The chunker derives its per-chunk budget from the configured token
  window. Changing the configured token window changes chunk sizing with no code
  change.
- **AC-2.3**: Consecutive chunks overlap: each chunk after the first repeats a
  non-empty suffix of the preceding chunk's source text, so that no content lies
  in a gap between two adjacent chunks.
- **AC-2.4**: The set of chunks covers the entire source document — the union of
  the character spans the chunks are derived from equals the full document; no
  contiguous span of the source is omitted from all chunks.
- **AC-2.5**: Chunking is performed on token boundaries (via `tiktoken`), so any
  input is split until each chunk is within the token budget even when the input
  contains no whitespace — token slicing, not whitespace, bounds every chunk.
- **AC-2.6**: A single token-dense input (for example, a 5000-character string
  containing no spaces) is split into multiple chunks, each within the token
  budget; no chunk is dropped and no chunk is truncated.

### US-3: Make embedding dimension and re-indexing explicit when switching providers

As an operator switching providers, I want dimension changes handled explicitly,
so retrieval never silently breaks on a dimension mismatch.

Acceptance Criteria:
- **AC-3.1**: The dense (FAISS) index is created with the active provider's
  embedding dimension (300 for `fasttext`, 1024 for `lmstudio`/bge-large).
- **AC-3.2**: If an embedding vector's length does not equal the active provider's
  configured dimension, the indexing or query operation fails with an explicit
  error stating the configured and actual dimensions; it never stores or queries
  a mismatched vector.
- **AC-3.3**: When the active provider's dimension does not match the dimension of
  an already-persisted dense index for a corpus, the affected operation fails with
  an explicit error that instructs the operator to re-index, rather than mixing
  vectors of different dimensions in one index. Re-indexing uses the existing
  ingestion path (full re-ingest, which destroys and rebuilds the corpus index);
  no new re-index mechanism is introduced by this feature.

### US-4: Fail explicitly when the LM Studio provider cannot embed

As an operator, I want LM Studio failures surfaced explicitly, so I never index or
query with empty, zero, or partial vectors.

Acceptance Criteria:
- **AC-4.1**: If the LM Studio endpoint is unreachable, times out, or returns a
  non-success status at embedding time, the operation fails with an explicit error
  identifying the endpoint; it never substitutes a zero or empty vector.
- **AC-4.2**: If the LM Studio response does not contain one embedding per input
  chunk, the operation fails with an explicit error; partial results are not
  indexed.
- **AC-4.3**: BGE embedding vectors are unit-normalized before being indexed or
  used for search, consistent with the FAISS `IndexFlatIP` cosine-similarity
  assumption.
- **AC-4.4**: Query text is embedded with the same active provider as the documents
  in the corpus being queried.
- **AC-4.5**: A query whose token count (measured by `tiktoken`) exceeds the token
  budget is not silently truncated. The system reduces the query to the token
  budget and logs a warning before embedding, so over-budget queries are explicit
  and observable (see OQ-4 for the split-and-pool alternative).

## Constraints

### Technical
- `text-embedding-bge-large-en-v1.5@f16` is BERT-based with a hard 512-token input
  limit. The LM Studio endpoint **silently truncates** input beyond this limit
  (returns HTTP 200, no error, `usage.prompt_tokens: 0`) — verified against the
  live endpoint. Lossless indexing therefore requires pre-chunking below the limit;
  the endpoint cannot be relied on to signal overflow.
- BGE embeddings are 1024-dimensional; fastText embeddings are 300-dimensional. A
  single dense index cannot hold both.
- The LM Studio OpenAI-compatible `/v1/embeddings` endpoint accepts a list of
  inputs and returns one indexed vector per input (batching is supported) —
  verified against the live endpoint.
- `tiktoken` is introduced as a token-counting dependency (explicitly approved for
  this feature). It uses OpenAI BPE encoding, which is **not** BGE's BERT WordPiece
  tokenizer, so its count is a close approximation, not BGE's exact count. The 0.80
  safety fraction (AC-2.1) absorbs this approximation error.
- Configuration models are strict (`extra="forbid"`, `frozen=True`); new settings
  require explicit, validated fields.
- The `Embeddings` contract (`embed(texts) -> list[list[float]]`) is unchanged; both
  providers satisfy it so that orchestration, storage, and search are unaffected.

### Operational
- Switching the active provider changes the embedding dimension and therefore
  requires a full re-index of every corpus. Existing 300-dimensional indices are
  incompatible with the 1024-dimensional BGE provider and vice versa.
- The `lmstudio` provider requires a reachable LM Studio instance with the
  configured embedding model available; it is a local, non-paid dependency.

### Business
- No new external or paid services are introduced; embedding stays local (fastText
  on disk, or LM Studio on the local machine).

## Edge Cases

- **Empty or whitespace-only document**: behavior is unchanged from today — the
  existing validation error is raised; no provider call is made.
- **Document shorter than one chunk**: produces exactly one chunk within budget,
  embedded normally.
- **Token-dense chunk (code, long URLs, no whitespace)**: split by the character
  backstop (AC-2.5) until every chunk is within the token budget; never truncated.
- **LM Studio unreachable / model not loaded / request timeout**: explicit error
  (AC-4.1); nothing is indexed for that document or returned for that query.
- **LM Studio returns fewer vectors than inputs**: explicit error (AC-4.2).
- **Embedding vector of unexpected length**: explicit error (AC-3.2).
- **`overlap` configured so the chunk step is non-positive**: the existing chunker
  validation error is raised.
- **Provider selector valid but provider-specific config invalid** (e.g., negative
  dimension, safety fraction ≥ 1.0): startup validation error (AC-1.5).
- **Selecting a provider whose dimension differs from an existing persisted index**:
  explicit re-index error (AC-3.3); no silent mixing of dimensions.
- **Booting with `lmstudio` active and no local model file present**: startup
  succeeds (AC-1.8) — the absent `.bin` is not an error for this provider; the
  current fastText file check applies only when `fasttext` is active.
- **Over-budget query (more tokens than the budget)**: reduced to budget with a
  logged warning before embedding (AC-4.5); never silently truncated.

## Non-Goals

- **8192-token windows / `bge-m3`**: out of scope. `bge-large-en-v1.5` is capped at
  512 tokens; an 8192-token window would require a different model that is not part
  of this feature.
- **Automatic re-embedding or migration of existing indices** on provider switch:
  out of scope. The operator re-indexes deliberately; auto-migration risks silent
  data divergence.
- **Per-corpus or per-request provider selection**: out of scope. Exactly one
  active provider per running service instance keeps index dimensions consistent.
- **Changing fastText behavior**: out of scope. The `fasttext` path must remain
  identical to today.
- **Concurrent multi-request embedding parallelism beyond endpoint batching**: out
  of scope for behavior. Batching is the throughput mechanism; specific batch size
  and any concurrency are implementation concerns (Phase 3), not behavioral
  requirements.
- **Query/passage instruction-prefix asymmetry for BGE**: deferred (see Open
  Questions). This iteration embeds queries and passages symmetrically.

## Open Questions

- **OQ-1 (deferred decision, operator may override): BGE query/passage prefix.**
  BGE v1.5 retrieval can improve when the *query* is prefixed with an instruction
  (e.g., "Represent this sentence for searching relevant passages:") while passages
  are embedded plain. v1.5 is only mildly sensitive to this. Default decision for
  this iteration: **do not** add a prefix; embed queries and passages symmetrically,
  and revisit as a retrieval-quality follow-up. Flagged for explicit operator
  confirmation.
- **OQ-2 (documented decision): tiktoken encoding.** Token counts use the
  `cl100k_base` encoding as a stable, widely-available approximation of BGE token
  counts. Recorded for visibility; change only if measurement shows the 0.80
  fraction plus character backstop is insufficient.
- **OQ-3 (documented decision): safety fraction configurability.** The 0.80 safety
  fraction is operator-configurable via the LM Studio embedding configuration
  section, defaulting to 0.80. Recorded for visibility.
- **OQ-4 (documented decision, operator may override): over-budget query handling.**
  Default decision (AC-4.5): reduce an over-budget query to the token budget and
  log a warning — explicit, never silent. The principled no-loss alternative is to
  split the query, embed each part, and mean-pool into one normalized query vector.
  Deferred because real queries rarely exceed the budget; flagged for operator
  confirmation if query truncation proves lossy in practice.

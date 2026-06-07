# Embedding Providers - Test Specification

Derived solely from `embedding-providers-specification.md`. Scenarios describe
observable behavior; no implementation detail is assumed.

## Testing Approach (language-aware)

Detected stack: Python + pytest. Existing conventions (mirrored here): deterministic
fakes and `monkeypatch` instead of live services (`FakeFastTextModel`), `tmp_path` for
filesystem state, and startup-validation tests (`test_validate_startup_missing_model`).
LM Studio is reached over `httpx`, so the `lmstudio` provider is exercised against a
**fake embeddings endpoint** (stubbed `httpx` transport) — no live LM Studio in CI.
Token counts are produced by `tiktoken`, which is deterministic and offline.

## Coverage Matrix

| Spec requirement | Test scenario(s) |
|---|---|
| AC-1.1 provider selector valid/invalid | TS-1.1a, TS-1.1b, TS-1.1c |
| AC-1.2 fasttext regression-locked | TS-1.2 |
| AC-1.3 lmstudio embeds 1024-dim normalized | TS-1.3 |
| AC-1.4 LM Studio config section present | TS-1.4 |
| AC-1.5 strict validation of new section | TS-1.5a, TS-1.5b, TS-1.5c, TS-1.5d |
| AC-1.6 lmstudio selected, section absent | TS-1.6 |
| AC-1.7 fasttext startup requires local file | TS-1.7a, TS-1.7b |
| AC-1.8 lmstudio startup needs no file, no reachability | TS-1.8a, TS-1.8b |
| AC-2.1 every chunk ≤ token budget | TS-2.1 |
| AC-2.2 chunker adapts to window | TS-2.2 |
| AC-2.3 consecutive chunks overlap | TS-2.3 |
| AC-2.4 full document coverage | TS-2.4 |
| AC-2.5 token slicing splits over-budget chunk | TS-2.5 |
| AC-2.6 token-dense no-space input | TS-2.6 |
| AC-3.1 FAISS dim = active provider dim | TS-3.1a, TS-3.1b |
| AC-3.2 vector length mismatch → error | TS-3.2a, TS-3.2b |
| AC-3.3 provider/index dim mismatch → re-index error | TS-3.3 |
| AC-4.1 LM Studio unreachable/error → explicit | TS-4.1a, TS-4.1b |
| AC-4.2 vector count mismatch → explicit | TS-4.2 |
| AC-4.3 BGE vectors unit-normalized | TS-4.3 |
| AC-4.4 query uses active provider | TS-4.4 |
| AC-4.5 over-budget query reduced + warned | TS-4.5 |
| EC empty/whitespace document | TS-EC-1 |
| EC document shorter than one chunk | TS-EC-2 |
| EC non-positive chunk step | TS-EC-7 |
| Non-Goal: no 8192/alternate model auto-switch | TS-NG-1 |

## Test Scenarios

### US-1: Provider selection via configuration

```
TS-1.1a: Select the fasttext provider
  Given a configuration whose embedding provider selector is "fasttext"
  When the service builds its embedding provider
  Then the active provider is the fastText provider

TS-1.1b: Select the lmstudio provider
  Given a configuration whose embedding provider selector is "lmstudio"
    And a complete LM Studio embedding configuration section
  When the service builds its embedding provider
  Then the active provider is the LM Studio provider

TS-1.1c: Reject an unknown provider value
  Given a configuration whose embedding provider selector is "word2vec"
  When the configuration is loaded
  Then loading fails with a validation error naming the selector field and value "word2vec"

TS-1.2: fastText embeddings are unchanged (regression lock)
  Given the fasttext provider with a known model stub
  When the same input text is embedded
  Then the returned vector has 300 dimensions
    And the vector is unit-normalized
    And it equals the recorded baseline vector for that input
    And no LM Studio request is made

TS-1.3: lmstudio embeddings are 1024-dim and normalized
  Given the lmstudio provider backed by a fake embeddings endpoint
  When a text is embedded
  Then the returned vector has 1024 dimensions
    And the vector is unit-normalized

TS-1.4: LM Studio settings load from the dedicated config section
  Given a configuration with an LM Studio embedding section specifying base URL,
        model name, dimension, token window, and safety fraction
  When the configuration is loaded
  Then all five settings are available to the system with the configured values

TS-1.5a: Reject unknown keys in the LM Studio section
  Given an LM Studio embedding section containing an unrecognized key
  When the configuration is loaded
  Then loading fails with a validation error identifying the unknown key

TS-1.5b: Reject a non-positive embedding dimension
  Given an LM Studio embedding section whose dimension is 0
  When the configuration is loaded
  Then loading fails with a validation error stating the dimension must be greater than 0

TS-1.5c: Reject a non-positive token window
  Given an LM Studio embedding section whose token window is 0
  When the configuration is loaded
  Then loading fails with a validation error stating the token window must be greater than 0

TS-1.5d: Enforce the safety-fraction range (0.0, 1.0]
  Given an LM Studio embedding section whose safety fraction is the boundary value
  When the configuration is loaded
  Then a fraction of 0.0 is rejected
    And a fraction greater than 1.0 is rejected
    And a fraction of 1.0 is accepted

TS-1.6: lmstudio selected but its config section is absent
  Given a configuration whose selector is "lmstudio" and which omits the LM Studio section
  When the configuration is loaded
  Then loading fails with a validation error naming the missing LM Studio section

TS-1.7a: fasttext startup succeeds when the model file exists
  Given the fasttext provider is active
    And the local model file exists under <data_dir>/models
  When startup validation runs
  Then startup validation passes

TS-1.7b: fasttext startup fails when the model file is missing
  Given the fasttext provider is active
    And no local model file exists under <data_dir>/models
  When startup validation runs
  Then startup validation fails with a "model file not found" error

TS-1.8a: lmstudio startup succeeds without a local model file
  Given the lmstudio provider is active
    And no local model file exists under <data_dir>/models
  When startup validation runs
  Then startup validation passes

TS-1.8b: lmstudio startup does not probe reachability
  Given the lmstudio provider is active
    And the LM Studio endpoint is unreachable
  When startup validation runs
  Then startup validation passes
    And no embedding request is made during startup
```

### US-2: Token-window-aware, lossless chunking

```
TS-2.1: Every chunk stays within the token budget
  Given the lmstudio provider with token window 512 and safety fraction 0.80
    And a document whose token count far exceeds the budget
  When the document is chunked for embedding
  Then every chunk has a tiktoken token count of 409 or fewer

TS-2.2: Chunk sizing adapts to the configured token window
  Given two configurations identical except for token window (256 vs 512), fraction 0.80
  When the same document is chunked under each configuration
  Then chunks under the 256 window are at most ~204 tokens
    And chunks under the 512 window are at most ~409 tokens
    And the smaller window produces more chunks for the same document

TS-2.3: Consecutive chunks overlap
  Given a document that produces at least two chunks
  When the document is chunked
  Then each chunk after the first shares a non-empty run of source content with the
       preceding chunk

TS-2.4: Chunks cover the entire document
  Given a multi-chunk document
  When the document is chunked
  Then every contiguous unit of the source document appears in at least one chunk
    And no unit of the source is absent from all chunks

TS-2.5: A single over-budget chunk is split on token boundaries
  Given a single whitespace-free string whose tiktoken token count exceeds the budget
  When the string is chunked
  Then it is split into more than one chunk
    And every resulting chunk is within the token budget

TS-2.6: A 5000-character no-space input is chunked losslessly
  Given a 5000-character string containing no whitespace, under window 512
  When the string is chunked
  Then more than one chunk is produced
    And every chunk is within the token budget
    And concatenating the chunks (removing overlap) reproduces the full input
    And no chunk is truncated or dropped
```

### US-3: Dimension and re-index handling

```
TS-3.1a: fasttext index uses dimension 300
  Given the fasttext provider is active
  When the dense index is created for a corpus
  Then the dense index is created with dimension 300

TS-3.1b: lmstudio index uses dimension 1024
  Given the lmstudio provider is active with configured dimension 1024
  When the dense index is created for a corpus
  Then the dense index is created with dimension 1024

TS-3.2a: Indexing a mismatched-length vector is rejected
  Given the active provider's configured dimension is 1024
  When a chunk embedding of length 300 is submitted for indexing
  Then indexing fails with an error stating configured=1024 and actual=300
    And the vector is not stored

TS-3.2b: Querying with a mismatched-length vector is rejected
  Given the active provider's configured dimension is 1024
  When a query embedding of length 300 is submitted for search
  Then the search fails with a dimension-mismatch error
    And no search is performed

TS-3.3: Operating on an index built at a different dimension is rejected
  Given a corpus whose persisted dense index was built at dimension 300
    And the lmstudio provider (dimension 1024) is active
  When the corpus is indexed or queried
  Then the operation fails with an explicit error instructing the operator to re-index
    And vectors of differing dimensions are never mixed in one index
```

### US-4: LM Studio failure handling

```
TS-4.1a: Unreachable endpoint produces an explicit error
  Given the lmstudio provider whose endpoint is unreachable
  When a text is embedded
  Then embedding fails with an explicit error identifying the endpoint
    And no zero or empty vector is returned
    And nothing is indexed for the affected document

TS-4.1b: Non-success response produces an explicit error
  Given the lmstudio provider whose endpoint returns HTTP 500
  When a text is embedded
  Then embedding fails with an explicit error
    And no vector is returned

TS-4.2: A response missing vectors is rejected
  Given the lmstudio provider and a batch of 3 chunks
    And a fake endpoint that returns only 2 embeddings
  When the batch is embedded
  Then embedding fails with an explicit error about the vector/input count mismatch
    And no partial results are indexed

TS-4.3: BGE vectors are unit-normalized
  Given the lmstudio provider backed by a fake endpoint returning an un-normalized vector
  When a text is embedded
  Then the returned vector has an L2 norm of 1.0 within tolerance

TS-4.4: Queries use the active provider
  Given the lmstudio provider is active
  When a query is embedded for search
  Then the query embedding is produced by the LM Studio endpoint
    And the fastText model is not used

TS-4.5: An over-budget query is reduced with a warning, not silently
  Given the lmstudio provider with token window 512 and fraction 0.80
    And a query whose tiktoken token count exceeds the budget
  When the query is embedded
  Then a warning is logged identifying the over-budget query
    And the embedded query is within the token budget
    And the query embedding is still produced
```

## Edge Case Scenarios

```
TS-EC-1: Empty or whitespace-only document is rejected before embedding
  Given any active provider
  When a document of only whitespace is submitted for indexing
  Then it is rejected with the existing "document text must not be empty" error
    And no embedding request is made

TS-EC-2: A document shorter than one chunk yields one chunk
  Given the lmstudio provider and a document well under the token budget
  When the document is chunked
  Then exactly one chunk is produced
    And that chunk is within the token budget

TS-EC-7: A non-positive chunk step is rejected
  Given a chunking configuration whose overlap yields a non-positive step
  When chunking is attempted
  Then it fails with the existing "non-positive chunk step" error
```

## Negative Scenario (Non-Goals)

```
TS-NG-1: The system does not silently accept an alternate-window model
  Given a configuration selecting "lmstudio"
  When the provider selector is set to any value other than "fasttext" or "lmstudio"
  Then configuration loading is rejected (no implicit substitution of another model
       or token window occurs)
```

## Traceability

Every acceptance criterion (AC-1.1 … AC-4.5) maps to at least one scenario in the
coverage matrix. Every spec Edge Case maps to a scenario (token-dense input →
TS-2.5/TS-2.6; LM Studio failures → TS-4.1/TS-4.2; dimension mismatch → TS-3.2/TS-3.3;
re-index → TS-3.3; lmstudio-without-file boot → TS-1.8a; over-budget query → TS-4.5).
No orphan scenarios. The deferred decisions (OQ-1 query prefix, OQ-4 split-and-pool)
are intentionally not tested in this iteration; if promoted to requirements, each will
need scenarios added here.

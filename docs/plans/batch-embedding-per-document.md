# Sketch: Batch embeddings per document

## Context

Today `Orchestration.index_document` embeds **one chunk at a time** inside the
per-chunk loop (`src/minirag/orchestration.py:102`):

```python
chunk_embedding = self._embeddings.embed([chunk_span.text])[0]
```

Both embedding providers are built to batch, so this is wasted work:

- **LM Studio** (`src/minirag/search/embedding_agent.py:49`) already sub-batches up
  to `batch_size` (32 in `config.yaml`) per HTTP request — but fed one text at a
  time it pays **one HTTP round-trip per chunk** instead of one per 32.
- **fastText** (`src/minirag/search/embeddings.py:55`) loops per text; batching
  removes per-call overhead.

The fix: compute **all** of a document's chunk embeddings in a single
`embed(...)` call before the indexing loop. The `Embeddings` contract already
returns vectors in input order (LM Studio sorts by `index`; fastText appends in
order), so a batched call is a drop-in. This is the highest-value / lowest-risk
ingestion speedup and needs **no interface, client, or backend changes**.

## The change (single method, single file)

File: `src/minirag/orchestration.py`, method `index_document`.

**Before** (chunking + loop, lines ~84–104):

```python
chunk_spans = self._chunker(text)

chunk_ids: list[int] = []
for chunk_index, chunk_span in enumerate(chunk_spans):
    try:
        line_from = text.count("\n", 0, chunk_span.char_start) + 1
        line_to = text.count("\n", 0, max(chunk_span.char_end - 1, chunk_span.char_start)) + 1
        chunk_id = self._storage.insert_chunk(
            document_id=document_id,
            content=chunk_span.text,
            chunk_index=chunk_index,
            char_start=chunk_span.char_start,
            char_end=chunk_span.char_end,
            line_from=line_from,
            line_to=line_to,
        )
        chunk_ids.append(chunk_id)

        chunk_embedding = self._embeddings.embed([chunk_span.text])[0]   # <-- per-chunk call
        self._dense.index(chunk_id=chunk_id, embedding=chunk_embedding)
        self._sparse.index(chunk_id=chunk_id, content=chunk_span.text)
    except Exception as exc:
        logger.error(
            "Failed to index chunk %d of document_id=%s: %s",
            chunk_index, document_id, exc,
        )
        raise RuntimeError(f"failed to index chunk {chunk_index} of document_id={document_id}") from exc
```

**After** — embed once up front, then zip spans with their vectors:

```python
chunk_spans = self._chunker(text)

# Batch-embed every chunk in one call before indexing. The Embeddings contract
# returns vectors in input order, so chunk_embeddings[i] pairs with chunk_spans[i].
# LM Studio sub-batches internally (batch_size), collapsing one HTTP round-trip
# per chunk into ceil(n / batch_size); fastText loses only per-call overhead.
chunk_embeddings = self._embeddings.embed([chunk_span.text for chunk_span in chunk_spans])

chunk_ids: list[int] = []
for chunk_index, (chunk_span, chunk_embedding) in enumerate(
    zip(chunk_spans, chunk_embeddings, strict=True)
):
    try:
        line_from = text.count("\n", 0, chunk_span.char_start) + 1
        line_to = text.count("\n", 0, max(chunk_span.char_end - 1, chunk_span.char_start)) + 1
        chunk_id = self._storage.insert_chunk(
            document_id=document_id,
            content=chunk_span.text,
            chunk_index=chunk_index,
            char_start=chunk_span.char_start,
            char_end=chunk_span.char_end,
            line_from=line_from,
            line_to=line_to,
        )
        chunk_ids.append(chunk_id)

        self._dense.index(chunk_id=chunk_id, embedding=chunk_embedding)   # <-- uses precomputed vector
        self._sparse.index(chunk_id=chunk_id, content=chunk_span.text)
    except Exception as exc:
        logger.error(
            "Failed to index chunk %d of document_id=%s: %s",
            chunk_index, document_id, exc,
        )
        raise RuntimeError(f"failed to index chunk {chunk_index} of document_id={document_id}") from exc
```

Net diff: **+1 batched `embed` line, loop header gains `zip(..., strict=True)`,
−1 per-chunk `embed` line.** Storage inserts and `dense/sparse.index` stay inside
the loop, so the `"failed to index chunk N"` error wrapping is unchanged.

`strict=True` matches the existing idiom (`src/minirag/retrieval/faiss_dense.py:139`)
and guards against a provider returning the wrong vector count.

## Why it's safe

- **Ordering** is guaranteed by both providers (documented input-order return),
  so `chunk_embeddings[i]` always matches `chunk_spans[i]`.
- **Providers still sub-batch internally**, so passing all texts is correct even
  for large documents — LM Studio splits into `batch_size` groups itself.
- **Empty / zero-chunk docs**: the chunker raises on empty text before this
  point; defensively, `embed([])` returns `[]` and the loop is skipped.
- **Failure atomicity improves slightly**: if the embedding backend is down, it
  now fails *before* any chunk rows/vectors are written, instead of after chunk 0.

## Behavioral note to decide (minor)

Moving `embed` out of the loop moves its exceptions out of the
`except Exception → raise RuntimeError("failed to index chunk N")` wrapper:

- LM Studio unreachable → `RuntimeError` (unchanged: still HTTP 500 via
  `src/minirag/api/routes_index.py:64`).
- Runtime dimension mismatch → raw `ValueError`, which
  `src/minirag/api/routes_index.py:62` maps to **HTTP 400 instead of the current
  500**.

This is an edge case (dimension is normally validated at model load).
Recommended: accept it (400 is arguably more correct). If exact status parity is
required, wrap the batch `embed` call and re-raise as `RuntimeError`.

## Files affected

- `src/minirag/orchestration.py` — the only production change (one method).
- No changes to `Embeddings` implementations / protocol, clients,
  `scripts/ingest.py`, the FAISS / Tantivy / SQLite backends, or the API route.

## Test impact & verification

- **Existing unit tests pass unchanged.** `FakeEmbeddings.embed`
  (`tests/test_orchestration.py:28`) is already list-aware;
  `test_orchestration_partial_chunk_failure` still holds (inserts remain in the
  loop, `len(storage.chunks) == 1`).
- **Optional new test**: give a fake embeddings a call counter and assert
  `embed` is invoked **once** per `index_document` (locks in the optimization).
- **Verify end-to-end**:
  - `uv run pytest tests/test_orchestration.py tests_integration/test_integration.py`
    — the integration path exercises real fastText batching.
  - Manual: `just start` then `just ingest <corpus>`. On the LM Studio provider,
    confirm far fewer `/v1/embeddings` requests and lower wall-clock; on fastText,
    a smaller improvement. (Per project convention, run via `uv run` / `just`.)

## Out of scope (from the earlier investigation)

Amortizing `dense.persist()` / `sparse.persist()` across documents
(`src/minirag/orchestration.py:114-115`) and document-level parallelism (blocked
by unlocked FAISS / Tantivy writes) are separate, higher-effort follow-ups — not
part of this sketch.

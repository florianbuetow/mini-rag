# Plan: Idempotent re-ingestion and clean-stop (STOP file)

## Context

Two defects, both exposed by the `videos` ingest dying twice mid-run
(`httpx.ReadTimeout` at 11,107/25,460).

### Defect 1 — an interrupted document stays permanently half-indexed

`Orchestration.index_document` (`src/minirag/orchestration.py:65-118`) writes to three
stores with different durability points:

| Store | When it becomes durable |
| --- | --- |
| SQLite document + citation | `insert_document_with_citation` commits immediately (`sqlite.py:233`) |
| SQLite chunk rows | `insert_chunk` commits **per chunk** (`sqlite.py:302`) |
| FAISS vectors | `self._dense.persist()` — **once, after the chunk loop** (`orchestration.py:114`) |
| Tantivy entries | `self._sparse.persist()` — **once, after the chunk loop** (`orchestration.py:115`) |

Kill the process mid-document and SQLite is ahead of both indices: the chunk rows are
committed, the vectors and lexical entries are not.

The ledger then cements it. `record_indexed` runs only *after* `index_document` returns
(`scripts/ingest.py:86`), so the interrupted file is absent from the ledger and gets
retried on the next run. The retry hits the `document_citations.citation_key` UNIQUE
constraint, and `ingest.py:99-113` treats that as *"already indexed server-side"* — it
logs a warning, records the file in the ledger, and continues. The document is now
recorded as complete while missing part of its search coverage, permanently.

**This failure is silent, which makes it worse than the 500s it replaces.** A missing
FAISS entry raises nothing: `_resolve_results` (`orchestration.py:180-219`) only fails in
the opposite direction, when an index returns a chunk_id absent from SQLite. Here the
chunk simply never surfaces. `corpus_stats` counts it, `get_chunk` returns it, the ledger
asserts the file is done — and dense search silently never retrieves it. Recall degrades
with every crash, with no signal, and is indistinguishable from weak embeddings or bad
chunking. On an evals corpus it corrupts the very measurements used to diagnose it.

### Defect 2 — there is no way to stop an ingest cleanly

The only way to stop a run today is to kill it, which triggers Defect 1 by construction.
A long ingest (`videos` is ~25k files at ~400-900 files/hour) cannot be paused for a
reboot, a config change, or contention without damaging one document.

## Goals

1. Re-indexing a file that is already present is **idempotent**: same end state as
   indexing it once, with all three stores consistent.
2. A crashed or stopped run **self-repairs** on the next run — no manual intervention, no
   full re-ingest.
3. An operator can stop a run **cleanly** at a document boundary via a `STOP` file.
4. Divergence between SQLite and FAISS is **detectable**, not silent.

### Acceptance criteria

- After killing an ingest mid-document and re-running it, for every document in the
  corpus: `COUNT(chunks WHERE document_id = D)` equals the number of that document's
  chunk_ids present in the FAISS `id_map`, and the document's content is retrievable by
  both dense and sparse search.
- Corpus-wide: `SELECT COUNT(*) FROM chunks` equals `faiss.ntotal`.
- Creating `STOP` during a run causes exit after the in-flight document completes, with
  the ledger committed, and the next run resumes with no gap and no duplicate.

## Design decisions

**Repair server-side, not client-side.** `scripts/ingest.py` talks to the service over
HTTP (`POST /v1/corpus/{corpus}/index`) and has no access to the three stores. The
delete-then-index sequence must be atomic with respect to a single request, so it belongs
in `Orchestration.index_document`. The client keeps its existing single call.

**Delete-then-reindex, not diff-and-patch.** Detecting *which* chunks of a document are
missing from FAISS would require re-embedding to compare, and Tantivy has no per-chunk
existence check. Deleting the document from all three stores and indexing it fresh is
simpler, provably correct, and costs one document's work.

**Ordering alone cannot fix this.** Whichever store commits last, a kill in the gap leaves
the other ahead. Committing SQLite last would trade silent recall loss for FAISS orphans —
the 500-error failure mode, which is louder but still broken. Only an idempotent re-index
closes the window.

**`STOP` is never auto-deleted.** A run that stops on `STOP` leaves the file in place, and
the next run refuses to start while it exists. Auto-deleting would make the pill fire once
and vanish, so an operator who set it deliberately could be overridden by any scheduled
job. Removal is an explicit operator action.

---

## Change 1 — per-document deletion in SQLite

**File:** `src/minirag/storage/sqlite.py`, `src/minirag/storage/interface.py`

Add to `StorageWriter` (`interface.py:62`):

```python
@abstractmethod
def delete_document(self, document_id: int) -> list[int]:
    """Delete a document, its chunks, and its citation. Return the deleted chunk IDs."""

@abstractmethod
def get_document_id(self, citation_key: str) -> int | None:
    """Return the document ID owning a citation_key, or None if not found."""
```

`get_document_id` is the reverse of the existing `get_citation_key(document_id)`
(`sqlite.py:447`); only the forward direction exists today.

`SQLiteStorage.delete_document` semantics:

- Reject `document_id <= 0` with `ValueError`, matching the guard style used throughout
  the class.
- Single transaction (`BEGIN` / `commit` / `rollback` on exception), following
  `insert_document_with_citation` (`sqlite.py:200-236`).
- `SELECT chunk_id FROM chunks WHERE document_id = ?` **first** — the caller needs those
  IDs to purge FAISS and Tantivy, and they are unrecoverable after the delete.
- Delete in FK-safe order: `document_citations`, then `chunks`, then `documents`.
  `PRAGMA foreign_keys = ON` is set (`sqlite.py:32`), so the reverse order fails.
- Deleting a non-existent `document_id` returns `[]` and is not an error — the repair path
  must be safe to call speculatively.

The `corpus_stats` delete triggers (`sqlite.py:158-190`) fire row-by-row and keep the
cached counts correct with no extra work. Note this only holds because the triggers
suppress SQLite's truncate optimization; do not "optimize" these into bulk deletes.

## Change 2 — per-chunk removal from FAISS

**File:** `src/minirag/retrieval/faiss_dense.py`, `src/minirag/retrieval/dense_interface.py`

Add to `DenseRetrieval` (`dense_interface.py:8`):

```python
@abstractmethod
def remove_ids(self, chunk_ids: list[int]) -> int:
    """Remove vectors by chunk ID. Return the number removed."""
```

`FAISSDense.remove_ids`:

```python
def remove_ids(self, chunk_ids: list[int]) -> int:
    if len(chunk_ids) == 0:
        return 0
    id_vector = np.array(chunk_ids, dtype=np.int64)
    return int(self._index.remove_ids(id_vector))
```

Add `remove_ids` to the `FaissIndex` Protocol (`faiss_dense.py:16`) so the `cast` stays
honest.

**Verified against the installed FAISS**, on the exact index type this code builds
(`IndexIDMap(IndexFlatIP)`, `faiss_dense.py:89-92`): added 5 vectors with IDs 101-105,
called `remove_ids([102, 104])` → returned `2`, `ntotal` went 5 → 3, `id_map` became
`[101, 103, 105]`, and a search for a removed vector no longer returns its ID. IDs absent
from the index are silently ignored, so the call is safe to make speculatively.

Do **not** persist inside `remove_ids`. The caller persists once after re-indexing, so a
crash between delete and re-index leaves the on-disk index untouched and the next run
repeats the whole repair.

## Change 3 — per-chunk removal from Tantivy

**File:** `src/minirag/retrieval/tantivy_sparse.py`, `src/minirag/retrieval/sparse_interface.py`

Add the matching `remove_ids(chunk_ids: list[int]) -> None` to `SparseRetrieval` and
implement it with `delete_documents_by_term` on the `chunk_id` field.

**Verified:** the installed `tantivy v0.26.0` `IndexWriter` exposes `delete_all_documents`,
`delete_documents`, `delete_documents_by_term`, and `delete_documents_by_query`. The schema
declares `chunk_id` as `add_integer_field("chunk_id", stored=True, indexed=True, fast=True)`
(`tantivy_sparse.py:190`), so term-deletion on it is valid.

Reuse the existing lazy-writer pattern from `index` (`tantivy_sparse.py:205-216`): create
the writer if `self._writer is None`, issue the deletes, and let the existing `persist()`
(`tantivy_sparse.py:218-225`) commit them alongside the re-indexed documents. Deletes and
adds then land in one commit, which is what makes the repair atomic from a reader's view.

## Change 4 — make `index_document` idempotent

**File:** `src/minirag/orchestration.py`, method `index_document` (line 65)

Insert between citation validation (line 74-80) and the storage write (line 82):

```python
# A file already present means a previous run wrote it but did not finish: either it
# was interrupted mid-document (chunk rows committed, vectors not yet persisted) or its
# ledger entry was lost. Either way its indexed state is unproven, so purge every trace
# and index it fresh rather than trusting it. This is what makes a crashed run safe to
# re-run: re-indexing a file is idempotent, not an error.
if citation is not None:
    existing_id = self._storage.get_document_id(str(citation["citation_key"]))
    if existing_id is not None:
        self._purge_document(document_id=existing_id)
```

with:

```python
def _purge_document(self, document_id: int) -> None:
    """Remove a document from storage and both retrieval indices."""
    chunk_ids = self._storage.delete_document(document_id=document_id)
    self._dense.remove_ids(chunk_ids)
    self._sparse.remove_ids(chunk_ids)
    with self._citation_key_cache_lock:
        self._citation_key_cache.pop(document_id, None)
    logger.info("Purged stale document_id=%s (%d chunks) before re-index", document_id, len(chunk_ids))
```

The `_citation_key_cache` eviction (`orchestration.py:62`) is required: the cache is
keyed by `document_id` and a re-indexed document gets a **new** ID, so a stale entry would
outlive its document.

Auto-generated citations (`citation is None`) derive their key from the document ID
(`sqlite.py:211-218`) and cannot collide, so they skip the purge.

The existing per-chunk failure handler (`orchestration.py:105-112`) is unchanged: a
failure mid-re-index leaves the document partially written again, and the *next* run
purges and retries it. The repair is convergent, not one-shot.

## Change 5 — remove the conflict workaround in the ingest script

**File:** `scripts/ingest.py`

Change 4 makes `UNIQUE constraint failed: document_citations.citation_key` unreachable
from this path. Delete the `CITATION_KEY_CONFLICT` constant (line 18) and its `except
RuntimeError` branch (lines 99-113), and let a `RuntimeError` fail the run as any other
error does. Drop `reconciled_existing` from the summary counters (lines 67, 104, 116+).

Keep the ledger behaviour as-is: `record_indexed` after a successful index
(`ingest.py:86`), `ledger.commit` at the end. That contract already works — it is what
allowed both `videos` deaths to resume without losing work.

## Change 6 — the `STOP` poison pill

**File:** `scripts/ingest.py`, plus a helper in `src/minirag/ingestion/ledger.py`

### Semantics

- **Location, two scopes, either one triggers:**
  - `{data_dir}/STOP` — halts any ingest, for "stop everything".
  - `{data_dir}/storage/{corpus}/STOP` — halts only that corpus.
- **Content is ignored.** Existence is the signal. An empty file is valid; any text in it
  is logged verbatim as the stop reason, so an operator can leave a note.
- **Checked once per document, at the top of the file loop**, before the
  `already_indexed` skip. This is the only place where all three stores are consistent —
  the previous document has been fully indexed *and* recorded in the ledger. Checking
  mid-document would reintroduce Defect 1.
- **On detection:** log at WARNING with the corpus, the file about to be processed, the
  position (`i/num_files`), and the file's contents if non-empty; call `ledger.commit` so
  `indexed.log` is folded into `indexed.txt`; print the same summary a normal run prints;
  exit **0**. A clean stop is not a failure.
- **Checked once more at startup**, before the first file. If `STOP` exists, refuse to
  start: log at ERROR and exit **3**, distinct from both success and a genuine failure, so
  a scheduler can tell "deliberately halted" from "broken".
- **Never deleted by the ingest.** Removing it is an explicit operator action. This is
  what stops a scheduled job from silently overriding a deliberate halt.

### Sketch

```python
STOP_EXIT_CODE = 3


def stop_file_paths(data_dir: Path, corpus: str) -> list[Path]:
    """Return the global and per-corpus poison-pill paths, in precedence order."""
    return [data_dir / "STOP", data_dir / "storage" / corpus / "STOP"]


def stop_requested(data_dir: Path, corpus: str) -> Path | None:
    """Return the first existing STOP file, or None."""
    return next((path for path in stop_file_paths(data_dir, corpus) if path.is_file()), None)
```

In `ingest_files`, at the top of the `for i, file_path in enumerate(...)` loop
(`ingest.py:69`):

```python
stop_path = stop_requested(data_dir, corpus)
if stop_path is not None:
    reason = stop_path.read_text(encoding="utf-8").strip()
    logger.warning(
        "STOP file found at %s — halting cleanly at [%d/%d] before %s%s",
        stop_path, i, num_files, relative_to_input,
        f" (reason: {reason})" if reason else "",
    )
    break     # falls through to the existing ledger.commit + summary
```

`break` rather than `return` so the run exits through the existing commit-and-summarise
path — the stop must not bypass the ledger commit.

Read errors on the `STOP` file (permissions, race with deletion) must not crash the run:
wrap the `read_text` in `try/except OSError` and fall back to an empty reason. The
*existence* check is the contract; the contents are a convenience.

### `just` recipes

Add to `justfile`, next to the existing `ingest`/`update` recipes (lines 258, 275):

- `stop corpus=""` — write the `STOP` file (global when no corpus given), echoing the path.
- `resume corpus=""` — remove it, and say so if there was nothing to remove.

---

## Ordering and dependencies

| Step | Depends on | Independently shippable |
| --- | --- | --- |
| 1. SQLite `delete_document` + `get_document_id` | — | yes |
| 2. FAISS `remove_ids` | — | yes |
| 3. Tantivy `remove_ids` | — | yes |
| 4. `index_document` purge-then-index | 1, 2, 3 | yes — this is the behavioural change |
| 5. Drop the conflict branch | 4 | yes |
| 6. `STOP` file | — | yes, fully independent |

1-3 are additive: new methods, no existing call sites touched, nothing observable changes
until step 4 lands. Step 6 touches only `scripts/ingest.py` and the justfile and can land
first, which is worth doing — it is what makes the *current* `videos` run stoppable
without damage.

## Test plan

**Unit — `tests/test_storage_sqlite.py`**
- `delete_document` returns the document's chunk IDs and removes rows from all three tables.
- `delete_document` on an unknown ID returns `[]` and does not raise.
- `corpus_stats` decrements correctly after a delete (guards the trigger interaction).
- `get_document_id` round-trips with `get_citation_key`; returns `None` when absent.

**Unit — dense/sparse**
- `remove_ids` drops the vectors: `ntotal` decreases, removed IDs vanish from search results.
- `remove_ids([])` is a no-op returning 0.
- `remove_ids` with IDs not in the index does not raise.
- Tantivy: a removed chunk no longer matches a query that previously hit it.

**Unit — `tests/test_orchestration.py`**
- Indexing the same citation key twice yields one document, and `chunk_count` equals the
  single-index count — not double.
- The second index call produces new chunk IDs and the old ones are absent from both indices.
- The citation-key cache does not retain the superseded document ID.

**Integration — `tests_integration/`** (the acceptance test for Defect 1)
- Index N documents, then simulate an interruption by indexing a document whose chunk
  rows commit while the persist is stubbed to raise.
- Re-run the ingest over the same input.
- Assert `SELECT COUNT(*) FROM chunks` equals `faiss.ntotal`, and that the interrupted
  document's content is returned by both dense and sparse search.

**Integration — `STOP`**
- With `STOP` present at startup: exits 3, indexes nothing, ledger unchanged.
- Created mid-run: the in-flight document completes, the ledger contains it, exit is 0,
  and a follow-up run resumes at exactly the next file with no gap and no duplicate.
- Per-corpus `STOP` does not halt a different corpus.

## Risks

**Re-index cost on resume.** Every resumed run now re-indexes one document that the old
code skipped. One document per interruption — negligible against a 25k-file corpus, and it
is the entire point.

**Deletion is destructive.** `delete_document` removes committed rows. It is reached only
when a citation key already exists, i.e. only when the file is about to be written again
from source. The source file is the authority; the DB is a derived index (a premise the
codebase already states, `sqlite.py:95-99`).

**Tantivy deletes are commit-scoped.** `delete_documents_by_term` takes effect on
`commit()`. Since deletes and re-adds share the existing `persist()` call, a reader never
observes the deleted-but-not-re-added state. Do not add an intermediate `persist()`
between the purge and the re-index.

**FAISS `IndexFlatIP` compaction.** `remove_ids` on `IndexIDMap` rewrites the underlying
storage; at 250k vectors (`ai`-scale) this is O(n) per call. One call per repaired
document is fine. Do not use this method for bulk deletion loops.

## Repairing what is already on disk

The changes above prevent future damage but do not repair documents already half-indexed
by the two `videos` deaths. A one-off reconcile using the same primitives:

1. Read all `chunk_id`s from SQLite.
2. Diff against `faiss.vector_to_array(index.id_map)`.
3. For every chunk present in SQLite but missing from FAISS, resolve its
   `document_id`, purge that document, and re-index it from its `source_path`.

Ship this as `scripts/reconcile.py --corpus <name> [--check-only]`. The `--check-only` mode
is the detection half of Goal 4 and should also run at corpus open: compare
`corpus_stats().chunk_count` against `dense.ntotal` and log a WARNING on mismatch. That
one comparison is what turns this whole failure class from silent into visible.

## Out of scope

- The `_drop_legacy_tables_if_needed` fail-closed change (`sqlite.py:94-112`) — the
  separate defect that wiped 10 corpora on 2026-07-21. Related, tracked separately.
- Batching embeddings per document (`docs/plans/batch-embedding-per-document.md`).
- Raising the client-side HTTP timeout that caused the two `videos` deaths.
- Cross-store transactionality. Not achievable across SQLite, FAISS, and Tantivy;
  idempotent re-index is the substitute.

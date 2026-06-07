# Embedding Providers - Test Implementation Specification

How each scenario in `embedding-providers-test-specification.md` becomes a pytest
test, and the production components those tests target. Written before the feature
exists; all tests must fail on first run.

## Test Framework & Conventions

- **Framework:** pytest (existing). Plain `assert`; `pytest.raises(... , match=...)`
  for error scenarios; `pytest.mark.parametrize` for decision tables.
- **Isolation:** `tmp_path` for filesystem state; `monkeypatch` for env/attribute
  patching; `caplog` for warning assertions (AC-4.5). `pytest-randomly` is active, so
  tests must not depend on order or shared mutable state.
- **No live LM Studio:** the LM Studio HTTP boundary is faked with
  `httpx.MockTransport`, injected into the provider. No new test dependency.
- **Tokenization:** `tiktoken` is used for real in tests (deterministic, offline) to
  assert token budgets.
- **Existing fakes reused:** `FakeFastTextModel`/`FakeFastTextModule` from
  `tests/test_embeddings.py` for the fasttext regression lock.

## Production Components Under Test (design reference)

These are introduced by the feature; the tests below target their observable behavior.

1. **Config (`config.py`)** — `EmbeddingsConfig` gains:
   - `provider: str = "fasttext"` (validated to `{"fasttext","lmstudio"}`) — the feature flag.
   - existing `model_name`, `dimension` remain (fastText settings).
   - `lmstudio: LMStudioEmbeddingsConfig | None = None` — the new section
     (`base_url`, `model_name`, `dimension`, `max_input_tokens`, `safety_fraction`,
     `batch_size`, `timeout_seconds`), strict + frozen.
   - model-level validator: `provider == "lmstudio"` requires `lmstudio` present (AC-1.6).
   - helper `active_dimension() -> int` returns `dimension` or `lmstudio.dimension`.
   - **Backward compatible:** existing `config.yaml` validates unchanged (`provider`
     defaults to `fasttext`, `lmstudio` defaults `None`).

2. **`EmbeddingAgent`** (`search/embedding_agent.py`, new) — encapsulates the LM
   Studio call. Accepts an injectable `httpx` transport/client. `embed_batches(chunks)`
   splits chunks into `batch_size` groups, POSTs each batch to `{base_url}/embeddings`
   as `{"model":..., "input":[...]}` **sequentially**, validates one vector per input
   (AC-4.2), and raises an explicit error on connection failure / non-2xx (AC-4.1).
   Returns raw (un-normalized) vectors.

3. **`LMStudioEmbeddings`** (`search/embeddings_lmstudio.py`, new) — implements the
   existing `Embeddings` protocol. Delegates to `EmbeddingAgent`, then unit-normalizes
   (AC-4.3) and validates each vector length against configured dimension (AC-3.2).

4. **Token-aware chunker** (`ingestion/token_chunker.py`, new) —
   `chunk_text_by_tokens(text, max_tokens, overlap)`: builds chunks of ≤ `max_tokens`
   tiktoken tokens (cl100k_base) with token overlap by slicing on token boundaries, so
   even whitespace-free input is bounded (AC-2.5/2.6). The existing word `chunk_text`
   is unchanged and used for fasttext.

5. **`Chunker` injection** — `Orchestration` receives a chunker strategy (word-based
   for fasttext; token-based for lmstudio) instead of calling `chunk_text` directly, so
   the active provider's token budget governs chunking.

6. **`build_embeddings(embeddings_config, data_dir) -> Embeddings`**
   (`backend_factory.py` or new factory) — returns `FastTextEmbeddings` or
   `LMStudioEmbeddings` by `provider`. Replaces the direct construction in `app.py`.

7. **Provider-aware startup** (`startup_validation.py`) — local model-file check runs
   only when `provider == "fasttext"` (AC-1.7/1.8); no LM Studio reachability probe.

**Parallelism answer (AC constraint):** chunks are embedded in batches of `batch_size`
(default 32) per HTTP request — verified that `/v1/embeddings` returns one indexed
vector per list input. Batches are issued **sequentially**; a single local LM Studio
instance serializes embedding work server-side, so client-side request concurrency is
intentionally out of scope (the knob is `batch_size`).

## Test Structure

Mirrors the existing flat `tests/` layout; one behavior per test function; names
describe behavior.

| File | Covers |
|---|---|
| `tests/test_config.py` (extend) | TS-1.1c, TS-1.4, TS-1.5*, TS-1.6 |
| `tests/test_embeddings_factory.py` (new) | TS-1.1a, TS-1.1b |
| `tests/test_embeddings.py` (extend) | TS-1.2 |
| `tests/test_embedding_agent.py` (new) | TS-1.3, TS-4.1a, TS-4.1b, TS-4.2 |
| `tests/test_embeddings_lmstudio.py` (new) | TS-4.3, TS-3.2a, TS-3.2b |
| `tests/test_token_chunker.py` (new) | TS-2.1, TS-2.2, TS-2.3, TS-2.4, TS-2.5, TS-2.6, TS-EC-2, TS-EC-7 |
| `tests/test_startup_validation.py` (new) | TS-1.7a, TS-1.7b, TS-1.8a, TS-1.8b |
| `tests/test_backend_factory.py` (extend) | TS-3.1a, TS-3.1b, TS-3.3 |
| `tests/test_orchestration.py` (extend) | TS-4.4, TS-4.5, TS-EC-1 |
| `tests/test_config.py` (extend) | TS-NG-1 |

## Test Scenario Mapping

| TS | Test function | Setup → Action → Assertion |
|---|---|---|
| TS-1.1a | `test_factory_builds_fasttext_provider` | Config `provider="fasttext"` + stubbed model → call `build_embeddings` → returns `FastTextEmbeddings` instance |
| TS-1.1b | `test_factory_builds_lmstudio_provider` | Config `provider="lmstudio"` + lmstudio section → `build_embeddings` → returns `LMStudioEmbeddings` |
| TS-1.1c | `test_rejects_unknown_provider_value` | YAML with `provider="word2vec"` → `Config.from_yaml` → `pytest.raises(ValidationError, match="provider")` |
| TS-1.2 | `test_fasttext_embeddings_regression_locked` | `FakeFastTextModel` with fixed vectors → `embed(["x"])` → vector == recorded baseline, len 300, unit norm; no httpx used |
| TS-1.3 | `test_agent_returns_1024_dim_vector` | `EmbeddingAgent` with `MockTransport` returning one 1024-vector → `embed_batches(["t"])` → one 1024-length vector |
| TS-1.4 | `test_lmstudio_config_section_loads` | YAML with full lmstudio section → load → all five fields equal configured values |
| TS-1.5a | `test_rejects_unknown_lmstudio_key` | lmstudio section with extra key → load → `ValidationError` naming the key |
| TS-1.5b | `test_rejects_nonpositive_lmstudio_dimension` | `dimension=0` → load → `ValidationError` "greater than 0" |
| TS-1.5c | `test_rejects_nonpositive_token_window` | `max_input_tokens=0` → load → `ValidationError` "greater than 0" |
| TS-1.5d | `test_safety_fraction_range` | parametrize `[0.0→error, 1.5→error, 1.0→ok, 0.8→ok]` → load → respective outcomes |
| TS-1.6 | `test_lmstudio_selected_without_section_fails` | `provider="lmstudio"`, no lmstudio block → load → `ValidationError` naming missing section |
| TS-1.7a | `test_fasttext_startup_passes_with_model_file` | provider fasttext, model file in `tmp_path/models` → `validate_startup_environment` → no raise |
| TS-1.7b | `test_fasttext_startup_fails_without_model_file` | provider fasttext, no model file → validate → `FileNotFoundError` "model file not found" |
| TS-1.8a | `test_lmstudio_startup_passes_without_model_file` | provider lmstudio, no model file → validate → no raise |
| TS-1.8b | `test_lmstudio_startup_does_not_probe_endpoint` | provider lmstudio, unreachable URL, spy on transport → validate → no raise AND zero HTTP calls |
| TS-2.1 | `test_every_chunk_within_budget` | long doc, window 512, frac 0.8 → `chunk_text_by_tokens` → each chunk tiktoken len ≤ 409 |
| TS-2.2 | `test_chunk_size_scales_with_window` | parametrize window 256/512 → chunk same doc → max token len ≤ ~204 / ≤ ~409; 256 yields more chunks |
| TS-2.3 | `test_consecutive_chunks_overlap` | doc producing ≥2 chunks → chunk → each chunk after first shares a non-empty token run with predecessor |
| TS-2.4 | `test_chunks_cover_entire_document` | multi-chunk doc → chunk → every source token index present in ≥1 chunk |
| TS-2.5 | `test_whitespace_free_overbudget_is_split` | one no-space string > budget tokens → chunk → >1 chunk, each ≤ budget |
| TS-2.6 | `test_5000_char_nospace_input_lossless` | 5000-char no-space string, window 512 → chunk → >1 chunk, each ≤ budget, de-overlapped concat == input |
| TS-3.1a | `test_fasttext_index_dimension_300` | provider fasttext → build orchestration → FAISS created with dim 300 (assert via spy/captured arg) |
| TS-3.1b | `test_lmstudio_index_dimension_1024` | provider lmstudio (dim 1024) → build orchestration → FAISS created with dim 1024 |
| TS-3.2a | `test_index_rejects_mismatched_vector_length` | `LMStudioEmbeddings` dim 1024, agent returns len-300 vector → `embed` → `ValueError` "configured=1024" / "actual=300" |
| TS-3.2b | `test_query_rejects_mismatched_vector_length` | same, query path → search → dimension-mismatch error, no search performed |
| TS-3.3 | `test_dimension_mismatch_with_persisted_index_requires_reindex` | persisted FAISS at dim 300, provider lmstudio dim 1024 → index/query → explicit error mentioning re-index |
| TS-4.1a | `test_agent_unreachable_endpoint_errors` | `MockTransport` raising `ConnectError` → `embed_batches` → explicit error naming endpoint; no zero vector |
| TS-4.1b | `test_agent_http_500_errors` | `MockTransport` → 500 → `embed_batches` → explicit error; no vector |
| TS-4.2 | `test_agent_missing_vectors_errors` | 3 inputs, transport returns 2 embeddings → `embed_batches` → explicit count-mismatch error; nothing returned |
| TS-4.3 | `test_lmstudio_vectors_unit_normalized` | agent returns un-normalized vector → `LMStudioEmbeddings.embed` → L2 norm ≈ 1.0 |
| TS-4.4 | `test_query_uses_active_provider` | orchestration with lmstudio provider (spy) + fasttext fake → query → lmstudio agent called, fasttext fake not called |
| TS-4.5 | `test_overbudget_query_warns_not_silent` | lmstudio, query > budget tokens, `caplog` → embed query → warning logged AND returned vector’s source ≤ budget tokens AND vector produced |
| TS-EC-1 | `test_whitespace_document_rejected_before_embedding` | any provider (spy), whitespace doc → `index_document` → existing "must not be empty" error; embed not called |
| TS-EC-2 | `test_short_document_single_chunk` | doc under budget, window 512 → chunk → exactly 1 chunk, within budget |
| TS-EC-7 | `test_nonpositive_step_rejected` | overlap producing step ≤ 0 → chunk → existing "non-positive chunk step" error |
| TS-NG-1 | `test_provider_enum_is_closed` | parametrize invalid provider strings → load → all rejected (no implicit substitution) |

## Fixtures & Test Data

- **`fake_embeddings_transport(handler)`** (module helper) — builds an
  `httpx.MockTransport` from a callable mapping request → `httpx.Response`; injected
  into `EmbeddingAgent`. Variants: success (N vectors), 500, `ConnectError`,
  short-count, un-normalized vector.
- **`lmstudio_config_factory(**overrides)`** — returns a valid
  `LMStudioEmbeddingsConfig`/dict with sensible defaults, overridable per test
  (dimension, window, fraction, batch_size) to avoid hardcoded duplication.
- **`make_config_yaml(tmp_path, **sections)`** — writes a minimal valid `config.yaml`
  for config/startup tests, extending the pattern already in `test_config.py`.
- **`sample_documents`** — small prose doc (single chunk), long prose doc (many
  chunks), 5000-char no-space string (token-dense). Inline factories, not fixture
  files.
- **`real tiktoken encoding`** — `cl100k_base` (per OQ-2), loaded once per module.
- **Mock boundary:** only the LM Studio HTTP call and the fastText model are faked.
  Chunker, normalization, config, factory, and orchestration run for real (no
  over-mocking).
- **Lifecycle:** all fixtures are function-scoped except the tiktoken encoding
  (module-scoped, read-only) — preserves isolation under `pytest-randomly`.

## Alignment Check

**Full alignment.** Every scenario TS-1.1a … TS-NG-1 maps to exactly one test
function with setup, action, and assertion defined. No coverage gaps.

**Initial-failure check:** every test targets a component that does not yet exist
(`EmbeddingAgent`, `LMStudioEmbeddings`, `chunk_text_by_tokens`, `build_embeddings`,
the `provider`/`lmstudio` config fields, provider-aware startup) or new behavior on an
existing one — so all tests fail on first run, as required. The fasttext regression
lock (TS-1.2) is the one test over existing behavior; it is expected to *pass*
pre-change and acts as a guard that the refactor does not alter fastText output (noted
explicitly so it is not mistaken for a broken initial-failure case).

**No implementation coupling:** dimension/FAISS scenarios (TS-3.1a/b) assert the
dimension passed to the dense backend at construction — an observable boundary, not
private state. All other assertions are on return values, raised errors, or logged
warnings.

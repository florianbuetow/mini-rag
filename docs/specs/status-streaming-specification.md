# Chat Status Streaming - Behavioral Specification

## Objective

Surface real-time, non-persistent status updates while a chat completion request is being processed, so users can see what the system is doing before and during answer generation.

The feature must keep transient status updates separate from assistant answer text and chat history. Status updates must help the user understand the current stage of the RAG flow, including search, retrieval, reranking, final context size, and answer streaming, without polluting the persisted conversation.

## Background And Current Behavior

The existing chat endpoint already streams via Server-Sent Events (SSE):

- `POST /v1/chat/completions` returns `text/event-stream`.
- The backend currently emits every assistant text chunk as an anonymous `data: ...` SSE line.
- The backend ends the stream with `data: [DONE]`.
- The frontend reads the `fetch()` response body with `resp.body.getReader()`.
- The frontend currently treats every `data:` line, except `[DONE]`, as assistant answer text.
- The frontend appends streamed text into `assistantText`.
- After streaming completes, the frontend persists `currentMessages`, including the final assistant message, with `PUT /v1/chats/<id>`.

Relevant current files:

- `src/minirag/api/routes_chat_completions.py` owns the SSE endpoint.
- `src/minirag/agent.py` owns the Strands agent and the `search_documents` tool.
- `src/minirag/orchestration.py` owns dense, sparse, and hybrid search orchestration.
- `src/minirag/reranking/cross_encoder.py` owns optional cross-encoder reranking.
- `web/index.html` owns stream consumption, assistant text rendering, and chat persistence.

The existing conversational-agent specification explicitly says internal tool use is not surfaced. This feature changes that product contract by surfacing bounded progress metadata while preserving answer-only chat history.

## Current Codebase Findings

This section records implementation-relevant findings from the current codebase inspection.

### Backend Stream Path

Current behavior in `src/minirag/api/routes_chat_completions.py`:

- `StreamableAgent.stream(...)` is typed as `Generator[str, None, None]`.
- `_stream_agent_response(...)` wraps each yielded string as an anonymous SSE `data: ...` event.
- Stream completion is currently represented as anonymous `data: [DONE]`.
- Stream exceptions are currently serialized as anonymous `data: error: ...`, which makes errors look like assistant text to existing clients.
- The route owns HTTP-level validation for health, corpus existence, request model, search mode, `top_k`, `alpha`, and response headers.

Implication:

- The route is the correct place to serialize a typed internal event model into public SSE framing.
- Error events should become named `error` events with JSON payloads, while preserving a terminal `done` event.
- The route should not compute retrieval metrics because it does not see final `SearchResult` objects.

### Agent And Tool Path

Current behavior in `src/minirag/agent.py`:

- `MiniRagAgent.stream(...)` returns only assistant text chunks.
- `_stream_sync(...)` consumes `agent.stream_async(prompt)` and forwards events containing `"data"` only.
- `_stream_sync(...)` discards non-`data` lifecycle/tool events from Strands.
- `_make_search_tool(...)` creates the `search_documents` tool as a synchronous nested function.
- `search_documents(...)` performs retrieval and converts final results into one text payload for the LLM tool result.
- `search_documents(...)` has direct access to the exact final `SearchResult` list and therefore can compute final chunk and document metrics.

Implication:

- The agent layer is the right boundary for a typed internal stream event model.
- `search_documents(...)` needs a status callback or queue/event sink so it can emit retrieval status while keeping its synchronous tool return value.
- Final context metrics should be computed inside or immediately after `search_documents(...)`, using the exact list returned to the agent.
- The initial `generating_query` phase can be emitted before the Strands stream starts, but the exact moment the model has decided the tool query may require Strands lifecycle/tool events if available.

### Retrieval And Reranking Path

Current behavior in `src/minirag/orchestration.py`:

- `search_dense(...)` validates parameters, embeds the query, calls dense retrieval, and resolves chunks.
- `search_sparse(...)` validates parameters, calls sparse retrieval, and resolves chunks.
- `search_hybrid(...)` computes `should_rerank`.
- When reranking is active, `search_hybrid(...)` computes `retrieval_top_k` from `self._reranker.candidate_count(top_k)`.
- Dense and sparse searches are called with `retrieval_top_k`.
- Dense and sparse results are merged with `merge_hybrid_results(..., top_k=retrieval_top_k)`.
- If reranking is active, the merged candidates are passed to `self._reranker.rerank(..., top_k=top_k)`.
- The method currently returns only the final `list[SearchResult]`, not intermediate counts or trace data.

Current behavior in `src/minirag/reranking/cross_encoder.py`:

- `CrossEncoderReranker.candidate_count(top_k)` returns `top_k * candidate_multiplier`.
- `CrossEncoderReranker.rerank(...)` returns `ranked_results[:top_k]`.
- No relevance threshold, per-document cap, or token-budget pruning is applied.

Implication:

- Final context metrics can be implemented without changing orchestration.
- Exact `candidate_retrieval` metrics require either a trace object or instrumentation inside `search_hybrid(...)`.
- If the first implementation avoids orchestration trace changes, candidate status should stay generic or be omitted except where exact counts are available.
- Status copy must not imply relevance acceptance, thresholding, filtering, or full-corpus document counts.

### Frontend Stream Path

Current behavior in `web/index.html`:

- `sendMessage()` creates the user bubble and an empty assistant bubble before calling `/v1/chat/completions`.
- The stream parser reads `resp.body.getReader()` with `TextDecoder`.
- The parser currently handles only line-level `data:` fields.
- Every non-empty, non-`[DONE]` data value is appended to `assistantText`.
- Empty `data:` lines are interpreted as newline tokens.
- `data: error: ...` is appended to `assistantText` with error styling.
- After streaming, `currentMessages.push({ role: "assistant", content: assistantText })` persists exactly the accumulated assistant text.
- Markdown and JSON exports use `currentMessages`, so any status accidentally appended to `assistantText` would be persisted and exported.

Implication:

- The frontend needs a real SSE parser that tracks `event:` names and buffers all `data:` lines until the blank-line event boundary.
- Only `event: token` with `data.text` may mutate `assistantText`.
- `event: status` must update separate DOM-only state near the in-progress assistant bubble.
- `event: error` should be rendered deliberately as an error state, not routed through status or token handling.
- Persist/export safety is mostly achieved by preserving the existing `currentMessages` flow and keeping status outside `assistantText`.

### Test Surface

Current relevant tests and fixtures:

- `tests/test_api_routes_chat_completions.py` parses only anonymous `data:` lines and expects text chunks plus `[DONE]`.
- `tests_integration/test_chat_completion_contract.py` also parses only anonymous `data:` lines and expects `[DONE]`.
- `tests_e2e/conftest.py` fake completion streams currently emit legacy anonymous SSE chunks.
- `tests_e2e/test_chat_ui_streaming.py` verifies incremental assistant growth, disabled controls, request payloads, and persistence.
- `tests_e2e/test_chat_ui_error_states.py` assumes the fake error stream emits `data: error: ...`.

Implication:

- Backend and integration SSE helpers need to parse named events.
- E2E fake streams should be updated to emit typed `status`, `token`, `error`, and `done` events.
- Existing incremental-growth tests should continue to assert growth from token events.
- New persistence/export tests should explicitly assert status text is absent from `currentMessages`, Markdown export, and JSON export.

## User Stories And Acceptance Criteria

US-1: As a user, I want to see progress while the assistant is working, so that I know the request is active and where time is being spent.

Acceptance Criteria:
  AC-1.1: The UI displays a transient status message soon after sending a user message.
  AC-1.2: The UI updates the status as the backend moves through search, retrieval, reranking, context preparation, and answer streaming.
  AC-1.3: Status updates are displayed near the in-progress assistant response, not as standalone chat messages.
  AC-1.4: Status updates disappear, collapse, or settle into a final non-intrusive state after the assistant response completes.

US-2: As a user, I want status metrics to tell me how much context is being used, so that I can understand the retrieval footprint of the answer.

Acceptance Criteria:
  AC-2.1: After final retrieval selection, the UI shows the number of chunks used to generate the answer.
  AC-2.2: After final retrieval selection, the UI shows the number of unique documents used to generate the answer.
  AC-2.3: Unique documents are deduplicated by `document_id`, not by citation key, title, source path, or chunk count.
  AC-2.4: The status message includes both values, for example: `Using 8 chunks from 3 documents`.

US-3: As a user, I do not want internal status updates mixed into the conversation, so that chat history and exports contain only user and assistant content.

Acceptance Criteria:
  AC-3.1: Status events never mutate `assistantText`.
  AC-3.2: Status events are never pushed into `currentMessages`.
  AC-3.3: Status events are never persisted by `PUT /v1/chats/<id>`.
  AC-3.4: Status events are not included in Markdown or JSON chat exports.
  AC-3.5: Reloading a saved chat does not display historical status updates.

US-4: As a developer, I want a typed stream contract, so that frontend code can route answer tokens and status metadata safely.

Acceptance Criteria:
  AC-4.1: The SSE stream uses named event types, not only anonymous `data:` events.
  AC-4.2: Assistant answer text is carried only by token events.
  AC-4.3: Status metadata is carried only by status events.
  AC-4.4: Completion is represented by a dedicated done event or a backwards-compatible `[DONE]` sentinel.
  AC-4.5: Error handling remains explicit and does not cause status payloads to be rendered as answer text.

## Stream Contract

The backend should emit typed SSE events. The preferred event types are:

- `status` - transient progress metadata for the UI.
- `token` - assistant answer text that should be appended to the assistant message.
- `error` - stream-level error metadata.
- `done` - completion marker.

Example stream:

```text
event: status
data: {"timestamp":"2026-05-23T09:30:30.534637+00:00","message":"Preparing request...","type":"info"}

event: status
data: {"timestamp":"2026-05-23T09:30:30.536598+00:00","message":"Generating search query...","type":"info"}

event: status
data: {"timestamp":"2026-05-23T09:30:34.049676+00:00","message":"Searching corpus...","type":"info"}

event: status
data: {"timestamp":"2026-05-23T09:30:34.605220+00:00","message":"Using 50 chunks from 36 documents","type":"info"}

event: status
data: {"timestamp":"2026-05-23T09:34:20.888304+00:00","message":"Streaming answer...","type":"info"}

event: token
data: {"text":"The answer starts here"}

event: token
data: {"text":" and continues."}

event: done
data: {}
```

Rules:

- `token.data.text` is the only field that contributes to persisted assistant content.
- `status.data.message` is UI-only and must not be persisted.
- Status payloads must use exactly this public shape: `{"timestamp": string, "message": string, "type": "info" | "warn" | "error"}`.
- Status messages must be deterministic backend-compiled strings. The backend must not ask an LLM to generate status copy.
- No extra fields are required or used to render a status message.
- Numeric values embedded in `message` must describe observed behavior, not aspirational behavior.
- Do not say `Searched N documents` unless the backend actually exposes and measures that count.

## Status Messages

Current deterministic status messages:

- `Preparing request...`
- `Generating search query...`
- `Searching corpus...`
- `Using {chunk_count} chunks from {document_count} documents`
- `Using 0 chunks from 0 documents`
- `Streaming answer...`
- empty string `""` to reset/clear the UI status after answer processing completes

The UI renders only the `message` string and uses `type` for severity styling. It does not route status behavior by phase or extra metadata.

An empty status message is a control value with the same public status payload shape. The frontend must treat `{"message": ""}` as a request to clear and hide the status display. The empty reset status must not be rendered as visible text and must not be persisted.

## Retrieval Metrics

### Final Context Metrics

The final context metrics must be computed from the exact `SearchResult` list returned by the final retrieval call that is fed back to the agent.

For a result list named `results`:

```python
chunk_count = len(results)
document_count = len({result.document_id for result in results})
```

Status copy:

```text
Using {chunk_count} chunks from {document_count} documents
```

The document count must deduplicate by `document_id`.

### Candidate Metrics

Candidate metrics should be reported only when meaningful and observable.

For hybrid search with reranking enabled:

- `top_k` is the requested final chunk count.
- `candidate_multiplier` comes from `search.reranking.candidate_multiplier`.
- `retrieval_top_k = top_k * candidate_multiplier`.
- Dense search is called with `retrieval_top_k`.
- Sparse search is called with `retrieval_top_k`.
- Dense and sparse results are merged.
- The merged candidate list is reranked.
- The reranker returns the final `top_k` results.

Useful status copy:

```text
Retrieved {candidate_chunks} candidates for reranking
Reranking candidates...
Using {chunk_count} chunks from {document_count} documents
```

Candidate counts should reflect actual candidate list lengths where available, not merely the requested `retrieval_top_k`. For example, an under-populated corpus may return fewer candidates than requested.

For dense, sparse, or hybrid without reranking, candidate status should be skipped or generalized because there is no expanded reranking pool.

### Search Scope Metrics

The product should report corpus-wide search scope metrics when they can be obtained with explicit semantics and without a linear scan on every query.

Required semantics:

- `corpus_document_count` means the total number of source documents known to the corpus storage layer.
- `corpus_chunk_count` means the total number of stored chunks known to the corpus storage layer.
- Counts must come from storage/index metadata or an aggregate count query that is effectively O(1) for the request path.
- Counts may be loaded at backend startup or lazily on the first query for a corpus.
- Counts must be cached in the backend process until the next backend restart.
- No recounting is required during a backend process lifetime.
- Do not compute corpus-wide counts with a linear scan during chat processing.

Useful future status copy:

```text
Searching corpus with {corpus_document_count} documents and {corpus_chunk_count} chunks...
```

If only one count is available with clean semantics, status copy must only mention the available count.

The current codebase does not yet expose a clean public API for total documents or total chunks searched.

Current internal signals:

- FAISS has an internal `ntotal`, which corresponds to indexed vectors/chunks, not unique source documents.
- Tantivy has an internal `searcher.num_docs`, which corresponds to indexed sparse documents/chunks, not necessarily source documents.
- SQLite storage has `documents` and `chunks` tables, but the storage abstraction does not expose total counts.

Therefore, do not emit:

```text
Searched 381923 documents
```

unless a future implementation adds explicit corpus statistics with clearly defined semantics.

Potential future metrics:

- `corpus_document_count` - total source documents in the corpus.
- `corpus_chunk_count` - total chunks in the corpus.
- `dense_index_chunk_count` - total dense vectors searched.
- `sparse_index_chunk_count` - total sparse indexed chunks searched.

Until those exist, prefer:

```text
Searching corpus...
Using N chunks from M documents
```

### Token-Budget Context Pruning

Token-budget pruning is now in scope as the first quality-control mechanism for selected retrieval context.

Required behavior:

- Add a configuration value describing the fraction of the active model context window that may be used for retrieved documents.
- Example: `0.6` means up to 60% of the model context window may be used for retrieved/reranked document text in the LLM query.
- Discover the active model context window from the LM Studio API because the context window may vary by model.
- Use `tiktoken` to count document/context tokens for pruning.
- Apply pruning after search and reranking have produced an ordered result list.
- Preserve ranking order while pruning: keep the highest-ranked chunks that fit inside the document-token budget.
- Leave score thresholds and per-document caps out of this first pruning implementation.
- Status wording must distinguish searched/retrieved candidates from chunks actually included after token-budget pruning.

Potential status copy:

```text
Pruned context to {kept_chunk_count} chunks within {token_budget} document tokens
```

Final context metrics should describe the pruned context actually sent to the LLM, not the pre-pruning result list.

## Reranking And Quality Gate Behavior

There is currently no quality gate or score threshold that removes low-relevance chunks or documents after retrieval or reranking.

Current behavior:

- `top_k` caps how many final chunks are returned.
- `candidate_multiplier` expands only the pre-reranking candidate pool.
- Reranking re-sorts candidates and returns `ranked_results[:top_k]`.
- Dense/sparse scores are normalized.
- Reranker logits are sigmoid-normalized.
- No score is compared against a minimum threshold.
- No per-document cap is applied.
- No token-budget pruning is applied before returning the tool result.

Implication:

- A low-scoring chunk can still be fed to the LLM if it lands inside the final `top_k`.
- Status wording must not imply that selected chunks passed a relevance threshold unless such a threshold is implemented.
- Say `Using N chunks from M documents`, not `Accepted N relevant chunks`, unless a future quality gate is added.

Potential future quality-gate features after token-budget pruning:

- Add `min_score` or `score_threshold` after reranking/merging.
- Add a per-document chunk cap.
- If added, status should distinguish retrieved candidates from threshold-passing context.

This status streaming feature should not add a quality threshold unless explicitly requested as separate scope.

## Configuration

`candidate_multiplier` is set in configuration, not by the user per chat request.

Current config path:

```yaml
search:
  reranking:
    enabled: true
    model_name: cross-encoder/ms-marco-MiniLM-L12-v2
    candidate_multiplier: 3
```

Current code path:

- `src/minirag/config.py` defines `RerankingConfig.candidate_multiplier`.
- `src/minirag/api/app.py` passes `search_config.reranking.candidate_multiplier` to `CrossEncoderReranker`.
- `src/minirag/reranking/cross_encoder.py` computes `candidate_count(top_k)` as `top_k * candidate_multiplier`.
- `src/minirag/orchestration.py` uses that candidate count only when reranking is enabled and available.

Example:

- `top_k = 50`
- `candidate_multiplier = 3`
- reranking enabled
- dense retrieval requests up to 150 results
- sparse retrieval requests up to 150 results
- merged candidates are reranked
- final context is at most 50 chunks

## Backend Requirements

### SSE Framing

The backend must frame events with explicit SSE event names:

```text
event: status
data: {...}

event: token
data: {...}

event: done
data: {}
```

JSON data must be safely encoded. Newlines inside text must not break SSE framing.

### Agent Stream Events

The Strands SDK `stream_async()` emits more than plain answer text. It can expose lifecycle, tool-use, and text events.

Current code in `MiniRagAgent._stream_sync()` only forwards events containing `"data"`. This discards useful tool/lifecycle events such as current tool use. The implementation should introduce a typed internal stream event model rather than returning only plain strings.

Recommended internal event shapes:

```python
{"type": "status", "message": "Searching corpus...", "status_type": "info"}
{"type": "token", "text": "..."}
{"type": "error", "message": "..."}
{"type": "done"}
```

The public SSE route should serialize these internal events into named SSE events.

### Search Tool Instrumentation

The `search_documents` tool is the best place to emit retrieval-specific status because it has access to:

- the compiled tool query
- corpus
- search mode
- requested `top_k`
- `alpha`
- reranking flag
- final `SearchResult` list
- final chunk count
- final deduplicated document count

However, `search_documents` currently returns a tool result synchronously and does not have a status callback. Add a local callback or queue-based event sink that lets the tool emit status events into the same output stream used for answer tokens.

Possible implementation approach:

- `MiniRagAgent.stream(...)` returns typed events instead of strings.
- `MiniRagAgent._make_search_tool(...)` accepts a `status_callback`.
- The callback enqueues status events into the stream queue.
- `_stream_sync()` forwards both callback-generated status events and Strands text events.
- If status events cross thread boundaries, guard the `deque` with the minimal synchronization needed for correct wakeups and FIFO draining.

### Orchestration Instrumentation

If candidate-level status must be exact, `Orchestration.search_hybrid()` needs to expose or emit intermediate metrics:

- whether reranking was active
- effective `retrieval_top_k`
- dense result count
- sparse result count
- merged candidate count before reranking
- final result count after reranking

Options:

1. Return only final results and keep candidate status generic.
2. Add a `SearchTrace`/`SearchStats` object alongside final results.
3. Add an optional status callback to orchestration search methods.

Preferred for this feature:

- Add a small typed trace object if exact candidate metrics are needed.
- Keep existing query route behavior backwards-compatible.
- Avoid changing public `/v1/corpus/{corpus}/query/*` response contracts unless explicitly scoped.

## Frontend Requirements

The frontend stream parser must understand typed SSE events.

Current frontend behavior reads line-by-line and handles only `data:`.

Required behavior:

- Track the current SSE event name from `event: ...`.
- Accumulate one or more `data:` lines for an event.
- Dispatch complete events on blank lines.
- Parse JSON payloads for typed events.
- For `token`, append payload `text` to `assistantText`.
- For `status`, require `timestamp`, `message`, and `type`; update a separate transient status element with `message`.
- For `error`, display an error state without treating error metadata as normal assistant content.
- For `done`, stop or mark completion.
- For malformed JSON, anonymous legacy frames, unknown event names, or invalid payload shapes, display a descriptive stream contract error that includes the parser failure and a pretty-printed JSON payload when possible.
- For `status` with an empty `message`, clear and hide the global status display.

Persistence rule:

- `currentMessages.push({ role: "assistant", content: assistantText })` must use only accumulated token text.
- Status messages must not be included in `assistantText`.

Required UI behavior:

- Create the assistant bubble immediately as today.
- Add one persistent DOM element at the bottom of the current chat history for transient status display.
- Give this element a stable `id` so stream handling code can update it directly.
- Update this bottom status element as status events arrive.
- Keep the status element visually subordinate to chat messages.
- On empty status message, clear the status text and hide the status element.
- After the answer returns from the LLM, reset the status by sending an empty status message.

Status must not be rendered as a chat message, inside a persisted assistant bubble, or inside exportable message content.

## Error Handling

Errors must not be confused with assistant tokens.

Recommended behavior:

- Backend emits `event: error` with JSON data.
- Frontend adds error styling to the in-progress assistant bubble.
- Frontend may append a user-visible error message to the assistant bubble if needed, but this should be deliberate and should not be confused with status metadata.
- If partial answer tokens already exist, preserve them.
- If no answer tokens exist, display a concise error message.
- Existing behavior of saving partial/error content may remain, but status metadata must still be excluded.

Example:

```text
event: error
data: {"message":"LM Studio unreachable"}

event: done
data: {}
```

## Backwards Compatibility

No legacy anonymous SSE compatibility is required.

Current compatibility decision:

- `/v1/chat/completions` uses typed named SSE as the only supported chat stream contract.
- The web UI must consume typed named SSE.
- The MCP server must not expose chat status updates.
- The MCP server currently uses REST search/citation/list-corpora endpoints, not `/v1/chat/completions` SSE.
- If future MCP features call chat completions, they must consume the typed contract or explicitly ignore status events.
- Anonymous legacy `data:` frames should continue to be treated as stream contract errors in the UI.

No request flag, header, or version field is needed unless a future external client requirement is accepted.

## Tests

### Backend Unit Tests

Add or update tests in `tests/test_api_routes_chat_completions.py`.

Required assertions:

- The endpoint still returns `text/event-stream`.
- The stream emits at least one `status` event before the first `token` event.
- Answer text is emitted as `token` events.
- The stream ends with `done`.
- Error conditions emit `error` and `done`.
- Search settings (`search_mode`, `top_k`, `alpha`, `reranking`) are still passed to the agent.

Add test helper support for parsing named SSE events:

```python
[
    {"event": "status", "data": {...}},
    {"event": "token", "data": {"text": "..."}},
    {"event": "done", "data": {}},
]
```

### Agent Unit Tests

Add tests around `MiniRagAgent` or an extracted event-stream helper.

Required assertions:

- `search_documents` emits `searching` before executing retrieval.
- Final context status reports `chunks = len(results)`.
- Final context status reports `documents = len({result.document_id for result in results})`.
- Deduplication uses `document_id`.
- No-results retrieval emits `no_results` with zero chunks and zero documents.

### Orchestration Tests

If orchestration trace/stats are added, update `tests/test_orchestration.py` and `tests/test_reranker.py`.

Required assertions:

- Reranking enabled uses `top_k * candidate_multiplier` as the retrieval candidate count.
- Reranking disabled uses `top_k` directly.
- Candidate stats reflect actual returned candidate counts, not only requested counts.
- Final result count remains capped by `top_k`.
- No score threshold is applied unless a separate quality-gate feature is implemented.

### Frontend E2E Tests

Add or update tests in `tests_e2e/test_chat_ui_streaming.py`.

Required assertions:

- A status element appears while the assistant response is pending.
- The status text updates during streaming.
- The status element is the stable bottom-of-chat status element, not a persisted chat message.
- An empty status message clears and hides the status element.
- The final assistant message text does not contain status phrases such as `Searching`, `Using N chunks`, or `Streaming answer`.
- Persisted chat messages do not contain status text.
- Exported Markdown and JSON do not contain status text.
- The assistant response still grows incrementally over token events.
- Send controls remain disabled during streaming and re-enabled after completion.

## Non-Goals

- Do not add a quality threshold or relevance gate as part of this feature.
- Do not add per-document chunk caps as part of this feature.
- Do not persist status events in chat history.
- Do not expose raw internal prompts, full tool payloads, embeddings, reranker scores for every chunk, or sensitive implementation details.
- Do not change non-chat query endpoints unless required for shared internal instrumentation.

## Open Questions

1. Resolved: LM Studio model context metadata is read from `/api/v1/models`, using the active loaded instance `config.context_length` when available. `/api/v0/models` is used as a fallback for `max_context_length`, and the configured fallback token count is used if metadata cannot be fetched.
2. Resolved: browser/client disconnect cancellation is represented as a backend `threading.Event`; the sync bridge polls it, cancels the active async Strands/LM Studio stream task, and stops forwarding events.
3. Resolved: the default document context-window fraction is `0.6`.

## Implementation Notes

Likely implementation sequence:

1. Define a small internal event type for chat stream events.
2. Update the chat completions route to serialize typed events as named SSE events.
3. Update fake agents and backend tests to emit and parse typed events.
4. Add status callback support around `search_documents`.
5. Compute final context metrics from the exact final `SearchResult` list.
6. Optionally add orchestration search stats if exact candidate counts are required.
7. Update the frontend SSE parser to dispatch by event type.
8. Render status in an ephemeral DOM element separate from assistant content.
9. Verify persisted chat history and exports exclude status metadata.
10. Run unit tests and deterministic chat UI streaming tests.

## Implementation Readiness Map

This section records the current implementation anchors and recommended first-pass scope.

### Core Contract

The `/v1/chat/completions` stream should move from anonymous SSE chunks to typed named events:

- `status` - transient UI-only progress metadata.
- `token` - the only event type that mutates and persists assistant answer text.
- `error` - explicit stream-level errors.
- `done` - terminal marker.

Status must never enter `assistantText`, `currentMessages`, persisted chat history, Markdown export, or JSON export.

### Main Touch Points

- Backend SSE framing: `src/minirag/api/routes_chat_completions.py`.
  - Current behavior wraps every yielded string as `data: ...` and ends with `data: [DONE]`.
  - Required behavior serializes internal stream events as named SSE JSON events.
  - Required follow-up behavior sends an empty status message after LLM answer processing completes so the UI can clear status.
- Agent stream events: `src/minirag/agent.py`.
  - Current behavior yields only text chunks.
  - `_stream_sync()` currently discards non-`data` Strands lifecycle/tool events.
  - Required behavior should expose a small typed internal chat stream event model.
  - Required follow-up behavior should let Strands/tool lifecycle code fire-and-forget status events into a FIFO queue.
  - Preferred queue implementation is a Python `deque`, with a single backend reader using `popleft()` to forward events.
- Retrieval status and final metrics: `src/minirag/agent.py`.
  - `search_documents()` has the exact final `SearchResult` list.
  - It is the best first-pass location for `searching`, `context_ready`, and `no_results` status events.
  - Final metrics should be computed as `len(results)` and `len({result.document_id for result in results})`.
- Optional candidate metrics: `src/minirag/orchestration.py`.
  - Exact reranking candidate counts require a trace/stats object or a callback from hybrid search.
  - Final context metrics do not require orchestration changes.
- Frontend stream parser: `web/index.html`.
  - Current behavior treats every `data:` line as assistant text.
  - Required behavior parses full SSE events, dispatches by `event:`, and appends only `token.data.text`.
  - Required follow-up behavior renders status in one stable bottom-of-chat element and clears it when status `message` is empty.
- Persistence and export safety: `web/index.html`.
  - Existing persistence and exports already flow through `currentMessages`.
  - Keeping status out of `assistantText` preserves chat persistence, Markdown export, and JSON export boundaries.
- MCP server: `mcp/mini-rag.ts`.
  - Current tools use REST search, citation, and corpus-list endpoints.
  - MCP does not consume or expose chat-completion status events.
  - Status-streaming changes should not require MCP compatibility work unless a future MCP chat tool is added.

### Product Decisions - 2026-05-23

- Legacy anonymous SSE compatibility is not required.
- The supported surfaces are the web UI and MCP server.
- The web UI must use typed named SSE.
- The MCP server must not expose chat status updates.
- Corpus-wide metrics are desired if document/chunk counts can be obtained in O(1) or equivalent request-time cost and cached until backend restart.
- More granular lifecycle statuses are desired.
- Granular statuses should be implemented with fire-and-forget status writes into a FIFO queue, preferably a Python `deque`, read by the backend stream forwarder.
- Cancellation support is required for long-running LLM generation; search/retrieval cancellation is not a priority because those operations are effectively instantaneous for current use.
- Token-budget pruning is desired as the first context quality-control mechanism.
- Token-budget pruning should use a configured fraction of the active model context window, discover the context window from LM Studio, and count tokens with `tiktoken`.
- Status is only a live processing indicator.
- Completed answers should not retain status text.
- The backend must clear status after answer processing by sending an empty status message.
- The UI must render status in a stable bottom-of-chat element and hide that element when the empty reset status arrives.

### Test Touch Points

- Backend unit SSE contract: `tests/test_api_routes_chat_completions.py`.
- Integration SSE contract: `tests_integration/test_chat_completion_contract.py`.
- Deterministic fake streams: `tests_e2e/conftest.py`.
- UI streaming, persistence, and export assertions:
  - `tests_e2e/test_chat_ui_streaming.py`
  - `tests_e2e/test_chat_ui_export.py`

### First-Pass Scope Recommendation

Implement typed status, token, error, and done events end to end.

Include exact final context metrics because they are already available in `search_documents()`.

Skip exact `candidate_retrieval` metrics in the first pass unless orchestration trace plumbing is explicitly included. The stream contract allows unavailable metrics to be omitted, and this avoids changing non-chat query behavior just to expose intermediate hybrid-search internals.

## Implementation Status - 2026-05-23

This section records what the first implementation pass completed and what remains.

### Implemented

- [x] Added a typed internal chat stream event shape in `src/minirag/chat_stream.py`.
- [x] Made public status payloads intentionally small: `{"timestamp", "message", "type"}` only.
- [x] Kept status copy deterministic in backend constants/format strings; no LLM generation is used for status messages.
- [x] Changed `POST /v1/chat/completions` from anonymous answer chunks to named JSON SSE events:
  - [x] `event: status`
  - [x] `event: token`
  - [x] `event: error`
  - [x] `event: done`
- [x] Kept a small internal fake-agent normalization path in the route so a string yielded by an older test double is serialized as a `token` event; this is not public legacy SSE compatibility.
- [x] Added an initial `queued` status from the route before agent work begins.
- [x] Added `generating_query` status before the Strands stream starts.
- [x] Added `searching` status from the `search_documents` tool before retrieval executes.
- [x] Added `context_ready` status after final retrieval selection when results exist.
- [x] Added `no_results` status when final retrieval returns no chunks.
- [x] Added `streaming_answer` status before the first answer token emitted by `stream_async()`.
- [x] Suppressed model text emitted before retrieval context is ready, so query-planning whitespace or reasoning cannot leak into the persisted assistant answer.
- [x] Delayed `Streaming answer...` until the first token after `Using N chunks...` or `Using 0 chunks...`.
- [x] Set the LM Studio chat stream timeout to 15 minutes for slow local generation.
- [x] Computed final context metrics from the exact final `SearchResult` list returned to the agent:
  - [x] `chunks = len(results)`
  - [x] `documents = len({result.document_id for result in results})`
- [x] Deduplicated final document count by `document_id`.
- [x] Kept retrieval status events separate from the tool result text returned to the LLM.
- [x] Updated the web UI stream parser to read full SSE events:
  - [x] tracks `event:` names
  - [x] buffers one or more `data:` lines
  - [x] dispatches on blank-line event boundaries
  - [x] parses JSON payloads for typed events
- [x] Ensured only `token.data.text` mutates `assistantText`.
- [x] Added descriptive UI stream-contract errors for malformed messages:
  - [x] invalid JSON states the parse failure and pretty-prints the payload when possible
  - [x] invalid `status`, `token`, or `error` payload shapes state the expected JSON shape
  - [x] anonymous legacy `data:` frames state that named events are required
  - [x] unknown event names state the accepted event names
  - [x] the frontend aborts the fetch after a stream contract violation
- [x] Rendered status in a single stable bottom-of-chat `#chat-status` DOM element.
- [x] Added an empty reset status message after answer processing so the UI clears and hides `#chat-status`.
- [x] Kept status out of `currentMessages`, persisted chat payloads, Markdown export, and JSON export.
- [x] Updated deterministic fake chat-completion streams to emit typed status, token, error, and done events.
- [x] Updated backend and integration SSE parsing helpers to parse named events.
- [x] Added cached corpus-wide scope metrics:
  - [x] storage exposes `CorpusStats(document_count, chunk_count)`
  - [x] SQLite stores stats in a metadata table maintained by insert/delete triggers
  - [x] chat reads stored counts instead of scanning document/chunk rows
  - [x] `CorpusManager` caches counts per corpus until backend restart or explicit corpus destroy
- [x] Added a FIFO `ChatEventQueue` backed by `collections.deque`, with one reader draining via `popleft()`.
- [x] Routed deterministic tool/lifecycle statuses through the queue as fire-and-forget events.
- [x] Added client-disconnect cancellation plumbing for long-running LLM generation:
  - [x] the HTTP stream owns a cancellation event
  - [x] generator close sets the cancellation event
  - [x] the Strands async bridge polls the event
  - [x] cancellation calls `task.cancel()` on the active model stream
- [x] Added token-budget context pruning:
  - [x] config defines `search.context_pruning.document_context_fraction`
  - [x] config defines a fallback context-window token count
  - [x] LM Studio metadata discovers the active model context window per model and caches it
  - [x] `tiktoken` counts the exact chunk text shape returned to the LLM
  - [x] pruning runs after search/reranking and preserves result order
  - [x] final context metrics describe the pruned result list actually sent to the LLM

### Tested

- [x] Backend unit contract tests in `tests/test_api_routes_chat_completions.py`:
  - [x] endpoint still returns `text/event-stream`
  - [x] status event appears before the first token event
  - [x] answer text is emitted as `token` events
  - [x] stream ends with `done`
  - [x] stream errors emit `error` and `done`
  - [x] search settings still pass through to the agent
- [x] Agent status tests in `tests/test_agent_status_stream.py`:
  - [x] `search_documents` emits `searching` before retrieval
  - [x] cached corpus-wide scope metrics are included when available
  - [x] `context_ready` reports final chunk count
  - [x] `context_ready` reports unique document count by `document_id`
  - [x] no-results retrieval emits `no_results` with zero chunks and documents
  - [x] token pruning runs before final metrics
  - [x] FIFO queue ordering is preserved
  - [x] active model stream cancellation stops later tokens
- [x] Storage and corpus stats tests:
  - [x] SQLite stats track documents/chunks through trigger-maintained metadata
  - [x] stats survive reopening the database
  - [x] destroy resets stats to zero
  - [x] `CorpusManager` caches stats and invalidates them on destroy
- [x] LM Studio metadata tests:
  - [x] OpenAI-compatible `/v1` base URLs are converted to the LM Studio API root
  - [x] `/api/v1/models` loaded instance context length is preferred
  - [x] `/api/v1/models` max context fallback is supported
  - [x] `/api/v0/models` max context fallback is supported
- [x] Context pruning tests:
  - [x] result order is preserved
  - [x] chunks over the budget are skipped
  - [x] token counts use the exact returned context format
- [x] Deterministic browser tests in `tests_e2e/test_chat_ui_streaming.py`:
  - [x] status appears while the assistant response is pending
  - [x] status updates during streaming
  - [x] the bottom `#chat-status` element is hidden after the empty reset status
  - [x] final assistant message text excludes status phrases
  - [x] persisted chat messages exclude status text
  - [x] assistant response still grows incrementally from token events
  - [x] send controls remain disabled during streaming and re-enabled after completion
- [x] Deterministic export tests in `tests_e2e/test_chat_ui_export.py`:
  - [x] Markdown export excludes status text
  - [x] JSON export excludes status text
- [x] Integration contract tests in `tests_integration/test_chat_completion_contract.py` were updated to the typed SSE contract.
- [x] Mocked integration tests in `tests_integration/test_chat_status_stream_contract.py` validate backend emission for:
  - [x] status, token, done events
  - [x] status payload shape
  - [x] status type normalization
  - [x] agent exceptions becoming `error` plus `done`
  - [x] hybrid reranking candidate status remains UI-only status text
- [x] Exact hybrid reranking candidate metrics:
  - [x] orchestration exposes internal trace data without changing public query response contracts
  - [x] chat status reports the actual merged candidate count before reranking starts
  - [x] status emits `Retrieved {candidate_chunks} candidates for reranking`
  - [x] status emits `Reranking candidates...`
- [x] Orchestration trace tests:
  - [x] reranking-enabled retrieval candidate count expansion
  - [x] reranking-disabled direct `top_k` behavior
  - [x] actual returned candidate counts from under-populated result sets
  - [x] final result count remains capped by reranking output
- [x] Verification commands run:
  - [x] `uv run pytest tests/test_context_pruning.py tests/test_lm_studio.py tests/test_storage_sqlite.py tests/test_corpus.py tests/test_agent_status_stream.py tests/test_api_routes_chat_completions.py -q`
  - [x] `uv run pytest tests_integration/test_chat_status_stream_contract.py tests_integration/test_chat_completion_contract.py tests_e2e/test_chat_ui_streaming.py tests_e2e/test_chat_ui_export.py tests_e2e/test_chat_ui_error_states.py -q`
  - [x] `uv run ruff check src/minirag/config.py src/minirag/storage/interface.py src/minirag/storage/sqlite.py src/minirag/orchestration.py src/minirag/corpus.py src/minirag/context_pruning.py src/minirag/lm_studio.py src/minirag/chat_stream.py src/minirag/agent.py src/minirag/api/routes_chat_completions.py src/minirag/api/app.py tests/test_context_pruning.py tests/test_lm_studio.py tests/test_storage_sqlite.py tests/test_corpus.py tests/test_agent_status_stream.py tests/test_api_routes_chat_completions.py tests_integration/test_chat_status_stream_contract.py tests_e2e/test_chat_ui_streaming.py`
  - [x] `uv run mypy src/minirag/config.py src/minirag/storage/interface.py src/minirag/storage/sqlite.py src/minirag/orchestration.py src/minirag/corpus.py src/minirag/context_pruning.py src/minirag/lm_studio.py src/minirag/chat_stream.py src/minirag/agent.py src/minirag/api/routes_chat_completions.py src/minirag/api/app.py`
  - [x] `just ci-quiet`
  - [x] `uv run pytest tests/test_agent_status_stream.py tests/test_api_routes_chat_completions.py tests_integration/test_chat_status_stream_contract.py`
  - [x] `uv run pytest tests/test_api_routes_chat_completions.py tests/test_agent_status_stream.py tests_integration/test_chat_status_stream_contract.py tests_e2e/test_chat_ui_error_states.py tests_e2e/test_chat_ui_streaming.py`
  - [x] `uv run pytest tests/test_agent_status_stream.py tests/test_api_routes_chat_completions.py tests_integration/test_chat_status_stream_contract.py`
  - [x] `uv run ruff check src/minirag/chat_stream.py src/minirag/agent.py src/minirag/api/routes_chat_completions.py tests/test_agent_status_stream.py tests/test_api_routes_chat_completions.py tests_integration/test_chat_status_stream_contract.py`
  - [x] `uv run mypy src/minirag/chat_stream.py src/minirag/agent.py src/minirag/api/routes_chat_completions.py tests/test_agent_status_stream.py tests/test_api_routes_chat_completions.py tests_integration/test_chat_status_stream_contract.py`
- [x] Current-instance restart and status validation:
  - [x] `just stop`
  - [x] `just status` confirmed the service stopped
  - [x] `just start`
  - [x] `just status` confirmed the service was healthy on `127.0.0.1:9191`
- [x] End-to-end streaming validation against the current instance with model `qwen/qwen3.6-35b-a3b`, corpus `ai`, and the requested agent-orchestration query:
  - [x] observed `Preparing request...`
  - [x] observed `Generating search query...`
  - [x] observed two `Searching corpus...` updates because the model made two search tool calls
  - [x] observed `Using 50 chunks from 36 documents`
  - [x] observed `Using 50 chunks from 42 documents`
  - [x] observed `Streaming answer...`
  - [x] observed streamed `token` events
  - [x] observed terminal `done`
  - [x] observed no anonymous legacy `data:` frames
  - [x] observed no `error` event after increasing the LM Studio stream timeout

### Final Report

Implementation completed on the current instance only, using the configured service on `127.0.0.1:9191`.

Delivered behavior:

- Backend emits named SSE events: `status`, `token`, `error`, and `done`.
- Public status payloads are exactly `{"timestamp", "message", "type"}`.
- Status messages are deterministic backend strings and are not generated by the LLM.
- The UI renders malformed stream messages as descriptive stream contract errors with the parser failure and pretty-printed payload when possible.
- Pre-retrieval model text is suppressed so query-planning whitespace or reasoning cannot leak into the persisted assistant answer.
- `Streaming answer...` appears only when final answer tokens actually start.
- LM Studio streaming timeout is set to 15 minutes for slow local generation.
- Mocked integration tests validate backend event emission and edge cases.

Validation evidence:

- `uv run pytest tests/test_agent_status_stream.py tests/test_api_routes_chat_completions.py tests_integration/test_chat_status_stream_contract.py` passed with `32 passed`.
- Ruff passed for the touched Python source and status-streaming test files.
- Mypy passed for the touched Python source and status-streaming test files.
- Current-instance restart was validated with `just stop`, `just status`, `just start`, and `just status`; the service was healthy on `127.0.0.1:9191`.
- End-to-end stream test using `qwen/qwen3.6-35b-a3b`, corpus `ai`, and the requested agent-orchestration query emitted:
  - `Preparing request...`
  - `Generating search query...`
  - two `Searching corpus...` events because the model made two search tool calls
  - `Using 50 chunks from 36 documents`
  - `Using 50 chunks from 42 documents`
  - `Streaming answer...`
  - streamed `token` events
  - terminal `done`
- The raw E2E capture is `/private/tmp/minirag-status-e2e-timeout.sse`.
- The final E2E stream emitted no anonymous legacy frames and no `error` event.
- 2026-05-23 follow-up validation:
  - `uv run pytest tests/test_agent_status_stream.py tests/test_api_routes_chat_completions.py tests/test_reranker.py tests_integration/test_chat_status_stream_contract.py tests_integration/test_chat_completion_contract.py::TestChatCompletionSSE::test_sse_stream_with_done -q` passed with `50 passed`.
  - `just test-integration` passed with `58 passed, 6 skipped`.
  - `just test-e2e` passed with `128 passed, 3 skipped, 31 deselected`.
  - `just code-lspchecks` passed with `0 errors`.
  - `just ci-quiet` passed all checks, including quality gates, unit tests, integration tests, deterministic E2E, MCP tests, and Pyright.
  - Manual service restart and status checks passed with `just stop`, `just status`, `just start`, `just status`, and final `just stop`.
  - Manual raw SSE validation against `127.0.0.1:9191` with loaded model `gemma-3-1b-it` and corpus `knowledgebase` observed typed `status`, `token`, and terminal `done` events.

### Task List

- [x] STS-001: Add exact hybrid reranking candidate metrics.
  - Acceptance: when hybrid reranking is active, the stream can report the actual merged candidate count before reranking without guessing from requested `top_k`.
  - Depends on: orchestration trace plumbing or a status callback from `search_hybrid()`.
  - Completed: implemented with `search_hybrid_with_trace()` plus a reranking candidate callback.
- [x] STS-002: Add an orchestration-level search trace/stats object.
  - Acceptance: trace exposes reranking active, effective `retrieval_top_k`, dense count, sparse count, merged candidate count, and final result count.
  - Constraint: must not change public non-chat query response contracts unless explicitly scoped.
  - Completed: implemented as internal `SearchTrace`; public query endpoints still use result-only `search_hybrid()`.
- [x] STS-003: Add orchestration tests for candidate counts and reranking trace data.
  - Acceptance: tests prove reranking-enabled and reranking-disabled count behavior, actual returned candidate counts, and final `top_k` cap.
  - Depends on: STS-001 or STS-002.
  - Completed: implemented in `tests/test_reranker.py`; agent and mocked integration coverage were added for the status stream.
- [x] STS-004: Add cached corpus-wide search scope metrics.
  - Acceptance: status can report total corpus documents and chunks via explicit storage/retrieval APIs with agreed semantics.
  - Acceptance: counts are loaded at startup or first query and cached in backend memory until backend restart.
  - Acceptance: the chat request path does not perform a linear scan to compute corpus-wide counts.
  - Constraint: do not emit `Searched N documents` from FAISS/Tantivy internals alone.
  - Completed: implemented through `StorageReader.corpus_stats()`, SQLite `corpus_stats` metadata maintained by triggers, `Orchestration.corpus_stats()`, and `CorpusManager.corpus_stats()` process caching.
- [x] STS-005: Resolve legacy SSE compatibility/versioning.
  - Decision: no legacy anonymous SSE compatibility is required.
  - Evidence: the web UI consumes typed named SSE, and `mcp/mini-rag.ts` uses search/citation/list-corpora REST endpoints rather than chat SSE.
  - Constraint: if a future MCP chat tool is added, it must consume typed SSE or ignore status events explicitly.
  - Status: resolved by product decision; no version flag required.
- [x] STS-006: Add richer Strands lifecycle/tool-use status through a FIFO status queue.
  - Acceptance: Strands/tool lifecycle code can fire-and-forget deterministic status events without blocking on SSE serialization.
  - Acceptance: the backend stream forwarder drains events FIFO from a queue, preferably a Python `deque`, using a single reader with `popleft()`.
  - Acceptance: raw SDK events are translated into bounded deterministic user-facing messages, not exposed directly.
  - Constraint: do not add extra public status JSON fields just to render UI status.
  - Completed: implemented `ChatEventQueue` with `deque`, status callbacks for search/reranking/pruning/context-ready lifecycle events, and route serialization from typed internal events into bounded public status payloads.
- [x] STS-007: Propagate browser/client disconnect cancellation into active LM Studio generation.
  - Acceptance: if the frontend aborts the request, the backend stops the active LM Studio generation when possible.
  - Acceptance: implementation investigates the LM Studio API/client path to identify the correct cancellation mechanism before coding.
  - Constraint: only long-running LLM processing needs cancellation; search/retrieval operations are not the target.
  - Completed: the HTTP stream sets a cancellation event on generator close; the sync/async bridge polls it and cancels the active async task with `task.cancel()`.
- [x] STS-008: Add token-budget context pruning.
  - Acceptance: config defines the fraction of the active model context window available for retrieved document context.
  - Acceptance: the active model context window is discovered from LM Studio because it may vary per model.
  - Acceptance: document/context token counts use `tiktoken`.
  - Acceptance: pruning runs after search/reranking and preserves result order while keeping only chunks that fit the document-token budget.
  - Acceptance: final context metrics and status describe the pruned context actually sent to the LLM.
  - Constraint: do not add score thresholds or per-document caps in this task.
  - Completed: implemented `ContextPruner`, `LMStudioModelInfo`, config defaults, and chat-tool pruning before final metrics/tool text.
- [x] STS-009: Move status rendering to a bottom-of-chat resettable element.
  - Acceptance: the UI has one stable status element at the bottom of the current chat history with a stable `id`.
  - Acceptance: non-empty status messages update that element.
  - Acceptance: an empty status message clears and hides that element.
  - Acceptance: the backend sends an empty status message after the LLM answer completes.
  - Acceptance: status remains transient and is not persisted, exported, or replayed when reopening saved chats.
  - Completed: implemented `#chat-status`, `setChatStatus()`, backend empty reset status before `done`, and E2E coverage that the status element hides after completion.

### Deferred Scope Notes

- Legacy anonymous SSE compatibility.
  - No longer deferred; explicitly not required.
- Score threshold and per-document chunk caps.
  - These remain out of scope for the next pruning pass.
- Persisted historical status replay.
  - Status remains transient and intentionally is not stored with chat history.

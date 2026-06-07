# Reranker Quality Gate - Design And Implementation Plan

**Date:** 2026-05-23
**Status:** Proposed
**Related spec:** `docs/specs/status-streaming-specification.md`

## 1. Overview

Add an optional quality gate for RAG chat retrieval that filters the final reranked chunk list before it is fed back to the LLM.

The gate is controlled from the chat UI and persisted in each chat's `search_settings`. It is available only when reranking is active, because the gate relies on reranker scores as the strongest relevance signal currently available in mini-rag.

The quality gate is per chunk. Each chunk is evaluated independently. There is no per-document cap and no document-level diversity rule. `document_id` is used only for deduplicated reporting, not for selection.

## 2. Problem Statement

Today, chat retrieval sends the final `top_k` chunks to the agent/tool result. There is no quality threshold after dense retrieval, sparse retrieval, hybrid merge, or cross-encoder reranking.

Current behavior:

- `top_k` caps how many final chunks are returned.
- `candidate_multiplier` expands the candidate pool before reranking.
- Reranking sorts candidates and returns `ranked_results[:top_k]`.
- Scores are normalized or bounded in different ways, but no score is used as a cutoff.
- Low-scoring chunks can still be fed to the LLM if they are inside the final `top_k`.

This makes it hard to prevent weak context from influencing generated answers, especially when the corpus contains few relevant results or the requested `top_k` is high.

## 3. Goals

- Let users enable or disable a quality gate from the UI.
- Let users adjust a minimum reranker score between `0.0` and `1.0`.
- Let users configure a minimum number of top-ranked chunks that are always kept before threshold filtering starts.
- Apply the gate only when reranking is enabled.
- Apply the gate per chunk, after reranking.
- Keep chunk selection independent of `document_id`.
- Preserve existing chat search settings persistence.
- Provide clear backend validation so impossible combinations cannot silently behave differently than the UI suggests.
- Prepare status-streaming metrics so users can see how many chunks were kept and how many documents those chunks represent.

## 4. Non-Goals

- Do not add a per-document chunk cap.
- Do not add document-level diversity selection.
- Do not use `document_id` for filtering.
- Do not add token-budget pruning in this feature.
- Do not add a dense/sparse/hybrid score threshold when reranking is disabled.
- Do not calibrate a universal threshold across all models and corpora.
- Do not change ingestion, chunking, embedding, or citation behavior.
- Do not change standalone query endpoint response shapes unless necessary for internal reuse.

## 5. Terminology

- **Reranker score:** The normalized score assigned by `CrossEncoderReranker.rerank()`. In the current implementation, raw cross-encoder logits are passed through sigmoid, producing a value in `[0.0, 1.0]`.
- **Quality gate:** The post-reranking filter that decides which chunks are sent back to the agent.
- **Protected chunks:** The first `quality_min_chunks` chunks in reranked order. These are always kept while the quality gate is enabled.
- **Threshold-filtered chunks:** Chunks after the protected prefix. These are kept only when `score >= quality_min_score`.
- **Used chunks:** The final chunk list passed to the LLM/tool result after the quality gate.

## 6. Design Decisions

### 6.1 Use Reranker Scores, Not Dense Or Sparse Scores

The gate should use reranker scores because the cross-encoder directly scores `(query, chunk text)` pairs.

Dense, sparse, and hybrid scores are weaker threshold signals:

- Dense scores are embedding/model dependent.
- Sparse scores are normalized relative to the best sparse hit for that query.
- Hybrid scores blend query-relative dense and sparse values.
- Reranker scores are still not perfect probabilities, but they are the best available per-chunk relevance signal.

Therefore, strict quality gating requires reranking.

### 6.2 Gate After Reranking

The quality gate must run after reranking, not before.

Pipeline with gate enabled:

1. Retrieve dense and sparse candidates.
2. Merge hybrid candidates.
3. Rerank merged candidates.
4. Apply quality gate to the reranked result list.
5. Send the kept chunks to the agent/tool result.

### 6.3 Keep A Protected Prefix Before Applying The Threshold

The gate uses two values:

- `quality_min_chunks`
- `quality_min_score`

Selection rule:

1. Keep the first `quality_min_chunks` reranked chunks.
2. For the remaining reranked chunks, keep only chunks with `score >= quality_min_score`.

Example with `quality_min_chunks = 3` and `quality_min_score = 0.60`:

```text
rank 1 score 0.91 -> keep, protected by quality_min_chunks
rank 2 score 0.72 -> keep, protected by quality_min_chunks
rank 3 score 0.41 -> keep, protected by quality_min_chunks
rank 4 score 0.65 -> keep, passes threshold
rank 5 score 0.53 -> drop
rank 6 score 0.62 -> keep, passes threshold
```

This gives the model a minimum amount of context while pruning the low-scoring tail.

If `quality_min_chunks = 0`, the gate can return zero chunks. That is allowed and should produce the "no sufficiently relevant information found" path.

### 6.4 No Per-Document Cap

Do not add `max_chunks_per_document`.

Reasoning:

- A per-document cap is a diversity control, not a quality gate.
- If one document has many highly relevant chunks, a cap would remove useful evidence.
- Each chunk's quality must be evaluated independently.
- `document_id` remains useful for deduplicated reporting only.

### 6.5 Backend Must Enforce Eligibility

The UI should disable unavailable controls, but the backend must still validate the request.

Quality gate is active only when:

```text
search_mode == "hybrid"
reranking == true
quality_gate == true
```

If `quality_gate == true` and this condition is not met, the backend should reject the request with HTTP 422 rather than silently ignoring the gate.

## 7. User-Facing Settings

Add these fields to chat search settings:

```json
{
  "quality_gate": false,
  "quality_min_chunks": 3,
  "quality_min_score": 0.6
}
```

Suggested defaults:

- `quality_gate`: `false`
- `quality_min_chunks`: `3`
- `quality_min_score`: `0.6`

Validation:

- `quality_gate` must be boolean.
- `quality_min_chunks` must be an integer `>= 0`.
- `quality_min_chunks <= top_k`.
- `quality_min_score` must be a number in `[0.0, 1.0]`.
- `quality_gate == true` requires `search_mode == "hybrid"` and `reranking == true`.

Open default question:

- The exact default for `quality_min_score` should be treated as a starting point, not a calibrated universal threshold. It may be adjusted after evals.

## 8. UI Requirements

The chat settings panel should expose quality gate controls alongside search mode, top-k, alpha, and reranking.

Controls:

- Toggle: `Quality gate`
- Numeric control or stepper: `Min chunks`
- Slider plus numeric display/input: `Min score`

Availability rules:

- Quality gate controls are enabled only when `search_mode` is `hybrid` and reranking is enabled.
- If the user switches to dense or sparse mode, disable the quality gate controls.
- If the user disables reranking, disable the quality gate controls.
- Disabled controls may retain their last configured values, but the gate is inactive.

Persistence rules:

- Store all three values in `searchSettings`.
- Include all three values in `POST /v1/chats`.
- Include all three values in `PUT /v1/chats/<id>` when search settings change.
- Restore all three values when loading a saved chat.
- Include all three values in `POST /v1/chat/completions`.

Suggested UX behavior:

- If the quality gate is disabled because reranking is unavailable, visibly disable the controls.
- Do not use explanatory paragraphs in the app UI.
- Use compact labels and native controls consistent with the existing settings panel.

## 9. API Contract Changes

Extend `ChatCompletionRequest`:

```python
quality_gate: bool = False
quality_min_chunks: int = 3
quality_min_score: float = 0.6
```

Extend chat `search_settings` objects accepted and persisted by:

- `POST /v1/chats`
- `PUT /v1/chats/<chat_id>`
- `GET /v1/chats/<chat_id>`

Existing chat files without these fields should load with defaults.

Invalid request examples:

```json
{
  "search_mode": "dense",
  "reranking": true,
  "quality_gate": true
}
```

Expected result: HTTP 422, because quality gate requires hybrid reranking.

```json
{
  "search_mode": "hybrid",
  "reranking": false,
  "quality_gate": true
}
```

Expected result: HTTP 422, because quality gate requires reranking.

```json
{
  "top_k": 5,
  "quality_gate": true,
  "quality_min_chunks": 6
}
```

Expected result: HTTP 422, because `quality_min_chunks` cannot exceed `top_k`.

## 10. Backend Implementation Plan

### 10.1 Model The Gate Settings

Add a small model or dataclass for quality gate settings.

Possible type:

```python
class QualityGateConfig(BaseModel):
    enabled: bool = False
    min_chunks: int = 3
    min_score: float = 0.6
```

Or keep flat request fields if that better matches existing search settings:

```python
quality_gate: bool = False
quality_min_chunks: int = 3
quality_min_score: float = 0.6
```

Flat fields are likely less disruptive because existing chat search settings are flat.

### 10.2 Extend Agent Protocol

Update `StreamableAgent.stream(...)` to accept:

- `quality_gate: bool`
- `quality_min_chunks: int`
- `quality_min_score: float`

Update `MiniRagAgent.stream(...)` and `_make_search_tool(...)` with the same values.

### 10.3 Apply Gate In The Search Tool Or Orchestration

Preferred location for first implementation: inside `MiniRagAgent.search_documents`, after `orch.search_hybrid(...)` returns.

Reason:

- The quality gate is currently chat-agent behavior, not necessarily a standalone query endpoint behavior.
- It avoids changing `/v1/corpus/{corpus}/query/hybrid` behavior.
- It has immediate access to final `SearchResult` objects before they are formatted into the tool response.

Pseudo-code:

```python
def apply_quality_gate(
    results: list[SearchResult],
    min_chunks: int,
    min_score: float,
) -> list[SearchResult]:
    protected = results[:min_chunks]
    remaining = results[min_chunks:]
    passing = [result for result in remaining if result.score >= min_score]
    return [*protected, *passing]
```

Eligibility:

```python
gate_active = quality_gate and search_mode == "hybrid" and reranking
```

If `quality_gate` is true but not eligible, request validation should already have rejected the request.

### 10.4 No Results Path

If the gate removes all chunks:

- Return a tool result that says no sufficiently relevant documents were found.
- Do not feed weak chunks to the LLM.

Suggested tool text:

```text
No sufficiently relevant documents found in the corpus.
```

This should be distinct from:

```text
No relevant documents found in the corpus.
```

The distinction helps debug whether retrieval returned nothing or the quality gate filtered everything.

### 10.5 Metrics For Status Streaming

The quality gate should produce metrics that status streaming can emit later:

- `pre_gate_chunks`
- `post_gate_chunks`
- `protected_chunks`
- `threshold_kept_chunks`
- `dropped_chunks`
- `min_score`
- `min_chunks`
- `post_gate_documents = len({result.document_id for result in kept_results})`

Example status:

```text
Quality gate kept 5 of 50 chunks: 3 guaranteed, 2 above min score 0.60.
Using 5 chunks from 4 documents.
```

This feature can compute those metrics even if full status streaming lands separately.

## 11. Frontend Implementation Plan

### 11.1 State

Extend the default search settings:

```javascript
let searchSettings = {
    search_mode: 'hybrid',
    top_k: 50,
    alpha: 0.5,
    reranking: true,
    quality_gate: false,
    quality_min_chunks: 3,
    quality_min_score: 0.6
};
```

### 11.2 DOM

Add controls to the existing settings panel:

- `#quality-gate-toggle`
- `#quality-min-chunks`
- `#quality-min-score-slider`
- `#quality-min-score-value`

Use existing UI patterns from:

- reranking toggle
- top-k numeric input
- alpha slider/value display

### 11.3 UI Logic

Add helpers:

```javascript
function qualityGateAvailable() {
    return searchModeSelect.value === 'hybrid' && rerankingToggle.checked;
}

function updateQualityGateAvailability() {
    const enabled = qualityGateAvailable();
    qualityGateToggle.disabled = !enabled;
    qualityMinChunksInput.disabled = !enabled || !qualityGateToggle.checked;
    qualityMinScoreSlider.disabled = !enabled || !qualityGateToggle.checked;
}
```

Whenever search mode, reranking, or quality gate changes:

- update availability
- read settings from UI
- persist settings to local storage
- persist settings to the active chat when available

### 11.4 Request Payload

Include the fields in chat completion requests:

```javascript
body: JSON.stringify({
    messages: currentMessages,
    model: modelSelector.value,
    corpus: corpusSelector.value,
    search_mode: searchSettings.search_mode,
    top_k: searchSettings.top_k,
    alpha: searchSettings.alpha,
    reranking: searchSettings.reranking,
    quality_gate: searchSettings.quality_gate,
    quality_min_chunks: searchSettings.quality_min_chunks,
    quality_min_score: searchSettings.quality_min_score
})
```

## 12. Test Plan

### 12.1 Backend Route Tests

Update `tests/test_api_routes_chat_completions.py`.

Add tests:

- Defaults are passed to the agent when omitted.
- Explicit quality gate settings are passed to the agent.
- `quality_min_score < 0` returns 422.
- `quality_min_score > 1` returns 422.
- `quality_min_chunks < 0` returns 422.
- `quality_min_chunks > top_k` returns 422.
- `quality_gate == true` with dense mode returns 422.
- `quality_gate == true` with sparse mode returns 422.
- `quality_gate == true` with hybrid mode and reranking false returns 422.
- `quality_gate == true` with hybrid mode and reranking true is accepted.

### 12.2 Agent Tests

Add tests around the gate helper and/or `MiniRagAgent`.

Required cases:

- Keeps all chunks when gate disabled.
- Keeps first `min_chunks` even below threshold.
- Applies threshold only after `min_chunks`.
- Allows zero chunks when `min_chunks = 0` and none pass threshold.
- Deduped document count uses `document_id` only for metrics, not filtering.
- Does not cap chunks per document.

Example test data:

```text
rank 1 document_id=1 score=0.91
rank 2 document_id=1 score=0.72
rank 3 document_id=1 score=0.41
rank 4 document_id=2 score=0.65
rank 5 document_id=3 score=0.53
rank 6 document_id=1 score=0.62
```

With `min_chunks=3` and `min_score=0.60`, expected kept chunk ranks: `1, 2, 3, 4, 6`.

### 12.3 Chat Persistence Tests

Update `tests/test_api_routes_chats.py`.

Add tests:

- Creating a chat with quality gate settings persists them.
- Creating a chat without quality gate settings defaults them.
- Updating `search_settings` can update quality gate fields.
- Loading a chat returns quality gate fields.
- Existing chat files lacking these fields are normalized by frontend or handled with defaults.

### 12.4 Frontend E2E Tests

Update deterministic chat UI tests.

Add tests:

- Quality gate controls are visible in the settings panel.
- Controls are enabled only when mode is hybrid and reranking is enabled.
- Toggling quality gate changes request payload.
- Adjusting min chunks changes request payload.
- Adjusting min score changes request payload.
- Settings persist across chat reload.
- Settings are restored when clicking a saved chat.

### 12.5 Reranker / Orchestration Tests

No orchestration behavior change is required if the gate is implemented in `MiniRagAgent`.

If the gate is moved into orchestration later, add tests that prove:

- Query endpoints either opt into or do not use the gate explicitly.
- Reranker output is filtered after reranking.
- Public query route behavior remains documented.

## 13. Rollout Sequence

Recommended implementation order:

1. Add request model fields and backend validation.
2. Update fake agents and route tests.
3. Add a pure quality gate helper with unit tests.
4. Thread settings through `StreamableAgent` and `MiniRagAgent`.
5. Apply the helper after reranked hybrid search in `search_documents`.
6. Add UI controls and search settings persistence.
7. Add frontend payload tests and e2e tests.
8. Add status metrics hooks if status streaming is implemented in the same branch.
9. Run unit tests and deterministic chat UI tests.

## 14. Risks And Mitigations

Risk: Users may treat `quality_min_score` as a universal relevance probability.

Mitigation: Keep the setting adjustable and describe it internally as a reranker score threshold, not a probability.

Risk: `quality_min_chunks` can preserve low-scoring chunks.

Mitigation: This is intentional. Users can set `quality_min_chunks = 0` for strict filtering.

Risk: Quality gate silently inactive due to disabled reranking.

Mitigation: Disable controls in the UI and reject invalid backend combinations.

Risk: Existing saved chats lack the new settings.

Mitigation: Apply defaults when loading or normalizing search settings.

Risk: The threshold default may be too high or too low.

Mitigation: Treat `0.6` as provisional and adjust after evals.

## 15. Open Questions

1. Should the first implementation default `quality_gate` to off for all existing and new chats?
2. Is `quality_min_score = 0.6` an acceptable provisional default, or should it start lower until eval data exists?
3. Should `quality_min_chunks` default to `3`, or should it default to `1` to make the gate stricter?
4. Should standalone query endpoints eventually support quality gate parameters, or should this remain chat-only?
5. Should the future status-streaming feature show pre-gate and post-gate counts even when the quality gate is disabled?


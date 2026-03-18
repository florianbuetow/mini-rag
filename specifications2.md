# Chat UI Test Expansion Specification

## 1. Purpose

Define the next test suite for the chat UI so that it covers:

- the actual browser behavior of the single-page chat UI,
- the backend contracts the UI depends on,
- the full RAG user journey against real corpora,
- LM Studio readiness and model availability,
- failure and recovery cases that are currently either untested or only partially tested.

This document is implementation-focused. It is intentionally more detailed than the existing `docs/specs/chat-ui-test-specification.md` and `docs/specs/chat-ui-test-implementation-specification.md`.

## 2. Review of Current State

### 2.1 What already exists

- Behavioral specs for chat UI, chat persistence, conversational agent, static serving, and integration live under `docs/specs/`.
- A browser suite exists in `tests_e2e/test_chat_ui.py`.
- A narrow real-RAG browser suite exists in `tests_e2e/test_rag_journey.py`.
- Unit coverage exists for chat CRUD and chat completions routes.

### 2.2 Gaps in the current plan and implementation

The current documentation and tests are not enough to prove the UI works end to end.

Main gaps:

- The existing browser tests are mostly smoke tests. Many of them only assert visibility or element counts and do not verify request payloads, saved state, or semantic correctness.
- The current browser suite does not cover most failure paths in a deterministic way.
- The `knowledgebase` and `llmevals` corpora requested for real-RAG testing do not currently exist in `data/input/`; they must be seeded by the test harness.
- LM Studio is treated as an external prerequisite instead of something the suite can validate and prepare.
- The existing real-RAG journey only covers two prompts in one corpus and does not exercise cross-corpus isolation, follow-ups, or negative cases.
- Several important UI behaviors from the existing chat UI spec are either unimplemented or not verified:
  - restoring the last active chat after refresh,
  - warning when chat save fails,
  - JSON export containing the full chat object rather than a partial export payload.

### 2.3 Testing philosophy for the new suite

Follow `AGENTS.md`, `bestpractices.md`, and the existing specs:

- never assume environment state,
- seed or verify everything explicitly,
- fail fast with actionable messages,
- prefer deterministic browser tests for mechanics,
- use real full-stack tests only where real retrieval/model behavior matters,
- keep browser tests isolated and order-independent,
- run `just ci-quiet` regularly during implementation to verify the repo still meets the required quality bar,
- when `just ci-quiet` fails, fix the code or tests so they satisfy the existing checks; do not weaken, bypass, or rewrite the checks just to make the suite pass.

## 3. Proposed Test Architecture

The new suite should be split into three layers.

### 3.1 Layer A: Deterministic browser e2e

Purpose:

- prove the UI mechanics,
- prove request payloads and persistence behavior,
- remove LLM variability from tests that do not need it.

Approach:

- start a dedicated test server that serves the real `web/` app,
- use deterministic fake model data and deterministic streaming responses,
- keep the backend chat CRUD routes real,
- replace only the chat completion agent and LM Studio model proxy behavior where needed.

Recommended files:

- `tests_e2e/test_chat_ui_shell.py`
- `tests_e2e/test_chat_ui_sidebar.py`
- `tests_e2e/test_chat_ui_streaming.py`
- `tests_e2e/test_chat_ui_export.py`
- `tests_e2e/test_chat_ui_error_states.py`

### 3.2 Layer B: Real full-stack RAG browser e2e

Purpose:

- prove that the UI can drive a real chat session with real retrieval and a real loaded LM Studio model,
- prove corpus switching and semantic separation across corpora,
- prove citation-backed answers for real content.

Approach:

- seed `knowledgebase` and `llmevals`,
- ingest both corpora,
- ensure LM Studio has an allowed model loaded,
- run Playwright against the real service and real model.

Recommended files:

- `tests_e2e/test_chat_ui_rag_knowledgebase.py`
- `tests_e2e/test_chat_ui_rag_llmevals.py`
- `tests_e2e/test_chat_ui_cross_corpus.py`

### 3.3 Layer C: Integration tests

Purpose:

- verify service startup, ingestion, LM Studio readiness, and backend boundaries without the browser,
- keep environment preparation failures separate from UI failures.

Recommended files:

- `tests_integration/test_chat_ui_service_boot.py`
- `tests_integration/test_chat_ui_seed_and_ingest.py`
- `tests_integration/test_lm_studio_readiness.py`
- `tests_integration/test_chat_completion_contract.py`

## 4. Required Harness Changes

## 4.1 Dedicated test config and temp data dir

Do not reuse developer data.

For browser and integration runs, generate a temporary config and data tree per session:

- `tmp/data/input/knowledgebase/txt/`
- `tmp/data/input/llmevals/txt/`
- `tmp/data/storage/`
- `tmp/data/index/`
- `tmp/data/models/`
- `tmp/chats/`

Use an isolated service port for most browser tests. Keep one separate integration test that explicitly verifies the production contract on port `9191`.

## 4.2 Corpus seeding is mandatory

Because the requested corpora are not present in the repo, the suite must create them explicitly.

Do not make the tests depend on manually maintained local corpora.

Seed files should be plain `.txt` files created by the test harness, not copied from an uncontrolled workstation directory.

## 4.3 LM Studio readiness is mandatory

Before real-RAG tests:

1. Probe `http://127.0.0.1:1234/v1/models`.
2. If an allowed model is already loaded, use it.
3. If no allowed model is loaded, use the local `lms` CLI to prepare one.
4. If the CLI is unavailable or no allowed local model exists on disk, fail with a clear message and skip only the real-RAG subset.

Allowed model policy:

- Prefer `gemma` instruct/chat variants.
- Prefer `qwen` instruct/chat variants below 32B.
- Reject very large models by pattern, such as `32b`, `70b`, `72b`, `110b`, `405b`.

Suggested load order:

1. `qwen` instruct/chat <= 14B
2. `gemma` instruct/chat <= 12B
3. any other allowed `qwen` or `gemma` under 32B

Suggested CLI flow:

1. `lms server status`
2. if needed: `lms server start`
3. `lms ps`
4. if loaded models are unsuitable: `lms unload --all`
5. `lms ls`
6. `lms load <model-key> --identifier e2e-model -y`
7. poll `GET http://127.0.0.1:1234/v1/models` until `e2e-model` or the loaded model id appears

The tests must not auto-download models.

## 5. Browser Coverage List

The following behaviors should be covered across deterministic browser e2e and real-RAG browser e2e.

### 5.1 App shell and boot

- root URL serves the chat app
- CSS is loaded
- sidebar, selectors, chat area, and composer all render
- app handles empty chats state
- app handles empty corpora state
- app handles empty or unavailable model list state

### 5.2 Model selector

- model list populates from `/v1/models`
- option labels equal model ids
- preferred lightweight model is selected by default
- switching model changes the next `/v1/chat/completions` payload
- model selection persists when loading an existing chat

### 5.3 Corpus selector

- corpus list populates from `/v1/corpora`
- corpora are alphabetically ordered
- default corpus is the first alphabetical corpus
- switching corpus changes the next `/v1/chat/completions` payload
- corpus selection persists when loading an existing chat

### 5.4 Sidebar and chat CRUD

- no chats empty state
- new chat creates a persisted chat using currently selected model and corpus
- sidebar order is newest first
- active chat highlight updates correctly
- clicking a sidebar entry loads full history
- rename via button
- rename via double-click
- `Escape` cancels rename
- blur commits rename
- blank rename is rejected
- long chat names render without breaking layout
- delete inactive chat removes only that chat
- delete active chat clears the transcript

### 5.5 Composer and transcript

- user message appears immediately
- assistant bubble appears before stream completion
- assistant text grows incrementally during stream
- send button and textarea are disabled while streaming
- composer is re-enabled after stream completion
- transcript auto-scrolls to bottom during long streams
- HTML-like user content is rendered as text, not executed
- very long assistant content remains visible and scrollable

### 5.6 Persistence and refresh

- after a successful response, the saved chat contains the full user and assistant history
- loading a saved chat restores transcript, model, and corpus
- refreshing the page restores the last active chat if that behavior is implemented
- if last-active restore is not implemented yet, the test should be marked as a required gap and added when the feature lands

### 5.7 Export

- export menu opens and closes correctly
- Markdown download uses `.md`
- JSON download uses `.json`
- Markdown includes both roles and contents in order
- JSON export contains the full chat object, not a reduced payload
- export filename is derived from the visible chat name and sanitized

### 5.8 Error handling

- LM Studio unavailable while loading models
- chat stream returns an SSE error after partial output
- chat persistence `PUT` fails after response completion
- chat list load fails
- specific chat load fails
- delete request fails

### 5.9 Cross-corpus isolation

- same prompt on different corpora yields different citations
- corpus switch only affects the next turn
- an existing chat reopened later still uses its stored corpus unless the user changes it
- answers from `knowledgebase` do not cite `llmevals` documents and vice versa

## 6. Deterministic Browser Test Cases

These are the required deterministic browser tests. They are not corpus-semantic tests; they prove UI mechanics and request/response handling.

1. App boot renders shell.
2. Empty sidebar state shown when no chats exist.
3. Model selector populates and default model is preferred lightweight option.
4. Corpus selector populates and defaults to first alphabetical corpus.
5. New chat sends `POST /v1/chats` with current model and corpus.
6. New chat clears transcript and inserts a sidebar entry.
7. Clicking a saved chat loads transcript, model, and corpus.
8. Sidebar shows chats newest first.
9. Rename via edit button sends `PUT /v1/chats/<id>` with `name`.
10. Rename via double-click works.
11. Blank rename is rejected.
12. Rename `Escape` cancels.
13. Delete inactive chat removes it from sidebar.
14. Delete active chat clears the transcript.
15. User message appears before stream completes.
16. Assistant message grows incrementally over at least two chunks.
17. Send controls are disabled for the duration of streaming.
18. Browser request to `/v1/chat/completions` contains full message history.
19. Browser request to `/v1/chat/completions` contains selected model.
20. Browser request to `/v1/chat/completions` contains selected corpus.
21. Successful completion triggers chat persistence `PUT` with full history.
22. Stream error after partial output preserves visible partial text.
23. Save failure after response surfaces a visible warning.
24. Export Markdown content is structurally correct.
25. Export JSON contains full chat object fields: `id`, `name`, `model`, `corpus`, `messages`, `created_at`, `updated_at`.
26. Refresh restores last active chat when implemented.
27. User-supplied HTML is escaped in transcript rendering.
28. Long transcript auto-scrolls to the latest message.

## 7. Integration Test Cases

These tests should run without Playwright.

1. Seed `knowledgebase` and `llmevals` into an isolated temp data dir.
2. Ingest `knowledgebase` successfully.
3. Ingest `llmevals` successfully.
4. `GET /v1/corpora` returns exactly `["knowledgebase", "llmevals"]` in sorted order.
5. `GET /v1/models` returns an empty data set when LM Studio is unreachable and does not hard-fail the service.
6. LM Studio readiness helper accepts an already-loaded allowed model.
7. LM Studio readiness helper unloads a disallowed large model and loads an allowed model when possible.
8. Chat completion route returns SSE and `[DONE]`.
9. Chat completion route rejects invalid corpus for the seeded service.
10. Chat completion route streams an error when the model provider fails.
11. `just start` or the equivalent launched service serves `/` and `/v1/*` on the same port.
12. Startup without `web/` still serves API endpoints and returns 404 at `/`.

## 8. Seed Corpus Design

The harness must create deterministic seed documents with stable citation keys.

### 8.1 knowledgebase corpus

Create these files in `input/knowledgebase/txt/`.

| Citation key | Topic | Required facts |
|---|---|---|
| `kb_intent_engineering.txt` | intent engineering | intent engineering is the practice of specifying user goals, constraints, tools, and evaluation criteria; it is broader than prompt wording alone |
| `kb_prompt_engineering.txt` | prompt engineering | prompt engineering focuses on phrasing prompts; intent engineering includes task framing, tools, guardrails, and validation |
| `kb_rag_basics.txt` | RAG basics | retrieval augmented generation combines retrieval with generation; retrieve first, then ground answer in source text |
| `kb_hybrid_search.txt` | hybrid retrieval | hybrid search combines dense and sparse retrieval; reranking can improve relevance |
| `kb_chunking.txt` | chunking | chunk size and overlap affect recall, precision, and duplication |
| `kb_citations.txt` | citation behavior | grounded answers should cite source documents with bracketed citation keys |
| `kb_chat_persistence.txt` | chat storage | chats are stored with `id`, `name`, `model`, `corpus`, `messages`, `created_at`, `updated_at` |
| `kb_export.txt` | exports | Markdown export is human-readable; JSON export should contain the full chat object |
| `kb_corpora.txt` | corpora list | corpora are listed alphabetically and can be switched between turns |
| `kb_models.txt` | model guidance | prefer smaller `gemma` or `qwen` instruct/chat models for local tool-using tests |
| `kb_streaming.txt` | SSE behavior | assistant text should stream incrementally and disable duplicate sends |
| `kb_no_results.txt` | no-results behavior | if nothing relevant is found, the assistant should say so instead of hallucinating |

### 8.2 llmevals corpus

Create these files in `input/llmevals/txt/`.

| Citation key | Topic | Required facts |
|---|---|---|
| `le_rouge_l.txt` | ROUGE-L | ROUGE-L recall measures longest common subsequence overlap against a reference |
| `le_precision_recall_at_k.txt` | retrieval metrics | precision@k measures relevance within top-k; recall@k measures coverage of relevant items in top-k |
| `le_groundedness.txt` | groundedness | groundedness checks whether generated claims are supported by retrieved evidence |
| `le_hallucination.txt` | hallucination checks | unsupported claims, wrong citations, and fabricated facts are evaluation failures |
| `le_judge_models.txt` | judge models | judge-model evaluations are useful but can be biased and should be calibrated |
| `le_pairwise.txt` | pairwise evaluation | pairwise comparison is useful for ranking two model outputs against each other |
| `le_dataset_design.txt` | eval dataset design | evaluation sets should cover easy, medium, hard, and adversarial examples |
| `le_latency.txt` | latency budgets | evaluation should track latency separately for retrieval, generation, and full turn time |
| `le_reproducibility.txt` | reproducibility | fix seedable variables when possible and record model, corpus, and prompt versions |
| `le_error_analysis.txt` | error analysis | bucket failures by retrieval miss, grounding miss, citation miss, or reasoning miss |
| `le_thresholds.txt` | pass-fail thresholds | thresholds should be explicit and metric-specific rather than subjective |
| `le_reporting.txt` | reporting | reports should show scenario id, prompt, corpus, citations, latency, and pass/fail result |

## 9. Real-RAG Scenario Assertions

Each real-RAG browser scenario must use fuzzy assertions, not exact full-string matches.

Minimum assertions per scenario:

- assistant response is non-empty,
- response contains at least two expected keywords or stems,
- response contains at least one citation marker,
- response contains at least one expected citation key from the active corpus,
- for cross-corpus tests, response must not cite a document from the wrong corpus.

Preferred helper functions:

- `send_message_and_wait(page, text, timeout_ms=120000) -> str`
- `select_corpus(page, corpus_name)`
- `select_model(page, model_id)`
- `current_assistant_text(page) -> str`
- `assert_has_keywords(text, keywords, minimum=2)`
- `assert_has_citation_keys(text, keys)`
- `assert_lacks_citation_keys(text, keys)`
- `fetch_saved_chat(api_client, chat_id) -> dict`

## 10. knowledgebase Scenario Set

Implement all of the following as Playwright tests against the real service and real corpus.

| ID | Prompt / flow | Required assertions |
|---|---|---|
| `KB-01` | ask: `What is intent engineering?` | mentions `intent` and `engineering`; cites `kb_intent_engineering.txt` |
| `KB-02` | ask: `How is intent engineering different from prompt engineering?` | mentions both terms and a contrast such as `broader`, `constraints`, or `tooling`; cites `kb_intent_engineering.txt` or `kb_prompt_engineering.txt` |
| `KB-03` | ask: `What is retrieval augmented generation?` | mentions retrieval and generation; cites `kb_rag_basics.txt` |
| `KB-04` | ask: `Why use hybrid search instead of only dense search?` | mentions dense plus sparse and relevance; cites `kb_hybrid_search.txt` |
| `KB-05` | ask: `How do chunk size and overlap affect retrieval?` | mentions `chunk`, `overlap`, `recall`, or `duplication`; cites `kb_chunking.txt` |
| `KB-06` | ask: `How should grounded answers show citations?` | mentions bracketed citation keys or source references; cites `kb_citations.txt` |
| `KB-07` | ask: `What fields are stored when a chat is persisted?` | mentions at least four stored fields; cites `kb_chat_persistence.txt` |
| `KB-08` | ask: `What is the difference between Markdown export and JSON export?` | contrasts readability vs full object fidelity; cites `kb_export.txt` |
| `KB-09` | ask: `How are corpora listed and switched in the chat UI?` | mentions alphabetical ordering and turn-level switching; cites `kb_corpora.txt` |
| `KB-10` | ask: `Which local models should we prefer for e2e testing?` | mentions `gemma` or `qwen` and smaller local models; cites `kb_models.txt` |
| `KB-11` | multi-turn: ask `What is SSE in this app?`, then `Why should duplicate sends be blocked?` | second answer mentions streaming and disabled inputs, uses prior context, cites `kb_streaming.txt` |
| `KB-12` | ask an out-of-scope question such as `Who won the 1998 World Cup?` | either states that no relevant documents were found or refuses to ground from corpus; should not invent a `kb_` citation |

## 11. llmevals Scenario Set

Implement all of the following as Playwright tests against the real service and real corpus.

| ID | Prompt / flow | Required assertions |
|---|---|---|
| `LE-01` | ask: `What does ROUGE-L recall measure?` | mentions longest common subsequence or overlap vs reference; cites `le_rouge_l.txt` |
| `LE-02` | ask: `What is the difference between precision@k and recall@k?` | contrasts precision vs coverage; cites `le_precision_recall_at_k.txt` |
| `LE-03` | ask: `What is groundedness in an LLM evaluation?` | mentions support from evidence or retrieved documents; cites `le_groundedness.txt` |
| `LE-04` | ask: `How should we detect hallucinations in evals?` | mentions unsupported claims, fabricated facts, or wrong citations; cites `le_hallucination.txt` |
| `LE-05` | ask: `What are the risks of using judge models?` | mentions bias or calibration; cites `le_judge_models.txt` |
| `LE-06` | ask: `When should we use pairwise evaluation?` | mentions ranking or comparing two outputs; cites `le_pairwise.txt` |
| `LE-07` | ask: `How should we design an evaluation dataset?` | mentions easy, medium, hard, or adversarial coverage; cites `le_dataset_design.txt` |
| `LE-08` | ask: `What latency numbers should an eval report include?` | mentions retrieval, generation, or total turn time; cites `le_latency.txt` |
| `LE-09` | ask: `What makes an eval reproducible?` | mentions versions, seeds, model, corpus, or prompt tracking; cites `le_reproducibility.txt` |
| `LE-10` | ask: `How should we categorize failures during error analysis?` | mentions retrieval miss, grounding miss, citation miss, or reasoning miss; cites `le_error_analysis.txt` |
| `LE-11` | ask: `How should pass-fail thresholds be defined?` | mentions explicit metric-specific thresholds; cites `le_thresholds.txt` |
| `LE-12` | ask: `What should be in an eval report for each scenario?` | mentions scenario id, prompt, citations, latency, or pass/fail; cites `le_reporting.txt` |

## 12. Cross-Corpus Scenario Set

Implement at least these additional real-RAG tests.

| ID | Flow | Required assertions |
|---|---|---|
| `CC-01` | ask `What is groundedness?` in `knowledgebase`, then in `llmevals` | responses differ; `llmevals` cites `le_groundedness.txt`; `knowledgebase` does not cite `le_` docs |
| `CC-02` | ask `What is export for?` in `knowledgebase`, then same prompt in `llmevals` | `knowledgebase` cites `kb_export.txt`; `llmevals` should either cite no relevant `le_` source or explain no relevant docs |
| `CC-03` | start chat in `knowledgebase`, ask one question, switch to `llmevals`, ask eval question | second turn cites only `le_` docs |
| `CC-04` | reopen a saved chat whose stored corpus is `knowledgebase` | selectors restore stored corpus and model before next send |

That yields 28 real-RAG scenarios total:

- 12 `KB-*`
- 12 `LE-*`
- 4 `CC-*`

This exceeds the requested 20+ corpus-driven scenarios.

## 13. Files and Fixtures To Add

### 13.1 New helper module

Create `tests_e2e/helpers_chat_ui.py` with:

- service health checks,
- LM Studio readiness helpers,
- corpus seeding helpers,
- ingestion helpers,
- Playwright transcript helpers,
- citation and keyword assertion helpers.

### 13.2 New browser fixtures

Extend `tests_e2e/conftest.py` with:

- `e2e_env_session`
- `service_process`
- `api_client`
- `page_ready`
- `seeded_corpora`
- `loaded_model_id`
- `clean_chats`

### 13.3 New integration helpers

Create `tests_integration/helpers_runtime.py` with:

- temp config creation,
- subprocess start/stop,
- free-port allocation,
- ingestion wrappers,
- LM Studio CLI wrappers.

## 14. Non-Flaky Assertion Rules

Use these rules to keep the suite stable:

- never assert exact full assistant strings,
- assert semantic keywords and expected citations instead,
- wait on observable UI state transitions such as input re-enabled, not arbitrary sleeps,
- use generous timeouts only for real-RAG tests,
- keep deterministic UI tests on fake streaming responses with known chunk boundaries,
- do not share chats across tests,
- do not share browser pages across tests,
- log the selected model id, corpus, prompt, response text, and citations for every failed real-RAG scenario.

## 15. Known Implementation Gaps Exposed By This Spec

The current codebase is likely to fail some of the tests above until the UI is tightened.

Expected gaps:

- no persisted "last active chat" restore on refresh,
- no visible warning when chat save fails,
- JSON export is not currently the full saved chat object,
- some current browser tests rely on broad element visibility rather than request/response verification,
- current real-RAG coverage is too narrow and does not cover `llmevals`.

These are not reasons to weaken the test plan. They are reasons to fix the product or explicitly narrow the product spec.

## 16. Deliverables

Implementation is complete when all of the following exist:

- deterministic browser e2e suite for UI mechanics,
- real-RAG Playwright suite for `knowledgebase` and `llmevals`,
- LM Studio readiness helper with explicit allowed-model policy,
- isolated corpus seeding and ingestion helpers,
- integration tests for service, corpora, and LM Studio boundaries,
- at least 28 corpus-driven real-RAG scenarios implemented and runnable,
- `just ci-quiet` is run at regular checkpoints during implementation and again before completion,
- any failures from `just ci-quiet` are resolved by fixing code, tests, or fixtures rather than weakening the checks,
- the suite produces actionable failure output without requiring manual inspection of the browser.

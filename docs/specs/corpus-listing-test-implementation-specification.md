# Corpus Listing — Test Implementation Specification

## Test Framework & Conventions

- **Language:** Python 3.12
- **Test framework:** pytest with pytest-asyncio (asyncio_mode = "auto")
- **HTTP testing:** FastAPI `TestClient` (synchronous wrapper around httpx)
- **Assertion style:** Plain `assert` statements
- **Mocking strategy:** Fake/stub classes (no external mocking library — matches existing project pattern)
- **Test location:** `tests/` directory, one file per feature area

## Test Structure

- **File:** `tests/test_api_routes_corpora.py`
- **Grouping:** Single test module with standalone test functions (no class needed — small scope)
- **Naming:** `test_<scenario_description>` reflecting the behavior tested

## Test Scenario Mapping

| Test Scenario | Test Function | File |
|--------------|---------------|------|
| TS-1: List corpora successfully | `test_list_corpora_returns_sorted_list` | `tests/test_api_routes_corpora.py` |
| TS-2: Corpora returned in alphabetical order | `test_list_corpora_alphabetical_order` | `tests/test_api_routes_corpora.py` |
| TS-3: Reject when service unhealthy | `test_list_corpora_returns_503_when_unhealthy` | `tests/test_api_routes_corpora.py` |
| TS-4: Return empty array when no corpora | `test_list_corpora_empty_when_none_exist` | `tests/test_api_routes_corpora.py` |

### TS-1: List corpora successfully

- **Setup (Given):** Create a FastAPI app with a `FakeCorpusManager` that returns `["alpha", "beta", "gamma"]` from `list_corpora()`. Set `app.state.app_status = "healthy"`.
- **Action (When):** `TestClient(app).get("/v1/corpora")`
- **Assertion (Then):** Status 200. Response JSON matches `{"status": "success", "data": {"corpora": ["alpha", "beta", "gamma"]}}`. Each entry is a non-empty string.

### TS-2: Corpora returned in alphabetical order

- **Setup (Given):** Create a FastAPI app with a `FakeCorpusManager` that returns `["gamma", "alpha", "beta"]` from `list_corpora()` (pre-sorted by the real corpus manager — test verifies the API preserves order).
- **Action (When):** `TestClient(app).get("/v1/corpora")`
- **Assertion (Then):** Status 200. `data.corpora` equals `["alpha", "beta", "gamma"]` (sorted).

### TS-3: Reject when service unhealthy

- **Setup (Given):** Create a FastAPI app with `app.state.app_status = "shutting_down"`.
- **Action (When):** `TestClient(app).get("/v1/corpora")`
- **Assertion (Then):** Status 503.

### TS-4: Return empty array when no corpora

- **Setup (Given):** Create a FastAPI app with a `FakeCorpusManager` that returns `[]` from `list_corpora()`. Set healthy status.
- **Action (When):** `TestClient(app).get("/v1/corpora")`
- **Assertion (Then):** Status 200. `data.corpora` equals `[]`.

## Fixtures & Test Data

- **`fake_app` fixture:** Creates a minimal FastAPI app, includes the `info_router`, and sets `app.state` with a `FakeConfig`, `FakeCorpusManager`, and `app_status = "healthy"`. Reused by all tests (each test can override state as needed).
- **`FakeCorpusManager`:** Stub class with a configurable `list_corpora()` return value. Matches the pattern used in existing `tests/test_api_routes.py`.
- **No external dependencies or mocks.** All tests use in-memory fakes.
- **Isolation:** Each test creates its own TestClient or overrides app state — no shared mutable state between tests.

## Alignment Check

Full alignment. All 4 test scenarios (TS-1 through TS-4) are mapped to test functions with setup, action, and assertion defined. No gaps. No implementation coupling — all tests verify HTTP responses at the API boundary.

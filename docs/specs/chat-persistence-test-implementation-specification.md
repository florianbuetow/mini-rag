# Chat Persistence — Test Implementation Specification

## Test Framework & Conventions

- **Language:** Python 3.12
- **Test framework:** pytest with pytest-asyncio (asyncio_mode = "auto")
- **HTTP testing:** FastAPI `TestClient`
- **Assertion style:** Plain `assert` statements
- **Mocking strategy:** Temporary directories (using `tmp_path` fixture) for chat file storage — no file system mocks
- **Test location:** `tests/` directory

## Test Structure

- **File:** `tests/test_api_routes_chats.py`
- **Grouping:** Test functions grouped by CRUD operation, prefixed by operation
- **Naming:** `test_<operation>_<scenario_description>`

## Test Scenario Mapping

| Test Scenario | Test Function | File |
|--------------|---------------|------|
| TS-1: Create a new chat | `test_create_chat_with_model_and_corpus` | `tests/test_api_routes_chats.py` |
| TS-2: Default chat name is datetime | `test_create_chat_default_name_is_datetime` | `tests/test_api_routes_chats.py` |
| TS-3: List all chats | `test_list_chats_returns_summary_entries` | `tests/test_api_routes_chats.py` |
| TS-4: Chats sorted by most recent first | `test_list_chats_sorted_by_updated_at_descending` | `tests/test_api_routes_chats.py` |
| TS-5: Load a specific chat | `test_get_chat_returns_full_object` | `tests/test_api_routes_chats.py` |
| TS-6: Load non-existent chat | `test_get_chat_returns_404_for_nonexistent` | `tests/test_api_routes_chats.py` |
| TS-7: Rename a chat | `test_update_chat_rename` | `tests/test_api_routes_chats.py` |
| TS-8: Update chat messages | `test_update_chat_messages` | `tests/test_api_routes_chats.py` |
| TS-9: Update non-existent chat | `test_update_chat_returns_404_for_nonexistent` | `tests/test_api_routes_chats.py` |
| TS-10: Delete a chat | `test_delete_chat_removes_it` | `tests/test_api_routes_chats.py` |
| TS-11: Delete non-existent chat | `test_delete_chat_returns_404_for_nonexistent` | `tests/test_api_routes_chats.py` |
| TS-12: Empty chat list | `test_list_chats_empty_when_none_exist` | `tests/test_api_routes_chats.py` |
| TS-13: Auto-create chats directory | `test_create_chat_auto_creates_directory` | `tests/test_api_routes_chats.py` |
| TS-14: Concurrent chat creation | `test_concurrent_chat_creation_unique_ids` | `tests/test_api_routes_chats.py` |
| TS-15: Invalid request body | `test_create_chat_invalid_json_returns_422` | `tests/test_api_routes_chats.py` |
| TS-16: Missing required fields | `test_create_chat_missing_fields_returns_422` | `tests/test_api_routes_chats.py` |
| TS-17: Corrupted chat file | `test_list_chats_excludes_corrupted_files` | `tests/test_api_routes_chats.py` |
| TS-18: Reject when service unhealthy | `test_chats_returns_503_when_unhealthy` | `tests/test_api_routes_chats.py` |

### TS-1: Create a new chat

- **Setup (Given):** Build app with chat storage pointing to `tmp_path/chats/`. Set healthy.
- **Action (When):** `client.post("/v1/chats", json={"model": "gemma-3-1b", "corpus": "docs"})`
- **Assertion (Then):** Status 201. Response contains `id` (non-empty string), `model` == `"gemma-3-1b"`, `corpus` == `"docs"`, `messages` == `[]`, `created_at` and `updated_at` are valid ISO 8601, `name` is present.

### TS-2: Default chat name is datetime

- **Setup (Given):** Build app with chat storage.
- **Action (When):** `client.post("/v1/chats", json={"model": "gemma-3-1b", "corpus": "docs"})` (no `name` field)
- **Assertion (Then):** Status 201. `name` matches regex `\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}`.

### TS-3: List all chats

- **Setup (Given):** Create 2 chats via POST. Build app.
- **Action (When):** `client.get("/v1/chats")`
- **Assertion (Then):** Status 200. `chats` array has 2 entries. Each entry has `id`, `name`, `updated_at`. No entry has `messages`.

### TS-4: Chats sorted by most recent first

- **Setup (Given):** Create chat A, then chat B (B has later `updated_at`).
- **Action (When):** `client.get("/v1/chats")`
- **Assertion (Then):** Chat B appears before chat A in the array.

### TS-5: Load a specific chat

- **Setup (Given):** Create a chat, then update it with 3 messages via PUT.
- **Action (When):** `client.get(f"/v1/chats/{chat_id}")`
- **Assertion (Then):** Status 200. Response contains full chat object with all 3 messages.

### TS-6: Load non-existent chat

- **Setup (Given):** Build app. No chats created.
- **Action (When):** `client.get("/v1/chats/nonexistent-id")`
- **Assertion (Then):** Status 404.

### TS-7: Rename a chat

- **Setup (Given):** Create a chat. Record its `updated_at`.
- **Action (When):** `client.put(f"/v1/chats/{chat_id}", json={"name": "new name"})`
- **Assertion (Then):** Status 200. `name` == `"new name"`. `updated_at` is later than the original.

### TS-8: Update chat messages

- **Setup (Given):** Create a chat (0 messages).
- **Action (When):** `client.put(f"/v1/chats/{chat_id}", json={"messages": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]})`
- **Assertion (Then):** Status 200. `messages` has 2 entries. `updated_at` is updated.

### TS-9: Update non-existent chat

- **Setup (Given):** Build app. No chats created.
- **Action (When):** `client.put("/v1/chats/nonexistent-id", json={"name": "test"})`
- **Assertion (Then):** Status 404.

### TS-10: Delete a chat

- **Setup (Given):** Create a chat.
- **Action (When):** `client.delete(f"/v1/chats/{chat_id}")`
- **Assertion (Then):** Status 200. Subsequent `GET /v1/chats/{chat_id}` returns 404. Chat absent from `GET /v1/chats`.

### TS-11: Delete non-existent chat

- **Setup (Given):** Build app.
- **Action (When):** `client.delete("/v1/chats/nonexistent-id")`
- **Assertion (Then):** Status 404.

### TS-12: Empty chat list

- **Setup (Given):** Build app. No chats created.
- **Action (When):** `client.get("/v1/chats")`
- **Assertion (Then):** Status 200. `chats` == `[]`.

### TS-13: Auto-create chats directory

- **Setup (Given):** Build app with `data_dir/chats/` not yet existing.
- **Action (When):** `client.post("/v1/chats", json={"model": "gemma-3-1b", "corpus": "docs"})`
- **Assertion (Then):** Status 201. The `chats/` directory now exists on disk.

### TS-14: Concurrent chat creation

- **Setup (Given):** Build app.
- **Action (When):** Send 5 `POST /v1/chats` requests using `ThreadPoolExecutor` concurrently.
- **Assertion (Then):** All 5 return status 201. All 5 have unique `id` values.

### TS-15: Invalid request body

- **Setup (Given):** Build app.
- **Action (When):** `client.post("/v1/chats", content="not json", headers={"content-type": "application/json"})`
- **Assertion (Then):** Status 422.

### TS-16: Missing required fields

- **Setup (Given):** Build app.
- **Action (When):** `client.post("/v1/chats", json={})`
- **Assertion (Then):** Status 422.

### TS-17: Corrupted chat file

- **Setup (Given):** Build app. Write a valid chat JSON file and a corrupted (non-JSON) file into the chats directory on disk.
- **Action (When):** `client.get("/v1/chats")`
- **Assertion (Then):** Status 200. Only the valid chat appears in the list.

### TS-18: Reject when service unhealthy

- **Setup (Given):** Build app with `app_status = "shutting_down"`.
- **Action (When):** `client.get("/v1/chats")`
- **Assertion (Then):** Status 503.

## Fixtures & Test Data

- **`chat_app` fixture (function-scoped):** Creates a FastAPI app with chat routes included, `app.state` configured with a `tmp_path`-based `data_dir` for chat storage, `FakeConfig`, healthy status. Returns `(app, TestClient, tmp_path)`.
- **`create_chat` helper:** Convenience function that sends `POST /v1/chats` and returns the response JSON. Used to set up preconditions in multiple tests.
- **No external mocks.** All tests use real file I/O against `tmp_path`.
- **Isolation:** Each test gets its own `tmp_path` via function-scoped fixture — no shared mutable state.

## Alignment Check

Full alignment. All 18 test scenarios (TS-1 through TS-18) are mapped to test functions with setup, action, and assertion defined. No gaps. No implementation coupling — all tests verify HTTP responses at the API boundary and use observable file system side effects (directory creation) only where specified.

# Backend error surfacing investigation

## 1. Q1 root cause

### Silent `POST /v1/chats` failure path

Evidence:

- `config.yaml:7-8` configures `data.data_dir` to `/Volumes/2TB/data/projects/mini-rag/data`; `src/minirag/config.py:315-320` resolves that configured path directly when it is absolute.
- `src/minirag/api/app.py:69-70` resolves `data_dir`, and `src/minirag/api/app.py:112-115` stores it on `app.state.data_dir`.
- `src/minirag/api/routes_chats.py:62-65` derives chat storage as `<data_dir>/chats`.
- `src/minirag/api/routes_chats.py:111-139` handles `POST /v1/chats`: it creates the chat directory, builds the chat JSON, and calls `_write_chat(...)`.
- `src/minirag/api/routes_chats.py:92-95` writes the file with `chat_file.open("w")` and `json.dump(...)`. There is no local `try/except`, so a disk-full `OSError: [Errno 28]` escapes this route.
- `src/minirag/api/responses.py:11-13` defines the standard JSON error envelope as `{"status": <int>, "error": <message>}`.
- `src/minirag/api/app.py:47-51` has an uncaught-exception handler that logs the exception and returns `error_response(status=500, message=str(exc))`; `src/minirag/api/app.py:118-119` registers that handler.

Inference:

- In the current worktree, a disk-full failure in `_write_chat()` should become an HTTP 500 JSON envelope at the backend boundary. The backend path is therefore not the final silent surface; the frontend ignores or drops that failed envelope for chat creation.

Frontend evidence:

- `web/index.html:279-285` defines `apiPost(...)` by calling `fetch(...)` and returning `{ status: resp.status, data: await resp.json() }`. It never checks `resp.ok` and never throws for 4xx/5xx.
- `web/index.html:622-637` uses `apiPost('/v1/chats', ...)` in explicit New Chat creation. If `result.status !== 201`, the function does nothing visible; its `catch` only logs `Failed to create chat`.
- `web/index.html:655-674` uses `apiPost('/v1/chats', ...)` in the auto-create path before sending. If status is not 201, it returns at `web/index.html:669-670`; if parsing/fetch throws, it returns at `web/index.html:672-674`. Neither branch renders an error.
- `tests_e2e/test_chat_ui_error_states.py:126-144` covers visible warnings for failed `PUT /v1/chats/<id>`, but the searched test surface has no equivalent visible-error test for failed `POST /v1/chats`.

Root cause:

- The direct silent gap is `apiPost(...)` plus its call sites. A backend 500 from `POST /v1/chats` is converted into a normal `{status, data}` value, then the explicit create path ignores non-201 and the auto-create path returns before creating any user/assistant bubble. The user sees no visible error because no UI error function is called.

### Chat-completion HTTP error path

Evidence:

- `src/minirag/api/routes_chat_completions.py:272-309` returns either a pre-stream `JSONResponse` for validation/health/corpus errors or a `StreamingResponse` for accepted chat-completion work.
- `src/minirag/api/routes_chat_completions.py:279-285` returns JSON 422 errors before streaming if the corpus is missing.
- `web/index.html:704-717` sends `POST /v1/chat/completions`.
- `web/index.html:719-724` checks `resp.ok` and throws an error using `responseErrorMessage(resp)` when the response is non-2xx or missing a readable body.
- `web/index.html:257-272` parses JSON error envelopes and returns `payload.error` when present.
- `web/index.html:882-890` catches thrown completion errors, writes `Error: ...` into the assistant bubble, marks it with `message-error`, and sets the chat status to error.
- `tests_e2e/test_chat_ui_error_states.py:55-73` asserts a non-SSE 500 JSON response from `/v1/chat/completions` renders the API error message and `.message-error`.

Inference:

- Current chat-completion non-streaming HTTP errors are surfaced. This path is not the silent incident path.

### Chat-completion mid-stream error path

Evidence:

- `src/minirag/chat_stream.py:15-21` defines internal stream events, including `type: "error"`.
- `src/minirag/api/routes_chat_completions.py:111-114` serializes named SSE events as `event: <name>` plus JSON `data`.
- `src/minirag/api/routes_chat_completions.py:128-145` maps internal `error` events to public `event: error` with `{"message": ...}`.
- `src/minirag/api/routes_chat_completions.py:210-235` wraps agent streaming: on exception it logs, emits `event: error` with `{"message": str(exc)}`, then emits reset status and `event: done`.
- `src/minirag/agent.py:403-421` catches exceptions from `agent.stream_async(prompt)`, puts the exception into the cross-thread queue, then terminates the queue.
- `src/minirag/agent.py:456-476` drains the queue and re-raises queued exceptions so the route-level stream wrapper can emit the SSE `error` event.
- `web/index.html:771-837` parses typed SSE events. For `event: error`, it requires a JSON object with string `message` and calls `displayStreamError(...)`.
- `web/index.html:743-750` renders stream errors into the assistant bubble, adds `message-error`, preserves partial text, and updates status with error severity.
- `tests/test_api_routes_chat_completions.py:503-514` asserts agent exceptions emit one `error` event and terminal `done`.
- `tests_e2e/test_chat_ui_error_states.py:29-54` covers preserving partial text on stream error; `tests_e2e/test_chat_ui_error_states.py:75-120` covers malformed stream contract errors being visible.

Inference:

- Current mid-stream backend errors are surfaced through typed SSE. This matches the status-streaming design in `docs/specs/status-streaming-specification.md:169-176`, which defines `status`, `token`, `error`, and `done`; `docs/specs/status-streaming-specification.md:206-215`, which keeps token/status semantics separated; and `docs/specs/status-streaming-specification.md:534-555`, which requires `event: error` with JSON data and visible frontend error styling.

### Secondary silent or weak JSON handling

Evidence:

- `web/index.html:274-277` defines `apiGet(...)` without `resp.ok` handling.
- `web/index.html:298-300` defines `apiDelete(...)` without `resp.ok` handling.
- `web/index.html:288-295` defines `apiPut(...)` with `resp.ok` handling, but throws only `PUT failed: <status>` and discards the backend JSON error message.
- `web/index.html:900-906` catches failed chat save and calls `showSaveWarning()`.
- `web/index.html:1061-1070` defines the visible save warning text.

Inference:

- `PUT` failures are visible but lose server detail. `GET`/`DELETE` and `POST` helpers are inconsistent. The query-execution incident needs `POST /v1/chats` fixed first, but the minimal robust design should normalize all JSON helper behavior.

## 2. Q2 design

### Backend JSON contract

Use the existing envelope:

```json
{"status": 500, "error": "failed to create chat"}
```

Evidence to preserve:

- `src/minirag/api/responses.py:11-13` already centralizes this shape.
- `src/minirag/api/app.py:36-44` already maps request validation errors to the same envelope.
- `src/minirag/api/app.py:47-51` already maps uncaught exceptions to the same envelope, and `src/minirag/api/app.py:118-119` registers it.

Minimal backend changes proposed:

- Keep `error_response(status, message)` as the public JSON error contract.
- Update `unhandled_exception_handler(...)` in `src/minirag/api/app.py:47-51` so 500 responses expose a user-safe message instead of raw `str(exc)`, while logging the full exception. A good minimal message is `"internal server error"` or a route-specific message when the route handles it.
- Add narrow `OSError` handling around chat persistence in `src/minirag/api/routes_chats.py:111-139` and `src/minirag/api/routes_chats.py:191-217`, returning a user-safe message such as `"failed to persist chat"` while preserving full exception logging. This makes disk-full failures clearer than a generic exception handler and keeps the response envelope consistent.

### Backend SSE contract

Keep the typed SSE contract already present:

```text
event: error
data: {"message":"chat completion stream failed"}

event: done
data: {}
```

Evidence to preserve:

- `src/minirag/api/routes_chat_completions.py:111-114` serializes named JSON SSE events.
- `src/minirag/api/routes_chat_completions.py:128-145` maps internal events to `status`, `token`, `error`, and `done`.
- `src/minirag/api/routes_chat_completions.py:228-235` catches stream exceptions and emits `error`, reset `status`, and `done`.
- `docs/specs/status-streaming-specification.md:171-176` defines the preferred typed event names.
- `docs/specs/status-streaming-specification.md:540-555` gives the required visible error behavior and example `event: error`.

Minimal backend changes proposed:

- Keep `event: error` with JSON `{"message": string}`.
- Make the emitted error message user-safe in `stream_agent_response(...)` at `src/minirag/api/routes_chat_completions.py:228-231`, while logging the exception. If product requirements need detail in development, gate it explicitly rather than leaking raw exception strings by default.
- Keep terminal `event: done` after an error, as already asserted by `tests/test_api_routes_chat_completions.py:503-514`.

### Frontend JSON handling

Implement one shared helper for JSON responses:

- Parse response bodies using the existing `responseErrorMessage(resp)` behavior at `web/index.html:257-272`.
- For every JSON helper, check `resp.ok` before returning success data.
- For failed JSON responses, throw `new Error(await responseErrorMessage(resp))`.

Minimal frontend changes proposed:

- Change `apiPost(...)` at `web/index.html:279-285` to check `resp.ok`, throw with the backend `error` message, and return only successful parsed JSON. This directly fixes silent failed `POST /v1/chats`.
- Change `apiGet(...)` at `web/index.html:274-277` and `apiDelete(...)` at `web/index.html:298-300` the same way for consistency.
- Improve `apiPut(...)` at `web/index.html:288-295` to throw the backend message instead of only `PUT failed: <status>`.
- Add a small visible create/send error surface using existing patterns:
  - Reuse `setChatStatus(text, "error")` from `web/index.html:586-594` when auto-create fails before a message bubble exists.
  - Add or generalize the existing warning pattern from `showSaveWarning()` at `web/index.html:1061-1070` for explicit New Chat failures.
  - Do not only `console.error(...)`; `web/index.html:635-637` and `web/index.html:672-674` are the exact places that must render.

### Frontend SSE handling

Keep the current typed parser and rendering:

- `web/index.html:719-724` already surfaces non-streaming HTTP errors before reading the stream.
- `web/index.html:771-837` already dispatches named SSE events and validates `error` payloads.
- `web/index.html:743-750` already renders `event: error` visibly while preserving partial text.
- `web/index.html:882-890` already renders thrown parser/HTTP errors visibly.

Minimal frontend change proposed:

- No new stream UI component is needed. Preserve `setChatStatus(...)`, `.message-error`, and assistant-bubble rendering.
- Ensure backend `event: error` messages remain user-safe because the UI intentionally displays them.

### Exact files and functions to change

- `src/minirag/api/app.py`
  - `unhandled_exception_handler(...)`: log full exception, return standard envelope with user-safe 500 message.
- `src/minirag/api/routes_chats.py`
  - `create_chat(...)`: catch/log `OSError` from `chats_dir.mkdir(...)` and `_write_chat(...)`, return `error_response(500, "...")`.
  - `update_chat(...)`: catch/log `OSError` from `_write_chat(...)`, return `error_response(500, "...")`.
  - `generate_title(...)`: catch/log `OSError` from the final `_write_chat(...)` if title persistence fails.
- `src/minirag/api/routes_chat_completions.py`
  - `stream_agent_response(...)`: ensure `event: error` payload is user-safe; keep `done`.
- `web/index.html`
  - `apiGet(...)`, `apiPost(...)`, `apiPut(...)`, `apiDelete(...)`: use one `resp.ok` + envelope parser path.
  - `createNewChat(...)`: render a visible error in the `catch`.
  - `sendMessage(...)` auto-create block: render a visible error before returning.
- Tests to add/update:
  - `tests/test_api_routes_chats.py`: disk/write failure returns JSON envelope, not a raw 500 body.
  - `tests_e2e/test_chat_ui_error_states.py`: failed auto-create `POST /v1/chats` displays a visible message.
  - Existing stream tests in `tests/test_api_routes_chat_completions.py:503-514` and `tests_e2e/test_chat_ui_error_states.py:55-120` should remain passing.

### Disk-full `POST /v1/chats` happy path after the fix

1. `sendMessage()` enters the auto-create block at `web/index.html:655-674`.
2. The backend attempts `create_chat(...)` at `src/minirag/api/routes_chats.py:111-139`.
3. `_write_chat(...)` at `src/minirag/api/routes_chats.py:92-95` raises `OSError`.
4. The backend logs the exception and returns `{"status":500,"error":"failed to persist chat"}`.
5. `apiPost(...)` sees `!resp.ok`, extracts `payload.error`, and throws.
6. The auto-create `catch` renders the error with `setChatStatus("Error: failed to persist chat", "error")` or the generalized warning banner, then returns. The user sees the failure instead of a no-op.

### Mid-stream completion error happy path after the fix

1. `/v1/chat/completions` has already returned `200 OK` and `text/event-stream`, so HTTP status can no longer change.
2. The agent or retrieval path raises during streaming; `src/minirag/agent.py:403-421` puts the exception into the stream queue.
3. `src/minirag/agent.py:456-476` re-raises it to the route stream wrapper.
4. `src/minirag/api/routes_chat_completions.py:228-235` logs it, emits `event: error` with `{"message":"chat completion stream failed"}`, then emits reset status and `event: done`.
5. `web/index.html:821-828` receives `event: error`, validates `message`, and calls `displayStreamError(...)`.
6. `web/index.html:743-750` preserves any partial assistant text, appends a visible `Error: ...`, sets `.message-error`, and sets the status to error.

### Compliance with project conventions

- AGENTS/CLAUDE require small, reviewable, verified diffs and final validation with lint/typecheck/tests (`AGENTS.md:60-64`, `CLAUDE.md:60-64`).
- The semgrep rules reject hidden fallbacks and missing-data masking: `config/semgrep/no-sneaky-fallbacks.yml:16-20`, `config/semgrep/no-sneaky-fallbacks.yml:44-49`, and `config/semgrep/no-default-values.yml:21-27`.
- The design complies by making errors explicit, propagating failed HTTP statuses through a single helper, and rendering visible UI errors instead of returning silently.

## 3. Open questions / risks

- User-safe message policy is not fully specified. Current backend code exposes `str(exc)` for uncaught 500s at `src/minirag/api/app.py:47-51` and stream errors at `src/minirag/api/routes_chat_completions.py:228-231`; changing that may require updating tests that currently assert raw exception text.
- A startup write probe exists at `src/minirag/startup_validation.py:26-34`, but it only proves writability during startup. It cannot detect a volume that fills later, so runtime persistence errors still need request-time handling.
- The existing visible warning text for save failures is persistence-specific (`web/index.html:1061-1070`). A generalized API-error banner may be cleaner than overloading `showSaveWarning()`, but it should stay minimal.
- `apiGet(...)` and `apiDelete(...)` currently share the same no-`resp.ok` weakness as `apiPost(...)`; fixing only `POST` solves the incident but leaves inconsistent JSON endpoint behavior.
- Existing E2E coverage verifies failed `PUT` and chat-completion errors, but not failed chat creation. Add a deterministic route interception for `POST /v1/chats` before considering this fixed.

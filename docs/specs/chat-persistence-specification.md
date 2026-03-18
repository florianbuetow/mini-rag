# Chat Persistence — Behavioral Specification

## Objective

Provide CRUD API endpoints for storing, retrieving, updating, and deleting chat conversations, so that users can resume previous conversations, rename them, and manage their chat history.

## User Stories & Acceptance Criteria

US-1: As a user, I want to create a new chat, so that I can start a conversation with the assistant.

Acceptance Criteria:
  AC-1.1: A `POST /v1/chats` request with a JSON body containing `model` (string) and `corpus` (string) creates a new chat and returns HTTP 201 with the full chat object.
  AC-1.2: The created chat has a `name` field defaulting to a human-readable datetime string (e.g., "2026-03-11 14:30:22") if no `name` is provided in the request.
  AC-1.3: The created chat has an empty `messages` array.
  AC-1.4: The created chat has `created_at` and `updated_at` timestamps set to the creation time in ISO 8601 format.
  AC-1.5: The returned chat object includes an `id` field that uniquely identifies the chat.

US-2: As a user, I want to list all my chats, so that I can see my conversation history and select one to resume.

Acceptance Criteria:
  AC-2.1: A `GET /v1/chats` request returns HTTP 200 with a JSON body containing a `chats` array.
  AC-2.2: Each entry in the `chats` array contains `id`, `name`, and `updated_at` fields (not the full message history).
  AC-2.3: The `chats` array is sorted by `updated_at` in descending order (most recent first).

US-3: As a user, I want to load a specific chat, so that I can see the full conversation history and continue it.

Acceptance Criteria:
  AC-3.1: A `GET /v1/chats/<id>` request returns HTTP 200 with the full chat object including all messages.
  AC-3.2: A `GET /v1/chats/<id>` request for a non-existent chat returns HTTP 404 with an error message.

US-4: As a user, I want to update a chat (rename it or append messages), so that I can organize my conversations and record new exchanges.

Acceptance Criteria:
  AC-4.1: A `PUT /v1/chats/<id>` request with a JSON body containing `name` (string) updates the chat's display name and returns HTTP 200 with the updated chat object.
  AC-4.2: A `PUT /v1/chats/<id>` request with a JSON body containing `messages` (array) replaces the chat's messages array and returns HTTP 200 with the updated chat object.
  AC-4.3: Any successful update sets `updated_at` to the current time.
  AC-4.4: A `PUT /v1/chats/<id>` request for a non-existent chat returns HTTP 404.

US-5: As a user, I want to delete a chat, so that I can remove conversations I no longer need.

Acceptance Criteria:
  AC-5.1: A `DELETE /v1/chats/<id>` request deletes the chat and returns HTTP 200 with a confirmation message.
  AC-5.2: A `DELETE /v1/chats/<id>` request for a non-existent chat returns HTTP 404.
  AC-5.3: After deletion, the chat no longer appears in `GET /v1/chats` and `GET /v1/chats/<id>` returns HTTP 404.

## Constraints

- **Technical:** Chats are stored as individual JSON files in `<data_dir>/chats/`, one file per chat.
- **Technical:** The filename format is timestamp-based (e.g., `20260311-143022.json`). Filenames are never renamed on disk — only the `name` field inside the JSON changes.
- **Technical:** The chat `id` is derived from the filename (the timestamp portion without the `.json` extension).
- **Technical:** Chat JSON schema: `{"name": string, "model": string, "messages": array, "corpus": string, "created_at": string, "updated_at": string}`.
- **Technical:** Each message in the `messages` array has at minimum `role` (string: "user" or "assistant") and `content` (string).
- **Technical:** All endpoints are under the `/v1` route prefix.
- **Technical:** All endpoints require the service to be in "healthy" status; otherwise they return HTTP 503.

## Edge Cases

- **No chats exist:** `GET /v1/chats` returns HTTP 200 with `{"chats": []}`.
- **`<data_dir>/chats/` directory does not exist:** The service creates it on first chat creation. `GET /v1/chats` returns an empty array.
- **Concurrent creation at the same second:** If two chats are created within the same second, the filenames must not collide. Use millisecond precision or an additional disambiguator (e.g., `20260311-143022-001.json`).
- **Invalid JSON in request body:** Return HTTP 422 with a descriptive error message.
- **Missing required fields on creation:** `POST /v1/chats` without `model` or `corpus` returns HTTP 422.
- **Chat file corrupted on disk:** If a chat file contains invalid JSON, `GET /v1/chats/<id>` returns HTTP 500 with an error message indicating the file is corrupted. The corrupted chat is excluded from `GET /v1/chats` listing (logged as a warning, not a crash).

## Non-Goals

- **Authentication or authorization.** All chats are accessible to any user of the local service.
- **Full-text search across chats.** Users browse by name and date only.
- **Chat sharing or export via the API.** Export is handled client-side in the frontend.
- **Message-level CRUD.** Messages are managed as part of the chat object, not individually.
- **Pagination of the chat list.** The number of chats is expected to be manageable without pagination.

## Open Questions

None.

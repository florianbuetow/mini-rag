# Chat Persistence — Test Specification

## Coverage Matrix

| Spec Requirement | Test Scenario(s) |
|-----------------|------------------|
| AC-1.1: POST /v1/chats creates chat, returns 201 | TS-1: Create a new chat |
| AC-1.2: Default name is datetime string | TS-2: Default chat name is datetime |
| AC-1.3: Created chat has empty messages | TS-1 (verified within) |
| AC-1.4: created_at and updated_at set | TS-1 (verified within) |
| AC-1.5: Returned chat has id | TS-1 (verified within) |
| AC-2.1: GET /v1/chats returns 200 with chats array | TS-3: List all chats |
| AC-2.2: List entries have id, name, updated_at only | TS-3 (verified within) |
| AC-2.3: Chats sorted by updated_at descending | TS-4: Chats sorted by most recent first |
| AC-3.1: GET /v1/chats/<id> returns full chat | TS-5: Load a specific chat |
| AC-3.2: GET non-existent chat returns 404 | TS-6: Load non-existent chat |
| AC-4.1: PUT with name renames chat | TS-7: Rename a chat |
| AC-4.2: PUT with messages replaces messages | TS-8: Update chat messages |
| AC-4.3: Update sets updated_at | TS-7, TS-8 (verified within) |
| AC-4.4: PUT non-existent chat returns 404 | TS-9: Update non-existent chat |
| AC-5.1: DELETE removes chat, returns 200 | TS-10: Delete a chat |
| AC-5.2: DELETE non-existent returns 404 | TS-11: Delete non-existent chat |
| AC-5.3: Deleted chat gone from list and get | TS-10 (verified within) |
| EC: No chats exist | TS-12: Empty chat list |
| EC: chats/ directory missing | TS-13: Auto-create chats directory |
| EC: Concurrent creation collision | TS-14: Concurrent chat creation |
| EC: Invalid JSON in request | TS-15: Invalid request body |
| EC: Missing required fields | TS-16: Missing required fields on create |
| EC: Corrupted chat file | TS-17: Corrupted chat file on disk |
| C: Service unhealthy returns 503 | TS-18: Reject when service unhealthy |

## Test Scenarios

### Happy Path — Create

**TS-1: Create a new chat**

```
Scenario: Create a chat with model and corpus
  Given the mini-rag service is running and healthy
  When the client sends POST /v1/chats with body {"model": "gemma-3-1b", "corpus": "docs"}
  Then the response status is 201
  And the response body contains a chat object with:
    - "id" is a non-empty string
    - "model" is "gemma-3-1b"
    - "corpus" is "docs"
    - "messages" is an empty array
    - "created_at" is a valid ISO 8601 timestamp
    - "updated_at" is a valid ISO 8601 timestamp
    - "name" is present
```

**TS-2: Default chat name is datetime**

```
Scenario: Chat name defaults to human-readable datetime
  Given the mini-rag service is running and healthy
  When the client sends POST /v1/chats with body {"model": "gemma-3-1b", "corpus": "docs"} and no "name" field
  Then the response status is 201
  And the chat "name" matches a datetime pattern (e.g., "2026-03-11 14:30:22")
```

### Happy Path — List

**TS-3: List all chats**

```
Scenario: List chats returns summary entries
  Given the mini-rag service is running and healthy
  And two chats exist
  When the client sends GET /v1/chats
  Then the response status is 200
  And the response body contains a "chats" array with 2 entries
  And each entry contains "id", "name", and "updated_at"
  And each entry does not contain "messages"
```

**TS-4: Chats sorted by most recent first**

```
Scenario: Chat list is sorted by updated_at descending
  Given the mini-rag service is running and healthy
  And chat A was updated before chat B
  When the client sends GET /v1/chats
  Then chat B appears before chat A in the chats array
```

### Happy Path — Load

**TS-5: Load a specific chat**

```
Scenario: Load full chat by ID
  Given the mini-rag service is running and healthy
  And a chat with id "20260311-143022" exists with 3 messages
  When the client sends GET /v1/chats/20260311-143022
  Then the response status is 200
  And the response body contains the full chat object including all 3 messages
```

### Happy Path — Update

**TS-7: Rename a chat**

```
Scenario: Rename a chat via PUT
  Given the mini-rag service is running and healthy
  And a chat with id "20260311-143022" exists with name "old name"
  When the client sends PUT /v1/chats/20260311-143022 with body {"name": "new name"}
  Then the response status is 200
  And the chat name is "new name"
  And the updated_at timestamp is later than before the update
```

**TS-8: Update chat messages**

```
Scenario: Replace chat messages via PUT
  Given the mini-rag service is running and healthy
  And a chat with id "20260311-143022" exists with 0 messages
  When the client sends PUT /v1/chats/20260311-143022 with body {"messages": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]}
  Then the response status is 200
  And the chat has 2 messages
  And the updated_at timestamp is later than before the update
```

### Happy Path — Delete

**TS-10: Delete a chat**

```
Scenario: Delete a chat by ID
  Given the mini-rag service is running and healthy
  And a chat with id "20260311-143022" exists
  When the client sends DELETE /v1/chats/20260311-143022
  Then the response status is 200
  And the response body contains a confirmation message
  And GET /v1/chats/20260311-143022 returns 404
  And the chat does not appear in GET /v1/chats
```

### Error Scenarios

**TS-6: Load non-existent chat**

```
Scenario: Load a chat that does not exist
  Given the mini-rag service is running and healthy
  When the client sends GET /v1/chats/nonexistent-id
  Then the response status is 404
  And the response body contains an error message
```

**TS-9: Update non-existent chat**

```
Scenario: Update a chat that does not exist
  Given the mini-rag service is running and healthy
  When the client sends PUT /v1/chats/nonexistent-id with body {"name": "test"}
  Then the response status is 404
```

**TS-11: Delete non-existent chat**

```
Scenario: Delete a chat that does not exist
  Given the mini-rag service is running and healthy
  When the client sends DELETE /v1/chats/nonexistent-id
  Then the response status is 404
```

**TS-15: Invalid request body**

```
Scenario: Invalid JSON in request body
  Given the mini-rag service is running and healthy
  When the client sends POST /v1/chats with an invalid JSON body
  Then the response status is 422
  And the response body contains an error message
```

**TS-16: Missing required fields on create**

```
Scenario: Create chat without required fields
  Given the mini-rag service is running and healthy
  When the client sends POST /v1/chats with body {} (no model, no corpus)
  Then the response status is 422
  And the response body contains an error message about missing fields
```

### Edge Case Scenarios

**TS-12: Empty chat list**

```
Scenario: List chats when none exist
  Given the mini-rag service is running and healthy
  And no chats exist
  When the client sends GET /v1/chats
  Then the response status is 200
  And the response body contains {"chats": []}
```

**TS-13: Auto-create chats directory**

```
Scenario: Chats directory is created on first chat creation
  Given the mini-rag service is running and healthy
  And the chats/ directory does not exist in data_dir
  When the client sends POST /v1/chats with body {"model": "gemma-3-1b", "corpus": "docs"}
  Then the response status is 201
  And the chats/ directory has been created
```

**TS-14: Concurrent chat creation**

```
Scenario: Two chats created in the same second do not collide
  Given the mini-rag service is running and healthy
  When two POST /v1/chats requests are sent concurrently with body {"model": "gemma-3-1b", "corpus": "docs"}
  Then both return status 201
  And each has a unique id
```

**TS-17: Corrupted chat file on disk**

```
Scenario: Corrupted file is excluded from listing
  Given the mini-rag service is running and healthy
  And a valid chat file and a corrupted (non-JSON) chat file exist on disk
  When the client sends GET /v1/chats
  Then the response status is 200
  And only the valid chat appears in the list
```

**TS-18: Reject when service unhealthy**

```
Scenario: Chat endpoints return 503 when service is unhealthy
  Given the mini-rag service is running but not in "healthy" status
  When the client sends GET /v1/chats
  Then the response status is 503
```

## Traceability

All acceptance criteria (AC-1.1 through AC-5.3), all edge cases, and the unhealthy service constraint are covered by test scenarios TS-1 through TS-18. No coverage gaps.

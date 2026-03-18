# Conversational Agent — Test Specification

## Coverage Matrix

| Spec Requirement | Test Scenario(s) |
|-----------------|------------------|
| AC-1.1: POST accepts messages, model, corpus | TS-1: Send a chat completion request |
| AC-1.2: Agent queries corpus via hybrid search | TS-1 (verified by response referencing corpus data) |
| AC-1.3: Response incorporates retrieved data | TS-1 (verified by content check) |
| AC-1.4: Agent uses specified model via LM Studio | TS-1 (verified by request) |
| AC-2.1: Response is SSE with text/event-stream | TS-2: Response streams via SSE |
| AC-2.2: Each event contains a response chunk | TS-2 (verified within) |
| AC-2.3: Final event signals completion | TS-3: Stream terminates with done signal |
| AC-2.4: Client disconnect stops generation | TS-4: Server handles client disconnect |
| AC-3.1: Agent has system prompt for friendly RAG behavior | TS-1 (verified by response tone/content) |
| AC-3.2: Full history sent to LLM | TS-5: Multi-turn conversation |
| EC: Empty messages array | TS-6: Reject empty messages |
| EC: Invalid corpus name | TS-7: Reject invalid corpus |
| EC: LM Studio unavailable | TS-8: Handle LLM provider error |
| EC: RAG returns no results | TS-9: Handle empty retrieval |
| EC: Concurrent requests | TS-10: Concurrent completions |
| C: Service unhealthy returns 503 | TS-11: Reject when service unhealthy |

## Test Scenarios

### Happy Path

**TS-1: Send a chat completion request**

```
Scenario: Send a message and receive a RAG-grounded response
  Given the mini-rag service is running and healthy
  And corpus "docs" exists with documents containing information about "mini-rag architecture"
  And LM Studio is running with a model available
  When the client sends POST /v1/chat/completions with body:
    {"messages": [{"role": "user", "content": "What is the architecture of mini-rag?"}], "model": "gemma-3-1b", "corpus": "docs"}
  Then the response content type is text/event-stream
  And the streamed response contains text related to the corpus content
```

**TS-2: Response streams via SSE**

```
Scenario: Response is delivered as a stream of SSE events
  Given the mini-rag service is running and healthy
  And corpus "docs" exists
  And LM Studio is running
  When the client sends POST /v1/chat/completions with a valid request
  Then the response content type is text/event-stream
  And multiple SSE events are received
  And each event contains a chunk of the assistant's response text
```

**TS-3: Stream terminates with done signal**

```
Scenario: SSE stream sends a completion signal
  Given the mini-rag service is running and healthy
  And corpus "docs" exists
  And LM Studio is running
  When the client sends POST /v1/chat/completions with a valid request
  And the full response is consumed
  Then the last SSE event indicates completion (e.g., [DONE] sentinel or stream closure)
```

**TS-5: Multi-turn conversation**

```
Scenario: Full conversation history is used for context
  Given the mini-rag service is running and healthy
  And corpus "docs" exists
  And LM Studio is running
  When the client sends POST /v1/chat/completions with body:
    {"messages": [
      {"role": "user", "content": "What is mini-rag?"},
      {"role": "assistant", "content": "Mini-rag is a retrieval-augmented generation system."},
      {"role": "user", "content": "Tell me more about its search capabilities."}
    ], "model": "gemma-3-1b", "corpus": "docs"}
  Then the response content type is text/event-stream
  And the streamed response acknowledges prior conversation context
```

### Edge Case Scenarios

**TS-4: Server handles client disconnect**

```
Scenario: Server stops generating when client disconnects
  Given the mini-rag service is running and healthy
  And corpus "docs" exists
  And LM Studio is running
  When the client sends POST /v1/chat/completions with a valid request
  And the client disconnects after receiving the first SSE event
  Then the server stops processing without raising an unhandled error
```

**TS-6: Reject empty messages**

```
Scenario: Empty messages array is rejected
  Given the mini-rag service is running and healthy
  When the client sends POST /v1/chat/completions with body:
    {"messages": [], "model": "gemma-3-1b", "corpus": "docs"}
  Then the response status is 422
  And the response body contains an error about empty messages
```

**TS-7: Reject invalid corpus**

```
Scenario: Non-existent corpus is rejected
  Given the mini-rag service is running and healthy
  And corpus "nonexistent" does not exist
  When the client sends POST /v1/chat/completions with body:
    {"messages": [{"role": "user", "content": "hello"}], "model": "gemma-3-1b", "corpus": "nonexistent"}
  Then the response status is 422
  And the response body contains an error about invalid corpus
```

**TS-8: Handle LLM provider error**

```
Scenario: SSE stream sends error when LM Studio is unavailable
  Given the mini-rag service is running and healthy
  And corpus "docs" exists
  And LM Studio is not running
  When the client sends POST /v1/chat/completions with a valid request
  Then the SSE stream sends an error event indicating the LLM provider is unreachable
  And the stream closes
```

**TS-9: Handle empty retrieval**

```
Scenario: Agent reports when no documents match the query
  Given the mini-rag service is running and healthy
  And corpus "empty-corpus" exists but contains no documents
  And LM Studio is running
  When the client sends POST /v1/chat/completions with body:
    {"messages": [{"role": "user", "content": "find something"}], "model": "gemma-3-1b", "corpus": "empty-corpus"}
  Then the streamed response indicates that no relevant documents were found
```

**TS-10: Concurrent completions**

```
Scenario: Multiple concurrent chat completion requests
  Given the mini-rag service is running and healthy
  And corpus "docs" exists
  And LM Studio is running
  When two POST /v1/chat/completions requests are sent concurrently
  Then both requests receive SSE streams independently
  And neither request blocks the other
```

**TS-11: Reject when service unhealthy**

```
Scenario: Chat completions returns 503 when service is unhealthy
  Given the mini-rag service is running but not in "healthy" status
  When the client sends POST /v1/chat/completions with a valid request
  Then the response status is 503
```

## Traceability

All acceptance criteria (AC-1.1 through AC-3.2), all edge cases, and the unhealthy service constraint are covered by test scenarios TS-1 through TS-11. No coverage gaps.

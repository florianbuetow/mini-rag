# Conversational Agent — Behavioral Specification

## Objective

Provide a chat completions endpoint that uses a Strands agent to answer user questions by first retrieving relevant information from mini-rag corpora, then generating a response grounded in that data, streamed to the client via Server-Sent Events (SSE).

## User Stories & Acceptance Criteria

US-1: As a user, I want to send a message to an assistant that retrieves information from my documents before answering, so that the assistant's responses are grounded in my data rather than purely generated.

Acceptance Criteria:
  AC-1.1: A `POST /v1/chat/completions` request accepts a JSON body with `messages` (array of message objects), `model` (string), and `corpus` (string).
  AC-1.2: The agent queries the specified corpus using the mini-rag retrieval system (hybrid search) before generating its answer.
  AC-1.3: The agent's response incorporates information retrieved from the corpus, not solely from the LLM's training data.
  AC-1.4: The agent uses the LLM specified by the `model` parameter via the LM Studio API at `http://127.0.0.1:1234`.

US-2: As a user, I want the assistant's response to stream in real time, so that I see partial output immediately instead of waiting for the full response.

Acceptance Criteria:
  AC-2.1: The response uses Server-Sent Events (SSE) with content type `text/event-stream`.
  AC-2.2: Each SSE event contains a chunk of the assistant's response as it is generated.
  AC-2.3: The final SSE event signals completion (e.g., a `[DONE]` sentinel or stream closure).
  AC-2.4: If the client disconnects mid-stream, the server stops generating and cleans up resources without error.

US-3: As a user, I want the assistant to behave as a friendly, competent helper that always backs up claims with data from my documents.

Acceptance Criteria:
  AC-3.1: The agent operates under a system prompt that instructs it to be friendly and competent, and to always back up claims with data retrieved from RAG tools.
  AC-3.2: The full conversation history (all messages in the `messages` array) is sent to the LLM on each request, enabling multi-turn conversations.

## Constraints

- **Technical:** The agent framework is Strands (`strands-agents`).
- **Technical:** The LLM provider is LM Studio running at `http://127.0.0.1:1234`, exposing an OpenAI-compatible API.
- **Technical:** The agent must have tools for querying mini-rag (at minimum: hybrid search on the specified corpus).
- **Technical:** The endpoint is `POST /v1/chat/completions` under the existing FastAPI application.
- **Technical:** The endpoint requires the service to be in "healthy" status; otherwise it returns HTTP 503.
- **Technical:** The SSE stream format must be compatible with the browser `EventSource` API and `fetch` with streaming body reading.

## Edge Cases

- **Empty messages array:** Return HTTP 422 — at least one user message is required.
- **Invalid model name:** The agent attempts to use the specified model. If LM Studio returns an error (model not found), the SSE stream sends an error event and closes.
- **Invalid corpus name:** Return HTTP 422 if the specified corpus does not exist in the corpus manager.
- **LM Studio unavailable:** The SSE stream sends an error event indicating the LLM provider is unreachable, then closes.
- **RAG retrieval returns no results:** The agent informs the user that no relevant documents were found in the corpus, rather than hallucinating an answer.
- **Very long conversation history:** The full history is sent to the LLM. If the conversation exceeds the model's context window, the LLM may truncate or error — the agent surfaces this error via the SSE stream.
- **Concurrent requests:** Multiple chat completion requests can be processed concurrently. Each request operates on its own conversation context.

## Non-Goals

- **Conversation memory within the agent.** The agent is stateless — the client sends the full message history each time. Persistence is handled by the chat persistence endpoints.
- **Multiple tool calls exposed to the user.** The agent's internal tool use (RAG queries) is not surfaced in the streamed response — only the final assistant text is streamed.
- **Model management.** Model listing and selection is handled by querying LM Studio directly (`GET http://127.0.0.1:1234/v1/models`).
- **Rate limiting or request queuing.** Not required for local use.
- **Citation formatting.** The agent may reference source documents in natural language, but structured citation objects are not part of this feature.

## Open Questions

None.

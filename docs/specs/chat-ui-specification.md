# Chat UI — Behavioral Specification

## Objective

Provide a ChatGPT-style single-page web interface that allows users to have multi-turn conversations with the mini-rag assistant, select models and corpora, manage chat history, and export conversations — all served from the mini-rag service.

## User Stories & Acceptance Criteria

US-1: As a user, I want to select which LLM model to use for my conversation, so that I can choose the model that best fits my needs.

Acceptance Criteria:
  AC-1.1: The UI displays a model selector dropdown populated by fetching `GET http://127.0.0.1:1234/v1/models`.
  AC-1.2: The dropdown defaults to a lightweight model with tool-use support (e.g., a gemma-3 or qwen variant) if available, otherwise the first model in the list.
  AC-1.3: The user can switch models mid-conversation. The selected model is used for the next message sent.
  AC-1.4: The model selector displays the model name/ID for each option.

US-2: As a user, I want to select which document corpus to query, so that the assistant answers from the correct set of documents.

Acceptance Criteria:
  AC-2.1: The UI displays a corpus selector dropdown populated by fetching `GET /v1/corpora`.
  AC-2.2: The corpus list is sorted alphabetically.
  AC-2.3: The default selection is the first corpus in the alphabetical list.
  AC-2.4: The user can switch corpora mid-conversation.

US-3: As a user, I want to see my previous chats in a sidebar, so that I can resume any past conversation.

Acceptance Criteria:
  AC-3.1: The left sidebar displays a list of previous chats fetched from `GET /v1/chats`.
  AC-3.2: Each chat entry shows the chat name and is clickable to load the full conversation.
  AC-3.3: Chats are sorted by most recently updated first.
  AC-3.4: Clicking a chat loads its full message history from `GET /v1/chats/<id>` and displays it in the chat area.
  AC-3.5: The currently active chat is visually highlighted in the sidebar.

US-4: As a user, I want to rename a chat inline in the sidebar, so that I can give conversations meaningful names.

Acceptance Criteria:
  AC-4.1: Each chat entry in the sidebar has an inline rename action (e.g., double-click or edit icon).
  AC-4.2: Renaming a chat sends a `PUT /v1/chats/<id>` request with the new name.
  AC-4.3: The sidebar updates to show the new name after a successful rename.
  AC-4.4: An empty name is not accepted — the UI prevents submission of a blank name.

US-5: As a user, I want to start a new chat, so that I can begin a fresh conversation.

Acceptance Criteria:
  AC-5.1: The UI has a "New chat" button that is always visible.
  AC-5.2: Clicking "New chat" clears the chat area and creates a new chat via `POST /v1/chats` with the currently selected model and corpus.
  AC-5.3: The new chat appears in the sidebar immediately.

US-6: As a user, I want to send messages and see the assistant's response streamed in real time, so that I get immediate feedback.

Acceptance Criteria:
  AC-6.1: The chat area displays message bubbles for user messages and assistant messages, visually distinct from each other.
  AC-6.2: When the user sends a message, it appears immediately in the chat area as a user bubble.
  AC-6.3: The assistant's response streams in real time via SSE from `POST /v1/chat/completions`, with text appearing incrementally in an assistant bubble.
  AC-6.4: During streaming, the user cannot send another message (the input is disabled or a loading indicator is shown).
  AC-6.5: The full conversation history (all messages) is sent with each request to `POST /v1/chat/completions`.
  AC-6.6: After the response completes, the chat is saved via `PUT /v1/chats/<id>` with the updated messages.

US-7: As a user, I want to export a conversation, so that I can save it locally for reference.

Acceptance Criteria:
  AC-7.1: The UI provides an export action for the current conversation.
  AC-7.2: The user can choose to export as Markdown or JSON format.
  AC-7.3: Exporting as Markdown produces a `.md` file with messages formatted as headings (role) and content.
  AC-7.4: Exporting as JSON produces a `.json` file containing the full chat object.
  AC-7.5: The export triggers a browser file download with an appropriate filename (e.g., `<chat-name>.md` or `<chat-name>.json`).

US-8: As a user, I want to delete a chat, so that I can remove conversations I no longer need.

Acceptance Criteria:
  AC-8.1: Each chat entry in the sidebar has a delete action (e.g., a delete icon or context menu option).
  AC-8.2: Deleting a chat sends a `DELETE /v1/chats/<id>` request.
  AC-8.3: After successful deletion, the chat is removed from the sidebar.
  AC-8.4: If the deleted chat was the active chat, the chat area is cleared.

## Constraints

- **Technical:** The frontend is a single-page HTML application served from the `web/` directory (subfolders: `css/`, `gfx/`).
- **Technical:** No frontend build toolchain (no npm, no bundlers). Plain HTML, CSS, and JavaScript.
- **Technical:** The UI must visually resemble ChatGPT's layout: sidebar on the left, chat area on the right, input at the bottom.
- **Technical:** SSE streaming is consumed using the browser `fetch` API with streaming body reading (not the `EventSource` API, since `POST` is required).
- **Technical:** The model list is fetched from `http://127.0.0.1:1234/v1/models` (LM Studio).
- **Technical:** The corpus list and chat CRUD use the mini-rag API endpoints.

## Edge Cases

- **LM Studio unreachable:** The model dropdown shows an error state or empty list with a message indicating models could not be loaded. The UI remains functional for browsing existing chats.
- **No corpora available:** The corpus dropdown shows an empty state with a message. Chat creation is disabled until a corpus is available.
- **No existing chats:** The sidebar shows an empty state (e.g., "No conversations yet").
- **SSE stream error mid-response:** The UI displays the partial response received so far and shows an error indicator. The conversation is still saved with whatever was received.
- **Very long messages:** Messages that exceed the visible area are scrollable. The chat area auto-scrolls to the latest message during streaming.
- **Network error during chat save:** The UI shows a warning that the conversation may not be saved. A retry mechanism is not required — the user can refresh to see the last saved state.
- **Browser refresh:** The UI loads the last active chat from the sidebar (or shows a blank state if no chats exist).

## Non-Goals

- **User authentication or accounts.** The UI is single-user, local use only.
- **Mobile-responsive design.** Desktop layout only.
- **Dark mode toggle.** A single theme is used (the ChatGPT-style dark theme is preferred, but a light theme is acceptable).
- **Message editing or regeneration.** Users cannot edit sent messages or regenerate assistant responses.
- **File upload or image attachment.** Text-only conversations.
- **Keyboard shortcuts beyond standard browser shortcuts.** No custom keybindings required.
- **Accessibility compliance (WCAG).** Semantic HTML is preferred, but full accessibility compliance is not in scope.

## Open Questions

None.

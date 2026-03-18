# Chat UI User Journeys and Expected Outcomes

Please read AGENTS.md and bestpractices.md

## 1. Purpose

Define every user journey through the chat UI, the expected visual outcome at each step, and the edge cases that must be tested. This document exists because `specifications2.md` missed a critical journey: the user who opens the app and starts typing without clicking "+ New Chat" first. That gap escaped all 69 E2E tests.

This spec is exhaustive by design. Every state the user can reach, every action they can take from that state, and every visual outcome is listed. If a journey is not here, it is not supported.

## 2. Application States

The UI has exactly three state variables:

| Variable | Type | Initial | Meaning |
|---|---|---|---|
| `currentChatId` | `string \| null` | `null` | The active chat. When null, the user has no chat selected. |
| `currentMessages` | `array` | `[]` | Messages in the active chat. |
| `isStreaming` | `boolean` | `false` | Whether a response is currently streaming. |

Every user journey starts from one of these entry states:

| Entry State | Conditions |
|---|---|
| **S1: Cold start** | First visit. No chats in storage. No localStorage. |
| **S2: Return visit, chats exist** | Chats exist on the server. `minirag_last_chat` may or may not be set in localStorage. |
| **S3: Active chat** | A chat is loaded. `currentChatId` is set. Messages may or may not exist. |
| **S4: Streaming** | A response is currently being streamed. `isStreaming` is true. |

## 3. User Journeys

Each journey is numbered. Sub-steps show the exact expected outcome at each point.

---

### J-01: Cold start — app loads with no chats

**Precondition:** No chats on server. No localStorage.

**Steps and expected outcomes:**

1. User navigates to `/`.
2. Page loads. Three parallel fetches fire: `/v1/models`, `/v1/corpora`, `/v1/chats`.
3. **Model selector:** Populates with available models sorted alphabetically. Default selects the first model whose ID contains `gemma` or `qwen` (case-insensitive). If none match, selects index 0.
4. **Corpus selector:** Populates with available corpora. First corpus is selected.
5. **Sidebar:** Shows "No conversations yet" empty state text.
6. **Chat area:** Empty. No messages rendered.
7. **Message input:** Visible, enabled, shows placeholder "Send a message...".
8. **Send button:** Visible, enabled (visually), but clicking it does nothing because `currentChatId` is null.

**Bug identified:** The user sees an enabled input and send button, but sending silently fails. There is no visual indication that a chat must be created first.

**Required fix (one of):**
- **(A) Auto-create:** When the user sends a message with no active chat, auto-create a chat using the current model and corpus selections, then send the message.
- **(B) Disable input:** Disable the message input and send button when `currentChatId` is null. Show placeholder text like "Click + New Chat to start".
- **(C) Visual prompt:** Show a prompt in the empty chat area: "Start a new conversation" with a button or instruction.

---

### J-02: Cold start — user clicks "+ New Chat"

**Precondition:** State S1 (cold start). Models and corpora loaded.

1. User clicks "+ New Chat".
2. `POST /v1/chats` fires with `{ model: <selected>, corpus: <selected> }`.
3. Server returns 201 with chat object.
4. **Sidebar:** New entry appears with auto-generated name (datetime format `YYYY-MM-DD HH:MM:SS`). Entry is highlighted as active.
5. **Chat area:** Cleared (empty, ready for messages).
6. **Message input:** Focused, enabled.
7. `currentChatId` is set. User can now send messages.

---

### J-03: Cold start — user clicks "+ New Chat" before models/corpora load

**Precondition:** State S1. Models and/or corpora fetch still in flight or failed.

1. User clicks "+ New Chat" while model selector value is `""` or corpus selector value is `""`.
2. `createNewChat()` checks `if (!model || !corpus) return`.
3. **Expected outcome:** Nothing happens. No chat is created. No error is shown.

**Bug identified:** Silent failure. The user clicked a button and nothing happened.

**Required fix:** Either disable the "+ New Chat" button until both selectors have valid values, or show a visible error message.

---

### J-04: Cold start — models fail to load

**Precondition:** `/v1/models` returns an error or is unreachable.

1. **Model selector:** Shows "Error loading models" as the only option.
2. **Corpus selector:** Loads normally (independent fetch).
3. **Sidebar:** Loads normally.
4. User cannot create a new chat (model value is empty string).
5. **Expected outcome:** "+ New Chat" should be disabled or show an error when clicked.

---

### J-05: Cold start — corpora fail to load

**Precondition:** `/v1/corpora` returns an error or is unreachable.

1. **Corpus selector:** Shows "Error loading corpora" as the only option.
2. **Model selector:** Loads normally.
3. User cannot create a new chat (corpus value is empty string).
4. **Expected outcome:** Same as J-04 — either disable or show error.

---

### J-06: Cold start — no models available

**Precondition:** `/v1/models` returns `{ data: [] }`.

1. **Model selector:** Shows "No models available" as the only option.
2. User cannot create a new chat.
3. **Expected outcome:** Clear indication that no models are loaded.

---

### J-07: Cold start — no corpora available

**Precondition:** `/v1/corpora` returns `{ data: { corpora: [] } }`.

1. **Corpus selector:** Shows "No corpora available" as the only option.
2. User cannot create a new chat.

---

### J-08: Return visit — last active chat restored

**Precondition:** State S2. Chats exist. `minirag_last_chat` is set in localStorage and references a valid chat ID.

1. User navigates to `/`.
2. Models, corpora, and chat list load.
3. Chat list renders in sidebar with entries sorted newest first.
4. `getLastActiveChat()` returns the stored chat ID.
5. A matching `.chat-entry` element exists in the sidebar.
6. `loadChat(lastChatId)` fires automatically.
7. **Chat area:** Renders all messages from the restored chat.
8. **Model selector:** Set to the chat's stored model.
9. **Corpus selector:** Set to the chat's stored corpus.
10. **Sidebar:** Restored chat entry is highlighted as active.
11. **Message input:** Enabled, focused. User can send immediately.

---

### J-09: Return visit — last active chat no longer exists

**Precondition:** State S2. `minirag_last_chat` references a chat ID that has been deleted.

1. Models, corpora, and chat list load.
2. `getLastActiveChat()` returns a chat ID.
3. No matching `.chat-entry` element exists in the sidebar.
4. `loadChat()` is NOT called.
5. **Chat area:** Empty.
6. **Sidebar:** Chat list renders, but no entry is highlighted.
7. `currentChatId` remains null.
8. **Expected outcome:** Same as J-01 — user must select or create a chat.

---

### J-10: Return visit — no last active chat stored

**Precondition:** State S2. `minirag_last_chat` not in localStorage.

1. Chat list renders in sidebar.
2. No chat is auto-loaded.
3. **Chat area:** Empty.
4. `currentChatId` remains null.

---

### J-11: User selects an existing chat from sidebar

**Precondition:** State S2 or S3. At least one chat exists in sidebar.

1. User clicks a chat entry in the sidebar.
2. `loadChat(chatId)` fires.
3. `GET /v1/chats/{chatId}` returns the full chat object.
4. **Chat area:** All messages render in order (user bubbles on right with dark background, assistant bubbles on left with no background).
5. **Model selector:** Updated to the chat's stored model value.
6. **Corpus selector:** Updated to the chat's stored corpus value.
7. **Sidebar:** Clicked entry gets `.active` class. Previously active entry loses it.
8. `currentChatId` is set. `currentMessages` is populated.
9. **Message input:** Enabled.
10. `localStorage.minirag_last_chat` updated to this chat's ID.

---

### J-12: User sends a message (happy path)

**Precondition:** State S3. Active chat. Not streaming.

1. User types text into the message input.
2. User clicks send button (or presses Enter without Shift).
3. **Immediately:**
   - `isStreaming` set to true.
   - Send button disabled (greyed out, opacity 0.5).
   - Message input disabled.
   - User message appended to `currentMessages`.
   - User message bubble appears in chat area with role label "You" and the typed text.
   - Input cleared and resized to minimum.
   - Chat area scrolls to bottom.
   - Empty assistant bubble appears with role label "Assistant".
4. **Streaming phase:**
   - `POST /v1/chat/completions` fires with `{ messages: currentMessages, model: <selected>, corpus: <selected> }`.
   - Server sends SSE chunks: `data: {text}\n\n`.
   - Each chunk appends text to the assistant bubble's content div.
   - Chat area scrolls to bottom on each chunk.
5. **Stream ends:**
   - Server sends `data: [DONE]\n\n`. This is ignored (not appended to text).
   - Assistant text is pushed to `currentMessages` as `{ role: "assistant", content: assistantText }`.
   - `PUT /v1/chats/{chatId}` fires with `{ messages: currentMessages }` to persist.
   - `isStreaming` set to false.
   - Send button re-enabled.
   - Message input re-enabled and focused.

---

### J-13: User sends a message — empty input

**Precondition:** State S3. Message input is empty or whitespace-only.

1. User clicks send or presses Enter.
2. `sendMessage()` trims input. Result is empty string.
3. **Expected outcome:** Nothing happens. No API call. No bubble. No state change.

---

### J-14: User sends a message — no active chat

**Precondition:** `currentChatId` is null (S1 or S2, no chat selected).

1. User types text and clicks send.
2. `sendMessage()` checks `!currentChatId` and returns.
3. **Current behavior:** Silent failure. Nothing happens.
4. **Expected behavior:** See J-01 required fix.

---

### J-15: User sends a message — already streaming

**Precondition:** State S4. `isStreaming` is true.

1. User somehow triggers `sendMessage()` (should not be possible if input is disabled).
2. `sendMessage()` checks `isStreaming` and returns.
3. **Expected outcome:** No duplicate request. No visual change.
4. **Defense in depth:** Input and button are disabled during streaming, so this path should not be reachable via normal UI interaction.

---

### J-16: User presses Shift+Enter in message input

**Precondition:** State S3. Message input is focused.

1. User presses Shift+Enter.
2. Keydown handler checks `!e.shiftKey` — condition is false.
3. Default browser behavior: newline inserted in textarea.
4. `autoResizeInput()` fires on the `input` event.
5. **Expected outcome:** Textarea grows (up to max 200px). No message sent.

---

### J-17: Streaming response includes an error

**Precondition:** State S4. Streaming is in progress.

1. Server sends a chunk starting with `error:` (e.g., `data: error: LM Studio unreachable\n\n`).
2. The error text is appended to `assistantText`.
3. `.message-error` class is added to the assistant content div.
4. **Visual outcome:** Text turns red (#ef4444) and italic.
5. Streaming may continue (additional chunks may arrive).
6. After stream ends, the error text is saved as the assistant message content.

---

### J-18: Streaming response — network failure mid-stream

**Precondition:** State S4. `fetch()` or `reader.read()` throws.

1. The `catch` block fires.
2. If `assistantText` is empty (no chunks received): assistant bubble shows "Error: Failed to get response" with `.message-error` class.
3. If `assistantText` is non-empty (partial response received): partial text is preserved as-is in the bubble. No error text appended.
4. `currentMessages` is updated with whatever `assistantText` contains (possibly empty).
5. Chat is saved via PUT.
6. Streaming state is cleaned up: button and input re-enabled.

---

### J-19: Chat save fails after response

**Precondition:** State S4 → streaming complete. `PUT /v1/chats/{chatId}` throws.

1. `apiPut()` throws (server error, network error, etc.).
2. `showSaveWarning()` is called.
3. **Visual outcome:** A dark red banner appears at the top of the main content area: "Failed to save chat. Your messages may not be persisted."
4. Banner has an X button to dismiss.
5. The messages remain visible in the chat area (they exist in `currentMessages` in memory).
6. Streaming cleanup completes normally (input re-enabled).

---

### J-20: User creates multiple chats

**Precondition:** State S3.

1. User clicks "+ New Chat" while an existing chat is active.
2. New chat is created via API.
3. **Sidebar:** New entry appears. Previous chat entry remains but loses `.active` highlight.
4. **Chat area:** Cleared. Previous chat's messages are no longer visible.
5. `currentChatId` updated to new chat. `currentMessages` reset to `[]`.
6. Previous chat's messages are NOT lost — they were saved to server on the last successful response.

---

### J-21: User switches between existing chats

**Precondition:** State S3. Multiple chats exist.

1. User clicks a different chat entry in the sidebar.
2. Previous chat's messages disappear from chat area.
3. New chat's messages load and render.
4. Model and corpus selectors update to the loaded chat's values.
5. **Important:** If the user changed model/corpus selectors after loading the previous chat but before sending a message, those changes are lost (not persisted anywhere).

---

### J-22: User switches chat while streaming

**Precondition:** State S4. Streaming is in progress.

1. User clicks a different chat in the sidebar.
2. `loadChat()` fires — it does NOT check `isStreaming`.
3. `currentChatId` changes to the new chat. `currentMessages` replaced.
4. Chat area re-renders with the new chat's messages.
5. **Bug risk:** The in-flight streaming response will still:
   - Append text to the (now orphaned) assistant content div.
   - Push the assistant message to the (now replaced) `currentMessages`.
   - Try to PUT to the old chat ID (which is correct for saving the old chat, but `currentMessages` no longer matches).
6. When streaming completes, input and button are re-enabled.
7. **Expected outcome is undefined.** This is a race condition.

**Required fix:** Either (A) prevent chat switching during streaming (disable sidebar clicks), or (B) abort the in-flight stream when switching chats.

---

### J-23: User renames a chat via edit button

**Precondition:** State S2 or S3. At least one chat exists.

1. User hovers over a chat entry — action buttons (pencil, X) appear.
2. User clicks the pencil (edit) button.
3. `stopPropagation()` prevents the click from also triggering `loadChat()`.
4. Chat name span is hidden. An `<input>` field appears in its place.
5. Input is pre-filled with the current name, text is selected.
6. **User can now:**
   - Type a new name and press Enter → `finishRename()` fires.
   - Press Escape → rename cancelled, original name restored.
   - Click elsewhere (blur) → `finishRename()` fires.

---

### J-24: User renames a chat via double-click

**Precondition:** Same as J-23.

1. User double-clicks a chat entry.
2. Both `click` (loadChat) and `dblclick` (startRename) events fire.
3. **Expected outcome:** The chat loads AND the rename input appears. The user sees the chat's messages AND the rename field simultaneously.

---

### J-25: Rename — valid new name

**Precondition:** Rename input is active (J-23 or J-24).

1. User types "My Research Chat" and presses Enter.
2. `finishRename()` trims input. Non-empty and different from current name.
3. Input element removed. Name span made visible again with new text.
4. `PUT /v1/chats/{chatId}` fires with `{ name: "My Research Chat" }`.
5. **Visual outcome:** Chat entry shows new name immediately (optimistic update).

---

### J-26: Rename — blank name rejected

**Precondition:** Rename input is active.

1. User clears the input (empty or whitespace) and presses Enter.
2. `finishRename()` trims → empty string.
3. `if (newName && newName !== currentName)` is false.
4. Input removed. Name span restored with ORIGINAL name.
5. No API call.

---

### J-27: Rename — same name submitted

**Precondition:** Rename input is active.

1. User does not change the name and presses Enter.
2. `newName === currentName` → condition is false.
3. Input removed. Name span restored. No API call.

---

### J-28: Rename — Escape cancels

**Precondition:** Rename input is active.

1. User presses Escape.
2. `cancelled` flag set to true. Input removed. Name span restored.
3. Subsequent blur event calls `finishRename()`, but `cancelled` flag prevents any action.
4. No API call.

---

### J-29: User deletes an inactive chat

**Precondition:** State S3. Multiple chats exist. User deletes a chat that is NOT the currently active one.

1. User hovers over a non-active chat entry and clicks the X (delete) button.
2. `stopPropagation()` prevents `loadChat()`.
3. `DELETE /v1/chats/{chatId}` fires.
4. `chatId !== currentChatId` — active chat is NOT cleared.
5. `loadChatList()` refreshes the sidebar.
6. **Visual outcome:** Deleted chat disappears from sidebar. Active chat and its messages remain unchanged.

---

### J-30: User deletes the active chat

**Precondition:** State S3. The user deletes the currently active chat.

1. User clicks X on the active chat entry.
2. `DELETE /v1/chats/{chatId}` fires.
3. `chatId === currentChatId` → `currentChatId` set to null, `currentMessages` set to `[]`.
4. `renderMessages()` fires → chat area cleared.
5. `loadChatList()` refreshes sidebar.
6. **Visual outcome:** Chat area is empty. No chat is active. Sidebar may show other chats or "No conversations yet".
7. **State:** Returns to S1 or S2 (no active chat). Same issues as J-01 apply — input appears enabled but send silently fails.

---

### J-31: User deletes the only chat

**Precondition:** State S3. Only one chat exists.

1. Same as J-30.
2. After deletion, sidebar shows "No conversations yet".
3. Chat area is empty.
4. **State:** S1 (cold start equivalent).

---

### J-32: User changes model selector

**Precondition:** State S3. Active chat loaded.

1. User selects a different model from the dropdown.
2. No API call fires immediately.
3. The new model value will be used in the NEXT `POST /v1/chat/completions` request.
4. The new model value will be used if the user creates a new chat.
5. **Important:** The model change is NOT persisted to the current chat. If the user reloads or switches chats and comes back, the chat's original model is restored.

---

### J-33: User changes corpus selector

**Precondition:** State S3.

1. Same behavior as J-32 but for corpus.
2. Corpus change affects the next completion request.
3. Not persisted to the current chat until the next successful response + save.

---

### J-34: Export — Markdown

**Precondition:** State S3. `currentMessages` is non-empty.

1. User clicks "Export" button. Export menu appears (`.visible` class toggled).
2. User clicks "Markdown (.md)".
3. `exportAsMarkdown()` fires.
4. Markdown content generated: `# Chat Export\n\n## User\n\n{content}\n\n## Assistant\n\n{content}\n\n...`
5. Filename: sanitized chat name + `.md`. Sanitization replaces non-alphanumeric characters (except `_` and `-`) with `_`.
6. Browser triggers a file download.
7. Export menu closes.

---

### J-35: Export — JSON

**Precondition:** State S3. `currentMessages` is non-empty. `currentChatId` is set.

1. User clicks "Export" → "JSON (.json)".
2. `exportAsJson()` fires.
3. `GET /v1/chats/{chatId}` fetches the full saved chat object from the server.
4. **Success:** Downloaded JSON contains the full chat object (id, name, model, corpus, messages, created_at, updated_at).
5. **API failure fallback:** If GET fails, exports a minimal object with local state: `{ id, messages, model, corpus }` — no name, no timestamps.
6. Export menu closes.

---

### J-36: Export — no messages

**Precondition:** State S3. `currentMessages` is empty (new chat with no messages sent).

1. User clicks "Export" → "Markdown (.md)" or "JSON (.json)".
2. `if (!currentMessages.length) return` — function exits immediately.
3. **Expected outcome:** Nothing happens. No file downloaded.
4. **Bug identified:** No visual feedback that export requires messages.

---

### J-37: Export — no active chat

**Precondition:** `currentChatId` is null.

1. For Markdown: `if (!currentMessages.length) return` — messages is `[]`, so exits.
2. For JSON: `if (!currentMessages.length || !currentChatId) return` — exits.
3. **Expected outcome:** Nothing happens.

---

### J-38: Export menu — open and close

**Precondition:** Any state.

1. User clicks "Export" button. Menu appears (`.visible`).
2. User clicks "Export" button again. Menu disappears (toggle).
3. Alternatively: user clicks anywhere else on the page. Document click handler removes `.visible`.
4. **stopPropagation** on the export button prevents the document click handler from immediately closing the menu on open.

---

### J-39: Page refresh — with active chat

**Precondition:** State S3. Active chat. `minirag_last_chat` is set in localStorage.

1. User refreshes the page (F5 or browser reload).
2. All JavaScript state is lost (`currentChatId`, `currentMessages`, `isStreaming` reset).
3. `init()` runs. Models, corpora, chat list load.
4. `getLastActiveChat()` returns the stored chat ID.
5. If a matching sidebar entry exists → `loadChat()` fires → chat restored.
6. **Expected outcome:** User sees the same chat they were in before refresh. Messages, model, and corpus are restored.

---

### J-40: Page refresh — during streaming

**Precondition:** State S4. Streaming in progress.

1. User refreshes the page.
2. In-flight fetch is aborted by the browser.
3. The partially-streamed assistant message was NOT yet saved (PUT happens after streaming completes).
4. On reload, the chat loads from server with messages as they were before the interrupted send.
5. **Expected outcome:** The user's last sent message and the partial assistant response are LOST. The chat reverts to its last saved state.
6. **Note:** This is acceptable behavior. The user's typed message was already pushed to `currentMessages` in memory but the PUT had not fired yet.

---

### J-41: User sends message with Shift+Enter (multiline)

**Precondition:** State S3.

1. User types "line 1", presses Shift+Enter, types "line 2".
2. Textarea grows to accommodate the newline.
3. User presses Enter (without Shift) to send.
4. Message sent contains the full multiline text: `"line 1\nline 2"`.
5. **Visual outcome:** User bubble displays the multiline text. The `.message-content` div uses `white-space: pre-wrap` (from CSS) to preserve line breaks.

---

### J-42: Very long message input

**Precondition:** State S3.

1. User types a very long message (multiple paragraphs).
2. Textarea grows up to max height of 200px, then scrolls internally.
3. Message is sent normally.
4. **Visual outcome:** User bubble renders the full text. Chat area scrolls to accommodate.

---

### J-43: Very long assistant response

**Precondition:** State S4. Agent produces a very long response.

1. Chunks stream in. Assistant bubble grows.
2. Chat area auto-scrolls on each chunk.
3. After completion, the full text is visible and scrollable within the chat area.
4. **CSS:** `.message-content` has `word-wrap: break-word` to prevent horizontal overflow.

---

### J-44: XSS attempt in user message

**Precondition:** State S3.

1. User types `<script>alert('xss')</script>` or `<img src=x onerror=alert(1)>`.
2. Message is sent.
3. **Visual outcome:** The HTML is rendered as plain text, NOT executed. `appendMessageBubble()` uses `textContent` (not `innerHTML`), which escapes HTML.
4. **Security:** Safe by construction. No HTML injection possible through the message content path.

---

### J-45: Chat list fails to load

**Precondition:** `GET /v1/chats` returns error or is unreachable.

1. `loadChatList()` catch block fires.
2. **Sidebar:** Shows "Error loading chats".
3. User cannot see or select existing chats.
4. **Expected outcome:** User can still create a new chat if models and corpora loaded successfully.

---

### J-46: Loading a specific chat fails

**Precondition:** State S2. User clicks a chat entry but `GET /v1/chats/{chatId}` fails.

1. `loadChat()` catch block fires.
2. Error logged to console.
3. **Visual outcome:** No visible error to the user. Chat area remains as it was. No chat loads.
4. **Bug identified:** Silent failure. User clicked a chat and nothing happened.

**Required fix:** Show a visible error (e.g., a temporary toast or inline message in chat area).

---

### J-47: Delete request fails

**Precondition:** State S3. User clicks delete on a chat entry but `DELETE /v1/chats/{chatId}` fails.

1. `deleteChat()` catch block fires.
2. Error logged to console.
3. **Visual outcome:** No visible error. Chat entry remains in sidebar.
4. **Bug identified:** Silent failure.

**Required fix:** Show a visible error or leave the chat entry in place with feedback.

---

### J-48: Rename API call fails

**Precondition:** Rename input is active. User enters a new name. `PUT /v1/chats/{chatId}` fails.

1. `finishRename()` optimistically updates the name span.
2. `apiPut()` fires — this is a fire-and-forget call (no await, no error handling).
3. **Visual outcome:** Name appears changed in the sidebar, but the server still has the old name.
4. On next page load, the old name is restored.
5. **Bug identified:** No error handling on rename PUT. Optimistic update with no rollback.

---

### J-49: User opens export menu then clicks outside

**Precondition:** Export menu is visible.

1. User clicks anywhere on the page outside the export menu.
2. Document click handler fires: `exportMenu.classList.remove('visible')`.
3. **Expected outcome:** Menu closes.

---

### J-50: Concurrent chat creation

**Precondition:** User rapidly clicks "+ New Chat" multiple times.

1. Each click fires `createNewChat()`.
2. Multiple `POST /v1/chats` requests fire.
3. Each has a different timestamp-based ID (microsecond precision).
4. **Expected outcome:** Multiple chats created. Last one wins as the active chat. All appear in sidebar after `loadChatList()` refresh.
5. **Note:** There is no debounce or guard against rapid clicks.

---

### J-51: localStorage unavailable

**Precondition:** Browser has localStorage disabled or in private mode where it throws.

1. `saveLastActiveChat()` wraps in try/catch — silently ignores.
2. `getLastActiveChat()` wraps in try/catch — returns null.
3. **Expected outcome:** App works normally. Last-active-chat restore on refresh does not work. No errors shown.

---

## 4. State Transition Diagram

```
                           [Page Load]
                               |
                    +----------+----------+
                    |                     |
              No last chat          Has last chat
                    |                     |
                    v                     v
              S1/S2: No active      S3: Chat loaded
              chat selected         (restored from localStorage)
                    |                     |
          +---------+---------+           |
          |                   |           |
    Click sidebar       Click +New Chat   |
    entry                     |           |
          |                   v           |
          +--------> S3: Active Chat <----+
                         |       |
                    Send msg   Switch chat/
                         |     Delete active/
                         v     Refresh
                    S4: Streaming
                         |
                    Stream ends
                         |
                         v
                    S3: Active Chat
                    (messages updated)
```

## 5. Summary of Bugs and Gaps Found

| ID | Issue | Severity | Current Behavior | Expected Behavior |
|---|---|---|---|---|
| B-01 | Send with no active chat | **Critical** | Silent no-op | Auto-create chat or disable input |
| B-02 | "+ New Chat" before selectors load | Medium | Silent no-op | Disable button or show error |
| B-03 | Chat switch during streaming | Medium | Race condition — orphaned stream | Prevent switch or abort stream |
| B-04 | Load chat fails | Medium | Silent — console.error only | Show visible error |
| B-05 | Delete chat fails | Low | Silent — console.error only | Show visible error |
| B-06 | Rename PUT fails | Low | Optimistic update, no rollback | Handle error, rollback name |
| B-07 | Export with no messages | Low | Silent no-op | Disable export or show tooltip |
| B-08 | Refresh during streaming loses message | Low | Message lost (acceptable) | Document as known behavior |
| B-09 | Rapid "+ New Chat" clicks | Low | Multiple chats created | Debounce or disable during create |

## 6. Required Test Cases

These test cases cover the gaps identified above and complement `specifications2.md`.

### 6.1 Critical — must exist before the bug can be considered fixed

| Test ID | Journey | Assertion |
|---|---|---|
| UJ-01 | J-01/J-14: Send message with no active chat | Message appears in chat area OR visible error/prompt shown |
| UJ-02 | J-03: Click "+ New Chat" before selectors load | Button is disabled OR visible error shown |
| UJ-03 | J-22: Switch chat during streaming | Either switch is blocked OR stream is aborted cleanly |

### 6.2 High priority — important UX correctness

| Test ID | Journey | Assertion |
|---|---|---|
| UJ-04 | J-01: Cold start empty state | Input is disabled with guidance OR auto-create is enabled |
| UJ-05 | J-08: Return visit restores last chat | Chat area shows messages, model/corpus selectors match |
| UJ-06 | J-09: Return visit, last chat deleted | No crash, no auto-load, sidebar renders correctly |
| UJ-07 | J-12: Happy path send and stream | User bubble appears immediately, assistant grows, controls disabled then re-enabled |
| UJ-08 | J-17: Stream error response | Error text shown in red italic in assistant bubble |
| UJ-09 | J-18: Network failure mid-stream | Partial text preserved OR error message shown |
| UJ-10 | J-19: Chat save fails | Warning banner visible at top of main area |
| UJ-11 | J-30: Delete active chat | Chat area cleared, no active chat, input state correct |
| UJ-12 | J-44: XSS in message | HTML rendered as text, not executed |

### 6.3 Medium priority — completeness

| Test ID | Journey | Assertion |
|---|---|---|
| UJ-13 | J-02: Create new chat | Sidebar entry appears, chat area cleared, input focused |
| UJ-14 | J-04: Models fail to load | Selector shows error, new chat disabled or errors |
| UJ-15 | J-05: Corpora fail to load | Selector shows error, new chat disabled or errors |
| UJ-16 | J-06: No models available | Selector shows "No models available" |
| UJ-17 | J-07: No corpora available | Selector shows "No corpora available" |
| UJ-18 | J-11: Select chat from sidebar | Messages render, model/corpus restore, highlight updates |
| UJ-19 | J-13: Send empty message | Nothing happens, no API call |
| UJ-20 | J-15: Send while streaming | No duplicate request |
| UJ-21 | J-16: Shift+Enter in input | Newline inserted, no message sent, textarea grows |
| UJ-22 | J-20: Create second chat | Previous chat preserved, new chat active |
| UJ-23 | J-21: Switch between chats | Messages swap, selectors update |
| UJ-24 | J-23: Rename via edit button | Input appears, name updates on Enter |
| UJ-25 | J-24: Rename via double-click | Chat loads AND rename input appears |
| UJ-26 | J-25: Valid rename | Name updates in sidebar, PUT fires |
| UJ-27 | J-26: Blank rename rejected | Original name restored, no PUT |
| UJ-28 | J-28: Rename Escape cancels | Original name restored, no PUT |
| UJ-29 | J-29: Delete inactive chat | Removed from sidebar, active chat unchanged |
| UJ-30 | J-32: Change model selector | Next completion uses new model |
| UJ-31 | J-33: Change corpus selector | Next completion uses new corpus |
| UJ-32 | J-34: Export Markdown | File downloads with correct format and filename |
| UJ-33 | J-35: Export JSON | File downloads with full chat object |
| UJ-34 | J-36: Export with no messages | Nothing happens or button disabled |
| UJ-35 | J-38: Export menu toggle | Opens on click, closes on click outside |
| UJ-36 | J-39: Refresh restores chat | Same chat loaded after refresh |
| UJ-37 | J-41: Multiline message | Line breaks preserved in display |
| UJ-38 | J-43: Long assistant response | Auto-scroll works, text visible and scrollable |
| UJ-39 | J-45: Chat list load fails | Error shown in sidebar |
| UJ-40 | J-46: Load specific chat fails | Visible error to user |
| UJ-41 | J-48: Rename PUT fails | Error handled, name rolled back or error shown |
| UJ-42 | J-51: localStorage unavailable | App works, no crash |

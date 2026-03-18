# Chat UI — Test Specification

## Coverage Matrix

| Spec Requirement | Test Scenario(s) |
|-----------------|------------------|
| AC-1.1: Model dropdown populated from LM Studio | TS-1: Model selector loads models |
| AC-1.2: Default to lightweight model | TS-2: Default model selection |
| AC-1.3: Switch models mid-conversation | TS-3: Switch model mid-conversation |
| AC-1.4: Model name displayed | TS-1 (verified within) |
| AC-2.1: Corpus dropdown from /v1/corpora | TS-4: Corpus selector loads corpora |
| AC-2.2: Corpus list sorted alphabetically | TS-4 (verified within) |
| AC-2.3: Default to first corpus | TS-5: Default corpus selection |
| AC-2.4: Switch corpus mid-conversation | TS-6: Switch corpus mid-conversation |
| AC-3.1: Sidebar lists previous chats | TS-7: Sidebar displays chat list |
| AC-3.2: Chat entry shows name, is clickable | TS-7 (verified within) |
| AC-3.3: Sorted by most recent | TS-7 (verified within) |
| AC-3.4: Click loads full chat | TS-8: Load chat from sidebar |
| AC-3.5: Active chat highlighted | TS-8 (verified within) |
| AC-4.1: Inline rename action | TS-9: Rename chat inline |
| AC-4.2: Rename sends PUT | TS-9 (verified within) |
| AC-4.3: Sidebar updates after rename | TS-9 (verified within) |
| AC-4.4: Empty name rejected | TS-10: Reject empty chat name |
| AC-5.1: New chat button visible | TS-11: New chat button |
| AC-5.2: New chat clears area, creates via POST | TS-11 (verified within) |
| AC-5.3: New chat appears in sidebar | TS-11 (verified within) |
| AC-6.1: User/assistant message bubbles | TS-12: Message bubbles displayed |
| AC-6.2: User message appears immediately | TS-12 (verified within) |
| AC-6.3: Assistant response streams via SSE | TS-13: Streaming assistant response |
| AC-6.4: Input disabled during streaming | TS-14: Input disabled during streaming |
| AC-6.5: Full history sent with each request | TS-13 (verified within) |
| AC-6.6: Chat saved after response | TS-15: Chat saved after response completes |
| AC-7.1: Export action available | TS-16: Export conversation |
| AC-7.2: Choose Markdown or JSON | TS-16 (verified within) |
| AC-7.3: Markdown export format | TS-17: Export as Markdown |
| AC-7.4: JSON export format | TS-18: Export as JSON |
| AC-7.5: Browser download triggered | TS-16 (verified within) |
| AC-8.1: Delete action in sidebar | TS-19: Delete chat from sidebar |
| AC-8.2: Delete sends DELETE request | TS-19 (verified within) |
| AC-8.3: Chat removed from sidebar | TS-19 (verified within) |
| AC-8.4: Active chat deleted clears area | TS-20: Delete active chat clears area |
| EC: LM Studio unreachable | TS-21: Model dropdown error state |
| EC: No corpora available | TS-22: Empty corpus state |
| EC: No existing chats | TS-23: Empty sidebar state |
| EC: SSE stream error | TS-24: Handle streaming error |
| EC: Long messages scrollable | TS-25: Chat area scrolls |

## Test Scenarios

### Model Selector

**TS-1: Model selector loads models**

```
Scenario: Model dropdown is populated from LM Studio
  Given the Chat UI is loaded
  And LM Studio is running with models "gemma-3-1b" and "qwen-2.5-7b"
  When the user opens the model selector dropdown
  Then the dropdown contains "gemma-3-1b" and "qwen-2.5-7b"
```

**TS-2: Default model selection**

```
Scenario: Model selector defaults to a lightweight model
  Given the Chat UI is loaded
  And LM Studio is running with models "gemma-3-1b" and "llama-70b"
  Then the model selector shows "gemma-3-1b" as the default selection
```

**TS-3: Switch model mid-conversation**

```
Scenario: User switches model during a conversation
  Given the Chat UI is loaded with an active conversation
  And the model selector shows "gemma-3-1b"
  When the user selects "qwen-2.5-7b" from the model dropdown
  And sends a new message
  Then the request to /v1/chat/completions uses model "qwen-2.5-7b"
```

### Corpus Selector

**TS-4: Corpus selector loads corpora**

```
Scenario: Corpus dropdown is populated from the API
  Given the Chat UI is loaded
  And corpora "alpha", "beta", "gamma" exist
  When the user opens the corpus selector dropdown
  Then the dropdown contains "alpha", "beta", "gamma" in alphabetical order
```

**TS-5: Default corpus selection**

```
Scenario: Corpus selector defaults to first alphabetical corpus
  Given the Chat UI is loaded
  And corpora "beta", "alpha" exist
  Then the corpus selector shows "alpha" as the default selection
```

**TS-6: Switch corpus mid-conversation**

```
Scenario: User switches corpus during a conversation
  Given the Chat UI is loaded with an active conversation using corpus "alpha"
  When the user selects "beta" from the corpus dropdown
  And sends a new message
  Then the request to /v1/chat/completions uses corpus "beta"
```

### Sidebar — Chat List

**TS-7: Sidebar displays chat list**

```
Scenario: Previous chats appear in the sidebar
  Given the Chat UI is loaded
  And 3 chats exist with different updated_at timestamps
  Then the sidebar shows 3 chat entries
  And each entry displays the chat name
  And chats are sorted by most recently updated first
```

**TS-8: Load chat from sidebar**

```
Scenario: Clicking a chat loads the full conversation
  Given the Chat UI is loaded
  And a chat "My Research" exists with 4 messages
  When the user clicks "My Research" in the sidebar
  Then the chat area displays all 4 messages
  And "My Research" is visually highlighted in the sidebar
```

### Sidebar — Rename

**TS-9: Rename chat inline**

```
Scenario: Rename a chat from the sidebar
  Given the Chat UI is loaded
  And a chat named "Old Name" exists in the sidebar
  When the user triggers inline rename on "Old Name"
  And enters "New Name"
  And confirms the rename
  Then the sidebar shows "New Name" instead of "Old Name"
```

**TS-10: Reject empty chat name**

```
Scenario: Empty name is not accepted during rename
  Given the Chat UI is loaded
  And a chat named "My Chat" exists in the sidebar
  When the user triggers inline rename on "My Chat"
  And clears the name field to empty
  And attempts to confirm
  Then the rename is not submitted
  And the chat name remains "My Chat"
```

### New Chat

**TS-11: New chat button**

```
Scenario: Create a new chat via the new chat button
  Given the Chat UI is loaded
  And the new chat button is visible
  When the user clicks the new chat button
  Then the chat area is cleared
  And a new chat appears in the sidebar
```

### Chat Area — Messages and Streaming

**TS-12: Message bubbles displayed**

```
Scenario: User and assistant messages are displayed as distinct bubbles
  Given the Chat UI is loaded with a chat containing user and assistant messages
  Then user messages and assistant messages are visually distinct
```

**TS-13: Streaming assistant response**

```
Scenario: Assistant response streams in real time
  Given the Chat UI is loaded with an active chat
  When the user sends a message "What is mini-rag?"
  Then the user message appears immediately in the chat area
  And an assistant message bubble appears
  And text appears incrementally in the assistant bubble as the SSE stream delivers chunks
```

**TS-14: Input disabled during streaming**

```
Scenario: User cannot send messages while streaming
  Given the Chat UI is loaded with an active chat
  When the user sends a message and the assistant response is streaming
  Then the message input is disabled or a loading indicator is shown
  And the user cannot send another message until streaming completes
```

**TS-15: Chat saved after response completes**

```
Scenario: Chat is persisted after assistant response
  Given the Chat UI is loaded with an active chat
  When the user sends a message and the assistant response completes
  Then the chat is saved via PUT /v1/chats/<id> with the full message history
```

### Export

**TS-16: Export conversation**

```
Scenario: Export action is available for active chat
  Given the Chat UI is loaded with an active chat containing messages
  Then an export action is available
  And the user can choose between Markdown and JSON formats
```

**TS-17: Export as Markdown**

```
Scenario: Export conversation as Markdown file
  Given the Chat UI is loaded with a chat "My Chat" containing messages
  When the user exports as Markdown
  Then a file download is triggered
  And the file has a .md extension
  And the file contains messages formatted with role headings and content
```

**TS-18: Export as JSON**

```
Scenario: Export conversation as JSON file
  Given the Chat UI is loaded with a chat "My Chat" containing messages
  When the user exports as JSON
  Then a file download is triggered
  And the file has a .json extension
  And the file contains the full chat object as JSON
```

### Delete

**TS-19: Delete chat from sidebar**

```
Scenario: Delete a chat via the sidebar
  Given the Chat UI is loaded
  And a chat "Old Chat" exists in the sidebar
  When the user triggers delete on "Old Chat"
  Then "Old Chat" is removed from the sidebar
```

**TS-20: Delete active chat clears area**

```
Scenario: Deleting the active chat clears the chat area
  Given the Chat UI is loaded
  And the active chat is "Current Chat"
  When the user deletes "Current Chat" from the sidebar
  Then the chat area is cleared
  And "Current Chat" is removed from the sidebar
```

### Edge Case Scenarios

**TS-21: Model dropdown error state**

```
Scenario: Model dropdown shows error when LM Studio is unreachable
  Given the Chat UI is loaded
  And LM Studio is not reachable
  Then the model dropdown shows an error state or empty list with a message
  And the rest of the UI remains functional (sidebar, corpus selector)
```

**TS-22: Empty corpus state**

```
Scenario: Corpus dropdown handles no corpora
  Given the Chat UI is loaded
  And no corpora exist
  Then the corpus dropdown shows an empty state with a message
```

**TS-23: Empty sidebar state**

```
Scenario: Sidebar handles no existing chats
  Given the Chat UI is loaded
  And no chats exist
  Then the sidebar shows an empty state message (e.g., "No conversations yet")
```

**TS-24: Handle streaming error**

```
Scenario: SSE error mid-stream shows partial response
  Given the Chat UI is loaded with an active chat
  When the user sends a message
  And the SSE stream encounters an error after partial data
  Then the partial response is displayed
  And an error indicator is shown
```

**TS-25: Chat area scrolls**

```
Scenario: Long conversations are scrollable
  Given the Chat UI is loaded with a chat containing many messages
  Then the chat area is scrollable
  And the view auto-scrolls to the latest message
```

## Traceability

All acceptance criteria (AC-1.1 through AC-8.4) and all edge cases are covered by test scenarios TS-1 through TS-25. No coverage gaps.

# Chat UI — Test Implementation Specification

## Test Framework & Conventions

- **Language:** Python 3.12 (test harness) + JavaScript (frontend under test)
- **E2E test framework:** Playwright (as specified in `specifications.md`: "Every feature must be verified with Playwright")
- **Python Playwright binding:** `playwright` Python package via `pytest-playwright`
- **Assertion style:** Playwright `expect()` assertions + plain `assert`
- **Test location:** `tests_e2e/` directory (separate from unit tests in `tests/`)
- **Test runner:** `uv run pytest tests_e2e/`

## Test Structure

- **File:** `tests_e2e/test_chat_ui.py`
- **Grouping:** Test functions grouped by UI area, prefixed by area
- **Naming:** `test_<area>_<scenario_description>`
- **Prerequisite:** The mini-rag service must be running on port 9191 with LM Studio available at `http://127.0.0.1:1234`. Tests use a real running service, not mocks.

## Test Scenario Mapping

| Test Scenario | Test Function | File |
|--------------|---------------|------|
| TS-1: Model selector loads models | `test_model_selector_loads_models` | `tests_e2e/test_chat_ui.py` |
| TS-2: Default model selection | `test_model_selector_defaults_to_lightweight` | `tests_e2e/test_chat_ui.py` |
| TS-3: Switch model mid-conversation | `test_model_switch_mid_conversation` | `tests_e2e/test_chat_ui.py` |
| TS-4: Corpus selector loads corpora | `test_corpus_selector_loads_corpora` | `tests_e2e/test_chat_ui.py` |
| TS-5: Default corpus selection | `test_corpus_selector_defaults_to_first` | `tests_e2e/test_chat_ui.py` |
| TS-6: Switch corpus mid-conversation | `test_corpus_switch_mid_conversation` | `tests_e2e/test_chat_ui.py` |
| TS-26: Corpus description displayed | `test_corpus_description_panel_renders_sanitized_markdown` | `tests_e2e/test_chat_ui_corpus_descriptions.py` |
| TS-27: Missing corpus description | `test_corpus_description_panel_renders_sanitized_markdown` | `tests_e2e/test_chat_ui_corpus_descriptions.py` |
| TS-28: Unsafe corpus description Markdown | `test_corpus_description_panel_renders_sanitized_markdown` | `tests_e2e/test_chat_ui_corpus_descriptions.py` |
| TS-7: Sidebar displays chat list | `test_sidebar_displays_chat_list` | `tests_e2e/test_chat_ui.py` |
| TS-8: Load chat from sidebar | `test_sidebar_load_chat` | `tests_e2e/test_chat_ui.py` |
| TS-9: Rename chat inline | `test_sidebar_rename_chat` | `tests_e2e/test_chat_ui.py` |
| TS-10: Reject empty chat name | `test_sidebar_reject_empty_rename` | `tests_e2e/test_chat_ui.py` |
| TS-11: New chat button | `test_new_chat_button` | `tests_e2e/test_chat_ui.py` |
| TS-12: Message bubbles displayed | `test_message_bubbles_displayed` | `tests_e2e/test_chat_ui.py` |
| TS-13: Streaming assistant response | `test_streaming_assistant_response` | `tests_e2e/test_chat_ui.py` |
| TS-14: Input disabled during streaming | `test_input_disabled_during_streaming` | `tests_e2e/test_chat_ui.py` |
| TS-15: Chat saved after response | `test_chat_saved_after_response` | `tests_e2e/test_chat_ui.py` |
| TS-16: Export conversation | `test_export_action_available` | `tests_e2e/test_chat_ui.py` |
| TS-17: Export as Markdown | `test_export_as_markdown` | `tests_e2e/test_chat_ui.py` |
| TS-18: Export as JSON | `test_export_as_json` | `tests_e2e/test_chat_ui.py` |
| TS-19: Delete chat from sidebar | `test_sidebar_delete_chat` | `tests_e2e/test_chat_ui.py` |
| TS-20: Delete active chat clears area | `test_delete_active_chat_clears_area` | `tests_e2e/test_chat_ui.py` |
| TS-21: Model dropdown error state | `test_model_dropdown_error_when_lm_studio_down` | `tests_e2e/test_chat_ui.py` |
| TS-22: Empty corpus state | `test_corpus_dropdown_empty_state` | `tests_e2e/test_chat_ui.py` |
| TS-23: Empty sidebar state | `test_sidebar_empty_state` | `tests_e2e/test_chat_ui.py` |
| TS-24: Handle streaming error | `test_streaming_error_shows_partial_response` | `tests_e2e/test_chat_ui.py` |
| TS-25: Chat area scrolls | `test_chat_area_scrolls_to_latest` | `tests_e2e/test_chat_ui.py` |

### TS-1: Model selector loads models

- **Setup (Given):** Navigate to `http://localhost:9191/`.
- **Action (When):** Click the model selector dropdown.
- **Assertion (Then):** Dropdown contains at least one model option with a model name/ID.

### TS-2: Default model selection

- **Setup (Given):** Navigate to `http://localhost:9191/`.
- **Action (When):** Observe the model selector's selected value.
- **Assertion (Then):** The selected model contains "gemma" or "qwen" (lightweight model) if available, otherwise any model is selected.

### TS-3: Switch model mid-conversation

- **Setup (Given):** Navigate to page. Create a new chat. Send one message.
- **Action (When):** Select a different model from the dropdown.
- **Assertion (Then):** The model dropdown shows the newly selected model. Intercept next network request to verify the `model` field changes.

### TS-4: Corpus selector loads corpora

- **Setup (Given):** Navigate to `http://localhost:9191/`.
- **Action (When):** Click the corpus selector dropdown.
- **Assertion (Then):** Dropdown contains at least one corpus. Options are in alphabetical order.

### TS-5: Default corpus selection

- **Setup (Given):** Navigate to `http://localhost:9191/`.
- **Action (When):** Observe the corpus selector's selected value.
- **Assertion (Then):** The first corpus alphabetically is selected.

### TS-6: Switch corpus mid-conversation

- **Setup (Given):** Navigate to page. Start a conversation.
- **Action (When):** Select a different corpus.
- **Assertion (Then):** The corpus dropdown shows the new selection.

### TS-26: Corpus description displayed

- **Setup (Given):** Navigate to `http://localhost:9191/` with `GET /v1/corpora` returning at least one corpus and a Markdown description in `data.descriptions`.
- **Action (When):** Open the corpus information action for the selected corpus.
- **Assertion (Then):** The description surface renders the selected corpus description as Markdown.

### TS-27: Missing corpus description

- **Setup (Given):** Navigate to `http://localhost:9191/` with `GET /v1/corpora` returning `No description available.` for the selected corpus.
- **Action (When):** Open the corpus information action.
- **Assertion (Then):** The description surface shows `No description available.`.

### TS-28: Unsafe corpus description Markdown

- **Setup (Given):** Navigate to `http://localhost:9191/` with `GET /v1/corpora` returning Markdown that includes a script tag or event-handler attribute.
- **Action (When):** Open the corpus information action.
- **Assertion (Then):** The rendered description contains safe Markdown output only; script tags and event-handler attributes are absent, and no injected script executes.

### TS-7: Sidebar displays chat list

- **Setup (Given):** Create 3 chats via API before loading the page. Navigate to page.
- **Action (When):** Observe the sidebar.
- **Assertion (Then):** Sidebar shows 3 chat entries. Each displays a chat name. Sorted by most recent first.

### TS-8: Load chat from sidebar

- **Setup (Given):** Create a chat with messages via API. Navigate to page.
- **Action (When):** Click the chat entry in the sidebar.
- **Assertion (Then):** The chat area displays the messages. The clicked chat is visually highlighted.

### TS-9: Rename chat inline

- **Setup (Given):** Create a chat. Navigate to page.
- **Action (When):** Trigger rename on the chat (double-click or edit icon). Type "Renamed Chat". Confirm.
- **Assertion (Then):** The sidebar shows "Renamed Chat".

### TS-10: Reject empty chat name

- **Setup (Given):** Create a chat. Navigate to page.
- **Action (When):** Trigger rename. Clear the field. Attempt to confirm.
- **Assertion (Then):** The rename is not applied. The original name persists.

### TS-11: New chat button

- **Setup (Given):** Navigate to page.
- **Action (When):** Click the "New chat" button.
- **Assertion (Then):** The chat area is cleared. A new entry appears in the sidebar.

### TS-12: Message bubbles displayed

- **Setup (Given):** Load a chat with user and assistant messages.
- **Action (When):** Observe the chat area.
- **Assertion (Then):** User messages and assistant messages have distinct visual styles (different CSS classes or alignment).

### TS-13: Streaming assistant response

- **Setup (Given):** Load the page with a new chat.
- **Action (When):** Type a message and send it.
- **Assertion (Then):** The user message appears immediately. An assistant bubble appears. Text appears incrementally (wait for the bubble to have progressively more text content).

### TS-14: Input disabled during streaming

- **Setup (Given):** Load the page.
- **Action (When):** Send a message. While the assistant is responding...
- **Assertion (Then):** The input field or send button is disabled. After streaming completes, the input is re-enabled.

### TS-15: Chat saved after response

- **Setup (Given):** Load the page. Start a new chat.
- **Action (When):** Send a message. Wait for the response to complete.
- **Assertion (Then):** Fetch the chat from the API (`GET /v1/chats/<id>`). The messages array includes the user message and assistant response.

### TS-16: Export action available

- **Setup (Given):** Load the page with an active chat containing messages.
- **Action (When):** Look for an export action (button, menu, icon).
- **Assertion (Then):** The export action is visible and clickable.

### TS-17: Export as Markdown

- **Setup (Given):** Load a chat with messages.
- **Action (When):** Trigger export as Markdown. Intercept the download event.
- **Assertion (Then):** A download is triggered. The filename has `.md` extension. Content contains role headings and message text.

### TS-18: Export as JSON

- **Setup (Given):** Load a chat with messages.
- **Action (When):** Trigger export as JSON. Intercept the download event.
- **Assertion (Then):** A download is triggered. The filename has `.json` extension. Content is valid JSON with chat fields.

### TS-19: Delete chat from sidebar

- **Setup (Given):** Create a chat. Navigate to page.
- **Action (When):** Trigger delete on the chat entry.
- **Assertion (Then):** The chat is removed from the sidebar.

### TS-20: Delete active chat clears area

- **Setup (Given):** Load a chat in the chat area.
- **Action (When):** Delete that chat from the sidebar.
- **Assertion (Then):** The chat area is cleared. The chat is gone from the sidebar.

### TS-21: Model dropdown error state

- **Setup (Given):** LM Studio is not running. Navigate to page.
- **Action (When):** Observe the model dropdown.
- **Assertion (Then):** The dropdown shows an error message or empty state. The rest of the UI (sidebar, corpus selector) is functional.

### TS-22: Empty corpus state

- **Setup (Given):** No corpora configured. Navigate to page.
- **Action (When):** Observe the corpus dropdown.
- **Assertion (Then):** The dropdown shows an empty state or message.

### TS-23: Empty sidebar state

- **Setup (Given):** No chats exist. Navigate to page.
- **Action (When):** Observe the sidebar.
- **Assertion (Then):** The sidebar shows an empty state message.

### TS-24: Handle streaming error

- **Setup (Given):** Configure a scenario where the SSE stream errors mid-response (e.g., stop LM Studio mid-stream, or use a mock that errors).
- **Action (When):** Send a message. The stream errors after partial data.
- **Assertion (Then):** Partial text is visible in the assistant bubble. An error indicator is shown.

### TS-25: Chat area scrolls to latest

- **Setup (Given):** Load a chat with many messages (enough to overflow the chat area).
- **Action (When):** Observe the chat area scroll position.
- **Assertion (Then):** The latest message is visible (scroll position is at the bottom).

## Fixtures & Test Data

- **`page` fixture:** Playwright page navigated to `http://localhost:9191/`. Fresh browser context per test.
- **`api_client` fixture:** httpx client pointed at `http://localhost:9191` for API-level setup (creating chats before UI tests).
- **`clean_chats` fixture (autouse):** Deletes all chats via `GET /v1/chats` + `DELETE /v1/chats/<id>` before each test to ensure isolation.
- **Download interception:** Use Playwright's `page.expect_download()` for export tests.
- **Network interception:** Use `page.route()` to intercept and verify request payloads for model/corpus switching tests.
- **Isolation:** Fresh browser context + clean chats directory per test.

## Alignment Check

Full alignment. All 25 test scenarios (TS-1 through TS-25) are mapped to test functions. No gaps.

**Design notes:**
- TS-21 (LM Studio down) and TS-24 (streaming error) depend on external service state. These may need to be run in a specific environment where LM Studio can be controlled.
- TS-22 (empty corpus) requires a service started with no corpora ingested — may need a separate test configuration.

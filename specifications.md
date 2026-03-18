
Please read AGENTS.md and bestpractices.md

# Project: Mini-RAG Chat UI

Build a ChatGPT-style web interface for the mini-rag system.

## Task Tracking

Use beads (the beads issue tracker) to manage your work:
1. Run /beads:init if not already initialized.
2. Create a ticket for each task below using /beads:create.
3. When you start a task, update it to in_progress using /beads:update.
4. When a task is complete and tested, close it using /beads:close.
5. If a task is blocked, note the blocker using /beads:update.

Do this BEFORE writing any code. Plan first, track everything.

## Architecture

- **Frontend**: Single-page HTML app in `web/` (subfolders: `css/`, `gfx/`)
- **Backend**: Extend the mini-rag service with new API endpoints and static file serving
- **Agent framework**: Strands (strands-agents) — minimal setup for tools and agent
- **LLM provider**: LM Studio at http://127.0.0.1:1234
- **Streaming**: Server-sent events (SSE) for streaming responses to the UI
- **Port**: Serve the UI on port 9191

## Tasks

### 1. Backend: Corpus listing endpoint
- Add `GET /v1/corpora` returning `{"corpora": ["name1", "name2", ...]}` sorted alphabetically.
- If this endpoint already exists, verify it works and move on.

### 2. Backend: Static file serving
- Serve files from `web/` directory at the root path.
- Structure: `web/index.html`, `web/css/`, `web/gfx/`.

### 3. Backend: Chat persistence endpoints
- Store chats as JSON in `<data_dir>/chats/`, one file per chat.
- Filename: timestamp-based (e.g., `20260311-143022.json`), never renamed on disk.
- Chat JSON schema: `name` (display name, default = datetime), `model`, `messages[]`, `corpus`, `created_at`, `updated_at`.
- Endpoints:
  - `GET /v1/chats` — list all chats (id, name, updated_at)
  - `GET /v1/chats/<id>` — load full chat
  - `POST /v1/chats` — create new chat
  - `PUT /v1/chats/<id>` — update (rename, append messages)
  - `DELETE /v1/chats/<id>` — delete a chat

### 4. Backend: Conversational agent with Strands
- Strands agent with tools for querying mini-rag (hybrid search, etc.).
- System prompt: friendly, competent assistant that always backs up claims with data from RAG tools.
- Endpoint: `POST /v1/chat/completions` — accepts messages + model + corpus, streams via SSE.
- Agent must retrieve and read RAG results before generating its answer.

### 5. Frontend: ChatGPT-style UI
- **Model selector**: dropdown fetching from `GET http://127.0.0.1:1234/v1/models`. Default to gemma-3-1b or similar lightweight model with tool-use support.
- **Corpus selector**: dropdown from `/v1/corpora`, alphabetical, default = first.
- **Sidebar**: list of previous chats on the left, selectable, with inline rename.
- **Chat area**: message bubbles (user/assistant), streaming display.
- **New chat** button.
- **Export**: download conversation as Markdown or JSON.
- Switching models mid-conversation must work (full history sent each time).
- Stream responses in real-time via SSE.
- Copy the look and feel of ChatGPT.

### 6. Integration: Auto-launch with mini-rag
- When mini-rag starts, the chat UI is also served on port 9191.

## Testing

Every feature must be verified with Playwright. Do NOT ask the user — test it yourself.
Example tests: select a model, start a new chat, send a message, switch corpus, rename a chat, export conversation, resume old chat.
For LLM testing, use gemma-3-1b or other lightweight tool-use capable models (gemma-3 variants, qwen variants).


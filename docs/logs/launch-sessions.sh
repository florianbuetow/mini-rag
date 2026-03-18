#!/bin/bash
SESSION="claude-swarm"
SPECIFICATIONS="specifications3.md"
BESTPRACTICES="bestpractices.md"

# cat > "$SPECIFICATIONS" << 'EOF'

# Please read AGENTS.md and bestpractices.md

# # Project: Mini-RAG Chat UI

# Build a ChatGPT-style web interface for the mini-rag system.

# ## Task Tracking

# Use beads (the beads issue tracker) to manage your work:
# 1. Run /beads:init if not already initialized.
# 2. Create a ticket for each task below using /beads:create.
# 3. When you start a task, update it to in_progress using /beads:update.
# 4. When a task is complete and tested, close it using /beads:close.
# 5. If a task is blocked, note the blocker using /beads:update.

# Do this BEFORE writing any code. Plan first, track everything.

# ## Architecture

# - **Frontend**: Single-page HTML app in `web/` (subfolders: `css/`, `gfx/`)
# - **Backend**: Extend the mini-rag service with new API endpoints and static file serving
# - **Agent framework**: Strands (strands-agents) — minimal setup for tools and agent
# - **LLM provider**: LM Studio at http://127.0.0.1:1234
# - **Streaming**: Server-sent events (SSE) for streaming responses to the UI
# - **Port**: Serve the UI on port 9191

# ## Tasks

# ### 1. Backend: Corpus listing endpoint
# - Add `GET /v1/corpora` returning `{"corpora": ["name1", "name2", ...]}` sorted alphabetically.
# - If this endpoint already exists, verify it works and move on.

# ### 2. Backend: Static file serving
# - Serve files from `web/` directory at the root path.
# - Structure: `web/index.html`, `web/css/`, `web/gfx/`.

# ### 3. Backend: Chat persistence endpoints
# - Store chats as JSON in `<data_dir>/chats/`, one file per chat.
# - Filename: timestamp-based (e.g., `20260311-143022.json`), never renamed on disk.
# - Chat JSON schema: `name` (display name, default = datetime), `model`, `messages[]`, `corpus`, `created_at`, `updated_at`.
# - Endpoints:
#   - `GET /v1/chats` — list all chats (id, name, updated_at)
#   - `GET /v1/chats/<id>` — load full chat
#   - `POST /v1/chats` — create new chat
#   - `PUT /v1/chats/<id>` — update (rename, append messages)
#   - `DELETE /v1/chats/<id>` — delete a chat

# ### 4. Backend: Conversational agent with Strands
# - Strands agent with tools for querying mini-rag (hybrid search, etc.).
# - System prompt: friendly, competent assistant that always backs up claims with data from RAG tools.
# - Endpoint: `POST /v1/chat/completions` — accepts messages + model + corpus, streams via SSE.
# - Agent must retrieve and read RAG results before generating its answer.

# ### 5. Frontend: ChatGPT-style UI
# - **Model selector**: dropdown fetching from `GET http://127.0.0.1:1234/v1/models`. Default to gemma-3-1b or similar lightweight model with tool-use support.
# - **Corpus selector**: dropdown from `/v1/corpora`, alphabetical, default = first.
# - **Sidebar**: list of previous chats on the left, selectable, with inline rename.
# - **Chat area**: message bubbles (user/assistant), streaming display.
# - **New chat** button.
# - **Export**: download conversation as Markdown or JSON.
# - Switching models mid-conversation must work (full history sent each time).
# - Stream responses in real-time via SSE.
# - Copy the look and feel of ChatGPT.

# ### 6. Integration: Auto-launch with mini-rag
# - When mini-rag starts, the chat UI is also served on port 9191.

# ## Testing

# Every feature must be verified with Playwright. Do NOT ask the user — test it yourself.
# Example tests: select a model, start a new chat, send a message, switch corpus, rename a chat, export conversation, resume old chat.
# For LLM testing, use gemma-3-1b or other lightweight tool-use capable models (gemma-3 variants, qwen variants).

# EOF

cat > "$BESTPRACTICES" << 'EOF'

- Never assume anything, use web search, context7 or analyze the codebase to check your assumptions.
- Never make shortcuts.
- Never leave things the way they are for compatiblity or future development.
- Only focus on implementing what is required in the most efficient way.
- Follow software engineering best practices.
- Write tests before you write the impelementation.
- Run tests regularly even when not prompted.
- Your tests will be your proof that what you implemented works.
- Never use bash -C commands. Run scripts directly with ./scritname.sh
- Never just delete files. Plan first, move with caution. But then fully commit when the plan is clear.
- If you catch yourself poking around trying to find a solution take a step back and analyze the problem with fresh eyes, you are probably approaching it wrong or missing some key information on how to do something.
- Always run just ci-quiet to check if code quality standards are satisfied and all tests pass

EOF

# Kill existing session if any
tmux kill-session -t "$SESSION" 2>/dev/null

# Layout: 2x3 grid on left (75%) + full-height right column (25%)
tmux new-session -d -s "$SESSION"

# 3 columns, distribute evenly
tmux split-window -h -t "$SESSION"
tmux split-window -h -t "$SESSION"
tmux select-layout -t "$SESSION" even-horizontal

# Split each column into 2 rows (right to left so indices don't shift)
tmux split-window -v -p 50 -t "$SESSION:0.2"
tmux split-window -v -p 50 -t "$SESSION:0.1"
tmux split-window -v -p 50 -t "$SESSION:0.0"

# Full-height right column (worker)
tmux split-window -fh -t "$SESSION" -p 25

WORKER=6
MONITORS=(0 1 2 3 4 5)

sleep 10
# Launch claude in all 7 panes
echo "Launching claude in 7 panes..."
for i in $(seq 0 6); do
  tmux send-keys -t "$SESSION.$i" "unset CLAUDECODE && claude" Enter
  sleep 1
done

# Wait for claude to start up
echo "Waiting for claude to start up..."
sleep 10

# Send spec-dd to worker pane (right column)
echo "Sending /spec-dd to pane $WORKER..."
tmux send-keys -t "$SESSION.$WORKER" -l "/spec-dd read $SPECIFICATIONS"
sleep 1
tmux send-keys -t "$SESSION.$WORKER" Enter

# Send monitor prompts to monitor panes
for pane in "${MONITORS[@]}"; do
  echo "Creating monitoring instructions for pane $pane..."
  if [ "$pane" -eq 0 ]; then
    watch_pane=$WORKER
  else
    watch_pane=$((pane - 1))
  fi
  cat > "monitor-pane-${pane}.md" << EOF
You are Claude in pane ${pane}. You monitor ONLY pane ${watch_pane} — do NOT read from or interact with any other pane.

## How to monitor

Periodically run: tmux capture-pane -t ${SESSION}.${watch_pane} -p

## Rules
  
- NEVER read from any pane other than pane ${watch_pane}. Only run tmux capture-pane on pane ${watch_pane}.
- If pane ${watch_pane} is waiting for user input, YOU are the user. Provide the input it needs to continue. Unblock it.
- All feedback and unblocking input you provide MUST be aligned with ${SPECIFICATIONS}, bestpractices.md, and AGENTS.md. Read these files first so you know the project requirements.
- If pane ${watch_pane} asks a question, answer it based on ${SPECIFICATIONS}, bestpractices.md, and AGENTS.md. Tell it to review those files if it seems confused.
- If pane ${watch_pane} violates bestpractices.md or AGENTS.md, interrupt it and point out the violation.
- Keep pane ${watch_pane} busy working on its task until the task is fully finished.
- When the pane says it is fully finished you must read the ${SPECIFICATIONS} file and ask it about every single point on it. Chances are that some points were missed. Interrogate the other pane. Always also run just ci-quiet yourself to check if code quality standards are satisfied and all tests pass. Tell the agent to run it and fix the errors when you see something is wrong.
- You can ask pane ${watch_pane} if the task is fully completed. Only when it answers with a complete (not partial) yes are you done as well.
- When the agent gets stuck poking repeatedly at the problem unable to solve it, suggest to take a step back and to use websearch to find a solition idea.
- Your job is to unblock pane ${watch_pane}. There will be no user input but yours.
- When you are pane 0 and see the next pane perform a "compacting", make sure to send a follow up prompt to re-read AGENTS.md, bestpractices.md and ${SPECIFICATIONS} to keep them focussed on the task.
- When you see that the next pane needs unblocking, then set the next sleep to 10s to check if there is a follow up question. If there isn't one, go back to your regular sleep interval.
- Compute your sleep interval to be 30s + (your pane-id squared) * 45 seconds.
- Never terminate, the next command is always to sleep and check the pane you are watching again.

EOF

  echo "Sending monitor prompt to pane $pane..."
  sleep 1
  tmux send-keys -t "$SESSION.$pane" -l "Read monitor-pane-${pane}.md and follow those instructions exactly. DO NOT READ FROM ANY OTHER PANE!"
  sleep 1
  tmux send-keys -t "$SESSION.$pane" Enter
done

echo ""
echo "Session '$SESSION' launched with 7 panes."
echo "Pane $WORKER: worker (right column, 30% width, full height)"
echo "Panes ${MONITORS[*]}: monitors (2 rows x 3 columns, 70% width)"
echo ""
echo "Attaching..."
exec tmux attach -t "$SESSION"

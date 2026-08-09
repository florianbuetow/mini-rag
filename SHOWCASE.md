# MiniRAG — Talk to Your Own Documents, Locally

> A local-first RAG (Retrieval-Augmented Generation) system: index your own
> `.md`, `.txt`, and `.pdf` documents, then **chat** with them. The assistant
> searches your corpus, reads only the most relevant passages, and writes a
> grounded answer **with inline citations** — all on your machine, with no cloud
> services and nothing leaving your laptop.

![Made with AI](https://img.shields.io/badge/Made%20with-AI-333333?labelColor=f00) ![Verified by Humans](https://img.shields.io/badge/Verified%20by-Humans-333333?labelColor=brightgreen) ![Runs locally](https://img.shields.io/badge/Runs-100%25%20local-333333?labelColor=10a37f)

---

## 1. The one-sentence pitch

**MiniRAG turns a folder of documents into a chat partner that answers from
*your* material and shows you exactly where every claim came from.**

For a non-technical reader: imagine giving a brilliant assistant a private
library — books on architecture, your meeting notes, a stack of research
papers — and being able to *ask it questions in plain language*. It doesn't
make things up; it finds the relevant pages, reads them, and answers with
footnotes you can verify.

For a technical reader: it's a fully local, configuration-driven hybrid
retrieval engine (BM25 + dense vectors + cross-encoder reranking) wired to a
tool-calling LLM agent, exposed through a FastAPI service, an MCP server, and a
ChatGPT-style web UI.

---

## 2. Why this exists — the problem in one picture

A large language model is smart but has two hard limits:

1. **It doesn't know your private documents.** It was trained on the public web,
   not on your notes, your codebase, or your company's PDFs.
2. **It can't read everything at once.** Even a 10,000-document library will not
   fit into a model's context window.

RAG solves both. Instead of stuffing the whole library into the prompt, we
**search** the library, select only the handful of passages that actually
matter, and hand *those* to the model.

```mermaid
flowchart LR
    Q["Your question"] --> S["Search the whole corpus<br/>(fast, local index)"]
    S --> P["Pick the few best passages<br/>that fit the model's context"]
    P --> L["LLM writes a grounded answer<br/>+ citations"]
    L --> A["Answer you can trust<br/>and verify"]

    style Q fill:#2f2f2f,stroke:#10a37f,color:#ececec
    style A fill:#0b7a5e,stroke:#10a37f,color:#ffffff
    style L fill:#343541,stroke:#10a37f,color:#ececec
```

> **The core trick:** MiniRAG searches the *entire* index but places only the
> *selected evidence* into the prompt. Large collections stay usable, answers
> stay grounded, and you can always trace a claim back to its source.

---

## 3. What you can do with it

| Use case | Example |
|----------|---------|
| **Personal knowledge base** | Index books on refactoring, prompting, and system design; ask "What does the literature say about the strangler-fig pattern?" |
| **Research assistant** | Drop in a folder of papers (with citation metadata); get answers with proper `[1] author2026` references. |
| **Notes & docs Q&A** | Point it at your meeting notes or product docs and interrogate them conversationally. |
| **Tooling for AI agents** | Expose your corpus to Claude (or any MCP client) as a `search` tool via the bundled MCP server. |

---

## 4. The 30,000-foot architecture

Five high-level components, each independently swappable:

```mermaid
flowchart TB
    subgraph UI["🖥️  Web UI (browser)"]
        CHAT["ChatGPT-style chat<br/>corpus · model · retrieval controls"]
    end

    subgraph SVC["⚙️  FastAPI Service (local, in-process)"]
        API["REST API<br/>/v1/..."]
        AGENT["RAG Agent<br/>(tool-calling, streaming)"]
        subgraph RET["🔎  Hybrid Retrieval"]
            SPARSE["Lexical search<br/>BM25 / Tantivy"]
            DENSE["Dense search<br/>FastText + FAISS"]
            MERGE["Merge + rerank<br/>cross-encoder"]
        end
        PRUNE["Context pruning<br/>(token budget)"]
        STORE[("SQLite<br/>docs · chunks · citations")]
    end

    subgraph LLM["🧠  LLM (LM Studio, OpenAI-compatible)"]
        INF["Local model inference<br/>streams tokens"]
    end

    CHAT -- "SSE chat stream" --> API
    API --> AGENT
    AGENT -- "decides to search" --> RET
    SPARSE --> MERGE
    DENSE --> MERGE
    MERGE --> PRUNE
    PRUNE -- "selected evidence" --> AGENT
    AGENT -- "prompt + evidence" --> INF
    INF -- "grounded answer + citations" --> AGENT
    AGENT -- "tokens + status" --> API
    RET <--> STORE

    style UI fill:#171717,stroke:#444,color:#ececec
    style SVC fill:#212121,stroke:#444,color:#ececec
    style LLM fill:#1e1e2e,stroke:#10a37f,color:#ececec
    style RET fill:#2f2f2f,stroke:#10a37f,color:#ececec
```

**Why this shape?** The LLM never talks to the index directly. It is given one
**tool** — `search_documents` — and *decides on its own* when to call it. The
service owns retrieval, scoring, pruning, and citation tracking; the model owns
language and reasoning. Clean separation, each side independently testable and
replaceable.

---

## 5. End-to-end: what happens when you ask a question

This is the full lifecycle of a single chat message, touching every high-level
component: **UI → API → Agent → LLM (query decision) → lexical search → dense
search → reranking → context pruning → LLM inference → UI**.

```mermaid
sequenceDiagram
    autonumber
    participant U as 🖥️ Web UI
    participant A as ⚙️ API<br/>(/v1/chat/completions)
    participant AG as 🤖 RAG Agent<br/>(Strands)
    participant M as 🧠 LLM<br/>(LM Studio)
    participant SP as 🔤 Lexical<br/>(Tantivy BM25)
    participant DN as 🧮 Dense<br/>(FastText+FAISS)
    participant RR as 🎯 Reranker<br/>(cross-encoder)
    participant PR as ✂️ Context Pruner

    U->>A: POST messages + corpus + model + retrieval settings
    A-->>U: SSE status: "Preparing request…"
    A->>AG: stream(messages, model, corpus, mode, top_k, alpha, reranking)
    AG->>M: Here's the question + a search_documents tool
    A-->>U: SSE status: "Generating search query…"
    M-->>AG: tool call → search_documents("…query…")
    A-->>U: SSE status: "Searching corpus with N docs / M chunks…"

    par Hybrid retrieval
        AG->>DN: embed query → top-k vectors (cosine)
        AG->>SP: BM25 keyword search → top-k
    end
    DN-->>AG: scored chunks [0..1]
    SP-->>AG: scored chunks [0..1]
    AG->>AG: merge: alpha·dense + (1-alpha)·sparse

    opt Reranking enabled
        A-->>U: SSE status: "Retrieved C candidates / Reranking…"
        AG->>RR: re-score (query, passage) pairs jointly
        RR-->>AG: reordered top-k (sigmoid scores)
    end

    AG->>PR: fit chunks into token budget
    PR-->>AG: pruned evidence set
    A-->>U: SSE status: "Using K chunks from D documents"
    AG->>M: prompt + selected evidence (tool result)
    A-->>U: SSE status: "Streaming answer…"
    M-->>AG: answer tokens (streamed)
    AG-->>A: token events
    A-->>U: SSE token: … … … (live typing)
    M-->>AG: "#### Sources\n- [1] key …"
    A-->>U: SSE token: citations
    A-->>U: SSE done
    Note over U: Renders answer with citation pills, autosaves the chat, may auto-generate a title
```

Every status line in that diagram is a **real event** the service emits over
Server-Sent Events, so the user sees the machine thinking: *generating query →
searching → reranking → pruning → streaming answer*.

---

## 6. The data folder — where everything lives

MiniRAG is **multi-corpus**: each named corpus (e.g. `books`, `notes`) gets its
own isolated storage and indices. Everything derives from one configurable
`data_dir`.

```text
data/
├── input/
│   └── {corpus}/
│       ├── md/            # Markdown source files (human-authored)
│       ├── txt/           # Plain-text, ingestion-ready  ← the index reads from here
│       │   ├── doc.txt
│       │   └── doc.json   # Optional citation sidecar (flat or nested format)
│       ├── metadata/      # Source/citation metadata
│       └── evals/         # Q&A pairs for retrieval-quality evaluation
│
├── models/                # Embedding + reranker model files
│   └── cc.en.300.bin      # FastText, 300-dim Common Crawl English
│
├── storage/
│   └── {corpus}/
│       └── minirag.db     # SQLite: documents, chunks, citations
│
├── index/
│   └── {corpus}/
│       ├── faiss/         # Dense vector index (cosine via inner product)
│       └── tantivy/       # Lexical BM25 index (tokenized, stemmed)
│
├── chats/                 # Persisted conversations as JSON (atomic writes)
│   └── 20260623-..._.json
│
└── export/                # Exported chunks for inspection/debugging
```

**Path discipline:** components only know their own subdirectory convention
(the ingestion module knows `input/{corpus}/txt/`, the embeddings module knows
`models/`). The base `data_dir` is the single source of truth, set in config.

---

## 7. The ingestion pipeline — from raw files to a searchable index

```mermaid
flowchart TB
    subgraph CONV["1 · Convert to text"]
        MD["doc.md"] -->|md2txt.py| TXT["doc.txt"]
        PDF["doc.pdf"] -->|pdf2txt.py| TXT
        JSON["doc.json<br/>citation sidecar"] -.copied alongside.-> TXT
    end

    subgraph ING["2 · Ingest (scripts/ingest.py → IndexingClient → API)"]
        TXT --> LED{"In the ledger?<br/>(incremental mode)"}
        LED -- "yes" --> SKIP["Skip (already indexed)"]
        LED -- "no" --> POST["POST /v1/corpus/{corpus}/index"]
    end

    subgraph PIPE["3 · Service-side indexing pipeline (Orchestration)"]
        POST --> DOC["Store document + citation<br/>(SQLite, fail-fast on dup key)"]
        DOC --> CHUNK["Chunk text<br/>500 words, 30% overlap"]
        CHUNK --> EMB["Embed each chunk<br/>(unit-normalized vectors)"]
        EMB --> FAISS[("Index in FAISS<br/>dense")]
        CHUNK --> TANT[("Index in Tantivy<br/>sparse / BM25")]
        EMB --> SQL[("Store chunks<br/>SQLite")]
    end

    PIPE --> LEDW["Record file in ingestion ledger"]

    style CONV fill:#171717,stroke:#444,color:#ececec
    style ING fill:#212121,stroke:#444,color:#ececec
    style PIPE fill:#2f2f2f,stroke:#10a37f,color:#ececec
```

Key properties:

- **Incremental indexing** — a per-corpus *ledger* records what's already
  indexed. `just ingest --update` adds only new files; a full `just ingest`
  destroys and rebuilds. Re-indexing 10,000 documents takes < 10 minutes on a
  modern laptop.
- **Citations are first-class** — every document carries a citation record,
  either from a `.json` sidecar (flat `{cite_key, title, doi, …}` *or* nested
  format — both are normalized) or auto-generated from the filename. Citation
  keys must be unique; duplicates fail fast.
- **Fail-fast, no silent partial state** — if one file fails to index, ingestion
  stops with the original error. Files indexed before the failure stay in the
  ledger, so a re-run resumes cleanly.
- **Deterministic** — files are processed in sorted order for reproducible
  chunk/document IDs.

---

## 8. Dense vs. Sparse retrieval — and why you need both

This is the heart of "hybrid" search. The two methods fail in *opposite* ways,
so combining them is strictly better than either alone.

### Sparse (lexical / BM25 — Tantivy)

Matches **the actual words**. Think of a very smart `Ctrl-F` that understands
word frequency, document length, and stemming.

- ✅ Exact terms, names, codes, rare jargon, acronyms (`K8s`, `BM25`, `useEffect`).
- ✅ Transparent and fast; no model needed.
- ❌ **Vocabulary mismatch:** a search for "car" misses a document that only
  says "automobile." It matches *strings*, not *meaning*.

### Dense (semantic / vector — FastText + FAISS)

Matches **meaning**. Each chunk and the query become a 300-dimensional vector;
similar meanings land near each other in vector space (cosine similarity).

- ✅ Synonyms and paraphrase: "car" ≈ "automobile" ≈ "vehicle."
- ✅ Conceptual questions where the user's words differ from the document's.
- ❌ **Imprecise on exact tokens:** can rank a *thematically* similar passage
   above the one that literally contains the term you typed; may blur rare
   identifiers.

### Side-by-side

| Dimension | Sparse (BM25) | Dense (vectors) |
|-----------|---------------|-----------------|
| Matches on | Exact words / stems | Meaning / semantics |
| Synonyms & paraphrase | ✗ Misses | ✓ Handles |
| Rare terms, IDs, names | ✓ Excellent | ~ Can blur |
| Typo / morphology | ~ Stemming helps | ✓ Robust |
| Interpretability | ✓ "these words matched" | ✗ Opaque geometry |
| Cost | Cheap, no model | Needs an embedding model |
| Classic failure | "car" ≠ "automobile" | ranks vibe over the exact keyword |

### Hybrid = the best of both

MiniRAG runs **both** searches, normalizes each to `[0, 1]`, then blends them
with a single tunable knob **α (alpha)**:

```
final_score = α · dense_score + (1 − α) · sparse_score
```

- `α = 1.0` → pure semantic (meaning only)
- `α = 0.0` → pure lexical (keywords only)
- `α = 0.65` → the shipped default — lean semantic, keep keyword precision

```mermaid
flowchart LR
    Q["query"] --> D["Dense top-k<br/>(meaning)"]
    Q --> S["Sparse top-k<br/>(keywords)"]
    D --> N["normalize → 0..1"]
    S --> N2["normalize → 0..1"]
    N --> W["α · dense"]
    N2 --> W2["(1−α) · sparse"]
    W --> SUM["sum per chunk"]
    W2 --> SUM
    SUM --> R["ranked candidates"]
    style Q fill:#2f2f2f,stroke:#10a37f,color:#ececec
    style R fill:#0b7a5e,stroke:#10a37f,color:#ffffff
```

---

## 9. Why a reranker? (The crucial third stage)

Hybrid merge gives a *good* ordering, but dense and sparse scores were computed
**independently of each other** and then arithmetically combined. Neither stage
ever looked at the query and a passage *together*. That's exactly what a
cross-encoder reranker does.

### Bi-encoder vs. cross-encoder

```mermaid
flowchart TB
    subgraph BI["Bi-encoder — used for retrieval (fast, scalable)"]
        Q1["query"] --> EQ["encode query → vector"]
        DOCS["every chunk"] --> ED["encode chunk → vector<br/>(precomputed at index time)"]
        EQ --> COS["cosine similarity"]
        ED --> COS
    end

    subgraph CE["Cross-encoder — used for reranking (slow, precise)"]
        PAIR["[query, chunk] together"] --> TR["one model pass over the PAIR"]
        TR --> SC["relevance score"]
    end

    style BI fill:#212121,stroke:#444,color:#ececec
    style CE fill:#2f2f2f,stroke:#10a37f,color:#ececec
```

- A **bi-encoder** (retrieval) embeds the query and each chunk *separately*.
  This is what makes search fast — chunk vectors are precomputed once and stored
  in FAISS — but the query and chunk never "meet," so subtle relevance is lost.
- A **cross-encoder** (reranker) feeds the query and a candidate passage through
  the model **together**, letting every query word attend to every passage word.
  Far more accurate, but far too slow to run over the whole corpus.

### The pattern: retrieve wide, rerank narrow

```mermaid
flowchart LR
    Q["query"] --> H["Hybrid retrieve<br/>top_k × candidate_multiplier<br/>(e.g. 50 × 3 = 150)"]
    H --> CE["Cross-encoder re-scores<br/>all 150 (query, passage) pairs"]
    CE --> TOP["Return the true top-k<br/>(e.g. best 50)"]
    style Q fill:#2f2f2f,stroke:#10a37f,color:#ececec
    style TOP fill:#0b7a5e,stroke:#10a37f,color:#ffffff
```

MiniRAG retrieves a **wide** candidate pool (`top_k × candidate_multiplier`,
default ×3) cheaply with the bi-encoder + BM25, then spends the expensive
cross-encoder pass only on those finalists. Raw logits are squashed to `[0, 1]`
with a sigmoid and the list is re-sorted.

> **Why it matters for the answer:** the reranker decides *which* passages reach
> the LLM. Better finalists → a better-grounded, more accurate answer with the
> right citations. The model is only ever as good as the evidence you hand it.

Reranking is **opt-in** via config (`search.reranking.enabled`); the chat UI
also exposes a per-conversation toggle. Default model:
`cross-encoder/ms-marco-MiniLM-L12-v2`.

---

## 10. Context pruning — fitting evidence into the model's head

Even after reranking, the selected chunks must fit inside the model's context
window alongside the system prompt and the answer. MiniRAG counts tokens
(`tiktoken`, `cl100k_base`) and keeps the highest-ranked chunks that fit within
a **document-token budget** = `context_window × document_context_fraction`
(default 60% of the window).

- The model's true context window is discovered live from **LM Studio's metadata
  API** (`/api/v1/models`, with a `/api/v0` fallback), cached per model.
- If LM Studio metadata is unavailable, it falls back to a conservative 4096-token
  window.
- The UI reports pruning when it happens: *"Pruned context to K chunks within
  N document tokens."*

```mermaid
flowchart LR
    RANK["reranked chunks<br/>(best first)"] --> LOOP{"adding this chunk<br/>still under budget?"}
    LOOP -- yes --> KEEP["keep it"]
    LOOP -- no --> DROP["drop it, try next"]
    KEEP --> LOOP
    KEEP --> OUT["evidence set → LLM"]
    style OUT fill:#0b7a5e,stroke:#10a37f,color:#ffffff
```

---

## 11. The LLM layer — a tool-calling agent

The conversational agent is built on the **Strands Agents SDK** talking to a
**local LM Studio** server over its OpenAI-compatible API
(`http://127.0.0.1:1234/v1`). This means **any** model you load in LM Studio
works — the model id is passed through verbatim.

How it behaves:

- The agent is given the `search_documents` tool and a system prompt instructing
  it to **always ground claims in retrieved data** and to **cite sources**.
- It autonomously decides when to search (it can search, read, and even refine).
- Tool results are formatted as `[citation_key#chunkN] passage text` so the
  model can map evidence back to sources.
- The model emits a final **`#### Sources`** section mapping `[1]`, `[2]`… to
  source document keys — and is explicitly forbidden from inventing keys.
- Responses **stream token-by-token** back to the browser; the stream is fully
  **cancellable** (closing the request stops model inference mid-flight).
- A separate lightweight **title agent** generates a ≤5-word chat title from the
  first exchange.

---

## 12. Detailed system diagram (low level)

Every module, the interface it implements, and its concrete backend. **All
backends are swappable** because everything is programmed against an interface.

```mermaid
flowchart TB
    subgraph CLIENTS["Consumers"]
        WEB["Web UI<br/>(static SPA)"]
        MCP["MCP server<br/>(mini-rag.ts)"]
        PYC["Python clients<br/>IndexingClient / QueryClient"]
        SCRIPTS["scripts/<br/>ingest · md2txt · pdf2txt · search · evaluate"]
    end

    subgraph APIL["FastAPI layer (api/)"]
        RC["routes_chat_completions<br/>SSE streaming"]
        RH["routes_chats<br/>chat CRUD + title"]
        RQ["routes_query<br/>dense / sparse / hybrid"]
        RI["routes_index<br/>index / destroy"]
        RCI["routes_citation"]
        RINFO["routes_info<br/>health · info · models · corpora · shutdown"]
        STATIC["static file mount"]
        GUARD["ensure_healthy() guard<br/>+ uniform response envelope"]
    end

    subgraph CORE["Core (minirag/)"]
        CM["CorpusManager<br/>per-corpus cache"]
        ORCH["Orchestration<br/>index + search coordination"]
        AGENT["MiniRagAgent<br/>(Strands, streaming, tool-calling)"]
        PRUNE["ContextPruner<br/>(tiktoken budget)"]
        FAC["backend_factory<br/>builds per-corpus backends"]
    end

    subgraph IFACES["Interfaces → Implementations"]
        EMB["Embeddings<br/>→ FastText | LM Studio"]
        ST["Storage<br/>→ SQLiteStorage"]
        DR["DenseRetrieval<br/>→ FAISSDense (IndexFlatIP)"]
        SR["SparseRetrieval<br/>→ TantivySparse (BM25)"]
        RK["Reranker (Protocol)<br/>→ CrossEncoderReranker"]
        HM["merge_hybrid_results<br/>(pure function)"]
    end

    subgraph EXT["External / local services"]
        LM["LM Studio<br/>chat + embeddings + metadata"]
    end

    WEB --> RC & RH & RQ & RI & RCI & RINFO
    MCP --> RQ & RCI & RINFO
    PYC --> RQ & RI & RCI
    SCRIPTS --> PYC
    STATIC --> WEB

    RC --> AGENT
    RH -.persists JSON.-> CHATS[("data/chats/*.json")]
    RQ --> CM
    RI --> CM
    RCI --> CM
    AGENT --> CM
    AGENT --> PRUNE
    AGENT --> LM
    RINFO -.proxy.-> LM

    CM --> ORCH
    CM --> FAC
    FAC --> EMB & ST & DR & SR & RK
    ORCH --> EMB & ST & DR & SR & RK & HM
    EMB -.lmstudio provider.-> LM

    style CLIENTS fill:#171717,stroke:#444,color:#ececec
    style APIL fill:#212121,stroke:#444,color:#ececec
    style CORE fill:#2f2f2f,stroke:#10a37f,color:#ececec
    style IFACES fill:#1e1e2e,stroke:#10a37f,color:#ececec
    style EXT fill:#343541,stroke:#10a37f,color:#ececec
```

### Storage schema (SQLite, per corpus)

```mermaid
erDiagram
    DOCUMENTS ||--o{ CHUNKS : "has many"
    DOCUMENTS ||--|| CITATIONS : "described by"
    DOCUMENTS {
        int document_id PK
        text content
    }
    CHUNKS {
        int chunk_id PK
        int document_id FK
        text content
    }
    CITATIONS {
        text citation_key PK
        int document_id FK
        text citation_json
    }
```

Retrieval engines return `(chunk_id, score)`; the orchestration layer resolves
each chunk back to its text and citation key through SQLite (with a thread-safe
LRU cache for citation-key lookups), producing the uniform `SearchResult` type
used everywhere — retrieval, merge, rerank, clients, and API serialization.

---

## 13. The REST API at a glance

All endpoints are versioned under `/v1`, return a uniform envelope
(`{status, data}` or `{status, error}`), and are guarded by a health check.

| Method & path | Purpose |
|---------------|---------|
| `POST /v1/chat/completions` | **The chat endpoint** — streams a grounded answer over SSE (`status`/`token`/`error`/`done`). |
| `GET/POST/PUT/DELETE /v1/chats[/{id}]` | Chat persistence (list, create, load, update, delete). |
| `POST /v1/chats/{id}/generate-title` | Auto-name a conversation. |
| `GET /v1/corpora` | List indexed corpora discovered on disk. |
| `GET /v1/models` | Proxy LM Studio's model list (avoids browser CORS). |
| `POST /v1/corpus/{corpus}/query/{dense\|sparse\|hybrid}` | Raw retrieval (no LLM) — great for demos and evaluation. |
| `POST /v1/corpus/{corpus}/index` · `DELETE …/index` | Index one document / wipe a corpus. |
| `GET /v1/corpus/{corpus}/citation/{key}` | Full citation metadata for a source. |
| `GET /v1/health` · `GET /v1/info` · `POST /v1/shutdown` | Service lifecycle & introspection. |

> The split between `query/*` (pure retrieval) and `chat/completions` (retrieval
> **+** generation) makes MiniRAG easy to demo: you can show the raw ranked
> chunks first, then show the LLM turning them into an answer.

---

## 14. The web UI

A ChatGPT-style single-page app served directly by the FastAPI service — **pure
vanilla JavaScript** (~1,270 lines, IIFE pattern, no React/Vue), **no build
step**. Markdown is rendered with `marked`, code is highlighted with
`highlight.js`, and all HTML is sanitized with `DOMPurify`.

**Layout** — a fixed left **sidebar** (chat history + "New Chat"), a sticky
**top bar** (model & corpus selectors, search settings, theme toggle, export), a
scrollable **chat pane** (centered, markdown-rendered messages), and a fixed
**input area** with an auto-resizing textarea. Fully responsive: the sidebar
collapses to an off-canvas drawer under 768px.

**Retrieval controls**, persisted both to `localStorage` and per-conversation:

| Control | Behaviour |
|---------|-----------|
| Corpus selector | Populated from `GET /v1/corpora`; disables new chats when no corpus exists. |
| Model selector | Populated from `GET /v1/models`; grouped by prefix, embedding/OCR models filtered out. |
| Search mode | `hybrid` / `dense` / `sparse`. |
| `top_k` | 1–100, default 50. |
| **α slider** | 0.0–1.0 dense/sparse balance, live value readout. |
| Reranking toggle | On by default. |

**Live pipeline feedback** — a status chip with a pulsing dot mirrors the SSE
`status` events in real time ("Generating search query…", "Searching corpus
with N documents and M chunks…", "Reranking candidates…", "Using K chunks from D
documents", "Streaming answer…"). Tokens stream into the message as they arrive;
`error` events surface as an inline error pill, and the frontend even validates
the stream contract and reports malformed payloads.

**Citations** — the model's bracketed `[citation_key]` references are extracted
before markdown parsing and re-rendered as teal **citation pills** (display
chips that make the grounded sources visually unmistakable). Full citation
metadata is available from `GET /v1/corpus/{corpus}/citation/{key}`.

**Conversation management** — chats are created on first send, autosaved via
`PUT /v1/chats/{id}` after each turn, auto-titled after the first exchange
(`POST …/generate-title`), renamable, deletable, and **exportable to Markdown or
JSON**. The last active chat is restored from `localStorage` on reload. A
local-first **dark/light theme** toggle (persisted) completes the "quiet reading
room" aesthetic.

> *Note:* there is no dedicated "stop generation" button in the UI today — the
> request is aborted on error or navigation. The **service** side, however, is
> fully cancellable: a client disconnect sets a cancellation event that stops
> the active model stream mid-flight.

---

## 15. Technology stack

| Layer | Technology |
|-------|------------|
| Service | Python 3.12+, FastAPI, Uvicorn, Pydantic (strict, no optional config) |
| Dense retrieval | FastText (`cc.en.300.bin`, 300-d) + FAISS (`IndexFlatIP`, cosine) |
| Sparse retrieval | Tantivy (BM25, tokenization, stemming) |
| Reranking | sentence-transformers cross-encoder (optional) |
| Embeddings providers | FastText (local) **or** LM Studio (OpenAI-compatible) — swappable |
| LLM | Any model via LM Studio (OpenAI-compatible), driven by Strands Agents SDK |
| Storage | SQLite (documents, chunks, citations) |
| Persistence | JSON chat files (atomic temp-file + rename) |
| Integrations | MCP server (Node + TypeScript) exposing `search` / `get_citation` / `list_corpora` |
| Tooling | `uv` (packages), `just` (tasks) |

---

## 16. What makes it engineering-grade

- **Configuration-driven, zero hardcoded defaults** — every setting lives in
  `config.yaml`, validated by strict Pydantic models (`extra="forbid"`, every
  field required). The service refuses to start on a bad config (fail-fast).
- **Interfaces everywhere** — Storage, DenseRetrieval, SparseRetrieval, Reranker,
  and Embeddings are all abstractions; SQLite/FAISS/Tantivy/cross-encoder/FastText
  are *just one implementation each*, swappable without touching callers.
- **Multi-corpus isolation** — each corpus has its own SQLite DB and FAISS/Tantivy
  indices, created lazily and cached.
- **Honest errors** — no silent fallbacks, no masked failures; exceptions bubble
  up with descriptive messages inside a uniform response envelope.
- **A real quality bar** — the CI pipeline runs format, style, strict type
  checking (mypy **and** pyright), security scan (bandit), dependency hygiene
  (deptry), vulnerability audit (pip-audit), spell check, custom static analysis
  (semgrep — no defaults, no type suppression), and enforces test coverage.

---

## 17. See it run (≈ 3 commands)

```bash
just init                      # set up env, fetch the FastText model, write config.yaml
just start                     # launch the FastAPI service (UI at http://127.0.0.1:7001)
just md2txt corpus=books       # convert data/input/books/md → txt
just ingest corpus=books       # build the hybrid index
# → open the browser, pick the corpus + a model loaded in LM Studio, and chat.
```

Prefer the raw retrieval view for a demo? `just search corpus=books` runs an
interactive search loop, and `just evaluate corpus=books` scores retrieval
quality against your own Q&A pairs.

---

### One slide, if you only have one

> **MiniRAG** indexes your documents three ways — keywords (BM25), meaning
> (vectors), and a precision reranker — searches the whole library, hands only
> the best evidence to a *local* LLM, and streams back an answer with citations
> you can trace to the source. No cloud. Fully swappable. Honest about its sources.

---
marp: true
theme: xebia-theme
paginate: true
---

![bg cover](images/slide_graphics/library.png)

<style>
/* ASCII flow diagrams are left-aligned art: the theme centers .flow-diagram
   lines individually, which breaks monospace column alignment (pipes, arrows,
   branch connectors). Keep the framed box centered, but the text left-aligned. */
section .flow-diagram pre,
section .flow-diagram pre code { text-align: left !important; }

/* A markdown <table> defaults to content width and aligns left inside its
   wrapper (text-align can't center a table box). Center the table itself. */
section .table-container table,
section .uc-table table { margin-left: auto; margin-right: auto; }
</style>

---

<style scoped>
  section .quote-block { font-size: 0.72em; }
  section .column img {
    border-radius: 8px;
    box-shadow: 0 4px 18px rgba(0,0,0,0.25);
  }
</style>

<div class="columns" style="align-items: center; width: 100%;">
<div class="column" style="justify-content: center; min-width: 0; overflow: hidden;">

# MiniRAG
### Talk to your own documents, locally
by Florian Buetow

<br/>

<div class="quote-block">

> Turn a folder of documents into a chat partner that answers from *your*
> material — and shows you exactly where every claim came from.

</div>
<br/>
<div class="smaller-content">100% local · no cloud · hybrid search + a tool-calling LLM</div>
</div>
<div class="column" style="align-items: center; justify-content: center; text-align: center; min-width: 0;">

<img src="images/slide_graphics/library.png" style="max-width: 100%; height: auto;">

</div>
</div>

---

<style scoped>
  section .toc { font-weight: bold; }
  section .toc li { color: var(--dark); }
</style>

# Table of Contents

<div class="toc">

1. The Idea
2. Architecture
3. Data &amp; Ingestion
4. Retrieval — the Heart
5. Under the Hood
6. Run It

</div>

---

# 1 · The Idea

&nbsp;

---

## The problem an LLM can't solve alone

<style scoped>
  section .challenge-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    width: 92%;
    margin: 0 auto;
    align-items: start;
    text-align: left;
  }
  section .challenge-panel {
    border-left: 4px solid var(--cta-green);
    padding-left: 0.9rem;
  }
  section .challenge-panel h2 {
    font-size: 1em;
    margin: 0 0 0.4em 0;
    color: var(--tranquil-velvet);
  }
  section .challenge-panel p { font-size: 0.78em; line-height: 1.3; }
</style>

<div class="challenge-layout">
<div class="challenge-panel">

## It doesn't know your documents

<p>It was trained on the public web — not on your notes, your codebase, or your private PDFs.</p>

</div>
<div class="challenge-panel">

## It can't read everything at once

<p>A 10,000-document library will never fit inside a model's context window.</p>

</div>
</div>

<!--
A large language model is smart but has two hard limits: it doesn't know your private material, and it can't ingest a whole library at once. RAG — Retrieval-Augmented Generation — solves both.
-->

---

## The core trick

<div class="flow-diagram">
<pre>
Your question
      |
      v
Search the WHOLE corpus          (fast local index: BM25 + vectors)
      |
      v
Pick only the BEST passages      (the few that fit the context window)
      |
      v
LLM writes a grounded answer     (+ citations)
      |
      v
An answer you can trust and verify
</pre>
</div>

<!--
The core trick: search the entire index, but place only the selected evidence into the prompt. Large collections stay usable, answers stay grounded, and every claim can be traced back to its source.
-->

---

<style scoped>
  section .uc-table { width: 90%; margin: 0 auto; }
  section .uc-table table { font-size: 0.8em; line-height: 1.15; }
  section .uc-table td, section .uc-table th { padding: 0.45em 0.6em; }
  section .uc-table th { color: var(--tranquil-velvet); }
</style>

## What you can do with it

<div class="uc-table">

| Use case | Example |
| --- | --- |
| **Personal knowledge base** | Index books on refactoring &amp; architecture; ask "What does the literature say about the strangler-fig pattern?" |
| **Research assistant** | Drop in a folder of papers; get answers with proper `[1] author2026` references. |
| **Notes &amp; docs Q&amp;A** | Interrogate your meeting notes or product docs conversationally. |
| **Tooling for AI agents** | Expose your corpus to Claude (or any MCP client) as a `search` tool. |

</div>

<!--
Anything you can put in a folder of .md, .txt, or .pdf becomes a grounded, queryable knowledge source.
-->

---

# 2 · Architecture

&nbsp;

---

## Five components, each swappable

<div class="flow-diagram">
<pre>
        Browser  ·  Web UI (chat)
                 |   SSE stream
                 v
        FastAPI service   (local, in-process)
                 |
                 v
        RAG Agent   (tool-calling, streaming)
            |  decides WHEN to search
            v
   +-------------------------------+
   |        Hybrid Retrieval        |
   |   Lexical   (BM25 / Tantivy)   |
   |   Dense     (FastText + FAISS) |
   |   Merge + cross-encoder rerank |
   +-------------------------------+
            |  selected evidence
            v
       Context pruning  (token budget)
            |
            v
        Local LLM (LM Studio)  -->  streams answer + citations
</pre>
</div>

<!--
The LLM never touches the index directly. It is given ONE tool — search_documents — and decides on its own when to call it. The service owns retrieval, scoring, pruning, and citation tracking; the model owns language and reasoning. Clean separation, each side independently testable and replaceable.
-->

---

<style scoped>
  section .flow-diagram pre { font-size: 0.46em; line-height: 1.25; }
</style>

## End-to-end: one question, every component

<div class="flow-diagram">
<pre>
UI  --POST /v1/chat/completions-->  API
                                     |  status: "Preparing request..."
                                     v
                               RAG Agent  -->  LLM  (question + search tool)
                                     |  status: "Generating search query..."
                                     v
                       LLM calls  search_documents("...query...")
                                     |  status: "Searching N docs / M chunks..."
                       +-------------+-------------+
                       v                           v
              Dense: FastText+FAISS        Sparse: Tantivy BM25
              embed -> cosine top-k        keyword top-k
                       +-------------+-------------+
                                     v
                    Merge:   alpha*dense + (1-alpha)*sparse
                                     |  status: "Reranking candidates..."
                                     v
              Cross-encoder re-scores (query, passage) pairs
                                     v
                  Context pruning  ->  fit the token budget
                                     |  status: "Using K chunks / D docs"
                                     v
              Agent  -->  LLM:   prompt + selected evidence
                                     |  status: "Streaming answer..."
                                     v
        LLM streams tokens  -->  API  --(SSE)-->  UI   (live typing)
                                     v
        "#### Sources / [1] key..."  -->  citation pills,  then  done
</pre>
</div>

<!--
Every status line here is a REAL Server-Sent Event the service emits, so the user watches the machine think: generating query, searching, reranking, pruning, streaming. Dense and sparse run in parallel; the merge, rerank, and prune stages decide exactly which passages reach the model.
-->

---

# 3 · Data &amp; Ingestion

&nbsp;

---

## The data folder — multi-corpus by design

<div class="tree-content">
<pre>
data/
|-- input/{corpus}/
|     |-- md/         Markdown source files
|     |-- txt/        Ingestion-ready text   <-- the index reads from here
|     |     |-- doc.txt
|     |     +-- doc.json    citation sidecar (optional)
|     |-- metadata/   source / citation metadata
|     +-- evals/      Q&A pairs for retrieval-quality evaluation
|-- models/           cc.en.300.bin (FastText) + reranker cache
|-- storage/{corpus}/minirag.db    SQLite: documents, chunks, citations
|-- index/{corpus}/
|     |-- faiss/      dense vector index
|     +-- tantivy/    lexical BM25 index
+-- chats/            persisted conversations (JSON, atomic writes)
</pre>
</div>

<!--
Each named corpus (books, notes, ...) gets its own isolated SQLite DB and FAISS/Tantivy indices. Everything derives from one configurable data_dir; each component only knows its own subdirectory convention.
-->

---

## Ingestion: from raw files to a searchable index

<style scoped>
  section .flow-diagram pre { font-size: 0.55em; }
</style>

<div class="flow-diagram">
<pre>
doc.md  /  doc.pdf            doc.json (citation)
      |  md2txt / pdf2txt           |
      v                             |
   doc.txt  <-----------------------+
      |
      v
 In the ledger?  --yes-->  skip (already indexed)
      |  no
      v
 POST /v1/corpus/{corpus}/index
      |
      v
 Store document + citation     (SQLite, fail-fast on duplicate key)
      v
 Chunk text   (500 words, 30% overlap)
      v
 Embed each chunk   (unit-normalized vectors)
      |--->  FAISS    (dense index)
      |--->  Tantivy  (sparse / BM25)
      +--->  SQLite   (chunk text)
      v
 Record the file in the ingestion ledger
</pre>
</div>

<!--
Incremental indexing: a per-corpus ledger records what's already indexed, so `just ingest --update` adds only new files. Citations are first-class (sidecar or auto-generated, both normalized). Fail-fast, deterministic order, no silent partial state. ~10,000 docs index in under 10 minutes on a laptop.
-->

---

# 4 · Retrieval — the Heart

&nbsp;

---

<style scoped>
  section .table-container { width: 92%; }
  section .table-container table { font-size: 0.82em; }
</style>

## Dense vs. Sparse — they fail in opposite ways

<div class="table-container">

| Dimension | Sparse (BM25) | Dense (vectors) |
| --- | --- | --- |
| Matches on | Exact words / stems | Meaning / semantics |
| Synonyms &amp; paraphrase | Misses | Handles |
| Rare terms, IDs, names | Excellent | Can blur |
| Typos / morphology | Stemming helps | Robust |
| Interpretability | "these words matched" | Opaque geometry |
| Cost | Cheap, no model | Needs an embedding model |
| Classic failure | "car" != "automobile" | ranks vibe over the exact keyword |

</div>

<!--
Sparse is a very smart Ctrl-F: great on exact terms, but blind to synonyms. Dense matches meaning: great on paraphrase, but can blur rare identifiers. Because they fail in opposite ways, combining them beats either alone.
-->

---

## Hybrid = the best of both, with one knob

<style scoped>
  section .statement {
    font-size: 1.15em;
    color: var(--tranquil-velvet);
    font-weight: bold;
    margin: 0 auto 0.8em auto;
    width: 84%;
  }
</style>

<div class="statement">
Run both searches, normalize each to 0..1, then blend.
</div>

<div class="flow-diagram">
<pre>
final_score  =  alpha * dense_score  +  (1 - alpha) * sparse_score

   alpha = 1.0   ->  pure meaning   (semantic only)
   alpha = 0.0   ->  pure keywords  (lexical only)
   alpha = 0.65  ->  the shipped default
</pre>
</div>

<!--
Alpha is the single tunable balance between semantic and lexical. The shipped default leans semantic while keeping keyword precision. It's exposed per-conversation in the UI.
-->

---

<style scoped>
  section .recap-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.2rem;
    width: 94%;
    margin: 0 auto;
    align-items: stretch;
  }
  section .recap-block {
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    min-height: 300px;
    padding: 20px;
    text-align: left;
  }
  section .recap-block h2 { font-size: 1em; margin: 0 0 0.5em 0; color: var(--tranquil-velvet); }
  section .recap-block p { font-size: 0.74em; line-height: 1.3; }
</style>

## Why you need a reranker

<div class="recap-grid">
<div class="recap-block">

## Bi-encoder — retrieval (fast)

<p>Encodes the query and each chunk <strong>separately</strong>. Chunk vectors are precomputed once and stored in FAISS — that's what makes search fast and scalable.</p>
<p>But the query and the passage never "meet", so subtle relevance is lost.</p>

</div>
<div class="recap-block">

## Cross-encoder — rerank (precise)

<p>Feeds the query and a candidate passage through the model <strong>together</strong>, so every query word attends to every passage word.</p>
<p>Far more accurate — but far too slow to run over the whole corpus.</p>

</div>
</div>

<!--
Hybrid merge combines two scores that were each computed independently of the other. Neither stage ever looked at the query and a passage together. That is exactly what the cross-encoder does — and it decides which passages reach the LLM.
-->

---

## Retrieve wide, rerank narrow

<div class="flow-diagram">
<pre>
query
  |
  v
Hybrid retrieve   top_k x candidate_multiplier      (e.g. 50 x 3 = 150)
  |   cheap: bi-encoder + BM25
  v
Cross-encoder re-scores all 150 (query, passage) pairs
  |   expensive, but only on the finalists
  v
Return the TRUE top-k   (best 50)   -->   LLM
</pre>
</div>

<div class="smaller-content" style="margin-top: 0.8em;">
Then <strong>context pruning</strong> keeps the highest-ranked chunks that fit a token budget
(default 60% of the model's context window, discovered live from LM Studio).
</div>

<!--
Retrieve a wide candidate pool cheaply, then spend the expensive cross-encoder pass only on the finalists. Reranking is opt-in via config; the UI also exposes a per-chat toggle. The model is only ever as good as the evidence you hand it.
-->

---

# 5 · Under the Hood

&nbsp;

---

<style scoped>
  section .runtime-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.8rem 1.2rem;
    width: 94%;
    margin: 0 auto;
    text-align: left;
  }
  section .runtime-item { border-left: 4px solid var(--cta-green); padding-left: 0.7rem; }
  section .runtime-item h2 { font-size: 0.9em; margin: 0 0 0.2em 0; color: var(--tranquil-velvet); }
  section .runtime-item p { font-size: 0.68em; line-height: 1.25; margin: 0; }
</style>

## The LLM layer — a tool-calling agent

<div class="runtime-grid">
<div class="runtime-item">

## Local &amp; model-agnostic

<p>Talks to LM Studio over its OpenAI-compatible API. Any model you load works — the id is passed through verbatim.</p>

</div>
<div class="runtime-item">

## Autonomous search

<p>Given the <code>search_documents</code> tool, the agent decides when to search, what to search for, and when it has enough.</p>

</div>
<div class="runtime-item">

## Grounded &amp; cited

<p>Evidence arrives tagged <code>[citation_key#chunkN]</code>; the model emits a Sources section and is forbidden to invent keys.</p>

</div>
<div class="runtime-item">

## Streaming &amp; cancellable

<p>Answers stream token-by-token; a client disconnect stops model inference mid-flight.</p>

</div>
</div>

<!--
Built on the Strands Agents SDK. A separate lightweight title agent names each conversation from the first exchange.
-->

---

<style scoped>
  section .flow-diagram pre { font-size: 0.5em; line-height: 1.3; }
</style>

## Detailed system map — interfaces &amp; implementations

<div class="flow-diagram">
<pre>
Consumers:  Web UI  ·  MCP server  ·  Python clients  ·  scripts/
                          |
                          v
FastAPI (api/):  chat_completions (SSE) · chats (CRUD) · query (dense/sparse/hybrid)
                 index · citation · info (health/models/corpora) · static
                          |   ensure_healthy() guard + uniform {status,data} envelope
                          v
Core (minirag/):  CorpusManager  -->  Orchestration
                  MiniRagAgent (Strands) · ContextPruner · backend_factory
                          |
                          v
Interfaces  ->  Implementations   (each independently swappable)
   Embeddings       ->  FastText  |  LM Studio
   Storage          ->  SQLite
   DenseRetrieval   ->  FAISS (IndexFlatIP, cosine)
   SparseRetrieval  ->  Tantivy (BM25)
   Reranker         ->  CrossEncoder (sentence-transformers)
   merge_hybrid_results   (pure function)
                          |
                          v
External:  LM Studio  (chat · embeddings · model metadata)
</pre>
</div>

<!--
Everything is programmed against an interface; SQLite / FAISS / Tantivy / cross-encoder / FastText are each just one implementation. Retrieval engines return (chunk_id, score); the orchestration layer resolves those to text and citation keys through SQLite, producing the uniform SearchResult used everywhere.
-->

---

<style scoped>
  section .table-container { width: 94%; }
  section .table-container table { font-size: 0.7em; line-height: 1.05; }
  section .table-container td, section .table-container th { padding: 0.3em 0.45em; }
</style>

## The REST API at a glance

<div class="table-container">

| Method &amp; path | Purpose |
| --- | --- |
| `POST /v1/chat/completions` | The chat endpoint — streams a grounded answer over SSE (status / token / error / done). |
| `… /v1/chats[/{id}]` | Chat persistence (list · create · load · update · delete) + generate-title. |
| `GET /v1/corpora` | List indexed corpora discovered on disk. |
| `GET /v1/models` | Proxy LM Studio's model list (avoids browser CORS). |
| `POST /v1/corpus/{corpus}/query/{dense\|sparse\|hybrid}` | Raw retrieval, no LLM — great for demos &amp; evaluation. |
| `POST` · `DELETE /v1/corpus/{corpus}/index` | Index one document / wipe a corpus. |
| `GET /v1/corpus/{corpus}/citation/{key}` | Full citation metadata for a source. |
| `GET /v1/health` · `/v1/info` · `POST /v1/shutdown` | Lifecycle &amp; introspection. |

</div>

<!--
The split between query/* (pure retrieval) and chat/completions (retrieval + generation) makes MiniRAG easy to demo: show the raw ranked chunks first, then show the LLM turning them into an answer.
-->

---

<style scoped>
  section .layer-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
    width: 96%;
    margin: 0 auto;
    align-items: stretch;
  }
  section .layer-card { border: 1px solid #d1d9e0; border-radius: 6px; background: #f6f8fa; padding: 18px; text-align: left; }
  section .layer-card h2 { font-size: 1em; margin: 0 0 0.5em 0; color: var(--tranquil-velvet); }
  section .layer-card p { font-size: 0.72em; line-height: 1.25; margin: 0.4em 0; }
</style>

## Engineering principles

<div class="layer-grid">
<div class="layer-card">

## Config-driven

<p>Zero hardcoded defaults. Every setting lives in <code>config.yaml</code>, validated by strict Pydantic (extra="forbid").</p>
<p>Bad config? The service refuses to start.</p>

</div>
<div class="layer-card">

## Interfaces everywhere

<p>Storage, dense, sparse, reranker, embeddings are all abstractions.</p>
<p>Swap a backend without touching callers. Multi-corpus isolation built in.</p>

</div>
<div class="layer-card">

## Quality gates

<p>CI runs format, mypy + pyright, bandit, deptry, pip-audit, spell-check, semgrep, and enforces test coverage.</p>

</div>
</div>

<!--
Honest errors: no silent fallbacks, no masked failures. Exceptions bubble up with descriptive messages inside a uniform response envelope.
-->

---

# 6 · Run It

&nbsp;

---

## See it run in ~3 commands

```bash
just init                    # set up env, fetch the FastText model, write config.yaml
just start                   # launch the service  ->  UI at http://127.0.0.1:7001
just md2txt corpus=books     # convert data/input/books/md  ->  txt
just ingest corpus=books     # build the hybrid index
# open the browser, pick a corpus + a model loaded in LM Studio, and chat.
```

<div class="smaller-content" style="margin-top: 1em;">
Prefer the raw retrieval view for a demo? <code>just search corpus=books</code> runs an
interactive search loop, and <code>just evaluate corpus=books</code> scores retrieval
quality against your own Q&amp;A pairs.
</div>

<!--
Three commands to a working, local, grounded chat over your own documents.
-->

---

# Demo

---

# Summary

- Indexes your documents **three ways** — keywords (BM25), meaning (vectors), and a precision reranker
- Searches the **whole** library, but sends only the **best evidence** to the LLM
- Streams a **grounded answer** with citations you can trace to the source
- Runs **100% locally** — no cloud, with fully swappable backends

<!--
The one-slide takeaway.
-->

---

![bg cover](images/slide_graphics/library.png)

<div class="white-text">

github.com/florianbuetow/mini-rag

</div>

# Product

## Register

product

## Users

Developers and technical practitioners running MiniRAG locally on their own
machine. They have indexed one or more private corpora (books on refactoring,
prompting, architecture; personal notes; reference docs) and want a fast,
grounded way to interrogate them without sending anything to the cloud.

Context of use: focused desk work, often alongside an editor or terminal. The
user already understands retrieval concepts (lexical vs. semantic, reranking,
top-k) and expects to see and tune them. The primary job on any screen is the
same — ask a question, get a trustworthy answer grounded in their own documents,
and be able to verify where it came from.

## Product Purpose

A local, no-cloud chat interface over MiniRAG's hybrid (lexical + vector) search.
It lets a user converse with their indexed corpus: the agent decides when to
search, retrieves the most relevant chunks, and writes a grounded answer with
inline citations back to the source documents.

It exists because raw search results aren't an answer and a full corpus won't fit
in a model's context. MiniRAG searches the whole index but places only the
selected evidence in the prompt, keeping large collections usable. The chat UI is
the human surface for that loop: pick a corpus and model, tune retrieval, ask,
read a cited answer, and keep the conversation.

Success looks like: the user trusts the answer because they can see the citations
and the search mode behind it; retrieval is fast; and the interface never gets in
the way of reading documents and answers. When evidence can't fit safely, the
system fails honestly rather than silently dropping context — the UI should
reflect that same honesty.

## Brand Personality

Developer-native and precise. Built by and for engineers, with the quiet
confidence of a tool that does one thing well and shows its work.

- Voice: direct, technical, no marketing gloss. Names things accurately
  (corpus, hybrid, alpha, rerank) rather than dumbing them down.
- Tone: calm and matter-of-fact. Informative under load (streaming status,
  errors) without drama.
- Three words: precise, local-first, unobtrusive.
- Emotional goal: trust and control. The user should feel the tool is fast,
  honest about what it did, and entirely theirs.

## Anti-references

_Inferred from the register, personality, and current code — confirm or correct._

- **Consumer-chat cutesiness.** No oversized rounded speech bubbles, emoji-led
  affordances, mascots, or playful onboarding. This is an instrument, not an
  assistant persona.
- **Marketing-page visual language.** No decorative gradients, glassmorphism,
  gradient text, hero-metric blocks, or "AI slop" flourishes. Restraint reads as
  competence here.
- **Hidden retrieval mechanics.** Never bury citations, search mode, alpha, or
  status behind a "clean" minimal veneer. For this audience, visible mechanics
  are a feature, not clutter — a polished surface must not cost transparency.
- **Generic look-alike by default.** The current UI borrows heavily from a
  well-known consumer chat product. Familiarity is fine as a baseline, but the
  tool should not feel like an uncredited clone; small, deliberate choices should
  signal it is its own local-first instrument.

## Design Principles

1. **Retrieval is the product — make it legible.** Citations, search mode, and
   live status are first-class. An answer the user can't trace isn't finished.
2. **The tool disappears.** Chrome stays quiet so the documents and the answer
   carry the screen. Decoration that competes with content is a regression.
3. **Power without clutter.** Expose real retrieval controls (mode, alpha,
   top-k, reranking) to those who want them, tucked away for those who don't.
   Depth on demand, calm by default.
4. **Local-first honesty.** Fast, offline, and truthful about what happened.
   Surface failures plainly (e.g. evidence too large to fit) instead of degrading
   silently. Trust is earned by showing the work.
5. **Precise over playful.** Every element earns its place. Prefer the exact word
   and the restrained choice over the friendly-but-vague one.

## Accessibility & Inclusion

Target bar: solid, verified defaults (not formal certification).

- **Contrast:** WCAG AA — body text ≥ 4.5:1, large/bold text ≥ 3:1, in both dark
  and light themes. Placeholder and muted text held to the same body threshold.
- **Keyboard:** Every interactive control (new chat, rename/delete, selectors,
  settings, send, export, theme) reachable and operable by keyboard, with a
  logical focus order.
- **Focus visibility:** Clear, non-color-only focus indicators on all controls.
- **Motion:** Honor `prefers-reduced-motion: reduce` — every animation needs a
  reduced or instant alternative.
- **Semantics:** Meaningful labels on icon-only controls and live regions for
  streaming/status updates so assistive tech announces progress and errors.

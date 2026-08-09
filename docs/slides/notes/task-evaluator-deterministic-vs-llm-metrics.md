# Task Evaluator: Deterministic vs Non-Deterministic Metrics

Note for later. Which metrics the task evaluator computes deterministically (rule-based, no LLM) versus which come from the LLM judge.

Sources: `.kamino/evals/scripts/evaluate_task.py` and `.claude/agents/task-evaluator.md`.

## Deterministic metrics (computed by `evaluate_task.py`, rule-based, no LLM)

### Objective text metrics
- character count, word count, sentence count
- estimated token count (chars ÷ 4)
- syllable count, average sentence words
- Flesch reading ease
- Flesch-Kincaid grade level

### Structural indicator counts (keyword / pattern matching)
- bullet count
- explicit requirement count
- constraint indicator count
- success criteria indicator count
- input/output indicator count
- vague term count
- contradiction indicator count
- tool indicator count
- domain indicator count

### Heuristic scores derived from those metrics by fixed rules (still deterministic)
- clarity, ambiguity, consistency, completeness, difficulty (each 1–5)
- task type classification
- recommended mapping
- open issues

## Non-deterministic part (produced by the `task-llm-judge` subagent, semantic / LLM reasoning)
- LLM-judged scores for the same six dimensions — clarity, ambiguity, consistency, completeness, difficulty, and task type — plus a rationale.

## Key points
- The **same six dimensions are scored twice**: once deterministically by the script's rules, once semantically by the LLM judge. The evaluator then merges both and flags any disagreement between them.
- One nuance: the script's "difficulty" score is its **own rule-based estimate** — it is **not** the Bradley-Terry pairwise difficulty ranking, which is a separate component (the difficulty ranker).

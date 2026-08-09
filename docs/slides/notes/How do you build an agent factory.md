# Chat Export

### User

How do you build an agent factory?

---

### Assistant

An agent factory is a system that produces specialized agents from reusable templates rather than hand-crafting every agent.

The core idea is:

```
Problem   ↓Agent Selection   ↓Template Instantiation   ↓Capability Wiring   ↓Validation   ↓Runnable Agent
```

### 1. Agent Templates

Create parameterized templates instead of agents.

Example:

```
name: code-reviewervariables:  - repository  - programming_languagesystem_prompt: \|  You are a code reviewer for {{programming_language}}.  Review code from {{repository}}.tools:  - search_code  - read_filesuccess_criteria:  - Security issues identified  - Maintainability concerns identified
```

Think of templates as classes and agents as objects.

---

### 2. Agent Registry

Store templates in a catalog.

```
agents/├── code-reviewer.md├── bug-investigator.md├── article-writer.md├── search-engineer.md└── release-manager.md
```

Each template contains:

- purpose
- required variables
- tools
- model requirements
- cost profile
- expected outputs

---

### 3. Agent Selection Layer

Given a task:

> "Review my Rust project for concurrency bugs"

The factory ranks templates.

```
bug-investigator     0.95code-reviewer        0.88release-manager      0.11
```

Selection methods:

1. Rule-based
2. Embedding similarity
3. LLM ranking
4. Hybrid

Most factories use hybrid.

---

### 4. Variable Extraction

Determine required parameters.

Template:

```
required:  - repository  - language
```

Task:

```
Review github.com/foo/bar for Rust concurrency issues.
```

Extraction:

```
repository: github.com/foo/barlanguage: rust
```

Missing variables trigger clarification or lookup.

---

### 5. Context Assembly

Build the context package.

Combine:

- template
- user request
- documentation
- project files
- memories
- previous runs

Result:

```
System Prompt+Tool Definitions+Knowledge Files+Task
```

---

### 6. Tool Wiring

Attach only necessary tools.

Example:

```
article-writer:  - web_search  - markdown_writercode-reviewer:  - git  - grep  - file_readerdeployment-agent:  - kubectl  - terraform
```

Tool minimization improves reliability.

---

### 7. Model Selection

Factory chooses a model.

Example policy:

```
simple:  model: smallanalysis:  model: mediumarchitecture:  model: large
```

Or:

```
article-writer:  claudecode-reviewer:  gptcoding-agent:  codex
```

The agent creator should not hardcode a model.

---

### 8. Agent Generation

Generate final agent specification.

Example:

```
agent:  name: rust-concurrency-reviewermodel: claudetools:  - git  - read_filecontext:  - repository docsprompt:  specialized instructions
```

This artifact becomes executable.

---

### 9. Validation

Before releasing:

#### Template validation

Variables resolved?

```
{{repository}}
```

remaining → fail.

#### Tool validation

All required tools available?

#### Prompt validation

Token limits respected?

#### Safety validation

No forbidden tools?

---

### 10. Evaluation

Run benchmark tasks.

Example:

```
task:  find race conditionexpected:  identify lock ordering bug
```

Measure:

- success rate
- latency
- token cost
- tool calls
- hallucinations

---

### 11. Self-Improvement Layer

Factories become powerful when they generate new templates.

Process:

```
Agent runs    ↓Observe failures    ↓Generate improved template    ↓Evaluate    ↓Promote if better
```

This is similar to evolutionary optimization.

---

### Minimal Architecture

```
Task  ↓Router  ↓Template Registry  ↓Variable Extractor  ↓Context Builder  ↓Tool Binder  ↓Model Selector  ↓Validator  ↓Runnable Agent
```

The mistake most people make is building agents.

The scalable approach is building:

1. Templates
2. Selection mechanisms
3. Validation mechanisms

Once those exist, creating a new agent becomes mostly a data problem rather than an engineering problem.

---

### Assistant

This is where most discussions become hand-wavy. Every metric requires:

```
Metric→ Ground truth→ Measurement procedure→ Collection point→ Storage→ Aggregation
```

Without ground truth, most metrics are meaningless.

# 1. Agent Selection Accuracy

Question:

```
Did the factory choose the best agent?
```

Ground truth:

Create an evaluation dataset.

```
task: Find deadlocks in Rust codeagents:  rust-reviewer: 95  security-reviewer: 20  article-writer: 0
```

Scores are obtained by actually running all candidate agents and evaluating outputs.

Measurement:

```
selection_accuracy =correct_selections / total_tasks
```

Collection point:

Immediately after execution and evaluation.

Storage:

```
task_id:selected_agent:best_agent:correct: true\|false
```

---

# 2. Agent Success Rate

Question:

```
Did the selected agent accomplish the task?
```

Ground truth depends on task type.

Examples:

## Coding

Ground truth:

```
Unit testsIntegration testsLintingType checking
```

Success:

```
All tests pass
```

---

## Search

Ground truth:

Human-labelled relevant documents.

Success:

```
nDCGMRRRecall@KPrecision@K
```

---

## Extraction

Ground truth:

Annotated dataset.

Success:

```
PrecisionRecallF1
```

---

## Writing

Ground truth:

Human evaluation or rubric.

Success:

```
score > threshold
```

Storage:

```
task_id:evaluation_score:pass: true
```

---

# 3. Context Retrieval Quality

Question:

```
Did we retrieve the right information?
```

Ground truth:

Human labels.

Example:

```
query:relevant_docs:  - doc1  - doc7  - doc13
```

Retrieved:

```
retrieved:  - doc7  - doc13  - doc22
```

Compute:

```
Recall = 2/3Precision = 2/3
```

Collection point:

Immediately after retrieval.

Storage:

```
query:retrieved_docs:relevant_docs:
```

---

# 4. Context Utilization

Question:

```
Did the agent use retrieved context?
```

Method:

Track citations.

Example:

```
Retrieved:  doc1  doc2  doc3Used:  doc2
```

Metric:

```
utilization =used_docs / retrieved_docs
```

Collection:

During generation.

Requires:

- citation system
- attribution system
- trace analysis

---

# 5. Tool Selection Quality

Question:

```
Were the right tools exposed?
```

Ground truth:

Run evaluation set.

Example:

```
task:  deploy kubernetes servicerequired_tools:  kubectl
```

Metric:

```
tool_selection_recalltool_selection_precision
```

Collection:

Before execution.

Storage:

```
available_tools:selected_tools:required_tools:
```

---

# 6. Tool Success Rate

Question:

```
Did tools work?
```

Metric:

```
successful_calls / total_calls
```

Log:

```
tool:arguments:success:latency:
```

Collection:

Every tool invocation.

---

# 7. Model Routing Quality

Question:

```
Did we choose the right model?
```

Ground truth:

Offline evaluation.

Run:

```
Task→ GPT→ Claude→ Gemini→ Small model
```

Evaluate all.

Metric:

```
chosen_model_score /best_possible_score
```

Sometimes called:

```
regret
```

Example:

```
Best score = 95Chosen score = 90Regret = 5
```

---

# 8. Cost Efficiency

Question:

```
How much did success cost?
```

Metric:

```
cost_per_success =total_cost / successful_tasks
```

Collection:

Every execution.

Store:

```
tokens:model_cost:tool_cost:
```

---

# 9. Failure Attribution

Question:

```
Why did the task fail?
```

This usually requires a failure classifier.

Input:

```
TaskRetrieved ContextToolsOutputEvaluation
```

Output:

```
failure_type:  retrieval
```

or

```
failure_type:  wrong_agent
```

or

```
failure_type:  tool_failure
```

Storage:

```
failure_reason:confidence:
```

---

# 10. Factory-Level Metric

The most important one.

For every task:

```
task:selected_agent:selected_model:selected_tools:retrieved_context:output:evaluation:cost:latency:
```

This becomes a giant table.

Then you can ask:

```
Which agent fails most?Which retrieval strategy works best?Which model has lowest cost per success?Which tools cause failures?Which context sources correlate with success?
```

This table is the equivalent of click logs in a search engine.

---

# The mature approach

A mature agent factory eventually creates three datasets:

### Routing Dataset

```
Task → Best AgentTask → Best ModelTask → Best Tools
```

Used to improve selection.

### Retrieval Dataset

```
Task → Relevant Context
```

Used to improve retrieval.

### Evaluation Dataset

```
Task → Expected Outcome
```

Used to measure success.

Once you have these three datasets, improving the factory becomes a data science problem: train better rankers, routers, retrievers, and evaluators using execution logs and evaluation outcomes. Without them, most "agent optimization" is guesswork.


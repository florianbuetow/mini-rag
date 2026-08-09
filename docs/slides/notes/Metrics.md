### User

Sorry I want the complete overview of metrics to collect in bullet points and then I want to know how to use these metrics to compute things like success etc

---

### Assistant

# Raw Metrics to Collect

## Task Metrics

- Task ID
- Task type
- Task category
- User request
- Extracted intent
- Extracted entities
- Extracted variables
- Missing variables
- Clarification requests
- Ground truth available (yes/no)

---

## Agent Selection Metrics

- Selected agent
- Candidate agents
- Ranking score per candidate
- Selection confidence
- Agent version
- Template version

---

## Model Selection Metrics

- Selected model
- Candidate models
- Estimated task difficulty
- Estimated cost
- Estimated latency

---

## Context Retrieval Metrics

Per retrieval step:

- Query
- Retrieval method
- Retrieved document IDs
- Retrieval scores
- Number of documents retrieved
- Number of chunks retrieved
- Context token count
- Source type (files, web, memory, database)

---

## Context Usage Metrics

Per document/chunk:

- Retrieved
- Included in prompt
- Referenced by agent
- Referenced in final answer
- Number of references
- Number of tokens consumed

---

## Tool Metrics

Per tool call:

- Tool name
- Tool version
- Input size
- Output size
- Start timestamp
- End timestamp
- Duration
- Success/failure
- Error type
- Retry count

---

## Agent Execution Metrics

- Agent start time
- Agent end time
- Agent duration
- Number of reasoning steps
- Number of tool calls
- Number of retrieval calls
- Number of retries
- Number of failures
- Maximum context size used

---

## Token Metrics

Per model invocation:

- Input tokens
- Output tokens
- Cached input tokens
- Cache hit/miss
- Prompt token count
- Context token count

---

## Cost Metrics

Per invocation:

- Model cost
- Retrieval cost
- Tool cost
- Storage cost
- Total cost

---

## Latency Metrics

- Retrieval latency
- Tool latency
- Model latency
- Evaluation latency
- End-to-end latency

---

## Evaluation Metrics

Per task:

- Expected outcome
- Actual outcome
- Pass/fail
- Human score
- Judge score
- Confidence score

---

## Failure Metrics

- Failure occurred
- Failure stage
- Failure category
- Failure severity
- Root cause

Example categories:

```
wrong_agentwrong_modelwrong_toolbad_retrievalmissing_contexthallucinationtool_errortimeoutformat_errorevaluation_error
```

---

# Derived Metrics

These are computed from raw metrics.

---

## Agent Success Rate

Raw:

```
task_idpass/fail
```

Formula:

```
success_rate =successful_tasks / total_tasks
```

Example:

```
95 successes100 tasks95%
```

---

## Agent Selection Accuracy

Need an evaluation set where the best agent is known.

Raw:

```
selected_agentbest_agent
```

Formula:

```
selection_accuracy =correct_selections / total_tasks
```

Example:

```
selected = rust-reviewerbest = rust-reviewercorrect
```

---

## Retrieval Precision

Raw:

```
retrieved_docsrelevant_docs
```

Formula:

```
precision =relevant_retrieved /total_retrieved
```

Example:

```
retrieved = 10relevant = 7precision = 70%
```

---

## Retrieval Recall

Formula:

```
recall =relevant_retrieved /all_relevant_docs
```

Example:

```
all relevant = 20retrieved relevant = 10recall = 50%
```

---

## Context Utilization

Raw:

```
retrieved_docsused_docs
```

Formula:

```
utilization =used_docs /retrieved_docs
```

Example:

```
100 retrieved20 used20%
```

---

## Tool Success Rate

Formula:

```
successful_calls /all_calls
```

Example:

```
980 / 100098%
```

---

## Tool Necessity

Formula:

```
tasks_using_tool /tasks_exposing_tool
```

Example:

```
tool exposed 100 timesused 20 times20%
```

Low values often indicate overexposure.

---

## Cost Per Success

Formula:

```
total_cost /successful_tasks
```

Example:

```
$10050 successful tasks$2 per success
```

---

## Latency Per Success

Formula:

```
sum(latency_successes) /successful_tasks
```

Useful because failed tasks often terminate early.

---

## Failure Rate

Formula:

```
failed_tasks /total_tasks
```

---

## Failure Distribution

Formula:

```
failure_type_count /all_failures
```

Example:

```
retrieval: 40%tool: 30%hallucination: 20%other: 10%
```

This tells you where engineering effort should go.

---

## Model Routing Quality

Need offline evaluation.

Raw:

```
chosen_model_scorebest_model_score
```

Formula:

```
routing_regret =best_score -chosen_score
```

Example:

```
best = 95chosen = 92regret = 3
```

Lower is better.

---

## Cost Efficiency

Formula:

```
success_rate /cost
```

or

```
successful_tasks /dollar
```

Example:

```
200 successful tasks$504 successes per dollar
```

---

## Agent Efficiency

Formula:

```
success_rate /(avg_cost × avg_latency)
```

Very useful when comparing agents.

---

# What Actually Matters

In practice, most mature factories end up optimizing around:

1. Success Rate
2. Cost Per Success
3. End-to-End Latency
4. Retrieval Precision
5. Retrieval Recall
6. Agent Selection Accuracy
7. Failure Distribution
8. Human Correction Rate

Everything else is usually diagnostic data used to explain movement in those eight metrics. The equivalent of an agent factory's "north star metric" is usually:

```
Useful Task Completions-----------------------Cost × Latency
```

subject to an acceptable quality threshold.

---

### User

What can you tell me about expected challenges building an agent factory based on these principles?

---

### Assistant

The biggest surprise is that most challenges are not agent problems. They are evaluation, retrieval, and data problems.

# 1. No Ground Truth

You cannot improve what you cannot measure.

Example:

```
Write a blog postAnalyze this architectureReview this codebase
```

What does "good" mean?

Without:

- golden datasets
- expected outputs
- test suites
- evaluation rubrics

you cannot compute success rate, selection accuracy, or routing quality.

This is usually the first bottleneck.

---

# 2. Sparse Evaluation Data

Suppose you have:

```
100 agent templates
```

and

```
10,000 tasks
```

Most task-agent combinations are never observed.

You know:

```
Agent A succeeded
```

You do not know:

```
Would Agent B have done better?
```

This makes agent selection accuracy difficult to measure.

---

# 3. Counterfactual Explosion

To know whether routing was optimal:

```
Task→ Run every agent→ Run every model→ Run every retrieval strategy
```

This is often 10x–1000x more expensive than production.

You therefore get:

```
observed performance
```

instead of

```
best possible performance
```

---

# 4. Retrieval Dominates Everything

Most failures look like:

```
bad reasoning
```

but are actually:

```
missing information
```

Example:

```
Wrong answer
```

because:

```
Relevant document never retrieved
```

Improving retrieval often produces larger gains than improving prompts.

---

# 5. Context Quality Is Hard To Measure

You can measure:

```
document retrieved
```

You cannot easily measure:

```
document helpful
```

or

```
document harmful
```

A retrieved document may:

- improve the answer
- distract the model
- increase latency
- cause hallucinations

Simple precision/recall does not fully capture this.

---

# 6. Agent Boundaries Drift

Initially:

```
Code ReviewerSecurity ReviewerArchitecture Reviewer
```

Later:

```
All three perform similar tasks.
```

You accumulate overlapping agents.

Questions emerge:

```
Should these be merged?Should routing decide?Should one become a specialization?
```

Agent catalogs tend to grow uncontrollably.

---

# 7. Tool Proliferation

Every new tool increases:

```
selection complexity
```

Example:

```
10 tools
```

vs

```
100 tools
```

The routing problem becomes much harder.

You eventually need:

- tool metadata
- capability taxonomy
- tool rankings

Very similar to service discovery.

---

# 8. Prompt Versioning Becomes Impossible

Over time:

```
Agent v1Agent v2Agent v3Agent v17
```

Question:

```
Did v17 improve?
```

Without controlled evaluations you do not know.

Many factories accumulate prompt debt.

---

# 9. Success Is Often Multi-Dimensional

Consider:

```
Success
```

What does it mean?

Could mean:

- correctness
- latency
- cost
- completeness
- safety
- user satisfaction

Often these conflict.

Example:

```
Best answer
```

may also be:

```
Most expensive answer
```

---

# 10. Failure Attribution Is Difficult

Suppose task fails.

Possible causes:

```
wrong agentwrong modelbad retrievalbad prompttool failurehallucination
```

The final failure looks identical:

```
bad answer
```

Determining root cause is often the hardest analytics problem.

---

# 11. Feedback Loops

Factories frequently optimize for what they can measure.

Example:

```
Optimize latency
```

Result:

```
Less retrievalSmaller contextWorse answers
```

Or:

```
Optimize judge score
```

Result:

```
Agents learn to satisfy the judgerather than the user
```

Classic reward hacking.

---

# 12. Cold Start

Initially you have:

```
No logsNo evaluationsNo routing data
```

Yet routing requires data.

You must bootstrap with:

- rules
- heuristics
- human labels
- synthetic tasks

The first months are usually data collection.

---

# 13. Long-Tail Tasks

You'll discover:

```
80% of tasks
```

fit a handful of templates.

Remaining:

```
20%
```

are unique.

Examples:

```
Debug this Kubernetes outageReview this legal contractAnalyze this acquisition target
```

Creating a dedicated agent for every niche task does not scale.

---

# 14. Agent Factory Becomes a Search Engine

Eventually the architecture resembles:

```
Task→ Retrieval→ Ranking→ Selection→ Execution→ Evaluation
```

Challenges become:

- ranking quality
- retrieval quality
- evaluation quality
- feedback quality

rather than prompt engineering.

---

# 15. The Biggest Risk

Many teams build:

```
Agent Factory
```

before building:

```
Evaluation Factory
```

The result is dozens of agents and no way to know:

- which are useful
- which are redundant
- which improved
- which regressed

The first system to build is usually not the agent factory itself, but the infrastructure that can measure agent quality, compare alternatives, and generate reliable feedback signals. Once that exists, improving the factory becomes an optimization problem rather than guesswork.

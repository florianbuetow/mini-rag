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

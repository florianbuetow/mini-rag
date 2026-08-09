---
marp: true
theme: xebia-theme
paginate: true
---

![bg cover](images/slide_graphics/kamino451.png)

---

<style scoped>
  section .quote-block { font-size: 0.7em; }

  /* Badge image — edit the values below:
       translate( RIGHT% , DOWN% )   moves it right and down
       scale( 1.3 )                  sizes it (1.3 = +30%) */
  section .column img {
    transform: translate(10%, 4%) scale(1.0);
  }
</style>

<div class="columns" style="align-items: center; width: 100%;">
<div class="column" style="justify-content: center; min-width: 0; overflow: hidden;">

# How to Build an Agent Factory
by Florian Buetow

<br/>

<div class="quote-block">

> Kamino? I'm not familiar with it. Is it in the Republic?

— Obi-Wan Kenobi

> No, no. It's beyond the Outer Rim. I'd say about, twelve parsecs outside the Rishi Maze.

— Dexter Jettster

</div>
<br/>
<div class="smaller-content">Source: Star Wars - Episode II - Attack of the Clones</div>
</div>
<div class="column" style="align-items: center; justify-content: center; text-align: center; min-width: 0;">
<br/>
<img src="images/slide_graphics/kamino451-badge.png" style="max-width: 100%; height: auto;">

</div>
</div>

---

<style scoped>
  section .quote-block2 {
    font-weight: bold;
  }
  section .quote-block2 li {
    color: var(--dark);
  }

</style>
# Table of Contents

<div class="quote-block2">

1. What is an Agent Factory?
2. Key Concepts and Challenges
3. Kamino451 
4. Scaling to Production
5. Summary

</div>

---

# What is an Agent Factory?

&nbsp;

<!--
A system to design, evaluate, and deploy agents.

An agent factory is not just an agent and not just a prompt. It is the repeatable system that turns a task into a runnable agent by selecting the right template, preparing the right context, wiring the right tools, and validating that the result can actually be used.
-->

---

## What an Agent Factory Does

<style scoped>
  section .flow-block {
    width: max-content;
    max-width: 90%;
    margin: 0 auto;
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    padding: 22px 28px;
    text-align: left;
  }

  section .flow-block pre {
    background: transparent;
    border: 0;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 1em;
    line-height: 1.18;
    margin: 0;
    padding: 0;
    white-space: pre;
  }
</style>

<div class="flow-block">

<pre>
Task
  ↓
Agent Selection
  ↓
Context + Tooling
  ↓
Validation
  ↓
Runnable Agent
</pre>
</div>
<!--
At the simplest level, an agent factory takes a task, evaluates what kind of agent is needed, prepares that agent for the task, and returns a runnable agent. The important shift is that agent creation becomes an explicit pipeline instead of an improvised prompt.
-->

---

## But Why Not Just Launch an Agent?

<div class="cc-screen">
<pre class="cc-welcome"><span class="cc-logo"> ▐▛███▜▌</span>   <span class="cc-title">Claude Code</span> <span class="cc-dim">v2.1.185</span>
<span class="cc-logo">▝▜█████▛▘</span>  <span class="cc-dim">Mythos with xhigh effort · Claude Max </span>
<span class="cc-logo">  ▘▘ ▝▝</span>    <span class="cc-dim">~/Developer/github/kamino451</span>
<br/>
<div>&gt; Launch a read-only security-review subagent to audit
the current changes and return only prioritized findings
with severity, file:line, and suggested fixes.
</div>
</pre>
</div>


<!--
That works for a demo.

But what happens when we need to do this 100 times?

What if we want to do this with Codex?


In tools like Claude Code or Codex, we can already ask for a specialized agent to do a specific task. That is powerful, and for a single task it can be enough. The question is what happens when this becomes part of a real delivery process with many agents, many repositories, repeated runs, and quality expectations.
-->

---

## From Prompts to Agent Factories

<center>

| One-off Prompt | Markdown Agent | Agent Factory |
| --- | --- | --- |
| Human/parent asks for it | Invoked by name or description | Router/policy selects a definition |
| Different each time | Static agent definition | Managed agent matching  |
| Current conversation is context | Agent file + invocation context | Context package assembled per run |
| Capabilities are ad hoc | Tools/model/permissions configured or inherited | Capabilities selected and validated |
| No quality control | "Agent works well" | Traces and evals measure quality |
| Improved by prompt tweaks | Improved by editing the definition | Improved via templates, routing, evals |

</center>
<!--
This contrast is deliberately about lifecycle, not whether a Markdown agent is a real runtime agent. Claude Code subagents are runtime agents and can be configured with tools, model, permissions, hooks, memory, isolation, and more. The agent factory is our architecture concept: the lifecycle around agent definitions that selects, configures, validates, executes, measures, and improves agent runs.
-->

---

<style scoped>
  section .flow-block {
    width: max-content;
    max-width: 90%;
    margin: 0 auto;
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    padding: 22px 28px;
    text-align: left;
  }

  section .flow-block pre {
    background: transparent;
    border: 0;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 1em;
    line-height: 1.18;
    margin: 0;
    padding: 0;
    white-space: pre;
  }
</style>

## Software Factory vs Agent Factory vs Agents

<div class="flow-block">
<pre>
Software Factory
  builds and ships software
        |
        | needs reliable agents
        v
Agent Factory
  builds and ships agents
        |
        | produces
        v
Agents + Agent Workflows
</pre>
</div>

<!--
A software factory turns requirements into running software. But once agents participate in that factory, we need a repeatable way to create, evaluate, deploy, and improve those agents. The agent factory becomes a key component of the software factory.
-->

---

<style scoped>
  section .recap-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.2rem;
    width: 100%;
    align-items: stretch;
  }

  section .recap-block {
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    box-sizing: border-box;
    min-height: 340px;
    padding: 18px;
    text-align: left;
  }

  section .recap-block pre {
    background: transparent;
    border: 0;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 1em;
    line-height: 1.22;
    margin: 0;
    padding: 0;
    white-space: pre-wrap;
  }
</style>

## What an Agent Factory Does (v2)

<div class="recap-grid">
<div class="recap-block">
<pre>
Task
  ↓
Agent Selection
  ↓
Context + Tooling
  ↓
Validation
  ↓
Runnable Agent
</pre>
</div>
<div class="recap-block">
<pre>
Estimate task complexity
  ↓
Match task to agent + model
Create new agents on the fly
  ↓
Assemble context
Bind tools and models
  ↓
Compile the agent
  ↓
Observe, Evaluate, Improve
</pre>
</div>
</div>

<!--
The recap is that an agent factory is both a pipeline and a control system. It produces runnable agents, but it also estimates the task, routes work, assembles context, binds tools and models, tracks quality, records failures, and feeds those results back into better templates.
-->

---

# Key Concepts and Challenges

&nbsp;

---

<style scoped>
  section .layer-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
    width: 100%;
    align-items: stretch;
  }

  section .layer-card {
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    background: #f6f8fa;
    padding: 20px;
    text-align: left;
  }

  section .layer-card h2 {
    font-size: 1.1em;
    margin: 0 0 0.5em 0;
    color: var(--tranquil-velvet);
  }

  section .layer-card p {
    font-size: 0.75em;
    line-height: 1.25;
    margin: 0.4em 0;
  }
</style>

# Three Layers of an Agent Factory

<div class="layer-grid">
<div class="layer-card">

## Blueprints

<p>Defines what kinds of agents can exist.</p>

<p>Templates and registries make agent creation reusable instead of improvised.</p>

</div>
<div class="layer-card">

## Compilation

<p>Turn a concrete task into a runnable agent.</p>

<p>The factory evaluates the task, selects an agent, model, builds context, and binds capabilities.</p>

</div>
<div class="layer-card">

## Feedback Loops

<p>Evaluate tasks, agent-model performance and analyze errors.</p>

<p>Evaluation and training close the loop between agent behavior and templates.</p>

</div>
</div>

<!--
This section is about the components that make an agent factory more than a collection of agents. The simple model is three layers: design-time definitions, run-time assembly, and the learning loop that improves future runs.
-->

---

<style scoped>
  section .component-list {
    width: 86%;
    margin: 0 auto;
    text-align: left;
  }

  section .component-list li {
    margin-bottom: 0.8em;
    line-height: 1.25;
  }

  section .component-list strong {
    color: var(--tranquil-velvet);
  }

  section .challenge {
    margin-top: 1.4em;
    font-size: 0.8em;
    color: var(--dark-grey);
    text-align: center;
  }
</style>

## Layer 1: Blueprints

<div class="component-list">

- **Agent templates** act as contracts: they describe roles, inputs, outputs, constraints, success criteria, and capability needs.
- **Agent registry** stores those templates so the factory can discover, version, compare, and reuse them.

<br/>
This allows the creation of specialized agents and agent blueprints without turning them into static and brittle prompts.
</div>



<!--
Templates (static vs dynamic)

At design time we are not launching agents yet. We are defining the raw material the factory can use later. Templates are contracts for possible workers: what they need, what they can do, what they should produce, and how we know they succeeded. The registry makes those templates discoverable and governable.
-->

---

<style scoped>
  section .recap-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.2rem;
    width: 100%;
    align-items: stretch;
  }

  section .recap-block {
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    box-sizing: border-box;
    min-height: 340px;
    padding: 18px;
    text-align: left;
  }

  section .recap-block pre {
    background: transparent;
    border: 0;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6em;
    line-height: 1.22;
    margin: 0;
    padding: 0;
    white-space: pre-wrap;
  }
</style>

## Layer 1: Blueprints

<div class="recap-grid">
<div class="recap-block">
<div class="component-list">

- **Agent templates** act as contracts: they describe roles, inputs, outputs, constraints, success criteria, and capability needs.

<br/>
This allows the creation of customised and specialized agents without turning them into static and brittle prompts.
</div>

</div>
<div class="recap-block">
<pre>
---
name: code-reviewer
description: Review changed code for bugs, maintainability issues, and unsafe patterns.
tools: Read, Grep, Glob, Bash
TODO: Update the yaml frontmatter to match the actual .kamino implementation
inputs: ['files']
outputs: ['outputfile']
model: sonnet
---

You are a senior code reviewer.
Inspect only the following files: {{files}}
Focus on correctness, security, readability, and test impact. Be concise and specific and prefer concrete findings over generic advice. Output: Findings, Risks, Suggested fixes in to file {{outputfile}}
</pre>
</div>
</div>

<!--
TODO: This blueprint needs to be reviewed later to match a real agent in .kamino
-->

---

<style scoped>
  section .recap-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.2rem;
    width: 100%;
    align-items: stretch;
  }

  section .recap-block {
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    box-sizing: border-box;
    min-height: 340px;
    padding: 18px;
    text-align: left;
  }

  section .recap-block pre {
    background: transparent;
    border: 0;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6em;
    line-height: 1.22;
    margin: 0;
    padding: 0;
    white-space: pre-wrap;
  }
</style>

## Layer 1: Blueprints

<div class="recap-grid">
<div class="recap-block">
<div class="component-list">

- **Agent registry** stores those templates so the factory can discover, version, compare, and reuse them.

<br/>
The registry allows progressive disclosure of specialized agents and versioning of agents.
</div>

</div>
<div class="recap-block">
<pre>
.kamino
├── agents
│   ├── autoresearch-agent-improver.md
│   ├── autoresearch-eval-author.md
│   ├── autoresearch-llm-evaluator.md
│   ├── autoresearch-program-author.md
│   ├── bradley-terry-pairwise-ranking.md
│   ├── code-reviewer.md
│   ├── pairwise-difficulty-judge.md
│   ├── task-evaluator.md
│   └── task-llm-judge.md
│
└── agent-registry.md
</pre>
</div>
</div>

<!--
TODO: This blueprint needs to be reviewed later to match the real location and name of of agent-registry.md
-->
---

<style scoped>
  section .recap-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.2rem;
    width: 100%;
    align-items: stretch;
  }

  section .recap-block {
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    box-sizing: border-box;
    min-height: 340px;
    padding: 18px;
    text-align: left;
  }

  section .recap-block pre {
    background: transparent;
    border: 0;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6em;
    line-height: 1.22;
    margin: 0;
    padding: 0;
    white-space: pre-wrap;
  }
</style>

## Layer 1: Blueprints

<div class="recap-grid">
<div class="recap-block">
<pre>
.kamino
├── agents
│   ├── autoresearch-agent-improver.md
│   ├── autoresearch-eval-author.md
│   ├── autoresearch-llm-evaluator.md
│   ├── autoresearch-program-author.md
│   ├── bradley-terry-pairwise-ranking.md
│   ├── code-reviewer.md
│   ├── pairwise-difficulty-judge.md
│   ├── task-evaluator.md
│   └── task-llm-judge.md
│
└── agent-registry.md
</pre>
</div>
<div class="recap-block">
<pre>
TODO: show the content of agent-registry.md (cateogization of agents, and progressive disclosure)
</pre>
</div>
</div>

<!--
TODO: This blueprint needs to be reviewed later to match the real location and name of of agent-registry.md
-->

---

<style scoped>
  section .runtime-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.8rem 1.2rem;
    width: 96%;
    margin: 0 auto;
    text-align: left;
  }

  section .runtime-item {
    border-left: 4px solid var(--cta-green);
    padding-left: 0.7rem;
  }

  section .runtime-item h2 {
    font-size: 0.95em;
    margin: 0 0 0.2em 0;
    color: var(--tranquil-velvet);
  }

  section .runtime-item p {
    font-size: 0.7em;
    line-height: 1.2;
    margin: 0;
  }
</style>

## Layer 2: Compilation

<div class="runtime-grid">
<div class="runtime-item">

## Task evaluator

<p>Profiles the task before routing using deterministic metrics and an LLM judge to score clarity, ambiguity, consistency, completeness, difficulty, and task type</p>

</div>
<div class="runtime-item">

## Task difficulty ranker

<p>Places the task on a difficulty scale relative to prior tasks. Pairwise harder-than judgements feed a Bradley-Terry model that yields a difficulty score and the nearest prior tasks.</p>

</div>
<div class="runtime-item">

## Context builder

<p>Assembles the files, docs, memories, examples, and run-specific facts the agent needs.</p>

</div>
<div class="runtime-item">

## Agent router

<p>Selects the template, agent type, or workflow that best fits the evaluated task.</p>

</div>
<div class="runtime-item">

## Agent builder

<p>Instantiates the selected template by filling variables and producing runnable instructions.</p>

</div>
<div class="runtime-item">

## Tool/model binder

<p>Attaches the minimum useful tools, model, effort, permissions, and guardrails for the run.</p>

</div>
</div>

<!--
This is where the factory adapts to the task. The task evaluator decides what kind of problem this is. The router selects a definition. The builder turns that definition into a runnable agent. The context builder and tool/model binder decide what the agent knows and what it can do.
-->

---

<style scoped>
  section .te-grid {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 1.4rem;
    width: 96%;
    margin: 0 auto;
    align-items: start;
    text-align: left;
  }

  section .te-grid pre {
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6em;
    line-height: 1.25;
    margin: 0;
    padding: 16px 18px;
    white-space: pre;
  }

  section .te-grid h3 {
    font-size: 0.85em;
    margin: 0 0 0.3em 0;
    color: var(--tranquil-velvet);
  }

  section .te-grid ul {
    margin: 0 0 0.9em 0;
    padding-left: 1.1em;
  }

  section .te-grid li {
    font-size: 0.66em;
    line-height: 1.3;
  }
</style>

## How the Task Evaluator Works

<div class="te-grid">
<div>
<pre>
Task text
   |
   |-- evaluate_task.py   (objective, rule-based)
   |      length, readability,
   |      structure signals
   |      -> 1-5 scores + mapping
   |
   |-- task-llm-judge     (semantic)
   |      re-scores the same
   |      dimensions + rationale
   |
   v
   merge, handle disagreements
   |
   v
Task evaluation
</pre>
</div>
<div>

### Semantic Scoring (easy, normal, hard)

- clarity
- ambiguity
- consistency
- completeness
- difficulty


### Deterministic Scoring

- length & estimated tokens
- readability (Flesch, grade level)
- structure: requirements, constraints, success criteria, input/output
- vague-term, contradiction, tool & domain counts

### Task classification

- code_generation, research, writing
- multi_step_planning, tool_workflow
- data_extraction, factual_qa
- general_task (fallback)

</div>
</div>

<!--
The task evaluator is hybrid. evaluate_task.py is deterministic: it measures length, Flesch readability, and structural signals (requirements, constraints, success criteria, vague terms, contradictions, tools), then derives 1-5 scores, a task type, and a recommended mapping by fixed rules. task-llm-judge re-scores the same dimensions semantically. The evaluator merges both and flags any disagreement. It does not call the difficulty ranker.
-->

---

<style scoped>
  section .bt-model {
    width: max-content;
    max-width: 92%;
    margin: 0 auto 1rem auto;
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    padding: 12px 20px;
  }

  section .bt-model pre {
    background: transparent;
    border: 0;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.62em;
    line-height: 1.3;
    margin: 0;
    padding: 0;
    white-space: pre;
  }

  section .bt-cols {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.4rem;
    width: 96%;
    margin: 0 auto;
    text-align: left;
  }

  section .bt-cols h3 {
    font-size: 0.85em;
    margin: 0 0 0.3em 0;
    color: var(--tranquil-velvet);
  }

  section .bt-cols pre {
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.58em;
    line-height: 1.3;
    margin: 0;
    padding: 14px 16px;
    white-space: pre;
  }
</style>

## How the Difficulty Ranker Works

<div class="bt-model">
<pre>
Bradley-Terry model: 
   Each task i has a strength s<sub>i</sub>
   P(i harder than j) = s<sub>i</sub> / (s<sub>i</sub> + s<sub>j</sub>)
</pre>
</div>

<div class="bt-cols">
<div>

### Build the ranking

<pre>
1  LLM Judge scores the strengths of two tasks s<sub>i</sub> and s<sub>j</sub>.
2  Weight each win by confidence c<sub>i</sub> and c<sub>j</sub>
   -> WIN MATRIX
3  Fit strengths s<sub>i</sub> by iteration:
   - Start: every s<sub>i</sub> is equal
   - Sweep: recompute each s<sub>i</sub> from its weighted
            wins and opponents' current s<sub>i</sub>,
            then normalize
   - Repeat until s<sub>i</sub> barely change (500 max)
4  Difficulty d<sub>i</sub>:= centered log(s<sub>i</sub>)
</pre>
</div>
<div>

### Place a new task

<pre>
binary search the ranked list:
  compare target vs the
  midpoint anchor
  harder -> upper half
  easier -> lower half
  tie    -> stop
missing pair -> ask the judge
  for that one pair, then continue
~log2(n) comparisons ->
  insertion rank
  difficulty score
  nearest tasks
</pre>
</div>
</div>

<!--
The ranker turns subjective "which task is harder" judgements into a single difficulty scale. pairwise-difficulty-judge supplies each comparison with a confidence weight; bradley_terry_pairwise_ranking.py fits per-task strengths from the weighted wins (rank mode) and places a new task with a binary search that asks the judge only for the comparisons it actually needs (similar mode).
-->

---

<style scoped>
  section .learning-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.2rem;
    width: 90%;
    margin: 0 auto;
    align-items: stretch;
  }

  section .learning-card {
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    padding: 22px;
    text-align: left;
  }

  section .learning-card h2 {
    font-size: 1.05em;
    margin: 0 0 0.5em 0;
    color: var(--tranquil-velvet);
  }

  section .learning-card p {
    font-size: 0.75em;
    line-height: 1.25;
    margin: 0;
  }

  section .challenge {
    margin-top: 1.4em;
    font-size: 0.8em;
    color: var(--dark-grey);
    text-align: center;
  }
</style>

## Layer 3: Feedback Loops

<div class="learning-grid">
<div class="learning-card">

## Task evaluator

<p>Evaluates a given task against metrics such as difficulty, complexity, ambiguity or task type.</p>

</div>
<div class="learning-card">

## Agent evaluator

<p>Measures the result and the run trace against task-specific success criteria, tests, rubrics, or benchmarks.</p>

</div>
<div class="learning-card">

## Agent trainer

<p>Feeds evaluation results back into templates, routing rules, context policies, eval sets, and guardrails.</p>

</div>
</div>

<!--
The learning layer is what makes the factory improve. The evaluator asks whether the run worked. The trainer is not necessarily model fine-tuning; it can mean improving templates, routing, retrieval, guardrails, and eval datasets from observed failures.
-->

---

## How to evaluate a task?

TODO: THIS SLIDE IS NOT WRITTEN YET:

Motivation: We need to know how difficult the task is in order to find a good agent and the best model to increase its success rate.

TODO: We need to research what properties of a task we need to measure
- Classify Task
- Measure task quality
- Measure task difficulty
- Measure task clarity
- Measure task ambiguity

bullet points what the goal is. The goal is... ...to rank the task along dimensions of difficulty, complexity and ambiguity.
---

<style scoped>
  section .flow-block {
    width: max-content;
    max-width: 90%;
    margin: 0 auto;
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    padding: 22px 28px;
    text-align: left;
  }

  section .flow-block pre {
    background: transparent;
    border: 0;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6em;
    line-height: 1.18;
    margin: 0;
    padding: 0;
    white-space: pre;
  }
</style>

# Full Flow

<div class="flow-block">
<pre>
Task
  |
  v
Task Evaluator
  |
  v
Agent Router  <------  Template Registry
  |                         |
  v                         v
Agent Builder  <------  Agent Templates
  |
  v
Context Builder + Tool/Model Binder
  |
  v
Runnable Agent
  |
  v
Agent Evaluator
  |
  v
Agent Trainer
  |
  v
Better templates / routing / context / evals
</pre>
</div>

<!--
This is the full flow in one picture. The registry and templates are design-time assets. The task evaluator, router, builder, context builder, and binder assemble a runnable agent. The evaluator and trainer close the loop so the factory can improve.
-->

---

<style scoped>
  section .statement {
    font-size: 1.35em;
    line-height: 1.2;
    color: var(--tranquil-velvet);
    font-weight: bold;
    margin: 0 auto 1.2em auto;
    width: 80%;
  }

  section .decision-chain {
    width: fit-content;
    margin: 0 auto;
    text-align: left;
    font-size: 0.9em;
    line-height: 1.5;
  }
</style>

# Every Component Is a Decision

<div class="statement">
Every decision point creates a failure mode.
</div>

<div class="decision-chain">

- Which template?
- Which context?
- Which tools and model?
- Which validation rules?
- Which evaluation signal?
- Which component do we improve?

</div>

<!--
The component diagram is useful, but the practical challenge is that every component makes a decision. If the decision is wrong, the agent can fail even if the prompt looks reasonable. The rest of this section walks through the major failure modes.
-->

---

<style>
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

  section .challenge-panel p,
  section .challenge-panel li {
    font-size: 0.72em;
    line-height: 1.25;
  }

  section .challenge-panel ul {
    margin: 0;
  }
</style>

# Routing Is a Ranking Problem

<div class="challenge-layout">
<div class="challenge-panel">

## Concept

<p>The factory must choose the right template, model, tool set, and effort level for the task.</p>

</div>
<div class="challenge-panel">

## Failure modes

- Good agent, wrong task
- Cheap model, hard problem
- Heavy model, simple task
- Missing specialist workflow

</div>
</div>

<!--
Routing is not just picking a name from a list. It is a ranking problem. The selected agent can fail because the route was wrong, not because the agent definition itself was bad. This is why routing eventually needs measurable feedback.
-->

---

<style scoped>
  section .budget-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
    width: 92%;
    margin: 0 auto;
    text-align: left;
  }

  section .budget-card {
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    padding: 18px;
  }

  section .budget-card h2 {
    font-size: 0.95em;
    margin: 0 0 0.4em 0;
    color: var(--tranquil-velvet);
  }

  section .budget-card p {
    font-size: 0.68em;
    line-height: 1.25;
    margin: 0;
  }
</style>

# Context Is a Budget

<div class="budget-grid">
<div class="budget-card">

## Too Little

<p>The agent guesses, hallucinates, or misses project-specific constraints.</p>

</div>
<div class="budget-card">

## Too Much

<p>The agent gets noise, latency, cost, and a larger surface for distraction.</p>

</div>
<div class="budget-card">

## Just Enough

<p>The factory supplies the smallest context package that can prove the task.</p>

</div>
</div>

<!--
Context assembly is one of the hardest parts of an agent factory. More context is not automatically better. The useful question is whether the factory retrieved the right information and whether the agent actually used it.
-->

---

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

  section .challenge-panel p,
  section .challenge-panel li {
    font-size: 0.72em;
    line-height: 1.25;
  }

  section .challenge-panel ul {
    margin: 0;
  }
</style>

# Capabilities Are Risk

<div class="challenge-layout">
<div class="challenge-panel">

## Concept

<p>Tools, model choice, effort, permissions, memory, and guardrails define what the agent can do.</p>

</div>
<div class="challenge-panel">

## Tradeoff

- Too little power: the task fails
- Too much power: risk and cost increase
- Wrong power: the agent optimizes the wrong path

</div>
</div>

<!--
Capability binding is a safety and effectiveness decision. The factory should attach the minimum useful power for the task: enough to finish, but not a broad set of tools and permissions just because they are available.
-->

---

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

  section .challenge-panel p,
  section .challenge-panel li {
    font-size: 0.72em;
    line-height: 1.25;
  }

  section .challenge-panel ul {
    margin: 0;
  }
</style>

# Evaluation Needs Ground Truth

<div class="challenge-layout">
<div class="challenge-panel">

## Concept

<p>"Looks good" is not an evaluation strategy. The factory needs task-specific success evidence.</p>

</div>
<div class="challenge-panel">

## Examples

- Tests, lint, type checks
- Expected outputs
- Retrieval labels
- Human rubrics
- Benchmark tasks

</div>
</div>

<!--
Different tasks need different evaluation signals. Code can often be checked with tests and static analysis. Search needs relevance labels. Writing may need a rubric. Without some form of ground truth, the factory cannot reliably improve.
-->

---

<style scoped>
  section .attribution-table {
    width: 90%;
    margin: 0 auto;
  }

  section .attribution-table table {
    font-size: 0.86em;
    line-height: 1.12;
  }

  section .attribution-table table td,
  section .attribution-table table th {
    padding: 0.34em 0.55em;
  }

  section .attribution-table table th {
    color: var(--tranquil-velvet);
  }
</style>

# Failure Attribution Enables Learning

<div class="attribution-table">

| If the failure was... | Improve... |
| --- | --- |
| Wrong agent selected | Router or template descriptions |
| Missing or stale context | Context builder or retrieval policy |
| Tool could not complete the task | Tool/model binder or permissions |
| Agent did the wrong thing | Template instructions or constraints |
| Output looked good but failed | Evaluator or success criteria |
| Failure keeps repeating | Training loop or regression evals |

</div>

<!--
Failure attribution matters because not every failed run should lead to prompt editing. If the router picked the wrong agent, fix routing. If the agent lacked context, fix context assembly. If the evaluator missed the failure, fix the evaluation. This is how the factory learns from runs instead of accumulating random prompt tweaks.
-->

---

<style scoped>
  section .learning-loop {
    width: fit-content;
    margin: 0 auto;
    background: #f6f8fa;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    padding: 24px 32px;
    text-align: left;
  }

  section .learning-loop pre {
    background: transparent;
    border: 0;
    color: #1f2328;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.74em;
    line-height: 1.2;
    margin: 0;
    padding: 0;
  }
</style>

# The Factory Learns From Runs

<div class="learning-loop">
<pre>
Run
  ↓
Trace
  ↓
Evaluate
  ↓
Attribute failure
  ↓
Improve templates, routing,
context policies, tools, evals
</pre>
</div>

<!--
This is the bridge to production. A factory is only useful at scale if its runs become data. Traces and evaluations should feed back into better templates, routing, context policies, tool policies, and eval sets.
-->

---

# Kamino451 

&nbsp;

---

# Kamino451 

A lightweight implementation of key concepts.

---

![bg cover](images/slide_graphics/kamino451.png)

---

# Scaling to Production

&nbsp;

---

# Summary

&nbsp;


<!-- ---

# Links
https://cracking-ai-engineering.com
https://github.com/florianbuetow/kamino451

![w:320](images/slide_graphics/blog-qr.svg) &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; ![w:320](images/slide_graphics/github-kamino-qr.svg) 
 -->
---

![bg cover](images/slide_graphics/kamino451.png)

![w:320](images/slide_graphics/blog-qr.svg) &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; ![w:320](images/slide_graphics/github-kamino-qr.svg) 

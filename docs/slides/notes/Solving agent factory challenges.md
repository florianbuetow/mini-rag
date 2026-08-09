# Solving Agent Factory Challenges

Research note for the "Key Concepts and Challenges" section.

## Scope and caveat

"Agent factory" is our architecture framing, not a single vendor-defined primitive. The implementation tactics below are synthesized from source-backed primitives: agent definitions, subagents, handoffs, tools, guardrails, traces, evals, datasets, retrieval evaluation, and workflow orchestration.

When converting this into slides, avoid claiming that any vendor directly ships an "agent factory" as described here. The defensible claim is:

> An agent factory applies software-engineering lifecycle controls around agent definitions and agent runs.

## Source-backed building blocks

- OpenAI Agents SDK defines an agent as a unit that packages model, instructions, and optional runtime behavior such as tools, guardrails, MCP servers, handoffs, and structured outputs.
- OpenAI recommends traces first while debugging behavior, then datasets and eval runs when repeatability is needed. Traces capture model calls, tool calls, guardrails, and handoffs.
- OpenAI Agents SDK tracing records LLM generations, tool calls, handoffs, guardrails, and custom events as spans inside traces.
- OpenAI guardrails support checks and validations on user input, final agent output, and custom function-tool invocations.
- Claude Code subagents can be selected by description or explicitly by name. Claude's docs say clear descriptions help Claude decide when to invoke a subagent.
- Anthropic's contextual retrieval research argues that retrieval quality is often improved by preserving contextual information during indexing/retrieval and reports large reductions in failed retrievals with contextual embeddings/BM25 and reranking.
- LlamaIndex evaluation docs distinguish response evaluation from retrieval evaluation and list retrieval metrics such as MRR, hit rate, and precision.
- LangSmith evaluation docs separate offline evaluation on curated datasets from online production evaluation, and describe a feedback loop where failing production traces are added to datasets and fixes are validated offline before redeploying.

## 1. Every Component Is a Decision

Challenge:

Every component makes a decision: template, context, tools, model, validation, evaluation, and improvement target. If decisions are implicit, failures become hard to reproduce.

How to meet it:

- Represent every decision as data.
- Give every run a `run_id`, `task_id`, `template_version`, `router_version`, `context_policy_version`, `tool_policy_version`, and `evaluator_version`.
- Store candidate sets, not only final choices:
  - candidate templates
  - candidate models
  - candidate tools
  - retrieved context candidates
  - selected evaluator
- Attach decision metadata to traces/spans:
  - why this route was chosen
  - confidence score
  - constraints used
  - rejected alternatives
- Use structured output for decision records where possible, so analysis is not string parsing.

Technical pattern:

```text
Task
  -> decision log
  -> selected route
  -> trace spans
  -> evaluation result
  -> failure attribution
```

Slide-ready line:

> Make every factory decision observable before trying to make it intelligent.

## 2. Routing Is a Ranking Problem

Challenge:

The factory must choose the right template, model, tool set, and effort level. A good agent can fail if assigned to the wrong task.

Source-backed facts:

- Claude Code subagents can be invoked by name, and Claude can automatically delegate based on the subagent `description`.
- OpenAI handoffs allow delegation to specialist agents; handoff descriptions can hint when a model should pick a handoff.
- LangGraph documents routing and supervisor/orchestrator-worker patterns as workflow/agent patterns.
- OpenAI eval docs recommend using trace grading to answer whether a prompt or routing change improved end-to-end behavior.

How to meet it:

- Treat templates as ranked candidates, not a flat menu.
- Maintain routing metadata on templates:
  - task types
  - required inputs
  - expected outputs
  - required tools
  - allowed models
  - cost/latency profile
  - known failure modes
- Use a staged router:
  1. Rule filters for hard constraints.
  2. Embedding or lexical retrieval for candidate templates.
  3. LLM or scoring model for final ranking.
  4. Confidence threshold for fallback or clarification.
- Log the full candidate list and selected route.
- Build a routing eval set:
  - tasks
  - expected/best template
  - acceptable templates
  - unacceptable templates
- Measure:
  - top-1 routing accuracy
  - top-k recall
  - route regret when counterfactual runs are available
  - fallback/clarification rate
  - cost per successful route

Technical caution:

Do not claim the router always knows the "best" agent. In production, you often know only observed performance. True best-agent labels require expensive counterfactual runs or curated labels.

Slide-ready line:

> Routing improves when template descriptions become eval targets, not just documentation.

## 3. Context Is a Budget

Challenge:

The factory must choose what the agent should know. Too little context causes missing facts. Too much context adds noise, latency, cost, and distraction.

Source-backed facts:

- Anthropic describes RAG as retrieving relevant information and appending it to the prompt, and notes retrieval can fail when chunks lose context.
- Anthropic reports contextual retrieval can reduce failed retrievals substantially, especially with reranking.
- LlamaIndex separates response evaluation from retrieval evaluation and lists retrieval metrics such as MRR, hit rate, and precision.

How to meet it:

- Define a context budget per task class:
  - maximum tokens
  - maximum files/chunks
  - source priority
  - freshness requirements
  - required citation/usage policy
- Use a context assembly pipeline:
  1. Query planning: derive search queries from task.
  2. Retrieval: code search, file search, vector/BM25, web, memory.
  3. Reranking: choose the highest-value chunks.
  4. Compression/summarization: reduce low-signal content.
  5. Packaging: include only what the agent needs for the next run.
- Evaluate retrieval separately from final answer quality.
- Track context usage:
  - retrieved
  - included
  - cited/referenced
  - used in final answer
  - later judged relevant/irrelevant
- Build context eval sets:
  - task/query
  - relevant documents/chunks
  - expected evidence
  - negative/harmful distractors

Metrics:

- retrieval recall
- precision
- MRR / hit rate
- context token cost
- citation coverage
- unused context ratio
- missed-evidence failures

Slide-ready line:

> Context is not "more text"; it is selected evidence under a budget.

## 4. Capabilities Are Risk

Challenge:

Tools, models, permissions, effort, memory, and guardrails define what an agent can do. Too little power makes it ineffective; too much power increases cost and risk.

Source-backed facts:

- OpenAI agent definitions include tools, handoffs, guardrails, MCP servers, and structured outputs as part of runtime behavior.
- OpenAI tools documentation says tools extend model capabilities through built-in tools, function calling, tool search, and remote MCP servers.
- OpenAI guardrails run checks on input, output, and tool invocations; tool guardrails are needed around each custom function-tool call.

How to meet it:

- Maintain a capability catalog:
  - tool name/version
  - purpose
  - input/output schema
  - permission level
  - side effects
  - cost/latency profile
  - failure modes
  - required approvals
- Bind capabilities using least privilege:
  - start with minimum tool set
  - add tools only when required by task/evaluator
  - separate read-only, write, destructive, and external-production actions
- Validate before run:
  - required tools exist
  - credentials/permissions are present
  - unresolved variables are absent
  - policy allows the capability
  - human approval required for risky actions
- Use guardrails at the correct boundary:
  - input guardrails before expensive or risky routing
  - tool guardrails around tool calls
  - output guardrails on final deliverables
- Record all tool decisions and tool calls in traces.

Metrics:

- tool selection precision/recall
- tool call success rate
- permission denial rate
- approval rate
- guardrail tripwire rate
- cost/latency per tool
- side-effect incidents

Slide-ready line:

> Capabilities should be selected, validated, and audited, not simply exposed.

## 5. Evaluation Needs Ground Truth

Challenge:

"Looks good" does not prove success. Different task types need different evaluation surfaces.

Source-backed facts:

- OpenAI eval docs recommend traces while debugging, and datasets/eval runs once "good" is known and repeatability is needed.
- LangSmith describes offline evaluation on curated datasets to compare versions and catch regressions, and online evaluation for production interactions.
- LangSmith evaluators can include human review, code rules, LLM-as-judge, and pairwise comparison.
- LlamaIndex notes response evaluation can use correctness, semantic similarity, faithfulness, context relevancy, answer relevancy, and guideline adherence.

How to meet it:

- Define task classes before defining evaluators:
  - code change
  - code review
  - research
  - extraction
  - retrieval
  - writing
  - planning
  - deployment
- Attach evaluator type to each task class:
  - deterministic tests for code behavior
  - static analysis/lint/typecheck for code quality gates
  - schema validation for structured outputs
  - reference answers for extraction/QA
  - retrieval labels for context quality
  - rubric or human review for writing/planning
  - LLM-as-judge where deterministic or labeled evaluation is not feasible
- Create eval datasets:
  - curated examples
  - production traces that failed
  - synthetic edge cases, clearly marked as synthetic
  - regression cases for fixed failures
- Keep evaluator versions and thresholds explicit.
- Run offline evals before changing templates/router/context policies.
- Use online evals/sampling in production to discover new failure modes.

Technical caution:

LLM-as-judge is useful but should not be treated as ground truth. Use it as one evaluator, calibrate against human labels where possible, and prefer deterministic checks when available.

Slide-ready line:

> The evaluator is part of the product, not an afterthought.

## 6. Failure Attribution Enables Learning

Challenge:

When a run fails, the fix might be routing, context, tools, template design, model choice, guardrails, or the evaluator. Without attribution, teams edit prompts randomly.

Source-backed facts:

- OpenAI traces record model calls, tool calls, guardrails, handoffs, and custom events.
- OpenAI trace grading can be used to answer whether the agent picked the right tool, whether a handoff happened when it should have, and whether workflow behavior improved.
- LangSmith describes adding failing production traces to datasets, creating targeted evaluators, validating fixes offline, and redeploying.

How to meet it:

- Create a failure taxonomy:
  - wrong_template
  - wrong_model
  - wrong_tool
  - missing_context
  - stale_context
  - hallucination
  - tool_error
  - permission_blocked
  - guardrail_blocked
  - evaluator_error
  - output_format_error
  - timeout
- Add a post-run attribution step:
  1. Inspect trace spans.
  2. Compare expected vs actual outcome.
  3. Assign one primary failure category.
  4. Optionally assign contributing categories.
  5. Link failure to the component/version to change.
- Convert high-confidence failures into regression evals.
- Keep attribution conservative:
  - "unknown" is better than a false root cause.
  - distinguish root cause from symptom.

Cause-to-fix mapping:

| Failure | Improve |
| --- | --- |
| Wrong agent selected | Router or template descriptions |
| Missing/stale context | Context builder or retrieval policy |
| Tool could not complete task | Tool/model binder or permissions |
| Agent did the wrong thing | Template instructions or constraints |
| Output looked good but failed | Evaluator or success criteria |
| Failure keeps repeating | Training loop or regression evals |

Slide-ready line:

> Attribution tells you where to intervene.

## 7. The Factory Learns From Runs

Challenge:

Runs generate evidence, but evidence only improves the system if it is converted into changes and regression protection.

Source-backed facts:

- OpenAI recommends moving from traces to datasets/eval runs when repeatability is needed.
- LangSmith describes a feedback loop: add failing production traces to datasets, create targeted evaluators, validate fixes offline, and redeploy.

How to meet it:

- Treat every run as an event record:
  - input task
  - selected template/model/tools
  - context package
  - trace
  - output
  - evaluation result
  - failure attribution
  - cost/latency
- Promote failures into regression cases:
  - minimal reproduction
  - expected behavior
  - failure category
  - fixed-by component
- Improve the right asset:
  - template instructions
  - template metadata
  - router/ranking rules
  - context retrieval policy
  - tool binding policy
  - guardrails
  - evaluator rubric
  - eval dataset
- Validate the change against:
  - original failing case
  - nearby cases
  - broad smoke eval
  - cost/latency budget
- Only then promote a new version.

Technical caution:

"Agent trainer" should not imply model fine-tuning by default. Most early improvements are better templates, routing, retrieval, tool policies, guardrails, and evals. Fine-tuning can be a later option when enough high-quality data exists.

Slide-ready line:

> A factory improves by turning failed runs into regression tests and policy changes.

## Minimal implementation checklist

If building a first practical version, implement in this order:

1. Template registry with versioned metadata.
2. Decision log for every run.
3. Trace capture for model calls, tool calls, handoffs, guardrails, and custom events.
4. Context package builder with token budget and retrieval metadata.
5. Capability binder with least-privilege tool policy.
6. Pre-run validation checks.
7. Task-type-specific evaluators.
8. Failure taxonomy and attribution record.
9. Dataset of fixed failures.
10. Offline regression eval before promoting a factory change.

## Sources

- OpenAI, "Agent definitions": https://developers.openai.com/api/docs/guides/agents/define-agents
- OpenAI, "Using tools": https://developers.openai.com/api/docs/guides/tools
- OpenAI, "Evaluate agent workflows": https://developers.openai.com/api/docs/guides/agent-evals
- OpenAI Agents SDK, "Tracing": https://openai.github.io/openai-agents-python/tracing/
- OpenAI Agents SDK, "Guardrails": https://openai.github.io/openai-agents-python/guardrails/
- OpenAI Agents SDK, "Handoffs": https://openai.github.io/openai-agents-python/handoffs/
- Claude Code docs, "Subagents in the SDK": https://code.claude.com/docs/en/agent-sdk/subagents
- Anthropic Engineering, "Contextual Retrieval in AI Systems": https://www.anthropic.com/engineering/contextual-retrieval
- LlamaIndex docs, "Evaluating": https://developers.llamaindex.ai/python/framework/module_guides/evaluating/
- LangSmith docs, "Evaluation": https://docs.langchain.com/langsmith/evaluation
- LangGraph docs, "Workflows and agents": https://docs.langchain.com/oss/python/langgraph/workflows-agents

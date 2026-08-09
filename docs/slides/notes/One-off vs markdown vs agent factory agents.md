# One-off Prompt vs Markdown Agent vs Agent Factory

Research note for the "What is an Agent Factory?" slide section.

## Short thesis

The useful maturity ladder is:

1. One-off prompt: a disposable instruction created for one task.
2. Markdown agent: a reusable role/configuration artifact stored in a file.
3. Agent factory: a lifecycle/control system that can route, parameterize, validate, observe, evaluate, and improve agent definitions and runs.

Correction: "runtime-instantiated" is not a valid contrast between Markdown agents and agent-factory agents. A Markdown subagent is also instantiated at runtime when invoked. The real contrast is where adaptation, quality control, and improvement live. A Markdown agent gives you a reusable agent definition. An agent factory gives you the surrounding process that chooses, configures, validates, evaluates, and improves definitions and runs.

Markdown agents are a real improvement over one-off prompts because they make roles reusable and versionable. Their limitation is not that they are "not real runtime agents"; their limitation is that the file itself is a definition. Production concerns around routing, per-run configuration, validation, evals, failure analysis, and feedback into future versions require additional machinery.

## Source-backed observations

### One-off agents

A one-off agent is not usually a first-class artifact. It is a prompt or request in a conversation, for example: "launch a security reviewer for these changes."

Strengths:

- Fastest way to delegate a task.
- Good for exploration, demos, and unique work.
- Can be highly task-specific because the user describes the immediate goal directly.

Shortcomings:

- Usually not saved as a reusable unit.
- Hard to rerun consistently because the prompt, context, tool state, and model state are often implicit.
- Quality feedback is anecdotal unless the run is separately traced or evaluated.
- Governance is weak because constraints depend on what was said in the moment.

Slide language:

> One-off prompts are powerful, but they evaporate after the task.

### Markdown agents

Claude Code custom subagents are a strong example of Markdown agents. The official docs say subagents are specialized assistants for task-specific workflows and that each subagent runs in its own context window with a custom system prompt, specific tool access, and independent permissions. Claude delegates to a subagent when the task matches the subagent description.

Claude Code subagents can be stored as Markdown files with YAML frontmatter. The docs list scopes such as project `.claude/agents/`, user `~/.claude/agents/`, plugin `agents/`, and current-session JSON via `--agents`. The frontmatter can configure fields such as `name`, `description`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, and `color`. The Markdown body becomes the system prompt.

Important operational detail: if a subagent file is added or edited directly on disk, Claude Code loads it at session start, so the session must be restarted for direct file edits to take effect. Subagents created through the `/agents` UI can take effect immediately.

Strengths:

- Reusable role definition instead of an improvised prompt.
- Versionable when checked into a project.
- Can define tool access, model choice, permissions, memory, hooks, and isolation.
- Useful when the same worker role is needed repeatedly.
- Better context hygiene because the subagent can work in its own context and report back a summary.

Shortcomings compared with an agent factory:

- The file is a reusable definition, not a factory process.
- Routing is supported, but Claude's automatic delegation depends on the task description, the subagent `description`, and current context; this is not the same as an explicit measurable router.
- Tool/model/permission configuration is supported, and per-invocation model override is also supported. Capability selection policy is outside the Markdown file unless encoded by surrounding orchestration.
- Hooks and memory are supported, so "no guardrails" would be false. The narrower issue is that hooks/memory are local mechanisms, not automatically an eval-backed improvement loop.
- Quality is not automatically measured just because the agent exists as Markdown.
- Improvement is manual unless paired with traces, datasets, evals, or another feedback loop.
- Direct file edits may require a session restart to load, which is fine for authoring but not ideal as a runtime adaptation mechanism.
- A Markdown agent can define a strong worker, but not by itself the full production system around selection, validation, monitoring, evaluation, and improvement.

Slide language:

> Markdown agents preserve the worker definition; factories manage the lifecycle around it.

### Factory-managed agents / runs

OpenAI's Agents SDK documentation frames an SDK agent as a richer production unit: it packages a model, instructions, and optional runtime behavior such as tools, guardrails, MCP servers, handoffs, and structured outputs. The same page says to start with one focused agent and add more only when separate ownership, different instructions, different tool surfaces, or different approval policies are needed.

OpenAI's agent evaluation documentation adds the missing production feedback loop. It recommends traces while debugging behavior, where a trace captures model calls, tool calls, guardrails, and handoffs for a run. It then recommends moving to datasets and eval runs when repeatability is needed, so teams can benchmark changes, compare prompts, and run larger-scale evaluations over time.

Claude Code dynamic workflows and agent teams show the same direction from reusable agents toward orchestration systems. Agent teams add a lead, teammates, shared task list, messaging, task assignment, hooks, and quality gates. Dynamic workflows are JavaScript scripts that orchestrate many subagents in the background and can be read and rerun.

An agent factory is therefore not just "an agent stored somewhere." More precisely, it is a process/control plane that can produce or select an agent definition and manage the run:

1. Intake task.
2. Estimate task complexity and risk.
3. Select or generate an agent template.
4. Fill task-specific variables.
5. Assemble context.
6. Select model, effort, tools, permissions, and guardrails.
7. Validate the runnable agent.
8. Execute and trace the run.
9. Evaluate output and workflow behavior.
10. Feed results back into templates, routing, eval sets, and policies.

Strengths:

- It can use Markdown agents as templates or inputs.
- It adds explicit routing and template selection around the agent definitions.
- It can assemble context per run instead of relying only on caller-provided context.
- It can apply a policy for tools, models, effort, permissions, and guardrails per run.
- It can validate the runnable configuration before execution.
- It can trace and evaluate runs so quality is measurable.
- It can classify failures and feed results back into templates, routing, eval sets, and policies.
- It turns agents into managed production components rather than isolated reusable prompts.

Shortcomings / costs:

- Higher engineering overhead.
- Requires datasets, traces, eval criteria, and governance policy.
- More moving parts: router, registry, context builder, tool binder, validator, runner, evaluator, observability.
- Can be overkill for single-use or low-risk tasks.

Slide language:

> The factory is not a better prompt file; it is the lifecycle around the agent.

## Comparison table for slides

This table is stronger than the current slide because it separates artifact maturity from production maturity.

| Dimension | One-off prompt | Markdown agent | Agent factory |
| --- | --- | --- | --- |
| Artifact | Conversation instruction | Reusable role/config file | Lifecycle/control system |
| Reuse | Low | Medium/high | High |
| Runtime instantiation | Yes, as part of the conversation | Yes, when invoked | Yes, after selection/configuration |
| Adaptation | Manual prompt edits | Invocation prompt + configured fields | Selection/configuration policy |
| Context | Whatever is in the chat | Static prompt + caller context | Assembled per run |
| Tool/model choice | Ad hoc | Configured, inherited, or overridden | Policy-driven selection |
| Routing | Human asks directly | Description-based delegation | Measurable router/template selection |
| Validation | Usually none | Possible through hooks/settings | Factory-level pre-run checks |
| Quality signal | Anecdotal | Manual unless instrumented | Traces, evals, benchmarks |
| Improvement | Prompt tweaks | File edits or memory/hooks | Feedback loop into templates/evals |
| Best for | Demos, unique tasks | Repeated specialist roles | Production agent systems |

## Short slide version

```markdown
### From Saved Agents to Agent Factories

<center>

| One-off prompt | Markdown agent | Agent factory |
| --- | --- | --- |
| Exists in the conversation | Exists as a reusable file | Exists as a managed process |
| Role is improvised | Role is declared | Role/template is selected |
| Context is whatever is present | Context comes from invocation + file | Context is assembled by policy |
| Tools are ad hoc | Tools/model can be configured | Capabilities are selected/validated |
| Quality is anecdotal | Quality is manual unless instrumented | Quality is traced and evaluated |
| Hard to repeat | Easy to reuse | Repeatable, measurable, improvable |

</center>
```

## Speaker note draft

One-off agents are useful because they are fast. You ask the tool to launch a worker for a task, and the worker does the job. But that instruction usually disappears into the conversation. A Markdown agent is the next step: we save the role, prompt, tools, and sometimes model, permissions, hooks, memory, or isolation in a file. That is much better for reuse. The factory is not "more runtime" than a Markdown agent; the Markdown agent also runs at runtime. The factory is the lifecycle around it: it takes the task as input, chooses the right kind of agent or template, supplies context, applies capability policy, validates the run, traces it, evaluates it, and uses the outcome to improve future runs.

## Proposed narrative

1. "Why not just launch an agent?" - one-off prompt.
2. "We can save that role as Markdown." - reusable role artifact.
3. "But saved does not mean production-managed." - reusable definition, but lifecycle still external.
4. "An agent factory adds the lifecycle and feedback loop." - routing, context, validation, traces, evals, improvement.

## Sources

- Claude Code docs, "Create custom subagents": https://code.claude.com/docs/en/sub-agents
  - Subagents are specialized assistants with their own context, system prompt, tool access, and permissions.
  - They can be Markdown files with YAML frontmatter.
  - Claude delegates based on the subagent description.
  - File edits on disk are loaded at session start.
- Claude Code docs, "Orchestrate teams of Claude Code sessions": https://code.claude.com/docs/en/agent-teams
  - Agent teams add coordination, shared task lists, messaging, hooks, and quality gates.
- Claude Code docs, "Orchestrate subagents at scale with dynamic workflows": https://code.claude.com/docs/en/workflows
  - Dynamic workflows are scripts that orchestrate many subagents and can be read and rerun.
- OpenAI docs, "Agent definitions": https://developers.openai.com/api/docs/guides/agents/define-agents
  - Agents package model, instructions, tools, guardrails, MCP servers, handoffs, structured outputs, and runtime behavior.
- OpenAI docs, "Evaluate agent workflows": https://developers.openai.com/api/docs/guides/agent-evals
  - Traces, graders, datasets, and eval runs turn agent quality into something measurable and repeatable.
- OpenAI Codex docs, "Custom instructions with AGENTS.md": https://developers.openai.com/codex/guides/agents-md
  - AGENTS.md is useful background for Markdown-based persistent guidance, though it is project instruction context rather than a named runtime agent.

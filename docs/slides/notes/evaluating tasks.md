**Yes, evaluating tasks along multiple dimensions is a core part of building an effective "agent factory"** (a system for generating, routing, or composing agents/models for incoming tasks). This enables smart mapping: simple/clear tasks go to lightweight/fast models or basic agents; complex/ambiguous ones go to stronger models, specialized agents, tool-using agents, multi-agent workflows, or even human-in-the-loop.

Your suggested dimensions (clarity, ambiguity, correctness/no contradictions, length, quality, difficulty) are excellent starting points. They directly support routing, cost optimization, quality control, and failure prevention.

### Best Metrics: Prioritized by Accuracy + Practicality

Here are the **most effective and accurately measurable metrics**, grouped by type. I focus on those that work well in production for task profiling before routing.

#### 1. Objective / Rule-Based Metrics (Highest Accuracy: Near 100%, Fast & Deterministic)
These require no LLM and are computed instantly with libraries (e.g., `tiktoken`, `textstat`, `spaCy`).

- **Length** (Token count, word count, character count)  
  **Best for**: Proxy for cost, latency, and baseline complexity.  
  **Accuracy**: Perfect (use the exact tokenizer of your target models).  
  **Why best**: Extremely reliable; longer tasks often need stronger models or decomposition.

- **Readability / Syntactic Complexity** (Flesch Reading Ease score, Flesch-Kincaid Grade Level, average sentence length, parse tree depth)  
  **Best for**: Proxy for clarity and cognitive load on the model.  
  **Accuracy**: Very high (formula-based or NLP parsing).  
  **Interpretation**: Higher Flesch Reading Ease = easier/clearer. Extremely low or high scores can flag issues (jargon overload or overly simplistic/vague writing). Combine with LLM metrics for best results.

- **Structural Indicators** (Number of explicit requirements, constraints, success criteria, bullet points/lists, input/output specifications).  
  **Accuracy**: High (rule-based parsing or lightweight LLM extraction).  
  Good signals of quality and completeness.

#### 2. LLM-as-a-Judge Metrics (High Accuracy: 80–95%+ Human Agreement When Done Right)
These handle the nuanced, semantic aspects your question highlights. Modern practice relies heavily on **LLM-as-Judge** with structured rubrics, few-shot examples, chain-of-thought reasoning, and JSON output. Strong judges (Claude 3.5/4, GPT-4o-class, or well-tuned open models) + ensembling deliver reliable results.

**Recommended dimensions and how to measure them**:

- **Clarity** (Score 1–5 or 1–10)  
  Rubric example: "How clearly and unambiguously is the task stated? Are goals, inputs, outputs, constraints, and success criteria explicit?"  
  **Why best**: Directly addresses your question. Low clarity often leads to poor agent performance regardless of model size.

- **Ambiguity** (Score or binary flags + count of vague elements)  
  Rubric: "How many reasonable interpretations exist? Presence of vague terms ('good', 'appropriate', 'somehow', etc.) or underspecified elements?"  
  Often measured as the inverse of clarity or separately.

- **Consistency / Absence of Contradictions** (Binary or score + list of issues)  
  Rubric: "Does the task description contain logical contradictions, conflicting requirements, or internal inconsistencies?"  
  **Why excellent**: Highly reliable with LLM judges; flags tasks that need human clarification before routing.

- **Completeness / Overall Quality** (Score 1–5)  
  Rubric: "Does the task include all necessary context, constraints, expected output format, evaluation criteria, and edge cases?"  
  Strong predictor of downstream success.

- **Difficulty / Complexity** (Easy/Medium/Hard classification or 1–10 score)  
  Best approach: Hierarchical taxonomy + few-shot examples in the judge prompt (e.g., "Easy: single factual lookup; Medium: multi-step reasoning with tools; Hard: novel planning + tool chaining + uncertainty").  
  Can also incorporate capability requirements (reasoning depth, tool use, multi-agent coordination, domain knowledge).  
  **Why powerful for mapping**: Directly informs model/agent selection. Proxies like predicted CoT length or uncertainty can supplement.

- **Task Type / Category** (Classification)  
  Examples: Factual QA, code generation, creative writing, multi-step planning, tool-heavy workflow, summarization, etc.  
  **Accuracy**: Very high with classification-style prompting or embedding + classifier. Critical for routing to specialized models/agents.

**Proven frameworks**:
- **PEEM** (Prompt Engineering Evaluation Metrics): Excellent structured rubric with prompt-level axes (clarity/structure, linguistic quality, fairness) + rationales. Uses LLM evaluator and shows strong alignment with downstream performance.
- Tools like DeepEval, Braintrust, LangSmith, or custom Pydantic-structured judges make this production-ready.

### How to Achieve "Good Accuracy" in Practice

| Metric Type       | Accuracy Level      | How to Maximize Reliability                  | Speed/Cost      |
|-------------------|---------------------|----------------------------------------------|-----------------|
| Length & Readability | Near 100%          | Direct formulas/libraries                   | Instant        |
| LLM-as-Judge (Clarity, Ambiguity, Consistency, Difficulty, etc.) | 80–95%+ human agreement | Detailed rubrics + examples + CoT + JSON + ensemble (2–3 judges) + periodic human calibration (Cohen's kappa) | Low–Medium (use strong but efficient judge) |
| Task Type         | Very High          | Few-shot classification or fine-tuned small model | Fast           |

**Best practices for high-accuracy LLM judges**:
- Use **explicit rubrics** with definitions and 2–4 few-shot examples per score level.
- Require **rationale + score** in structured output (easier to debug and audit).
- **Ensemble** judges or use self-consistency (multiple runs).
- Calibrate against a small human-labeled set regularly.
- Hybrid system: Objective metrics + LLM scores → feed into rules or a lightweight meta-classifier for final routing decision.

### How This Supports Task → Model/Agent Mapping

| Task Profile                          | Recommended Mapping                     | Rationale |
|---------------------------------------|-----------------------------------------|---------|
| Short + High clarity + Low difficulty + High consistency | Small/fast model + simple agent        | Cost/latency efficient |
| High difficulty + Tool needs + Multi-step | Strong model + planning/tool agent     | Capability match |
| High ambiguity or contradictions     | Clarification agent → human review     | Prevent downstream failures |
| Low completeness                     | Agent that asks clarifying questions   | Improves success rate |

This profiling can run as a lightweight pre-processing step in your agent factory pipeline.

### Summary of Best Metrics
- **Core reliable set**: Length (tokens) + Readability (Flesch) + **LLM-as-Judge on Clarity, Ambiguity, Consistency (no contradictions), Completeness, Difficulty, and Task Type**.
- These are measurable with **good-to-excellent accuracy** today using hybrid objective + LLM-judge approaches.
- Start simple (length + basic LLM clarity/consistency scores) and expand. Monitor routing success rates and iterate on rubrics.

This approach is already used in production agentic systems (Azure Agent Factory patterns, various LLM routing papers, and evaluation frameworks). It turns task evaluation from a vague art into a measurable, automatable component of your factory. 

If you share more details about your tech stack (e.g., specific models, frameworks like LangGraph/CrewAI, or evaluation tools), I can suggest concrete implementation code or rubrics.
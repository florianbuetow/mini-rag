---
marp: true
theme: xebia-theme
paginate: true
---

<div class="columns" style="align-items: center;">
<div class="column" style="justify-content: center;">

# Kamino451
by Florian Buetow

<br/>

> Kamino. I'm not familiar with it. Is it in the Republic?

> No, no. It's beyond the Outer Rim. I'd say about, 12 parsecs outside the Rishi Maze.

 <div class="smaller-content">Obi-Wan Kenobi and Dexter Jettster in</br>Star Wars: Episode II - Attack of the Clones</div>


</div>
<div class="column" style="align-items: center; justify-content: center;">

![w:640](images/slide_graphics/kamino451-badge.png)

</div>
</div>

---


### Kamino

 
```
TODO: Kamino is an aquatic planet ...
```
### Fahrenheit 451

```
TODO: A Sci-Fi Novel by Ray Bradburry about a dystopican future about censorship where the books that humans are allowed to read are restricted.
```

### Kamino451

```
TODO: Combining the idea of cloing agents and tailorign the context they are allowed to receive.
```

---


# Speaker

<div class="profile-grid">
<div class="speaker_profile_columns">
  <div class="speaker_profile_column">
    <img src="images/speakers/flori.jpg" alt="Florian Buetow" style="max-width: 100%; max-height: 320px;">
  </div>
  <div class="column" style="display: flex; flex-direction: column; justify-content: center; text-align: left;"><br>
    <strong>Florian Buetow</strong><br>
    Software Consultant at Xebia<br>
    <br>
    <span>LinkedIn: <a href="https://www.linkedin.com/in/fbuetow/">linkedin.com/in/fbuetow</a></span>
    <span>GitHub: <a href="https://github.com/florianbuetow">github.com/florianbuetow</a></span>
    <span>Blog: <a href="https://cracking-ai-engineering.com">cracking-ai-engineering.com</a></span>
  </div>
</div>
</div>

---


![w:1020](images/slide_graphics/kamino451.png)

---

<div class="cc-screen">
<pre class="cc-welcome"><span class="cc-logo"> ▐▛███▜▌</span>   <span class="cc-title">Claude Code</span> <span class="cc-dim">v2.1.169</span>
<span class="cc-logo">▝▜█████▛▘</span>  <span class="cc-dim">Sonnet 4.6 with high effort · Claude Max</span>
<span class="cc-logo">  ▘▘ ▝▝</span>    <span class="cc-dim">/Users/flo</span></pre>
</div>

---


# What Is Kamino451?

![w:380](images/slide_graphics/kamino451-badge.png)

**LIVE DEMO**

</div>

---


## Agent Factory Features

- Filesystem based (`.kamino/`)
- Blueprints for "cloning" tested agents
- Blueprints for creating ad-hoc agents
- Task complexity ranker
- Automatic task decomposition 
- Automatic model to agent mapping
- A `factory` plugin for Claude/codex
- Task agnostic agent orchestrator
- Agent evaluation framework

---


## Typical Workflow 1

- State your task
- Get back agents
- Launch the agents

## Behind the scenes

- Task decomposition
- Task to agent mapping
- Task to model mapping

---

# Example

Using the factory skill

```claude
/factory Write me an article based on demo/bratwurst-wars.md as the source material, following demo/styleguide.md. 
```
---

```claude
/factory Write me an article based on demo/bratwurst-wars.md as the source material, following demo/styleguide.md.
But I also want you to fact check and review the article for me and then present me the final results as files.
```
---

```claude
/factory lets use the reviews to iterate on our current article draft, then perform another check.
```





/delegate to opus the following command verbatim without any additions or redactions: "/factory to orchetrate the folllwing task: /factory write me an article based on demo/bratwurst-wars.md as the source material, following demo/styleguide.md.  But I also want you to fact check and review the article for me and then present me the final results as files."

---


## Typical Workflow 2

- Evaluate your agents (improve task to agent mapping)
- Improve your agents (improve model to agent mapping)

## Behind the scenes

- Collect data 
- Run auto-research
- Version improvements
- Generate report

---


![bg cover](images/slide_graphics/kiro-hackathon.jpg)

---


## Specification-Driven Development

![w:840](images/slide_graphics/kiro1.jpg)

---


## First Attempt: Specification-Driven


```markdown
R1: The focused pane's title must be rendered with ItemSelected
    styling (blue bg, white fg).

R2: The inactive pane's title must retain default styling
    (bold white text, no background).

R3: Highlighting must update immediately when Tab is pressed,
    with no perceptible delay.

R4: Highlighting must not break the top border alignment -
    the junction character must remain aligned with the separator.
```

Survived planning. Did not survive implementation.

---


## Attempt 2: Tutorials as Specification

- **Tutorial 1** - CLI for individual files
- **Tutorial 2** - groups of files (collections)
- **Tutorial 3** - TUI, with mockups

<br><br>

Much more detailed than a SPECS.md.

---


## Tutorial 1 - Protect a Single File

```bash
$ guard init 0644 root wheel
$ touch test.txt
$ guard add file test.txt

$ cat .guardfile
config:
    guard_mode: "0644"
files:
    - path: ./test.txt
      mode: "0644"
      guard: false

$ sudo guard toggle file test.txt
Guard enabled for test.txt
```

User stories with inputs and outputs.

---


## Tutorial 2 - Protect a Collection

```bash
$ guard create alice
$ guard update alice add alice1.txt alice2.txt shared.txt

$ guard show collection alice
[-] collection: alice (3 files)

$ sudo guard enable collection alice
Guard enabled for collection alice
Guard enabled for alice1.txt
Guard enabled for alice2.txt
Guard enabled for shared.txt
```

Last-operation-wins on shared files; conflict detection on ambiguous toggles.

---


## Tutorial 3 - The TUI Mockup

```text
╔═ Files ═══════════════════════════════╤═ Collections ═════════════════╗
║                                       │                               ║
║ > docs                                │ [G] alice                     ║
║   [G] alice1.txt                      │ [-] bob                       ║
║   [G] alice2.txt                      │                               ║
║   [-] bob1.txt                        │                               ║
║   [G] shared.txt                      │                               ║
║                                       │                               ║
╠═══════════════════════════════════════╧═══════════════════════════════╣
║ ↑↓:Navigate  ←→:Expand  Space:Toggle  Tab:Switch  /:Search  Q:Quit    ║
╚═══════════════════════════════════════════════════════════════════════╝
```

Screen capture as specification.

---


## The AI Said It Was Done


```text
PLACEHOLDER (resolved by C1):
  "The implementation is now complete."
  $ just test
  FAIL: TestGuardAdd_PreservesPermissions
```

But the tests were still failing.

---


<div style="font-size: 1.35em;">

## *"Yes, you are absolutely right!"*

</div>

---


## Tests as Machine-Readable Spec

```bash
test_add_positive() {
    # Setup
    $GUARD_BIN init 000 $(whoami) $(id -gn)
    touch test1.txt
    initial_perms=$(get_file_permissions test1.txt)

    # Run
    $GUARD_BIN add test1.txt

    # Assert
    assert_exit_code $? 0                 "guard add should succeed"
    file_in_registry "$(pwd)/test1.txt"  || fail "not in registry"
    assert_equals "false" "$(get_guard_flag $(pwd)/test1.txt)"
    assert_equals "$initial_perms" "$(get_file_permissions test1.txt)"
}
```

Same specs, different "encoding"

---


## The Bootstrap Script

```bash
chmod -w tests/test-tui-search-001.sh
chflags uchg internal/security/path_validator.go
```

Protecting the first tests and code files manually

---


## Corollary: What Worked, What Didn't

<div class="columns">
<div class="column">

### Models

- Some followed specs better than others
- Top tier ≠ guaranteed
- Over-engineering varies by family
- Deviate from the best specifications

</div>
<div class="column">

### Harnesses

- Claude Code CLI → tightest loop
- Kiro IDE → heavier spec ceremony
- Harness mattered more than model

</div>
</div>

---


## AI Code, Characteristic Mistakes

- Defaults that silently mask missing config
- Fallbacks that hide the real failure
- `log.Print(err)` and keep going
- Over-engineering a 30-line script into a framework
- Moving files between packages on every refactor

---


## More Static Guardrails

<div class="columns">
<div class="column">

- **gofmt** - formatting
- **golangci-lint** - meta-linter suite
- **go vet** / **staticcheck** - bug patterns
- **gocyclo** - cyclomatic complexity
- **gocognit** - cognitive complexity

</div>
<div class="column">

- **semgrep** - forbidden patterns
- **gosec** - security
- **layer tests** - architectural contracts
- **shell + tmux tests** - behavior
- **just ci** - runs them all

</div>
</div>

---


## Semgrep - Restrict Access Patterns

```yaml
- id: registry-load-restricted
  message: |
    Direct calls to registry.Load() are restricted to the
    security layer. All loads must go through Security,
    which performs path validation and tamper detection.
  severity: ERROR
  pattern: $REG.Load()
  paths:
    exclude:
      - "**/*_test.go"
      - "**/internal/security/security.go"
```

One rule. Architecture enforced statically, instead of by hope.

---


## golangci-lint - Many Checks, One Wall

```yaml
linters:
  enable:
    - errcheck       # unchecked errors
    - govet          # suspicious constructs
    - staticcheck    # bug patterns
    - ineffassign    # ineffective assignments
    - unused         # dead code
    - gosec          # security issues
    - revive         # style

issues:
  max-issues-per-linter: 0
  max-same-issues: 0
```

Linters are guardrails the AI can't argue with.

---


## Complexity Gates

```bash
# Cyclomatic - branching depth
gocyclo -over 10 .

# Cognitive - how hard a human (or AI) has to read it
gocognit -over 15 .
```

Two thresholds. Build red until the AI splits the function.

---


## Architecture by Contract


![w:720](images/slide_graphics/PLACEHOLDER-architecture.png)

Enforcing boundaries and dependencies.

---


## Architectural Unit Tests

```go
func TestLayering_NoTuiFilesystemImports(t *testing.T) {
    tuiDir := filepath.Join(repoRoot(t), "internal", "tui")
    forbidden := []string{"/internal/filesystem"}
    assertNoForbiddenStrings(t, tuiDir, forbidden)
}

func TestLayering_NoPrintingInManagerOrFilesystem(t *testing.T) {
    forbidden := []string{"fmt.Print"}
    assertNoForbiddenStrings(t,
        filepath.Join(repoRoot(t), "internal", "manager"), forbidden)
    assertNoForbiddenStrings(t,
        filepath.Join(repoRoot(t), "internal", "filesystem"), forbidden)
}
```

The AI moves files between layers on every refactor. These tests stop it.

---


## Enforcing Quality Gates

---


## Stop Hook

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "just ci-quiet"
          }
        ]
      }
    ]
  }
}
```

Coding agent gets feedback every turn until `just ci-quiet` passes.

---


## Git Pre-Commit Hook

```bash
# .githooks/pre-commit
#!/bin/bash
just ci-quiet
```

Enable once with `git config core.hooksPath .githooks`. Commit is blocked if CI fails.

---


## The Verification Gap

- **42%** of code is AI-generated
- **96%** of developers don't fully trust it
- **48%** validate all of it

<div class="source-link">

Source: [Sonar 2026 State of Code](https://www.sonarsource.com/company/press-releases/sonar-data-reveals-critical-verification-gap-in-ai-coding/)

</div>

---


## The AI Validation Pyramid

---


![w:1120](images/slide_graphics/ai-validation-pyramid-mode-detailed.png)

---


## Internal vs External Quality

- Tests validate intended behavior
- Guardrails enforce internal code quality

---


## You Need Both


![w:560](images/slide_graphics/PLACEHOLDER-external-internal.png)

- Code itself is context - which is why quality matters.
- Tests and guardrails provide feedback that becomes part of the context.

---


## Why It Works


![w:560](images/slide_graphics/PLACEHOLDER-feedback-loop.png)

The agent self-corrects when the environment talks back.

---


## The Shift

- I stopped reviewing code
- I review behavior and AI-generated reports
- Every issue becomes a new test or guardrail

---


## Bonus Patterns - Skills I Use

- **Beyond SOLID Principles** - structural sanity
- **Archibald** - architecture review
- **Security Review** - adversarial assumptions
- **Adversarial Review** - try to crash your own software

---


## Augmenting Reviews with AI-Assisted Reviews

- **Pattern skills** - SOLID, common smells, etc.
- **Specialized agents** - security, input validation, performance, etc.
- **Compliance agents** - check implementation against spec / intent / best practices.


![w:720](images/slide_graphics/PLACEHOLDER-two-agent-triage.png)

One agent finds issues. A second agent says which ones are real.

---


## How to Get Started

1. **Bootstrap:** Init the guardrails with defaults; verify they pass on a green baseline.
2. **Define and document behavior:** Expected behavior as tutorials with examples, inputs, outputs and steps.
3. **Decide and document the architecture:** Components, dependencies and constraints.
4. **Guardrails:** Convert behaviors and architecture into tests and guardrails.
5. **Implementation:** In an environment where the guardrails provide feedback; lock the tests.
6. **Review:** Analyze the results and issues with agents/skills until satisfied. → Update guardrails/add tests.
7. **Iterate:** GOTO 2, add new features by repeating the loop.

---


<div class="columns" style="align-items: center;">
<div class="column" style="justify-content: center;">

<h1>Thank You!</h1>

<div><strong>Github:</strong> github.com/florianbuetow/...</div>
<div>- guard</div>
<div>- ai-guardrails</div>
<div>- claude-code</div>
<br>
<div><strong>LinkedIn:</strong> linkedin.com/in/florianbuetow</div>

</div>
<div class="column" style="align-items: center; justify-content: center;">

![h:360](images/slide_graphics/guard-logo.png)

</div>
</div>

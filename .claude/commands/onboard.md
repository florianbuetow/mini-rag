---
description: Load project context and report readiness
---

Read all of the following files in parallel, then report a 2-sentence summary of the project state:
- CLAUDE.md
- All markdown files in the project root (*.md)
- All markdown files in docs/ (docs/**/*.md)
- pyproject.toml (for dependencies and project metadata)
- config.yaml.template (for current configuration)

After reading, report:
1. What the project does (1 sentence)
2. Current state: branch, recent commits, any uncommitted changes

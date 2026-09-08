---
name: project-checks
description: Run the end-of-session quality gate that mirrors the Claude stop-hook checks.
agent: agent
---

Use `.claude/hooks/run_tests.py` and `.claude/hooks/doc_link_check.py` as the behavioral reference for this command.
Run the same quality gate Claude would enforce before finishing a non-WIP change:
1. `uv run ruff check . --fix`
2. `uv run ruff check .`
3. `uv run pytest -q --cov=awesome_templates --cov-report=term-missing`
4. If the change touched documentation, also run the equivalent doc-link validation described in `.claude/hooks/doc_link_check.py` or `.github/skills/link-check/SKILL.md`.
Treat any additional user input as an optional scope hint or WIP explanation.
Never weaken, skip, or reinterpret a failing check; either fix it or clearly report why the user asked to stop short.

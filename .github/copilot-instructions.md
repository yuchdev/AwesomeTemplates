# GitHub Copilot guidance for Awesome Templates

`AGENTS.md` and `CLAUDE.md` are the repository's detailed engineering guidance.
Read the nearest applicable file before changing code. This file defines the
Copilot-specific integration and does not replace those instructions.

## Native customization layout

This repository keeps `.claude/` as the behavioral source of truth and exposes
equivalent Copilot customizations through GitHub's supported locations:

- `.github/agents/*.agent.md` - specialist custom agents
- `.github/skills/*/SKILL.md` - reusable workflows
- `.github/prompts/*.prompt.md` - loop and quality-gate slash-command workflows
- `.github/hooks/*.json` - automatic lifecycle guards and quality gates
- `.github/workflows/copilot-setup-steps.yml` - cloud-agent environment bootstrap

There is no general `.github/copilot/` content directory. GitHub reserves that
path for settings; runtime state used by the long-running prompt workflows goes
under `.github/copilot/state/` and must remain untracked.

When changing a shared agent, skill, command, loop, or hook behavior, update its
equivalent under `.claude/`, `.junie/`, and `.github/` in the same change.

## Workflow parity

Skills are already exposed as slash commands, so do not add prompt files with
the same names. Copilot has no native recurring loop scheduler. The `implement-milestone`,
`implement-subtasks`, and `update-docs` prompt files therefore read the matching
`.claude/loops/*.md` file as their behavioral specification and continue
iterations in the current session.

The hooks reuse the audited Python implementations in `.claude/hooks/`.
PascalCase Copilot hook event names provide Claude-compatible snake_case event
fields and tool aliases, while individual tool arguments may still be
camelCase. Keep both argument forms supported. Do not convert the event names
to camelCase without also adapting the scripts' input protocol.

## Safety and completion

- Never commit secrets; the pre-edit hook blocks recognized credential shapes.
- Never run destructive or production-targeting shell commands automatically.
- Keep `Optional[T]` annotations; do not introduce `T | None`.
- Before completing code work, run:
  1. `uv run ruff check . --fix`
  2. `uv run ruff check .`
  3. `uv run pytest -q --cov=awesome_templates --cov-report=term-missing`
- For template changes, also run
  `uv run pytest tests/test_integration_real_repo.py`.

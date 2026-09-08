# Junie playbook for Claude-parity automation

This repository keeps `.claude/` as the reference implementation for maintainer automation. Junie should mirror the same safety and quality behavior, but use Junie's native structure:

- custom agents in `.junie/agents/`
- agent skills in `.junie/skills/`
- manually-invoked workflows in `.junie/commands/`
- shared always-on guidance here in `.junie/playbook.md`

## Hook parity policy

Junie's documented project structure gives us first-class agents, skills, commands, and guideline files. It does **not** give this repository a stable, documented project-local hook directory that cleanly matches Claude's `settings.json` hook wiring, so do **not** invent one here.

Instead, treat `.claude/settings.json` and the scripts in `.claude/hooks/` as the behavioral source of truth and apply their intent manually in Junie sessions:

### Session-start parity

At the start of a substantial task, gather the same live context that `.claude/hooks/session_start.py` injects for Claude:

- current git branch
- last 5 commits
- open P0/P1 issues when `gh` is authenticated
- the reminder to delegate sensitive work to the appropriate specialist agent

### Bash-guard parity

Before running shell commands, follow `.claude/hooks/guard_bash.py`:

- refuse destructive commands such as recursive force deletes, raw-disk writes, destructive SQL, force-pushes, and hard resets
- treat anything aimed at `prod` or `production` as blocked unless the user explicitly wants a production action and has acknowledged the risk
- when a command would have been blocked by Claude's bash guard, stop and ask the user rather than attempting a workaround

### Pre-edit secret-scan parity

Before writing or editing content that might contain credentials or tokens, apply the intent of `.claude/hooks/secret_scan.py`:

- never add real secrets to tracked files
- prefer environment variables, placeholders, or documented secret managers
- when in doubt, run the repository's secret-scan workflow before finalizing the change

### Post-edit formatting and style parity

After code edits, follow the intent of `.claude/hooks/post_edit_format.py` and `.claude/hooks/style_fixes.py`:

- Python edits should be formatted and lint-fixed with the repository's `ruff` commands
- keep the repository's typing convention of `Optional[T]`, never `T | None`
- use the existing code style instead of introducing drive-by reformatting

### End-of-session quality gate parity

Before you consider a non-WIP code task done, follow the same gate `.claude/hooks/run_tests.py` enforces:

1. `uv run ruff check . --fix`
2. `uv run ruff check .`
3. `uv run pytest -q --cov=awesome_templates --cov-report=term-missing`

For documentation-heavy changes, also apply the equivalent of `.claude/hooks/doc_link_check.py` and use `/link-check` or `/update-docs` when appropriate.

### Review and audit parity

When Claude would have relied on its post-edit review hooks, use the Junie-native commands and agents instead:

- `/secret-scan`
- `/dep-audit`
- `/link-check`
- `/project-checks`
- `/pr-review`

These workflows exist to preserve the Claude behavior while keeping the Junie side in Junie's documented agent/skill/command layout.

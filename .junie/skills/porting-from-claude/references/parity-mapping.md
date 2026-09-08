# Claude → Junie parity mapping

Use this table to classify each Claude artifact before editing anything.

| Claude source | Junie target in this repo | Port shape | Notes |
|---|---|---|---|
| `.claude/agents/<name>.md` | `.junie/agents/<name>.md` | near-1:1 adaptation | Preserve role and guardrails; swap Claude-only workflow references for Junie skills/commands. |
| `.claude/skills/<name>/SKILL.md` | `.junie/skills/<name>/SKILL.md` | mirrored skill tree | Port `references/` and `examples/` with it; repair internal links. |
| `.claude/skills/<name>/references/*` | `.junie/skills/<name>/references/*` | mirrored support files | Keep relative layout stable so `SKILL.md` links do not drift. |
| `.claude/skills/<name>/examples/*` | `.junie/skills/<name>/examples/*` | mirrored support files | Treat example content as part of the skill, not optional garnish. |
| `.claude/loops/<name>.md` | `.junie/commands/<name>.md` | thin wrapper | Point back to the Claude loop as the authority, adapt `$prompt`, state paths, and self-rescheduling semantics. |
| `.claude/settings.json` | `.junie/playbook.md` plus relevant commands/skills | behavior extraction | Read it as the index of what Claude enforced automatically. |
| `.claude/hooks/session_start.py` | `.junie/playbook.md` | manual parity guidance | In this repo, session-start behavior is documented and applied manually at the start of substantial tasks. |
| `.claude/hooks/guard_bash.py` | `.junie/playbook.md` | manual parity guidance | Preserve the block conditions; do not try to emulate them with an invented hook file. |
| `.claude/hooks/secret_scan.py` | `.junie/playbook.md` + `.junie/skills/secret-scan/` + `/secret-scan` | split behavior | The skill explains the manual sweep; the playbook preserves the pre-edit intent. |
| `.claude/hooks/post_edit_format.py` / `.claude/hooks/style_fixes.py` | `.junie/playbook.md` + `/project-checks` | split behavior | Preserve formatting and style expectations through workflow guidance and final checks. |
| `.claude/hooks/run_tests.py` | `.junie/playbook.md` + `/project-checks` | split behavior | Preserve the fixed `ruff` + `pytest` gate; do not reinterpret failures away. |
| Claude permission allow/deny lists | prose guardrails only | manual parity note | This repo has no equivalent project-local Junie permission schema to copy mechanically. |

## Recommended port order

1. Read `.claude/settings.json` and extract hook behavior.
2. Update `.junie/playbook.md` if the behavior is new.
3. Mirror shared skills and their support files.
4. Add or update command wrappers for loops.
5. Port agents that depend on those skills and commands.

## Repo-specific constraint

For this repository, prefer `.junie/playbook.md` as the catch-all guidance file. While a prior
roadmap spike noted `.junie/guidelines.md` as a convention observed in another project, this repo's
actual established source of truth is [../../../playbook.md](../../../playbook.md).

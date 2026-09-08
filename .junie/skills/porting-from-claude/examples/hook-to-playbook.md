# Example: port hook behavior into the playbook

This repo's hook parity pattern starts from
[../../../../.claude/settings.json](../../../../.claude/settings.json), not from a Junie hook file.

## Source inventory

`settings.json` wires these Claude behaviors:

- `SessionStart` → `.claude/hooks/session_start.py`
- `PreToolUse(Bash)` → `.claude/hooks/guard_bash.py`
- `PreToolUse(Write|Edit|MultiEdit)` → `.claude/hooks/secret_scan.py`
- `PostToolUse(Write|Edit|MultiEdit)` → formatting, style, dep audit, and doc-link checks
- `Stop` → `.claude/hooks/run_tests.py` plus `.claude/hooks/doc_link_check.py`

## Junie port shape

Do **not** create `.junie/hooks/` and do **not** copy the JSON.

Instead, preserve the same behavior in three places:

1. [../../../playbook.md](../../../playbook.md)
   - session-start parity
   - bash-guard parity
   - pre-edit secret-scan parity
   - post-edit formatting/style parity
   - end-of-session quality gate parity
2. [../../../commands/project-checks.md](../../../commands/project-checks.md)
   - explicit reusable command for the stop-hook quality gate
3. Existing Junie skills such as
   [../../../skills/secret-scan/SKILL.md](../../../skills/secret-scan/SKILL.md) and
   [../../../skills/link-check/SKILL.md](../../../skills/link-check/SKILL.md)
   - deeper operator instructions for the manual workflow Claude performed automatically

## Why this is the efficient port

- One playbook section can cover the whole class of hook behavior instead of scattering duplicate
  prose across many agents.
- Commands and skills hold the detailed "how" only where repeatable workflows need it.
- The Claude hook scripts remain the clearest executable definition of the original behavior, so the
  Junie side can point at them instead of restating every detail.

## Pattern to reuse

When a Claude artifact is automatic and cross-cutting, ask:

1. Is this an always-on rule? Put the parity rule in `playbook.md`.
2. Is this a repeatable operator workflow? Add or update a Junie command.
3. Is this deep procedural guidance? Add or update a Junie skill.

If the answer is "all three," split the behavior exactly that way instead of looking for a fake 1:1
hook file.

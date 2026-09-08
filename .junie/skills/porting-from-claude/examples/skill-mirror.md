# Example: mirror a Claude skill tree into `.junie/skills/`

The `secret-scan` skill pair is the cleanest existing example:

- Claude source: [../../../../.claude/skills/secret-scan/SKILL.md](../../../../.claude/skills/secret-scan/SKILL.md)
- Junie target: [../../../skills/secret-scan/SKILL.md](../../../skills/secret-scan/SKILL.md)
- Shared support files:
  - [../../../../.claude/skills/secret-scan/references/pattern-catalog.md](../../../../.claude/skills/secret-scan/references/pattern-catalog.md)
  - [../../../skills/secret-scan/references/pattern-catalog.md](../../../skills/secret-scan/references/pattern-catalog.md)

## Mirroring steps

1. Copy the Claude skill directory shape, not just the top-level `SKILL.md`.
2. Preserve relative paths like `references/pattern-catalog.md` so existing links keep working.
3. Update prose that names the execution surface:
   - Claude slash-command names become Junie command or skill names where relevant.
   - If the real implementation is still a Claude-owned script or hook, say that explicitly.
4. Re-run link validation for the new skill directory.

## Why this is the efficient port

- The skill stays grounded in already-reviewed Claude content.
- Examples and references remain close to the operator instructions that use them.
- Future parity updates are easy to spot by diffing the matching Claude and Junie directories.

## Anti-pattern

Do **not** port only `SKILL.md` and drop the support files. That leaves dangling links or silent loss
of operator context and makes the Junie copy drift almost immediately.

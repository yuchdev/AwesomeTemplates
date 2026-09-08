# Existing Claude → Junie patterns in this repository

These files are the best concrete examples to copy before inventing a new port shape.

## Hook parity source and destination

- **Claude source:** [../../../../.claude/settings.json](../../../../.claude/settings.json)
- **Junie destination:** [../../../playbook.md](../../../playbook.md)

This is the canonical answer to "where do Claude hooks go in Junie here?" The playbook carries the
behavioral rules for session start, bash guardrails, secret scanning, formatting/style, and the
end-of-session quality gate without claiming Junie has a project-local hooks directory.

## Loop → command wrappers

- [../../../../.claude/loops/update-docs.md](../../../../.claude/loops/update-docs.md) →
  [../../../commands/update-docs.md](../../../commands/update-docs.md)
- [../../../../.claude/loops/implement-milestone.md](../../../../.claude/loops/implement-milestone.md) →
  [../../../commands/implement-milestone.md](../../../commands/implement-milestone.md)

These show the preferred wrapper style:

- point back to the Claude loop as authoritative,
- treat `$prompt` as the loop argument,
- move state to `.junie/state/...`,
- translate Claude loop or slash-command spellings into Junie command forms,
- remind the reader that hook parity now lives in the playbook.

## Skill mirrors

- [../../../../.claude/skills/secret-scan/SKILL.md](../../../../.claude/skills/secret-scan/SKILL.md) →
  [../../../skills/secret-scan/SKILL.md](../../../skills/secret-scan/SKILL.md)
- [../../../../.claude/skills/link-check/SKILL.md](../../../../.claude/skills/link-check/SKILL.md) →
  [../../../skills/link-check/SKILL.md](../../../skills/link-check/SKILL.md)

These pairs show that a Junie skill can still name a Claude-owned implementation detail when that is
the real shared engine. The port is about keeping the workflow honest, not pretending every runtime
surface moved.

## Agent mirrors

- [../../../../.claude/agents/docs-updater.md](../../../../.claude/agents/docs-updater.md) →
  [../../../agents/docs-updater.md](../../../agents/docs-updater.md)
- [../../../../.claude/agents/create-from-template.md](../../../../.claude/agents/create-from-template.md) →
  [../../../agents/create-from-template.md](../../../agents/create-from-template.md)

These pairs show the preferred agent strategy: keep the role and workflow intact, adapt the
frontmatter and linked Junie skills, and leave repo-specific guardrails in place.

## Design record

For the file-layout decision behind these patterns, see
[/docs/roadmap/0001-alternative-harness-support/08.0-junie-porting-session/01-spike-junie-porting-target.md](/docs/roadmap/0001-alternative-harness-support/08.0-junie-porting-session/01-spike-junie-porting-target.md).

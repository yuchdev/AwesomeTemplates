---
name: porting-from-claude
description: Use when a repository already has `.claude/` agents, skills, hooks, or loops and you need the equivalent Junie-native structure with minimal drift. Maps each Claude artifact to the right `.junie/` target and calls out the unsupported cases that must stay as documented manual parity.
---

# Porting From Claude

Port repository-local Claude automation into Junie by preserving **behavior** first and file shape
second. Reuse the Claude source aggressively when there is an obvious 1:1 mapping, and only write
new Junie prose where Claude relied on a construct Junie does not expose directly in this repo.

Use this skill together with [../../playbook.md](../../playbook.md). For the repo's recorded design
decision about Junie's file layout, see
[/docs/roadmap/0001-alternative-harness-support/08.0-junie-porting-session/01-spike-junie-porting-target.md](/docs/roadmap/0001-alternative-harness-support/08.0-junie-porting-session/01-spike-junie-porting-target.md).

## Quick map

- [references/parity-mapping.md](references/parity-mapping.md) - canonical Claude → Junie target map
- [references/repo-patterns.md](references/repo-patterns.md) - concrete mappings already present in
  this repository
- [examples/hook-to-playbook.md](examples/hook-to-playbook.md) - port hook behavior without inventing
  `.junie/hooks/`
- [examples/loop-to-command.md](examples/loop-to-command.md) - turn a Claude loop into a Junie command
- [examples/skill-mirror.md](examples/skill-mirror.md) - mirror a Claude skill tree into `.junie/`

## Efficiency rules

1. **Inventory before editing.** Build a matrix of every relevant Claude artifact:
   `.claude/settings.json`, `.claude/hooks/*.py`, `.claude/agents/*.md`, `.claude/skills/*`, and
   `.claude/loops/*.md`.
2. **Prefer same-name peers.** If `.junie/<kind>/<name>` already exists, update it instead of adding
   a second variant.
3. **Port shared dependencies first.** Hook-parity guidance and reusable skills should land before
   the agents that reference them.
4. **Keep wrappers thin.** A Junie command that points back to a Claude loop is better than a large,
   duplicated workflow document.
5. **Do not simulate unsupported features.** If Claude used hooks or permission settings, carry the
   intent into `.junie/playbook.md` or the relevant skill/command instead of fabricating a fake file
   format.

## Steps

1. **Read the behavioral source.** Start with `.claude/settings.json` plus any Claude artifact you
   are porting. For this repo, also read `.junie/playbook.md` because it already defines the agreed
   hook-parity policy.

2. **Classify each artifact by port shape** using
   [references/parity-mapping.md](references/parity-mapping.md):
   - agent → agent
   - skill tree → mirrored skill tree
   - loop → command wrapper
   - hook/settings behavior → playbook, command, or skill guidance

3. **Capture hook parity first.** Extract the behavior Claude was enforcing automatically at session
   start, before shell use, before edits, after edits, and at stop. Decide where each rule belongs in
   Junie:
   - `.junie/playbook.md` for always-on guidance,
   - a Junie command when the behavior is a repeatable workflow,
   - a skill when the behavior needs deeper how-to instructions.

4. **Mirror skills with their support files.** When a Claude skill has `references/` or `examples/`,
   port them together. A skill that links to missing support files is incomplete even if `SKILL.md`
   itself exists.

5. **Convert loops into commands.** Use the existing command pattern in this repo:
   name the Claude loop as the authority, treat `$prompt` as the loop argument, move any state path to
   `.junie/state/`, and replace self-rescheduling with continued iteration in the current Junie
   session.

6. **Port agents last.** Once the shared skills and commands exist, adapt the Claude agent to Junie by
   changing only what is required:
   - update frontmatter,
   - point at Junie skills/commands,
   - keep the original role, guardrails, and stop conditions.

7. **Verify documentation integrity.** Run link checks over the files you added or changed and confirm
   that every new `references/` and `examples/` link resolves.

## What not to do

- Do **not** create `.junie/hooks/` in this repository.
- Do **not** copy `.claude/settings.json` into a pretend Junie settings file.
- Do **not** rewrite a Claude workflow from scratch if a thin wrapper would stay more maintainable.
- Do **not** drop examples or reference files from a skill and call the port complete.
- Do **not** rename well-established artifacts without a strong reason.

## Output

Report the port as:

```markdown
## Claude → Junie port

### Added
- <new Junie paths>

### Updated
- <existing Junie path>: <new parity added>

### Behavioral parity carried manually
- <Claude hook/settings behavior>: <where Junie preserves it>

### Open questions
- <only if something needs human judgement>
```

## Completion checklist

- [ ] Every relevant Claude source artifact inventoried before editing
- [ ] Each artifact mapped to a concrete Junie target or an explicit manual-parity note
- [ ] Skill ports include `references/` and `examples/` when the Claude source had them
- [ ] Loop ports are thin wrappers that point back to the Claude workflow
- [ ] Hook behavior preserved via `.junie/playbook.md`, commands, or skills - never `.junie/hooks/`
- [ ] Link validation run on the touched Markdown files

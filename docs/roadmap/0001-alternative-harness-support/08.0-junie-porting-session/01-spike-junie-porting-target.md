# 01 - Spike: Junie's own agent/skill config convention (outcome 1 only)

**Parent task:** 08.0 Junie porting session (headless)
**State:** ✅ Complete (2026-08-30) - task 03.0 landed on outcome 1, so this
subtask applies in full.
**Depends on:** task 03.0 outcome 1
**Blocks:** 02 (this task)

## Objective

Same shape as task 07.0 subtask 01, for Junie: determine where JetBrains'
Junie conventionally expects repository-level agent/skill-like configuration
to live, so `port.py`'s prompt can name a concrete target. Research only - no
source file changes.

## Questions to answer

Identical in kind to task 07.0 subtask 01's four questions, adapted to
whatever Junie's actual headless surface (confirmed by task 03.0) turns out to
support:

1. Does Junie have an established, documented convention for repository-scoped
   agent/skill configuration, distinct from its IDE-embedded interactive
   experience?
2. If yes, what shape (single file, directory, structured config)?
3. Does writing to that location require anything beyond the tool/permission
   grant task 03.0's outcome-1 contract already established for the
   marker-research use case?
4. Is there a meaningful agent/skill distinction in Junie's own model, or a
   flatter single concept?

## Constraints

- Same as task 07.0 subtask 01: confirm against current JetBrains
  documentation, do not guess, and record "no fixed convention" as a
  legitimate finding if that's the case.

## Success criteria

- [x] This file records a dated, sourced answer to all four questions, or an
      explicit "no fixed convention" conclusion - only if task 03.0 landed on
      outcome 1. If task 03.0 landed on outcome 2, mark this subtask N/A here
      and point to that finding instead of leaving it looking unstarted.
- [x] `status.md` reflects the outcome before subtask 02 starts.

## Findings (2026-08-30)

Confirmed two ways against the installed standalone `junie` CLI (`Junie version: 26.8.24`): its
own `--help` text, and - stronger evidence - direct filesystem inspection of real, populated
`.junie/` directories already present in several independent projects on this machine (this
repo's own `.junie/`, plus `AegisSwr`, `CanonixEngine`, and `UrlShortener`), which is empirical
confirmation of the convention actually being used, not just documented as a flag.

**Q1. Established convention distinct from the IDE-embedded experience - yes, confirmed both
ways.** `--help`'s "Skills"/"Custom agents"/"Commands"/"Configuration" option groups each name a
"default locations (per user / per project)" toggle (`--skill-default-locations`,
`--agent-default-locations`, `--command-default-locations`, `--config-default-locations`), and
the config flag spells out the exact project-level path pattern: `<project>/.junie/config.json`
(alongside `~/.junie/config.json` for the user-level default). Filesystem inspection confirms
`.junie/` is the real, populated project-root convention this repo (and several others on this
machine) already uses - not merely a documented-but-unused flag.

**Q2. Shape - directly observed, not inferred:**
- **Agents:** `.junie/agents/<name>.md` - flat, one Markdown file per agent. Observed in this
  repo's own `.junie/agents/` (13 files, e.g. `python-expert.md`, `security-auditor.md`,
  `feature-reviewer.md`) and in `AegisSwr`/`CanonixEngine`/`UrlShortener`. This shape exactly
  mirrors `.claude/agents/`'s own convention 1:1.
- **Skills:** `.junie/skills/<name>/SKILL.md` - one directory per skill containing a `SKILL.md`
  file (some skills additionally carry a `references/` or `examples/` subdirectory). Observed
  identically across all four sampled projects (e.g. `.junie/skills/pr-review/SKILL.md`,
  `.junie/skills/secret-scan/SKILL.md` plus `secret-scan/references/`). This shape exactly mirrors
  `.claude/skills/`'s own convention 1:1 - `catalog.py`'s existing "a skill is a directory
  containing a `SKILL.md`" rule applies verbatim.
- **Commands:** `.junie/commands/` - observed as a populated directory in `CanonixEngine` (not
  present in the other three sampled projects, so its use may be more occasional/project-specific
  than agents/skills) - a plausible candidate for a "loops"-adjacent concept (a saved, reusable
  command), though its internal file shape was not inspected in this pass.
- **Guidelines:** `.junie/guidelines.md` - a single Markdown file, observed in the `Legend`
  project - a repo-instructions-style catch-all, parallel to Copilot's
  `.github/copilot-instructions.md`/`AGENTS.md` role.
- **MCP:** `.junie/mcp/` was observed in `AegisSwr` (MCP server configuration) - not one of the
  four Claude-authored kinds, noted only for completeness.
- **Hooks:** no `.junie/hooks/` (or any similarly-named directory) was observed in any of the four
  sampled projects, and `--help`'s full option listing has no `--hook-location`/
  `--hook-default-locations` flag family the way skills/agents/commands each do. This is recorded
  as a genuine, disclosed absence within the scope of what was sampled (four projects' top-level
  `.junie/` contents, not an exhaustive survey) - not fabricated as "confirmed no convention
  exists everywhere," but consistent enough across independent samples to treat as the working
  answer for the porting hint.

**Q3. Additional tool/permission grant needed? No - for a stronger reason than Copilot's answer.**
Task 03.0's outcome-1 spike already established that Junie's CLI exposes **no tool/permission-
restriction mechanism of any kind** - a headless Junie session's action scope is bounded only by
its working directory (`--project`), not by an allowlist. Since nothing is gated in the first
place, there is nothing additional to grant for writing to `.junie/agents/`, `.junie/skills/`,
etc. - the existing (documented, if unenforced-by-flag) constraint stands unchanged.

**Q4. Meaningful agent/skill distinction - yes, confirmed both by `--help`'s separate
`--agent-location`/`--skill-location`/`--command-location` flag families and by the empirically
observed directory shapes actually differing (agents: flat `.md` files; skills: directories with
`SKILL.md`) - not a single flattened concept. `commands` is a plausible third, distinct concept
worth naming separately in the hint rather than folding into either agents or skills.

**Resulting `porting_target_hint` for subtask 02:** name `.junie/agents/<name>.md` for agents,
`.junie/skills/<name>/SKILL.md` for skills, and `.junie/commands/` as a candidate (not confirmed
by this pass to have a fixed internal shape) for anything loop-like; leave hooks with the same
explicit "no fixed convention, say so" escape hatch Copilot's hint already uses, and name
`.junie/guidelines.md` as the catch-all for anything else.

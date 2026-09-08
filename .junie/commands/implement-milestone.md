---
description: Drive a roadmap milestone to completion using the Claude loop as the behavioral source of truth.
allowPromptArgument: true
---

Read `.claude/loops/implement-milestone.md` and follow it as the authoritative workflow.
Treat `$prompt` as the milestone argument.
Apply these Junie adaptations while preserving the Claude behavior:
- Use `.junie/state/implement-milestone-{milestone-slug}.json` for any derived cursor or resumable state you create.
- When the Claude loop says to reschedule itself, continue iterating within the current Junie session until the milestone completes or you hit a stop-and-ask gate.
- Invoke the Junie command forms `/implement-subtasks`, `/verify-subtask`, `/test-gap`, `/pr-review`, and `/update-docs` instead of Claude `/loop ...` or slash-command spellings.
- Keep `.claude/settings.json` and `.junie/playbook.md` in mind for hook-parity checks that Claude would have received automatically.
If `$prompt` is empty or ambiguous, stop and ask the user to disambiguate the milestone.

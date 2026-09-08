---
description: Drive one roadmap task through its subtask queue using the Claude loop as the behavioral source of truth.
allowPromptArgument: true
---

Read `.claude/loops/implement-subtasks.md` and follow it as the authoritative workflow.
Treat `$prompt` as the task argument.
Apply these Junie adaptations while preserving the Claude behavior:
- Use `.junie/state/implement-subtasks-{task-slug}.json` for any derived cursor or resumable state you create.
- When the Claude loop says to reschedule itself, continue iterating within the current Junie session until the task completes or you hit a stop-and-ask gate.
- Use the Junie command forms `/verify-subtask`, `/test-gap`, `/pr-review`, and `/update-docs` instead of Claude loop or slash-command names.
- Apply the automation expectations from `.junie/playbook.md` where Claude relied on automatic hooks.
If `$prompt` is empty or ambiguous, stop and ask the user to identify the task.

---
description: Run the iterative documentation maintenance workflow using the Claude loop as the behavioral source of truth.
allowPromptArgument: true
---

Read `.claude/loops/update-docs.md` and follow it as the authoritative workflow.
Treat `$prompt` as an optional doc path. If omitted, run scan mode.
Apply these Junie adaptations while preserving the Claude behavior:
- Use `.junie/state/update-docs-scan.json` for any derived cursor or resumable scan state you create.
- When the Claude loop says to reschedule itself, keep iterating within the current Junie session until the workflow converges or you hit a review-only remainder.
- Use the Junie command forms `/link-check` and `/doc-xref` where the Claude loop refers to Claude slash commands or loops.
- Keep `.junie/playbook.md` in mind for the hook-parity checks that Claude would normally receive automatically.

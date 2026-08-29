# 01 - Spike: Copilot's own agent/skill config convention

**Parent task:** 07.0 Copilot porting session
**State:** ⬜ Not started
**Depends on:** task 02.0 (Copilot's confirmed non-interactive/tool-allowlist
contract - this spike is narrower, just the output-location question)
**Blocks:** 02 (this task)

## Objective

Determine where GitHub Copilot's own tooling conventionally expects
repository-level agent/skill/instruction configuration to live, so
`port.py`'s prompt can name a concrete target instead of a generic "wherever
is idiomatic for you" sentence. This is research, not implementation - no
source file changes.

## Questions to answer

1. Does Copilot have an established, documented convention for
   repository-scoped custom instructions or agent-like configuration (for
   example, a well-known file or directory GitHub's own docs point at)?
2. If yes: is it a single file, a directory of files, or something more
   structured (front-matter, JSON/YAML config)? Record enough shape detail
   that a prompt sentence naming it would actually help Copilot, not just
   gesture at it.
3. Does writing to that location require any tool-allowlist entry beyond what
   task 02.0's confirmed contract already grants for the marker-research use
   case (`Read`/`Grep`/`Glob`/`Edit`/`TodoWrite`)? Porting needs `Write`
   (task 06.0 subtask 01's `PORTING_TOOLS`) to a path that, unlike marker
   research, is NOT under `.claude/` - confirm Copilot's tool-allowlist syntax
   permits scoping `Write` to (or excluding it from) specific paths if that
   matters for safety, or whether it's an all-or-nothing grant.
4. Is there a meaningful difference between "agent" and "skill" equivalents in
   Copilot's own model, or does it use a single flatter concept for both?
   (This affects only the wording of the hint, not this codebase's structure -
   Claude's four-kind split stays canonical regardless of the answer.)

## Constraints

- Confirm against GitHub's current, published documentation - this is a
  fast-moving product area; re-verify rather than relying on possibly-stale
  general knowledge.
- If no fixed convention exists, that is a legitimate answer - record it and
  let `porting_target_hint` stay `None` (task 01.0 subtask 01's default).

## Success criteria

- [ ] This file records a dated, sourced answer to all four questions, or an
      explicit "no fixed convention, hint stays generic" conclusion.
- [ ] `status.md` reflects the spike's outcome before subtask 02 starts.

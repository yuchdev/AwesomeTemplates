# 01 - Spike: Junie's own agent/skill config convention (outcome 1 only)

**Parent task:** 08.0 Junie porting session (headless)
**State:** ⬜ Not started - **only applicable if task 03.0 landed on outcome
1** (a confirmed headless CLI mode exists). If task 03.0 landed on outcome 2,
skip this subtask entirely and go straight to subtask 02's outcome-2 branch.
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

- [ ] This file records a dated, sourced answer to all four questions, or an
      explicit "no fixed convention" conclusion - only if task 03.0 landed on
      outcome 1. If task 03.0 landed on outcome 2, mark this subtask N/A here
      and point to that finding instead of leaving it looking unstarted.
- [ ] `status.md` reflects the outcome before subtask 02 starts.

# 01 - Spike: does Junie have a headless CLI mode?

**Parent task:** 03.0 `junie` adapter
**State:** ⬜ Not started
**Depends on:** task 01.0
**Blocks:** 02 (this task); indirectly gates task 08.0 (Junie porting session,
which the milestone requires to run headless)

## Objective

Determine, against JetBrains' own current Junie documentation and (if
installable in this environment) the product itself, whether Junie exposes a
supported, documented, **non-interactive** invocation mode suitable for
unattended use in `generate`'s pipeline - as opposed to only an IDE-embedded,
interactive agent experience. This is research, not implementation - no source
file changes.

## Questions to answer

1. Does JetBrains publish a CLI or headless/CI mode for Junie at all, under
   any name? (Check current JetBrains documentation and release notes - this
   is a fast-moving product area, so re-verify rather than relying on
   knowledge that may predate a relevant release.)
2. If yes: what is its invocation contract - binary name, non-interactive
   flag, prompt-delivery mechanism (stdin vs. argument), tool/permission
   configuration, model selection (if any), and exit-code/output contract?
   Answer the same five categories of question task 02.0 subtask 01 asks for
   Copilot, adapted to whatever Junie's actual surface turns out to be.
3. If no: is there a stated roadmap or public signal that one is planned? Not
   load-bearing for this task's outcome, but worth recording for whoever
   revisits this later.

## Outcome and next step

- **Outcome 1 (headless mode exists and is documented):** record its
  confirmed contract in this file; subtask 02 builds `_build_junie_command` +
  a fully-functional `_JUNIE` registration from it, following task 02.0
  subtask 02's pattern.
- **Outcome 2 (no such mode exists):** record that finding explicitly in this
  file and in `status.md`; subtask 02 ships the registered-but-unavailable stub
  instead. This is the expected, legitimate outcome per
  [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s own
  framing - do not treat it as a blocker requiring escalation, and do not
  invent a contract to avoid landing on it.

## Constraints

- Confirm against current, dated sources - cite what was checked and when in
  this file, since "Junie has no CLI mode" is exactly the kind of fact that
  can go stale.
- Do not guess a plausible-sounding CLI contract in the absence of
  confirmation - outcome 2 is an acceptable, documented result; a fabricated
  outcome 1 is not.

## Success criteria

- [ ] This file records a dated, sourced answer: either outcome 1 with a
      confirmed contract, or outcome 2 with the evidence that no such mode
      exists (or could not be confirmed) as of the check date.
- [ ] `status.md` reflects the spike's outcome before subtask 02 starts.

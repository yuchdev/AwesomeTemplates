# 02 - Wire the confirmed hint into `_COPILOT`

**Parent task:** 07.0 Copilot porting session
**State:** ⬜ Not started
**Depends on:** 01 (this task's confirmed answers)
**Blocks:** none

## Objective

Set `_COPILOT.porting_target_hint` in `src/awesome_templates/harnesses.py`
from subtask 01's findings, and adjust `_build_copilot_command` if subtask 01
found that porting's `Write`-outside-`.claude/` need requires a different
tool-allowlist entry than the marker-research tool set already covers.

## Changes to `src/awesome_templates/harnesses.py`

`Harness` is `frozen=True` (task 01.0 subtask 01), so update the module-level
instance directly rather than mutating it:

```python
_COPILOT = Harness(
    name="copilot",
    binary_names=("copilot",),
    default_model=...,  # from task 02.0
    prompt_via=...,       # from task 02.0
    forwards_anthropic_key=False,
    build_command=_build_copilot_command,
    porting_target_hint=(
        "<subtask 01's confirmed sentence, e.g. 'Write repository-level "
        "instructions to <path>, one entry per ported agent/skill.'>"
        if False  # replace with the real confirmed value or leave `None`
        else None
    ),
)
```

If subtask 01 found no fixed convention, leave `porting_target_hint=None`
explicitly (with a one-line comment citing subtask 01's document) rather than
omitting the field silently - a future reader should be able to tell "this
was checked and found nothing" apart from "this was never checked."

If subtask 01 found that `Write` needs a differently-scoped tool-allowlist
entry for porting than for marker research, `_build_copilot_command` (task
02.0 subtask 02) needs a branch or an additional parameter to express it - the
exact shape depends entirely on subtask 01's finding about Copilot's
allowlist syntax; do not guess it here ahead of that finding.

## Constraints

- No change to `_COPILOT`'s behavior for the `--harness copilot` (marker-
  research) path - this subtask only affects the `--port-to copilot` path,
  via `porting_target_hint` and, if needed, an additive `build_command`
  branch that marker research never triggers.
- Same coding constraints as prior harnesses.py subtasks.

## Success criteria

- [ ] `harnesses.get("copilot").porting_target_hint` reflects subtask 01's
      finding (a concrete sentence, or an explicitly-commented `None`).
- [ ] `port.build_porting_prompt(..., harness=harnesses.get("copilot"))`
      embeds the hint verbatim when set.
- [ ] The `--harness copilot` (non-porting) path's constructed command is
      unchanged by this subtask.
- [ ] `ruff check src/` clean.

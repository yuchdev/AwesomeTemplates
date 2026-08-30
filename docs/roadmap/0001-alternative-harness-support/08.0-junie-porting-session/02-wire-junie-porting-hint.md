# 02 - Wire the confirmed hint into `_JUNIE`, or confirm the honest-rejection path

**Parent task:** 08.0 Junie porting session (headless)
**State:** ✅ Complete (2026-08-30) - Outcome 1
**Depends on:** 01 (outcome 1) or task 03.0's outcome-2 stub directly
**Blocks:** none

## Objective

Under outcome 1: same as task 07.0 subtask 02, adapted to `_JUNIE` - set
`porting_target_hint` from subtask 01's finding, adjusting
`_build_junie_command` only if the porting `Write` scope needs it.

Under outcome 2: verify (do not newly implement) that `--port-to junie` is
already unreachable via task 03.0's registered-but-unavailable `_JUNIE`
(`binary_names=()`, so `harnesses.find_harness` always returns `None`), and
that task 06.0 subtask 03's dispatch surfaces the same honest message
`--harness junie` gives, not a generic one. This subtask's job under outcome 2
is confirmation and, if needed, a message-text fix in `cli.py` - not new
`harnesses.py` code.

## Changes to `src/awesome_templates/harnesses.py` (outcome 1 only)

```python
_JUNIE = Harness(
    name="junie",
    binary_names=(...,),   # from task 03.0 outcome 1
    default_model=...,      # from task 03.0 outcome 1
    prompt_via=...,          # from task 03.0 outcome 1
    forwards_anthropic_key=False,
    build_command=_build_junie_command,
    porting_target_hint=(
        "<subtask 01's confirmed sentence>"
    ),
)
```

## Verification (outcome 2 only)

No `harnesses.py` change. Confirm in a REPL or a quick script:

```python
from awesome_templates import harnesses

assert harnesses.find_harness(harnesses.get("junie")) is None
```

Then trace `cli.py`'s `--port-to junie` path (task 06.0 subtask 03's
validation plus `port.port_tree_headless`'s `RuntimeError` on a missing
binary) and confirm the error message reaching the user says "Junie has no
supported headless CLI mode yet" (task 04.0 subtask 03's message), not a
generic "not found on PATH" - if `port_tree_headless`'s own `RuntimeError`
text differs from `resolve_tree_headless`'s harness-aware message, align it
(e.g. by having `port_tree_headless` raise the same
`harness_obj.binary_names`-empty-aware message, or by having `cli.py`'s
`--port-to` dispatch reuse task 04.0 subtask 03's message-selection logic
rather than a plain `_fail(str(exc))`).

## Constraints

- Outcome 2 adds no workaround, no interactive fallback, and no new
  `harnesses.py` entry beyond what task 03.0 already registered.
- Outcome 1 follows the same coding constraints as task 07.0 subtask 02.

## Success criteria

**Outcome 1:**
- [x] `harnesses.get("junie").porting_target_hint` reflects subtask 01's
      finding.
- [x] The `--harness junie` (non-porting) path's constructed command is
      unchanged by this subtask.

**Outcome 2 (not applicable - outcome 1 landed):**
- [ ] `generate --resolve-markers --port-to junie` fails with the same
      "Junie has no supported headless CLI mode yet" wording `--harness junie`
      alone already produces - not a generic "not found on PATH" message.
- [ ] No interactive Junie session is ever launched as a fallback.

**Either way:**
- [x] `ruff check src/` clean.

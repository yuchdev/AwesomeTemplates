# 02 - `_JUNIE` registration (outcome-dependent)

**Parent task:** 03.0 `junie` adapter
**State:** ⬜ Not started
**Depends on:** 01 (this task's confirmed outcome)
**Blocks:** task 04.0 (`--harness junie` becomes selectable, honestly, either
way); task 08.0 (Junie porting session - buildable only under outcome 1)

## Objective

Register `_JUNIE` in `src/awesome_templates/harnesses.py`, in the shape
subtask 01's outcome dictates.

## Outcome 1: headless mode confirmed

Same pattern as task 02.0 subtask 02 (`_build_copilot_command`/`_COPILOT`):

```python
def _build_junie_command(
    junie_bin: str,
    *,
    tools: tuple[str, ...],
    model: Optional[str],
    prompt: Optional[str] = None,
) -> list[str]:
    """The headless argv for `junie`, per subtask 01's confirmed contract."""
    ...  # built from subtask 01's confirmed flags, not placeholders


_JUNIE = Harness(
    name="junie",
    binary_names=(...,),  # subtask 01's confirmed binary name(s)
    default_model=...,     # subtask 01's confirmed model alias, or None
    prompt_via=...,         # "stdin" or "arg" per subtask 01
    forwards_anthropic_key=False,
    build_command=_build_junie_command,
)

_REGISTRY["junie"] = _JUNIE
```

## Outcome 2: no headless mode exists

Register `_JUNIE` as present-but-unusable, so `--harness junie` is a clean,
honest rejection rather than an unknown-choice error - and so a future
JetBrains release only requires filling in `binary_names`/`build_command`,
not adding a new registry entry from scratch:

```python
def _build_junie_command(*args, **kwargs) -> list[str]:
    """Unreachable: `_JUNIE.binary_names` is empty, so `find_harness` always
    returns `None` for this harness and no caller ever calls this function.
    Exists only to satisfy `Harness.build_command`'s type - replace with a
    real implementation if/when JetBrains ships a documented headless mode."""
    raise NotImplementedError(
        "Junie has no supported headless CLI mode yet - see "
        "docs/roadmap/0001-alternative-harness-support/03.0-junie-adapter/01-spike-junie-headless-mode.md"
    )


_JUNIE = Harness(
    name="junie",
    binary_names=(),  # deliberately empty - find_harness(_JUNIE) always returns None
    default_model=None,
    prompt_via="stdin",
    forwards_anthropic_key=False,
    build_command=_build_junie_command,
)

_REGISTRY["junie"] = _JUNIE
```

Task 04.0's CLI wiring is responsible for turning `find_harness(_JUNIE) is
None` into the specific message "Junie has no supported headless CLI mode
yet" rather than the generic "`junie` CLI not found on PATH" a real-but-missing
binary would get - see task 04.0 subtask 03's harness-named-message
requirement. This subtask's job is only to make that distinction possible
(empty `binary_names` is itself the signal); the message text lives in
`cli.py`, not here.

## Constraints

- Do not populate `binary_names` with a guessed value under outcome 2 "just in
  case" - a non-empty tuple would make `find_harness` attempt `shutil.which`
  against a name that may not exist, which could coincidentally resolve to an
  unrelated binary on some machine's `PATH`.
- Same coding constraints as tasks 01.0/02.0.

## Success criteria

**Outcome 1:**
- [ ] `harnesses.get("junie")` returns a fully functional `Harness` sourced
      from subtask 01's confirmed contract.

**Outcome 2:**
- [ ] `harnesses.get("junie")` returns a `Harness` with `binary_names=()`.
- [ ] `harnesses.find_harness(harnesses.get("junie"))` returns `None`
      unconditionally (no `shutil.which` call can accidentally succeed).
- [ ] Calling `_build_junie_command` directly raises `NotImplementedError`
      with a message pointing at subtask 01's spike document.

**Either way:**
- [ ] `ruff check src/` clean.

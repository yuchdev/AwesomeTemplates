# 02 - `_build_copilot_command` + `_COPILOT` registration

**Parent task:** 02.0 `copilot` adapter
**State:** ✅ Complete (2026-08-30)
**Depends on:** 01 (this task's confirmed answers)
**Blocks:** task 04.0 (`--harness copilot` becomes selectable), task 07.0
(Copilot porting session)

## Objective

Using subtask 01's confirmed contract (not the placeholder flags below - these
are illustrative shape only), add `_build_copilot_command` and `_COPILOT` to
`src/awesome_templates/harnesses.py`, registered as `_REGISTRY["copilot"]`.

## File: `src/awesome_templates/harnesses.py` (additions)

```python
def _build_copilot_command(
    copilot_bin: str,
    *,
    tools: tuple[str, ...],
    model: Optional[str],
    prompt: Optional[str] = None,
) -> list[str]:
    """The headless argv for `copilot`, per subtask 01's confirmed contract.

    Placeholder shape - replace every flag name below with subtask 01's
    confirmed answer before this function ships:
    """
    cmd = [copilot_bin, "<non-interactive-flag-from-subtask-01>"]
    if model is not None:
        cmd += ["<model-flag-from-subtask-01>", model]
    cmd += ["<tool-allowlist-flag-from-subtask-01>", *tools]
    if _COPILOT.prompt_via == "arg" and prompt is not None:
        cmd.append(prompt)
    return cmd


_COPILOT = Harness(
    name="copilot",
    binary_names=("copilot",),
    default_model=None,  # or subtask 01's confirmed model alias
    prompt_via="stdin",  # or "arg" - set from subtask 01's finding
    forwards_anthropic_key=False,
    build_command=_build_copilot_command,
)

_REGISTRY["copilot"] = _COPILOT
```

## Implementation notes

- `binary_names` may need more than one candidate if GitHub ships the CLI
  under more than one command name across install methods - confirm during
  subtask 01 rather than assuming a single name.
- If subtask 01 found no `--model`-equivalent flag, `default_model` stays
  `None` and `_build_copilot_command` must branch on `model is None` to omit
  the flag entirely (shown above) - passing a `None` positionally into an argv
  list is a bug, not a no-op.
- If subtask 01 found no exact 1:1 mapping for one of `_BASE_TOOLS`'s names
  (`Read`, `Grep`, `Glob`, `Edit`, `TodoWrite`) or `Write` (needed by
  `--update-guidelines` and by porting), add a small translation dict here
  (`_TOOL_NAME_MAP: dict[str, str]`) rather than silently passing Claude's tool
  names through unchanged - a name Copilot doesn't recognize should fail loudly
  at command-construction time, not degrade permissions silently at runtime.

## Constraints

- `forwards_anthropic_key=False` - never add `ANTHROPIC_API_KEY` handling to
  this function; `resolve_tree_headless`/`port_tree_headless` already skip it
  based on this flag (task 01.0 subtask 02).
- Same coding constraints as task 01.0: `Optional[T]`, `from __future__ import
  annotations`, `ruff` clean, no new `# type: ignore`.

## Success criteria

- [x] `harnesses.get("copilot")` returns a `Harness` with every field sourced
      from subtask 01's confirmed answers - no placeholder flag names remain.
- [x] `_build_copilot_command` never emits a `None` model flag when
      `default_model is None` and no explicit `model` is passed.
- [x] `harnesses.HARNESS_NAMES` already listed `"copilot"` (task 01.0); this
      subtask makes `get("copilot")` actually resolve instead of raising
      `KeyError`.
- [x] `ruff check src/` clean.

## Post-review amendment (2026-08-30)

`/pr-review` (feature-reviewer) found two defects fixed before this task closed: (1) `prompt=None`
produced malformed argv (copilot's `-p` takes an adjacent value, unlike claude's bare `-p` flag) -
fixed with an early `raise ValueError` guard, matching this doc's own "passing a `None`
positionally into an argv list is a bug, not a no-op" principle applied to `prompt`, not just
`model`. (2) The tool-gating pair `--deny-tool=shell --allow-tool=write` was an untested
substitution for `--allow-all-tools --deny-tool=shell`, the only combination this task's own spike
actually ran live (the spike's live test hit an auth error before reaching any approval-prompt
behavior, so the narrower pair's non-interactive-mode sufficiency was never confirmed) - reverted
to the live-validated `--allow-all-tools --deny-tool=shell` (deny still takes precedence over
`--allow-all-tools` per the confirmed permissions model, so the no-shell boundary holds).

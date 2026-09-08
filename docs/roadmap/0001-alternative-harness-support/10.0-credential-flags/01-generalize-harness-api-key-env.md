# 01 - Generalize `Harness.api_key_env`

**Parent task:** 10.0 Credential flags + `--backend` removal
**State:** ✅ Complete
**Depends on:** task 01.0's `Harness` registry
**Blocks:** 02, 03 (this task)

## Objective

Replace `Harness.forwards_anthropic_key: bool` with `Harness.api_key_env: Optional[str]` - the
environment variable name a given harness's CLI reads for key-based authentication
(`"ANTHROPIC_API_KEY"` for `claude`), or `None` when the harness has no key-based auth mechanism
at all (`copilot`/`junie` authenticate only through their own login flow). This is what lets
`cli.py`'s new `--api-key`/`--api-key-env` flags (subtask 02) generalize across harnesses
instead of hardcoding `"ANTHROPIC_API_KEY"`, and what lets `sanity_check` reject the flags
outright for a harness with no env-var slot to fill.

## File: `src/awesome_templates/harnesses.py`

- `Harness` dataclass field rename: `forwards_anthropic_key: bool` → `api_key_env:
  Optional[str]`. Docstring rewritten to describe the env-var-name semantics above.
- `_CLAUDE = Harness(..., api_key_env="ANTHROPIC_API_KEY", ...)`.
- `_COPILOT = Harness(..., api_key_env=None, ...)`, `_JUNIE = Harness(..., api_key_env=None,
  ...)`.
- `_build_copilot_command`'s docstring passage about `--secret-env-vars=ANTHROPIC_API_KEY`
  being defense-in-depth "since `forwards_anthropic_key=False`" updated to reference
  `api_key_env=None` instead.

## File: `src/awesome_templates/headless.py`

`resolve_tree_headless`'s env construction generalizes from:

```python
env = {**os.environ}
if api_key and harness_obj.forwards_anthropic_key:
    env["ANTHROPIC_API_KEY"] = api_key
else:
    env.pop("ANTHROPIC_API_KEY", None)
```

to (as actually shipped - a `/pr-review` security pass during subtask 03 recommended
generalizing the strip itself, not just the re-add, to `harness_obj.api_key_env`; the snippet
below is the final, shipped form, not this subtask's original draft):

```python
env = {**os.environ}
env.pop("ANTHROPIC_API_KEY", None)  # never leak an ambient Anthropic key into any harness
if harness_obj.api_key_env:
    env.pop(harness_obj.api_key_env, None)  # same guarantee for a future non-Anthropic harness
    if api_key:
        env[harness_obj.api_key_env] = api_key
```

The unconditional strip preserves the existing HIGH-severity-fix behavior (defense-in-depth
against a shell-exported key leaking into copilot/junie, see status.md's task 01.0 notes) for
every harness; the second line generalizes the injection to whatever env var name the harness
declares, rather than a hardcoded `"ANTHROPIC_API_KEY"`.

## File: `src/awesome_templates/port.py`

`port_tree_headless`'s porting-target guard (`if harness_obj.forwards_anthropic_key: raise
ValueError(...)`) becomes `if harness_obj.api_key_env is not None: raise ValueError(...)`,
updating the message and the two explanatory comments referencing the old field name.
Behavior is unchanged - `copilot`/`junie` both still have no key-env, so the guard still always
fires the same way (never, for either valid `--port-to` target).

## Constraints

- Behavior-identical for the default case: no `api_key` given still produces the same
  `env` (ambient `ANTHROPIC_API_KEY` stripped, nothing added) for every harness.
- `from __future__ import annotations`; `Optional[T]`, never `T | None`.

## Success criteria

- [x] `Harness.api_key_env` exists; `forwards_anthropic_key` no longer exists anywhere in
      `src/`.
- [x] `harnesses.get("claude").api_key_env == "ANTHROPIC_API_KEY"`; `harnesses.get("copilot")`/
      `harnesses.get("junie")`'s `api_key_env is None`.
- [x] `resolve_tree_headless(out_dir, api_key=None, warnings=[])` (no `harness` argument)
      behaves identically to today.
- [x] `port_tree_headless` still refuses to run for any harness with a non-`None`
      `api_key_env` (currently: none of the valid `--port-to` targets, so this remains
      unreachable in practice, same as before).
- [x] `ruff check src/` clean.

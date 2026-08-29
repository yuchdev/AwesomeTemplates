# 03 - `cli.py`: `--port-to` flag + validation + dispatch

**Parent task:** 06.0 `--port-to` pipeline orchestration
**State:** ⬜ Not started
**Depends on:** 02 (this task), task 04.0 (the `--harness` flag and
`resolve_value` branch this subtask extends)
**Blocks:** task 09.0 (CLI-level porting tests)

## Objective

Add `--port-to {copilot,junie}` to `generate`, gated on `--resolve-markers`
and on `--harness` being `claude` (its default) per the milestone's answered
design question - "Claude is always the reference harness" is enforced
strictly here, not just as a self-port check. Dispatch to
`port.port_tree_headless` right after the initial Claude-authoring stage
succeeds, in the same `generate` invocation (the chained-pipeline shape this
milestone chose over a separate follow-up command).

## Changes to `src/awesome_templates/cli.py`

New option, alongside `harness` (task 04.0 subtask 01):

```python
port_to: Optional[str] = typer.Option(
    None,
    "--port-to",
    click_type=click.Choice(("copilot", "junie")),
    help="after the initial Claude-authored .claude/ tree is ready, launch this "
    "harness in its own headless session and task it with porting every agent/ "
    "skill/loop/hook into its own native form - requires --resolve-markers and "
    "--harness claude (the default); the target harness re-authors each kind in "
    "its own idiom, it does not copy files",
),
```

Validation, alongside the existing `harness_value`/`resolve_value` checks:

```python
if port_to and not resolve_value:
    _fail(f"--port-to {port_to} requires --resolve-markers")
    return
if port_to and harness_value != "claude":
    _fail(
        f"--port-to {port_to} requires --harness claude (the default) - "
        "porting always reads a Claude-authored .claude/ tree"
    )
    return
```

Dry-run output (extends task 04.0 subtask 02's payload):

```python
if dry_run:
    payload = {
        ...,
        "harness": harness_value,
        "port_to": port_to,
    }
    ...
    if port_to:
        console.print(f"Port to: {port_to}")
    return
```

Dispatch, appended after the existing `resolve_value` block's `summary[...]`
assignments (still inside `if resolve_value:`, after `rsum`/`summary` are
fully populated - see task 04.0 subtask 03's final shape):

```python
if port_to:
    from awesome_templates import port

    port_summary = port.port_tree_headless(
        out_dir,
        harness=port_to,
        warnings=warnings,
        project_root=target_dir,
        log=log,
    )
    summary["ported_to"] = port_to
    summary["ported_kinds"] = port_summary.manifest_kinds
    summary["port_command_ok"] = port_summary.command_ok
```

Wrap the dispatch's `RuntimeError` (raised by `port_tree_headless` when the
target binary is missing) the same way the existing `claude_bin is None`
branch is handled - as a hard `_fail`, not a warning, since a missing
`--port-to` binary means the explicitly requested porting stage cannot run at
all:

```python
if port_to:
    from awesome_templates import port

    try:
        port_summary = port.port_tree_headless(
            out_dir, harness=port_to, warnings=warnings, project_root=target_dir, log=log,
        )
    except RuntimeError as exc:
        _fail(str(exc))
        return
    summary["ported_to"] = port_to
    summary["ported_kinds"] = port_summary.manifest_kinds
    summary["port_command_ok"] = port_summary.command_ok
```

## Implementation notes

- The two validation checks are independent and both must be reachable in
  isolation: `--port-to copilot` with no `--resolve-markers` should report the
  `--resolve-markers` problem, not the harness one, when both are true -
  order the checks so the more fundamental gate (`--resolve-markers`) is
  checked first, matching the order shown above.
- `--port-to`'s dispatch sits *after* the existing `if resolve_value:` block's
  body (which already ran the Claude authoring/marker-research session and
  populated `summary["markers_resolved"]` etc.) - not interleaved with it.
  This is what "chained in one invocation, after the initial stage succeeds"
  means concretely: `port_tree_headless` only runs once `rsum` exists.
- If the initial Claude stage itself hard-failed (e.g. `--update-guidelines`
  with no `claude` binary, from task 04.0 subtask 03's branch), execution
  already returned via `_fail` before reaching the `--port-to` dispatch - no
  additional guard needed here for that case.

## Constraints

- `--port-to`'s two validation checks must run before any preset copy or
  headless session starts - matching every other `generate` flag-combination
  validation, which happens early, before `copy_preset` is called.
- No new import of `subprocess` or `harnesses` directly in `cli.py` for this
  subtask - `port.port_tree_headless` is the only new call site, imported
  lazily inside the `if resolve_value:` block like `headless`/`resolver`
  already are.

## Success criteria

- [ ] `generate --port-to copilot` (no `--resolve-markers`) fails with
      `"--port-to copilot requires --resolve-markers"`.
- [ ] `generate --resolve-markers --harness copilot --port-to junie` fails
      with the `--harness claude` message, even though it is not a literal
      self-port.
- [ ] `generate --resolve-markers --port-to copilot` (harness defaults to
      `claude`) passes validation and reaches the dispatch.
- [ ] `--dry-run --json` includes `"port_to": null` when `--port-to` is
      omitted, and the chosen value otherwise; console mode prints
      `Port to: ...` only when set.
- [ ] A missing `--port-to` binary hard-fails the whole `generate` invocation
      (non-zero exit), even though the initial Claude stage already
      succeeded and wrote `.claude/`.
- [ ] `ruff check src/` clean.

# 03 - Missing-binary branching, no silent fallback for non-claude

**Parent task:** 04.0 `cli.py` wiring
**State:** ⬜ Not started
**Depends on:** 01
**Blocks:** task 06.0 (`--port-to`'s own missing-binary handling follows this
same shape)

## Objective

Rewrite the `resolve_value` block in `generate` (currently `if claude_bin: ...
else: ... falls back to resolver.resolve_tree`) so the one-shot API fallback
is reachable **only** when `harness_value == "claude"`. A missing `copilot` or
`junie` binary is a hard failure with a harness-named, actionable message -
never a silent substitution of a different vendor's model for the one the
user explicitly asked for.

## Changes to `src/awesome_templates/cli.py`

Today's block (see [`cli.py`](/src/awesome_templates/cli.py), the `if
resolve_value:` branch inside `generate`):

```python
if resolve_value:
    from awesome_templates import headless, resolver

    api_key = resolver.load_api_key(Path.cwd())
    claude_bin = harnesses.find_harness(harnesses.get("claude"))  # updated by task 01.0 subtask 02

    if claude_bin:
        rsum, guidelines_updated = headless.resolve_tree_headless(
            out_dir, api_key=api_key, warnings=warnings, claude_bin=claude_bin,
            project_root=target_dir, update_guidelines=update_guidelines, log=log,
        )
        ...
    else:
        if update_guidelines:
            _fail("--update-guidelines needs the `claude` CLI on PATH ...")
            return
        if not api_key:
            _fail("--resolve-markers needs the `claude` CLI on PATH, or ANTHROPIC_API_KEY ...")
            return
        # falls back to resolver.resolve_tree with a warning
        ...
```

Becomes:

```python
if resolve_value:
    from awesome_templates import headless, resolver

    api_key = resolver.load_api_key(Path.cwd())
    harness_obj = harnesses.get(harness_value)
    harness_bin = harnesses.find_harness(harness_obj)

    if harness_bin:
        rsum, guidelines_updated = headless.resolve_tree_headless(
            out_dir,
            api_key=api_key,
            warnings=warnings,
            harness=harness_value,
            claude_bin=harness_bin,
            project_root=target_dir,
            update_guidelines=update_guidelines,
            log=log,
        )
        if update_guidelines:
            summary["guidelines_updated"] = guidelines_updated
    elif harness_value != "claude":
        # No silent fallback for a non-default harness (plan.md non-goal):
        # substituting a different vendor's model for the one the user
        # explicitly asked for would be a surprising, unrequested behavior
        # change.
        if harness_value == "junie" and not harness_obj.binary_names:
            _fail(
                "Junie has no supported headless CLI mode yet - "
                "see docs/roadmap/0001-alternative-harness-support/03.0-junie-adapter/ "
                "or use --harness claude"
            )
        else:
            _fail(
                f"{harness_value} CLI not found on PATH - install it (or check "
                f"authentication), or use --harness claude"
            )
        return
    else:
        # harness_value == "claude": today's unchanged fallback behavior.
        if update_guidelines:
            _fail(
                "--update-guidelines needs the `claude` CLI on PATH "
                "(it runs a headless Claude Code research session)"
            )
            return
        if not api_key:
            _fail(
                "--resolve-markers needs the `claude` CLI on PATH, or ANTHROPIC_API_KEY "
                "(in the environment or a .env in the cwd) for the one-shot API fallback"
            )
            return
        message = (
            "claude CLI not found on PATH - falling back to one-shot API marker "
            "resolution (weaker research); install Claude Code for the full research pass"
        )
        warnings.append(message)
        log.warning(message)
        try:
            from awesome_templates.ai import client as ai_client

            fallback_client = ai_client.build_client(api_key)
        except ModuleNotFoundError:
            _fail("--resolve-markers needs the 'ai' extra: pip install awesome_templates[ai]")
            return
        rsum = resolver.resolve_tree(
            out_dir, api_key=api_key, warnings=warnings, context_root=target_dir,
            make_client=lambda: fallback_client, log=log,
        )
    summary["markers_resolved"] = rsum.resolved
    ...  # unchanged
```

## Implementation notes

- The `harness_value == "junie" and not harness_obj.binary_names` branch is
  the honest-unavailable path task 03.0 subtask 02's outcome-2 registration
  produces: an empty `binary_names` tuple is itself the signal that this
  harness was never expected to be found, as opposed to "installed but not on
  `PATH`" - the message should say so explicitly rather than telling the user
  to "install it" when there is nothing to install yet. If task 03.0 landed on
  outcome 1 instead, `_JUNIE.binary_names` is non-empty and this branch is
  simply never taken - the generic "CLI not found on PATH" message applies to
  `junie` the same as `copilot`.
- `summary` should also record which harness actually ran, for parity with
  the dry-run `"harness"` key added in subtask 02:
  `summary["harness"] = harness_value` right after `summary = {...}` is
  constructed earlier in `generate`.

## Constraints

- The three-way branch (`harness_bin` found / not found and non-claude / not
  found and claude) must be exhaustive and never fall through silently - every
  path either runs a session, hard-fails, or takes the documented `claude`
  fallback.
- No new import of `subprocess` or any harness-specific module in `cli.py`
  itself - it only orchestrates via `harnesses`/`headless`.

## Success criteria

- [ ] `generate --resolve-markers --harness copilot` with no `copilot` binary
      on `PATH` fails with a message naming `copilot` and exit code 1 - no
      fallback to `resolver.resolve_tree` occurs (assert via a test that
      `resolver.resolve_tree` is never called - e.g. monkeypatch it to raise
      if invoked).
- [ ] Same for `--harness junie` when `_JUNIE.binary_names` is empty (outcome
      2): the message specifically says Junie has no headless CLI mode yet,
      not a generic "not found on PATH".
- [ ] `generate --resolve-markers` with no `--harness` flag and no `claude`
      binary on `PATH` still falls back to `resolver.resolve_tree` with a
      warning, exit code 0 - unchanged from today.
- [ ] `generate --resolve-markers --harness claude` (explicit default) behaves
      identically to omitting `--harness` entirely.
- [ ] `summary["harness"]` is present in the JSON summary output for every
      `--resolve-markers` run.

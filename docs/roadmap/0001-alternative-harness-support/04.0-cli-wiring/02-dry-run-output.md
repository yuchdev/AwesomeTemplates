# 02 - Dry-run output

**Parent task:** 04.0 `cli.py` wiring
**State:** ⬜ Not started
**Depends on:** 01
**Blocks:** none

## Objective

Add a `Harness: ...` line (console) / `"harness"` key (JSON) to `generate
--dry-run`'s output, mirroring the existing `Specializations: ...` line/
`"specializations"` key.

## Changes to `src/awesome_templates/cli.py`

In the `dry_run` block:

```python
if dry_run:
    payload = {
        "preset": preset_value,
        "out": out_value,
        "substitutions": subs,
        "specializations": specializations_value,
        "harness": harness_value,
    }
    if resolve_value:
        from awesome_templates.markers import scan_tree

        payload["markers_to_resolve"] = len(scan_tree(workspace.path(preset_value)))
    if json_out:
        typer.echo(json.dumps(payload, indent=2))
    else:
        console.print(f"Would generate preset '{preset_value}' into: {out_dir}")
        console.print(f"Substitutions: {subs}")
        if specializations_value:
            console.print(f"Specializations: {', '.join(specializations_value)}")
        if resolve_value:
            console.print(f"Harness: {harness_value}")
            console.print(f"Would AI-resolve {payload['markers_to_resolve']} marker(s)")
    return
```

Note `"harness"` is always included in the JSON payload (even when
`resolve_value` is false, since `harness_value` is always defined and
defaults to `"claude"`), but the console `Harness: ...` line is only printed
when `resolve_value` is true - printing it unconditionally would be noise for
the common case where `--resolve-markers` isn't used at all and `--harness`
is silently `"claude"` by default.

## Constraints

- Placement in the JSON payload dict and console print order should follow
  the existing pattern (`specializations` before `harness` in both, matching
  the flag declaration order in the `generate` signature).

## Success criteria

- [ ] `generate --dry-run --json` output includes `"harness": "claude"` when
      no `--harness` flag is passed.
- [ ] `generate --resolve-markers --harness copilot --dry-run` (non-JSON)
      prints a `Harness: copilot` line before `Would AI-resolve ...`.
- [ ] `generate --dry-run` (no `--resolve-markers`) prints no `Harness: ...`
      line in console mode, but still includes `"harness": "claude"` in
      `--json` mode.

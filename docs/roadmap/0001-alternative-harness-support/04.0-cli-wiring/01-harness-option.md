# 01 - `--harness` option + validation

**Parent task:** 04.0 `cli.py` wiring
**State:** ⬜ Not started
**Depends on:** task 01.0 (`harnesses.HARNESS_NAMES`, `harnesses.get`)
**Blocks:** 02, 03 (this task)

## Objective

Add a `--harness {claude,copilot,junie}` option to `generate` in
[`cli.py`](/src/awesome_templates/cli.py), defaulting to `"claude"`, with a
config-file fallback and the same "rejected without `--resolve-markers`"
validation `--seed-roadmap` and `--update-guidelines` already have.

## Changes to `src/awesome_templates/cli.py`

Add the import and the option, next to `update_guidelines` in the `generate`
signature:

```python
from awesome_templates import harnesses  # new import, alongside existing catalog/config/etc imports
import click

...

harness: Optional[str] = typer.Option(
    None,
    "--harness",
    click_type=click.Choice(harnesses.HARNESS_NAMES),
    help="which headless CLI runs the marker-research session: claude (default), "
    "copilot, or junie - requires --resolve-markers and that CLI installed/authenticated",
),
```

In the body, alongside the existing `resolve_value`/`seed_roadmap`/
`update_guidelines` derivation:

```python
harness_value = harness or cfg.get("harness", "claude")

if harness_value != "claude" and not resolve_value:
    _fail(f"--harness {harness_value} requires --resolve-markers")
    return
```

Note the check is `harness_value != "claude"`, not "harness was passed at
all" - passing `--harness claude` explicitly without `--resolve-markers` is
harmless (it's the default anyway) and should not be rejected; only a
*non-default* harness choice implies "I want a marker-research session; if
`--resolve-markers` is absent that's a real usage error worth catching early.

## Implementation notes

- `click_type=click.Choice(...)` mirrors the existing pattern used elsewhere
  in this CLI for enum-like flags (see `LogVerbosity`'s use via
  `graph_cmd`'s `log_verbosity` - though that one uses a Typer/Click enum
  type rather than a raw `click.Choice`; either is acceptable here since
  `HARNESS_NAMES` is a plain string tuple, not a `str, enum.Enum` subclass -
  keep it a plain `click.Choice` unless a project reviewer prefers promoting
  it to an enum for consistency with `LogVerbosity`).
- Typer's `click.Choice` validation happens before the command body runs, so
  an unknown `--harness` value (e.g. `--harness gpt4`) is rejected by Click
  itself with its own "invalid choice" message and a non-zero exit code -
  no manual `_fail(...)` call is needed for that case, only for the
  "valid choice but missing `--resolve-markers`" case shown above.
- Config-file fallback follows the same "override wins" semantics every other
  scalar `generate` option already has (`cfg.get("harness", "claude")`), not
  the `--specialization` list exception.

## Constraints

- `Optional[str]` for the flag parameter (mirroring `preset`, `name`, etc.);
  the *resolved* `harness_value` after the `or` fallback is always a `str`.
- No change to `--harness claude`'s (the default's) behavior when
  `--resolve-markers` is absent - `harness_value != "claude"` in the guard
  above is what keeps that path a no-op.

## Success criteria

- [ ] `generate --harness copilot` (no `--resolve-markers`) fails with
      `"--harness copilot requires --resolve-markers"` and exit code 1.
- [ ] `generate --harness bogus` fails via Click's own choice validation
      (exit code 2, "Invalid value" in output) before reaching `_fail`.
- [ ] `generate` with no `--harness` flag and no `resolve_markers` config key
      behaves identically to today (harness_value defaults to `"claude"`,
      guard is a no-op).
- [ ] `generate --config-file cfg.json` with `{"harness": "copilot",
      "resolve_markers": true}` and no CLI `--harness` flag resolves
      `harness_value == "copilot"`.
- [ ] `ruff check src/` clean.

# 01 - `Harness` dataclass + registry skeleton

**Parent task:** 01.0 `harnesses.py` + `claude` relocation
**State:** ⬜ Not started
**Depends on:** none
**Blocks:** 02 (this task); 02.0, 03.0, 04.0, 06.0 (downstream tasks register into
or read `_REGISTRY`/`get`/`find_harness` this subtask creates)

## Objective

Create `src/awesome_templates/harnesses.py` with the `Harness` dataclass,
`HARNESS_NAMES`, `find_harness`, `get`, and an initially-empty `_REGISTRY` (populated
with `_CLAUDE` in subtask 02, once that lands - keep it as `{}` here if 02 hasn't
landed yet, or land 01 and 02 together, since a registry with no entries is not
independently useful). No caller is updated yet - `headless.py`/`cli.py` still use
today's `find_claude`/`build_command` until subtask 02.

## File: `src/awesome_templates/harnesses.py`

```python
"""Per-backend adapters for headless sessions - marker research (headless.py)
and cross-harness porting (port.py): binary discovery and argv construction for
each supported CLI. Those callers stay responsible for *what* a session needs to
do (the manifest, the prompt, reconciliation); this module is only responsible
for *how* to ask a given CLI to do it, so a wrong guess about one backend's flag
names is a one-function fix here, not a rewrite of a caller. See
docs/roadmap/0001-alternative-harness-support/plan.md's "Proposed architecture"
section for the design this module implements.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable, Optional

HARNESS_NAMES = ("claude", "copilot", "junie")


@dataclass(frozen=True)
class Harness:
    """One headless-CLI backend's identity and argv-construction recipe.

    :ivar name: the `--harness` value this registration answers to.
    :ivar binary_names: candidate executable names tried in order via
        `shutil.which` - more than one entry lets a harness accept an
        alternate binary name without a second registry entry.
    :ivar default_model: the model alias passed when the caller doesn't
        override it, or `None` when the backend has no CLI model flag.
    :ivar prompt_via: `"stdin"` when the session prompt is piped to the
        subprocess's stdin (claude's mechanism today), `"arg"` when the
        backend instead expects the prompt as a command-line argument -
        `build_command` is responsible for placing it correctly in that case,
        and the caller must not also pipe it over stdin.
    :ivar forwards_anthropic_key: whether `ANTHROPIC_API_KEY` should be
        forwarded into this harness's subprocess environment - true only for
        `claude`; copilot/junie authenticate through their own mechanisms.
    :ivar build_command: `(binary, *, tools, model, prompt) -> argv`. `prompt`
        is unused (and should not be embedded in argv) when `prompt_via` is
        `"stdin"`; it is required and must appear in the returned argv when
        `prompt_via` is `"arg"`.
    :ivar porting_target_hint: free-text hint, consumed by `port.py`'s prompt
        builder, naming where this harness conventionally expects its own
        agent/skill-equivalent files to live. `None` until tasks 07.0/08.0
        confirm it for copilot/junie; `claude` never needs one since it is
        never a `--port-to` target.
    """

    name: str
    binary_names: tuple[str, ...]
    default_model: Optional[str]
    prompt_via: str
    forwards_anthropic_key: bool
    build_command: Callable[..., list[str]]
    porting_target_hint: Optional[str] = None


def find_harness(harness: Harness) -> Optional[str]:
    """Absolute path of the first installed candidate binary, or None -
    the same contract `headless.find_claude()` has today, generalized.

    :param harness: the :class:`Harness` whose `binary_names` to search.
    :return: absolute path to the first match on `PATH`, or `None` if none
        of `harness.binary_names` is installed.
    """
    for candidate in harness.binary_names:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def get(name: str) -> Harness:
    """Look up a harness by its `--harness`/`--port-to` value.

    :param name: one of `HARNESS_NAMES`.
    :return: the registered :class:`Harness`.
    :raises KeyError: if `name` is not registered - `cli.py` turns this into
        the same `_fail(...)` shape `_resolve_preset` already uses for an
        unknown preset (see task 04.0).
    """
    return _REGISTRY[name]


_REGISTRY: dict[str, Harness] = {}
```

## Implementation notes

- `_REGISTRY` is declared last, after every `Harness` instance it references,
  matching the ordering constraint Python's module-level evaluation imposes
  (a dict literal referencing `_CLAUDE` needs `_CLAUDE` already bound). Land
  this subtask together with subtask 02 in practice, or leave `_REGISTRY = {}`
  as a placeholder if landing them separately - either way `get("claude")`
  must work once both are merged, since subtask 02's own success criteria
  depend on it.
- `HARNESS_NAMES` is a plain tuple of the three names this milestone knows
  about up front, independent of which ones are actually registered yet -
  `cli.py`'s `click.Choice(harnesses.HARNESS_NAMES)` (task 04.0) uses it so the
  `--harness` flag's help text and validation don't have to change again when
  tasks 02.0/03.0 land. It intentionally does not derive from
  `_REGISTRY.keys()`, since at this subtask `_REGISTRY` may still be empty.
- `porting_target_hint` is added here (not deferred to task 07.0) so the
  dataclass shape never needs a field added later - a later field addition to
  a frozen dataclass with existing call sites is a larger diff than adding it
  once with a `None` default up front.

## Constraints

- `from __future__ import annotations` at the top; `Optional[T]` from
  `typing`, never `T | None`.
- No import of `subprocess`, `headless`, or `port` in this module - it only
  ever locates binaries and assembles argv lists; it never runs anything.
- Every public name (`Harness`, `find_harness`, `get`) carries a docstring.

## Success criteria

- [ ] `src/awesome_templates/harnesses.py` exists with `Harness`,
      `HARNESS_NAMES`, `find_harness`, `get`, `_REGISTRY`.
- [ ] `find_harness` returns the first `shutil.which` hit across
      `binary_names`, or `None` when none resolve.
- [ ] `get("bogus")` raises `KeyError`.
- [ ] `ruff check src/` clean.

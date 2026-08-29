# 01 - `tests/test_harnesses.py`

**Parent task:** 05.0 Tests
**State:** ⬜ Not started
**Depends on:** tasks 01.0 (`_CLAUDE`), 02.0 (`_COPILOT`), 03.0 (`_JUNIE`) - can
start against task 01.0 alone and grow as 02.0/03.0 land
**Blocks:** none

## Objective

New file `tests/test_harnesses.py` covering `harnesses.py`'s registry and
binary-discovery logic in isolation from any session-orchestration code.

## Test cases

```python
from __future__ import annotations

import pytest

from awesome_templates import harnesses


def test_find_harness_resolves_first_matching_binary(monkeypatch):
    # fake PATH via monkeypatch.setattr(shutil, "which", ...) or tmp_path bin dir
    ...


def test_find_harness_returns_none_when_no_candidate_installed(monkeypatch):
    ...


def test_find_harness_returns_none_for_empty_binary_names():
    # covers task 03.0's outcome-2 stub: _JUNIE with binary_names=()
    stub = harnesses.Harness(
        name="stub", binary_names=(), default_model=None, prompt_via="stdin",
        forwards_anthropic_key=False, build_command=lambda *a, **k: [],
    )
    assert harnesses.find_harness(stub) is None


def test_get_unknown_harness_raises_keyerror():
    with pytest.raises(KeyError):
        harnesses.get("bogus")


def test_get_claude_returns_registered_harness():
    harness = harnesses.get("claude")
    assert harness.name == "claude"
    assert harness.forwards_anthropic_key is True


def test_build_claude_command_matches_todays_output():
    # pins the "relocation, not rewrite" claim from task 01.0 subtask 02:
    # byte-identical argv for both the marker-research and
    # --update-guidelines tool sets.
    cmd = harnesses.get("claude").build_command(
        "/usr/local/bin/claude",
        tools=("Read", "Grep", "Glob", "Edit", "TodoWrite"),
        model="opus",
    )
    assert cmd == [
        "/usr/local/bin/claude", "-p", "--output-format", "text",
        "--setting-sources", "user", "--permission-mode", "bypassPermissions",
        "--no-session-persistence", "--model", "opus", "--tools",
        "Read", "Grep", "Glob", "Edit", "TodoWrite",
    ]


def test_build_copilot_command_shape():
    # once task 02.0 confirms real flags - assert against the CONFIRMED
    # contract, not the placeholder flags in that task's own subtask doc.
    ...


def test_build_junie_command_shape_or_unavailable():
    # branches on task 03.0's outcome: either assert a real argv shape
    # (outcome 1), or assert find_harness(get("junie")) is None and
    # calling _build_junie_command raises NotImplementedError (outcome 2).
    ...


def test_copilot_does_not_forward_anthropic_key():
    assert harnesses.get("copilot").forwards_anthropic_key is False


def test_junie_does_not_forward_anthropic_key():
    assert harnesses.get("junie").forwards_anthropic_key is False
```

## Implementation notes

- `test_build_claude_command_matches_todays_output` is the single most
  important test in this file - it is the concrete pin for task 01.0's
  "no behavior change" acceptance criterion. Write it before doing the
  relocation, so it fails against the pre-relocation code for the right
  reason (function doesn't exist yet) and passes identically after.
- Faking `PATH` for `find_harness` tests: prefer `monkeypatch.setenv("PATH",
  str(tmp_path))` with a real executable file created under `tmp_path` (same
  technique `tests/test_headless.py`-adjacent CLI tests likely already use
  for `claude`-on-PATH scenarios - check for an existing helper before adding
  a second one) over monkeypatching `shutil.which` directly, since the former
  exercises the real resolution path.

## Constraints

- No real `copilot`/`junie` binary invoked or assumed installed.
- `from __future__ import annotations` at the top.

## Success criteria

- [ ] All test cases above pass (or their outcome-1/outcome-2 variant, per
      task 03.0's actual result).
- [ ] `test_build_claude_command_matches_todays_output` fails if task 01.0's
      relocation changes even one flag's ordering.
- [ ] `uv run pytest tests/test_harnesses.py -q` green.

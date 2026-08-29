# 01 - `tests/test_port.py`: manifest + prompt tests

**Parent task:** 09.0 Porting pipeline tests
**State:** ⬜ Not started
**Depends on:** task 06.0 subtask 01 (`render_porting_manifest`,
`build_porting_prompt`)
**Blocks:** none

## Objective

New file `tests/test_port.py` covering `port.py`'s pure functions in
isolation - no subprocess, no `harnesses.py` binary discovery involved.

## Test cases

```python
from __future__ import annotations

from awesome_templates import port
from awesome_templates.harnesses import Harness


def _stub_harness(hint=None) -> Harness:
    return Harness(
        name="stub", binary_names=(), default_model=None, prompt_via="stdin",
        forwards_anthropic_key=False, build_command=lambda *a, **k: [],
        porting_target_hint=hint,
    )


def test_render_porting_manifest_counts_real_entities(fixture_workspace):
    manifest, counts = port.render_porting_manifest(fixture_workspace.path("demo"))
    assert counts == {"agents": 1, "hooks": 2, "loops": 0, "skills": 1}
    assert "widget-verifier" in manifest
    assert "adr-write" in manifest


def test_render_porting_manifest_empty_tree_no_claude_dir(tmp_path):
    manifest, counts = port.render_porting_manifest(tmp_path)
    assert counts == {"agents": 0, "hooks": 0, "loops": 0, "skills": 0}
    assert manifest.count("\n") <= 1  # header row only, no data rows


def test_build_porting_prompt_embeds_manifest(tmp_path):
    manifest = "| Kind | Name | Path |\n|------|------|------|\n| `agents` | `x` | `.claude/agents/x.md` |"
    prompt = port.build_porting_prompt(manifest, kit_root=tmp_path, harness=_stub_harness())
    assert manifest in prompt
    assert "re-author" in prompt.lower() or "own idiom" in prompt.lower()


def test_build_porting_prompt_uses_harness_hint_when_set(tmp_path):
    prompt = port.build_porting_prompt(
        "", kit_root=tmp_path, harness=_stub_harness(hint="Write to .github/copilot/"),
    )
    assert "Write to .github/copilot/" in prompt


def test_build_porting_prompt_generic_fallback_when_hint_none(tmp_path):
    prompt = port.build_porting_prompt("", kit_root=tmp_path, harness=_stub_harness(hint=None))
    assert "idiomatic for your own tool" in prompt


def test_build_porting_prompt_never_instructs_editing_claude_dir(tmp_path):
    prompt = port.build_porting_prompt("", kit_root=tmp_path, harness=_stub_harness())
    assert "do not edit" in prompt.lower() or "never" in prompt.lower()
```

## Implementation notes

- `test_render_porting_manifest_counts_real_entities` pins the exact counts
  `tests/conftest.py`'s `fixture_workspace`'s `"demo"` preset produces -
  update this test if that fixture's shape ever changes (it is shared with
  every other test file that uses `fixture_workspace`, so a change there is
  visible across the whole suite, not just here).
- The two `_stub_harness` calls avoid depending on `harnesses.get("copilot")`
  actually being registered yet - this file's pure-function tests should pass
  as soon as task 06.0 subtask 01 lands, independent of tasks 02.0/03.0/07.0/
  08.0's progress.

## Constraints

- No subprocess, no `run=` fakes in this file - that's subtask 02.
- `from __future__ import annotations` at the top.

## Success criteria

- [ ] All test cases above pass.
- [ ] `uv run pytest tests/test_port.py -q` green (once subtask 02 adds its
      own cases to the same file).

# 02 - `tests/test_headless.py` additions

**Parent task:** 05.0 Tests
**State:** ⬜ Not started
**Depends on:** task 01.0 (`resolve_tree_headless`'s `harness=` parameter)
**Blocks:** none

## Objective

Extend [`tests/test_headless.py`](/tests/test_headless.py) (which already has
the `kit` fixture and `_fake_run_factory` helper - see its lines 1-52) with
cases proving `resolve_tree_headless` dispatches through the harness registry
correctly, without a real `copilot`/`junie` binary.

## Test cases

```python
def test_resolve_tree_headless_defaults_to_claude(kit, monkeypatch):
    # no harness= kwarg passed - must resolve exactly as before task 01.0.
    ...


def test_resolve_tree_headless_with_copilot_harness(kit, monkeypatch, tmp_path):
    # Put a fake `copilot` executable on a synthetic PATH (monkeypatch.setenv),
    # scripted `run=` via _fake_run_factory, and assert:
    fake_bin = tmp_path / "bin" / "copilot"
    fake_bin.parent.mkdir()
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin.parent))

    fake_run = _fake_run_factory({...})
    unused_key = "placeholder-not-forwarded-for-non-claude-harness"
    summary, _ = headless.resolve_tree_headless(
        kit, api_key=unused_key, warnings=[], harness="copilot",
        run=fake_run,
    )
    call = fake_run.calls[0]
    assert call["cmd"] == harnesses.get("copilot").build_command(
        str(fake_bin), tools=("Read", "Grep", "Glob", "Edit", "TodoWrite"), model=None,
    )
    assert "ANTHROPIC_API_KEY" not in call["env"]  # forwards_anthropic_key=False


def test_resolve_tree_headless_unknown_harness_raises():
    with pytest.raises(KeyError):
        headless.resolve_tree_headless(Path("."), api_key=None, warnings=[], harness="bogus")


def test_resolve_tree_headless_claude_missing_binary_message_names_claude(kit, monkeypatch):
    monkeypatch.setenv("PATH", "")  # nothing resolves
    with pytest.raises(RuntimeError, match="claude"):
        headless.resolve_tree_headless(kit, api_key=None, warnings=[])
```

## Implementation notes

- The `"ANTHROPIC_API_KEY" not in call["env"]` assertion is the concrete pin
  for `forwards_anthropic_key=False` actually taking effect at the subprocess
  boundary, not just being a dataclass field nobody reads.
- Reuse the existing `kit` fixture (a minimal generated tree with block/
  inline/SME markers) rather than building a second one - the marker-research
  contract itself (manifest, prompt, reconciliation) doesn't change per
  harness, only which binary/argv/env the session runs with.
- `test_resolve_tree_headless_with_copilot_harness`'s exact `build_command`
  call assertion depends on task 02.0's confirmed contract - update the
  `tools=`/`model=` expectation to match once that lands (this doc predates
  it and uses the marker-research tool set as a placeholder).

## Constraints

- No real `copilot`/`junie` binary invoked - the fake executable file only
  needs to exist and be resolvable via `shutil.which`; it is never actually
  run (the `run=` fake intercepts before any real subprocess call).

## Success criteria

- [ ] `test_resolve_tree_headless_defaults_to_claude` passes unmodified
      before and after task 01.0's relocation (it is the regression pin for
      "no behavior change").
- [ ] The `copilot`-harness test asserts both the constructed command and the
      absence of `ANTHROPIC_API_KEY` from the subprocess env.
- [ ] `uv run pytest tests/test_headless.py -q` green.

# 02 - `tests/test_port.py`: `port_tree_headless` fake-run tests

**Parent task:** 09.0 Porting pipeline tests
**State:** ⬜ Not started
**Depends on:** task 06.0 subtask 02 (`port_tree_headless`, `PortSummary`)
**Blocks:** none

## Objective

Extend `tests/test_port.py` (subtask 01's file) with subprocess-boundary
tests for `port_tree_headless`, following `tests/test_headless.py`'s
`_fake_run_factory` pattern (reuse it via import, or duplicate the ~10-line
helper into `test_port.py` if cross-file import of a test helper is not this
repo's convention - check `tests/conftest.py` first for a shared-fixtures
precedent before duplicating).

## Test cases

```python
def test_port_tree_headless_no_entities_skips_subprocess(tmp_path):
    calls = []
    def fake_run(*a, **k):
        calls.append((a, k))
        raise AssertionError("must not be called when manifest is empty")
    summary = port.port_tree_headless(tmp_path, harness="copilot", warnings=[], run=fake_run)
    assert summary.command_ok is False
    assert calls == []


def test_port_tree_headless_missing_binary_raises(fixture_workspace, monkeypatch):
    monkeypatch.setenv("PATH", "")
    with pytest.raises(RuntimeError, match="copilot"):
        port.port_tree_headless(fixture_workspace.path("demo"), harness="copilot", warnings=[])


def test_port_tree_headless_dispatches_via_harness_build_command(fixture_workspace, monkeypatch, tmp_path):
    fake_bin = tmp_path / "bin" / "copilot"
    fake_bin.parent.mkdir()
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin.parent))

    calls = []
    def fake_run(cmd, *, cwd, env, capture_output, text, timeout, input):
        calls.append({"cmd": cmd, "env": env, "input": input})
        return subprocess.CompletedProcess(cmd, 0, stdout="ported 1 agent", stderr="")

    summary = port.port_tree_headless(
        fixture_workspace.path("demo"), harness="copilot", warnings=[], run=fake_run,
    )
    assert summary.command_ok is True
    assert summary.manifest_kinds == {"agents": 1, "hooks": 2, "loops": 0, "skills": 1}
    assert calls[0]["cmd"] == harnesses.get("copilot").build_command(
        str(fake_bin), tools=port.PORTING_TOOLS, model=harnesses.get("copilot").default_model,
        prompt=calls[0]["input"] or "",
    )
    assert "ANTHROPIC_API_KEY" not in calls[0]["env"]


def test_port_tree_headless_nonzero_exit_warns_not_raises(fixture_workspace, monkeypatch, tmp_path):
    fake_bin = tmp_path / "bin" / "copilot"
    fake_bin.parent.mkdir()
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin.parent))

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="permission denied")

    warnings = []
    summary = port.port_tree_headless(
        fixture_workspace.path("demo"), harness="copilot", warnings=warnings, run=fake_run,
    )
    assert summary.command_ok is False
    assert any("copilot" in w and "permission denied" in w for w in warnings)
```

## Implementation notes

- `test_port_tree_headless_dispatches_via_harness_build_command`'s exact
  `build_command` call assertion depends on task 02.0's confirmed contract
  (the `tools=`/`model=` values shown are the porting tool set from task 06.0
  subtask 01, not the marker-research one) - keep this test's expectation in
  sync with whatever `harnesses.get("copilot").build_command` actually
  requires once that lands.
- The "no entities skips subprocess" test is the concrete pin for
  `port_tree_headless`'s early-return-on-empty-manifest behavior (task 06.0
  subtask 02's implementation notes) - it must fail loudly (via the
  `AssertionError` inside `fake_run`) if that early return is ever removed.

## Constraints

- No real `copilot`/`junie` binary invoked - `fake_bin` only needs to exist
  and resolve via `PATH`; `fake_run` intercepts before any real subprocess
  call.
- `harness="junie"` variants of these same cases should be added once task
  03.0's outcome is known - either mirroring the `copilot` cases (outcome 1)
  or asserting the `RuntimeError`/empty-`binary_names` path directly
  (outcome 2).

## Success criteria

- [ ] All test cases above pass for `harness="copilot"`.
- [ ] Equivalent `harness="junie"` cases pass, in whichever shape task 03.0's
      outcome dictates.
- [ ] `uv run pytest tests/test_port.py -q` green.

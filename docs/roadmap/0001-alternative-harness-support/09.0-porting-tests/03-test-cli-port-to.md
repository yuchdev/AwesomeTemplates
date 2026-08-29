# 03 - `tests/test_cli.py`: `--port-to` validation tests

**Parent task:** 09.0 Porting pipeline tests
**State:** ⬜ Not started
**Depends on:** task 06.0 subtask 03 (`--port-to` flag + validation + dispatch)
**Blocks:** none

## Objective

Extend [`tests/test_cli.py`](/tests/test_cli.py) with `--port-to`'s
validation, gating, and dry-run cases, following the same
`runner.invoke(app, [...])` pattern task 05.0 subtask 03 uses for `--harness`.

## Test cases

```python
def test_generate_rejects_port_to_without_resolve_markers(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--port-to", "copilot", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "--port-to copilot requires --resolve-markers" in result.stdout


def test_generate_rejects_port_to_with_non_claude_harness(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        [
            "generate", ".", "--preset", "demo", "--name", "Test",
            "--resolve-markers", "--harness", "copilot", "--port-to", "junie", "--dry-run",
        ],
    )
    assert result.exit_code == 1
    assert "--port-to junie requires --harness claude" in result.stdout


def test_generate_rejects_unknown_port_to(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--port-to", "bogus", "--dry-run"],
    )
    assert result.exit_code == 2  # Click's own choice validation


def test_generate_dry_run_json_includes_port_to_null_by_default(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["generate", ".", "--preset", "demo", "--name", "Test", "--dry-run", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["port_to"] is None


def test_generate_port_to_missing_binary_fails_after_successful_claude_stage(
    fixture_workspace, tmp_path, monkeypatch
):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # force claude-CLI-missing fallback path off; adjust per task 04.0's actual env story
    monkeypatch.setenv("PATH", str(tmp_path))  # no copilot on PATH; claude fallback still needs handling

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate", str(out_dir), "--preset", "demo", "--name", "Test",
            "--resolve-markers", "--port-to", "copilot",
        ],
    )
    # Exact setup (mocking a successful claude stage without a real `claude`
    # binary) needs a scripted `claude` fake the same way test_headless.py's
    # kit fixture does, OR monkeypatching headless.resolve_tree_headless to a
    # stub - fill in once task 06.0 subtask 03 lands and this test can be run
    # against real code to see which setup is least brittle.
    assert result.exit_code == 1
    assert "copilot" in result.stdout
```

## Implementation notes

- `test_generate_port_to_missing_binary_fails_after_successful_claude_stage`
  is the one case in this file that needs the initial Claude stage to
  actually succeed before `--port-to`'s dispatch runs - the cleanest setup is
  probably `monkeypatch.setattr(cli_module.headless, "resolve_tree_headless",
  lambda *a, **k: (ResolveSummary(), []))` (or an equivalent stub for whatever
  path `--harness claude` actually takes in the test environment) so the test
  doesn't depend on a real `claude` binary being present in CI. Confirm the
  least brittle approach once task 06.0 subtask 03's code exists to run
  against.
- `test_generate_rejects_port_to_with_non_claude_harness` is the concrete pin
  for the strict "require `--harness claude`" design decision (not just a
  self-port check) - this is the single most important negative test in this
  subtask, since it's the one place the milestone's "Claude is always the
  reference harness" principle is actually enforced in code.

## Constraints

- No real `copilot`/`junie` binary invoked.
- `fixture_workspace`'s synthetic presets are sufficient for every case here -
  none of these tests need the real `templates/` tree.

## Success criteria

- [ ] All five test cases pass.
- [ ] `uv run pytest tests/test_cli.py -q` green.
- [ ] `uv run pytest --cov=awesome_templates -q` shows the new `--port-to`
      branches in `cli.py` covered.

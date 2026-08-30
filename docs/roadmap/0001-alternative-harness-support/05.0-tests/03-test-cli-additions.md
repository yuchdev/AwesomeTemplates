# 03 - `tests/test_cli.py` additions

**Parent task:** 05.0 Tests
**State:** ⬜ Not started
**Depends on:** task 04.0 (`--harness` flag + validation + dry-run + branching)
**Blocks:** none

## Objective

Extend [`tests/test_cli.py`](/tests/test_cli.py) with the four cases task
04.0's [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md) acceptance criteria name explicitly, following the existing
`test_generate_rejects_seed_roadmap_without_resolve_markers` pattern (line
171) for shape.

## Test cases

```python
def test_generate_rejects_harness_without_resolve_markers(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--harness", "copilot", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "--harness copilot requires --resolve-markers" in result.stdout


def test_generate_rejects_unknown_harness(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--harness", "gpt4", "--dry-run"],
    )
    assert result.exit_code == 2  # Click's own choice validation, not _fail's exit(1)


def test_generate_dry_run_json_includes_harness(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--dry-run", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["harness"] == "claude"


def test_generate_harness_binary_missing_fails_hard_no_fallback_for_non_claude(
    fixture_workspace, tmp_path, monkeypatch
):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    monkeypatch.setenv("PATH", str(tmp_path))  # nothing resolves, incl. no `claude`
    # Guard against an accidental silent fallback: resolver.resolve_tree must
    # never be called for a non-claude harness.
    def _boom(*a, **k):
        raise AssertionError("resolver.resolve_tree must not be called for --harness copilot")
    monkeypatch.setattr("awesome_templates.resolver.resolve_tree", _boom)

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate", str(out_dir), "--preset", "demo", "--name", "Test",
            "--resolve-markers", "--harness", "copilot",
        ],
    )
    assert result.exit_code == 1
    assert "copilot" in result.stdout
```

## Implementation notes

- `test_generate_rejects_unknown_harness` expects exit code `2` (Click's own
  validation failure), not `1` (`_fail`'s exit) - matching
  `test_docs_command_is_not_available`'s existing exit-code-2 pattern for a
  Click-level rejection rather than an application-level one.
- `test_generate_harness_binary_missing_fails_hard_no_fallback_for_non_claude`'s
  `_boom` monkeypatch is the concrete pin for [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s "no silent fallback"
  non-goal - it turns a silent regression (accidentally falling back to the
  one-shot API path for `copilot`) into a loud test failure instead of a
  passing-but-wrong test.
- Add a fifth case once task 03.0's outcome is known:
  `test_generate_harness_junie_no_headless_mode_message` (outcome 2) or a
  `junie`-flavored variant of the missing-binary test (outcome 1).

## Constraints

- `fixture_workspace` (from `tests/conftest.py`) provides the synthetic
  "demo"/"other" presets - no dependency on the real `templates/` tree for
  these tests.
- No real `copilot`/`junie` binary invoked.

## Success criteria

- [ ] All four (or five, once task 03.0's outcome is known) test cases pass.
- [ ] `uv run pytest tests/test_cli.py -q` green.
- [ ] `uv run pytest --cov=awesome_templates -q` shows no coverage regression
      on `cli.py`'s `resolve_value` branch.

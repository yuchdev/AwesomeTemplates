from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import awesome_templates.cli as cli_module
from awesome_templates.cli import app

runner = CliRunner()

POLICY = """
[tool.awesome_templates.model_policy]
mode = "warn"
[tool.awesome_templates.model_policy.recommended]
anthropic = ["claude-opus-5-5", "claude-sonnet-5-5"]
copilot = ["Sol 6.1"]
[tool.awesome_templates.model_policy.upgrade.anthropic]
families = { opus = "^claude-opus-", sonnet = "^claude-sonnet-" }
targets = { opus = "claude-opus-5-5", sonnet = "claude-sonnet-5-5" }
[tool.awesome_templates.model_policy.upgrade.copilot]
default = "Sol 6.1"
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    policy = tmp_path / "policy.toml"
    policy.write_text(POLICY)
    monkeypatch.setattr(cli_module, "PYPROJECT_PATH", policy)
    root = tmp_path / "proj"
    for rel, model in {
        ".claude/agents/a.md": "claude-opus-4-8",
        ".claude/agents/b.md": "claude-sonnet-4-6",
        ".github/agents/c.md": "GPT-4.1",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(f"---\nname: x\nmodel: {model}\n---\nbody\n")
    return root


def test_report_mode_lists_changes_writes_nothing_and_exits_one(project: Path):
    before = (project / ".claude/agents/a.md").read_text()
    result = runner.invoke(app, ["upgrade", str(project)])
    assert result.exit_code == 1
    out = " ".join(result.stdout.split())
    assert "claude-opus-4-8 -> claude-opus-5-5" in out and "claude-sonnet-4-6 -> claude-sonnet-5-5" in out
    assert "skipped copilot" in out  # unverified, not named
    assert (project / ".claude/agents/a.md").read_text() == before


def test_apply_writes_and_a_second_run_is_clean(project: Path):
    first = runner.invoke(app, ["upgrade", str(project), "--apply"])
    assert first.exit_code == 0, first.stdout
    assert "model: claude-opus-5-5\n" in (project / ".claude/agents/a.md").read_text()
    assert "model: GPT-4.1\n" in (project / ".github/agents/c.md").read_text()  # unverified: untouched
    assert runner.invoke(app, ["upgrade", str(project)]).exit_code == 0


def test_apply_reports_actual_writes_and_fails_when_application_is_incomplete(
    project: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(cli_module.upgrade, "apply_changes", lambda changes, warnings: 1)
    result = runner.invoke(app, ["upgrade", str(project), "--apply"])
    assert result.exit_code == 1
    assert "1/2 pin(s) updated" in " ".join(result.stdout.split())


def test_naming_an_unverified_harness_upgrades_it(project: Path):
    result = runner.invoke(app, ["upgrade", str(project), "--harness", "copilot", "--apply"])
    assert result.exit_code == 0, result.stdout
    assert "model: Sol 6.1\n" in (project / ".github/agents/c.md").read_text()
    assert "model: claude-opus-4-8\n" in (project / ".claude/agents/a.md").read_text()


def test_json_shape(project: Path):
    result = runner.invoke(app, ["upgrade", str(project), "--json"])
    payload = json.loads(result.stdout)
    assert payload["applied"] is False and len(payload["changes"]) == 2
    assert {"harness", "path", "line", "from", "to"} == set(payload["changes"][0])
    assert payload["skipped"][0]["harness"] == "copilot"


def test_apply_refuses_files_with_uncommitted_changes_unless_forced(project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        cli_module.upgrade, "dirty_files", lambda root, paths, **kw: [p for p in paths if p.name == "a.md"]
    )
    refused = runner.invoke(app, ["upgrade", str(project), "--apply"])
    assert refused.exit_code == 1 and "uncommitted" in " ".join(refused.stdout.split())
    assert "claude-opus-4-8" in (project / ".claude/agents/a.md").read_text()
    assert runner.invoke(app, ["upgrade", str(project), "--apply", "--force"]).exit_code == 0


def test_unknown_harness_and_missing_dir_fail(project: Path, tmp_path: Path):
    assert runner.invoke(app, ["upgrade", str(project), "--harness", "nope"]).exit_code == 1
    assert runner.invoke(app, ["upgrade", str(tmp_path / "missing")]).exit_code == 1


def test_policy_off_refuses(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    off = tmp_path / "off.toml"
    off.write_text('[tool.awesome_templates.model_policy]\nmode = "off"\n')
    monkeypatch.setattr(cli_module, "PYPROJECT_PATH", off)
    result = runner.invoke(app, ["upgrade", str(project)])
    assert result.exit_code == 1 and "policy is off" in " ".join(result.stdout.split())

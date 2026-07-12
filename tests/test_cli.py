from __future__ import annotations

import json

from typer.testing import CliRunner

import awesome_claude.cli as cli_module
from awesome_claude.cli import app

runner = CliRunner()


def test_list_json_runs():
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "presets" in payload
    assert "categories" in payload


def test_generate_dry_run_json():
    result = runner.invoke(
        app, ["generate", "--preset", "core-only", "--name", "Test", "--dry-run", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["out"] == ".claude"
    assert "core" in payload["plan"]


def test_generate_requires_name():
    result = runner.invoke(app, ["generate", "--preset", "core-only", "--dry-run"])
    assert result.exit_code == 1


def test_generate_rejects_unknown_preset():
    result = runner.invoke(app, ["generate", "--preset", "nope", "--name", "Test", "--dry-run"])
    assert result.exit_code == 1


def test_docs_new_unknown_type():
    result = runner.invoke(app, ["docs", "new", "bogus", "Title"])
    assert result.exit_code == 1


def test_generate_writes_a_real_kit(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / ".claude"
    result = runner.invoke(
        app,
        [
            "generate",
            "--preset",
            "core-only",
            "--name",
            "Acme Sync",
            "--out",
            str(out_dir),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    generated = (out_dir / "agents" / "widget-verifier.md").read_text()
    assert generated == "---\nname: widget-verifier\n---\n\nUse this agent for Acme Sync.\n"
    assert (out_dir / "settings.json").exists()


def test_generate_refuses_nonempty_out_without_force(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / ".claude"
    out_dir.mkdir()
    (out_dir / "existing.txt").write_text("pre-existing")
    result = runner.invoke(
        app, ["generate", "--preset", "core-only", "--name", "Acme", "--out", str(out_dir)]
    )
    assert result.exit_code == 1


def test_docs_copy_writes_files(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "docs-out"
    result = runner.invoke(app, ["docs", "copy", "--out", str(out_dir)])
    assert result.exit_code == 0, result.stdout
    assert (out_dir / "adr" / "template.md").is_file()


def test_docs_new_adr_writes_file(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["docs", "new", "adr", "A CLI-created decision"])
    assert result.exit_code == 0, result.stdout
    new_file = fixture_workspace.path("docs", "adr", "0002-a-cli-created-decision.md")
    assert new_file.is_file()
    assert "A CLI-created decision" in new_file.read_text()

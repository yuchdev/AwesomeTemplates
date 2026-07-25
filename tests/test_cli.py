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
    result = runner.invoke(app, ["docs", "copy", "--name", "Acme Sync", "--out", str(out_dir)])
    assert result.exit_code == 0, result.stdout
    assert (out_dir / "adr" / "template.md").is_file()


def test_docs_copy_requires_name(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "docs-out"
    result = runner.invoke(app, ["docs", "copy", "--out", str(out_dir)])
    assert result.exit_code == 1


def test_docs_copy_applies_substitution(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "foo.md").write_text("Hello {{PROJECT_NAME}}\n")
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", root)

    out_dir = tmp_path / "docs-out"
    result = runner.invoke(app, ["docs", "copy", "--name", "Acme Sync", "--out", str(out_dir)])
    assert result.exit_code == 0, result.stdout
    text = (out_dir / "foo.md").read_text()
    assert "Acme Sync" in text
    assert "{{PROJECT_NAME}}" not in text


def test_docs_copy_reports_unresolved_placeholder_warning(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "foo.md").write_text("Value: {{NOT_A_REAL_KEY}}\n")
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", root)

    out_dir = tmp_path / "docs-out"
    result = runner.invoke(app, ["docs", "copy", "--name", "Acme Sync", "--out", str(out_dir)])
    assert result.exit_code == 0, result.stdout
    assert "Warnings:" in result.stdout
    assert "unresolved placeholder" in result.stdout


def test_generate_copy_docs_applies_substitution(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "core" / "agents").mkdir(parents=True)
    (root / "core" / "agents" / "widget-verifier.md").write_text("An agent.\n")
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "x.md").write_text("Project: {{PROJECT_NAME}}\n")
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", root)

    out_dir = tmp_path / ".claude"
    docs_out_dir = tmp_path / "docs-out"
    result = runner.invoke(
        app,
        [
            "generate",
            "--categories",
            "core",
            "--name",
            "Acme",
            "--out",
            str(out_dir),
            "--copy-docs",
            "--docs-out",
            str(docs_out_dir),
        ],
    )
    assert result.exit_code == 0, result.stdout
    text = (docs_out_dir / "x.md").read_text()
    assert text == "Project: Acme\n"


def test_graph_command_writes_mermaid_doc(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_file = tmp_path / "dependency-graph.md"
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--out", str(out_file)])
    assert result.exit_code == 0, result.stdout
    text = out_file.read_text()
    assert "```mermaid" in text
    assert "graph LR" in text


def test_graph_command_json_output(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "nodes" in payload
    assert "edges" in payload


def test_graph_inline_flag_upserts_and_is_idempotent(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_file = tmp_path / "dependency-graph.md"

    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--out", str(out_file), "--inline"])
    assert result.exit_code == 0, result.stdout

    root = fixture_workspace.root
    before = {f: f.read_bytes() for f in root.rglob("*") if f.is_file()}

    result2 = runner.invoke(app, ["graph", str(fixture_workspace.root), "--out", str(out_file), "--inline", "--force"])
    assert result2.exit_code == 0, result2.stdout
    assert "Updated inline Dependencies block in 0 template file(s)" in result2.stdout

    after = {f: f.read_bytes() for f in root.rglob("*") if f.is_file()}
    assert before == after


def test_graph_inline_and_json_rejected_together(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--json", "--inline"])
    assert result.exit_code == 1


def test_graph_inline_requires_force_if_already_present(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)

    # 1. Run once to generate dependencies
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])
    assert result.exit_code == 0

    # 2. Run again without --force - should FAIL
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])
    assert result.exit_code == 1
    assert "already generated" in result.stdout
    assert "--force" in result.stdout


def test_graph_inline_succeeds_with_force_if_already_present(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)

    # 1. Run once to generate dependencies
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])
    assert result.exit_code == 0

    # 2. Run again WITH --force - should SUCCEED
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline", "--force"])
    assert result.exit_code == 0
    assert "Updated inline Dependencies block" in result.stdout


def test_docs_new_adr_writes_file(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["docs", "new", "adr", "A CLI-created decision"])
    assert result.exit_code == 0, result.stdout
    new_file = fixture_workspace.path("docs", "adr", "0002-a-cli-created-decision.md")
    assert new_file.is_file()
    assert "A CLI-created decision" in new_file.read_text()


def test_graph_remove_flag(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)

    agent_path = fixture_workspace.root / "core" / "agents" / "widget-verifier.md"
    hook_path = fixture_workspace.root / "core" / "hooks" / "_common.py"

    # 1. Add some dependencies first
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])
    assert result.exit_code == 0
    assert "<!-- BEGIN AUTOGENERATED: dependencies -->" in agent_path.read_text()
    assert "# BEGIN AUTOGENERATED: dependencies" in hook_path.read_text()

    # 2. Remove them
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--remove", "--verbose"])
    assert result.exit_code == 0
    assert "Removed inline Dependencies block" in result.stdout
    assert "widget-verifier.md: removed block" in result.stdout
    assert "_common.py: removed block" in result.stdout

    # 3. Verify they are gone
    assert "<!-- BEGIN AUTOGENERATED: dependencies -->" not in agent_path.read_text()
    assert "# BEGIN AUTOGENERATED: dependencies" not in hook_path.read_text()

    # 4. Run again - should say no block found in verbose mode and updated 0
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--remove", "--verbose"])
    assert result.exit_code == 0
    assert "Removed inline Dependencies block in 0 template file(s)" in result.stdout
    assert "widget-verifier.md: (no block found)" in result.stdout


def test_graph_inline_and_remove_mutually_exclusive(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline", "--remove"])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.stdout


def test_graph_remove_handles_spacing(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    agent_path = fixture_workspace.root / "core" / "agents" / "widget-verifier.md"

    original_content = agent_path.read_text()

    # Generate
    runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])

    # Remove
    runner.invoke(app, ["graph", str(fixture_workspace.root), "--remove"])

    # Content should be equal to original (modulo some potential whitespace normalization at the end)
    assert agent_path.read_text().strip() == original_content.strip()

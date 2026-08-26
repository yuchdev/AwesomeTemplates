from __future__ import annotations

import json

from typer.testing import CliRunner

import awesome_templates.cli as cli_module
from awesome_templates.cli import app

runner = CliRunner()


def test_top_level_help_includes_subcommand_options():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--log-verbosity" in result.stdout
    assert "--dry-run" in result.stdout
    assert "Usage: root docs" not in result.stdout


def test_docs_command_is_not_available():
    result = runner.invoke(app, ["docs"])
    assert result.exit_code == 2


def test_list_json_runs(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "demo" in payload
    assert payload["demo"]["agents"] == ["widget-verifier"]


def test_list_json_includes_specializations_per_preset(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["demo"]["specializations"] == ["widgets"]
    assert payload["other"]["specializations"] == []


def test_list_table_shows_specializations(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "specializations" in result.stdout
    assert "widgets" in result.stdout


def test_generate_dry_run_json(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["generate", ".", "--preset", "demo", "--name", "Test", "--dry-run", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["preset"] == "demo"
    assert payload["out"] == "."


def test_generate_requires_name(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["generate", ".", "--preset", "demo", "--dry-run"])
    assert result.exit_code == 1


def test_generate_rejects_unknown_preset(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["generate", ".", "--preset", "nope", "--name", "Test", "--dry-run"])
    assert result.exit_code == 1


def test_generate_rejects_unknown_specialization(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--specialization", "nope", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "unknown specialization" in result.stdout
    assert "widgets" in result.stdout  # lists the valid choice


def test_generate_dry_run_json_includes_specializations(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--specialization", "widgets", "--dry-run", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["specializations"] == ["widgets"]


def test_generate_dry_run_json_specializations_empty_by_default(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["generate", ".", "--preset", "demo", "--name", "Test", "--dry-run", "--json"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["specializations"] == []


def test_generate_with_specialization_writes_addon_agent(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        ["generate", str(out_dir), "--preset", "demo", "--name", "Acme", "--specialization", "widgets", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["specializations"] == ["widgets"]
    assert (out_dir / ".claude" / "agents" / "widget-specialist.md").is_file()
    assert (out_dir / ".claude" / "agents" / "widget-verifier.md").is_file()


def test_generate_writes_a_real_kit(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        ["generate", str(out_dir), "--preset", "demo", "--name", "Acme Sync", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    generated = (out_dir / ".claude" / "agents" / "widget-verifier.md").read_text()
    assert generated == "---\nname: widget-verifier\n---\n\nUse this agent for Acme Sync.\n"
    assert (out_dir / ".claude" / "settings.json").exists()
    assert (out_dir / "docs" / "adr" / "template.md").exists()
    assert (out_dir / "scripts" / "check_docs.py").exists()


def test_generate_refuses_nonempty_claude_without_force(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    (out_dir / ".claude").mkdir(parents=True)
    (out_dir / ".claude" / "existing.txt").write_text("pre-existing")
    result = runner.invoke(app, ["generate", str(out_dir), "--preset", "demo", "--name", "Acme"])
    assert result.exit_code == 1


def test_generate_refuses_nonempty_scripts_without_force(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    (out_dir / "scripts").mkdir(parents=True)
    (out_dir / "scripts" / "existing.py").write_text("pre-existing")
    result = runner.invoke(app, ["generate", str(out_dir), "--preset", "demo", "--name", "Acme"])
    assert result.exit_code == 1
    assert "scripts" in result.stdout


def test_generate_force_overwrites(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    (out_dir / ".claude").mkdir(parents=True)
    (out_dir / ".claude" / "existing.txt").write_text("pre-existing")
    result = runner.invoke(app, ["generate", str(out_dir), "--preset", "demo", "--name", "Acme", "--force"])
    assert result.exit_code == 0, result.stdout
    assert (out_dir / ".claude" / "agents" / "widget-verifier.md").exists()


def test_generate_applies_substitution_to_both_halves(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    (fixture_workspace.path("demo", "docs") / "x.md").write_text("Project: {{PROJECT_NAME}}\n")

    out_dir = tmp_path / "proj"
    result = runner.invoke(app, ["generate", str(out_dir), "--preset", "demo", "--name", "Acme"])
    assert result.exit_code == 0, result.stdout
    text = (out_dir / "docs" / "x.md").read_text()
    assert text == "Project: Acme\n"


def test_generate_rejects_seed_roadmap_without_resolve_markers(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--seed-roadmap", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "--seed-roadmap requires --resolve-markers" in result.stdout


def test_generate_populates_agents_doc_without_resolve_markers_flag(fixture_workspace, tmp_path, monkeypatch):
    # docgen runs unconditionally - no --resolve-markers, no API key needed.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    result = runner.invoke(app, ["generate", str(out_dir), "--preset", "demo", "--name", "Acme"])
    assert result.exit_code == 0, result.stdout
    agents_doc = (out_dir / "docs" / "agent" / "agents.md").read_text()
    assert agents_doc != "# Agent Reference\n"
    assert "widget-verifier" in agents_doc


def test_generate_help_documents_log_severity():
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    assert "TARGET_DIR" in result.stdout
    assert "--config-file" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--log-severity" in result.stdout


def test_generate_default_log_severity_stays_quiet(fixture_workspace, tmp_path, monkeypatch):
    # Default --log-severity (warning) must reproduce the exact pre-log_helper
    # output - no "copying preset"/"wrote ..." trace lines on stderr unless a
    # caller explicitly asks for --log-severity info or louder.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    result = runner.invoke(app, ["generate", str(out_dir), "--preset", "demo", "--name", "Acme"])
    assert result.exit_code == 0, result.stdout
    assert "copying preset" not in result.stderr
    assert "copying preset" not in result.stdout


def test_generate_log_severity_info_narrates_copy_steps(fixture_workspace, tmp_path, monkeypatch):
    # LogHelper writes to stderr, not stdout, so --json output stays parseable
    # regardless of --log-severity - see log_helper.py's module docstring.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            "--preset",
            "demo",
            "--name",
            "Acme",
            str(out_dir),
            "--log-severity",
            "info",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "copying preset 'demo'" in result.stderr
    assert "writing" in result.stderr  # docgen narration
    assert "copying preset" not in result.stdout  # never leaks onto stdout


def test_generate_log_severity_debug_traces_individual_files(fixture_workspace, tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            "--preset",
            "demo",
            "--name",
            "Acme",
            str(out_dir),
            "--log-severity",
            "debug",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "wrote" in result.stderr
    assert str(out_dir / ".claude" / "agents" / "widget-verifier.md") in result.stderr


def test_generate_json_output_stays_parseable_at_debug_log_severity(fixture_workspace, tmp_path, monkeypatch):
    # The whole point of writing trace output to stderr: --json's stdout must
    # remain valid JSON no matter how loud --log-severity is.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            "--preset",
            "demo",
            "--name",
            "Acme",
            str(out_dir),
            "--log-severity",
            "debug",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["preset"] == "demo"


def test_generate_produces_complete_preset_tree(fixture_workspace, tmp_path, monkeypatch):
    # Coupling is now structural (one preset tree, one copy) rather than a
    # runtime check: .claude/, docs/, and scripts/ always land together, from the same
    # source tree, so they can never drift out of sync at generation time.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    proj = tmp_path / "proj"
    result = runner.invoke(app, ["generate", str(proj), "--preset", "demo", "--name", "Big", "--json"])
    assert result.exit_code == 0, result.stdout
    assert (proj / ".claude").is_dir()
    assert (proj / "docs").is_dir()
    assert (proj / "scripts").is_dir()


# --- graph ---------------------------------------------------------------


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

    result2 = runner.invoke(
        app,
        ["graph", str(fixture_workspace.root), "--out", str(out_file), "--inline", "--force"],
    )
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

    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])
    assert result.exit_code == 1
    assert "already generated" in result.stdout
    assert "--force" in result.stdout


def test_graph_inline_succeeds_with_force_if_already_present(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)

    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline", "--force"])
    assert result.exit_code == 0
    assert "Updated inline Dependencies block" in result.stdout


def test_graph_remove_flag(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)

    agent_path = fixture_workspace.root / "demo" / ".claude" / "agents" / "widget-verifier.md"
    hook_path = fixture_workspace.root / "demo" / ".claude" / "hooks" / "_common.py"

    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])
    assert result.exit_code == 0
    assert "<!-- BEGIN AUTOGENERATED: dependencies -->" in agent_path.read_text()
    assert "# BEGIN AUTOGENERATED: dependencies" in hook_path.read_text()

    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--remove", "--log-verbosity", "debug"])
    assert result.exit_code == 0
    assert "Removed inline Dependencies block" in result.stdout
    assert "widget-verifier.md: removed block" in result.stdout
    assert "_common.py: removed block" in result.stdout

    assert "<!-- BEGIN AUTOGENERATED: dependencies -->" not in agent_path.read_text()
    assert "# BEGIN AUTOGENERATED: dependencies" not in hook_path.read_text()

    result = runner.invoke(app, ["graph", str(fixture_workspace.root), "--remove", "--log-verbosity", "debug"])
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
    agent_path = fixture_workspace.root / "demo" / ".claude" / "agents" / "widget-verifier.md"

    original_content = agent_path.read_text()

    runner.invoke(app, ["graph", str(fixture_workspace.root), "--inline"])
    runner.invoke(app, ["graph", str(fixture_workspace.root), "--remove"])

    assert agent_path.read_text().strip() == original_content.strip()

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from awesome_templates import headless
from awesome_templates.cli import app
from awesome_templates.markers import scan_tree

runner = CliRunner()


# --- fixture tree ----------------------------------------------------------


@pytest.fixture
def kit(tmp_path: Path) -> Path:
    """A minimal generated kit: two marker files (block, inline, SME) shaped
    like the real presets' agents."""
    root = tmp_path / "kit"
    agents = root / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "architect.md").write_text(
        "# Architect\n\n"
        "## Domain model\n\n"
        "<!-- TEMPLATE-INIT: research the architecture and describe it here -->\n",
        encoding="utf-8",
    )
    (agents / "reviewer.md").write_text(
        "# Reviewer\n\n"
        "Watch the hot paths: <!-- TEMPLATE-INIT: name the hot modules --> and be careful.\n\n"
        "<!-- SME REVIEW NEEDED: draft the threat model -->\n",
        encoding="utf-8",
    )
    return root


def _fake_run_factory(edits):
    """A fake subprocess.run capturing the call and applying `edits`
    ({path: new_text}) as if the session had made them."""
    calls = []

    def fake_run(cmd, *, input, cwd, env, capture_output, text, timeout):
        calls.append({"cmd": cmd, "input": input, "cwd": cwd, "env": env})
        for path, content in edits.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="did the work", stderr="")

    fake_run.calls = calls
    return fake_run


# --- project-root detection ------------------------------------------------


def test_detect_project_root_prefers_out_dir_with_manifest(tmp_path):
    out = tmp_path / "proj"
    out.mkdir()
    (out / "pyproject.toml").write_text("[project]\n")
    assert headless.detect_project_root(out, tmp_path) == out.resolve()


def test_detect_project_root_falls_back_to_cwd(tmp_path):
    out = tmp_path / "scratch" / "resolved"
    out.mkdir(parents=True)
    cwd = tmp_path / "realproj"
    (cwd / "src" / "pkg").mkdir(parents=True)
    (cwd / "src" / "pkg" / "main.py").write_text("")
    assert headless.detect_project_root(out, cwd) == cwd.resolve()


def test_detect_project_root_skeletal_everywhere_stays_out_dir(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    assert headless.detect_project_root(out, cwd) == out.resolve()


# --- manifest + prompt -----------------------------------------------------


def test_manifest_lists_every_marker_with_kit_relative_paths(kit, tmp_path):
    markers = scan_tree(kit)
    table = headless.render_manifest(markers, kit, tmp_path)
    assert "kit/.claude/agents/architect.md" in table
    assert "research the architecture" in table
    assert "SME REVIEW NEEDED" in table
    assert table.count("\n") == len(markers) + 1  # header + separator + rows


def test_prompt_embeds_manifest_and_closed_set_rule(kit, tmp_path):
    markers = scan_tree(kit)
    prompt = headless.build_prompt(
        markers, kit_root=kit, project_root=tmp_path, update_guidelines=False
    )
    assert "name the hot modules" in prompt
    assert "closed set of files you may edit" in prompt
    assert "TODO (fill in):" in prompt
    assert "README.md`, " not in prompt.split("## Resolution rules")[1]  # no guidelines section


def test_prompt_guidelines_section_only_when_enabled(kit, tmp_path):
    markers = scan_tree(kit)
    prompt = headless.build_prompt(
        markers, kit_root=kit, project_root=tmp_path, update_guidelines=True
    )
    assert "## Guideline docs" in prompt
    assert "kit/CLAUDE.md" in prompt
    assert "kit/AGENTS.md" in prompt


def test_prompt_same_root_collapses_root_note(kit):
    markers = scan_tree(kit)
    prompt = headless.build_prompt(
        markers, kit_root=kit, project_root=kit, update_guidelines=False
    )
    assert "both the current working directory" in prompt


# --- command construction --------------------------------------------------


def test_command_is_hard_allowlisted_and_skips_project_settings():
    cmd = headless.build_command("/bin/claude", update_guidelines=False)
    assert cmd[0] == "/bin/claude"
    assert "-p" in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == "user"
    # bypassPermissions is load-bearing: the kit's own .claude/** files are
    # otherwise blocked as sensitive, even under acceptEdits (see build_command).
    assert cmd[cmd.index("--permission-mode") + 1] == "bypassPermissions"
    tools = cmd[cmd.index("--tools") + 1 :]
    assert tools == ["Read", "Grep", "Glob", "Edit", "TodoWrite"]
    assert "Bash" not in cmd and "Write" not in cmd


def test_command_adds_write_only_for_guidelines():
    cmd = headless.build_command("/bin/claude", update_guidelines=True)
    assert "Write" in cmd[cmd.index("--tools") :]


# --- resolve_tree_headless -------------------------------------------------


def test_missing_api_key_leaves_ambient_auth(kit, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fake_run = _fake_run_factory({})
    headless.resolve_tree_headless(
        kit, api_key=None, warnings=[], claude_bin="/bin/claude",
        project_root=tmp_path, run=fake_run,
    )
    assert "ANTHROPIC_API_KEY" not in fake_run.calls[0]["env"]


def test_no_markers_skips_subprocess(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "plain.md").write_text("no markers here\n")
    warnings: list[str] = []

    def boom(*a, **k):  # must never be called
        raise AssertionError("subprocess invoked despite empty manifest")

    summary, guidelines = headless.resolve_tree_headless(
        tmp_path, api_key="k", warnings=warnings, claude_bin="/bin/claude", run=boom
    )
    assert summary.resolved == 0 and not warnings and guidelines == []


def test_full_session_reconciliation(kit, tmp_path):
    agents = kit / ".claude" / "agents"
    fake_run = _fake_run_factory(
        {
            agents / "architect.md": (
                "# Architect\n\n## Domain model\n\n"
                "The system is a `pipeline` built around `core/engine.py`.\n"
            ),
            agents / "reviewer.md": (
                "# Reviewer\n\n"
                "Watch the hot paths: `core/engine.py` and be careful.\n\n"
                "> **SME REVIEW NEEDED (AI-drafted - verify before relying on this):**\n"
                "> Threat model draft.\n"
            ),
        }
    )
    warnings: list[str] = []
    summary, guidelines = headless.resolve_tree_headless(
        kit,
        api_key="secret-key",
        warnings=warnings,
        claude_bin="/bin/claude",
        project_root=tmp_path,
        run=fake_run,
    )
    assert summary.resolved == 2
    assert summary.todos == 0
    assert summary.human_review == 1
    assert summary.failed == 0
    assert summary.files_touched == 2
    assert guidelines == []

    call = fake_run.calls[0]
    assert call["cwd"] == str(tmp_path.resolve())
    assert call["env"]["ANTHROPIC_API_KEY"] == "secret-key"
    assert "name the hot modules" in call["input"]


def test_todo_and_leftover_markers_counted(kit, tmp_path):
    agents = kit / ".claude" / "agents"
    # architect: honest TODO; reviewer: left completely untouched (2 markers fail)
    fake_run = _fake_run_factory(
        {
            agents / "architect.md": (
                "# Architect\n\n## Domain model\n\n"
                "> **TODO (fill in): research the architecture and describe it here**\n"
                "> Partial facts.\n"
            ),
        }
    )
    warnings: list[str] = []
    summary, _ = headless.resolve_tree_headless(
        kit, api_key="k", warnings=warnings, claude_bin="/bin/claude",
        project_root=tmp_path, run=fake_run,
    )
    assert summary.todos == 1
    assert summary.resolved == 0
    assert summary.failed == 2  # inline TEMPLATE-INIT + SME marker both untouched
    assert any("left a TODO" in w for w in warnings)
    assert any("left unresolved" in w for w in warnings)


def test_nonzero_exit_is_soft(kit, tmp_path):
    def failing_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    warnings: list[str] = []
    summary, _ = headless.resolve_tree_headless(
        kit, api_key="k", warnings=warnings, claude_bin="/bin/claude",
        project_root=tmp_path, run=failing_run,
    )
    assert summary.failed == 3  # all markers still in place
    assert any("exited with code 1" in w for w in warnings)


def test_timeout_is_soft(kit, tmp_path):
    def hanging_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))

    warnings: list[str] = []
    summary, _ = headless.resolve_tree_headless(
        kit, api_key="k", warnings=warnings, claude_bin="/bin/claude",
        project_root=tmp_path, run=hanging_run,
    )
    assert summary.failed == 3
    assert any("timed out" in w for w in warnings)


def test_guidelines_created_and_reported(kit, tmp_path):
    agents = kit / ".claude" / "agents"
    fake_run = _fake_run_factory(
        {
            agents / "architect.md": "# Architect\n\n## Domain model\n\nFacts about `core`.\n",
            agents / "reviewer.md": (
                "# Reviewer\n\nWatch the hot paths: `core/engine.py` and be careful.\n\n"
                "> **SME REVIEW NEEDED (AI-drafted - verify before relying on this):**\n"
                "> Draft.\n"
            ),
            kit / "README.md": "# Project\n",
            kit / "CLAUDE.md": "# Guidance\n",
            # AGENTS.md deliberately not produced -> warning
        }
    )
    warnings: list[str] = []
    summary, guidelines = headless.resolve_tree_headless(
        kit, api_key="k", warnings=warnings, claude_bin="/bin/claude",
        project_root=tmp_path, update_guidelines=True, run=fake_run,
    )
    assert guidelines == ["CLAUDE.md", "README.md"]
    assert any("did not produce AGENTS.md" in w for w in warnings)
    cmd = fake_run.calls[0]["cmd"]
    assert "Write" in cmd
    assert "## Guideline docs" in fake_run.calls[0]["input"]


def test_missing_claude_raises(kit, monkeypatch):
    monkeypatch.setattr(headless, "find_claude", lambda: None)
    with pytest.raises(RuntimeError, match="not on PATH"):
        headless.resolve_tree_headless(kit, api_key="k", warnings=[])


# --- CLI gating ------------------------------------------------------------


def test_cli_rejects_update_guidelines_without_resolve_markers(fixture_workspace, monkeypatch):
    monkeypatch.setattr("awesome_templates.cli.TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", "--preset", "demo", "--name", "Test", "--update-guidelines"],
    )
    assert result.exit_code == 1
    assert "--update-guidelines requires --resolve-markers" in result.output

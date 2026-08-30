from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from awesome_templates import harnesses, headless
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
        "# Architect\n\n## Domain model\n\n<!-- TEMPLATE-INIT: research the architecture and describe it here -->\n",
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
    prompt = headless.build_prompt(markers, kit_root=kit, project_root=tmp_path, update_guidelines=False)
    assert "name the hot modules" in prompt
    assert "closed set of files you may edit" in prompt
    assert "TODO (fill in):" in prompt
    assert "README.md`, " not in prompt.split("## Resolution rules")[1]  # no guidelines section


def test_prompt_guidelines_section_only_when_enabled(kit, tmp_path):
    markers = scan_tree(kit)
    prompt = headless.build_prompt(markers, kit_root=kit, project_root=tmp_path, update_guidelines=True)
    assert "## Guideline docs" in prompt
    assert "kit/CLAUDE.md" in prompt
    assert "kit/AGENTS.md" in prompt


def test_prompt_same_root_collapses_root_note(kit):
    markers = scan_tree(kit)
    prompt = headless.build_prompt(markers, kit_root=kit, project_root=kit, update_guidelines=False)
    assert "both the current working directory" in prompt


# --- command construction --------------------------------------------------


def test_command_is_hard_allowlisted_and_skips_project_settings():
    cmd = harnesses.get("claude").build_command(
        "/bin/claude", tools=("Read", "Grep", "Glob", "Edit", "TodoWrite"), model="opus"
    )
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
    cmd = harnesses.get("claude").build_command(
        "/bin/claude", tools=("Read", "Grep", "Glob", "Edit", "TodoWrite", "Write"), model="opus"
    )
    assert "Write" in cmd[cmd.index("--tools") :]


# --- resolve_tree_headless -------------------------------------------------


def test_missing_api_key_leaves_ambient_auth(kit, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fake_run = _fake_run_factory({})
    headless.resolve_tree_headless(
        kit,
        api_key=None,
        warnings=[],
        claude_bin="/bin/claude",
        project_root=tmp_path,
        run=fake_run,
    )
    assert "ANTHROPIC_API_KEY" not in fake_run.calls[0]["env"]


def test_non_forwarding_harness_strips_exported_key(kit, tmp_path, monkeypatch):
    # A non-forwarding harness (copilot/junie) must not leak an
    # ANTHROPIC_API_KEY the developer already has exported in their shell.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    non_forwarding = dataclasses.replace(harnesses.get("claude"), forwards_anthropic_key=False)
    monkeypatch.setattr(harnesses, "get", lambda name: non_forwarding)
    fake_run = _fake_run_factory({})
    headless.resolve_tree_headless(
        kit,
        api_key="k",
        warnings=[],
        claude_bin="/bin/claude",
        project_root=tmp_path,
        run=fake_run,
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
                "# Architect\n\n## Domain model\n\nThe system is a `pipeline` built around `core/engine.py`.\n"
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
        kit,
        api_key="k",
        warnings=warnings,
        claude_bin="/bin/claude",
        project_root=tmp_path,
        run=fake_run,
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
        kit,
        api_key="k",
        warnings=warnings,
        claude_bin="/bin/claude",
        project_root=tmp_path,
        run=failing_run,
    )
    assert summary.failed == 3  # all markers still in place
    assert any("exited with code 1" in w for w in warnings)


def test_timeout_is_soft(kit, tmp_path):
    def hanging_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))

    warnings: list[str] = []
    summary, _ = headless.resolve_tree_headless(
        kit,
        api_key="k",
        warnings=warnings,
        claude_bin="/bin/claude",
        project_root=tmp_path,
        run=hanging_run,
    )
    assert summary.failed == 3
    assert any("timed out" in w for w in warnings)


class _LogSpy:
    """Minimal LogHelper stand-in recording every message per level, so a test
    can assert on what would have been printed without touching stderr."""

    def __init__(self):
        self.messages: dict[str, list[str]] = {"error": [], "warning": [], "info": [], "debug": []}

    def error(self, message):
        self.messages["error"].append(message)

    def warning(self, message):
        self.messages["warning"].append(message)

    def info(self, message):
        self.messages["info"].append(message)

    def debug(self, message):
        self.messages["debug"].append(message)


def test_arg_harness_command_log_redacts_prompt(kit, tmp_path, monkeypatch):
    # A prompt_via="arg" harness embeds the whole marker-research prompt in argv;
    # the debug command-log line must redact it, not dump project context.
    arg_harness = harnesses.get("copilot")  # real prompt_via="arg" backend
    monkeypatch.setattr(harnesses, "get", lambda name: arg_harness)
    log = _LogSpy()
    fake_run = _fake_run_factory({})
    headless.resolve_tree_headless(
        kit,
        api_key=None,
        warnings=[],
        claude_bin="/bin/copilot",
        project_root=tmp_path,
        run=fake_run,
        log=log,
    )
    cmd_lines = [m for m in log.messages["debug"] if m.startswith("headless command:")]
    assert cmd_lines, "expected a debug command-log line"
    line = cmd_lines[0]
    assert "name the hot modules" not in line  # a marker instruction from the prompt
    assert "research the architecture" not in line
    assert "<prompt:" in line  # redaction placeholder present instead


def test_argv_too_large_is_soft(kit, tmp_path, monkeypatch):
    # An oversized argv (prompt_via="arg" over ARG_MAX) makes run() raise OSError
    # (E2BIG); like the timeout path it must degrade gracefully, not crash.
    arg_harness = harnesses.get("copilot")
    monkeypatch.setattr(harnesses, "get", lambda name: arg_harness)

    def too_big_run(cmd, **kwargs):
        raise OSError(7, "Argument list too long")  # errno 7 == E2BIG

    warnings: list[str] = []
    summary, _ = headless.resolve_tree_headless(
        kit,
        api_key=None,
        warnings=warnings,
        claude_bin="/bin/copilot",
        project_root=tmp_path,
        run=too_big_run,
    )
    assert summary.failed == 3  # all markers still in place
    assert any("prompt may be too large" in w for w in warnings)


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
        kit,
        api_key="k",
        warnings=warnings,
        claude_bin="/bin/claude",
        project_root=tmp_path,
        update_guidelines=True,
        run=fake_run,
    )
    assert guidelines == ["CLAUDE.md", "README.md"]
    assert any("did not produce AGENTS.md" in w for w in warnings)
    cmd = fake_run.calls[0]["cmd"]
    assert "Write" in cmd
    assert "## Guideline docs" in fake_run.calls[0]["input"]


def test_missing_claude_raises(kit, monkeypatch):
    # Simulate an uninstalled binary at the harness lookup itself; monkeypatching
    # PATH="" is unreliable because shutil.which falls back to os.defpath.
    monkeypatch.setattr(harnesses, "find_harness", lambda harness: None)
    with pytest.raises(RuntimeError, match="not on PATH"):
        headless.resolve_tree_headless(kit, api_key="k", warnings=[])


# --- resolve_tree_headless harness dispatch --------------------------------


def test_resolve_tree_headless_defaults_to_claude(kit, tmp_path):
    # No harness= kwarg: the session must resolve exactly as it did before the
    # harness registry existed - the claude backend, its opus default model, its
    # prompt piped over stdin, its ANTHROPIC_API_KEY forwarded into the env.
    fake_run = _fake_run_factory({})
    markers = scan_tree(kit)
    expected_prompt = headless.build_prompt(markers, kit_root=kit, project_root=tmp_path, update_guidelines=False)
    expected_cmd = harnesses.get("claude").build_command(
        "/bin/claude", tools=headless._BASE_TOOLS, model="opus", prompt=expected_prompt
    )
    headless.resolve_tree_headless(
        kit,
        api_key="k",
        warnings=[],
        claude_bin="/bin/claude",
        project_root=tmp_path,
        run=fake_run,
    )
    call = fake_run.calls[0]
    assert call["cmd"] == expected_cmd
    assert call["input"] == expected_prompt  # claude: prompt over stdin
    assert call["env"]["ANTHROPIC_API_KEY"] == "k"  # forwarded (forwards_anthropic_key=True)


def test_resolve_tree_headless_with_copilot_harness(kit, tmp_path, monkeypatch):
    # A fake copilot binary resolvable via shutil.which, never actually run (the
    # run= fake intercepts). The constructed argv must be exactly what copilot's
    # own build_command produces for that binary path, the base tools, no model,
    # and the real prompt resolve_tree_headless built - and ANTHROPIC_API_KEY
    # must be absent from the subprocess env (forwards_anthropic_key=False).
    fake_bin = tmp_path / "bin" / "copilot"
    fake_bin.parent.mkdir()
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin.parent))

    fake_run = _fake_run_factory({})
    markers = scan_tree(kit)
    expected_prompt = headless.build_prompt(markers, kit_root=kit, project_root=tmp_path, update_guidelines=False)
    # A non-empty key that must NOT reach copilot's env (forwards_anthropic_key=False).
    summary, _ = headless.resolve_tree_headless(
        kit,
        api_key="k",
        warnings=[],
        harness="copilot",
        project_root=tmp_path,
        run=fake_run,
    )
    call = fake_run.calls[0]
    assert call["cmd"] == harnesses.get("copilot").build_command(
        str(fake_bin),
        tools=headless._BASE_TOOLS,
        model=None,
        prompt=expected_prompt,
    )
    assert call["input"] is None  # copilot: prompt travels in argv, not stdin
    assert "ANTHROPIC_API_KEY" not in call["env"]  # forwards_anthropic_key=False


def test_resolve_tree_headless_with_junie_harness(kit, tmp_path, monkeypatch):
    # The marker-research contract (manifest, prompt, reconciliation) is
    # harness-agnostic; only the binary/argv/env change. Junie is a real
    # registry backend with a genuine headless mode, so its dispatch is pinned
    # the same way copilot's is: exact argv from its own build_command, no
    # ANTHROPIC_API_KEY leaked into its env.
    fake_bin = tmp_path / "bin" / "junie"
    fake_bin.parent.mkdir()
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin.parent))

    fake_run = _fake_run_factory({})
    markers = scan_tree(kit)
    expected_prompt = headless.build_prompt(markers, kit_root=kit, project_root=tmp_path, update_guidelines=False)
    # A non-empty key that must NOT reach junie's env (forwards_anthropic_key=False).
    summary, _ = headless.resolve_tree_headless(
        kit,
        api_key="k",
        warnings=[],
        harness="junie",
        project_root=tmp_path,
        run=fake_run,
    )
    call = fake_run.calls[0]
    assert call["cmd"] == harnesses.get("junie").build_command(
        str(fake_bin),
        tools=headless._BASE_TOOLS,
        model=None,
        prompt=expected_prompt,
    )
    assert call["input"] is None  # junie: prompt is a bare positional argv, not stdin
    assert "ANTHROPIC_API_KEY" not in call["env"]  # forwards_anthropic_key=False


def test_resolve_tree_headless_unknown_harness_raises(kit, tmp_path):
    # An unregistered harness name fails at the registry lookup (KeyError),
    # after the manifest scan but before any subprocess is constructed. Uses the
    # marker-carrying kit so the empty-manifest early return can't mask it.
    with pytest.raises(KeyError):
        headless.resolve_tree_headless(kit, api_key=None, warnings=[], harness="bogus", project_root=tmp_path)


def test_resolve_tree_headless_claude_missing_binary_message_names_claude(kit, monkeypatch):
    # Pin the harness lookup itself to "not installed" rather than emptying PATH:
    # shutil.which falls back to os.defpath when PATH="" on POSIX, so a stray
    # `claude` in /bin would false-pass (the same correction as
    # test_missing_claude_raises).
    monkeypatch.setattr(harnesses, "find_harness", lambda harness: None)
    with pytest.raises(RuntimeError, match="claude"):
        headless.resolve_tree_headless(kit, api_key=None, warnings=[])


# --- CLI gating ------------------------------------------------------------


def test_cli_rejects_update_guidelines_without_resolve_markers(fixture_workspace, monkeypatch):
    monkeypatch.setattr("awesome_templates.cli.TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--update-guidelines"],
    )
    assert result.exit_code == 1
    assert "--update-guidelines requires --resolve-markers" in result.output

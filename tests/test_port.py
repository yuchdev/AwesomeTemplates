"""Tests for `port.py`: the pure functions (`render_porting_manifest` and
`build_porting_prompt`) plus `port_tree_headless`'s subprocess boundary,
exercised against the real `harnesses.py` registry (copilot/junie) with a fake
`run=` so no real CLI is ever invoked.

`_stub_harness` fabricates a minimal `Harness` so the pure-function tests do not
depend on any real registry entry (`harnesses.get("copilot")` etc.) being wired.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import pytest

from awesome_templates import harnesses, port
from awesome_templates.harnesses import Harness
from awesome_templates.workspace import Workspace


def _stub_harness(hint: Optional[str] = None) -> Harness:
    return Harness(
        name="stub",
        binary_names=(),
        default_model=None,
        prompt_via="stdin",
        forwards_anthropic_key=False,
        build_command=lambda *a, **k: [],
        porting_target_hint=hint,
    )


def test_render_porting_manifest_counts_real_entities(fixture_workspace: Workspace) -> None:
    manifest, counts = port.render_porting_manifest(fixture_workspace.path("demo"))
    assert counts == {"agents": 1, "hooks": 2, "loops": 0, "skills": 1}
    assert "widget-verifier" in manifest
    assert "adr-write" in manifest


def test_render_porting_manifest_empty_tree_no_claude_dir(tmp_path: Path) -> None:
    manifest, counts = port.render_porting_manifest(tmp_path)
    assert counts == {"agents": 0, "hooks": 0, "loops": 0, "skills": 0}
    assert manifest.count("\n") <= 1  # header row only, no data rows


def test_build_porting_prompt_embeds_manifest(tmp_path: Path) -> None:
    manifest = "| Kind | Name | Path |\n|------|------|------|\n| `agents` | `x` | `.claude/agents/x.md` |"
    prompt = port.build_porting_prompt(manifest, kit_root=tmp_path, harness=_stub_harness())
    assert manifest in prompt
    assert "re-author" in prompt.lower() or "own idiom" in prompt.lower()


def test_build_porting_prompt_uses_harness_hint_when_set(tmp_path: Path) -> None:
    prompt = port.build_porting_prompt(
        "",
        kit_root=tmp_path,
        harness=_stub_harness(hint="Write to .github/copilot/"),
    )
    assert "Write to .github/copilot/" in prompt


def test_build_porting_prompt_generic_fallback_when_hint_none(tmp_path: Path) -> None:
    prompt = port.build_porting_prompt("", kit_root=tmp_path, harness=_stub_harness(hint=None))
    assert "idiomatic for your own tool" in prompt


def test_build_porting_prompt_never_instructs_editing_claude_dir(tmp_path: Path) -> None:
    prompt = port.build_porting_prompt("", kit_root=tmp_path, harness=_stub_harness())
    assert "do not edit" in prompt.lower() or "never" in prompt.lower()


# --- port_tree_headless: subprocess boundary -------------------------------
#
# Both real headless-porting backends (copilot from task 07.0, junie from task
# 08.0 - task 03.0 landed on Outcome 1: junie has a genuine headless mode) are
# `prompt_via="arg"`, `forwards_anthropic_key=False` harnesses whose dispatch
# must be pinned identically, so every case below is parametrized over both.
# No real `copilot`/`junie` binary is ever invoked: the fake executables only
# need to exist and resolve via `shutil.which`; `run=` intercepts before any
# real subprocess call. Per the spec's "check conftest first" note, there is no
# shared `fake_run` helper in `tests/conftest.py`, so each test uses its own
# inline closure (matching the spec's own inline-closure style) rather than
# importing `tests/test_headless.py::_fake_run_factory` across test files.

_PORT_HARNESSES = ["copilot", "junie"]


@pytest.mark.parametrize("harness", _PORT_HARNESSES)
def test_port_tree_headless_no_entities_skips_subprocess(tmp_path: Path, harness: str) -> None:
    calls: list[tuple] = []

    def fake_run(*a, **k):
        calls.append((a, k))
        raise AssertionError("must not be called when manifest is empty")

    summary = port.port_tree_headless(tmp_path, harness=harness, warnings=[], run=fake_run)
    assert summary.harness == harness
    assert summary.manifest_kinds == {"agents": 0, "hooks": 0, "loops": 0, "skills": 0}
    assert summary.command_ok is False
    assert calls == []


@pytest.mark.parametrize("harness", _PORT_HARNESSES)
def test_port_tree_headless_missing_binary_raises(
    fixture_workspace: Workspace, monkeypatch: pytest.MonkeyPatch, harness: str
) -> None:
    # Pin the harness lookup itself to "not installed" rather than emptying PATH:
    # shutil.which falls back to os.defpath when PATH="" on POSIX, so a stray
    # copilot/junie binary in a default bin dir would false-pass (the same
    # correction as tests/test_headless.py::test_missing_claude_raises).
    monkeypatch.setattr(harnesses, "find_harness", lambda harness: None)
    with pytest.raises(RuntimeError, match=harness):
        port.port_tree_headless(fixture_workspace.path("demo"), harness=harness, warnings=[])


@pytest.mark.parametrize("harness", _PORT_HARNESSES)
def test_port_tree_headless_dispatches_via_harness_build_command(
    fixture_workspace: Workspace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, harness: str
) -> None:
    # A fake binary resolvable via shutil.which, never actually run (run=
    # intercepts). A non-empty ANTHROPIC_API_KEY that must NOT reach the
    # subprocess env (forwards_anthropic_key=False for every --port-to target).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    fake_bin = tmp_path / "bin" / harness
    fake_bin.parent.mkdir()
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin.parent))

    calls: list[dict] = []

    def fake_run(cmd, *, cwd, env, capture_output, text, timeout, input):
        calls.append({"cmd": cmd, "cwd": cwd, "env": env, "input": input})
        return subprocess.CompletedProcess(cmd, 0, stdout="ported 1 agent", stderr="")

    out_dir = fixture_workspace.path("demo")
    summary = port.port_tree_headless(out_dir, harness=harness, warnings=[], run=fake_run)

    assert summary.command_ok is True
    assert summary.manifest_kinds == {"agents": 1, "hooks": 2, "loops": 0, "skills": 1}

    # Reconstruct the exact prompt port_tree_headless builds (via the real
    # manifest + the resolved kit root it uses as cwd), then assert the argv is
    # exactly what the harness's own build_command produces - not derived from
    # calls[0]["input"], which is always None for a prompt_via="arg" harness
    # (the prompt travels in argv, not stdin).
    harness_obj = harnesses.get(harness)
    manifest, _ = port.render_porting_manifest(out_dir)
    expected_prompt = port.build_porting_prompt(manifest, kit_root=out_dir.resolve(), harness=harness_obj)
    expected_cmd = harness_obj.build_command(
        str(fake_bin),
        tools=port.PORTING_TOOLS,
        model=harness_obj.default_model,
        prompt=expected_prompt,
    )
    assert calls[0]["cmd"] == expected_cmd
    assert calls[0]["input"] is None  # prompt_via="arg": prompt in argv, not stdin
    assert calls[0]["cwd"] == str(out_dir.resolve())
    assert "ANTHROPIC_API_KEY" not in calls[0]["env"]  # forwards_anthropic_key=False


@pytest.mark.parametrize("harness", _PORT_HARNESSES)
def test_port_tree_headless_nonzero_exit_warns_not_raises(
    fixture_workspace: Workspace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, harness: str
) -> None:
    fake_bin = tmp_path / "bin" / harness
    fake_bin.parent.mkdir()
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin.parent))

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="permission denied")

    warnings: list[str] = []
    summary = port.port_tree_headless(fixture_workspace.path("demo"), harness=harness, warnings=warnings, run=fake_run)
    assert summary.command_ok is False
    assert any(harness in w and "permission denied" in w for w in warnings)

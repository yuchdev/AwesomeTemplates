from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from awesome_templates import harnesses

# --- PATH-faking helper ----------------------------------------------------
# test_headless.py monkeypatches `harnesses.find_harness` directly (and notes
# PATH="" is unreliable because shutil.which falls back to os.defpath), so it
# has no reusable on-PATH helper. Per this subtask's spec we exercise the REAL
# resolution path instead: drop a real executable file in a tmp bin dir and put
# only that dir on PATH.


def _make_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *names: str) -> Path:
    """Create executable stub(s) `names` in a tmp bin dir and make it the sole
    PATH entry. Returns the bin dir."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name in names:
        exe = bindir / name
        exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bindir))
    return bindir


# --- find_harness ----------------------------------------------------------


def test_find_harness_resolves_first_matching_binary(tmp_path, monkeypatch):
    # Two candidate names, only the SECOND installed: find_harness must skip the
    # missing first and return the absolute path of the second.
    bindir = _make_on_path(tmp_path, monkeypatch, "second_bin")
    stub = harnesses.Harness(
        name="stub",
        binary_names=("first_bin_missing", "second_bin"),
        default_model=None,
        prompt_via="stdin",
        forwards_anthropic_key=False,
        build_command=lambda *a, **k: [],
    )
    found = harnesses.find_harness(stub)
    assert found == str(bindir / "second_bin")
    assert os.path.isabs(found)


def test_find_harness_prefers_earlier_binary_name(tmp_path, monkeypatch):
    # When BOTH candidates are installed the first-listed one wins.
    bindir = _make_on_path(tmp_path, monkeypatch, "alpha", "beta")
    stub = harnesses.Harness(
        name="stub",
        binary_names=("alpha", "beta"),
        default_model=None,
        prompt_via="stdin",
        forwards_anthropic_key=False,
        build_command=lambda *a, **k: [],
    )
    assert harnesses.find_harness(stub) == str(bindir / "alpha")


def test_find_harness_returns_none_when_no_candidate_installed(tmp_path, monkeypatch):
    _make_on_path(tmp_path, monkeypatch)  # empty bin dir, only entry on PATH
    stub = harnesses.Harness(
        name="stub",
        binary_names=("definitely_not_installed_xyz",),
        default_model=None,
        prompt_via="stdin",
        forwards_anthropic_key=False,
        build_command=lambda *a, **k: [],
    )
    assert harnesses.find_harness(stub) is None


def test_find_harness_returns_none_for_empty_binary_names():
    # covers task 03.0's outcome-2 stub shape: a Harness with binary_names=().
    stub = harnesses.Harness(
        name="stub",
        binary_names=(),
        default_model=None,
        prompt_via="stdin",
        forwards_anthropic_key=False,
        build_command=lambda *a, **k: [],
    )
    assert harnesses.find_harness(stub) is None


def test_find_harness_finds_real_claude_binary(tmp_path, monkeypatch):
    # The real _CLAUDE registration resolves through the same code path.
    bindir = _make_on_path(tmp_path, monkeypatch, "claude")
    assert harnesses.find_harness(harnesses.get("claude")) == str(bindir / "claude")


# --- get / registry --------------------------------------------------------


def test_get_unknown_harness_raises_keyerror():
    with pytest.raises(KeyError):
        harnesses.get("bogus")


def test_harness_names_all_registered():
    for name in harnesses.HARNESS_NAMES:
        assert harnesses.get(name).name == name


def test_get_claude_returns_registered_harness():
    harness = harnesses.get("claude")
    assert harness.name == "claude"
    assert harness.binary_names == ("claude",)
    assert harness.default_model == "opus"
    assert harness.prompt_via == "stdin"
    assert harness.forwards_anthropic_key is True


def test_get_copilot_registration_fields():
    harness = harnesses.get("copilot")
    assert harness.name == "copilot"
    assert harness.binary_names == ("copilot",)
    assert harness.default_model is None
    assert harness.prompt_via == "arg"
    assert harness.forwards_anthropic_key is False


def test_get_junie_registration_fields():
    harness = harnesses.get("junie")
    assert harness.name == "junie"
    assert harness.binary_names == ("junie",)
    assert harness.default_model is None
    assert harness.prompt_via == "arg"
    assert harness.forwards_anthropic_key is False


def test_copilot_does_not_forward_anthropic_key():
    assert harnesses.get("copilot").forwards_anthropic_key is False


def test_junie_does_not_forward_anthropic_key():
    assert harnesses.get("junie").forwards_anthropic_key is False


# --- _build_claude_command -------------------------------------------------


def test_build_claude_command_matches_todays_output():
    # Concrete pin for task 01.0's "relocation, not rewrite" / no-behavior-change
    # acceptance criterion: byte-identical argv, exact flag ordering.
    cmd = harnesses.get("claude").build_command(
        "/usr/local/bin/claude",
        tools=("Read", "Grep", "Glob", "Edit", "TodoWrite"),
        model="opus",
    )
    assert cmd == [
        "/usr/local/bin/claude",
        "-p",
        "--output-format",
        "text",
        "--setting-sources",
        "user",
        "--permission-mode",
        "bypassPermissions",
        "--no-session-persistence",
        "--model",
        "opus",
        "--tools",
        "Read",
        "Grep",
        "Glob",
        "Edit",
        "TodoWrite",
    ]


def test_build_claude_command_variadic_tools_go_last():
    # The write-enabled (--update-guidelines) tool set keeps identical structure:
    # --tools stays terminal so nothing is swallowed into its value list.
    cmd = harnesses.get("claude").build_command(
        "/usr/local/bin/claude",
        tools=("Read", "Grep", "Glob", "Edit", "TodoWrite", "Write"),
        model="opus",
    )
    assert cmd[cmd.index("--tools") + 1 :] == [
        "Read",
        "Grep",
        "Glob",
        "Edit",
        "TodoWrite",
        "Write",
    ]
    # prompt is accepted for parity but never embedded in claude's argv (stdin).
    assert "the prompt" not in cmd


def test_build_claude_command_ignores_prompt_arg():
    with_prompt = harnesses.get("claude").build_command(
        "/bin/claude", tools=("Read",), model="opus", prompt="a marker research prompt"
    )
    without_prompt = harnesses.get("claude").build_command("/bin/claude", tools=("Read",), model="opus")
    assert with_prompt == without_prompt
    assert "a marker research prompt" not in with_prompt


# --- _build_copilot_command ------------------------------------------------


def test_build_copilot_command_shape_no_model():
    cmd = harnesses.get("copilot").build_command(
        "/usr/local/bin/copilot",
        tools=("Read", "Edit"),
        model=None,
        prompt="do the research",
    )
    assert cmd == [
        "/usr/local/bin/copilot",
        "-p",
        "do the research",
        "--output-format",
        "text",
        "--allow-all-tools",
        "--deny-tool=shell",
        "--deny-tool=url",
        "--secret-env-vars=ANTHROPIC_API_KEY",
    ]


def test_build_copilot_command_appends_model_when_set():
    cmd = harnesses.get("copilot").build_command(
        "/usr/local/bin/copilot",
        tools=(),
        model="gpt-x",
        prompt="do the research",
    )
    assert cmd[-2:] == ["--model", "gpt-x"]
    # prompt stays adjacent to -p, its value slot.
    assert cmd[cmd.index("-p") + 1] == "do the research"


def test_build_copilot_command_raises_on_missing_prompt():
    # Regression: copilot's -p is both the non-interactive switch and the prompt
    # slot, so a None prompt would leave -p's value to be filled by the next flag
    # (broken argv). Found and fixed during /pr-review; load-bearing.
    with pytest.raises(ValueError):
        harnesses.get("copilot").build_command("/bin/copilot", tools=(), model=None, prompt=None)


def test_build_copilot_command_ignores_tools_for_flags(tmp_path):
    # tools is accepted for signature parity but never mapped onto flags.
    empty = harnesses.get("copilot").build_command("/bin/copilot", tools=(), model=None, prompt="p")
    populated = harnesses.get("copilot").build_command(
        "/bin/copilot",
        tools=("Read", "Grep", "Glob", "Edit", "TodoWrite"),
        model=None,
        prompt="p",
    )
    assert empty == populated
    assert "Read" not in populated and "--allow-tool" not in populated


# --- _build_junie_command --------------------------------------------------
# Task 03.0 landed on Outcome 1: a real headless mode was confirmed, so we pin
# the real argv shape (not the outcome-2 NotImplementedError branch).


def test_build_junie_command_shape_no_model():
    cmd = harnesses.get("junie").build_command(
        "/usr/local/bin/junie",
        tools=("Read", "Edit"),
        model=None,
        prompt="fix the bug",
    )
    assert cmd == [
        "/usr/local/bin/junie",
        "--output-format",
        "json",
        "--skip-update-check",
        "fix the bug",
    ]
    # bare positional task string is the final element (junie's only trigger).
    assert cmd[-1] == "fix the bug"


def test_build_junie_command_appends_model_before_prompt():
    cmd = harnesses.get("junie").build_command(
        "/usr/local/bin/junie",
        tools=(),
        model="junie-model",
        prompt="fix the bug",
    )
    assert cmd == [
        "/usr/local/bin/junie",
        "--output-format",
        "json",
        "--skip-update-check",
        "--model",
        "junie-model",
        "fix the bug",
    ]
    # prompt remains the terminal bare positional even with --model present.
    assert cmd[-1] == "fix the bug"


def test_build_junie_command_raises_on_missing_prompt():
    # Regression: the bare positional task string is junie's ONLY non-interactive
    # trigger, so a None prompt would silently drop into interactive mode rather
    # than failing cleanly. Found and fixed during /pr-review; load-bearing.
    with pytest.raises(ValueError):
        harnesses.get("junie").build_command("/bin/junie", tools=(), model=None, prompt=None)


def test_build_junie_command_ignores_tools_for_flags():
    # Junie exposes no tool/permission flag at all; tools must never become one.
    empty = harnesses.get("junie").build_command("/bin/junie", tools=(), model=None, prompt="p")
    populated = harnesses.get("junie").build_command(
        "/bin/junie",
        tools=("Read", "Grep", "Glob", "Edit", "TodoWrite"),
        model=None,
        prompt="p",
    )
    assert empty == populated
    assert "Read" not in populated and "--allow-tool" not in populated

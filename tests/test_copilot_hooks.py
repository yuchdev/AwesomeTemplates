"""Tests for Copilot-compatible payload handling in the shared hook helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
FAKE_CREDENTIAL = "sk-ant-" + ("A" * 36)


def _load_hook(name: str) -> ModuleType:
    sys.path.insert(0, str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(f"test_{name}", HOOKS_DIR / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_edited_path_accepts_copilot_camel_case() -> None:
    """Scenario: Copilot supplies filePath; Boundaries: relative path; On-failure: post-edit hooks skip the file."""
    common = _load_hook("_common")

    target = common.edited_path({"tool_input": {"filePath": "src/example.py"}})

    assert target == common.REPO_ROOT / "src" / "example.py"


@pytest.mark.parametrize(
    "tool_input",
    [
        {"newString": f"credential = '{FAKE_CREDENTIAL}'"},
        {"edits": [{"newString": f"credential = '{FAKE_CREDENTIAL}'"}]},
        {"patch": f"+ credential = '{FAKE_CREDENTIAL}'"},
    ],
)
def test_secret_scan_reads_copilot_edit_payloads(tool_input: dict[str, object]) -> None:
    """Scenario: Copilot edits contain a token; Boundaries: three payload shapes; On-failure: the write is allowed."""
    secret_scan = _load_hook("secret_scan")

    text = secret_scan._content_from_event({"tool_input": tool_input})

    assert secret_scan.scan_text(text)


def test_secret_scan_ignores_removed_patch_lines() -> None:
    """Scenario: a patch removes a token; Boundaries: deleted lines; On-failure: credential cleanup is blocked."""
    secret_scan = _load_hook("secret_scan")
    credential = FAKE_CREDENTIAL

    text = secret_scan._content_from_event(
        {"tool_input": {"patch": f"- credential = '{credential}'\n+ credential = '${{ANTHROPIC_API_KEY}}'"}}
    )

    assert not secret_scan.scan_text(text)


def test_placeholder_variable_name_does_not_hide_real_secret() -> None:
    """Scenario: a test-named variable holds a token; Boundaries: placeholder words; On-failure: secret is missed."""
    secret_scan = _load_hook("secret_scan")
    credential = FAKE_CREDENTIAL
    variable_name = "test_" + "api_key"

    assert secret_scan.scan_text(f"{variable_name} = '{credential}'")


def test_placeholder_word_inside_real_secret_does_not_bypass_scan() -> None:
    """Scenario: token text contains an allowlisted word; Boundaries: substring only; On-failure: secret is missed."""
    secret_scan = _load_hook("secret_scan")
    credential = "sk-ant-" + ("A" * 10) + "test" + ("B" * 20)

    assert secret_scan.scan_text(f"credential = '{credential}'")


@pytest.mark.parametrize("value", ["changeme", "${API_TOKEN}", "xxxxxxxx"])
def test_structured_placeholder_values_are_allowed(value: str) -> None:
    """Scenario: config uses an obvious placeholder; Boundaries: supported forms; On-failure: safe examples are blocked."""
    secret_scan = _load_hook("secret_scan")

    assert not secret_scan.scan_text(f"api_key = '{value}'")


def test_secret_hook_log_redacts_detected_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: a write is blocked; Boundaries: audit log fields; On-failure: the credential is persisted."""
    secret_scan = _load_hook("secret_scan")
    credential = FAKE_CREDENTIAL
    log_lines: list[str] = []
    monkeypatch.setattr(
        secret_scan,
        "read_event",
        lambda: {"tool_input": {"newString": f"credential = '{credential}'"}},
    )
    monkeypatch.setattr(secret_scan, "append_log", lambda _filename, line: log_lines.append(line))

    with pytest.raises(SystemExit) as exc_info:
        secret_scan._hook_mode()

    assert exc_info.value.code == 2
    assert credential not in "\n".join(log_lines)
    assert "Anthropic API key" in log_lines[0]


def test_secret_cli_output_redacts_detected_value(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario: a file scan finds a token; Boundaries: CLI output; On-failure: stdout discloses the credential."""
    secret_scan = _load_hook("secret_scan")
    credential = "sk-ant-" + ("A" * 36)
    target = tmp_path / "credentials.txt"
    target.write_text(f"credential = '{credential}'\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        secret_scan._cli_mode([str(target)])

    output = capsys.readouterr().out
    assert exc_info.value.code == 1
    assert credential not in output
    assert "Anthropic API key" in output

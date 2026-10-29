from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

from awesome_templates.log_helper import LogHelper, LogSeverity
from awesome_templates.model_policy import (
    ModelFinding,
    ModelPolicy,
    ModelPolicyError,
    PolicyMode,
    display_path,
    enforce,
    format_finding,
    load_policy,
    scan_agents_dir,
    scan_all,
    scan_generation,
    vendor_of,
)
from awesome_templates.workspace import Workspace

CURRENT = frozenset({"claude-opus-5-5", "claude-sonnet-5-5"})
OLD = "claude-opus-4-8"


def _policy(mode: PolicyMode = PolicyMode.warn) -> ModelPolicy:
    return ModelPolicy(mode, CURRENT)


def _agent(agents_dir: Path, name: str, model: Optional[str]) -> Path:
    agents_dir.mkdir(parents=True, exist_ok=True)
    model_line = f"model: {model}\n" if model is not None else ""
    path = agents_dir / f"{name}.md"
    path.write_text(f"---\nname: {name}\ndescription: x\n{model_line}---\n\nBody.\n", encoding="utf-8")
    return path


def _pyproject(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(body, encoding="utf-8")
    return path


# --- load_policy -----------------------------------------------------------------------------


def test_load_policy_missing_file_is_off(tmp_path: Path):
    policy = load_policy(tmp_path / "nope.toml")
    assert policy.mode is PolicyMode.off


def test_load_policy_missing_table_is_off(tmp_path: Path):
    # A repo that never configured a policy has not asked for one.
    assert load_policy(_pyproject(tmp_path, "[project]\nname = 'x'\n")).mode is PolicyMode.off


HEAD = "[tool.awesome_templates.model_policy]"
REC = "[tool.awesome_templates.model_policy.recommended]"


def test_load_policy_reads_mode_and_unions_vendors(tmp_path: Path):
    path = _pyproject(
        tmp_path,
        f'{HEAD}\nmode = "ERROR"\n{REC}\nanthropic = ["claude-opus-5-5"]\nopenai = ["gpt-x"]\n'
        '[tool.awesome_templates.model_policy.vendors]\nopenai = { key_env = "OAI_KEY" }\n',
    )
    policy = load_policy(path)
    assert policy.mode is PolicyMode.error  # case-insensitive
    assert policy.current == frozenset({"claude-opus-5-5", "gpt-x"})
    assert policy.recommended["openai"] == frozenset({"gpt-x"})
    assert policy.key_envs == {"openai": "OAI_KEY"}


def test_load_policy_mode_defaults_to_warn(tmp_path: Path):
    path = _pyproject(tmp_path, f'{HEAD}\n{REC}\nanthropic = ["claude-opus-5-5"]\n')
    assert load_policy(path).mode is PolicyMode.warn


def test_load_policy_rejects_unknown_mode(tmp_path: Path):
    # A typo must not silently disable the safety check.
    path = _pyproject(tmp_path, f'{HEAD}\nmode = "eror"\n{REC}\nanthropic = ["a"]\n')
    with pytest.raises(ModelPolicyError, match="eror"):
        load_policy(path)


@pytest.mark.parametrize(
    "body", ["", f"{REC}\nanthropic = []", f'{REC}\nanthropic = "claude-opus-5-5"', f"{REC}\nanthropic = [1]"]
)
def test_load_policy_active_mode_requires_real_recommendations(tmp_path: Path, body: str):
    path = _pyproject(tmp_path, f'{HEAD}\nmode = "warn"\n{body}\n')
    with pytest.raises(ModelPolicyError, match="recommended"):
        load_policy(path)


def test_load_policy_rejects_the_legacy_flat_current_list(tmp_path: Path):
    path = _pyproject(tmp_path, f'{HEAD}\nmode = "warn"\ncurrent = ["claude-opus-5-5"]\n')
    with pytest.raises(ModelPolicyError, match="recommended"):
        load_policy(path)


def test_load_policy_rejects_a_vendor_without_key_env(tmp_path: Path):
    path = _pyproject(
        tmp_path, f'{HEAD}\n{REC}\nanthropic = ["a"]\n[tool.awesome_templates.model_policy.vendors]\nanthropic = {{}}\n'
    )
    with pytest.raises(ModelPolicyError, match="key_env"):
        load_policy(path)


@pytest.mark.parametrize(
    ("model", "vendor"),
    [
        ("claude-opus-5-5", "anthropic"),
        ("gpt-5", "openai"),
        ("o3-mini", "openai"),
        ("gemini-2.5-pro", "google"),
        ("llama-3", None),
    ],
)
def test_vendor_of_infers_from_prefix(model: str, vendor: Optional[str]):
    assert vendor_of(model, _policy()) == vendor


def test_vendor_of_prefers_the_recommended_table():
    policy = ModelPolicy(PolicyMode.warn, frozenset({"llama-3"}), {"meta": frozenset({"llama-3"})})
    assert vendor_of("llama-3", policy) == "meta"


def test_load_policy_off_does_not_need_current(tmp_path: Path):
    path = _pyproject(tmp_path, '[tool.awesome_templates.model_policy]\nmode = "off"\n')
    assert load_policy(path).mode is PolicyMode.off


def test_load_policy_rejects_invalid_toml(tmp_path: Path):
    with pytest.raises(ModelPolicyError, match="cannot read"):
        load_policy(_pyproject(tmp_path, "this is = = not toml"))


# --- scan_agents_dir -------------------------------------------------------------------------


def test_scan_flags_only_non_current_pins(tmp_path: Path):
    agents = tmp_path / "agents"
    _agent(agents, "stale", OLD)
    _agent(agents, "fresh", "claude-sonnet-5-5")
    findings = scan_agents_dir(agents, _policy())
    assert [(f.path.name, f.model) for f in findings] == [("stale.md", OLD)]


@pytest.mark.parametrize("model", [None, "opus", "sonnet", "haiku", "inherit"])
def test_scan_exempts_missing_model_and_floating_aliases(tmp_path: Path, model: Optional[str]):
    # No pin / a floating alias can never go stale: Claude Code resolves it to the newest model itself.
    agents = tmp_path / "agents"
    _agent(agents, "a", model)
    assert scan_agents_dir(agents, _policy()) == []


def test_scan_unquotes_the_model_value(tmp_path: Path):
    agents = tmp_path / "agents"
    _agent(agents, "a", '"claude-opus-5-5"')
    _agent(agents, "b", f"'{OLD}'")
    assert [f.model for f in scan_agents_dir(agents, _policy())] == [OLD]


def test_scan_flags_unknown_ids_not_just_retired_ones(tmp_path: Path):
    # Allowlist semantics: a typo is caught as well as a retired model.
    agents = tmp_path / "agents"
    _agent(agents, "a", "claude-opus-5-55")
    assert [f.model for f in scan_agents_dir(agents, _policy())] == ["claude-opus-5-55"]


def test_scan_is_a_noop_when_off_or_dir_missing(tmp_path: Path):
    agents = tmp_path / "agents"
    _agent(agents, "stale", OLD)
    assert scan_agents_dir(agents, _policy(PolicyMode.off)) == []
    assert scan_agents_dir(tmp_path / "missing", _policy()) == []


# --- scope: scan_generation vs scan_all ------------------------------------------------------


@pytest.fixture
def scoped_workspace(tmp_path: Path) -> Workspace:
    """common + two presets, one with two specializations - every agent outdated, so the
    findings list *is* the scope that was scanned."""
    root = tmp_path / "templates"
    _agent(root / "common" / ".claude" / "agents", "common-agent", OLD)
    for preset in ("alpha", "beta"):
        _agent(root / preset / ".claude" / "agents", f"{preset}-agent", OLD)
        (root / preset / "docs").mkdir(parents=True)
    for spec in ("s1", "s2"):
        _agent(root / "alpha" / "specializations" / spec / ".claude" / "agents", f"{spec}-agent", OLD)
    return Workspace(root=root)


def _names(findings: list[ModelFinding]) -> set[str]:
    return {f.path.stem for f in findings}


def test_scan_generation_covers_common_preset_and_chosen_specializations_only(scoped_workspace: Workspace):
    findings = scan_generation(scoped_workspace, "alpha", ["s1"], _policy())
    # Not beta (another preset) and not s2 (a specialization nobody asked for).
    assert _names(findings) == {"common-agent", "alpha-agent", "s1-agent"}


def test_scan_generation_without_specializations_skips_them_all(scoped_workspace: Workspace):
    assert _names(scan_generation(scoped_workspace, "alpha", [], _policy())) == {"common-agent", "alpha-agent"}


def test_scan_all_covers_the_whole_tree(scoped_workspace: Workspace):
    assert _names(scan_all(scoped_workspace, _policy())) == {
        "common-agent",
        "alpha-agent",
        "beta-agent",
        "s1-agent",
        "s2-agent",
    }


# --- enforce ---------------------------------------------------------------------------------


def _finding(name: str = "x") -> ModelFinding:
    return ModelFinding(path=Path("/repo/templates/p/.claude/agents") / f"{name}.md", model=OLD)


def test_enforce_warn_appends_warnings_and_does_not_raise():
    warnings: list[str] = []
    enforce([_finding("a"), _finding("b")], _policy(PolicyMode.warn), warnings, relative_to=Path("/repo"))
    assert warnings == [
        f"outdated model in templates/p/.claude/agents/a.md: '{OLD}' is not in model_policy.recommended",
        f"outdated model in templates/p/.claude/agents/b.md: '{OLD}' is not in model_policy.recommended",
    ]


def test_enforce_warn_also_logs_each_finding(capsys: pytest.CaptureFixture[str]):
    enforce([_finding("a")], _policy(PolicyMode.warn), [], log=LogHelper(severity=LogSeverity.warning))
    assert "outdated model in" in capsys.readouterr().err


def test_enforce_error_raises_listing_every_offender_and_the_current_list():
    warnings: list[str] = []
    with pytest.raises(ModelPolicyError) as excinfo:
        enforce([_finding("a"), _finding("b")], _policy(PolicyMode.error), warnings)
    message = str(excinfo.value)
    assert "2 template agent(s)" in message
    assert "a.md" in message and "b.md" in message
    assert "claude-opus-5-5, claude-sonnet-5-5" in message
    assert warnings == []  # error mode reports through the exception, not the warnings list


def test_enforce_is_silent_with_no_findings_or_when_off():
    warnings: list[str] = []
    enforce([], _policy(PolicyMode.error), warnings)
    enforce([_finding()], _policy(PolicyMode.off), warnings)
    assert warnings == []


# --- display helpers -------------------------------------------------------------------------


def test_display_path_is_relative_only_when_under_the_base(tmp_path: Path):
    assert display_path(tmp_path / "a" / "b.md", tmp_path) == str(Path("a") / "b.md")
    assert display_path(Path("/elsewhere/b.md"), tmp_path) == str(Path("/elsewhere/b.md"))
    assert display_path(Path("/elsewhere/b.md")) == str(Path("/elsewhere/b.md"))


def test_format_finding_names_the_file_and_the_pin():
    text = format_finding(_finding("a"), Path("/repo"))
    assert "templates/p/.claude/agents/a.md" in text and OLD in text


# --- offline invariant -----------------------------------------------------------------------


def test_model_policy_import_does_not_pull_anthropic():
    # The check runs on every `generate`, including the plain offline one, so - like docgen - it must
    # never import anthropic, directly or transitively. Fresh interpreter = a true cold-import check.
    code = (
        "import sys; import awesome_templates.model_policy; "
        "assert 'anthropic' not in sys.modules, 'anthropic imported at load time'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

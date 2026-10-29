from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import awesome_templates.cli as cli_module
from awesome_templates.cli import app
from awesome_templates.workspace import Workspace

runner = CliRunner()

OLD = "claude-opus-4-8"
NEW = "claude-opus-5-5"


def _set_model(path: Path, model: str) -> None:
    path.write_text(
        f"---\nname: {path.stem}\nmodel: {model}\n---\n\nBody for {{{{PROJECT_NAME}}}}.\n", encoding="utf-8"
    )


def _policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    policy_file = tmp_path / "model-policy.toml"
    policy_file.write_text(body, encoding="utf-8")
    monkeypatch.setattr(cli_module, "MODEL_POLICY_PATH", policy_file)


def _mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    _policy(
        tmp_path,
        monkeypatch,
        f'mode = "{mode}"\n'
        f'[recommended]\nanthropic = ["{NEW}"]\n',
    )


@pytest.fixture
def stale_core(fixture_workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> Workspace:
    """`demo`'s own agent pins an outdated model; its `widgets` specialization is current."""
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    _set_model(fixture_workspace.path("demo", ".claude", "agents", "widget-verifier.md"), OLD)
    _set_model(
        fixture_workspace.path("demo", "specializations", "widgets", ".claude", "agents", "widget-specialist.md"), NEW
    )
    return fixture_workspace


@pytest.fixture
def stale_specialization(fixture_workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> Workspace:
    """The reverse: `demo` is current and only the opt-in `widgets` specialization is outdated."""
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    _set_model(fixture_workspace.path("demo", ".claude", "agents", "widget-verifier.md"), NEW)
    _set_model(
        fixture_workspace.path("demo", "specializations", "widgets", ".claude", "agents", "widget-specialist.md"), OLD
    )
    return fixture_workspace


def _generate(tmp_path: Path, *extra: str):
    out = tmp_path / "out"
    return out, runner.invoke(
        app, ["generate", ".", "--preset", "demo", "--name", "Test", "--output-dir", str(out), *extra]
    )


# --- generate: warn mode ---------------------------------------------------------------------


def test_generate_warn_mode_proceeds_and_reports_in_the_summary(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "warn")
    out, result = _generate(tmp_path, "--json")
    assert result.exit_code == 0, result.stdout
    assert (out / ".claude" / "agents" / "widget-verifier.md").is_file()  # generation went ahead
    summary = json.loads(result.stdout)
    assert any("outdated model" in w and OLD in w and "widget-verifier.md" in w for w in summary["warnings"])


def test_generate_dry_run_json_lists_model_warnings(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "warn")
    result = runner.invoke(app, ["generate", ".", "--preset", "demo", "--name", "T", "--dry-run", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload["model_warnings"]) == 1 and OLD in payload["model_warnings"][0]


def test_generate_with_all_current_models_has_no_model_warnings(stale_specialization, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "warn")
    result = runner.invoke(app, ["generate", ".", "--preset", "demo", "--name", "T", "--dry-run", "--json"])
    assert json.loads(result.stdout)["model_warnings"] == []


# --- generate: error mode (blocks) -----------------------------------------------------------


def test_generate_error_mode_blocks_and_writes_nothing(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "error")
    out, result = _generate(tmp_path)
    assert result.exit_code == 1
    assert "pin an outdated model" in " ".join(result.stdout.split())
    assert OLD in result.stdout
    assert not out.exists()  # the gate fires before copy_preset - no half-written tree


def test_generate_error_mode_also_blocks_dry_run(stale_core, tmp_path, monkeypatch):
    # --dry-run must fail the way a real run would, not defer the verdict to the real run.
    _mode(tmp_path, monkeypatch, "error")
    result = runner.invoke(app, ["generate", ".", "--preset", "demo", "--name", "T", "--dry-run"])
    assert result.exit_code == 1


def test_generate_error_mode_ignores_an_unchosen_stale_specialization(stale_specialization, tmp_path, monkeypatch):
    # A run is judged by what it copies: an opt-in specialization nobody asked for cannot block it.
    _mode(tmp_path, monkeypatch, "error")
    _, result = _generate(tmp_path)
    assert result.exit_code == 0, result.stdout


def test_generate_error_mode_blocks_when_the_stale_specialization_is_chosen(
    stale_specialization, tmp_path, monkeypatch
):
    _mode(tmp_path, monkeypatch, "error")
    out, result = _generate(tmp_path, "--specialization", "widgets")
    assert result.exit_code == 1
    assert "widget-specialist.md" in result.stdout
    assert not out.exists()


# --- generate: off / misconfigured -----------------------------------------------------------


def test_generate_off_mode_ignores_stale_pins(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "off")
    out, result = _generate(tmp_path, "--json")
    assert result.exit_code == 0, result.stdout
    assert not any("outdated model" in w for w in json.loads(result.stdout)["warnings"])


def test_generate_with_an_empty_policy_file_checks_nothing(stale_core, tmp_path, monkeypatch):
    _policy(tmp_path, monkeypatch, "")
    _, result = _generate(tmp_path, "--json")
    assert result.exit_code == 0, result.stdout


def test_generate_fails_loudly_on_a_malformed_policy(stale_core, tmp_path, monkeypatch):
    _policy(tmp_path, monkeypatch, 'mode = "eror"\n[recommended]\nanthropic = ["a"]\n')
    out, result = _generate(tmp_path)
    assert result.exit_code == 1
    assert "eror" in result.stdout
    assert not out.exists()


# --- check-models ----------------------------------------------------------------------------


def test_check_models_warn_reports_and_exits_zero(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "warn")
    result = runner.invoke(app, ["check-models"])
    assert result.exit_code == 0
    assert "widget-verifier.md" in result.stdout and "1 outdated pin(s)" in result.stdout


def test_check_models_error_reports_and_exits_one(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "error")
    result = runner.invoke(app, ["check-models"])
    assert result.exit_code == 1
    assert "widget-verifier.md" in result.stdout


def test_check_models_whole_tree_sees_unchosen_specializations(stale_specialization, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "error")
    result = runner.invoke(app, ["check-models"])
    assert result.exit_code == 1
    assert "widget-specialist.md" in result.stdout


def test_check_models_clean_tree(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "error")
    _set_model(stale_core.path("demo", ".claude", "agents", "widget-verifier.md"), NEW)
    result = runner.invoke(app, ["check-models"])
    assert result.exit_code == 0
    assert "current model" in result.stdout


def test_check_models_off_says_so_and_exits_zero(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "off")
    result = runner.invoke(app, ["check-models"])
    assert result.exit_code == 0
    assert "policy is off" in result.stdout


def test_check_models_json_shape(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "warn")
    result = runner.invoke(app, ["check-models", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "warn" and payload["current"] == [NEW]
    assert [f["model"] for f in payload["findings"]] == [OLD]
    assert payload["findings"][0]["path"].endswith("widget-verifier.md")


def test_check_models_preset_scopes_the_scan(stale_core, tmp_path, monkeypatch):
    # `other` has no model pins at all, so scoping to it is clean even though `demo` is stale.
    _mode(tmp_path, monkeypatch, "error")
    assert runner.invoke(app, ["check-models", "--preset", "other"]).exit_code == 0
    assert runner.invoke(app, ["check-models", "--preset", "demo"]).exit_code == 1


def test_check_models_rejects_unknown_preset(stale_core, tmp_path, monkeypatch):
    _mode(tmp_path, monkeypatch, "warn")
    assert runner.invoke(app, ["check-models", "--preset", "nope"]).exit_code == 1


# --- check-models --live ---------------------------------------------------------------------


def _fake_vendor(monkeypatch: pytest.MonkeyPatch, served: list[str], *, env: dict[str, str]) -> list[str]:
    """Route `check-models --live` through a fake Anthropic Models API; returns the requested URLs."""
    urls: list[str] = []
    real_verify = cli_module.model_catalog.verify

    def fetch(url, headers):
        urls.append(url)
        return json.dumps({"data": [{"id": m} for m in served], "has_more": False}).encode()

    monkeypatch.setattr(
        cli_module.model_catalog, "verify", lambda policy, pinned: real_verify(policy, pinned, env=env, fetch=fetch)
    )
    return urls


def _live_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    _policy(
        tmp_path,
        monkeypatch,
        f'mode = "{mode}"\n'
        f'[recommended]\nanthropic = ["{NEW}"]\n'
        '[vendors]\nanthropic = { key_env = "FAKE_KEY" }\n',
    )


def test_check_models_live_flags_an_unserved_recommendation_and_exits_one_in_error(stale_core, tmp_path, monkeypatch):
    _live_policy(tmp_path, monkeypatch, "error")
    _set_model(stale_core.path("demo", ".claude", "agents", "widget-verifier.md"), NEW)
    _fake_vendor(monkeypatch, ["claude-something-else"], env={"FAKE_KEY": "k"})
    result = runner.invoke(app, ["check-models", "--live"])
    assert result.exit_code == 1
    assert "does not list model" in " ".join(result.stdout.split()) and NEW in result.stdout


def test_check_models_live_in_warn_mode_reports_but_exits_zero(stale_core, tmp_path, monkeypatch):
    _live_policy(tmp_path, monkeypatch, "warn")
    _fake_vendor(monkeypatch, [], env={"FAKE_KEY": "k"})
    result = runner.invoke(app, ["check-models", "--live", "--json"])
    assert result.exit_code == 0
    live = json.loads(result.stdout)["live"]
    assert live["checked"] and {u["model"] for u in live["unserved"]} == {NEW, OLD}


def test_check_models_live_all_served_is_clean(stale_core, tmp_path, monkeypatch):
    _live_policy(tmp_path, monkeypatch, "error")
    _set_model(stale_core.path("demo", ".claude", "agents", "widget-verifier.md"), NEW)
    _fake_vendor(monkeypatch, [NEW], env={"FAKE_KEY": "k"})
    result = runner.invoke(app, ["check-models", "--live"])
    assert result.exit_code == 0 and "is served by its vendor" in " ".join(result.stdout.split())


def test_check_models_live_without_a_key_skips_instead_of_failing(stale_core, tmp_path, monkeypatch):
    _live_policy(tmp_path, monkeypatch, "warn")
    _set_model(stale_core.path("demo", ".claude", "agents", "widget-verifier.md"), NEW)
    urls = _fake_vendor(monkeypatch, [], env={})
    result = runner.invoke(app, ["check-models", "--live"])
    assert result.exit_code == 0 and urls == []
    assert "skipped" in result.stdout and "anthropic" in result.stdout
    assert "every recommended and pinned model is served" not in result.stdout
    assert "model checked" in result.stdout


def test_check_models_without_live_never_calls_the_vendor(stale_core, tmp_path, monkeypatch):
    _live_policy(tmp_path, monkeypatch, "warn")
    urls = _fake_vendor(monkeypatch, [], env={"FAKE_KEY": "k"})
    assert runner.invoke(app, ["check-models"]).exit_code == 0
    assert urls == []

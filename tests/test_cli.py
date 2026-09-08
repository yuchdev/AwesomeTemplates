from __future__ import annotations

import io
import json

import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner

import awesome_templates.cli as cli_module
from awesome_templates.cli import app
from awesome_templates.port import PortSummary
from awesome_templates.resolver import ResolveSummary

runner = CliRunner()


@pytest.fixture
def console_text(monkeypatch):
    """Capture what `cli_module.console` prints, for tests that call into cli.py
    directly instead of through the CliRunner.

    sanity_check reports through that module-level console, which the CliRunner
    picks up only because it captures the process's stdout - so this fixture is
    deliberately *not* autouse: swapping the console for every test would
    divert the output the CliRunner-based tests assert on. Returns a callable so
    a test reads the buffer after the call under test, not before. `width=200`
    keeps Rich from soft-wrapping short messages at all; `_flat` still
    normalizes anything that does wrap.
    """
    buffer = io.StringIO()
    monkeypatch.setattr(cli_module, "console", Console(file=buffer, width=200))
    return buffer.getvalue


def _flat(text: str) -> str:
    """Collapse Rich's soft line wrapping so a message assertion doesn't depend
    on the terminal width the test happened to run under - `console.print`
    wraps at the detected width, which can split a phrase mid-sentence."""
    return " ".join(text.split())


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


# --- sanity_check() called directly ------------------------------------------
#
# sanity_check documents a deliberate gate *order*, and order is exactly what
# end-to-end CLI invocations can't pin down: several of these combinations are
# invalid for more than one reason at once, and only the message says which
# reason won. These call it directly so the promised precedence is the thing
# under test.


def _check(**overrides):
    """Call sanity_check with a valid baseline, overridden per test."""
    kwargs = {
        "harness_value": None,
        "api_key": None,
        "api_key_env": None,
        "resolve_markers": False,
        "seed_roadmap": False,
        "update_guidelines": False,
        "port_to": None,
    }
    kwargs.update(overrides)
    cli_module.sanity_check(**kwargs)


def test_sanity_check_passes_the_plain_offline_case():
    _check()  # no engine, no AI stage - must not raise


def test_sanity_check_passes_the_supported_ai_case():
    _check(harness_value="claude", resolve_markers=True)


def test_sanity_check_rejects_api_key_and_api_key_env_together(console_text):
    # Gate 4: the two credential flags configure the same auth slot two ways, so
    # asking for both at once is incoherent - reported as a mutual-exclusion
    # error regardless of the AI stage's other flags.
    with pytest.raises(typer.Exit):
        _check(harness_value="claude", api_key="sk-x", api_key_env="ANTHROPIC_API_KEY", resolve_markers=True)
    assert "--api-key and --api-key-env are mutually exclusive" in _flat(console_text())


def test_sanity_check_credential_flag_requires_a_harness(console_text):
    # Gate 4: a credential flag authenticates a harness's session; with no
    # --harness named there is nothing for it to authenticate, so it is refused
    # before the AI stage is even considered.
    with pytest.raises(typer.Exit):
        _check(api_key="sk-x")
    assert "--api-key requires --harness" in _flat(console_text())


def test_sanity_check_credential_flag_gate_beats_not_implemented(console_text):
    # Gate 4 before gate 6: --api-key against a harness that authenticates only
    # through its own login (api_key_env is None, i.e. copilot/junie) is a flag
    # mistake, reported ahead of the less-actionable "copilot isn't built yet".
    with pytest.raises(typer.Exit):
        _check(harness_value="copilot", api_key="sk-x", resolve_markers=True)
    flat = _flat(console_text())
    assert "--harness copilot authenticates via its own login only" in flat
    assert "not implemented" not in flat


def test_sanity_check_unknown_name_beats_missing_engine(console_text):
    # Gate 2 before gate 4: a misspelled harness is a typo to fix, not a
    # "you didn't choose an engine" lecture.
    with pytest.raises(typer.Exit):
        _check(harness_value="claud", resolve_markers=True)
    assert "unknown harness 'claud'" in _flat(console_text())


def test_sanity_check_rider_prerequisite_beats_missing_engine(console_text):
    # Gate 3 before gate 4: --seed-roadmap without --resolve-markers is
    # reported as the rider problem, not as a missing engine.
    with pytest.raises(typer.Exit):
        _check(seed_roadmap=True)
    assert "--seed-roadmap requires --resolve-markers" in _flat(console_text())


def test_sanity_check_port_to_gate_beats_not_implemented(console_text):
    # Gate 5 before gate 6: --port-to with a non-claude harness is a flag
    # mistake, which is more actionable than "junie isn't built yet".
    with pytest.raises(typer.Exit):
        _check(harness_value="junie", resolve_markers=True, port_to="copilot")
    flat = _flat(console_text())
    assert "--port-to copilot requires --harness claude" in flat
    assert "not implemented" not in flat


def test_sanity_check_not_implemented_is_last(console_text):
    with pytest.raises(typer.Exit):
        _check(harness_value="junie", resolve_markers=True)
    assert "--harness junie is not implemented yet" in _flat(console_text())


def test_generate_rejects_harness_without_resolve_markers(fixture_workspace, monkeypatch):
    # An engine choice is meaningless on the offline path - naming one without
    # --resolve-markers is a mistake worth reporting, not a silent no-op. The
    # message must be reachable *before* the not-implemented gate, so this uses
    # copilot: a flag mistake is more actionable than "that harness isn't built".
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--harness", "copilot", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "--harness copilot has no effect without --resolve-markers" in _flat(result.stdout)


def test_generate_requires_a_harness_for_resolve_markers(fixture_workspace, monkeypatch):
    # The core of this contract: there is no default harness. --resolve-markers
    # with no --harness must refuse rather than quietly pick claude (and, with
    # ANTHROPIC_API_KEY exported, quietly bill an API).
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--resolve-markers", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "--resolve-markers requires --harness" in _flat(result.stdout)


@pytest.mark.parametrize("harness", ["copilot", "junie"])
def test_generate_rejects_unimplemented_harness(fixture_workspace, monkeypatch, harness):
    # copilot/junie stay valid *names* (their adapters exist) but are not wired
    # end-to-end, so they get a not-implemented notice, not "unknown harness".
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        [
            "generate",
            ".",
            "--preset",
            "demo",
            "--name",
            "Test",
            "--harness",
            harness,
            "--resolve-markers",
            "--dry-run",
        ],
    )
    assert result.exit_code == 1
    assert f"--harness {harness} is not implemented yet" in _flat(result.stdout)
    assert "unknown" not in result.stdout


def test_generate_backend_flag_is_gone(fixture_workspace, monkeypatch):
    # --backend was removed wholesale in task 10.0 (not merely gated): Typer/Click
    # itself rejects the flag as unknown (exit 2, "no such option") before the
    # command body runs, confirming it is fully absent from the option set.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--backend", "anthropic-api", "--dry-run"],
    )
    assert result.exit_code == 2  # Click's own option parsing, not _fail's exit(1)
    assert "no such option" in result.output.lower()


def test_generate_rejects_unknown_harness(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--harness", "gpt4", "--dry-run"],
    )
    assert result.exit_code == 2  # Click's own choice validation, not _fail's exit(1)


def test_generate_dry_run_json_includes_harness(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--dry-run", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    # No harness was asked for and none is defaulted in - the offline path picks
    # no vendor at all, and the payload has to say so rather than imply claude.
    # `--backend` is gone entirely, so the key must not resurface; auth reports
    # the default "login" source (no credential flag given).
    assert payload["harness"] is None
    assert "backend" not in payload
    assert payload["auth"] == "login"


@pytest.mark.parametrize("harness", ["copilot", "junie"])
def test_generate_unimplemented_harness_writes_nothing_at_all(fixture_workspace, tmp_path, monkeypatch, harness):
    # sanity_check's not-implemented gate runs before any generation, so an
    # unimplemented harness costs nothing: no output tree, no subprocess, and
    # emphatically no fallback to the direct-API path (which would be a silent
    # vendor substitution for the harness the user actually named).
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    monkeypatch.setenv("PATH", str(tmp_path))  # nothing resolves, incl. no CLI

    def _boom(*a, **k):
        raise AssertionError(f"no AI path may run for --harness {harness}")

    monkeypatch.setattr("awesome_templates.resolver.resolve_tree", _boom)
    monkeypatch.setattr("awesome_templates.headless.resolve_tree_headless", _boom)

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(out_dir),
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            harness,
        ],
    )
    assert result.exit_code == 1
    assert f"--harness {harness} is not implemented yet" in _flat(result.stdout)
    assert not out_dir.exists()


def test_generate_missing_claude_binary_fails_hard_with_no_api_fallback(fixture_workspace, tmp_path, monkeypatch):
    # The regression this hard-failure exists to prevent. `claude` absent from
    # PATH used to fall back to one-shot Messages API marker resolution -
    # silently, whenever ANTHROPIC_API_KEY merely happened to be exported. It
    # must now be a hard failure that names the missing CLI rather than quietly
    # taking a direct-API path, even with a key sitting right there in the env.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    monkeypatch.setenv("PATH", str(tmp_path))  # no `claude`
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-would-have-been-used")

    def _boom(*a, **k):
        raise AssertionError("the direct-API path must never run as a fallback")

    monkeypatch.setattr("awesome_templates.resolver.resolve_tree", _boom)

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(out_dir),
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
        ],
    )
    assert result.exit_code == 1
    flat = _flat(result.stdout)
    assert "the `claude` CLI was not found on PATH" in flat


def test_generate_never_forwards_an_api_key_into_the_harness_session(fixture_workspace, tmp_path, monkeypatch):
    # The no-flags (default) case. cli.py *can* forward a key now - that is
    # exactly what --api-key/--api-key-env do - but with neither flag given it
    # must still hand api_key=None to resolve_tree_headless regardless of any
    # ambient ANTHROPIC_API_KEY. The exact cause of the reported failure was
    # cli.py forwarding load_api_key(...)'s result unconditionally, where the
    # CLI treated ANTHROPIC_API_KEY as an auth source overriding the user's own
    # login - disabling org connectors and failing on an unfunded key. So the
    # default must forward nothing; headless.py's own tests cover the env
    # stripping that follows from api_key=None.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\nexit 0\n")
    fake_claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-must-not-be-forwarded")

    seen = {}

    def _capture(*a, **k):
        seen.update(k)
        return ResolveSummary(), []

    monkeypatch.setattr("awesome_templates.headless.resolve_tree_headless", _capture)

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(out_dir),
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert seen["api_key"] is None


# --- credential flags: --api-key / --api-key-env -----------------------------


def test_generate_api_key_flag_forwards_literal_value_to_harness(fixture_workspace, tmp_path, monkeypatch):
    # --api-key forwards its literal value straight into resolve_tree_headless's
    # api_key parameter - the credential the harness session authenticates with,
    # in place of the CLI's own login. This is the whole point of the flag.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\nexit 0\n")
    fake_claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    seen = {}

    def _capture(*a, **k):
        seen.update(k)
        return ResolveSummary(), []

    monkeypatch.setattr("awesome_templates.headless.resolve_tree_headless", _capture)

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(out_dir),
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
            "--api-key",
            "literal-key-value",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert seen["api_key"] == "literal-key-value"


def test_generate_api_key_env_forwards_variable_value_not_name(fixture_workspace, tmp_path, monkeypatch):
    # --api-key-env NAME reads NAME from the caller's own environment and
    # forwards its *value* (never the variable name itself) as the credential.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\nexit 0\n")
    fake_claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("MY_CUSTOM_KEY", "value-from-env")

    seen = {}

    def _capture(*a, **k):
        seen.update(k)
        return ResolveSummary(), []

    monkeypatch.setattr("awesome_templates.headless.resolve_tree_headless", _capture)

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(out_dir),
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
            "--api-key-env",
            "MY_CUSTOM_KEY",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert seen["api_key"] == "value-from-env"  # the value, not "MY_CUSTOM_KEY"


def test_generate_api_key_env_unset_variable_fails_before_subprocess(fixture_workspace, tmp_path, monkeypatch):
    # Naming a variable that isn't set is a clean exit-1 failure that names the
    # variable, raised before any harness subprocess is dispatched (the failure
    # happens during credential resolution, ahead of the binary lookup/run).
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    monkeypatch.setenv("PATH", str(tmp_path))  # no `claude` either
    monkeypatch.delenv("MISSING_KEY_VAR", raising=False)

    def _boom(*a, **k):
        raise AssertionError("no harness session may run when --api-key-env is unset")

    monkeypatch.setattr("awesome_templates.headless.resolve_tree_headless", _boom)

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(out_dir),
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
            "--api-key-env",
            "MISSING_KEY_VAR",
        ],
    )
    assert result.exit_code == 1
    flat = _flat(result.stdout)
    assert "MISSING_KEY_VAR" in flat
    assert "isn't set" in flat
    assert not out_dir.exists()  # nothing generated before the failure


def test_generate_rejects_api_key_and_api_key_env_together_via_cli(fixture_workspace, monkeypatch):
    # Mutual exclusion enforced end-to-end through sanity_check.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    monkeypatch.setenv("SOME_KEY_VAR", "v")
    result = runner.invoke(
        app,
        [
            "generate",
            ".",
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
            "--api-key",
            "literal-key-value",
            "--api-key-env",
            "SOME_KEY_VAR",
            "--dry-run",
        ],
    )
    assert result.exit_code == 1
    assert "--api-key and --api-key-env are mutually exclusive" in _flat(result.stdout)


def test_generate_rejects_api_key_without_harness(fixture_workspace, monkeypatch):
    # A credential flag has no session to authenticate without --harness.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--api-key", "literal-key-value", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "--api-key requires --harness" in _flat(result.stdout)


def test_generate_rejects_api_key_env_without_harness(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    monkeypatch.setenv("SOME_KEY_VAR", "v")
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--api-key-env", "SOME_KEY_VAR", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "--api-key-env requires --harness" in _flat(result.stdout)


@pytest.mark.parametrize("harness", ["copilot", "junie"])
def test_generate_rejects_credential_flag_for_login_only_harness(fixture_workspace, monkeypatch, harness):
    # copilot/junie authenticate only through their own login (api_key_env is
    # None), so a credential flag doesn't apply to them - and that flag mistake
    # is reported ahead of the less-actionable "not implemented yet" notice.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        [
            "generate",
            ".",
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            harness,
            "--api-key",
            "literal-key-value",
            "--dry-run",
        ],
    )
    assert result.exit_code == 1
    flat = _flat(result.stdout)
    assert f"--harness {harness} authenticates via its own login only" in flat
    assert "not implemented" not in flat


def test_generate_dry_run_json_auth_reports_api_key_source(fixture_workspace, monkeypatch):
    # Dry-run JSON's `auth` names the credential *source*, never the secret, and
    # still carries no `backend` key.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        [
            "generate",
            ".",
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
            "--api-key",
            "literal-key-value",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["auth"] == "api-key"
    assert "literal-key-value" not in result.stdout  # the source is named, not the secret
    assert "backend" not in payload


def test_generate_dry_run_json_auth_reports_api_key_env_source(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    monkeypatch.setenv("MY_KEY_VAR", "value-from-env")
    result = runner.invoke(
        app,
        [
            "generate",
            ".",
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
            "--api-key-env",
            "MY_KEY_VAR",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["auth"] == "api-key-env:MY_KEY_VAR"
    assert "value-from-env" not in result.stdout  # only the variable name surfaces
    assert "backend" not in payload


def test_generate_reads_api_key_env_from_config_file(fixture_workspace, tmp_path, monkeypatch):
    # --api-key-env names a variable, not a secret, so (unlike --api-key) it gets
    # the same config-file fallback every other scalar `generate` option has -
    # this is the one credential-flag path the CLI-flag tests above don't cover.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    monkeypatch.setenv("CONFIG_SOURCED_VAR", "value-from-config-sourced-env")
    config_path = tmp_path / "cfg.json"
    config_path.write_text(
        '{"harness": "claude", "api_key_env": "CONFIG_SOURCED_VAR", "preset": "demo", "project": {"name": "Test"}}'
    )
    result = runner.invoke(
        app,
        ["generate", ".", "--config-file", str(config_path), "--resolve-markers", "--dry-run", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["auth"] == "api-key-env:CONFIG_SOURCED_VAR"
    assert "value-from-config-sourced-env" not in result.stdout


def test_generate_reports_skipped_api_increments_under_a_harness(fixture_workspace, tmp_path, monkeypatch):
    # The tutorial/test-conventions/roadmap increments are direct Messages API
    # calls. Under a harness they must not run at all - and must be reported as
    # skipped rather than silently omitted, so a --seed-roadmap that produced
    # nothing says so.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\nexit 0\n")
    fake_claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-still-must-not-be-used")

    def _boom(*a, **k):
        raise AssertionError("no direct Messages API call may happen under --harness")

    monkeypatch.setattr("awesome_templates.resolver.maybe_write_tutorial", _boom)
    monkeypatch.setattr("awesome_templates.resolver.seed_first_milestone", _boom)
    monkeypatch.setattr("awesome_templates.resolver.maybe_describe_test_conventions", _boom)
    monkeypatch.setattr(
        "awesome_templates.headless.resolve_tree_headless",
        lambda *a, **k: (ResolveSummary(), []),
    )

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(out_dir),
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
            "--seed-roadmap",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["tutorial_written"] is False
    assert payload["roadmap_seeded"] is False
    assert payload["test_conventions_described"] is False
    assert payload["harness"] == "claude"
    assert "backend" not in payload
    assert payload["auth"] == "login"
    assert any("Nothing was sent to any vendor API" in w for w in payload["warnings"])


def test_generate_rejects_unknown_harness_from_config_file(fixture_workspace, tmp_path, monkeypatch):
    # A config-file `harness` value bypasses the HarnessChoice enum (Click only
    # validates the flag, never config.py's raw parsed dict), so cli.py guards
    # it explicitly before harnesses.get() - otherwise an unknown name would
    # reach get() and raise an uncaught KeyError (regression from task 04.0's
    # /pr-review).
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    config_path = tmp_path / "config.json"
    config_path.write_text('{"harness": "bogus", "preset": "demo", "project": {"name": "Test"}}')
    result = runner.invoke(
        app,
        ["generate", ".", "--config-file", str(config_path), "--dry-run"],
    )
    assert result.exit_code == 1
    assert "unknown harness 'bogus' (choices: claude, copilot, junie)" in result.stdout


# --- generate --port-to ---------------------------------------------------


def test_generate_rejects_port_to_without_resolve_markers(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--port-to", "copilot", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "--port-to copilot requires --resolve-markers" in result.stdout


def test_generate_rejects_port_to_with_non_claude_harness(fixture_workspace, monkeypatch):
    # The single most important negative test in this subtask: it pins the
    # strict "porting always reads a Claude-authored tree" rule - a non-claude
    # --harness is rejected even when --resolve-markers is present.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        [
            "generate",
            ".",
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "copilot",
            "--port-to",
            "junie",
            "--dry-run",
        ],
    )
    assert result.exit_code == 1
    assert "--port-to junie requires --harness claude" in result.stdout


def test_generate_rejects_unknown_port_to(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        ["generate", ".", "--preset", "demo", "--name", "Test", "--port-to", "bogus", "--dry-run"],
    )
    assert result.exit_code == 2  # Click's own choice validation, not _fail's exit(1)


def test_generate_dry_run_human_output_shows_harness_auth_and_port(fixture_workspace, monkeypatch):
    # The non-JSON dry-run branch prints the harness, auth source, and port-to
    # lines; this exercises that human-readable path (the JSON dry-run tests
    # cover the underlying payload data).
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(
        app,
        [
            "generate",
            ".",
            "--preset",
            "demo",
            "--name",
            "Test",
            "--specialization",
            "widgets",
            "--resolve-markers",
            "--harness",
            "claude",
            "--api-key",
            "literal-key-value",
            "--port-to",
            "copilot",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.stdout
    flat = _flat(result.stdout)
    assert "Harness: claude" in flat
    assert "Auth: api-key" in flat
    assert "Port to: copilot" in flat
    assert "Specializations: widgets" in flat


def test_generate_resolve_and_port_human_output(fixture_workspace, tmp_path, monkeypatch):
    # The success path through resolve + --update-guidelines + --port-to in
    # human-readable (non-JSON) form: exercises the console summary lines for
    # guideline docs and the port result. Both the harness research session and
    # the port session are stubbed, so no real CLI is invoked.
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\nexit 0\n")
    fake_claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    monkeypatch.setattr(
        "awesome_templates.headless.resolve_tree_headless",
        lambda *a, **k: (ResolveSummary(), ["README.md", "CLAUDE.md"]),
    )
    monkeypatch.setattr(
        "awesome_templates.port.port_tree_headless",
        lambda *a, **k: PortSummary(
            harness="copilot",
            manifest_kinds={"agents": 1, "skills": 0, "loops": 0, "hooks": 2},
            command_ok=True,
        ),
    )

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(out_dir),
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
            "--update-guidelines",
            "--port-to",
            "copilot",
        ],
    )
    assert result.exit_code == 0, result.stdout
    flat = _flat(result.stdout)
    assert "Guideline docs created/updated: README.md, CLAUDE.md" in flat
    assert "Ported to copilot" in flat


def test_generate_dry_run_json_includes_port_to_null_by_default(fixture_workspace, monkeypatch):
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)
    result = runner.invoke(app, ["generate", ".", "--preset", "demo", "--name", "Test", "--dry-run", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["port_to"] is None


def test_generate_port_to_missing_binary_fails_after_successful_claude_stage(fixture_workspace, tmp_path, monkeypatch):
    # The one case here that must reach the --port-to dispatch, which only runs
    # after the initial Claude-authored stage succeeds. Setup:
    #   * an explicit --harness claude (there is no default engine any more) and
    #     a fake `claude` on a scoped PATH so cli.py's `harness_bin` lookup
    #     resolves (find_harness uses shutil.which);
    #   * stub headless.resolve_tree_headless so that stage returns cleanly
    #     without ever executing the fake binary (patched on the real module,
    #     since cli.py imports it lazily as `from awesome_templates import
    #     headless` and calls it as a module attribute);
    # The API-only tutorial/roadmap/test-convention increments no longer run
    # under a harness at all, so no key handling is needed to keep them quiet.
    # copilot is absent from the same scoped PATH, so port.port_tree_headless
    # raises RuntimeError, which cli.py catches via _fail (exit 1).
    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", fixture_workspace.root)

    fake_claude = tmp_path / "claude"
    fake_claude.write_text("#!/bin/sh\nexit 0\n")
    fake_claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))  # scoped PATH: claude present, copilot absent (not PATH="")

    monkeypatch.setattr(
        "awesome_templates.headless.resolve_tree_headless",
        lambda *a, **k: (ResolveSummary(), []),
    )

    out_dir = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(out_dir),
            "--preset",
            "demo",
            "--name",
            "Test",
            "--resolve-markers",
            "--harness",
            "claude",
            "--port-to",
            "copilot",
        ],
    )
    assert result.exit_code == 1, result.stdout
    assert "copilot" in result.stdout
    # Specifically the port dispatch failing, not sanity_check refusing earlier.
    assert "not implemented" not in _flat(result.stdout)


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

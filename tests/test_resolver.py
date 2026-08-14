from __future__ import annotations

import json
from pathlib import Path

import pytest

# The resolver path is only meaningful with the `ai` extra installed; skip the
# whole module (rather than fail) when anthropic is absent, so the offline suite
# stays green without it.
anthropic = pytest.importorskip("anthropic")

import httpx

from awesome_templates import resolver
from awesome_templates.markers import find_markers
from awesome_templates.resolver import (
    ResolvedMarker,
    gather_context,
    load_api_key,
    maybe_describe_test_conventions,
    maybe_write_tutorial,
    parse_dotenv,
    render,
    render_milestone,
    resolve_tree,
    seed_first_milestone,
)

# --- fake client -----------------------------------------------------------


class _Text:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _Message:
    def __init__(self, payload: dict):
        self.content = [_Text(json.dumps(payload))]


class _Stream:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return _Message(self._payload)


class _Messages:
    def __init__(self, outcomes):
        # outcomes: a dict-payload/Exception, or a list consumed one per call
        self._outcomes = outcomes
        self.calls = 0

    def stream(self, **kwargs):
        self.calls += 1
        outcome = self._outcomes
        if isinstance(outcome, list):
            outcome = outcome[min(self.calls - 1, len(outcome) - 1)]
        return _Stream(outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.messages = _Messages(outcomes)


def _client(outcomes):
    return lambda: FakeClient(outcomes)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# --- .env / key loading ----------------------------------------------------


def test_parse_dotenv_handles_export_quotes_and_comments(tmp_path: Path):
    env_file = _write(
        tmp_path,
        ".env",
        "# a comment\nexport ANTHROPIC_API_KEY='sk-quoted'\nOTHER=plain\n\n",
    )
    env = parse_dotenv(env_file)
    assert env["ANTHROPIC_API_KEY"] == "sk-quoted"
    assert env["OTHER"] == "plain"


def test_load_api_key_env_beats_dotenv(tmp_path: Path, monkeypatch):
    _write(tmp_path, ".env", "ANTHROPIC_API_KEY=from-dotenv")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert load_api_key(tmp_path) == "from-env"


def test_load_api_key_falls_back_to_dotenv(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _write(tmp_path, ".env", "export ANTHROPIC_API_KEY=from-dotenv")
    assert load_api_key(tmp_path) == "from-dotenv"


# --- context bundle --------------------------------------------------------


def test_gather_context_includes_headings_and_respects_budget(tmp_path: Path):
    _write(tmp_path, "README.md", "This is the readme. " * 50)
    _write(tmp_path, "pyproject.toml", "[project]\nname='x'\n")
    _write(tmp_path, "src/app/main.py", "print('hi')\n")
    bundle = gather_context(tmp_path, char_budget=200)
    assert "## README.md" in bundle
    assert len(bundle) <= 200 + len("\n... (context truncated)")


# --- render ---------------------------------------------------------------


def test_render_low_confidence_is_todo_blockquote(tmp_path: Path):
    text = "before <!-- TEMPLATE-INIT: do the thing --> after"
    (marker,) = find_markers(text, tmp_path / "a.md")
    out = render(ResolvedMarker(marker=marker, prose="not sure", confident=False))
    assert out.startswith("> **TODO (fill in): do the thing**")
    assert "> not sure" in out


def test_render_sme_review_needed_always_flagged_even_when_confident(tmp_path: Path):
    text = "<!-- SME REVIEW NEEDED: populate with a threat model. -->"
    (marker,) = find_markers(text, tmp_path / "a.md")
    out = render(ResolvedMarker(marker=marker, prose="a drafted threat model outline", confident=True))
    assert out.startswith("> **SME REVIEW NEEDED")
    assert "> a drafted threat model outline" in out


# --- resolve_tree end to end (mocked) --------------------------------------


def test_resolve_tree_confident_replaces_marker(tmp_path: Path):
    _write(tmp_path, "a.md", "Domain:\n<!-- TEMPLATE-INIT: describe -->\nEnd\n")
    warnings: list[str] = []
    summary = resolve_tree(
        tmp_path,
        api_key="k",
        warnings=warnings,
        make_client=_client({"confident": True, "prose": "grounded prose"}),
    )
    result = (tmp_path / "a.md").read_text(encoding="utf-8")
    assert "TEMPLATE-INIT" not in result
    assert "grounded prose" in result
    assert summary.resolved == 1 and summary.todos == 0 and summary.failed == 0
    assert warnings == []


def test_resolve_tree_low_confidence_leaves_todo(tmp_path: Path):
    _write(tmp_path, "a.md", "<!-- TEMPLATE-INIT: describe the domain -->\n")
    warnings: list[str] = []
    summary = resolve_tree(
        tmp_path,
        api_key="k",
        warnings=warnings,
        make_client=_client({"confident": False, "prose": "no signal yet"}),
    )
    result = (tmp_path / "a.md").read_text(encoding="utf-8")
    assert "TEMPLATE-INIT" not in result
    assert "> **TODO (fill in): describe the domain**" in result
    assert summary.todos == 1 and summary.resolved == 0
    assert any("low confidence" in w for w in warnings)


def _rate_limit_error():
    req = httpx.Request("POST", "https://api.anthropic.com")
    return anthropic.RateLimitError("rate", response=httpx.Response(429, request=req), body=None)


def test_resolve_tree_api_error_leaves_marker_and_warns(tmp_path: Path):
    _write(tmp_path, "a.md", "<!-- TEMPLATE-INIT: describe -->\n")
    warnings: list[str] = []
    summary = resolve_tree(
        tmp_path,
        api_key="k",
        warnings=warnings,
        make_client=_client(_rate_limit_error()),
    )
    result = (tmp_path / "a.md").read_text(encoding="utf-8")
    assert "TEMPLATE-INIT" in result  # marker left intact
    assert summary.failed == 1 and summary.resolved == 0
    assert any("could not resolve" in w for w in warnings)


def _auth_error():
    req = httpx.Request("POST", "https://api.anthropic.com")
    return anthropic.AuthenticationError("bad", response=httpx.Response(401, request=req), body=None)


def test_resolve_tree_auth_error_aborts_with_one_warning(tmp_path: Path):
    _write(tmp_path, "a.md", "<!-- TEMPLATE-INIT: first -->\n<!-- TEMPLATE-INIT: second -->\n")
    warnings: list[str] = []
    summary = resolve_tree(
        tmp_path,
        api_key="k",
        warnings=warnings,
        make_client=_client(_auth_error()),
    )
    result = (tmp_path / "a.md").read_text(encoding="utf-8")
    assert result.count("TEMPLATE-INIT") == 2  # nothing resolved
    assert summary.failed == 1
    assert sum("aborted" in w for w in warnings) == 1


def test_resolve_tree_counts_sme_markers_as_human_review_not_resolved(tmp_path: Path):
    _write(tmp_path, "a.md", "<!-- SME REVIEW NEEDED: populate with a threat model. -->\n")
    warnings: list[str] = []
    summary = resolve_tree(
        tmp_path,
        api_key="k",
        warnings=warnings,
        make_client=_client({"confident": True, "prose": "a drafted threat model outline"}),
    )
    result = (tmp_path / "a.md").read_text(encoding="utf-8")
    assert "<!--" not in result  # marker comment syntax itself is gone...
    assert "> **SME REVIEW NEEDED" in result  # ...replaced by a flagged draft
    assert summary.human_review == 1
    assert summary.resolved == 0 and summary.todos == 0
    assert any("still needs human review" in w for w in warnings)


def test_resolve_tree_no_markers_is_noop(tmp_path: Path):
    _write(tmp_path, "a.md", "nothing to do here\n")
    warnings: list[str] = []
    summary = resolve_tree(tmp_path, api_key="k", warnings=warnings, make_client=_client({}))
    assert summary == resolver.ResolveSummary()
    assert warnings == []


# --- AI-assisted tutorial ---------------------------------------------------


def _build_tutorial_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / ".claude" / "agents" / "widget-verifier.md").write_text(
        "---\nname: widget-verifier\ndescription: Verifies widgets.\n---\n\nBody.\n"
    )
    (project / ".claude" / "skills").mkdir(parents=True)
    (project / "docs" / "agent").mkdir(parents=True)
    (project / "docs" / "agent" / "tutorial.md").write_text("# Agentic Tutorial\n")
    return project


def test_generate_tutorial_writes_content_referencing_real_agent_names(tmp_path: Path):
    project = _build_tutorial_project(tmp_path)
    warnings: list[str] = []
    client = FakeClient({"markdown": "# Tutorial\n\nStart with `widget-verifier`.\n"})

    written = maybe_write_tutorial(project, client, "context bundle", warnings)

    result = (project / "docs" / "agent" / "tutorial.md").read_text()
    assert written is True
    assert "widget-verifier" in result
    assert warnings == []


def test_maybe_write_tutorial_skips_when_already_customized(tmp_path: Path):
    project = _build_tutorial_project(tmp_path)
    (project / "docs" / "agent" / "tutorial.md").write_text("# My Own Tutorial\n\nAlready written.\n")
    warnings: list[str] = []
    client = FakeClient({"markdown": "should never be used"})

    written = maybe_write_tutorial(project, client, "context bundle", warnings)

    result = (project / "docs" / "agent" / "tutorial.md").read_text()
    assert written is False
    assert result == "# My Own Tutorial\n\nAlready written.\n"
    assert any("already customized" in w for w in warnings)


def test_maybe_write_tutorial_overwrites_the_stub(tmp_path: Path):
    project = _build_tutorial_project(tmp_path)
    client = FakeClient({"markdown": "# Tutorial\n\nReal content.\n"})

    written = maybe_write_tutorial(project, client, "context bundle", [])

    result = (project / "docs" / "agent" / "tutorial.md").read_text()
    assert written is True
    assert result == "# Tutorial\n\nReal content.\n"


# --- --seed-roadmap: "good first task" milestone seeding --------------------

_PLAN = {
    "milestone_title": "Notification Preferences",
    "task_slug": "notification-prefs",
    "task_name": "Notification Preferences",
    "subtasks": [
        {"slug": "prefs-model", "title": "Preferences model", "summary": "Add a preferences model."},
        {"slug": "prefs-endpoint", "title": "Preferences endpoint", "summary": "Expose it via an endpoint."},
    ],
}

_ROADMAP_SENTINEL_TEXT = (
    "Illustrative milestone. Replace this whole milestone with your own project's "
    "first real milestone once you adopt this template - it exists to show the "
    "shape, not to be extended.\n"
)


def test_render_milestone_produces_expected_file_tree():
    files = render_milestone(_PLAN)
    assert set(files) == {
        "plan.md",
        "status.md",
        "01.0-notification-prefs/README.md",
        "01.0-notification-prefs/01-prefs-model.md",
        "01.0-notification-prefs/02-prefs-endpoint.md",
    }
    assert "| 01.0 | Notification Preferences |" in files["status.md"]
    assert "Add a preferences model." in files["01.0-notification-prefs/01-prefs-model.md"]


def _build_example_milestone(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    milestone_dir = project / "docs" / "roadmap" / "0001-working-implementation"
    task_dir = milestone_dir / "01.0-hello-world-endpoint"
    task_dir.mkdir(parents=True)
    (milestone_dir / "plan.md").write_text(_ROADMAP_SENTINEL_TEXT)
    (milestone_dir / "status.md").write_text("# Milestone 0001 - Working Implementation - Status\n")
    (task_dir / "README.md").write_text("# Task 01.0 - Hello World Endpoint\n")
    return project


def test_seed_first_milestone_replaces_example_when_sentinel_present(tmp_path: Path):
    project = _build_example_milestone(tmp_path)
    warnings: list[str] = []
    client = FakeClient(_PLAN)

    acted = seed_first_milestone(project, client, "context bundle", warnings)

    milestone_dir = project / "docs" / "roadmap" / "0001-working-implementation"
    assert acted is True
    assert not (milestone_dir / "01.0-hello-world-endpoint").exists()  # example task gone
    assert (milestone_dir / "01.0-notification-prefs" / "README.md").is_file()
    assert "Notification Preferences" in (milestone_dir / "plan.md").read_text()
    assert warnings == []


def test_seed_first_milestone_noop_when_sentinel_already_gone(tmp_path: Path):
    project = _build_example_milestone(tmp_path)
    milestone_dir = project / "docs" / "roadmap" / "0001-working-implementation"
    milestone_dir.joinpath("plan.md").write_text("# Milestone 0001 - Our Real First Milestone\n")
    warnings: list[str] = []
    client = FakeClient({"should": "never be called"})

    acted = seed_first_milestone(project, client, "context bundle", warnings)

    assert acted is False
    assert (milestone_dir / "01.0-hello-world-endpoint").exists()  # left untouched
    assert any("already customized" in w for w in warnings)


# --- AI-drafted test-convention paragraph -----------------------------------


class _RecordingMessages(_Messages):
    def stream(self, **kwargs):
        self.last_kwargs = kwargs
        return super().stream(**kwargs)


class _RecordingClient:
    def __init__(self, outcomes):
        self.messages = _RecordingMessages(outcomes)


def _build_conventions_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "test_widgets.py").write_text("SUPER_SECRET_SOURCE_MARKER = 1\n")
    (project / "docs" / "test").mkdir(parents=True)
    (project / "docs" / "test" / "code_test_coverage.md").write_text("# Coverage\n")
    return project


def test_describe_test_conventions_uses_filenames_only_not_contents(tmp_path: Path):
    project = _build_conventions_project(tmp_path)
    client = _RecordingClient({"paragraph": "Tests mirror the module layout."})
    warnings: list[str] = []

    acted = maybe_describe_test_conventions(project, client, warnings)

    assert acted is True
    prompt = client.messages.last_kwargs["messages"][0]["content"]
    assert "tests/test_widgets.py" in prompt
    assert "SUPER_SECRET_SOURCE_MARKER" not in prompt
    result = (project / "docs" / "test" / "code_test_coverage.md").read_text()
    assert "Tests mirror the module layout." in result


def test_describe_test_conventions_skips_when_already_generated(tmp_path: Path):
    project = _build_conventions_project(tmp_path)
    (project / "docs" / "test" / "code_test_coverage.md").write_text(
        "# Coverage\n\n<!-- test-conventions:generated -->\n"
    )
    client = _RecordingClient({"paragraph": "should never be used"})
    warnings: list[str] = []

    acted = maybe_describe_test_conventions(project, client, warnings)

    assert acted is False
    assert any("already generated" in w for w in warnings)


def test_describe_test_conventions_noop_with_no_test_files(tmp_path: Path):
    project = tmp_path / "proj"
    (project / "docs" / "test").mkdir(parents=True)
    (project / "docs" / "test" / "code_test_coverage.md").write_text("# Coverage\n")
    client = _RecordingClient({"paragraph": "should never be used"})

    assert maybe_describe_test_conventions(project, client, []) is False

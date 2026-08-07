from __future__ import annotations

import json
from pathlib import Path

import pytest

# The resolver path is only meaningful with the `ai` extra installed; skip the
# whole module (rather than fail) when anthropic is absent, so the offline suite
# stays green without it.
anthropic = pytest.importorskip("anthropic")

import httpx

from awesome_claude import resolver
from awesome_claude.markers import find_markers
from awesome_claude.resolver import (
    ResolvedMarker,
    gather_context,
    load_api_key,
    parse_dotenv,
    render,
    resolve_tree,
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


def test_resolve_tree_no_markers_is_noop(tmp_path: Path):
    _write(tmp_path, "a.md", "nothing to do here\n")
    warnings: list[str] = []
    summary = resolve_tree(tmp_path, api_key="k", warnings=warnings, make_client=_client({}))
    assert summary == resolver.ResolveSummary()
    assert warnings == []

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
from typing import Mapping

import pytest

from awesome_templates import model_catalog
from awesome_templates.model_catalog import ModelCatalogError, UnservedModel, fetch_supported, verify
from awesome_templates.model_policy import ModelPolicy, PolicyMode

KEY = "sk-SECRET-123"


class FakeFetch:
    """Maps a URL substring to successive JSON bodies; records every (url, headers) it was asked for."""

    def __init__(self, pages: list[dict]):
        self.pages = list(pages)
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> bytes:
        self.calls.append((url, headers))
        return json.dumps(self.pages.pop(0)).encode()


def _policy(**recommended: list[str]) -> ModelPolicy:
    rec = {v: frozenset(ids) for v, ids in recommended.items()}
    envs = {"anthropic": "A_KEY", "openai": "O_KEY", "google": "G_KEY"}
    return ModelPolicy(PolicyMode.warn, frozenset(m for ids in rec.values() for m in ids), rec, envs)


def test_anthropic_follows_pagination_and_sends_the_key_in_a_header():
    fetch = FakeFetch(
        [
            {"data": [{"id": "claude-a"}], "has_more": True, "last_id": "claude-a"},
            {"data": [{"id": "claude-b"}], "has_more": False, "last_id": "claude-b"},
        ]
    )
    assert fetch_supported("anthropic", KEY, fetch=fetch) == {"claude-a", "claude-b"}
    assert "after_id=claude-a" in fetch.calls[1][0]
    assert fetch.calls[0][1]["x-api-key"] == KEY and "anthropic-version" in fetch.calls[0][1]
    assert all(KEY not in url for url, _ in fetch.calls)


def test_openai_uses_a_bearer_header():
    fetch = FakeFetch([{"data": [{"id": "gpt-5"}, {"id": "o3"}]}])
    assert fetch_supported("openai", KEY, fetch=fetch) == {"gpt-5", "o3"}
    assert fetch.calls[0][1]["Authorization"] == f"Bearer {KEY}"


def test_google_strips_the_models_prefix_and_follows_page_tokens():
    fetch = FakeFetch(
        [
            {"models": [{"name": "models/gemini-a"}], "nextPageToken": "t2"},
            {"models": [{"name": "models/gemini-b"}]},
        ]
    )
    assert fetch_supported("google", KEY, fetch=fetch) == {"gemini-a", "gemini-b"}
    assert "pageToken=t2" in fetch.calls[1][0]
    assert fetch.calls[0][1]["x-goog-api-key"] == KEY
    assert all(KEY not in url for url, _ in fetch.calls)


@pytest.mark.parametrize("vendor", ["anthropic", "openai", "google"])
@pytest.mark.parametrize(
    "body", [{"unexpected": 1}, {"data": "x", "models": "x"}, {"data": [{"nope": 1}], "models": [1]}]
)
def test_malformed_responses_raise_a_catalog_error(vendor: str, body: dict):
    with pytest.raises(ModelCatalogError):
        fetch_supported(vendor, KEY, fetch=FakeFetch([body]))


def test_non_json_response_raises():
    with pytest.raises(ModelCatalogError, match="not JSON"):
        fetch_supported("openai", KEY, fetch=lambda url, headers: b"<html>")


def test_endless_pagination_is_cut_off():
    endless = FakeFetch([{"data": [], "has_more": True, "last_id": "x"}] * (model_catalog.PAGE_LIMIT_GUARD + 1))
    with pytest.raises(ModelCatalogError, match="terminate"):
        fetch_supported("anthropic", KEY, fetch=endless)


def test_unknown_vendor_is_an_error():
    with pytest.raises(ModelCatalogError, match="no Models API client"):
        fetch_supported("mistral", KEY, fetch=FakeFetch([]))


def test_http_get_wraps_failures_without_leaking_the_key(monkeypatch: pytest.MonkeyPatch):
    def boom(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(model_catalog.urllib.request, "urlopen", boom)
    with pytest.raises(ModelCatalogError) as caught:
        model_catalog.http_get("https://api.openai.com/v1/models", {"Authorization": f"Bearer {KEY}"})
    assert "401" in str(caught.value) and KEY not in str(caught.value)


def test_http_get_wraps_network_errors(monkeypatch: pytest.MonkeyPatch):
    def down(request, timeout):
        raise urllib.error.URLError("dns")

    monkeypatch.setattr(model_catalog.urllib.request, "urlopen", down)
    with pytest.raises(ModelCatalogError, match="request failed"):
        model_catalog.http_get("https://api.openai.com/v1/models", {})


# --- verify ----------------------------------------------------------------------------------


def test_verify_reports_recommended_and_pinned_ids_the_vendor_does_not_serve():
    fetch = FakeFetch([{"data": [{"id": "claude-ok"}], "has_more": False}])
    result = verify(
        _policy(anthropic=["claude-ok", "claude-typo"]),
        ["claude-ok", "claude-retired"],
        env={"A_KEY": KEY},
        fetch=fetch,
    )
    assert result.unserved == [UnservedModel("anthropic", "claude-retired"), UnservedModel("anthropic", "claude-typo")]
    assert result.skipped_vendors == []


def test_verify_skips_a_vendor_without_a_key_and_never_contacts_it():
    fetch = FakeFetch([])
    result = verify(_policy(openai=["gpt-5"]), [], env={}, fetch=fetch)
    assert result.skipped_vendors == ["openai"] and result.unserved == [] and fetch.calls == []


def test_verify_does_not_contact_vendors_with_nothing_to_check():
    fetch = FakeFetch([{"data": [{"id": "claude-ok"}], "has_more": False}])
    verify(_policy(anthropic=["claude-ok"], openai=[], google=[]), [], env={"A_KEY": KEY, "O_KEY": KEY}, fetch=fetch)
    assert len(fetch.calls) == 1


def test_verify_routes_an_unlisted_pin_by_prefix():
    fetch = FakeFetch([{"models": [{"name": "models/gemini-ok"}]}])
    result = verify(_policy(anthropic=[]), ["gemini-typo"], env={"G_KEY": KEY}, fetch=fetch)
    assert result.unserved == [UnservedModel("google", "gemini-typo")]


def test_verify_refuses_a_pin_no_vendor_claims():
    with pytest.raises(ModelCatalogError, match="llama-3"):
        verify(_policy(anthropic=["claude-ok"]), ["llama-3"], env={}, fetch=FakeFetch([]))


def test_format_unserved_names_vendor_and_model():
    assert "openai" in model_catalog.format_unserved(UnservedModel("openai", "gpt-x"))


def test_model_catalog_import_does_not_pull_anthropic():
    code = "import sys; import awesome_templates.model_catalog; sys.exit('anthropic' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0

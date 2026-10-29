from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from awesome_templates import model_catalog, model_state
from awesome_templates.model_state import ModelStateError

NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)
KEY_ENVS = {"anthropic": "A_KEY", "openai": "O_KEY", "google": "G_KEY"}
DAY = timedelta(hours=24)


class FakeFetch:
    """Answers every vendor's list endpoint; records the URLs so a test can assert on 'no request'."""

    def __init__(self, ids=("m1", "m2")):
        self.ids, self.urls, self.fail = list(ids), [], False

    def __call__(self, url, headers):
        self.urls.append(url)
        if self.fail:
            raise model_catalog.ModelCatalogError("boom: HTTP 500")
        if "anthropic" in url:
            return json.dumps({"data": [{"id": i} for i in self.ids], "has_more": False}).encode()
        if "openai" in url:
            return json.dumps({"data": [{"id": i} for i in self.ids]}).encode()
        return json.dumps({"models": [{"name": f"models/{i}"} for i in self.ids]}).encode()


def _data(**live) -> dict:
    return {"schema": 1, "revision": "2026-10-29", "recommended": {}, "live": live}


def _entry(age: timedelta, ids=("old",)) -> dict:
    return {"fetched_at": model_state.format_time(NOW - age), "served": list(ids)}


# --- paths and seeding -----------------------------------------------------------------------


def test_default_state_path_uses_dot_local_state_awesome(tmp_path: Path):
    assert model_state.default_state_path({}, tmp_path) == tmp_path / ".local" / "state" / "awesome" / "models.json"


def test_default_state_path_honours_xdg_state_home(tmp_path: Path):
    assert model_state.default_state_path({"XDG_STATE_HOME": str(tmp_path)}) == tmp_path / "awesome" / "models.json"


def test_init_creates_the_file_from_the_template_and_creates_parent_dirs(tmp_path: Path):
    path = tmp_path / "deep" / "awesome" / "models.json"
    assert model_state.init_state(path) == "created"
    assert json.loads(path.read_text()) == model_state.load_template()
    assert not list(path.parent.glob(".models-*"))  # the atomic-write temp file is gone


def test_init_does_not_overwrite_an_existing_file(tmp_path: Path):
    path = tmp_path / "models.json"
    model_state.save(path, {**model_state.load_template(), "live": {"anthropic": _entry(timedelta(0))}})
    assert model_state.init_state(path) == "exists"
    assert "anthropic" in json.loads(path.read_text())["live"]


def test_reseed_replaces_policy_tables_but_keeps_the_live_cache(tmp_path: Path):
    path = tmp_path / "models.json"
    stale = {**model_state.load_template(), "recommended": {"anthropic": ["ancient"]}, "live": {"x": _entry(DAY)}}
    model_state.save(path, stale)
    assert model_state.init_state(path, reseed=True) == "reseeded"
    after = json.loads(path.read_text())
    assert after["recommended"] == model_state.load_template()["recommended"]
    assert after["live"] == {"x": _entry(DAY)}


def test_load_data_falls_back_to_the_template_when_there_is_no_state(tmp_path: Path):
    data, notes = model_state.load_data(tmp_path / "missing.json")
    assert data == model_state.load_template() and notes == []


def test_load_data_notes_a_state_file_older_than_the_template(tmp_path: Path):
    path = tmp_path / "models.json"
    model_state.save(path, {**model_state.load_template(), "revision": "2000-01-01"})
    _, notes = model_state.load_data(path)
    assert len(notes) == 1 and "init --reseed" in notes[0]


@pytest.mark.parametrize("body", ["{not json", "[]", '{"schema": 99}', '"text"', ""])
def test_a_corrupt_or_foreign_state_file_is_an_error_not_a_silent_fallback(tmp_path: Path, body: str):
    path = tmp_path / "models.json"
    path.write_text(body)
    with pytest.raises(ModelStateError):
        model_state.load_data(path)


def test_save_to_an_unwritable_location_is_a_clean_error(tmp_path: Path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(ModelStateError, match="cannot write"):
        model_state.save(blocker / "models.json", {})


# --- freshness -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entry", "fresh"),
    [
        (_entry(timedelta(minutes=5)), True),
        (_entry(DAY - timedelta(seconds=1)), True),
        (_entry(DAY), False),  # exactly max_age is stale
        (_entry(timedelta(days=30)), False),
        (_entry(-timedelta(hours=1)), False),  # timestamp in the future (clock skew) is not trusted
        ({"fetched_at": "yesterday", "served": ["a"]}, False),
        ({"fetched_at": model_state.format_time(NOW), "served": "oops"}, False),
        ({"served": ["a"]}, False),
        (None, False),
        ("garbage", False),
    ],
)
def test_is_fresh(entry, fresh: bool):
    assert model_state.is_fresh(entry, NOW, DAY) is fresh


# --- refresh ---------------------------------------------------------------------------------


def test_refresh_requests_a_vendor_with_no_cache_and_records_time_and_sorted_ids():
    fetch = FakeFetch(["b", "a"])
    data, report = model_state.refresh(_data(), KEY_ENVS, ["anthropic"], env={"A_KEY": "k"}, fetch=fetch, now=NOW)
    assert data["live"]["anthropic"] == {"fetched_at": "2026-10-29T12:00:00Z", "served": ["a", "b"]}
    assert report.refreshed == {"anthropic": 2} and len(fetch.urls) == 1


def test_refresh_makes_no_request_while_the_cache_is_fresh():
    fetch = FakeFetch()
    data, report = model_state.refresh(
        _data(anthropic=_entry(timedelta(hours=1))), KEY_ENVS, ["anthropic"], env={"A_KEY": "k"}, fetch=fetch, now=NOW
    )
    assert fetch.urls == [] and list(report.fresh) == ["anthropic"] and data["live"]["anthropic"]["served"] == ["old"]


def test_refresh_asks_again_once_the_cache_is_stale_and_force_ignores_freshness():
    fetch = FakeFetch(["new"])
    stale = _data(anthropic=_entry(timedelta(days=2)))
    data, _ = model_state.refresh(stale, KEY_ENVS, ["anthropic"], env={"A_KEY": "k"}, fetch=fetch, now=NOW)
    assert data["live"]["anthropic"]["served"] == ["new"]
    fresh = _data(anthropic=_entry(timedelta(minutes=1)))
    _, report = model_state.refresh(fresh, KEY_ENVS, ["anthropic"], env={"A_KEY": "k"}, fetch=fetch, now=NOW, force=True)
    assert report.refreshed == {"anthropic": 1}


def test_zero_max_age_always_asks():
    fetch = FakeFetch()
    _, report = model_state.refresh(
        _data(anthropic=_entry(timedelta(0))), KEY_ENVS, ["anthropic"], env={"A_KEY": "k"}, fetch=fetch, now=NOW,
        max_age=timedelta(0),
    )
    assert report.refreshed and len(fetch.urls) == 1


def test_a_vendor_without_a_key_is_skipped_and_never_contacted():
    fetch = FakeFetch()
    data, report = model_state.refresh(_data(), KEY_ENVS, ["openai"], env={}, fetch=fetch, now=NOW)
    assert report.no_key == ["openai"] and fetch.urls == [] and data["live"] == {}


def test_a_vendor_with_no_list_api_is_reported_not_attempted():
    fetch = FakeFetch()
    _, report = model_state.refresh(_data(), {"copilot": "C_KEY"}, ["copilot"], env={"C_KEY": "k"}, fetch=fetch, now=NOW)
    assert report.no_client == ["copilot"] and fetch.urls == []


def test_a_failed_request_keeps_the_previous_cache_and_reports_the_error():
    fetch = FakeFetch()
    fetch.fail = True
    stale = _data(anthropic=_entry(timedelta(days=2), ["kept"]))
    data, report = model_state.refresh(stale, KEY_ENVS, ["anthropic"], env={"A_KEY": "k"}, fetch=fetch, now=NOW)
    assert data["live"]["anthropic"]["served"] == ["kept"] and "HTTP 500" in report.failed["anthropic"]


def test_one_failing_vendor_does_not_stop_the_others():
    calls = []

    def fetch(url, headers):
        calls.append(url)
        if "anthropic" in url:
            raise model_catalog.ModelCatalogError("anthropic: down")
        return json.dumps({"data": [{"id": "gpt-x"}]}).encode()

    data, report = model_state.refresh(
        _data(), KEY_ENVS, ["anthropic", "openai"], env={"A_KEY": "k", "O_KEY": "k"}, fetch=fetch, now=NOW
    )
    assert list(report.failed) == ["anthropic"] and data["live"]["openai"]["served"] == ["gpt-x"]


def test_refresh_does_not_mutate_its_input():
    original = _data()
    model_state.refresh(original, KEY_ENVS, ["anthropic"], env={"A_KEY": "k"}, fetch=FakeFetch(), now=NOW)
    assert original["live"] == {}


def test_the_api_key_is_never_written_to_the_state_file(tmp_path: Path):
    path = tmp_path / "models.json"
    data, _ = model_state.refresh(_data(), KEY_ENVS, ["anthropic"], env={"A_KEY": "sk-SECRET"}, fetch=FakeFetch(), now=NOW)
    model_state.save(path, data)
    assert "sk-SECRET" not in path.read_text()


def test_served_returns_only_vendors_with_a_cached_list():
    assert model_state.served(_data(a=_entry(DAY, ["x"]), b={"fetched_at": "?"})) == {"a": frozenset({"x"})}


def test_model_state_import_does_not_pull_anthropic():
    code = "import sys; import awesome_templates.model_state; sys.exit('anthropic' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0

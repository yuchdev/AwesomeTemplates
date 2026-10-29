"""The per-user `models.json`: seeded from a packaged template, enriched with each vendor's live model list.

`model_policy` judges pins and `model_catalog` asks vendors what they serve; this module is the small
piece of persistence between them. The policy data (recommended IDs, roles, tiers, upgrade targets)
used to live in the repo's `model-policy.toml`; it now lives in a JSON file because that file also has
to carry *fetched* data - which models each vendor served and when we asked - and TOML is a poor home
for a machine-rewritten cache.

**Two files, on purpose.** `data/models.template.json` ships in the package and is the versioned source
of truth: a maintainer edits it to retire or adopt a model, and tests / the role x vendor matrix doc
read it directly so they never depend on anyone's home directory. `init` copies it once to
`~/.local/state/awesome/models.json` (or `$XDG_STATE_HOME/awesome/models.json`), where the `live`
section then accumulates. Commands that judge or rewrite read the state file, falling back to the
template when it does not exist, so nothing needs `init` to have run.

**The timestamp is the rate limiter.** Each vendor's `live` entry records `fetched_at`; a refresh younger
than `max_age` makes no request. That is the whole reason this file exists - listing models is cheap
but not free, and running it on every check would also make offline use fragile.

**Seeding is not merging.** A state file written from an older template keeps its old policy tables
until `init --reseed`, which replaces them with the template's and keeps `live`. Silently merging two
versions of a policy would hide exactly the staleness this tool exists to surface, so a lagging
`revision` is reported instead (`load_data` returns the note). Only the `live` section is ever
rewritten by a refresh, and no API key is ever stored.

Stdlib-only and offline except where a caller passes through `model_catalog`; it must never import
`anthropic`.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

from awesome_templates import model_catalog

SCHEMA = 1
TEMPLATE_PATH = Path(__file__).resolve().parent / "data" / "models.template.json"
DEFAULT_MAX_AGE = timedelta(hours=24)
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class ModelStateError(Exception):
    """The state file (or template) is unreadable, malformed, or cannot be written."""


def default_state_path(env: Optional[Mapping[str, str]] = None, home: Optional[Path] = None) -> Path:
    """`$XDG_STATE_HOME/awesome/models.json`, else `~/.local/state/awesome/models.json`."""
    env = os.environ if env is None else env
    base = env.get("XDG_STATE_HOME")
    root = Path(base) if base else (home or Path.home()) / ".local" / "state"
    return root / "awesome" / "models.json"


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ModelStateError(f"cannot read '{path}': {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ModelStateError(f"'{path}' is not a schema-{SCHEMA} models file (run `awesome-templates init --reseed`)")
    return data


def load_template(template: Path = TEMPLATE_PATH) -> dict:
    return _read(template)


def load_data(state_path: Path, template: Path = TEMPLATE_PATH) -> tuple[dict, list[str]]:
    """The effective models data: the state file if it exists, else the template.

    :returns: `(data, notes)`; `notes` says when the state file lags the template's `revision`.
    :raises ModelStateError: a state file exists but is unreadable or the wrong schema - falling back
        to the template would silently discard the user's cache and hide the problem.
    """
    seed = load_template(template)
    if not state_path.is_file():
        return seed, []
    data = _read(state_path)
    notes = []
    if str(data.get("revision", "")) < str(seed.get("revision", "")):
        notes.append(
            f"{state_path} is based on model-data revision {data.get('revision')!r}, newer is "
            f"{seed.get('revision')!r}: run `awesome-templates init --reseed`"
        )
    return data, notes


def save(path: Path, data: Mapping) -> None:
    """Atomically write `data` (temp file in the same directory, then rename), so a crash or a second
    process never leaves a half-written cache that would fail to parse."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".models-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise ModelStateError(f"cannot write '{path}': {exc}") from exc


def init_state(state_path: Path, *, reseed: bool = False, template: Path = TEMPLATE_PATH) -> str:
    """Create the state file from the template; with `reseed`, replace its policy tables but keep `live`.

    :returns: `"created"`, `"reseeded"` or `"exists"`.
    """
    seed = load_template(template)
    if not state_path.is_file():
        save(state_path, seed)
        return "created"
    if not reseed:
        return "exists"
    live = _read(state_path).get("live", {})
    save(state_path, {**seed, "live": live})
    return "reseeded"


def _parse_time(value: object) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, _TIME_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def format_time(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(_TIME_FORMAT)


def is_fresh(entry: object, now: datetime, max_age: timedelta) -> bool:
    """A `live` entry is fresh when its `fetched_at` parses, is not in the future, and is under `max_age`
    old. Anything unparseable counts as stale: re-asking is the safe direction."""
    fetched = _parse_time(entry.get("fetched_at")) if isinstance(entry, dict) else None
    return fetched is not None and timedelta(0) <= now - fetched < max_age and isinstance(entry.get("served"), list)


def served(data: Mapping) -> dict[str, frozenset[str]]:
    """Vendor -> model IDs it was last seen serving, for vendors that have a cached list."""
    live = data.get("live", {})
    return {
        vendor: frozenset(entry["served"])
        for vendor, entry in live.items()
        if isinstance(entry, dict) and isinstance(entry.get("served"), list)
    }


@dataclass
class RefreshReport:
    refreshed: dict[str, int] = field(default_factory=dict)  # vendor -> model count just fetched
    fresh: dict[str, str] = field(default_factory=dict)  # vendor -> fetched_at it was reused from
    no_key: list[str] = field(default_factory=list)  # has a list API but no key in the environment
    no_client: list[str] = field(default_factory=list)  # no list API (e.g. Copilot)
    failed: dict[str, str] = field(default_factory=dict)  # vendor -> error (never contains a key)


def refresh(
    data: Mapping,
    key_envs: Mapping[str, str],
    vendors: Iterable[str],
    *,
    env: Optional[Mapping[str, str]] = None,
    fetch: Optional[model_catalog.Fetch] = None,
    now: Optional[datetime] = None,
    max_age: timedelta = DEFAULT_MAX_AGE,
    force: bool = False,
) -> tuple[dict, RefreshReport]:
    """Refresh the `live` section for `vendors`, asking a vendor only when its cached list is stale.

    Returns a new dict (the input is not mutated) and what happened per vendor. A vendor whose request
    fails keeps its previous cached entry, so one outage never erases a good cache.

    :param fetch: HTTP boundary, resolved to `model_catalog.http_get` at call time so tests can swap it.
    """
    env = os.environ if env is None else env
    fetch = fetch or model_catalog.http_get
    now = now or datetime.now(UTC)
    updated = copy.deepcopy(dict(data))
    live = updated.setdefault("live", {})
    report = RefreshReport()
    for vendor in sorted(set(vendors)):
        if vendor not in model_catalog.FETCHERS:
            report.no_client.append(vendor)
            continue
        if not force and is_fresh(live.get(vendor), now, max_age):
            report.fresh[vendor] = live[vendor]["fetched_at"]
            continue
        key = env.get(key_envs.get(vendor, ""), "")
        if not key:
            report.no_key.append(vendor)
            continue
        try:
            ids = model_catalog.fetch_supported(vendor, key, fetch=fetch)
        except model_catalog.ModelCatalogError as exc:
            report.failed[vendor] = str(exc)
            continue
        live[vendor] = {"fetched_at": format_time(now), "served": sorted(ids)}
        report.refreshed[vendor] = len(ids)
    return updated, report

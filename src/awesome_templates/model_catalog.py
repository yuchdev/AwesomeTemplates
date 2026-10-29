"""Ask each vendor's Models API which model IDs it actually serves, and compare that to what we name.

`model_policy` answers "is this the model we *recommend*?" from a list a maintainer curates; it cannot
tell a typo'd or already-retired ID from a valid one that was simply never listed. The vendors' list
endpoints answer the other half - "does this ID exist right now?" - so a recommended or pinned ID that
the vendor does not return is a second, independent fault mode. They do not report deprecation, so a
deprecated-but-still-served model passes here; only the `recommended` list can call it outdated.

Kept apart from `model_policy` because that module is offline and runs on every `generate`, while this
one needs credentials and a network. It is reached only explicitly (`check-models --live`,
`pytest --live-models`), never from `generate`, which keeps "the offline path stays offline" and "no
implicit API use" true. Stdlib-only (`urllib`) on purpose: three trivial GETs do not justify three vendor
SDKs, and it must never import `anthropic`.

Testability at the boundary, like `headless.py`'s `run=`: every function that touches the network takes
`fetch=`, so tests supply a fake and no real request is made. A key travels only in a request header and
never appears in an error message.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Optional

from awesome_templates.model_policy import ModelPolicy, vendor_of

# (url, headers) -> response body. The default raises `ModelCatalogError` on any HTTP/network failure.
Fetch = Callable[[str, Mapping[str, str]], bytes]

ANTHROPIC_VERSION = "2023-06-01"
TIMEOUT_SECONDS = 30
PAGE_LIMIT_GUARD = 50  # a vendor that never stops paginating must not hang the run


class ModelCatalogError(Exception):
    """A vendor's list request failed or returned something unparseable. Never contains the API key."""


@dataclass(frozen=True)
class UnservedModel:
    """A recommended or pinned model ID that its vendor's Models API did not return."""

    vendor: str
    model: str


@dataclass(frozen=True)
class VerifyResult:
    unserved: list[UnservedModel]
    skipped_vendors: list[str]  # had IDs to check but no key in the environment


def http_get(url: str, headers: Mapping[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 - https only
            return response.read()
    except urllib.error.HTTPError as exc:
        raise ModelCatalogError(f"{urllib.parse.urlsplit(url).netloc}: HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ModelCatalogError(f"{urllib.parse.urlsplit(url).netloc}: request failed ({exc})") from None


def _get_json(url: str, headers: Mapping[str, str], fetch: Fetch) -> dict:
    body = fetch(url, headers)
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        raise ModelCatalogError(f"{urllib.parse.urlsplit(url).netloc}: response was not JSON") from None
    if not isinstance(payload, dict):
        raise ModelCatalogError(f"{urllib.parse.urlsplit(url).netloc}: unexpected response shape")
    return payload


def _ids(items: object, field_name: str, vendor: str) -> list[str]:
    if not isinstance(items, list) or not all(
        isinstance(i, dict) and isinstance(i.get(field_name), str) for i in items
    ):
        raise ModelCatalogError(f"{vendor}: model list has an unexpected shape")
    return [i[field_name] for i in items]


def _anthropic(api_key: str, fetch: Fetch) -> frozenset[str]:
    headers = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}
    found: set[str] = set()
    after: Optional[str] = None
    for _ in range(PAGE_LIMIT_GUARD):
        query = {"limit": "1000", **({"after_id": after} if after else {})}
        page = _get_json(f"https://api.anthropic.com/v1/models?{urllib.parse.urlencode(query)}", headers, fetch)
        found.update(_ids(page.get("data"), "id", "anthropic"))
        after = page.get("last_id")
        if not page.get("has_more") or not isinstance(after, str):
            return frozenset(found)
    raise ModelCatalogError("anthropic: pagination did not terminate")


def _openai(api_key: str, fetch: Fetch) -> frozenset[str]:
    page = _get_json("https://api.openai.com/v1/models", {"Authorization": f"Bearer {api_key}"}, fetch)
    return frozenset(_ids(page.get("data"), "id", "openai"))


def _google(api_key: str, fetch: Fetch) -> frozenset[str]:
    headers = {"x-goog-api-key": api_key}  # header, not ?key=, so the key stays out of URLs and logs
    found: set[str] = set()
    token: Optional[str] = None
    for _ in range(PAGE_LIMIT_GUARD):
        query = {"pageSize": "1000", **({"pageToken": token} if token else {})}
        page = _get_json(
            f"https://generativelanguage.googleapis.com/v1beta/models?{urllib.parse.urlencode(query)}", headers, fetch
        )
        names = _ids(page.get("models"), "name", "google")
        found.update(n.removeprefix("models/") for n in names)  # the API returns "models/gemini-..."
        token = page.get("nextPageToken")
        if not isinstance(token, str) or not token:
            return frozenset(found)
    raise ModelCatalogError("google: pagination did not terminate")


FETCHERS: Mapping[str, Callable[[str, Fetch], frozenset[str]]] = {
    "anthropic": _anthropic,
    "openai": _openai,
    "google": _google,
}


def fetch_supported(vendor: str, api_key: str, *, fetch: Fetch = http_get) -> frozenset[str]:
    """Every model ID `vendor` currently serves to this key.

    :raises ModelCatalogError: unknown vendor, HTTP/network failure, or an unparseable response.
    """
    try:
        fetcher = FETCHERS[vendor]
    except KeyError:
        raise ModelCatalogError(f"no Models API client for vendor '{vendor}' (known: {', '.join(FETCHERS)})") from None
    return fetcher(api_key, fetch)


def ids_to_verify(policy: ModelPolicy, pinned: Sequence[str]) -> dict[str, set[str]]:
    """`recommended` plus every pinned ID, grouped by vendor. A pin whose vendor cannot be told is
    returned under `"?"` so the caller can report it rather than silently skip it."""
    grouped: dict[str, set[str]] = {v: set(ids) for v, ids in policy.recommended.items() if ids}
    for model in pinned:
        grouped.setdefault(vendor_of(model, policy) or "?", set()).add(model)
    return grouped


def verify(
    policy: ModelPolicy,
    pinned: Sequence[str],
    *,
    env: Optional[Mapping[str, str]] = None,
    fetch: Fetch = http_get,
    cache: Optional[Mapping[str, frozenset[str]]] = None,
) -> VerifyResult:
    """Compare `recommended ∪ pinned` to what each vendor serves.

    A vendor listed in `cache` (the persisted `models.json` lists, see `model_state`) is judged from it
    with no key and no request. Otherwise a vendor with IDs to check but no key in `env` lands in
    `skipped_vendors` (the caller decides whether that is a skip or a failure); a vendor with no IDs is
    never contacted.

    :raises ModelCatalogError: a vendor request failed, or a pin matches no known vendor.
    """
    env = os.environ if env is None else env
    grouped = ids_to_verify(policy, pinned)
    if "?" in grouped:
        raise ModelCatalogError(f"cannot tell which vendor serves: {', '.join(sorted(grouped['?']))}")
    unserved: list[UnservedModel] = []
    skipped: list[str] = []
    for vendor in sorted(grouped):
        if cache is not None and vendor in cache:
            supported = cache[vendor]
        else:
            key = env.get(policy.key_envs.get(vendor, ""), "")
            if vendor not in FETCHERS or not key:  # harness-native vendors (copilot...) have no list API
                skipped.append(vendor)
                continue
            supported = fetch_supported(vendor, key, fetch=fetch)
        unserved.extend(UnservedModel(vendor, m) for m in sorted(grouped[vendor] - supported))
    return VerifyResult(unserved, skipped)


def format_unserved(item: UnservedModel) -> str:
    return f"{item.vendor} does not list model '{item.model}' (typo, retired, or not available to this key)"

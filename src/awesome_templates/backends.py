"""Direct-API backends for `generate --backend` - the non-agentic half of the
AI-engine choice whose agentic half `harnesses.py` owns.

Why this is a separate module from `harnesses.py` rather than more rows in its
registry: a *harness* is a third-party CLI installed on this machine that we
shell out to - it has a binary name to discover on `PATH`, an argv recipe, its
own authentication, and it runs an agentic loop that reads and edits files
itself. A *backend* is an HTTP API this package calls directly - no subprocess,
no binary, no agentic loop, and a metered per-token bill. They answer the same
question ("which model runs the AI stage?") through entirely different
machinery, which is precisely why `cli.sanity_check` treats `--harness` and
`--backend` as mutually exclusive. Keeping the registries apart means neither
grows fields that are meaningless for the other (`binary_names` for an API,
`api_key_env` for a CLI).

Every backend registered here is **declared but not implemented**. That is the
point of the module, not a gap in it: the direct-API path exists so that
spending metered API credit can only ever be a deliberate, explicit request
(`--backend anthropic-api`), never an implicit fallback taken because a harness
CLI happened to be missing from `PATH` or because `ANTHROPIC_API_KEY` happened
to be exported in the ambient shell. `cli.sanity_check` turns any selection
whose `implemented` flag is `False` into a "not implemented yet" exit before a
single request is placed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

BACKEND_NAMES = ("anthropic-api", "openai-api", "jetbrains-api")


@dataclass(frozen=True)
class Backend:
    """One direct-API backend's identity.

    :ivar name: the `--backend` value this registration answers to.
    :ivar vendor: human-readable vendor name, used in CLI messages.
    :ivar mirrors_harness: the `harnesses.HARNESS_NAMES` entry that reaches the
        same vendor's models through an installed CLI instead. This is what
        lets an error message about a missing harness binary name the *correct*
        API alternative rather than a generic one.
    :ivar api_key_env: the environment variable this backend would authenticate
        with. Recorded here for the eventual implementation and for error
        messages; **nothing in this package reads it implicitly** - see the
        module docstring.
    :ivar implemented: whether `generate` can actually run this backend today.
        `False` for every entry at present; `cli.sanity_check` converts a
        selection with `False` into a "not implemented yet" exit.
    """

    name: str
    vendor: str
    mirrors_harness: str
    api_key_env: str
    implemented: bool = False


_REGISTRY: dict[str, Backend] = {
    "anthropic-api": Backend(
        name="anthropic-api",
        vendor="Anthropic",
        mirrors_harness="claude",
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "openai-api": Backend(
        name="openai-api",
        vendor="OpenAI",
        mirrors_harness="copilot",
        api_key_env="OPENAI_API_KEY",
    ),
    "jetbrains-api": Backend(
        name="jetbrains-api",
        vendor="JetBrains",
        mirrors_harness="junie",
        api_key_env="JETBRAINS_API_KEY",
    ),
}


def get(name: str) -> Backend:
    """Look up a backend by its `--backend` value.

    :param name: one of `BACKEND_NAMES`.
    :return: the registered :class:`Backend`.
    :raises KeyError: if `name` is not registered - `cli.sanity_check` rejects
        unknown names with its own `_fail(...)` message before ever calling
        this, the same way it does for an unknown harness.
    """
    return _REGISTRY[name]


def mirror_of(harness_name: str) -> Optional[str]:
    """The `--backend` value that reaches the same vendor as `harness_name`.

    Used by `cli.py` to point a user whose harness CLI is missing at the
    explicit API alternative by name, instead of silently taking it for them.

    :param harness_name: a `harnesses.HARNESS_NAMES` entry.
    :return: the mirroring `--backend` value, or `None` if no backend mirrors
        that harness.
    """
    for backend in _REGISTRY.values():
        if backend.mirrors_harness == harness_name:
            return backend.name
    return None

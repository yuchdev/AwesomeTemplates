"""Thin wrapper around the Anthropic Messages API.

This is the only module in `awesome_templates` allowed to import `anthropic`,
and it does so lazily, inside functions, so a plain `awesome_templates generate`
(no `--resolve-markers`) never pays for or requires the `ai` extra. It knows
nothing about markers, prose, or confidence - resolver.py owns what to ask
and what to do with the answer; this module only knows how to place one
request and hand back parsed JSON.
"""

from __future__ import annotations

import json
import os
from typing import Any


def build_client(api_key: str) -> Any:
    """Construct an `anthropic.Anthropic` client, seeding the env var it reads."""
    import anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
    return anthropic.Anthropic()


def error_classes() -> tuple[tuple[type[BaseException], ...], tuple[type[BaseException], ...]]:
    """(auth_errors, api_errors) for a caller to except on, without importing
    `anthropic` itself. Falls back to a catch-all pair when the `ai` extra
    isn't installed, so callers driving a fake client (as tests do) still
    have something to except on."""
    try:
        import anthropic

        return (anthropic.AuthenticationError,), (anthropic.APIError,)
    except ModuleNotFoundError:
        return (), (Exception,)


def request_json(
    client: Any,
    *,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int = 8000,
) -> dict[str, Any]:
    """One streamed Messages API call with structured JSON output.

    Streamed (a large adaptive-thinking response would otherwise risk an HTTP
    timeout); the system prompt is marked ephemeral-cacheable since callers
    that issue many requests in a row (one per marker) reuse it verbatim.
    No temperature/top_p - both are rejected on claude-opus-4-8.
    """
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": schema},
        },
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    ) as stream:
        message = stream.get_final_message()
    text = next(block.text for block in message.content if block.type == "text")
    return json.loads(text)

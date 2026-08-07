"""Resolve `<!-- TEMPLATE-INIT: ... -->` markers by asking Anthropic to write
project-grounded prose - the network half of the AI-resolution feature.

This is the programmatic sibling of `.claude/agents/create-from-template.md`:
the agent does an interactive, agents-only pass inside Claude Code; this module
does an all-Markdown pass from `generate --resolve-markers`, calling the
Messages API once per marker with a curated bundle of the target project's own
context.

`anthropic` is imported lazily, inside functions only - so a plain
`awesome-claude generate` (no flag) never imports it and the offline path has
no dependency on the `ai` extra. markers.py does the pure scan/splice; this
module decides what each marker should say.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from awesome_claude.markers import Marker, apply_replacements, scan_tree

MODEL = "claude-opus-4-8"

# Manifests that identify what kind of project the target is, most-specific
# first. Only the first that exists is included in the context bundle.
_MANIFESTS = ("pyproject.toml", "pom.xml", "build.gradle.kts", "build.gradle", "package.json")

_SYSTEM = """\
You are the Template Initializer for a generated Claude Code kit. Each request
gives you one TEMPLATE-INIT instruction from a generated Markdown file plus the
prose surrounding it, and a bundle describing the target project the kit was
generated into.

Write concise prose that answers the instruction, grounded ONLY in the project
bundle below - never invent architecture, domain terms, or risk categories that
aren't evidenced there. Match the voice and format of the surrounding prose. If
the marker is inline in a sentence, return a fragment that reads naturally where
the comment sat; if it stands alone, you may return one or more sentences or a
short list.

Return prose only: no `<!-- ... -->` comment syntax and no `{{PLACEHOLDER}}`
tokens. If the bundle genuinely lacks the signal to answer confidently (e.g. a
skeletal project with no real code yet), set confident=false and put your best
partial guidance in prose - do not fabricate specifics to sound confident.
"""

_USER_TEMPLATE = """\
The marker is {placement}.

Instruction: {instruction}

Prose immediately before the marker:
---
{before}
---

Prose immediately after the marker:
---
{after}
---
"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "confident": {"type": "boolean"},
        "prose": {"type": "string"},
    },
    "required": ["confident", "prose"],
    "additionalProperties": False,
}


@dataclass
class ResolvedMarker:
    marker: Marker
    prose: str
    confident: bool


@dataclass
class ResolveSummary:
    resolved: int = 0
    todos: int = 0
    files_touched: int = 0
    failed: int = 0


def parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal `.env` parser: `KEY=value` and `export KEY=value`, `#` comments,
    surrounding quotes stripped. Deliberately not python-dotenv - the feature
    needs one variable, not a dependency."""
    env: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return env
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            env[key] = value
    return env


def load_api_key(cwd: Path) -> str | None:
    """ANTHROPIC_API_KEY from the environment, else from a `.env` in cwd."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    return parse_dotenv(cwd / ".env").get("ANTHROPIC_API_KEY") or None


def _read_head(path: Path, limit: int) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except (OSError, UnicodeDecodeError):
        return ""


def gather_context(target: Path, *, char_budget: int = 40_000) -> str:
    """Build a one-shot context bundle describing the target project: its intent
    docs, dependency manifest, source-tree shape, and design docs. Each section
    is labelled and truncated so the whole bundle stays within char_budget."""
    sections: list[str] = []

    for name in ("README.md", "CLAUDE.md", "AGENTS.md"):
        body = _read_head(target / name, 6_000)
        if body.strip():
            sections.append(f"## {name}\n{body}")

    for name in _MANIFESTS:
        manifest = target / name
        if manifest.is_file():
            body = _read_head(manifest, 6_000)
            if body.strip():
                sections.append(f"## {name}\n{body}")
            break

    tree: list[str] = []
    for sub in ("src", "tests", "app", "lib"):
        base = target / sub
        if base.is_dir():
            tree.extend(
                str(p.relative_to(target).as_posix())
                for p in sorted(base.rglob("*"))
                if p.is_file()
            )
    if tree:
        listing = "\n".join(tree[:300])
        if len(tree) > 300:
            listing += f"\n... (+{len(tree) - 300} more files)"
        sections.append(f"## Source tree\n{listing}")

    for label, pattern in (("ADRs", "docs/adr/*.md"), ("Specs", "docs/specs/*.md")):
        docs = sorted(target.glob(pattern))
        chunks = [f"### {d.relative_to(target).as_posix()}\n{_read_head(d, 2_000)}" for d in docs]
        chunks = [c for c in chunks if c.strip()]
        if chunks:
            sections.append(f"## {label}\n" + "\n\n".join(chunks))

    bundle = "\n\n".join(sections)
    if len(bundle) > char_budget:
        bundle = bundle[:char_budget] + "\n... (context truncated)"
    return bundle or "(the target project has no README, manifest, or source tree yet)"


def resolve_one(client, marker: Marker, context_bundle: str, *, model: str = MODEL) -> ResolvedMarker:
    """One Messages API call for one marker, returning parsed confidence+prose.

    Streamed (large adaptive-thinking outputs would otherwise risk an HTTP
    timeout) with structured output so the confidence signal is first-class. No
    temperature/top_p - both are rejected on claude-opus-4-8."""
    placement = "inline within a sentence" if marker.inline else "on its own line"
    user = _USER_TEMPLATE.format(
        placement=placement,
        instruction=marker.instruction,
        before=marker.before or "(start of file)",
        after=marker.after or "(end of file)",
    )
    with client.messages.stream(
        model=model,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": _SCHEMA},
        },
        system=[
            {
                "type": "text",
                "text": _SYSTEM + "\n\n# Target project context\n\n" + context_bundle,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user}],
    ) as stream:
        message = stream.get_final_message()
    text = next(b.text for b in message.content if b.type == "text")
    data = json.loads(text)
    return ResolvedMarker(
        marker=marker,
        prose=str(data["prose"]).strip(),
        confident=bool(data["confident"]),
    )


def render(resolved: ResolvedMarker) -> str:
    """Turn a resolved marker into the exact text that replaces the comment,
    honouring inline vs block placement and the low-confidence TODO fallback."""
    marker = resolved.marker
    prose = resolved.prose

    if not resolved.confident:
        head = f"{marker.indent}> **TODO (fill in): {marker.instruction}**"
        body_lines = [f"{marker.indent}> {line}" for line in prose.splitlines() if line.strip()]
        return head + ("\n" + "\n".join(body_lines) if body_lines else "")

    if marker.inline:
        # Stay on one line so the surrounding sentence isn't broken.
        return re.sub(r"\s+", " ", prose).strip()

    bullet = marker.bullet or ""
    lines = prose.splitlines() or [""]
    out = [f"{marker.indent}{bullet}{lines[0]}"]
    for line in lines[1:]:
        out.append(f"{marker.indent}{line}" if line.strip() else "")
    return "\n".join(out)


def _build_client(api_key: str):
    import anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
    return anthropic.Anthropic()


def resolve_tree(
    out_dir: Path,
    *,
    api_key: str,
    warnings: list[str],
    make_client=None,
) -> ResolveSummary:
    """Resolve every marker in a generated tree in place.

    Idempotent: a tree with no markers returns a zeroed summary and writes
    nothing. Per-marker API errors are soft (leave the marker, warn, continue);
    an auth error aborts the loop with a single clear warning - in both cases
    the already-valid offline tree is preserved and the caller keeps exit 0.
    make_client lets tests inject a fake client with no network."""
    summary = ResolveSummary()
    markers = scan_tree(out_dir)
    if not markers:
        return summary

    try:
        import anthropic

        auth_errors: tuple[type[BaseException], ...] = (anthropic.AuthenticationError,)
        api_errors: tuple[type[BaseException], ...] = (anthropic.APIError,)
    except ModuleNotFoundError:
        auth_errors = ()
        api_errors = (Exception,)

    context_bundle = gather_context(out_dir)
    client = make_client() if make_client is not None else _build_client(api_key)

    by_file: dict[Path, list[Marker]] = {}
    for marker in markers:
        by_file.setdefault(marker.path, []).append(marker)

    aborted = False
    for path, file_markers in by_file.items():
        if aborted:
            break
        repls: list[tuple[Marker, str]] = []
        for marker in file_markers:
            try:
                resolved = resolve_one(client, marker, context_bundle)
            except auth_errors as exc:  # abort the whole run
                warnings.append(
                    f"marker resolution aborted (authentication error: {exc}) - "
                    "check ANTHROPIC_API_KEY and re-run --resolve-markers"
                )
                summary.failed += 1
                aborted = True
                break
            except api_errors as exc:  # soft: leave this marker, keep going
                warnings.append(f"could not resolve a marker in {path.name} ({exc}) - left in place")
                summary.failed += 1
                continue
            except Exception as exc:  # bad/unexpected response - soft too
                warnings.append(f"could not resolve a marker in {path.name} ({exc}) - left in place")
                summary.failed += 1
                continue

            repls.append((marker, render(resolved)))
            if resolved.confident:
                summary.resolved += 1
            else:
                summary.todos += 1
                warnings.append(
                    f"low confidence for a marker in {path.name} - left a TODO: {marker.instruction}"
                )

        if repls:
            text = path.read_text(encoding="utf-8")
            path.write_text(apply_replacements(text, repls), encoding="utf-8")
            summary.files_touched += 1

    return summary

"""Discovery of the opt-in specialization layer: agent/skill add-ons nested
under templates/<preset>/specializations/<name>/, selected at `generate` time
via --specialization. See catalog.py's docstring for why a *preset* has
nothing to select or compose - this is a deliberately separate, optional
layer beside it, not an exception to that rule.

A specialization directory is shaped exactly like the "preset directory with
kind dirs nested one level under .claude/" case catalog.discover already
documents and handles (templates/<preset>/specializations/<name>/.claude/
{agents,skills}/), so this module adds no new discovery logic - only a new
place to point catalog.discover at, plus the domain rule specific to this
layer: only agents/ and skills/ are allowed. A hook is inert until something
wires it in settings.json, and settings.json is owned by the core preset (see
root CLAUDE.md's "already trimmed to reference only hooks that exist"), so a
specialization shipping a hook or loop with no wiring path would recreate the
dead-file bug class root CLAUDE.md documents as having shipped before.
"""

from __future__ import annotations

from pathlib import Path

from awesome_templates.catalog import KINDS, discover
from awesome_templates.workspace import Workspace

# Kinds a specialization is allowed to ship.
ALLOWED_KINDS = ("agents", "skills")


def specialization_root(workspace: Workspace, preset: str, name: str) -> Path:
    """The templates/<preset>/specializations/<name>/ directory - the
    specialization's own root, one level above its .claude/."""
    return workspace.path(preset) / "specializations" / name


def list_specializations(workspace: Workspace, preset: str) -> list[str]:
    """Every immediate child of templates/<preset>/specializations/ that has
    a .claude/ with at least one agent or skill. Empty (not an error) when
    the preset has no specializations/ directory at all, or when a child
    directory exists but carries no usable entity - both are treated as "not
    a real specialization" rather than surfaced as a discovery error, since
    an empty scaffold directory is not a user-facing failure."""
    base = workspace.path(preset) / "specializations"
    if not base.is_dir():
        return []
    names = []
    for child in sorted(p.name for p in base.iterdir() if p.is_dir()):
        catalog = discover(Workspace(root=base / child))
        entries = catalog.entries.get(".", {})
        if any(entries.get(kind) for kind in ALLOWED_KINDS):
            names.append(child)
    return names


def disallowed_kinds_present(workspace: Workspace, preset: str, name: str) -> list[str]:
    """Kinds this specialization ships that it isn't allowed to (hooks/,
    loops/, or its own settings.json) - empty when the specialization is
    clean. Used both by a repo-hygiene test over the real templates/ tree and
    as a courtesy check an author can run against a new specialization."""
    claude_dir = specialization_root(workspace, preset, name) / ".claude"
    found = [
        kind
        for kind in KINDS
        if kind not in ALLOWED_KINDS
        and (claude_dir / kind).is_dir()
        and any((claude_dir / kind).iterdir())
    ]
    if (claude_dir / "settings.json").exists():
        found.append("settings.json")
    return found

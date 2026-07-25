"""Resolving a preset/category/include-exclude request into a concrete Selection."""

from __future__ import annotations

from dataclasses import dataclass, field

from awesome_claude.catalog import CATEGORIES, KINDS, Catalog

KIND_ALIAS = {"agent": "agents", "hook": "hooks", "loop": "loops", "skill": "skills"}


class SelectionError(Exception):
    """Invalid category/entity selection input - the CLI surfaces this as an error message."""


@dataclass
class Selection:
    entries: dict[str, dict[str, set]] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> Selection:
        return cls(entries={cat: {kind: set() for kind in KINDS} for cat in CATEGORIES})

    def is_empty(self) -> bool:
        return not any(names for kinds in self.entries.values() for names in kinds.values())

    def add_category(self, catalog: Catalog, category: str) -> None:
        if category not in CATEGORIES:
            raise SelectionError(
                f"unknown category '{category}' (choices: {', '.join(CATEGORIES)})"
            )
        for kind in KINDS:
            if category in catalog.entries:
                self.entries[category][kind] |= set(catalog.entries[category][kind])

    @staticmethod
    def find_by_name(catalog: Catalog, kind: str, name: str) -> list[tuple[str, str]]:
        return [
            (cat, name)
            for cat in CATEGORIES
            if cat in catalog.entries and name in catalog.entries[cat][kind]
        ]

    def apply_tokens(self, catalog: Catalog, tokens: list[str], adding: bool) -> None:
        # token shape: "type:name" or "type:category/name" (the qualified form is
        # needed for the handful of names - currently just the shared _common.py
        # hook - that deliberately exist under more than one category).
        verb = "include" if adding else "exclude"
        for token in tokens:
            if ":" not in token:
                raise SelectionError(
                    f"--{verb} expects 'type:name' (e.g. agent:app-architect), got '{token}'"
                )
            type_, name = token.split(":", 1)
            kind = KIND_ALIAS.get(type_)
            if kind is None:
                raise SelectionError(
                    f"unknown --{verb} type '{type_}' (choices: agent, hook, loop, skill)"
                )

            cat: str | None
            if "/" in name:
                cat, name = name.split("/", 1)
                if cat not in CATEGORIES:
                    raise SelectionError(f"unknown category '{cat}' in --{verb} '{token}'")
                if name not in catalog.entries[cat][kind]:
                    raise SelectionError(f"no {type_} named '{name}' found in category '{cat}'")
            else:
                hits = self.find_by_name(catalog, kind, name)
                if not hits:
                    raise SelectionError(f"no {type_} named '{name}' found in any category")
                if len(hits) > 1:
                    qualified = ", ".join(f"{type_}:{c}/{name}" for c, _ in hits)
                    raise SelectionError(
                        f"'{name}' exists in more than one category - this is deliberate "
                        f"(e.g. the shared _common.py hook is duplicated per category so each "
                        f"category stays self-contained). Disambiguate with one of: {qualified}"
                    )
                cat, _ = hits[0]

            if adding:
                self.entries[cat][kind].add(name)
            else:
                self.entries[cat][kind].discard(name)

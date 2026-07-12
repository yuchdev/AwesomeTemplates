"""Dynamic settings.json assembly: drop hook wiring / permissions the selection doesn't include."""

from __future__ import annotations

import json
import re

from awesome_claude.selection import Selection
from awesome_claude.templating import apply_subs
from awesome_claude.workspace import Workspace

HOOK_CMD_RE = re.compile(r"hooks/([\w.\-]+)\.py")
PYTHON_TOOLING_RE = re.compile(r"pytest|ruff|uv run", re.I)


def build_settings(
    workspace: Workspace, selection: Selection, subs: dict[str, str], warnings: list[str]
) -> dict | None:
    src = workspace.path("core", "settings.json")
    if not src.exists():
        return None
    data = json.loads(apply_subs(src.read_text(encoding="utf-8"), subs))

    present_hooks = {
        name for kinds in selection.entries.values() for name in kinds.get("hooks", ())
    }

    for event, groups in list(data.get("hooks", {}).items()):
        kept_groups = []
        for group in groups:
            kept_hooks = []
            for h in group.get("hooks", []):
                m = HOOK_CMD_RE.search(h.get("command", ""))
                name = m.group(1) if m else None
                if name is None or name in present_hooks:
                    kept_hooks.append(h)
                else:
                    warnings.append(
                        f"settings.json: dropped '{event}' wiring for hook '{name}' "
                        "(not in selected output)"
                    )
            if kept_hooks:
                kept_groups.append({**group, "hooks": kept_hooks})
        if kept_groups:
            data["hooks"][event] = kept_groups
        else:
            del data["hooks"][event]

    if not any(selection.entries["python"].values()):
        before = data["permissions"]["allow"]
        data["permissions"]["allow"] = [p for p in before if not PYTHON_TOOLING_RE.search(p)]
        for dropped in set(before) - set(data["permissions"]["allow"]):
            warnings.append(
                f"settings.json: dropped Python-tooling permission '{dropped}' "
                "(python category not selected)"
            )

    return data

"""Bump outdated model pins in an *existing* project's agentic pipeline, one vendor at a time.

`generate` creates a project and then never touches it again, so a project generated last year keeps
pinning last year's models. This module finds the model pins an existing project carries
(Claude `.claude/agents`, Copilot `.github/agents`, Junie `.junie/agents`, Codex `.codex/config.toml`),
judges each against *its own vendor's* recommended list, and plans a rewrite to that vendor's target.
It is the project-side sibling of `model_policy` (which audits this repo's templates) and reads the
same `model-policy.toml` data, so there is still exactly one place that names models.

**The matcher is deliberately not a table of old -> new pairs.** Such a table grows with every release
and with every vendor. Instead each pin goes through independent facts - which vendor owns it (the
harness it was found in), is it in that vendor's `recommended` list, and what does
`ModelPolicy.upgrade_target` say for this *agent role* on this vendor - so the cost is a few dict
lookups per pin, whatever the number of past versions. The role is the agent file's stem: a
`cpp-expert` moves to a vendor's flagship tier while a `docs-updater` moves to its cheaper one, because
upgrading every agent to the most expensive model would be wrong. A pin whose role is unknown (a user's
own agent, Codex's single config) falls back to the old model's family, then the vendor default. A model
released tomorrow needs no edit to be upgraded *from*; only a tier's model moves when a vendor ships a
successor.

**Only Claude's pin location is verified.** The Copilot/Junie/Codex adapters encode the locations
`harnesses.py` documents, but their `model` field has not been confirmed against the real tools, so
auto-detection skips them with a message and they run only when named explicitly with `--harness`.
Guessing a file format and writing to a user's project is worse than doing nothing.

**Edits are single-line, in place.** A rewrite replaces only the model value on the one matched line,
preserving quotes, trailing comments and line endings; nothing is parsed and re-dumped, so unrelated
content cannot be reformatted. Stdlib-only and offline; it must never import `anthropic`.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from awesome_templates.log_helper import NULL_LOG, LogHelper
from awesome_templates.model_policy import FLOATING_ALIASES, ModelPolicy

# `model: value` inside a markdown frontmatter block; group 1 = prefix, 2 = quote, 3 = value, 5 = tail.
_FRONTMATTER_MODEL_RE = re.compile(r"^(\s*model\s*:\s*)([\"']?)([^\"'#\r\n]*?)(\2)(\s*(?:#.*)?)$")
# `model = "value"` in TOML; only quoted strings are rewritten.
_TOML_MODEL_RE = re.compile(r"^(\s*model\s*=\s*)([\"'])(.*?)(\2)(\s*(?:#.*)?)$")


@dataclass(frozen=True)
class HarnessSite:
    """Where one harness keeps model pins: what marks it as present and which files to scan.

    :ivar vendor: key into `ModelPolicy.recommended` / `.upgrade` that judges this harness's pins.
    :ivar verified: whether the pin location was confirmed against the real tool (see module docstring).
    """

    name: str
    vendor: str
    markers: tuple[str, ...]
    globs: tuple[str, ...]
    style: str  # "frontmatter" | "toml"
    verified: bool


SITES: dict[str, HarnessSite] = {
    s.name: s
    for s in (
        HarnessSite("claude", "anthropic", (".claude",), (".claude/agents/*.md",), "frontmatter", True),
        HarnessSite("copilot", "copilot", (".github/agents",), (".github/agents/*.md",), "frontmatter", False),
        HarnessSite("junie", "junie", (".junie",), (".junie/agents/*.md",), "frontmatter", False),
        HarnessSite("codex", "codex", (".codex",), (".codex/config.toml",), "toml", False),
    )
}


@dataclass(frozen=True)
class PinSite:
    harness: str
    path: Path
    line: int  # 1-based
    model: str
    role: Optional[str] = None  # agent file stem; None where the file is not one agent (TOML config)


@dataclass(frozen=True)
class Change:
    site: PinSite
    new_model: str


@dataclass
class UpgradePlan:
    changes: list[Change] = field(default_factory=list)
    unresolved: list[PinSite] = field(default_factory=list)  # outdated, but no target configured
    current: int = 0  # pins already fine
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (harness, reason)


def validate_harness_names(names: Sequence[str]) -> None:
    unknown = sorted(set(names) - set(SITES))
    if unknown:
        raise ValueError(f"unknown harness {', '.join(unknown)} (known: {', '.join(SITES)})")


def _files(root: Path, site: HarnessSite) -> list[Path]:
    return sorted({p for pattern in site.globs for p in root.glob(pattern) if p.is_file()})


def find_pins(root: Path, site: HarnessSite) -> list[PinSite]:
    """Every `model` pin the site's files carry (frontmatter block only for markdown; any `model =`
    string for TOML)."""
    pins = []
    for path in _files(root, site):
        lines = path.read_text(encoding="utf-8").splitlines()
        in_block = site.style == "toml"
        pattern = _TOML_MODEL_RE if site.style == "toml" else _FRONTMATTER_MODEL_RE
        for number, raw in enumerate(lines, start=1):
            if site.style == "frontmatter":
                if number == 1:
                    if raw.strip() != "---":
                        break
                    in_block = True
                    continue
                if raw.strip() == "---":
                    break
            match = pattern.match(raw) if in_block else None
            if match and match.group(3).strip():
                role = path.stem if site.style == "frontmatter" else None
                pins.append(PinSite(site.name, path, number, match.group(3).strip(), role))
    return pins


def detect(root: Path, site: HarnessSite) -> bool:
    return any((root / marker).exists() for marker in site.markers)


def plan_upgrade(
    root: Path,
    policy: ModelPolicy,
    harness_names: Optional[Sequence[str]] = None,
    *,
    warnings: Optional[list[str]] = None,
    log: LogHelper = NULL_LOG,
) -> UpgradePlan:
    """Decide, without writing, which pins under `root` should change and to what.

    With no `harness_names`, every *verified* harness found in the project is scanned and detected
    unverified ones are reported as skipped. Naming a harness explicitly scans it even if unverified
    (the caller asked), and reports it as skipped only when it is absent from the project.
    """
    warnings = [] if warnings is None else warnings
    plan = UpgradePlan()
    explicit = harness_names is not None
    for name in harness_names if harness_names is not None else SITES:
        site = SITES[name]
        if not detect(root, site):
            if explicit:
                plan.skipped.append((name, "not found in this project"))
            continue
        if not explicit and not site.verified:
            plan.skipped.append(
                (name, "detected, but its model location is not verified - name it with --harness to try")
            )
            continue
        recommended = policy.recommended.get(site.vendor, frozenset())
        for pin in find_pins(root, site):
            if pin.model in FLOATING_ALIASES or pin.model in recommended:
                plan.current += 1
                continue
            if not recommended:
                message = (
                    f"{site.name}: no recommended models configured for '{site.vendor}' - cannot judge {pin.model}"
                )
                warnings.append(message)
                log.warning(message)
                continue
            target = policy.upgrade_target(site.vendor, pin.model, pin.role)
            if target is None or target == pin.model:
                plan.unresolved.append(pin)
            else:
                plan.changes.append(Change(pin, target))
    return plan


def apply_changes(changes: Sequence[Change], *, warnings: Optional[list[str]] = None) -> int:
    """Rewrite each matched line in place; returns how many lines changed.

    The line is re-matched and its current value compared to the planned one before writing, so a file
    edited between `plan_upgrade` and now is left alone (and reported) rather than overwritten blindly.
    """
    warnings = [] if warnings is None else warnings
    written = 0
    by_path: dict[Path, list[Change]] = {}
    for change in changes:
        by_path.setdefault(change.site.path, []).append(change)
    for path, file_changes in by_path.items():
        lines = path.read_bytes().decode("utf-8").splitlines(keepends=True)
        for change in file_changes:
            site = SITES[change.site.harness]
            pattern = _TOML_MODEL_RE if site.style == "toml" else _FRONTMATTER_MODEL_RE
            raw = lines[change.site.line - 1]
            body = raw.rstrip("\r\n")
            match = pattern.match(body)
            if not match or match.group(3).strip() != change.site.model:
                warnings.append(f"{path}:{change.site.line} changed since planning - left alone")
                continue
            lines[change.site.line - 1] = (
                body[: match.start(3)] + change.new_model + body[match.end(3) :] + raw[len(body) :]
            )
            written += 1
        path.write_bytes("".join(lines).encode("utf-8"))
    return written


def dirty_files(
    root: Path, paths: Sequence[Path], *, run: Callable[..., subprocess.CompletedProcess] = subprocess.run
) -> list[Path]:
    """Return requested paths with uncommitted changes in `root`'s git repo.

    Uses paths relative to the `git -C root` working directory and NUL-delimited status bytes, so
    rename/copy paths and unusual filename bytes are handled exactly. Not a repo (or git absent)
    returns `[]`: there is no history to protect, so the check cannot refuse.

    :param root: Project directory whose Git worktree to inspect.
    :param paths: Candidate paths, absolute or relative to the current working directory.
    :param run: Subprocess runner, injectable so tests need no real Git.
    :returns: The requested paths that Git reports as dirty.
    """
    if not paths:
        return []
    pathspecs = [os.path.relpath(path, root) for path in paths]
    try:
        result = run(
            [
                "git",
                "-C",
                str(root),
                "--literal-pathspecs",
                "status",
                "--porcelain",
                "-z",
                "--",
                *pathspecs,
            ],
            capture_output=True,
            check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    entries = result.stdout.split(b"\0")
    dirty_names: set[bytes] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4:
            continue
        dirty_names.add(entry[3:])
        if (b"R" in entry[:2] or b"C" in entry[:2]) and index < len(entries):
            dirty_names.add(entries[index])
            index += 1
    requested_names = {os.fsencode(pathspec) for pathspec in pathspecs}
    matched_names = dirty_names & requested_names
    return [
        path
        for path, pathspec in zip(paths, pathspecs, strict=True)
        if os.fsencode(pathspec) in matched_names
    ]

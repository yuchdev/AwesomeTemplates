"""Detect template agents that pin an outdated Claude model, and apply the repo's policy to them.

Every agent under `templates/` pins a model in its frontmatter (`model: claude-opus-5-5`), and
those pins are *content this repo distributes into other people's projects* - so a pin that has
gone stale ships stale to everyone who generates from it. Nothing else in the pipeline looks at
the value: `docgen` only copies it into `docs/agent/agents.md`. This module is the one place that
asks "is this still a current model?", kept apart from `docgen` (which describes what shipped,
never judges it) and from `cli.py` (which should only decide what to do with a verdict).

**Policy lives in `pyproject.toml`**, not in code, so a maintainer retires a model by editing one
list, with no release of the generator:

    [tool.awesome_templates.model_policy]
    mode = "warn"                      # off | warn | error

    [tool.awesome_templates.model_policy.recommended]
    anthropic = ["claude-opus-5-5", "claude-sonnet-5-5"]
    openai = []
    google = []

    [tool.awesome_templates.model_policy.vendors]      # live check only: env var NAMES, never keys
    anthropic = { key_env = "ANTHROPIC_API_KEY" }

- `off`   - no check (also the behaviour when the table is absent: no config, no policy).
- `warn`  - findings become entries in `generate`'s `warnings`; generation proceeds.
- `error` - findings abort `generate` before anything is written (the same "refuse, don't
  half-write" stance as the non-empty `.claude/` check).

**One list, per vendor.** `recommended` is the single place a maintainer names the models templates
should use; `ModelPolicy.current` is the union of its values, and that union is what pins are judged
against. Whether a listed ID is actually *served* is a different question answered by the opt-in
`model_catalog` module (vendor Models APIs), never by this offline module.

**Allowlist, not denylist.** "Outdated" means "not in `current`", so there is a single list to
maintain per model release and a typo'd ID is caught as well as a retired one. Two things are
deliberately never findings: a missing `model:` line (the agent inherits the session's model, so
it cannot be stale) and the floating aliases Claude Code resolves to the newest model itself
(`opus`, `sonnet`, `haiku`, `inherit`).

**What a `generate` run is checked against** is exactly what it copies - `templates/common/`, the
chosen preset, and the chosen specializations - not the whole tree. Blocking a Java run because an
unrelated C++ specialization is stale would be wrong; the whole-tree sweep is the separate
`check-models` command.

Stdlib-only and offline, like `docgen`: it must never import `anthropic` (the check runs on every
`generate`, including the plain offline one).
"""

from __future__ import annotations

import enum
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from awesome_templates.catalog import list_presets
from awesome_templates.docgen import parse_frontmatter
from awesome_templates.log_helper import NULL_LOG, LogHelper
from awesome_templates.presets import COMMON_PRESET_NAME
from awesome_templates.specializations import list_specializations, specialization_root
from awesome_templates.workspace import Workspace

# Claude Code resolves these itself to its newest model of that tier (or the parent session's, for
# `inherit`), so pinning one can never go stale and they are exempt from the allowlist.
FLOATING_ALIASES = frozenset({"opus", "sonnet", "haiku", "inherit"})


class ModelPolicyError(Exception):
    """Either the policy configuration is invalid, or `mode = "error"` and outdated pins were
    found. The CLI surfaces it as an error message and a non-zero exit, like `ConfigError`."""


class PolicyMode(str, enum.Enum):
    off = "off"
    warn = "warn"
    error = "error"


@dataclass(frozen=True)
class UpgradeRule:
    """How one vendor's outdated model is replaced - three small facts, no old->new edges.

    `families` is an ordered list of (name, regex) classifying an *old* ID (`opus`, `sonnet`...);
    `targets` maps a family name to the model to move to; `default` catches an ID that matches no
    family or whose family has no target. A new release edits one target; a past release needs no
    entry at all, so the table never grows with the number of versions or vendors.
    """

    families: tuple[tuple[str, re.Pattern[str]], ...] = ()
    targets: Mapping[str, str] = field(default_factory=dict)
    default: Optional[str] = None

    def target_for(self, model: str) -> Optional[str]:
        for name, pattern in self.families:
            if pattern.search(model):
                return self.targets.get(name, self.default)
        return self.default


@dataclass(frozen=True)
class ModelPolicy:
    """`current` is every recommended ID across vendors; `recommended` keeps the per-vendor split and
    `key_envs` the env var *name* holding each vendor's key for the live check (both optional)."""

    mode: PolicyMode
    current: frozenset[str]
    recommended: Mapping[str, frozenset[str]] = field(default_factory=dict)
    key_envs: Mapping[str, str] = field(default_factory=dict)
    upgrade: Mapping[str, UpgradeRule] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelFinding:
    """One agent file whose pinned model is not in the policy's `current` list."""

    path: Path
    model: str


def load_policy(pyproject: Path) -> ModelPolicy:
    """Read `[tool.awesome_templates.model_policy]` from `pyproject`.

    A missing file or missing table is `off`, not an error: the generator can run from an
    install that has no repo `pyproject.toml` beside it, and a repo that never configured a
    policy has not asked for one. A *present but malformed* table is an error - silently
    treating `mode = "eror"` as `off` would turn a typo into a disabled safety check.

    :raises ModelPolicyError: unreadable/invalid TOML, an unknown `mode`, or `current` that is not a
        non-empty list of strings while the mode is `warn`/`error` (nothing could be judged).
    """
    if not pyproject.is_file():
        return ModelPolicy(PolicyMode.off, frozenset())
    try:
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ModelPolicyError(f"cannot read model policy from '{pyproject}': {exc}") from exc

    table = data.get("tool", {}).get("awesome_templates", {}).get("model_policy")
    if table is None:
        return ModelPolicy(PolicyMode.off, frozenset())

    raw_mode = table.get("mode", "warn")
    try:
        mode = PolicyMode(str(raw_mode).lower())
    except ValueError:
        choices = ", ".join(m.value for m in PolicyMode)
        raise ModelPolicyError(
            f"{pyproject}: [tool.awesome_templates.model_policy] mode = {raw_mode!r} is not one of: {choices}"
        ) from None

    if "current" in table:
        raise ModelPolicyError(
            f"{pyproject}: [tool.awesome_templates.model_policy] current was replaced by the per-vendor "
            "[tool.awesome_templates.model_policy.recommended] table (e.g. anthropic = [...])"
        )
    recommended = _parse_recommended(table.get("recommended", {}), pyproject)
    current = frozenset(m for ids in recommended.values() for m in ids)
    if mode is not PolicyMode.off and not current:
        raise ModelPolicyError(
            f"{pyproject}: [tool.awesome_templates.model_policy.recommended] must list at least one model "
            f"ID when mode is '{mode.value}'"
        )
    return ModelPolicy(
        mode,
        current,
        recommended,
        _parse_key_envs(table.get("vendors", {}), pyproject),
        _parse_upgrade(table.get("upgrade", {}), recommended, pyproject),
    )


def _parse_upgrade(
    raw: object, recommended: Mapping[str, frozenset[str]], pyproject: Path
) -> dict[str, UpgradeRule]:
    """Parse `[...model_policy.upgrade.<vendor>]`. A target (or default) that is not itself in that
    vendor's `recommended` list is rejected here, so `upgrade` can never write a model the policy
    would flag on the very next run."""
    where = f"{pyproject}: [tool.awesome_templates.model_policy.upgrade]"
    if not isinstance(raw, dict):
        raise ModelPolicyError(f"{where} must be a table of vendor tables")
    rules = {}
    for vendor, spec in raw.items():
        if not isinstance(spec, dict):
            raise ModelPolicyError(f"{where} {vendor} must be a table")
        families_raw, targets = spec.get("families", {}), spec.get("targets", {})
        default = spec.get("default")
        if not isinstance(families_raw, dict) or not isinstance(targets, dict):
            raise ModelPolicyError(f"{where} {vendor}: families and targets must be tables")
        families = []
        for name, regex in families_raw.items():
            try:
                families.append((name, re.compile(str(regex))))
            except re.error as exc:
                raise ModelPolicyError(f"{where} {vendor}: family '{name}' is not a valid regex: {exc}") from None
        unknown = sorted(set(targets) - set(families_raw))
        if unknown:
            raise ModelPolicyError(f"{where} {vendor}: targets name unknown families: {', '.join(unknown)}")
        wanted = [*targets.values(), *([default] if default is not None else [])]
        for target in wanted:
            if not isinstance(target, str) or target not in recommended.get(vendor, frozenset()):
                raise ModelPolicyError(
                    f"{where} {vendor}: upgrade target {target!r} must be listed under "
                    f"[tool.awesome_templates.model_policy.recommended] {vendor}"
                )
        rules[vendor] = UpgradeRule(tuple(families), dict(targets), default)
    return rules


def _parse_recommended(raw: object, pyproject: Path) -> dict[str, frozenset[str]]:
    where = f"{pyproject}: [tool.awesome_templates.model_policy.recommended]"
    if not isinstance(raw, dict):
        raise ModelPolicyError(f"{where} must be a table of vendor = [model IDs]")
    parsed = {}
    for vendor, ids in raw.items():
        if not isinstance(ids, list) or not all(isinstance(m, str) and m.strip() for m in ids):
            raise ModelPolicyError(f"{where} {vendor} must be a list of non-empty model ID strings")
        parsed[vendor] = frozenset(ids)
    return parsed


def _parse_key_envs(raw: object, pyproject: Path) -> dict[str, str]:
    where = f"{pyproject}: [tool.awesome_templates.model_policy.vendors]"
    if not isinstance(raw, dict):
        raise ModelPolicyError(f"{where} must be a table of vendor = {{ key_env = \"NAME\" }}")
    envs = {}
    for vendor, spec in raw.items():
        name = spec.get("key_env") if isinstance(spec, dict) else None
        if not isinstance(name, str) or not name:
            raise ModelPolicyError(f"{where} {vendor} needs key_env = \"ENV_VAR_NAME\"")
        envs[vendor] = name
    return envs


def scan_agents_dir(agents_dir: Path, policy: ModelPolicy) -> list[ModelFinding]:
    """Findings for every `*.md` agent directly under `agents_dir` pinning a non-current model."""
    if policy.mode is PolicyMode.off or not agents_dir.is_dir():
        return []
    findings = []
    for path in sorted(agents_dir.glob("*.md")):
        fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        model = fm.get("model", "").strip().strip("'\"")
        if not model or model in FLOATING_ALIASES or model in policy.current:
            continue
        findings.append(ModelFinding(path=path, model=model))
    return findings


def scan_generation(
    workspace: Workspace, preset: str, specializations: Sequence[str], policy: ModelPolicy
) -> list[ModelFinding]:
    """Findings for exactly the agent sources `copy_preset` would copy for this run."""
    dirs = [
        workspace.path(COMMON_PRESET_NAME, ".claude", "agents"),
        workspace.path(preset, ".claude", "agents"),
        *(specialization_root(workspace, preset, name) / ".claude" / "agents" for name in specializations),
    ]
    return [f for d in dirs for f in scan_agents_dir(d, policy)]


def scan_all(workspace: Workspace, policy: ModelPolicy) -> list[ModelFinding]:
    """Findings across the whole template tree: common, every preset, every specialization."""
    dirs = [workspace.path(COMMON_PRESET_NAME, ".claude", "agents")]
    for preset in list_presets(workspace):
        dirs.append(workspace.path(preset, ".claude", "agents"))
        dirs.extend(
            specialization_root(workspace, preset, name) / ".claude" / "agents"
            for name in list_specializations(workspace, preset)
        )
    return [f for d in dirs for f in scan_agents_dir(d, policy)]


_VENDOR_PREFIXES = (("claude-", "anthropic"), ("gpt-", "openai"), ("chatgpt-", "openai"), ("gemini-", "google"))
_OPENAI_REASONING_RE = re.compile(r"^o\d")


def vendor_of(model: str, policy: ModelPolicy) -> Optional[str]:
    """The vendor that serves `model`: whichever `recommended` list names it, else a prefix guess
    (`claude-`, `gpt-`, `o<digit>`, `gemini-`), else None. The guess lets a typo'd or unlisted pin still
    be routed to the right vendor's live check instead of escaping it."""
    for vendor, ids in policy.recommended.items():
        if model in ids:
            return vendor
    for prefix, vendor in _VENDOR_PREFIXES:
        if model.startswith(prefix):
            return vendor
    return "openai" if _OPENAI_REASONING_RE.match(model) else None


def display_path(path: Path, relative_to: Optional[Path] = None) -> str:
    """`path` relative to `relative_to` when it lies under it, else unchanged - so a synthetic
    workspace outside the repo (tests, an out-of-tree templates dir) still prints something sane."""
    if relative_to is not None:
        try:
            return str(path.relative_to(relative_to))
        except ValueError:
            pass
    return str(path)


def format_finding(finding: ModelFinding, relative_to: Optional[Path] = None) -> str:
    shown = display_path(finding.path, relative_to)
    return f"outdated model in {shown}: '{finding.model}' is not in model_policy.recommended"


def enforce(
    findings: Sequence[ModelFinding],
    policy: ModelPolicy,
    warnings: list[str],
    *,
    relative_to: Optional[Path] = None,
    log: LogHelper = NULL_LOG,
) -> None:
    """Apply the policy's mode to `findings`: append warnings, or raise.

    :raises ModelPolicyError: `mode = "error"` and there is at least one finding. The message lists
        every offender and the current list, so one failed run is enough to fix them all.
    """
    if not findings or policy.mode is PolicyMode.off:
        return
    lines = [format_finding(f, relative_to) for f in findings]
    if policy.mode is PolicyMode.error:
        current = ", ".join(sorted(policy.current))
        raise ModelPolicyError(
            f"{len(lines)} template agent(s) pin an outdated model (model_policy.mode = 'error' in "
            f"pyproject.toml; current: {current}):\n  " + "\n  ".join(lines)
        )
    for line in lines:
        warnings.append(line)
        log.warning(line)

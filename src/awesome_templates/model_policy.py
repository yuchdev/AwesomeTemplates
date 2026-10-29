"""Detect template agents that pin an outdated Claude model, and apply the repo's policy to them.

Every agent under `templates/` pins a model in its frontmatter (`model: claude-opus-5-5`), and
those pins are *content this repo distributes into other people's projects* - so a pin that has
gone stale ships stale to everyone who generates from it. Nothing else in the pipeline looks at
the value: `docgen` only copies it into `docs/agent/agents.md`. This module is the one place that
asks "is this still a current model?", kept apart from `docgen` (which describes what shipped,
never judges it) and from `cli.py` (which should only decide what to do with a verdict).

**Policy lives in `model-policy.toml`** (repo root), not in code and not in `pyproject.toml` - it
outgrew that file once `upgrade` needed per-role tables - so a maintainer retires a model by editing
one list, with no release of the generator:

    mode = "warn"                      # off | warn | error

    [recommended]
    anthropic = ["claude-opus-5-5", "claude-sonnet-5-5"]
    openai = []
    google = []

    [vendors]                          # live check only: env var NAMES, never keys
    anthropic = { key_env = "ANTHROPIC_API_KEY" }

    [roles]                            # agent role (file stem) -> cost tier, vendor-independent
    cpp-expert = "deep"
    [upgrade.anthropic.tiers]          # per vendor: tier -> model
    deep = "claude-opus-5-5"

- `off`   - no check (also the behaviour when the file is absent or empty: no config, no policy).
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

**Upgrade targets are chosen by role and vendor, never by old model.** `[roles]` gives each agent
role a tier (`deep`, `standard`...) once; each vendor's `[upgrade.<vendor>.tiers]` says which model
serves a tier. So `cpp-expert` can land on a vendor's flagship while `docs-updater` lands on its cheaper
model, and a new release edits one tier line per vendor. `docs/model-upgrade-matrix.md` renders the
resulting role x vendor table (`render_matrix`) and a test keeps it equal to this file.

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
    """How one vendor's outdated model is replaced - small facts, no old->new edges.

    `tiers` maps a cost tier to the model serving it and `roles` overrides that for one agent role;
    both are consulted first (see `ModelPolicy.upgrade_target`). The rest is the fallback for a pin
    whose role is unknown: `families` is an ordered list of (name, regex) classifying an *old* ID,
    `targets` maps a family name to the model to move to, `default` catches an ID that matches no
    family or whose family has no target. A new release edits one target; a past release needs no
    entry at all, so the table never grows with the number of versions or vendors.
    """

    families: tuple[tuple[str, re.Pattern[str]], ...] = ()
    targets: Mapping[str, str] = field(default_factory=dict)
    default: Optional[str] = None
    tiers: Mapping[str, str] = field(default_factory=dict)
    roles: Mapping[str, str] = field(default_factory=dict)

    def target_for(self, model: str) -> Optional[str]:
        for name, pattern in self.families:
            if pattern.search(model):
                return self.targets.get(name, self.default)
        return self.default


@dataclass(frozen=True)
class ModelPolicy:
    """`current` is every recommended ID across vendors; `recommended` keeps the per-vendor split and
    `key_envs` the env var *name* holding each vendor's key for the live check (both optional).
    `role_tiers` maps an agent role (file stem) to its vendor-independent cost tier."""

    mode: PolicyMode
    current: frozenset[str]
    recommended: Mapping[str, frozenset[str]] = field(default_factory=dict)
    key_envs: Mapping[str, str] = field(default_factory=dict)
    upgrade: Mapping[str, UpgradeRule] = field(default_factory=dict)
    role_tiers: Mapping[str, str] = field(default_factory=dict)

    def upgrade_target(self, vendor: str, model: str, role: Optional[str] = None) -> Optional[str]:
        """The model a stale `model` pin on `vendor` should move to, or None if nothing is configured.

        Order: the vendor's explicit override for `role`, then the vendor's model for the role's tier,
        then the old-ID family/default fallback (an agent that is not a known role, e.g. a user's own).
        """
        rule = self.upgrade.get(vendor)
        if rule is None:
            return None
        if role is not None:
            if role in rule.roles:
                return rule.roles[role]
            tier = self.role_tiers.get(role)
            if tier is not None and tier in rule.tiers:
                return rule.tiers[tier]
        return rule.target_for(model)


@dataclass(frozen=True)
class ModelFinding:
    """One agent file whose pinned model is not in the policy's `current` list."""

    path: Path
    model: str


def load_policy(path: Path) -> ModelPolicy:
    """Read the model policy from the standalone TOML file `path` (`model-policy.toml`).

    A missing or empty file is `off`, not an error: the generator can run from an install that has no
    policy file beside it, and a repo that never configured one has not asked for one. A *present but
    malformed* file is an error - silently treating `mode = "eror"` as `off` would turn a typo into a
    disabled safety check.

    :raises ModelPolicyError: unreadable/invalid TOML, an unknown `mode`, no recommended model while
        the mode is `warn`/`error` (nothing could be judged), or an inconsistent upgrade protocol
        (a target outside `recommended`, a role whose tier a vendor does not define, a bad regex).
    """
    if not path.is_file():
        return ModelPolicy(PolicyMode.off, frozenset())
    try:
        with path.open("rb") as fh:
            table = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ModelPolicyError(f"cannot read model policy from '{path}': {exc}") from exc
    if not table:
        return ModelPolicy(PolicyMode.off, frozenset())

    raw_mode = table.get("mode", "warn")
    try:
        mode = PolicyMode(str(raw_mode).lower())
    except ValueError:
        choices = ", ".join(m.value for m in PolicyMode)
        raise ModelPolicyError(f"{path}: mode = {raw_mode!r} is not one of: {choices}") from None

    recommended = _parse_recommended(table.get("recommended", {}), path)
    current = frozenset(m for ids in recommended.values() for m in ids)
    if mode is not PolicyMode.off and not current:
        raise ModelPolicyError(f"{path}: [recommended] must list at least one model ID when mode is '{mode.value}'")
    role_tiers = _parse_roles(table.get("roles", {}), path)
    upgrade = _parse_upgrade(table.get("upgrade", {}), recommended, path)
    _check_role_tiers(role_tiers, upgrade, path)
    return ModelPolicy(mode, current, recommended, _parse_key_envs(table.get("vendors", {}), path), upgrade, role_tiers)


def _str_table(raw: object, where: str) -> dict[str, str]:
    """A table whose keys and values are all non-empty strings."""
    if not isinstance(raw, dict) or not all(isinstance(v, str) and v.strip() for v in raw.values()):
        raise ModelPolicyError(f"{where} must be a table of name = \"non-empty string\"")
    return dict(raw)


def _parse_roles(raw: object, path: Path) -> dict[str, str]:
    return _str_table(raw, f"{path}: [roles]")


def _parse_upgrade(raw: object, recommended: Mapping[str, frozenset[str]], path: Path) -> dict[str, UpgradeRule]:
    """Parse `[upgrade.<vendor>]`. Every model it names (tier, role override, family target, default)
    must itself be in that vendor's `recommended` list, so `upgrade` can never write a model the policy
    would flag on the very next run."""
    where = f"{path}: [upgrade]"
    if not isinstance(raw, dict):
        raise ModelPolicyError(f"{where} must be a table of vendor tables")
    rules = {}
    for vendor, spec in raw.items():
        if not isinstance(spec, dict):
            raise ModelPolicyError(f"{where} {vendor} must be a table")
        families_raw = spec.get("families", {})
        if not isinstance(families_raw, dict) or not isinstance(spec.get("targets", {}), dict):
            raise ModelPolicyError(f"{where} {vendor}: families and targets must be tables")
        targets = _str_table(spec.get("targets", {}), f"{where} {vendor}.targets")
        tiers = _str_table(spec.get("tiers", {}), f"{where} {vendor}.tiers")
        roles = _str_table(spec.get("roles", {}), f"{where} {vendor}.roles")
        default = spec.get("default")
        families = []
        for name, regex in families_raw.items():
            try:
                families.append((name, re.compile(str(regex))))
            except re.error as exc:
                raise ModelPolicyError(f"{where} {vendor}: family '{name}' is not a valid regex: {exc}") from None
        unknown = sorted(set(targets) - set(families_raw))
        if unknown:
            raise ModelPolicyError(f"{where} {vendor}: targets name unknown families: {', '.join(unknown)}")
        wanted = [*targets.values(), *tiers.values(), *roles.values(), *([default] if default is not None else [])]
        for target in wanted:
            if not isinstance(target, str) or target not in recommended.get(vendor, frozenset()):
                raise ModelPolicyError(
                    f"{where} {vendor}: upgrade target {target!r} must be listed under [recommended] {vendor}"
                )
        rules[vendor] = UpgradeRule(tuple(families), targets, default, tiers, roles)
    return rules


def _check_role_tiers(role_tiers: Mapping[str, str], upgrade: Mapping[str, UpgradeRule], path: Path) -> None:
    """Every tier a role uses must be defined by each vendor that declares tiers at all - otherwise
    that role would silently fall through to the coarse fallback for that vendor."""
    for vendor, rule in upgrade.items():
        if not rule.tiers:
            continue
        missing = sorted({t for t in role_tiers.values() if t not in rule.tiers})
        if missing:
            raise ModelPolicyError(f"{path}: [upgrade.{vendor}.tiers] does not define tier(s) used by [roles]: {', '.join(missing)}")


def _parse_recommended(raw: object, path: Path) -> dict[str, frozenset[str]]:
    where = f"{path}: [recommended]"
    if not isinstance(raw, dict):
        raise ModelPolicyError(f"{where} must be a table of vendor = [model IDs]")
    parsed = {}
    for vendor, ids in raw.items():
        if not isinstance(ids, list) or not all(isinstance(m, str) and m.strip() for m in ids):
            raise ModelPolicyError(f"{where} {vendor} must be a list of non-empty model ID strings")
        parsed[vendor] = frozenset(ids)
    return parsed


def _parse_key_envs(raw: object, path: Path) -> dict[str, str]:
    where = f"{path}: [vendors]"
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
    return [f for d in _agent_dirs(workspace) for f in scan_agents_dir(d, policy)]


def _agent_dirs(workspace: Workspace) -> list[Path]:
    dirs = [workspace.path(COMMON_PRESET_NAME, ".claude", "agents")]
    for preset in list_presets(workspace):
        dirs.append(workspace.path(preset, ".claude", "agents"))
        dirs.extend(
            specialization_root(workspace, preset, name) / ".claude" / "agents"
            for name in list_specializations(workspace, preset)
        )
    return dirs


def discover_roles(workspace: Workspace) -> frozenset[str]:
    """Every agent role (file stem) the template tree ships - the set `[roles]` must cover."""
    return frozenset(p.stem for d in _agent_dirs(workspace) if d.is_dir() for p in d.glob("*.md"))


# `docs/model-upgrade-matrix.md` holds the rendered table between these markers; everything outside
# them is hand-written prose.
MATRIX_BEGIN = "<!-- model-matrix:begin (generated from model-policy.toml; run `awesome-templates model-matrix --write`) -->"
MATRIX_END = "<!-- model-matrix:end -->"


def render_matrix(policy: ModelPolicy) -> str:
    """The role x vendor table: for each role, its tier and the model each vendor moves it to.

    Pure function of the policy, so the doc can be regenerated byte-identically and compared. Vendors
    that declare neither tiers nor role overrides have no column - they cannot answer for a role.
    A final row shows what an agent that is not a known role falls back to.
    """
    vendors = sorted(v for v, r in policy.upgrade.items() if r.tiers or r.roles)
    header = ["Role", "Tier", *vendors]
    rows = [header, ["---"] * len(header)]
    for role in sorted(policy.role_tiers):
        cells = [policy.upgrade_target(v, "", role) or "-" for v in vendors]
        rows.append([f"`{role}`", policy.role_tiers[role], *(f"`{c}`" if c != "-" else c for c in cells)])
    fallback = [policy.upgrade[v].default for v in vendors]
    rows.append(["*any other role*", "-", *(f"`{c}`" if c else "-" for c in fallback)])
    return "\n".join("| " + " | ".join(r) + " |" for r in rows)


def splice_matrix(doc: str, policy: ModelPolicy) -> str:
    """`doc` with the text between the matrix markers replaced by the current rendering.

    :raises ModelPolicyError: the markers are missing, so there is nowhere to put the table.
    """
    start, end = doc.find(MATRIX_BEGIN), doc.find(MATRIX_END)
    if start < 0 or end < start:
        raise ModelPolicyError("model-upgrade-matrix doc has no matrix begin/end markers")
    return doc[: start + len(MATRIX_BEGIN)] + "\n" + render_matrix(policy) + "\n" + doc[end:]


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
            f"model-policy.toml; current: {current}):\n  " + "\n  ".join(lines)
        )
    for line in lines:
        warnings.append(line)
        log.warning(line)

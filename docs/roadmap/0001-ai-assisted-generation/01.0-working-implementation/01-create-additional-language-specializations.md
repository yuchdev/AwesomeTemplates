# Language Specializations

## Goal

For Python, add specialization agents/skills for:

* Django
* Web scraping
* ML/AI

For Java, add specialization agents/skills for:

* Spring
* Android

Specializations must be **independent from the core preset** (`../../../../templates/python`,
`../../../../templates/java`) — a preset generates correctly with zero specializations selected, exactly as
it does today. `generate` gets a new optional, repeatable flag to select zero or more
specializations; the entities they add are listed in `../../../agent/agents.md` /
`../../../agent/skills.md` (see task 02, which owns *how* those docs get populated).

## Why this isn't just "add more agents to templates/python"

Root `../../../../CLAUDE.md` currently states the generation model as a hard invariant:

> Generating one is *just* a recursive copy with substitution applied to every text file
> (see `presets.py`) — there is no runtime composition step, no category selection, no
> per-entity include/exclude. This is deliberate.

That invariant is about the **preset itself** — `../../../../.claude` + `../../..` + `../../../../scripts` must stay one
corpus authored and reviewed together (its `hooks` reference only what its `settings.json` wires,
its docs reference only what actually ships). Specializations don't touch that: they are a
**second, separate opt-in layer** that sits beside a preset, not inside it. This task adds that
layer without weakening the existing guarantee — a generated project with no `--specialization`
flags must be byte-for-byte what `generate` produces today (this is a regression test, not just a
design goal — see Acceptance Criteria).

`★ Insight ─────────────────────────────────────`
This is the same shape as `create-from-template` in the repo's own `../../../../.claude/agents` (per root
`../../../../CLAUDE.md`): a capability that is deliberately kept *outside* the preset tree because it isn't
something every generated project needs standing presence of. Specializations are the mirror
image — content the *target* project needs, but only some target projects, so it can't be baked
into the one tree every project gets.
`─────────────────────────────────────────────────`

## Design

### Directory shape

A specialization is a subdirectory of `templates/<preset>/specializations/<name>/`, shaped like a
*miniature* preset containing only the two kinds a specialization is allowed to touch —
`agents/` and `skills/`:

```
templates/
  python/
    .claude/                      # unchanged - the core preset
    docs/
    scripts/
    specializations/
      django/
        .claude/
          agents/
            django-expert.md
          skills/
            django-migrations/
              SKILL.md
      webscraping/
        .claude/
          agents/
            scraping-expert.md
      ml-ai/
        .claude/
          agents/
            ml-expert.md
  java/
    .claude/
    docs/
    scripts/
    specializations/
      spring/
        .claude/
          agents/
            spring-expert.md
      android/
        .claude/
          agents/
            android-expert.md
```

**Why nested under `templates/<preset>/`, not a top-level `templates/specializations/`:** Django
is meaningless in a Java-generated project and Spring is meaningless in a Python one. Nesting
under the owning preset makes an invalid pairing structurally impossible instead of something
`generate` has to validate at runtime.

**Why this is invisible to existing catalog/graph code, unchanged:**
`catalog.list_presets` only inspects *immediate* children of `../../../../templates` that have both `../../../../.claude`
and `../../..` — `../../../../templates/python/specializations` is two levels too deep and has no `../../..`, so it
is never mistaken for a third preset. `catalog.discover(Workspace(root=templates/python))` finds
`../../../../.claude` at that root and returns immediately — it never looks at `specializations/` at all.
Both are existing behaviors, not new code; this must stay true (see Acceptance Criteria).

**Why only `agents/` and `skills/`, never `hooks/`, `loops/`, or `settings.json`:** a hook is inert
until something wires it in `settings.json`, and `settings.json` is owned by the core preset (root
`../../../../CLAUDE.md`: "already trimmed to reference only hooks that exist in that preset"). Letting a
specialization ship a hook with no wiring path would recreate exactly the dead-file class of bug
root `../../../../CLAUDE.md` already documents as having shipped before (`hooks/doc_registry.py`,
`hooks/linkify_doc_mentions.py`). Agents and skills are self-contained Markdown that the user
invokes directly or Claude Code discovers by directory listing — no third file has to agree to
wire them in, so they're the only two kinds safe to add out-of-band.

### New module: `../../../../src/awesome_templates/specializations.py`

Pure filesystem code, no network, following the same "one focused module per concern" style as
`markers.py`:

```python
"""Discovery of the opt-in specialization layer: agent/skill add-ons nested
under templates/<preset>/specializations/<name>/, selected at `generate` time
via --specialization. See catalog.py's docstring for why a *preset* has
nothing to select or compose - this is a deliberately separate, optional
layer beside it, not an exception to that rule.
"""

from __future__ import annotations

from pathlib import Path

from awesome_templates.catalog import KINDS, discover
from awesome_templates.workspace import Workspace

# Kinds a specialization is allowed to ship. Anything else present under its
# .claude/ (hooks/, loops/, settings.json) is an authoring error - hooks need
# settings.json wiring that only the core preset owns (see module docstring).
ALLOWED_KINDS = ("agents", "skills")


def specialization_root(workspace: Workspace, preset: str, name: str) -> Path:
    return workspace.path(preset) / "specializations" / name


def list_specializations(workspace: Workspace, preset: str) -> list[str]:
    """Every immediate child of templates/<preset>/specializations/ that has
    a .claude/ with at least one agent or skill. Empty list (not an error)
    when the preset has no specializations dir at all."""
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
    loops/, or a settings.json) - empty when the specialization is clean."""
    root = specialization_root(workspace, preset, name) / ".claude"
    found = []
    for kind in KINDS:
        if kind not in ALLOWED_KINDS and (root / kind).is_dir() and any((root / kind).iterdir()):
            found.append(kind)
    if (root / "settings.json").exists():
        found.append("settings.json")
    return found
```

`list_specializations` deliberately reuses `catalog.discover` rather than hand-rolling a second
directory walk — `templates/<preset>/specializations/<name>/` is exactly the "preset directory
with kind dirs nested one level under `../../../../.claude`" shape `catalog.discover` already documents and
handles, so no new discovery logic is needed, only a new *place* to point it at.

### `presets.py`: merging a specialization into the copy

`copy_preset` gains an optional `specializations` parameter. After copying the base preset tree,
each selected specialization's `../../../../.claude` is copied into the same destination `../../../../.claude`, reusing
the existing `_copy_tree` helper (same substitution, same force semantics):

```python
def copy_preset(
    workspace: Workspace,
    preset: str,
    project_dir: Path,
    force: bool,
    subs: dict[str, str],
    warnings: list[str],
    specializations: Sequence[str] = (),
) -> int:
    """Copy templates/<preset>/ into project_dir/, then layer each selected
    specialization's agents/skills on top. Collisions between the base preset,
    two specializations, or a specialization and an earlier one, are an
    authoring bug in templates/ - not a runtime condition to swallow - so this
    raises rather than silently skipping or overwriting."""
    count = _copy_tree(workspace.path(preset), project_dir, force, subs, warnings)
    seen = _entity_names(project_dir)
    for name in specializations:
        spec_dir = specialization_root(workspace, preset, name) / ".claude"
        collisions = _entity_names(spec_dir) & seen
        if collisions:
            raise ValueError(
                f"specialization '{name}' redefines existing entit{'y' if len(collisions) == 1 else 'ies'}: "
                f"{', '.join(sorted(collisions))}"
            )
        count += _copy_tree(spec_dir, project_dir / ".claude", force, subs, warnings)
        seen |= _entity_names(spec_dir)
    return count
```

`_entity_names` is a small new helper (`{(kind, stem) for kind in KINDS for stem in ...}`) built on
the same `_discover_kind`-shaped walk `catalog.py` already has — collisions are a `../../../../templates`
authoring bug that should fail a test long before a user hits it (see Acceptance Criteria), so
raising here (rather than a soft warning) is intentional: it's the same posture the "no dead
hook/script pairs" rule in root `../../../../CLAUDE.md` takes toward other cross-tree authoring mistakes.

### `cli.py`: `--specialization` (repeatable)

```python
specialization: Optional[list[str]] = typer.Option(
    None, "--specialization",
    help="add a specialization's agents/skills on top of the preset "
    "(repeatable; see `awesome-templates list` for choices per preset)",
),
```

* Config-file fallback: `cfg.get("specializations", [])` (a JSON/TOML list). **CLI flags replace
  the config list wholesale when any `--specialization` is passed — they do not merge/union with
  it.** This matches every other `generate` option's override semantics (CLI always wins outright)
  and must be stated explicitly, since "merge" is the other plausible reading for a list-valued
  option and the two behave very differently.
* Validate each requested name against `specializations.list_specializations(workspace,
  preset_value)`; unknown name → `_fail(...)` listing the valid choices, mirroring
  `_resolve_preset`'s existing message shape exactly.
* `--dry-run --json` payload gains `"specializations": [...]`.
* The non-JSON dry-run console line gains a `Specializations: ...` line when any are selected.
* `list` command (table and `--json`) grows a `specializations` column/key per preset, sourced from
  `specializations.list_specializations`.

## Non-goals

* `awesome-templates graph` does **not** learn about `specializations/` in this task. It answers
  "does this authored corpus's cross-references resolve", which is a maintainer question about
  `../../../../templates` itself; a specialization selected at generate time isn't part of that corpus's
  authored graph. Worth revisiting later, not blocking this task.
* No specialization ships a hook, loop, or `settings.json` — enforced structurally (Acceptance
  Criteria), not just by convention.
* No UI/interactive picker — `--specialization` is a plain repeatable CLI flag.

## Acceptance Criteria

### Code

- [ ] `../../../../src/awesome_templates/specializations.py`: `specialization_root`, `list_specializations`,
      `disallowed_kinds_present` (or equivalent structural check), as sketched above.
- [ ] `../../../../src/awesome_templates/presets.py`: `copy_preset` accepts `specializations: Sequence[str] =
      ()`, layers each on top after the base copy, raises `ValueError` on entity-name collision.
- [ ] `../../../../src/awesome_templates/cli.py`: `generate` gains repeatable `--specialization`; validates
      against `list_specializations`; threads through to `copy_preset`; dry-run JSON/console output
      updated; `list_cmd` (table + `--json`) surfaces available specializations per preset.
- [ ] New template content (each file with real frontmatter matching the existing style of
      `../../../../templates/python/.claude/agents/python-expert.md` / `../../../../templates/java/.claude/agents/java-expert.md`
      — `name`, `description`, `model`, `tools`/`allowed-tools` — and using the same
      `{{PROJECT_NAME}}` / `{{PROJECT_PACKAGE}}` placeholders so zero new code in `templating.py`
      is needed):
  - [ ] `../../../../templates/python/specializations/django/.claude/agents/django-expert.md`
  - [ ] `../../../../templates/python/specializations/django/.claude/skills/django-migrations/SKILL.md`
  - [ ] `../../../../templates/python/specializations/webscraping/.claude/agents/scraping-expert.md`
  - [ ] `../../../../templates/python/specializations/ml-ai/.claude/agents/ml-expert.md`
  - [ ] `../../../../templates/java/specializations/spring/.claude/agents/spring-expert.md`
  - [ ] `../../../../templates/java/specializations/android/.claude/agents/android-expert.md`
- [ ] `../../../../src/awesome_templates/CLAUDE.md` module map gets a `specializations.py` entry, written in
      the same voice as the existing entries.
- [ ] Root `../../../../CLAUDE.md`'s "What this repo is" paragraph is updated to mention the specialization
      layer as an explicit, bounded exception alongside the "no composition" sentence — leaving
      that sentence unqualified after this ships would make `../../../../CLAUDE.md` actively wrong, and this
      file is instructions Claude Code itself loads every session.

### Tests

New `../../../../tests/test_specializations.py` (using `fixture_workspace` from `conftest.py`; extend that
fixture with a `demo/specializations/widgets/.claude/agents/widget-specialist.md` add-on so these
tests don't need their own from-scratch tree):

- [ ] `test_list_specializations_returns_only_valid_addons`
- [ ] `test_list_specializations_empty_when_no_specializations_dir`
- [ ] `test_list_specializations_skips_dir_with_no_agents_or_skills`
- [ ] `test_disallowed_kinds_present_flags_hooks_and_settings_json`
- [ ] `test_copy_preset_merges_specialization_agent_into_claude_agents` — generate `demo` +
      `widgets` into `tmp_path`, assert `.claude/agents/widget-specialist.md` exists *alongside*
      `.claude/agents/widget-verifier.md` (the base preset's own agent untouched).
- [ ] `test_copy_preset_no_specializations_is_byte_identical_to_current_output` — the regression
      guard for the "existing behavior unchanged" claim above: generate `demo` with
      `specializations=()` and assert the resulting tree matches exactly what today's
      `test_presets.py`/`test_cli.py` already assert for a plain generate.
- [ ] `test_copy_preset_specialization_name_collision_raises` — add a second synthetic
      specialization to the fixture that redefines `widget-verifier`, assert `ValueError`.

`../../../../tests/test_cli.py` additions (mirroring `test_generate_rejects_unknown_preset` /
`test_generate_dry_run_...` exactly):

- [ ] `test_generate_rejects_unknown_specialization`
- [ ] `test_generate_dry_run_json_includes_specializations`
- [ ] `test_generate_with_specialization_writes_addon_agent` (end-to-end, `--out tmp_path`)
- [ ] `test_list_cmd_json_includes_specializations_per_preset`

`../../../../tests/test_integration_real_repo.py` additions (parametrized over the *real* `../../../../templates`, like
the existing zero-dangling-`@docs/`-reference test):

- [ ] `test_real_preset_specializations_have_no_placeholder_leftovers` — for every
      `(preset, specialization)` pair `catalog.list_presets` × `specializations.list_specializations`
      produces, generate preset+specialization into `tmp_path` and assert no unresolved
      `{{PLACEHOLDER}}` remains (reusing whatever helper the existing placeholder-leftover check
      already uses).
- [ ] `test_real_specializations_ship_only_agents_and_skills` — for every real specialization,
      `disallowed_kinds_present(...) == []`. This is the test that makes the "no hooks/loops/
      settings.json in a specialization" rule enforced rather than aspirational.

### Docs

- [ ] `../../../agent/agents.md` / `../../../agent/skills.md` in each preset show specialization-provided
      entities *when selected* — this is task 02's deterministic doc-listing feature; this task's
      job is only to make sure the entities it needs to list are discoverable
      (`specializations.list_specializations` + `catalog.discover` on the specialization root), not
      to render the docs itself. Cross-reference, don't duplicate, task 02's acceptance criteria.
- [ ] Repo root `../../../../README.md` (if it documents `generate` usage) gets one `--specialization` example,
      e.g. `awesome-templates generate --preset python --name Acme --specialization django`.
- [ ] A new ADR, `docs/adr/000N-specialization-layer.md` (next available number under
      `../../../adr`), recording this composition-model decision using the repo's existing MADR
      template (see `../../../adr/0001-config-loading-via-layered-settings.md` for the shape) — this is
      exactly the kind of design decision root `../../../../CLAUDE.md` already points to ADRs for.

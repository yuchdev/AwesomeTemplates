# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A generator (`awesome-templates` CLI, source in `src/awesome_templates`) that copies a project-specific
*preset* — a complete, self-contained `.claude/` kit (`agents`, `hooks`, `loops`, `skills`,
`settings.json`) plus its own starter `docs/` and `scripts/` trees — from a template catalog under
`templates/`.
Templates use flat `{{PLACEHOLDER}}` substitution (`PROJECT_NAME`, `PROJECT_PACKAGE`,
`PROJECT_PURPOSE`, `PROJECT_SLUG_UPPER`) so a preset can be dropped into another project after a
single find/replace.

A preset is a directory shaped exactly like what lands in the target project:
`templates/<preset>/.claude/`, `templates/<preset>/docs/`, and `templates/<preset>/scripts/` as
siblings. There are currently two: `python` and `java`. Generating one is *just* a recursive copy with
substitution applied to every text file (see `presets.py`) — there is no runtime composition step, no
category selection, no per-entity include/exclude. This is deliberate: `.claude/`, `docs/`, and
`scripts/` must be generated together, because their references form one corpus. Baking all three
trees into one preset, authored and reviewed together, makes missing generated dependencies
structurally impossible instead of runtime-checked — see
`docs/roadmap/0001-docs-claude-connectivity.md` for the fuller design history (that RFC's Phase 0 was
a runtime `--strict` connectivity check; the preset-tree model superseded it with the same guarantee
by construction).

Keep `src/awesome_templates` (the generator's own code) and `templates/` (the content it distributes)
mentally separate — most bugs are in one or the other, rarely both.

This repo also has its own `.claude/` at the root — that's this repo's *own* maintainer tooling, a
third thing distinct from both of the above. `.claude/agents/create-from-template.md` is the one agent
in it so far: some agents inside `templates/<preset>/.claude/agents/*.md` carry a
`<!-- TEMPLATE-INIT: ... -->` marker — a fact that's project-specific in a way no `{{PLACEHOLDER}}`
substitution could ever fill in (see `reference/aegis/` for a real, lived-in example of what those
facts look like once filled). `create-from-template` is what closes that gap: given a target project's
path (one `awesome-templates generate` already ran against), it deeply analyzes that target and edits
*its* agent files in place. It is deliberately not shipped inside `templates/<preset>/` — it isn't a
capability the generated project needs standing presence of; it's a one-time bootstrap step run from
outside the target, not part of the target's own dev fleet.

## Commands

```bash
# one-time setup - creates .venv and uv.lock
uv sync

# run the CLI
uv run awesome-templates list
uv run awesome-templates generate --preset python --name "Acme Sync" --package acme_sync --out .

# maintainer-only: render this repo's own agent/hook/loop/skill reference graph
uv run awesome-templates graph                      # every preset, side by side
uv run awesome-templates graph templates/python      # one preset's own graph + doc connectivity
uv run awesome-templates graph --inline --force
uv run awesome-templates graph --remove

# tests
uv run pytest --cov=awesome_templates
uv run pytest tests/test_catalog.py::test_name_here   # single test
uv run pytest tests/test_integration_real_repo.py     # exercises the real templates/ tree

# lint
uv run ruff check src/ tests/
```

`generate` also accepts `--config <file.json|file.toml>` (CLI flags override matching config values)
and `--dry-run --json` for a machine-readable preview. `--out` is the project root that gets a
`.claude/` and a `docs/` subdirectory (default: `.`); pass `--force` to overwrite existing content in
either.

**Ruff config note:** both `ruff.toml` (repo root) and `pyproject.toml`'s `[tool.ruff]` section exist
and disagree (different `line-length`, `target-version`, `select`/`ignore` sets). `ruff.toml` takes
precedence when both are present in the same directory, so it — not the `pyproject.toml` block — is
what `ruff check` actually applies.

## Architecture

### The template catalog (`templates/`)

Fixed shape: `templates/<preset>/.claude/<agents|hooks|loops|skills>/` and `templates/<preset>/docs/`.
A preset is *any* immediate subdirectory of `templates/` with both a `.claude/` and a `docs/` child —
`catalog.list_presets` discovers them dynamically, so adding a third preset (e.g. a `node` set) is a
matter of dropping a new tree in, not a code change. `skills` entities are directories (containing
`SKILL.md` + assets); every other kind is a single `.md` or `.py` file, keyed by filename stem.

The two presets are independent and self-contained by design, not two views onto shared source: each
has its own `settings.json` (already trimmed to reference only hooks that exist in that preset — e.g.
`java`'s has no `pytest`/`ruff` permissions or `post_edit_format`/`style_fixes`/`dep_audit`/`run_tests`
wiring, since those hooks are Python-only) and its own copy of anything both presets need (e.g.
`_common.py`, `session_start.py`, the `pr-review` skill). This means the same content can legitimately
differ between presets — `python/.claude/hooks/_common.py` and `java/.claude/hooks/_common.py` are not
required to be identical — so don't "deduplicate" them back into a shared location without checking
whether they've actually diverged.

#### Executable tooling: `.claude/hooks/` vs `scripts/` (two tiers, one rule each)

A preset ships executables in exactly two places, and which one a file belongs in is decided by
**what triggers it**, not by what it does. `presets.py` copies the whole preset tree, so a top-level
`scripts/` directory lands in the generated project as a sibling of `.claude/` and `docs/`.

| | `.claude/hooks/` | `scripts/` |
|---|---|---|
| **Trigger** | Wired in `settings.json` - the harness runs it automatically on a matching tool call / session event | Invoked by explicit path from an agent, skill, or loop's prose |
| **Contract** | Hook protocol: event JSON on stdin, exit `0` allow / `2` block | Ordinary CLI: argv in, exit code out (must support `--help`) |
| **Cost budget** | Must stay cheap - it runs on *every* matching call | May be slow; it runs when someone asks for it |
| **Dependencies** | Stdlib + `_common.py` only. **Never** imports from `scripts/` | Stdlib only; independent of `_common.py` |

Two consequences that are easy to get wrong:

1. **A hook may also expose a CLI escape hatch** (`doc_link_check.py --check`, `style_fixes.py
   --check`, `secret_scan.py <paths>`) so a skill can re-run the same gate on demand. That does *not*
   make it a `scripts/` tool - `settings.json` still owns its trigger, so it stays a hook.
2. **A fast hook and a thorough `scripts/` tool may deliberately overlap** - `doc_link_check.py`
   (per-edit, inline) and `scripts/check_doc_links.py` (whole-corpus, on-demand) are complementary,
   not duplicates. Because the hook can't import from `scripts/`, the shared logic is genuinely
   duplicated, so **`_common.slugify` and `check_doc_links.slugify` must stay behaviourally
   identical** - otherwise the auto-gate and `/link-check` return contradictory verdicts for the same
   anchor. `tests/test_integration_tooling_tiers.py` pins that parity.

What is *not* allowed, and why each rule exists (every one of these has shipped as a bug here):

- A `.claude/hooks/*.py` and a `scripts/*.py` implementing the *same job* under different names with no
  documented split. The deleted `hooks/doc_registry.py` / `hooks/linkify_doc_mentions.py` were dead
  duplicates of the `scripts/` tools every skill actually invoked - unwired, unreferenced, and
  divergent (the hook `linkify_doc_mentions.py` was a needle-search tool; the `scripts/` one is a
  corpus rewriter - same name, different behaviour).
- Prose naming a tool the preset doesn't ship. `update-docs.md` invoked
  `.claude/hooks/doc_registry.py` for five iterations after that file was deleted, and the `java`
  preset's loop invoked `style_fixes.py`, which only exists in `python`.
- A hook importing a name `_common.py` doesn't define. `python`'s `doc_link_check.py` was wired for two
  events while importing four helpers its `_common.py` lacked - an `ImportError` on every edit.

Before adding or moving anything in either tier, run `uv run pytest
tests/test_integration_tooling_tiers.py`: it checks every `hooks/`/`scripts/` mention in every preset's
Markdown resolves, that `settings.json` wires only hooks that exist (and never a `scripts/` tool), that
every hook imports cleanly, that every script's `--help` works, and that the slug implementations agree.

### Generator pipeline (`src/awesome_templates`)

See [`src/awesome_templates/CLAUDE.md`](src/awesome_templates/CLAUDE.md) — the per-module map loads
automatically when working in that directory.

### Tests

`tests/conftest.py`'s `fixture_workspace` builds two tiny synthetic presets ("demo" and "other") under
`tmp_path`, each shaped like a real preset (`<preset>/.claude/<kind>/`, `<preset>/docs/`), for most
unit tests. `real_workspace` points at this repo's actual `templates/`, used by
`test_integration_real_repo.py` to catch real breakage a synthetic fixture can't — including a
parametrized regression test that generates each real preset and asserts zero dangling `@docs/`
references in the result. `test_dependencies.py` hand-builds a `Catalog` directly (bypassing
`catalog.discover()`'s filesystem walk) for its graph-matching-logic tests, since those exercise
`build_dependency_graph` against an arbitrary multi-category layout that isn't meant to model a real
preset.

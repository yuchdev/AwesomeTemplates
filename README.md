# Awesome Templates

A CLI generator that produces project-specific Claude Code kits. It copies a *preset* - a
complete, self-contained `.claude/` + `docs/` + `scripts/` tree - out of this repo's
`templates/` catalog into a target project, applying a flat placeholder substitution on the
way, so an agent fleet that was authored and reviewed once can be dropped into any number of
projects.

The generator installs as the `awesome-templates` console script; its source lives in
`src/awesome_templates/`.

## What a preset is

A preset is any immediate subdirectory of `templates/` that holds both a `.claude/` and a
`docs/` child. There are two today:

```
templates/python/{.claude,docs,scripts}
templates/java/{.claude,docs,scripts}
```

`.claude/` contains `agents/`, `hooks/`, `loops/`, `skills/`, and `settings.json`.

Generating a preset is *just* a recursive copy plus substitution - there is no runtime
composition step, no category selection, no per-entity include/exclude. That is deliberate:
`.claude/`, `docs/`, and `scripts/` are generated together because their cross-references
form one corpus, which makes a missing generated dependency structurally impossible rather
than something a runtime check has to catch. Adding a third preset is a matter of dropping a
new tree into `templates/`, not a code change - `catalog.list_presets` discovers them
dynamically.

The one deliberate exception is the **specialization layer**: each preset may ship zero or
more `templates/<preset>/specializations/<name>/.claude/` add-ons, restricted to `agents/`
and `skills/` only (a hook is inert without the `settings.json` wiring the base preset owns).
`python` offers `django`, `ml-ai`, and `webscraping`; `java` offers `spring` and `android`.

## Substitution and markers

Two kinds of gap get filled, by two different mechanisms:

1. **Deterministic placeholders.** A small fixed glossary - `PROJECT_NAME`,
   `PROJECT_PACKAGE`, `PROJECT_PURPOSE`, `PROJECT_SLUG_UPPER` - substituted by a flat regex
   find/replace over every text file (`templating.py`). An unresolved one produces a
   warning, not a hard failure.
2. **Markers.** `TEMPLATE-INIT` and `SME REVIEW NEEDED` comments carrying an instruction
   describing a project-specific fact that only exists once someone actually reads the
   target project's code. These are resolved by AI, opt-in via `--resolve-markers`.
   `TEMPLATE-INIT` may be resolved away on confident output (or left as a visible TODO
   blockquote); `SME REVIEW NEEDED` is *never* silently resolved - its output always stays
   flagged as an unreviewed AI draft regardless of the model's confidence.

## Usage

```bash
# one-time setup - creates .venv and uv.lock
uv sync

# see every preset and what it contains, including its specializations
uv run awesome-templates list

# generate a preset into a target project root
uv run awesome-templates generate --preset python --name "Acme Sync" --package acme_sync --out .

# layer one or more specializations' agents/skills on top (repeatable)
uv run awesome-templates generate --preset python --name "Acme Sync" --specialization django --out .

# preview without writing anything
uv run awesome-templates generate --preset python --name "Acme Sync" --dry-run --json
```

`--out` is the project root that receives the `.claude/`, `docs/`, and `scripts/`
subdirectories (default `.`). Generation refuses to overwrite non-empty output unless
`--force` is passed. `--specialization` is repeatable, and passing it at all *replaces* a
config file's `specializations` list wholesale rather than merging with it.

`--log-severity {error|warning|info|debug}` (default `warning`) controls live pipeline
tracing, written to stderr so `--json` output on stdout stays parseable at any level.

### Config file

`generate` also accepts `--config <file.json|file.toml>`, picked by extension. Any CLI flag
passed alongside overrides the matching config value.

```toml
preset = "python"
out = "."
force = false
specializations = ["django"]

[project]
name = "Acme Sync"
package = "acme_sync"
purpose = "Synchronizes Acme customer records nightly."
slug_upper = "ACME_SYNC"
```

| Field                | Substitutes         | Default if omitted                                    |
|----------------------|---------------------|-------------------------------------------------------|
| `preset`             | -                   | none - required (or pass `--preset`)                  |
| `out`                | -                   | `.`                                                   |
| `force`              | -                   | `false`                                               |
| `specializations`    | -                   | `[]`                                                  |
| `project.name`       | `PROJECT_NAME`      | none - required (or pass `--name`)                    |
| `project.package`    | `PROJECT_PACKAGE`   | slugified `project.name`                              |
| `project.purpose`    | `PROJECT_PURPOSE`   | a "TODO: describe what this project does" placeholder |
| `project.slug_upper` | `PROJECT_SLUG_UPPER`| upper-slugified `project.name`                        |
| `resolve_markers`    | -                   | `false` (or pass `--resolve-markers`)                 |

### AI-assisted resolution

Plain `generate` is fully offline. Two things layer on top of it:

**Always, no flags and no API key:** `docgen.py` regenerates
`docs/agent/{agents,skills,hooks}.md` and appends an "Actual Test Layout" section to
`docs/test/code_test_coverage.md`, derived from what is actually on disk in the freshly
generated tree (after any specialization layer has merged in).

**Opt-in, `--resolve-markers`:** marker resolution has two backends.

- When the `claude` CLI is on `PATH`, one headless Claude Code research session runs over
  the whole marker manifest with real Read/Grep/Glob access to the researched project,
  authenticating however that CLI already does. Results are reconciled by a before/after
  marker-scan diff, never the model's self-report.
- Without it, an older one-shot Messages API path runs as a warned fallback - one call per
  marker, grounded only in a static context bundle. This needs the optional `ai` extra and
  an `ANTHROPIC_API_KEY` (environment or a `.env` in the cwd).

```bash
uv pip install 'awesome-templates[ai]'    # only needed for the fallback path
export ANTHROPIC_API_KEY=sk-ant-...
uv run awesome-templates generate --config awesome-templates.toml --resolve-markers
```

Three further increments ride the same call, each with its own idempotency guard so a repeat
run never clobbers a user's edits: drafting `docs/agent/tutorial.md` (skipped once it is no
longer the shipped stub), appending one paragraph of observed test conventions to
`docs/test/code_test_coverage.md` (from test file *names* only, never contents), and - only
alongside `--seed-roadmap`, since it deletes example content - replacing the illustrative
roadmap milestone with an AI-proposed real first one. `--update-guidelines` (requires
`--resolve-markers` and the `claude` CLI, no fallback) has the same session create or update
`README.md`, `CLAUDE.md`, and `AGENTS.md` at the output root.

`--dry-run` reports how many markers *would* be resolved without calling any API.

### Maintainer-only: the dependency graph

```bash
uv run awesome-templates graph                   # every preset, side by side
uv run awesome-templates graph templates/python  # one preset's graph + doc connectivity
uv run awesome-templates graph --inline --force  # MUTATES templates/** in place
uv run awesome-templates graph --remove
```

This scans every entity's content for whole-word mentions of every other entity, to answer
"what breaks if I touch X". It does not participate in `generate`. Both mutating flags edit
the template tree in place - review `git diff` before committing.

## Layout

```
src/awesome_templates/     the generator
src/flake8_project_rules/  a standalone flake8 plugin (custom AST rules X001-X011)
templates/<preset>/        the content the generator distributes
tests/                     flat pytest suite; tests/flake8_lint/ covers the plugin
docs/roadmap/{NNNN}-*/     this project's own design documents
.claude/                   this repo's own maintainer tooling (not distributed)
```

Keep `src/awesome_templates/` (the generator's own code) and `templates/` (the content it
distributes) mentally separate - most bugs are in one or the other, rarely both. This repo's
root `.claude/` is a third thing again: its own maintainer tooling, currently one agent,
`create-from-template.md`, which is the interactive sibling of `--resolve-markers`.

## Development

```bash
uv run pytest --cov=awesome_templates                 # full suite
uv run pytest tests/test_catalog.py::test_name_here   # a single test
uv run pytest tests/test_integration_real_repo.py     # exercises the real templates/ tree
uv run ruff check src/ tests/
```

There is no CI workflow and no coverage floor - `pyproject.toml` sets no `fail_under` and no
`addopts`. The full local suite plus a clean ruff run is the bar.

**Ruff config note:** both `ruff.toml` (repo root) and `pyproject.toml`'s `[tool.ruff]`
section exist and deliberately disagree on `line-length`, `target-version`, and rule sets.
`ruff.toml` takes precedence when both are present in the same directory, so it - not the
`pyproject.toml` block - is what `ruff check` actually applies.

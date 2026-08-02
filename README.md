The goal of the project is to create easily deplayable sets of Claude Code agents, skills, hooks, loops obtained from the set of templates with easily substituted values.

The idea is as follows:

Replace explicit project name and other project-specific values in files with template that is easily to misrepresent in Markdown, e.g. `{{PROJECT_NAME}}`, `{{PROJECT_PURPOSE}}` and so on.
After this step, with simple replace artifacts can be added to another Python project.

Each preset is a complete, self-contained tree, shaped exactly like what lands in the target project:

```
templates/python/.claude
templates/python/docs
templates/java/.claude
templates/java/docs
```

`.claude/` contains

```
agents
hooks
loops
skills
settings.json
```

Generating a preset is a plain recursive copy of `templates/<preset>/` into the target project's root,
with `{{PLACEHOLDER}}` substitution applied to every text file - `.claude/` and `docs/` always land
together, from the same source tree, so an agent's `@docs/foo.md` reference can never point at a doc
that didn't get copied.

3. Markdown files contain multiple documents links. Rather than introducing templates, create `MIGRATION_REPORT.md` per each entitiy with all document references. Perhaps will be introduced templates for documents, or special documents conventions accross projects, e.g. `docs/adr` and `docs/roadmap`. The following design will be the subject of further design steps

4. Analyze any project- or technology dependent entities aside names and links and provide then in each `MIGRATION_REPORT.md`

This would be gate for the next design round or the first implementation round.

## Usage

The generator lives in `src/awesome_claude` and installs as the `awesome-claude` console script via `uv`.

```bash
# one-time setup - creates .venv and uv.lock
uv sync

# see every preset and what it contains
uv run awesome-claude list
uv run awesome-claude generate --preset python --name "Acme Sync" --package acme_sync --out .

# copy just a preset's docs/ scaffold, with {{PLACEHOLDER}} substitution applied
uv run awesome-claude docs copy --preset python --name "Acme Sync" --package acme_sync --out docs

# scaffold a new ADR into a preset's docs/
uv run awesome-claude docs new adr "Adopt structured logging" --preset python
```

`generate` also accepts `--config <file.json|file.toml>` (any flag passed alongside overrides the matching config value) and `--dry-run --json` for a machine-readable preview. `--out` is the project root that gets a `.claude/` and a `docs/` subdirectory (default: `.`); pass `--force` to overwrite existing content in either. Run `uv run awesome-claude generate --help` for the full flag reference.

### Development

Test suite and lint

```bash
uv run pytest --cov=awesome_claude
uv run ruff check src/ tests/
```

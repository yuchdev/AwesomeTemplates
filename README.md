The goal of the project is to create easily deplayable sets of Claude Code agents, skills, hooks, loops obtained from the set of templates with easily substituted values.

The idea is as follows:

Replace explicit project name and other project-specific values in files with template that is easily to misrepresent in Markdown, e.g. `{{PROJECT_NAME}}`, `{{PROJECT_PURPOSE}}` and so on.
After this step, with simple replace arfifacts can de added to another Python project.

```
templates/core
templates/helpers
templates/java
templates/orchestrators
templates/python
```

Each should contain

```
agents
hooks
loops
skills
```

3. Markdown files contain multiple documents links. Rather than introducing templates, create `MIGRATION_REPORT.md` per each entitiy with all document references. Perhaps will be introduced templates for documents, or special documents conventions accross projects, e.g. `docs/adr` and `docs/roadmap`. The following design will be the subject of further design steps

4. Analyze any project- or technology dependent entities aside names and links and provide then in each `MIGRATION_REPORT.md`

This would be gate for the next design round or the first implementation round.

## Usage

The generator lives in `src/awesome_claude` and installs as the `awesome-claude` console script via `uv`.

```bash
# one-time setup - creates .venv and uv.lock
uv sync

# see every preset/category/entity available
uv run awesome-claude list
uv run awesome-claude generate --preset python-minimal  --name "Acme Sync" --package acme_sync --out .claude

# copy the docs/ scaffold, with {{PLACEHOLDER}} substitution applied
uv run awesome-claude docs copy --name "Acme Sync" --package acme_sync --out docs

# scaffold a new ADR
uv run awesome-claude docs new adr "Adopt structured logging"
```

`generate` also accepts `--config <file.json|file.toml>` (any flag passed alongside overrides the matching config value), `--copy-docs`/`--check-requirements`, `--dry-run --json` for a machine-readable preview, and `--include type:name` / `--exclude type:name` to cherry-pick individual agents/hooks/loops/skills on top of a preset. Run `uv run awesome-claude generate --help` for the full flag reference.

### Development

Test suite and lint

```bash
uv run pytest --cov=awesome_claude
uv run ruff check src/ tests/
```

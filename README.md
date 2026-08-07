# Awesome Claude

The goal of the project is to create easily deplayable sets of Claude Code agents, skills, hooks, loops obtained from the set of templates with easily substituted values.

The idea is as follows:

Replace explicit project name and other project-specific values in files with template that is easily to misrepresent in Markdown, e.g. `{{PROJECT_NAME}}`, `{{PROJECT_PURPOSE}}` and so on.
After this step, with simple replace artifacts can be added to another Python project.

Each preset is a complete, self-contained tree, shaped exactly like what lands in the target project:

```
templates/python/.claude
templates/python/docs
templates/python/scripts
templates/java/.claude
templates/java/docs
templates/java/scripts
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
with `{{PLACEHOLDER}}` substitution applied to every text file. `.claude/`, `docs/`, and `scripts/`
always land together, from the same source tree, so agents and scripts cannot reference template
content that was not generated.

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
```

`generate` also accepts `--config <file.json|file.toml>` (any flag passed alongside overrides the matching config value) and `--dry-run --json` for a machine-readable preview. `--out` is the project root that gets `.claude/`, `docs/`, and `scripts/` subdirectories (default: `.`); pass `--force` to overwrite existing content in any of them. Run `uv run awesome-claude generate --help` for the full flag reference.

### Config file

[`awesome-claude.example.toml`](awesome-claude.example.toml) is a documented example of the file
`--config` accepts - copy it into your own project, edit the values, and run:

```bash
uv run awesome-claude generate --config awesome-claude.example.toml
```

JSON works the same way (picked by file extension); the schema is the same shape either way:

```json
{
  "preset": "python",
  "out": ".",
  "force": false,
  "project": {
    "name": "Acme Sync",
    "package": "acme_sync",
    "purpose": "Synchronizes Acme customer records nightly.",
    "slug_upper": "ACME_SYNC"
  }
}
```

| Field              | Substitutes            | Default if omitted                          |
|--------------------|-------------------------|----------------------------------------------|
| `preset`           | —                       | none - required (or pass `--preset`)         |
| `out`              | —                       | `.`                                          |
| `force`            | —                       | `false`                                      |
| `project.name`     | `{{PROJECT_NAME}}`      | none - required (or pass `--name`)           |
| `project.package`  | `{{PROJECT_PACKAGE}}`   | slugified `project.name`                     |
| `project.purpose`  | `{{PROJECT_PURPOSE}}`   | a `TODO: describe what this project does` placeholder |
| `project.slug_upper` | `{{PROJECT_SLUG_UPPER}}` | upper-slugified `project.name`             |
| `resolve_markers`  | —                       | `false` (or pass `--resolve-markers`)        |

Any CLI flag passed alongside `--config` overrides the matching value from the file.

### Resolving `TEMPLATE-INIT` markers with AI

`{{PLACEHOLDER}}` substitution fills the deterministic gaps. Some agent and loop files carry a second
kind: `<!-- TEMPLATE-INIT: <instruction> -->` markers describing a project-specific fact no find/replace
can supply. Pass `--resolve-markers` (or `resolve_markers = true` in the config) to have `generate`
resolve every such marker across the generated Markdown by calling Anthropic against the target
project's own code and docs — writing grounded prose, or a visible `> **TODO (fill in ...)**` blockquote
when it can't answer confidently.

This is opt-in: plain `generate` stays fully offline. It needs the optional `ai` extra and an API key:

```bash
uv pip install 'awesome-claude[ai]'      # pulls in the anthropic SDK
export ANTHROPIC_API_KEY=sk-ant-...       # or put it in a .env in the cwd
uv run awesome-claude generate --config awesome-claude.toml --resolve-markers
```

`--dry-run` reports how many markers *would* be resolved without calling the API.

### Development

Test suite and lint

```bash
uv run pytest --cov=awesome_claude
uv run ruff check src/ tests/
```

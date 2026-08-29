# 04 - Docs: root `CLAUDE.md` Commands section

**Parent task:** 04.0 `cli.py` wiring
**State:** ⬜ Not started
**Depends on:** 03
**Blocks:** none

## Objective

Document `--harness` in the repo root [`CLAUDE.md`](/CLAUDE.md)'s "Commands"
section, alongside the existing `generate` examples.

## Changes to `CLAUDE.md` (repo root)

Add one example line to the `Commands` fenced code block, after the existing
`--resolve-markers --seed-roadmap` line:

```bash
uv run awesome-templates generate . --preset python --name "Acme Sync" --resolve-markers --harness copilot
```

And a short note beneath the code block (matching the existing "Ruff config
note" callout's style) if `--harness`'s behavior needs more than the one-line
`--help` text already gives - e.g.:

> **`--harness` note:** defaults to `claude`; `copilot` and `junie` require
> `--resolve-markers` and that CLI installed/authenticated. There is no
> automatic fallback between harnesses - a missing `copilot`/`junie` binary is
> a hard failure naming that harness, not a silent substitution (see
> [docs/roadmap/0001-alternative-harness-support/plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)).

## Constraints

- Keep it to the example line plus a short callout - this file's own
  conventions favor dense reference over tutorial prose (see its "Ruff config
  note" for the expected length/tone).
- Run `/link-check` after editing.

## Success criteria

- [ ] `CLAUDE.md`'s Commands section shows a `--harness` example.
- [ ] `scripts/check_doc_links.py .` reports no new dangling links.

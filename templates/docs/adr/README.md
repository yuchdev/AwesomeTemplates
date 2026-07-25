# Architecture Decision Records

ADRs for {{PROJECT_NAME}} use the [MADR](https://adr.github.io/madr/) (Markdown Any Decision Records) template.
Each record lives in this directory as `000N-slug.md`. Mermaid diagrams referenced by ADRs
are in `assets/`.

## Inventory

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | 2025-01-01 |

## Template

Use `template.md` when creating a new ADR. The recommended invocation is:

```bash
uv run awesome-claude docs new adr "Short Title"
```

The `docs new adr` command scaffolds a MADR-formatted record pre-filled with context
and saves it here as the next `000N-slug.md`.

## Naming conventions

- Filename: `000N-kebab-slug.md` - sequential, zero-padded to four digits.
- Status values: `Proposed` | `Accepted` | `Implemented` | `Superseded` | `Deprecated`.
- Superseded ADRs keep their file; add a `Superseded by: [000N](...)` line to their header.

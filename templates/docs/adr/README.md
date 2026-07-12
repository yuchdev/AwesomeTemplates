# Architecture Decision Records

ADRs for {{PROJECT_NAME}} use the [MADR](https://adr.github.io/madr/) (Markdown Any Decision Records) template.
Each record lives in this directory as `000N-slug.md`. Mermaid diagrams referenced by ADRs
are in `assets/`.

## Inventory

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-new-ui-rich-based-design.md) | EXAMPLE - Live-updating terminal UI for CLI output | Implemented | 2026-01-12 |
| [0002](0002-agent-weight-as-property.md) | EXAMPLE - Configuration values are owned by the component that uses them | Accepted | 2026-07-08 |

## Template

Use `template.md` when creating a new ADR. The recommended invocation is:

```bash
/adr-write <short-title>
```

The `/adr-write` skill scaffolds a MADR-formatted record pre-filled with context
from recent git log and open GitHub issues, then saves it here as the next
`000N-slug.md`.

## Naming conventions

- Filename: `000N-kebab-slug.md` - sequential, zero-padded to four digits.
- Status values: `Proposed` | `Accepted` | `Implemented` | `Superseded` | `Deprecated`.
- Superseded ADRs keep their file; add a `Superseded by: [000N](...)` line to their header.

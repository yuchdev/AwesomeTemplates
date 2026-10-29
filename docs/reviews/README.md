# Reviews

Asynchronous review outputs from the `background-reviewer` agent: dependency
audits, secret scans, performance-regression findings, and license checks.

## Naming convention

`<type>-<scope>-<YYYY-MM-DD>.md` - e.g. `dep-audit-2025-09-01.md`,
`license-check-2025-10-15.md`.

## Contents

| Document                               | Description               |
|----------------------------------------|---------------------------|
| [example-report.md](example-report.md) | Example efficiency audit. |
| [model-migration-agents-2026-10-29.md](model-migration-agents-2026-10-29.md) | Preset agents moved to Opus 5.5 / Sonnet 5.5, with per-agent review findings. |

## What a review report must contain

1. **Scope** - what was reviewed (files, deps, date range).
2. **Findings** - each as `CRITICAL / HIGH / MEDIUM / LOW / INFO` with evidence.
3. **Verdict** - CRITICAL findings block merge until resolved.
4. **Recommended actions** - linked to GitHub issues where applicable.

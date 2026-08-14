---
name: django-migrations
description: User-invoked as /django-migrations [app]. Checks for model changes with no matching migration, reviews pending migrations for destructive operations, and generates missing migrations. Use before committing a model change or before a release that includes schema changes.
allowed-tools: Read, Grep, Glob, Bash
invocation: /django-migrations [app]
---

# Django Migrations Check

Verify the migration state for `$ARGUMENTS` (or every installed app if no argument is given), and
generate any migrations that are missing.

## Steps

1. Run `uv run python manage.py makemigrations --check --dry-run [app]`. A non-zero exit means at
   least one model has changed with no migration recorded for it - list which app(s).
2. If migrations are missing, run `uv run python manage.py makemigrations [app]` and read the
   generated operations. Confirm each one matches the intended model change - a stray
   `AlterField` on an unrelated column usually means a prior migration drifted from the model
   state and needs investigating before you add another on top of it.
3. Scan every migration that hasn't shipped yet (not in `git log` on the default branch) for
   destructive operations: `RemoveField`, `DeleteModel`, `AlterField` that drops a default or adds
   `null=False` to a column that may hold existing rows. Flag each one and ask whether a data
   backfill (`RunPython`) is needed before or alongside it, rather than assuming the migration is
   safe to run as-is against a populated table.
4. Run `uv run python manage.py migrate --check` against a throwaway/test database if one is
   configured, to confirm the full migration chain still applies cleanly end to end.
5. Delegate anything requiring a model/business-logic decision (should this field really be
   nullable? does this rename need a compatibility shim for in-flight requests?) to
   `django-expert` rather than deciding it here - this skill checks and generates, it doesn't
   design the schema.

## Output

Report: which app(s) had missing migrations, what was generated, which pending migrations (if
any) are destructive and need a backfill plan, and whether `migrate --check` passed.

## Completion checklist

- [ ] `makemigrations --check --dry-run` is clean for every app touched
- [ ] Every generated migration's operations were read and match the intended model change
- [ ] Destructive operations in pending migrations are flagged with a stated backfill plan (or
      explicitly confirmed safe, e.g. a brand-new table with no production rows yet)
- [ ] `migrate --check` passes

# 02 - `cli.py` flags + `--backend` removal

**Parent task:** 10.0 Credential flags + `--backend` removal
**State:** ✅ Complete
**Depends on:** 01 (this task); task 04.0's `sanity_check`/`generate`
**Blocks:** 03

## Objective

Delete `--backend` and `src/awesome_templates/backends.py` outright; add `--api-key`/
`--api-key-env` to `generate`, paired with `--harness` and validated in `sanity_check`; update
both `CLAUDE.md` files to match.

## File: `src/awesome_templates/backends.py` - deleted

Whole file removed. `mirror_of()`, `BACKEND_NAMES`, `Backend.implemented` and everything else
in it go with it - there is no replacement registry, since there is no second engine to
register.

## File: `src/awesome_templates/cli.py`

- `from awesome_templates import backends, docgen, harnesses` → drop `backends`.
- `BackendChoice` enum block deleted.
- `_engine_choices()` deleted (folded into `sanity_check`'s single `--harness` message).
- Two new `typer.Option`s on `generate`:
  - `api_key: Optional[str] = typer.Option(None, "--api-key", ...)` - no config-file fallback.
  - `api_key_env: Optional[str] = typer.Option(None, "--api-key-env", ...)` - config-file
    fallback via `cfg.get("api_key_env")`.
- `sanity_check(...)` signature drops `backend_value`, gains `api_key: Optional[str]` and
  `api_key_env: Optional[str]`. Rule set (in order, each may assume prior rules passed):
  1. Unknown `--harness` name (config-file bypass of the Typer enum) - unchanged from before,
     minus the backend half.
  2. `--seed-roadmap`/`--update-guidelines`/`--port-to` require `--resolve-markers` - unchanged.
  3. `--resolve-markers` requires `--harness`, and `--harness` has no effect without
     `--resolve-markers` - same two-way check as before, minus the backend half.
  4. `--api-key`/`--api-key-env` are mutually exclusive; either requires `--harness`; either
     against a harness whose `api_key_env` is `None` is rejected (`f"--harness {harness_value}
     authenticates via its own login only - {flag} doesn't apply to it"`).
  5. `--port-to` requires `--harness claude` - unchanged.
  6. Not-implemented last - unchanged, minus the backend branch.
- In `generate`'s body: resolve `api_key_env_value` (CLI, then config); after `sanity_check`
  passes, resolve the actual credential:

  ```python
  api_key_value = api_key
  if api_key_env_value:
      resolved = os.environ.get(api_key_env_value)
      if not resolved:
          _fail(f"--api-key-env {api_key_env_value} names a variable that isn't set")
          return
      api_key_value = resolved
  auth_label = "login"
  if api_key is not None:
      auth_label = "api-key"
  elif api_key_env_value:
      auth_label = f"api-key-env:{api_key_env_value}"
  ```

  `api_key_value` (never `auth_label`, which never carries the secret) is what reaches
  `headless.resolve_tree_headless(..., api_key=api_key_value, ...)` - replacing the old
  hardcoded `api_key=None`.
- Dry-run payload/console and the non-dry-run `summary` dict: `"backend"` key/line removed;
  `"auth": auth_label` added (JSON key and a console `Auth: ...` line, same shape
  `Specializations: ...` already has).
- The missing-binary hard failure drops its `mirror_of`-based `--backend <mirror>` suggestion -
  there is no alternative engine to name; the message is just "install it (or check its
  authentication)".
- The tutorial/roadmap-seed/test-conventions "skipped" warning drops its `--backend
  {mirror_of(...)}  once it is implemented` clause - there is no `--backend` to point at
  anymore; the message states plainly that these increments run no API calls of their own.

## Docs

- `src/awesome_templates/CLAUDE.md`: `backends.py` entry deleted; `harnesses.py` entry
  describes `api_key_env`; `headless.py` entry describes the generalized env construction;
  `cli.py` entry's gate-order description and default-engine paragraph rewritten for
  `--harness`-only + credential flags.
- Root `CLAUDE.md`: "AI-engine choice" paragraph rewritten (no `--backend`); new paragraph
  documenting `--api-key`/`--api-key-env` and the login-by-default rule; "No implicit API use"
  point 2 rewritten (no `--backend <mirror>` in the missing-binary message); a `--api-key-env`
  example line added to the Commands block.

## Constraints

- `--api-key` never has a config-file fallback (secret hygiene - see task README).
- The missing-binary and skipped-increments messages must not reference `--backend` in any
  form.
- `from __future__ import annotations`; `Optional[T]`, never `T | None`.

## Success criteria

- [x] `--backend` is not a recognized option (Typer/Click's own "no such option" exit 2).
- [x] `src/awesome_templates/backends.py` does not exist.
- [x] `--api-key`/`--api-key-env` exist, pair with `--harness`, are mutually exclusive, and are
      rejected against a harness with `api_key_env is None`.
- [x] `--api-key-env NAME` naming an unset variable fails with a clear message before any
      subprocess is invoked.
- [x] Dry-run JSON has no `"backend"` key and has `"auth"` in `{"login", "api-key",
      "api-key-env:<NAME>"}`.
- [x] `ruff check src/` clean.

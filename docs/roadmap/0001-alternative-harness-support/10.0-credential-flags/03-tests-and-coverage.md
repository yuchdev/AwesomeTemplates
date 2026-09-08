# 03 - Tests + coverage to ≥ 90%

**Parent task:** 10.0 Credential flags + `--backend` removal
**State:** ✅ Complete
**Depends on:** 01, 02
**Blocks:** -

## Objective

Bring the suite back to green against subtasks 01/02's field rename and flag changes, add
coverage for the new `--api-key`/`--api-key-env` behavior, and raise overall coverage to
**≥ 90%** - an explicit floor for this task only (see the task README for why this is an
exception to the repo's usual no-coverage-floor default). `uv run pytest --cov=awesome_templates`
last measured 87% at task 09.0's close (249 tests); deleting `tests/test_backends.py` (11 tests)
and `src/awesome_templates/backends.py` shifts both the numerator and denominator, so re-measure
from scratch rather than assuming the delta.

## Mechanical renames (no design judgment - do these first)

- `tests/test_headless.py`: the `dataclasses.replace(harnesses.get("claude"),
  forwards_anthropic_key=False)` construction and the `assert
  call["env"]["ANTHROPIC_API_KEY"] == ...` / `assert "ANTHROPIC_API_KEY" not in call["env"]`
  comment annotations referencing `forwards_anthropic_key` → `api_key_env=None` /
  `api_key_env` in prose. Behavior of every existing assertion is unchanged - only the field
  name in the construction and the explanatory comments.
- `tests/test_port.py`: same rename at the fake `Harness` construction and comment
  annotations.

## `tests/test_cli.py` - remove (dead: `--backend` no longer exists)

- `test_generate_rejects_backend_without_resolve_markers`
- `test_generate_rejects_harness_and_backend_together`
- `test_generate_rejects_every_backend_as_unimplemented`
- `test_generate_rejects_unknown_backend`
- `test_generate_rejects_unknown_backend_from_config_file`

And in the missing-binary test (`test_generate_hard_fails_when_claude_binary_is_missing` or
equivalent name), drop the `assert "--backend anthropic-api" in flat` line - the message no
longer suggests one.

`test_generate_never_forwards_an_api_key_into_the_harness_session` stays - its assertion
(`api_key=None` reaches `resolve_tree_headless` when neither credential flag is passed, even
with `ANTHROPIC_API_KEY` exported ambiently) is exactly the new default-to-login behavior.
Update its docstring/comment to say so explicitly (it now documents "the no-flags case", not
"cli.py never forwards a key" - it does, now, given an explicit flag).

## `tests/test_cli.py` - add

- `--api-key` with `--harness claude --resolve-markers` (fake `claude` on `PATH`, monkeypatch
  `headless.resolve_tree_headless`) forwards the literal value as `api_key` to
  `resolve_tree_headless`.
- `--api-key-env NAME` (with `NAME` set via `monkeypatch.setenv`) reads it and forwards its
  *value* (not the name) as `api_key`.
- `--api-key-env NAME` with `NAME` unset fails cleanly (exit 1, message names `NAME`) before
  any subprocess is invoked.
- `--api-key` and `--api-key-env` together is rejected (mutual exclusion).
- `--api-key` (or `--api-key-env`) without `--harness` is rejected.
- `--harness copilot --api-key x --resolve-markers` is rejected for "authenticates via its own
  login only" - and this fires *before* the "not implemented yet" notice (mirrors the existing
  ordering test for unimplemented harnesses without a credential flag).
- Dry-run JSON has no `"backend"` key in any of the three flag combinations (no flags / `--api-key`
  / `--api-key-env`) and has `"auth"` set to `"login"` / `"api-key"` / `"api-key-env:<NAME>"`
  respectively.
- `--backend anything` is rejected by Typer/Click itself (exit 2, "no such option") - one
  smoke test confirming the flag is fully gone, not merely disabled.

## Coverage pass

Once the above is green, run `uv run pytest --cov=awesome_templates --cov-report=term-missing`
and read the per-file "Missing" column for `cli.py`, `harnesses.py`, `headless.py`, `port.py`
specifically (the files this task touched) - the credential-flag branches (`sanity_check`'s
four new rules, the `api_key_env` resolution block, the `auth_label` three-way branch) are the
likeliest gaps given they're brand new code. Add targeted unit tests for any uncovered branch
found this way rather than padding coverage with redundant assertions on already-covered
lines. Stop once the total reaches ≥ 90% - this is a floor, not a target to maximize.

## Constraints

- No real `copilot`/`junie` binary invoked anywhere in the suite (unchanged repo convention).
- Every new/modified test still passes `ruff check tests/`.
- Do not weaken or delete an existing passing assertion to reach the coverage number - add
  tests, don't remove correctness checks.

## Success criteria

- [x] `tests/test_harnesses.py`, `tests/test_headless.py`, `tests/test_port.py` have no
      remaining `forwards_anthropic_key` reference.
- [x] `tests/test_backends.py` does not exist; no test anywhere references `backends`.
- [x] `tests/test_cli.py`'s backend-specific tests are gone; the new credential-flag tests
      listed above all pass.
- [x] `uv run pytest --cov=awesome_templates` - full suite green (282 passed), coverage
      exactly **90%** - confirmed independently twice (by the coordinating session and by
      `subtask-verifier`), not just the implementing agent's self-report.
- [x] `uv run ruff check src/ tests/` clean.
- [x] `/pr-review` reaches LGTM (or PASS_WITH_FOLLOWUP with no unresolved HIGH/CRITICAL) -
      APPROVE; see status.md's Task 10.0 section for the verdict.

**Delivered beyond the spec's original scope:** a `security-auditor` pass on the already-
written subtasks 01/02 code (run before this subtask began, since task 10.0 is
security-sensitive) found one LOW-severity follow-up - `headless.py`'s `ANTHROPIC_API_KEY`
strip should also generalize to `harness_obj.api_key_env` for defense against a hypothetical
future harness with a different key-env name - fixed as a small, spec-permitted src-side
addition alongside this subtask's test work.

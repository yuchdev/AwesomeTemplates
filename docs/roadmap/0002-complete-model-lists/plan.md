# Milestone 0002 - Complete Model Lists (supported, recommended, upgrade)

**Status:** not started. **Audience:** an implementing agent with no prior context. Read this whole
file before touching anything; every section is binding unless marked "guidance".

## Context

`models.json` (seeded from
[`models.template.json`](/src/awesome_templates/data/models.template.json), cached per user at
`~/.local/state/awesome/models.json`) is supposed to describe, per vendor, which models exist and
which ones the tool endorses. Today it does not:

| Section | anthropic | openai | google | copilot |
|---|---|---|---|---|
| `recommended` | 4 IDs | **empty** | **empty** | 2 display names |
| `upgrade.<vendor>` | full (tiers, families, targets, default) | **absent** | **absent** | tiers + default only |
| `live.<vendor>.served` (the supported list) | **absent** | **absent** | **absent** | n/a (no list API) |

Where the supported lists come from (already implemented, do not re-implement):

- [`model_catalog.py`](/src/awesome_templates/model_catalog.py) - the only module that calls vendor
  APIs: `_anthropic` (`GET https://api.anthropic.com/v1/models`, paginated by `after_id`),
  `_openai` (`GET https://api.openai.com/v1/models`), `_google`
  (`GET https://generativelanguage.googleapis.com/v1beta/models`, paginated by `pageToken`,
  `models/` prefix stripped). Registered in `FETCHERS`; entry point `fetch_supported`.
- [`model_state.py`](/src/awesome_templates/model_state.py) - `refresh` calls `fetch_supported` and
  stores `live.<vendor> = {fetched_at, served[]}`; skips a vendor whose cache is younger than
  `max_age`, or that has no key in its env var (`vendors.<v>.key_env`).
- `cli.py` `init` / `init --refresh` and `check-models --live` are the only callers.

Why `live` is empty today: `refresh` needs `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and
`GEMINI_API_KEY` in the environment and records a vendor as `no_key` otherwise. Also note the
model-ID strings in the template are maintainer-curated and may not match what the APIs return -
that mismatch is exactly what this milestone must detect.

## Objectives

1. **Supported lists.** Every one of `anthropic`, `openai`, `google` has a complete, current list of
   model IDs the vendor serves. Two layers, both required:
   - `live.<vendor>.served` - runtime cache, written only by `refresh` (unchanged semantics).
   - `supported.<vendor>` - NEW committed snapshot in the template (sorted, de-duplicated, with a
     per-vendor `snapshot_date`). It is the offline baseline that tests and `load_policy` use, because
     CI and tests must never need keys or a network. Copilot keeps its display-name list under
     `supported.copilot`, hand-curated from the docs page already cited in the template `notes`.
2. **Recommended lists.** `recommended.openai` and `recommended.google` are populated with current
   chat/coding-capable models, one per cost tier at minimum (`deep`, `standard`, `light`). Existing
   anthropic and copilot entries are re-validated, not rewritten without cause.
3. **Upgrade tables.** `upgrade.openai` and `upgrade.google` get `tiers`, `families`, `targets` and
   `default`, mirroring the shape of `upgrade.anthropic`. `upgrade.copilot` gains a `light` tier
   (or the spec documents why not). Every tier named in `roles` is defined for every vendor with an
   upgrade table, or the existing `_check_role_tiers` rejects the file.
4. **Subset invariant, enforced.** `upgrade targets ⊆ recommended ⊆ supported`, per vendor. The
   first inclusion already exists in `model_policy._parse_upgrade`; the second is new.
5. **Docs stay true.** `docs/model-upgrade-matrix.md` is regenerated and shows all four vendors.

## Constraints

Repository rules (from [CLAUDE.md](/CLAUDE.md); a violation fails review):

- `model_policy.py`, `model_state.py`, `model_catalog.py`: stdlib-only, never import `anthropic`,
  `from __future__ import annotations`, `Optional[T]` not `X | None`, module docstrings state purpose
  *and rationale*. No module-level state; thread parameters.
- The offline path stays offline: `generate` makes no network call and needs no keys. The new check
  must work from the committed template alone.
- No implicit API use: only `init` / `check-models --live` / `--live-models` tests may hit a vendor,
  with `fetch=` injectable. Keys travel only in headers and are never written to disk or logs.
- The maintainer edits `data/models.template.json` only; never hand-edit `live` and never commit
  anything from `~/.local/state/awesome/`.
- Do not invent model IDs. Every ID added must come from (a) a successful vendor Models API response
  or (b) the vendor's official documentation page, cited in the PR description with its URL and
  retrieval date. If neither is reachable for a vendor, stop and report instead of guessing.
- Do not remove or rename an ID already in `recommended` unless the vendor source shows it retired;
  list each removal explicitly in the PR description.
- Bump `revision` in the template whenever any policy table changes (it drives the stale-state
  note). Keep schema `1` unless adding `supported` forces a bump; if so, update `_read` and add a
  `--reseed` migration test.
- Conventional Commits, feature branch, never push to `master`. Tests/ruff per `ruff.toml`
  (line length 120).

Scope boundaries - do NOT:

- change `generate`, `headless.py`, `resolver.py`, or anything under `templates/` agents' pins
  unless a pinned ID turns out to be unsupported (then fix the pin and say so);
- add vendor SDK dependencies or a new HTTP client;
- add pricing, context-window, or capability metadata to `models.json`.

## Plan (suggested order; guidance)

1. **Establish ground truth.** Run `uv run awesome-templates init --refresh` with the three keys
   exported. If any key is missing, ask the user to supply it (`! export ...`) rather than
   proceeding on memory. Inspect `live.*.served`; note IDs that are aliases vs dated snapshots.
2. **Schema.** Add `supported` to the template; extend `ModelPolicy` with a
   `supported: Mapping[str, frozenset[str]]` field and parse it next to `_parse_recommended`.
3. **Fill data.** Populate `supported` from step 1 (filtering out non-chat models such as
   embeddings, TTS, image, moderation - state the filter rule in the template `notes`), then
   `recommended`, `upgrade.*`, `roles` tiers. Update `notes` and `revision`.
4. **Enforce.** In `load_policy`, raise `ModelPolicyError` for any `recommended` ID missing from
   that vendor's `supported` (message names vendor, ID and the nearest supported ID if one exists).
   `copilot` is checked against its curated `supported.copilot`. A vendor with an empty
   `recommended` and empty `supported` stays legal only for vendors the policy does not use.
5. **Live cross-check.** Extend `model_catalog.verify` (and `check-models --live`) so that, when a
   live cache exists, `supported ⊆ live.served` drift is reported as a warning ("snapshot lists X,
   vendor no longer serves it"). This is advisory; the hard failure remains offline.
6. **Matrix doc.** `uv run awesome-templates model-matrix --write`, then `--check`.
7. **Tests** (below), then the full suite and ruff.

## Success criteria (all must be demonstrably true)

Data:

- [ ] `supported.anthropic`, `.openai`, `.google` each non-empty, sorted, unique; each has
      `snapshot_date` within 7 days of the PR date.
- [ ] `recommended.{anthropic,openai,google}` each cover tiers `deep`, `standard`, `light`;
      `upgrade.{anthropic,openai,google}` define all three tiers plus `default`.
- [ ] For every vendor: `upgrade targets ⊆ recommended ⊆ supported` (checked by code, not by eye).
- [ ] Every ID added is traceable to an API response or cited doc URL in the PR description.

Behaviour:

- [ ] `load_policy` fails with `ModelPolicyError` when a recommended ID is absent from `supported`;
      the message names the vendor and ID.
- [ ] `uv run awesome-templates check-models` and `generate --preset python` / `--preset java`
      still pass with `mode = error` against the real template.
- [ ] `uv run awesome-templates upgrade <fixture project>` selects a correct target for an
      outdated pin of each of the 3 vendors (role x vendor).
- [ ] `check-models --live` with a fake `fetch=` flags a `supported` ID the vendor stopped serving.

Tests (new unless noted; all offline, use `fetch=` fakes and `tmp_path`):

- [ ] Unit: recommended-not-in-supported rejected; upgrade-target-not-in-recommended still
      rejected (existing); empty-recommended vendor tolerated only when unused.
- [ ] Unit: `supported` parsing rejects non-list, non-string, duplicates, unsorted input.
- [ ] Integration (real template): subset chain holds for all vendors; every `roles` tier exists
      for every vendor with an upgrade table; every agent pin under `templates/` is in `supported`.
- [ ] Drift: `model-matrix --check` passes (existing test) and the doc lists 4 vendors.
- [ ] `uv run pytest` green; `uv run ruff check src/ tests/` clean; coverage delta reported
      (no floor).
- [ ] Pinned import tests still pass (`anthropic` not imported by the three model modules).
- [ ] Opt-in `uv run pytest --live-models` run once with real keys and its output pasted into
      the PR; it is not part of the default suite.

Process:

- [ ] `status.md` created beside this file recording per-task state, in the format used by
      [0001-alternative-harness-support/status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
- [ ] Final report lists: IDs added/removed per section, sources used, commands run with pass/fail,
      and anything skipped or uncertain. Do not claim a check passed unless it was run.

## Stop and ask the user when

- a vendor key is unavailable or the Models API returns an unexpected shape;
- the API list and the docs disagree about whether a model is current;
- the `supported` design above would force a schema bump that breaks existing state files;
- a template agent's pin is not supported and the right replacement is not obvious.

## Verification commands

```bash
uv run awesome-templates init --refresh
uv run awesome-templates check-models --json
uv run awesome-templates check-models --live
uv run awesome-templates model-matrix --check
uv run pytest --cov=awesome_templates
uv run pytest tests/test_integration_real_repo.py
uv run ruff check src/ tests/
```

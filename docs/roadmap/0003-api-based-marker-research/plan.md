# Milestone 0002 - API-Based Agentic Marker Research

**Status:** deferred - not started, not scheduled. Captured here so the design isn't lost,
not because work is expected to begin soon.

## Why this milestone exists

[`0001-ai-assisted-generation/01.0-working-implementation/03-agentic-marker-research.md`](/docs/roadmap/0001-ai-assisted-generation/01.0-working-implementation/03-agentic-marker-research.md)
diagnoses why `generate --resolve-markers` produces instruction-echo instead of grounded
facts on well-documented targets: `resolve_one` is a single Messages API call with only a
static context bundle, so it genuinely cannot research the target project the way a marker
like "name the concrete modules to watch" requires.

That document's *first* draft proposed fixing this with a hand-rolled research harness: a
bespoke Messages-API tool-use loop producing a structured "fact sheet," consumed by a
cheaper one-shot pass per marker. The shipped direction instead reuses the `claude` CLI as a
subprocess (see 0001's task 03, "Proposed architecture"), on the reasoning that Claude Code
already provides real `Read`/`Grep`/`Glob` research via `create-from-template.md` and
there's little value in reinventing that harness in-house.

This milestone preserves the in-house alternative as a real, buildable design - worth
revisiting if the `claude`-CLI dependency the chosen approach assumes (installed, licensed,
authenticated on the machine running `generate`) turns out to be unacceptable for some
deployment of `awesome-templates` (e.g. a CI environment that can install a Python package
via the `ai` extra but cannot install a Node-based CLI, or a policy that forbids it).

## Proposed architecture: research once, resolve many

Split resolution into two phases with a durable artifact between them.

```
                 Phase A (agentic, expensive, once per target)
  target repo ──> ProjectResearcher ──> fact-sheet.json (evidence-linked)
                       │  read_file / grep / glob tool loop,
                       │  sandboxed to target root, budgeted
                       ▼
                 Phase B (one-shot, cheap, once per marker)
  fact-sheet.json + marker ──> resolve_one ──> grounded prose spliced in place
```

### Phase A - `ai/researcher.py`: an agentic research pass

One agentic conversation per target project, using the Messages API **tool-use loop** with
three read-only local tools, all path-jailed to the target root:

| Tool        | Contract                                                              |
|-------------|-----------------------------------------------------------------------|
| `read_file` | `{path, max_chars?}` -> file head; rejects paths outside target root  |
| `grep`      | `{pattern, glob?}` -> matching lines with `path:line` prefixes        |
| `list_tree` | `{subdir?, depth?}` -> directory listing                              |

The loop is budgeted (e.g. max 40 tool calls / 200k input tokens) and seeded with the same
`gather_context` bundle so the model starts oriented and spends its tool budget on the gaps:
opening entry points, tracing what data crosses trust boundaries, finding the large-payload
code paths.

Its final answer is a **Project Fact Sheet** - structured JSON validated against a schema
whose fields are exactly the union of what the current markers ask:

```jsonc
{
  "subsystems":        [{ "name", "role", "relates_to", "evidence": ["path", ...] }],
  "data_schemas":      [{ "name", "module", "role", "key_fields", "evidence" }],
  "entry_points":      [{ "kind": "cli|api|gui|worker", "module", "evidence" }],
  "backend_families":  [{ "family", "abc", "implementations", "factory", "evidence" }],
  "hot_paths":         [{ "module", "why_hot", "evidence" }],
  "untrusted_inputs":  [{ "category", "ingestion_point", "evidence" }],
  "sensitive_data":    [{ "category", "where_handled", "evidence" }],
  "business_invariants": [{ "invariant", "highest_cost_defect", "evidence" }],
  "quality_gates":     [{ "gate", "source", "evidence" }],       // coverage bars, CI gates
  "design_doc_locations": [{ "kind": "adr|spec|divergence-log", "path" }],
  "maturity": "skeletal | partial | mature",
  "notes": "anything observed that fits no field"
}
```

Every entry carries `evidence` (file paths actually read/grepped), which is what makes
Phase B *confident by construction*: prose is written from facts the researcher verified,
not from what a summary happened to mention.

The sheet is cached at `<out>/.awesome-templates/fact-sheet.json` (git-ignorable). Reruns of
`--resolve-markers` reuse it unless `--re-research` is passed; the existing tutorial, roadmap
seeding, and test-conventions generators switch to consuming it too, so the whole AI pass
reads the project once instead of four times from four different thin bundles.

### Phase B - per-marker resolution from the fact sheet

`resolve_one` keeps its current shape (system + user + JSON schema, one call per marker) but
its context becomes the fact sheet instead of the raw bundle. Consequences:

- **Consistency**: every marker across every file is answered from the same verified facts -
  no more one agent file naming a subsystem another file contradicts.
- **Cost**: the expensive agentic loop runs once; per-marker calls stay one-shot and can drop
  to a cheaper model (Sonnet-class), since the hard cognition already happened in Phase A.
- **Confidence semantics become mechanical**: `confident=false` is only legal when the
  relevant fact-sheet field is empty *and* `maturity != "mature"`. On a mature target an
  empty field means Phase A should be re-run with a bigger budget, not that a TODO should
  be printed.

### Quality gate on the output (belt and braces)

Before splicing, `resolve_tree` rejects (and retries once, then TODOs) any prose that:

- shares > ~60% of its token trigrams with the marker instruction (instruction-echo detector), or
- contains zero backtick-quoted identifiers when the instruction asks to "name" modules,
  files, or categories.

This turns the reported failure mode from "shipped silently" into "impossible to ship".

Additionally, the low-confidence `render()` fallback should lead with the model's partial
prose and demote the instruction restatement to a one-line tail
(`> _Original template instruction: ..._`), so even the worst case reads as a draft, not an
echo. (Format change - update `tests/test_resolver.py` render expectations alongside.)

## Implementation options considered

| Option | What | Verdict |
|--------|------|---------|
| **In-house tool loop (this milestone)** | Add `request_agentic()` to `ai/client.py`: a plain Messages API `tools=[...]` loop dispatching to three ~20-line local functions in `ai/researcher.py`. | Fits the existing architecture exactly: `ai/client.py` stays the only `anthropic` importer, unit-testable with the same fake-client pattern `resolve_tree` already uses, no new dependency beyond the `ai` extra + `ANTHROPIC_API_KEY` the feature already documents. Deferred, not rejected - see "Why this milestone exists" above. |
| `claude-agent-sdk` | Drive a headless Claude Code session via a Python SDK instead of raw subprocess text I/O. | A cleaner implementation of the *chosen* (0001/03) direction, not a competitor to this one - shares that direction's `claude`-install dependency. Not this milestone's concern. |
| Shell out to `claude -p` running `create-from-template` | Reuse the interactive agent non-interactively. | This is what 0001's task 03 adopted instead of this milestone - see that document. |

## Tasks

| Task | Name | Category | Output |
|------|------|----------|--------|
| 01 | `ai/researcher.py` + `request_agentic()` | feature | Tool-use loop (`read_file`/`grep`/`list_tree`), fact-sheet schema + `<out>/.awesome-templates/fact-sheet.json` cache, unit tests with a scripted fake client |
| 02 | Rewire `resolve_one`/`resolve_tree` onto the fact sheet | feature | `--re-research` flag; confidence semantics per "Phase B" above |
| 03 | Echo-detector + identifier check | feature | Reject/retry-once/TODO gate in `resolve_tree`; softened `render()` fallback (`tests/test_resolver.py` updated) |
| 04 | Point the other AI increments at the fact sheet | refactor | `generate_tutorial`, `propose_first_milestone`, `maybe_describe_test_conventions` consume the sheet; bespoke bundles retired |
| 05 | Fixture-repo integration test | test | Full pass against a documentation-rich fixture; asserts the three originally-failing markers resolve with concrete module paths and zero instruction-echo |

See [status.md](status.md) for progress (all tasks Not started - this milestone has not
begun).

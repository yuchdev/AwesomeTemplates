# Hallucination Mitigation - Docs

**Status:** proposal - not implemented. See [hallucination-mitigation.md](hallucination-mitigation.md)
for the shared taxonomy, the three-tier gate architecture, and the statistics schema this
document instantiates for the `docs` domain.

## Current state

Three mechanisms already exist that are, structurally, doc-hallucination mitigations, even
though none was built under that name:

- **`docgen.py`** sidesteps the problem entirely for `docs/agent/{agents,skills,hooks}.md`:
  those files are regenerated from real frontmatter and `settings.json` on every `generate`
  (its own module docstring: "turning that into ... is a glob and a render, not a research
  task"), so they cannot hallucinate - there is no generative step to hallucinate *in*. This
  is the strongest possible mitigation and the reason this proposal has nothing to add for
  those three files specifically.
- **`markers.py` + `resolver.py`** already implement the three-tier gate from the overview
  document for `--resolve-markers` output: a `TEMPLATE-INIT` marker resolves confidently or
  falls back to a visible TODO; a `SME REVIEW NEEDED` marker is *never* silently resolved
  regardless of the model's confidence score (`resolver.py` module docstring, and the
  invariant repeated verbatim in `CLAUDE.md`, "Invariants a change must not break").
- **`check_doc_links.py` / `.claude/hooks/doc_link_check.py` / `doc_registry.py`** already
  catch one specific fabricated-reference shape - a Markdown link or `#anchor` that does not
  resolve - both inline (fast, non-blocking hook, `doc_link_check.py`'s module docstring:
  "Always **non-blocking**") and on demand (`/link-check` skill, thorough scan).

What is missing is coverage for claims that are *true-shaped but not link-shaped* - prose
that asserts a fact about a target project without a checkable reference at all - and a
generalization of the marker-resolution gate's already-designed but not-yet-built next step.

## The motivating example already on record

`docs/roadmap/0001-ai-assisted-generation/01.0-working-implementation/03-agentic-marker-research.md#root-cause`
documents the exact failure this proposal targets, from real experience with this repo's own
feature: a single stateless API call resolving a `TEMPLATE-INIT` marker "produced
instruction-echo instead of facts" - the model, given only a static context bundle and no
real research capability, restated the marker's instruction back as if it were an answer.
The shipped fix (`headless.py`, a full headless Claude Code session with real `Read`/`Grep`/
`Glob` access) addresses the *research* half of the problem. The *verification* half -
confirming the resulting prose actually reflects what was researched, rather than trusting
the model's output at face value - is exactly what
`docs/roadmap/0003-api-based-marker-research/plan.md#quality-gate-on-the-output-belt-and-braces`
designs and defers:

> Before splicing, `resolve_tree` rejects (and retries once, then TODOs) any prose that
> shares > ~60% of its token trigrams with the marker instruction (instruction-echo
> detector), or contains zero backtick-quoted identifiers when the instruction asks to
> "name" modules, files, or categories.

This proposal's core recommendation for the docs domain is: **build that gate now**, as a
standalone, independently mergeable piece, rather than only as part of milestone 0003's
larger (and explicitly deferred) fact-sheet architecture. The echo-detector and
identifier-check functions do not depend on anything else in 0003's plan - they are pure
string functions over `(instruction, resolved_prose)` - so they can land against the
*current* single-call `resolver.resolve_one` path immediately, independent of whether the
larger headless-vs-in-house research architecture question is ever revisited.

## Proposed extensions

### 1. Ship the designed-but-deferred quality gate now

Implement the two checks from `plan.md` above as functions in `resolver.py`, called from
`resolve_tree` before `render()` ever writes a confident resolution:

```python
def _is_instruction_echo(instruction: str, prose: str, threshold: float = 0.6) -> bool:
    """True when `prose` shares more than `threshold` of its token trigrams with
    `instruction` - the resolved text is restating the question, not answering it."""

def _lacks_named_identifiers(instruction: str, prose: str) -> bool:
    """True when `instruction` asks to "name" concrete modules/files/categories but
    `prose` contains zero backtick-quoted spans - a confident-sounding non-answer."""
```

A marker whose resolution fails either check is retried once (a second, independent sample -
cheap insurance against a single unlucky generation) and, on a second failure, downgraded to
the existing low-confidence TODO path rather than spliced in as if confident. This changes no
public behavior for markers that already resolve well; it only catches the failure mode
already observed and documented.

### 2. A citation-format + anchor-existence linter

`CLAUDE.md`'s own "Design documents" section mandates a specific citation discipline: "Cite
these as `path#heading-slug`, never the file alone." That convention is currently
unenforced - nothing stops an AI-authored (or human-authored) doc from citing a bare file
path, or a `#heading-slug` that does not match any real heading. Extend `doc_registry.py`
(already the tool that "maps the corpus," per its own module docstring) with a check that:

- flags a citation to a multi-section document (anything under `docs/roadmap/`, `docs/adr/`
  in a distributed preset, or this repo's own `docs/security/`, `docs/reviews/`) that omits
  a `#heading-slug`, and
- verifies a present `#heading-slug` resolves against the target file's actual headings,
  using the *exact same* slugify logic `check_doc_links.py` already uses for anchors -
  reusing the existing anchor-matching code path here matters, since `CLAUDE.md` already
  flags what happens when two independent slugify implementations drift
  ("`_common.slugify` and `check_doc_links.slugify` **must stay behaviourally identical**").
  A new, third slugify implementation for citation-checking would recreate exactly the bug
  class that warning exists to prevent - this check must call the existing function, not
  reimplement it.

This directly catches a fabricated-reference hallucination shape distinct from a broken
Markdown link: a citation can be syntactically well-formed and still name a heading that was
never written, e.g. a model citing "the Quality gate section" with a slug it guessed rather
than one it read.

### 3. A "claims need citations" heuristic linter

Weaker than the above (heuristic, advisory-only, never blocking) but broader: scan
AI-authored prose for declarative sentences that assert something about "the codebase," "this
module," or a named file/function, and flag any such sentence with **zero** backtick-quoted
identifiers or citations nearby. This is the same shape as the code domain's instruction-echo-
in-comments check (see the code subarticle) and is deliberately scoped as advisory rather
than a blocking rule, since natural prose legitimately summarizes without a citation on every
sentence - the goal is surfacing candidates for the fact-check pass below to spend its
(more expensive) attention on, not rejecting output outright.

## Fact-checking docs with an agentic pass

The checks above are all syntactic - they verify a claim *looks* well-formed and its
references resolve. None of them verify the claim is *true*. That requires the same
adversarial-refutation pattern proposed for code, applied to doc prose specifically:

- For each AI-authored doc increment (`generate_tutorial`, `propose_first_milestone`,
  `maybe_describe_test_conventions` in `resolver.py`; a `--update-guidelines` edit to
  `CLAUDE.md`; a resolved `TEMPLATE-INIT` marker), extract the concrete, checkable claims -
  "module X owns Y," "the test suite covers Z," "run this command to do W."
- Spawn one or more independent fact-check passes, each re-deriving the claim from the
  *actual* target project by grep/read rather than from the model's own prior context - the
  same "research it yourself, don't trust the summary" principle `headless.py` already
  applies to marker research, turned inward on the *output* instead of the *input*.
- A claim confirmed by re-derivation ships. A claim refuted, or one the fact-checker cannot
  independently confirm, is downgraded - concretely, spliced with the same
  `SME REVIEW NEEDED`-style blockquote treatment `resolver.render` already uses for
  low-confidence and human-review content (`resolver.py:248`, `> **SME REVIEW NEEDED
  (AI-drafted - verify before relying on this):**`), reusing the exact rendering path rather
  than inventing a second "unverified" presentation.

Where to run this pass, in order of increasing scope:

1. **As a `resolve_tree`/`resolve_tree_headless` post-pass**, immediately after markers are
   resolved and before the summary is reported - catches the narrowest, highest-value case
   (this project's own generated output) first.
2. **As a `/doc-fact-check` skill**, invokable standalone the way `/link-check` already is,
   for auditing existing docs (this repo's own `docs/`, or a previously generated target
   project) independent of a fresh `--resolve-markers` run.
3. **Folded into `/pr-review`** as a fourth leg (alongside `feature-reviewer`,
   `security-auditor`, and the code-domain fact-check leg from the other subarticle) whenever
   a PR's diff touches `docs/` or a template's Markdown.

## Statistics collection

Extend `ResolveSummary` (`resolver.py:128`, currently `resolved` / `todos` / `human_review` /
`files_touched` / `failed`) with two new counters that the gate above naturally produces:
`echo_rejected` (caught by the instruction-echo/identifier check before ever reaching
`render()`) and `fact_check_failed` (caught by the agentic pass after a confident-looking
resolution). Persist the summary as a JSON file per run - not only the printed one-line
report `resolve_tree` currently emits - at a fixed, predictable location (e.g.
`<out_dir>/.awesome-templates/resolve-summary-<run-id>.json`, alongside the fact-sheet cache
path milestone 0003 already reserves for a similar purpose). Feed that into the shared JSONL
schema (`domain: "docs"`) from the overview document, and aggregate the same way the code
domain does, into the same dated `docs/reviews/hallucination-stats-<YYYY-MM-DD>.md` report -
one report, both domains' sections, so a reader sees the whole picture in one place even
though the two producers are independent.

Tracking these rates over time answers a question this repo cannot currently answer at all:
whether `--resolve-markers` output quality is improving or regressing as the underlying model
changes, and whether the headless-research architecture (`headless.py`) actually reduced the
instruction-echo rate the way `0001`'s task 03 predicted it would, or only moved the failure
mode somewhere harder to see.

## Preventing delivery

The concrete, mergeable-independently change this document recommends first: land the
instruction-echo + identifier-check gate (section 1 above) as a small, self-contained patch
to `resolver.py`, gated behind nothing - it strictly improves the existing low-confidence
fallback path and changes output for zero currently-well-resolved markers. Everything else in
this document (citation linter, fact-check pass, statistics aggregation) can follow
incrementally once that gate is in place and generating real pass/fail data to calibrate
against, per the phased rollout in the overview document.

A concrete invariant this proposal would add to `CLAUDE.md`'s "Invariants a change must not
break" section, for the maintainer to accept or reject rather than adopted here: **no
AI-resolved marker or AI-authored doc increment ships a confident factual claim without
either passing the instruction-echo/identifier gate or being flagged for human review** - a
direct generalization of the existing "`SME REVIEW NEEDED` is never silently resolved"
invariant to cover `TEMPLATE-INIT` output too, closing the gap between what the two marker
kinds currently guarantee.

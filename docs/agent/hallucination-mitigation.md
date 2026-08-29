# Hallucination Mitigation - Overview

**Status:** proposal - not implemented. No code in this repository has been changed to
support anything described below; this is a design document to be picked up as a
`docs/roadmap/` milestone if the maintainer agrees with the direction.

## Scope

This proposal is about one problem, seen in two places this repo already treats as
distinct (see `CLAUDE.md`, "Three things that are easy to confuse"):

1. **Code hallucination** - an AI-authored change to `src/awesome_templates/` (or to a
   consumer project's code, when the `python-expert`-equivalent agent is doing the writing)
   that looks plausible but asserts something false: a call to a function that does not
   exist, a docstring that describes behavior the body does not implement, a comment that
   restates the prompt instead of explaining the code.
2. **Docs hallucination** - AI-authored prose in `docs/`, in a generated target project's
   `.claude/` kit, or in a `--resolve-markers` fill-in, that states a fact about a codebase
   which is not true: a fabricated module path, an invented CLI flag, a confidently wrong
   description of what a target project's test suite covers.

Both are the same underlying failure - a probabilistic process asserting something as fact
without grounding - so this proposal shares one taxonomy and one architecture across both,
then splits into two subarticles because the concrete mechanics (an AST-based flake8 rule
vs. a Markdown citation checker) are genuinely different tools:

- [hallucination-mitigation-code.md](hallucination-mitigation-code.md) - static analysis
  (built on the existing `flake8_project_rules` plugin), code-specific statistics, and
  code-specific delivery gates.
- [hallucination-mitigation-docs.md](hallucination-mitigation-docs.md) - doc-link/citation
  analysis, fact-checking against the actual target project, and the marker-resolution
  pipeline's own gates.

This repo is unusually well-positioned for this proposal: it already ships a working
example of most of the individual mechanisms (a confidence/TODO fallback, a diff-based
reconciliation instead of trusting a model's self-report, a designed-but-deferred
instruction-echo detector). What is missing is not the primitives but (a) a place that
*counts* how often each mitigation actually fires, and (b) generalizing a couple of these
mechanisms beyond the one narrow place they were each built for.

## Why "hallucination" needs a narrower definition here

"Hallucination" is used loosely elsewhere to mean anything a model gets wrong. For this
proposal to produce checkable rules rather than vibes, it is scoped to **verifiable-false
claims** - a specific, falsifiable subclass:

| Class | Definition | Falsifiable how |
|-------|------------|------------------|
| Fabricated reference | Names a file, module, symbol, CLI flag, or config key that does not exist. | Grep/`Path.exists`/`ast` lookup against the actual tree. |
| Contract mismatch | A docstring/comment claims a behavior (return type, raised exception, parameter) the code does not have. | AST comparison of the claim against the signature/body. |
| Instruction echo | Output restates the prompt/instruction instead of producing new, grounded content - the shape already diagnosed in `docs/roadmap/0001-ai-assisted-generation/01.0-working-implementation/03-agentic-marker-research.md#root-cause`. | Trigram overlap with the instruction text. |
| Unsupported factual assertion | A confident statement about a *target project's* code, dependencies, or test coverage, made without a corresponding grep/read of that project surfacing supporting evidence. | Re-derive the claim independently and compare. |

Excluded deliberately: style preferences, subjective code-quality judgments, and plain bugs
that are not *false claims* (an off-by-one error is a bug, not a hallucination, unless a
comment asserts the loop is correct). Keeping the definition this narrow is what makes
"collect statistics" mean something other than "count every lint warning."

## Shared architecture

Both subarticles instantiate the same two-part architecture. Sections below define it once;
each subarticle applies it to its own artifact type.

### 1. A three-tier gate, not a single check

A single boolean "safe/unsafe" gate can't express what this repo already does with
`SME REVIEW NEEDED` markers (`markers.py`) - some content should never auto-ship even when a
deterministic check passes, because the check can't verify the class of claim involved. The
proposed gate keeps three tiers, matching the existing marker-resolution vocabulary
(`resolver.py`'s module docstring, "the confidence/TODO fallback"):

```
                 ┌─────────────────────┐
 AI output  ───▶ │ deterministic checks│──fail──▶  reject / TODO
                 └─────────┬───────────┘
                       pass│
                           ▼
                 ┌─────────────────────┐
                 │ agentic fact-check  │──fail──▶  human-review flag (never silent)
                 └─────────┬───────────┘
                       pass│
                           ▼
                       ship as-is
```

- **Deterministic checks** are cheap, run on every output, and catch the classes that are
  mechanically checkable (fabricated reference, contract mismatch, instruction echo). This
  is the tier the flake8 plugin and doc-link checker already occupy.
- **Agentic fact-check** is a second model pass, prompted adversarially ("try to find a
  claim in this text that the codebase does not support"), for the class deterministic
  checks structurally cannot reach - "unsupported factual assertion" about a target
  project's semantics, not just its file layout.
- **Human-review flag** is not a failure state to eliminate - `SME REVIEW NEEDED` markers
  already prove this repo accepts "flag for a human" as a legitimate terminal outcome
  (`resolver.py` module docstring: "a `SME REVIEW NEEDED` marker is never resolved
  ... regardless of the model's own confidence score"). The goal of this proposal is
  *shrinking* how often content reaches this tier by catching more upstream, not removing
  the tier.

This is a generalization of a pattern that already exists in one place:
`docs/roadmap/0003-api-based-marker-research/plan.md#quality-gate-on-the-output-belt-and-braces`
proposes exactly this shape (an echo detector plus an identifier-presence check, gating
`resolve_tree`) but scoped only to marker resolution. Both subarticles propose extending the
same shape to a wider surface: product code review and non-marker doc generation.

### 2. Durable, comparable statistics - not just pass/fail

`ResolveSummary` (`resolver.py:128`) already counts `resolved` / `todos` / `human_review` /
`failed` per run, but the count is only ever printed once and discarded - there is no file
anywhere that remembers last month's rate to compare against this month's. The proposal in
both subarticles is the same shape:

1. Every gate emits one structured record per checked artifact (file, or marker, or PR),
   append-only, JSON Lines, tagged with the hallucination class from the taxonomy above,
   the tier that caught it (deterministic / agentic / neither - shipped clean), and enough
   identifying context (file path, rule code, model id if known) to investigate later.
2. A periodic aggregation step turns the JSONL log into a dated Markdown report, following
   this repo's existing convention for durable, non-blocking output
   (`docs/reviews/README.md#naming-convention`: `<type>-<scope>-<YYYY-MM-DD>.md`) - concretely
   `docs/reviews/hallucination-stats-<YYYY-MM-DD>.md`, generated by the `background-reviewer`
   agent the same way a dependency audit already is.
3. The report tracks *rates*, not raw counts, so it stays meaningful as volume changes:
   fabricated-reference rate per 100 AI-authored files, echo rate per marker batch,
   fact-check disagreement rate per `--resolve-markers` run - each trended against the prior
   report so a regression after a model version bump is visible instead of anecdotal.

Concretely, one JSONL schema serves both subarticles (fields not applicable to a given
finding are simply omitted, not null-padded):

```jsonc
{
  "ts": "2026-08-29T00:00:00Z",
  "artifact": "src/awesome_templates/resolver.py",   // or a marker id, or a PR number
  "domain": "code",                                   // "code" | "docs"
  "class": "contract_mismatch",                        // taxonomy class from above
  "tier": "deterministic",                             // "deterministic" | "agentic" | "clean"
  "rule": "X013",                                       // rule code or check name
  "outcome": "rejected",                                // "rejected" | "todo" | "human_review" | "shipped"
  "model": "claude-sonnet-5"                            // omitted when not model-attributable
}
```

## Rollout

Both subarticles propose concrete, incremental steps rather than one big-bang change,
consistent with this repo having no CI gate to lean on (`CLAUDE.md`: "There is no `.github/`
and no CI"). Suggested order, cheapest and least risky first:

1. Add the new deterministic rules (flake8 rule codes, doc-link/citation checks) - these are
   pure functions, unit-testable the same way `X001`-`X012` already are, and ship with zero
   behavior change to anything that already passes.
2. Wire statistics emission into the existing hooks/skills that already run these checks, so
   the JSONL log starts accumulating real data before any gate becomes blocking.
3. Only after real baseline data exists, turn the highest-confidence deterministic checks
   from advisory to blocking (mirroring how `secret_scan.py` already blocks on a PreToolUse
   hook, `.claude/hooks/secret_scan.py`), and add the agentic fact-check as an additional
   `/pr-review` leg or `--resolve-markers` post-pass.
4. Start the periodic aggregation report once tier-1 and tier-2 are both emitting data, so
   the first report is meaningful rather than a single day's noise.

## Non-goals

- This does not propose detecting *every* way an LLM can be wrong - only the falsifiable
  subclass defined above. General code review for logic bugs remains `feature-reviewer`'s
  job; this proposal is additive to it, not a replacement.
- This does not propose adding CI. The repo has none by design (no `.github/`); every gate
  described here is either a Claude Code hook (already the enforcement mechanism for
  `secret_scan.py` and `doc_link_check.py`) or a skill invoked on demand.
- This does not propose editing `CLAUDE.md`'s own Invariants section. Two places below
  suggest a new invariant would make sense (a code-gate invariant and a docs-gate
  invariant); both are called out explicitly as suggestions for the maintainer to accept or
  reject, not changes this document makes unilaterally.

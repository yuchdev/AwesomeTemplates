# Hallucination Mitigation - Code

**Status:** proposal - not implemented. See [hallucination-mitigation.md](hallucination-mitigation.md)
for the shared taxonomy, the three-tier gate architecture, and the statistics schema this
document instantiates for the `code` domain.

## Current state: `flake8_project_rules`

`src/flake8_project_rules/` (`rules.py`, `plugin.py`) is a standalone flake8 AST plugin,
unrelated to the generator pipeline, implementing project-specific rules `X001`-`X012`. It
is the right foundation for deterministic code-hallucination checks for three reasons
already true of it today:

- It is **pure and unit-testable**: `check_tree(tree, filename, source)` takes an already-parsed
  AST and yields `RuleViolation` dataclasses - no I/O, no flake8 runtime needed to test a rule
  in isolation (`tests/flake8_lint/`).
- It already has **per-line `# noqa` suppression** (`_NOQA_RE`, `_is_noqa_suppressed`) with
  both bare and code-scoped forms, so a new rule inherits an escape hatch for the inevitable
  false positive without extra plumbing.
- Two existing rules are already, structurally, hallucination guards, even though they
  weren't framed that way:
  - **`X010`** (forbid suppressed `ImportError`/`ModuleNotFoundError`) stops a specific
    hallucination shape: code that "hedges" an import the author isn't sure exists by
    quietly downgrading it to optional, instead of the import failing loudly if the
    dependency was invented.
  - **`X007`/`X008`** (require a return annotation when a function returns a value; forbid
    an explicit `-> None`) enforce that the *stated* contract and the *actual* control flow
    agree - exactly the mechanism "contract mismatch" (see the taxonomy in the overview)
    needs, just currently scoped to return-type presence rather than return-type or
    docstring content.

None of `X001`-`X012` currently reads a docstring's prose against the signature it
describes, checks a string literal against the filesystem, or scores instruction-echo. Those
are the three gaps this document proposes closing.

## Proposed new rules

Each is written to slot into `rules.py` the same way the existing twelve do: a private
`_check_*` generator function added to `_iter_violations`, yielding `RuleViolation` records,
covered by the same `apply_noqa` suppression path with no special-casing.

### X013 - docstring/signature parameter divergence

**Class:** contract mismatch. This repo's own docstring convention is already Sphinx-style
`:param name:` (visible in `rules.py` itself, e.g. `check_tree`'s docstring), which makes
this mechanically checkable: parse the docstring's `:param NAME:` lines with a regex, diff
the name set against `ast.arguments`' actual parameter names.

```python
def _check_docstring_param_divergence(tree: ast.AST, filename: str) -> Iterable[RuleViolation]:
    """X013: flag :param NAME: entries naming a parameter the signature doesn't have,
    or a signature parameter with no matching :param NAME: entry, when the docstring
    documents *any* parameters at all (a docstring that documents none is X005's problem,
    not this rule's)."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node)
        if doc is None:
            continue
        documented = set(re.findall(r":param (\w+):", doc))
        if not documented:
            continue
        actual = {a.arg for a in node.args.args + node.args.kwonlyargs if a.arg != "self"}
        for phantom in documented - actual:
            yield RuleViolation(filename, node.lineno, node.col_offset, "X013",
                f"Docstring documents parameter `{phantom}`, which is not in the signature.")
        for undocumented in actual - documented:
            yield RuleViolation(filename, node.lineno, node.col_offset, "X013",
                f"Parameter `{undocumented}` is undocumented in a docstring that documents others.")
```

A phantom `:param:` is a near-canonical hallucination fingerprint: it is what happens when a
model edits a function signature and forgets the docstring, or drafts a docstring from a
plan that described a slightly different signature than what was actually written.

### X014 - claimed-but-absent raised exception

**Class:** contract mismatch. A docstring that says `:raises ValueError: ...` (or a plain
`Raises:` section, whichever convention a given module uses) but whose body contains no
`raise ValueError(...)` and calls no function whose own declared exceptions include it, is a
fabricated contract - usually the model describing what "should" happen rather than what the
code in front of it does. Scope this deliberately narrow to avoid false positives on
re-raised or propagated exceptions: flag only when the *documented* exception type does not
appear as a literal `raise ExceptionName(...)` or bare `raise` anywhere in the function body,
and does not appear as an argument the function calls with a `noqa`-style escape for the
(real, and common) case of exceptions raised deeper in the call graph.

### X015 - reference to a non-existent repo-relative path

**Class:** fabricated reference. Unlike `X001`-`X012`, this rule needs filesystem access, so
it cannot be a pure `check_tree(tree, filename, source)` function - it belongs in
`check_file(path)` instead, where a real `Path` is already available. Scan string literals
and comments for repo-relative-looking paths (a regex tuned to this repo's own conventions:
`src/...`, `templates/...`, `docs/...`, `tests/...`) and flag any that do not resolve
relative to the repository root. This directly catches the shape already documented as a
known failure mode in `docs/security/README.md`'s SME-review draft: `render_milestone`
interpolating a model-supplied slug into a path with no validation - a fabricated-path
hallucination and a path-traversal vulnerability are the same root cause (untrusted, unverified
model output reaching a filesystem operation), so this rule is also a defense-in-depth
security control, not only a hallucination detector.

### X016 - instruction-echo in a code comment

**Class:** instruction echo, applied to code instead of doc prose. A comment that restates
the diff/instruction it was generated from ("Add error handling for the null case", verbatim
mirroring a commit message or task description) rather than explaining the *why* violates
this repo's own comment convention (`CLAUDE.md`, "Conventions": "Only add [a comment] when
the WHY is non-obvious"). This is intentionally the hardest of the four to make fully
deterministic - a trigram-overlap-with-instruction-text detector (the same technique the
deferred milestone proposes for markers, see below) needs the instruction text as an input,
which a flake8 plugin invoked on a bare file does not have. Scope this one as
**advisory-only**, computed at PR-review time by the agentic tier described below rather than
as a blocking flake8 rule - it belongs in this document as the code-domain instance of
"instruction echo," but its home is the fact-check pass, not `rules.py`.

## Statistics collection

Wire two independent producers of the JSONL schema in
[hallucination-mitigation.md#2-durable-comparable-statistics---not-just-passfail](hallucination-mitigation.md#2-durable-comparable-statistics---not-just-passfail):

1. **`flake8_project_rules` itself.** Add an optional `--stats-out <path>` mode to
   `plugin.py` (or a thin wrapper script) that, alongside flake8's normal stdout reporting,
   appends one JSONL record per `RuleViolation` with `domain: "code"` and `class` mapped from
   `rule` via a fixed lookup table (`X013`/`X014` -> `contract_mismatch`, `X015` ->
   `fabricated_reference`, `X010` -> `fabricated_reference` when it fires, since a suppressed
   `ImportError` is functionally the same claim - "this dependency exists" - stated
   defensively instead of directly).
2. **The agentic fact-check pass** (below), which cannot be expressed as a flake8 rule at
   all, emits its own records with `tier: "agentic"` and `class: "unsupported_assertion"` or
   `"instruction_echo"`.

Aggregate both into `docs/reviews/hallucination-stats-<YYYY-MM-DD>.md` following the
existing `docs/reviews/README.md` report shape (Scope / Findings / Verdict / Recommended
actions), generated by `background-reviewer` the same way a dependency audit already is -
this reuses an existing agent responsibility rather than inventing a new owner.

## Combining deterministic checks with an agentic pass

Deterministic rules (`X013`-`X015`) catch structural mismatches - the claim and the code
disagree in a way `ast` can see directly. They cannot catch a **plausible but wrong**
claim where the code and the docstring agree with each other but both are wrong about the
world (a docstring says "matches this repo's `ruff.toml`" when it actually matches
`pyproject.toml`'s stricter, different config - a real, subtle class of error this
repo's own `ruff.toml`/`pyproject.toml` disagreement, documented in `CLAUDE.md`'s "Ruff
config note," makes newly plausible to get wrong). That class needs a second model, prompted
adversarially rather than generatively, to try to refute each claim by independently
re-deriving it:

- For each function touched in a diff, extract every factual claim from its docstring/
  comments (return behavior, side effects, referenced files/config).
- Spawn a fact-check pass whose prompt is explicitly framed as refutation, not confirmation
  ("find a claim in this diff the codebase does not support" rather than "does this diff
  look correct") - the adversarial framing matters, since a model asked to confirm tends to
  confirm.
- A claim that survives refutation ships; a claim that is refuted or that the fact-checker
  cannot verify one way or the other becomes a `human_review`-tier finding, following the
  same "never silently resolved" policy `SME REVIEW NEEDED` markers already establish for
  the docs side (see the docs subarticle).

This is exactly the reconciliation pattern `headless.py` already uses, generalized: rather
than trusting a model's self-report of what it changed, `headless.resolve_tree_headless`
diffs `markers.scan_tree` before and after the session
(`headless.py`, module docstring: "Reconciliation is a before/after `markers.scan_tree`
diff ... not the model's self-report, which is the right call and should stay that way," also
noted in the `docs/security/README.md` STRIDE draft under Repudiation). The fact-check pass
proposed here is the same idea applied to *semantic* claims instead of *file-set* claims:
don't ask the model whether its own docstring is accurate, verify it independently.

## Preventing delivery

Two enforcement points, escalating in strictness, mirroring `secret_scan.py`'s existing
dual-mode design (hook + standalone CLI):

1. **A `PreToolUse` hook**, structured like `.claude/hooks/secret_scan.py`, running the
   deterministic rules (`X013`-`X015`) against content about to be written and exiting `2` to
   block on the highest-confidence classes (`X015`'s nonexistent-path check has the fewest
   plausible false positives), while lower-confidence classes (`X013`/`X014`) surface as a
   warning first until real statistics justify promoting them to blocking - consistent with
   the phased rollout in the overview document.
2. **A `/pr-review` leg.** `/pr-review` already spawns `feature-reviewer` and
   `security-auditor` in parallel and synthesizes one verdict. Add a third parallel leg - a
   hallucination-fact-check pass - so a PR gets one merge verdict informed by all three,
   rather than requiring a separate manual step. This is additive: it does not change what
   `feature-reviewer` or `security-auditor` already look for.

A concrete invariant this proposal would add to `CLAUDE.md`'s "Invariants a change must not
break" section, for the maintainer to accept or reject rather than adopted here: **no
AI-authored docstring or comment claim ships without either passing the deterministic
contract check or being flagged for human review** - the code-domain mirror of the existing
"`SME REVIEW NEEDED` is never silently resolved" invariant.

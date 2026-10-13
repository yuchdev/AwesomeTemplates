---
name: document-tests
description: User-invoked as /document-tests [path]. Documents every JavaScript/TypeScript `it(...)`/`test(...)` case (Vitest, Jest, Mocha, node --test, Playwright Test) under path (default the whole repo) - classifies each as Unit, Mock, Integration, or E2E and inserts a standardized Scenario/Boundaries/On-failure JSDoc comment via the document_tests.py codemod, then delegates flagged/ambiguous cases to the test-documenter agent. Use to bring an undocumented or partially-documented test suite up to a consistent standard.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /document-tests [path]
---

# Document Tests

Document every `it(...)`/`test(...)`/`specify(...)` case (including `.only`,
`.skip`, and `.each` variants) under `$ARGUMENTS` (default the whole repo) with a
standardized classification + Scenario/Boundaries/On-failure JSDoc comment.

Unlike the `python` preset's equivalent, `scripts/document_tests.py` here is
**regex- and paren-counting-based, not AST-based** - the Python stdlib has no
JavaScript parser. It is a best-effort heuristic that reads structural signals
(test directory, filename segments such as `.e2e.`/`.integration.`, browser-driver
and mocking calls in the test body or at module scope), not test semantics. It
recognises only tests whose call starts a line and whose title is a string
literal. It will occasionally misparse unusual code; that is what step 2's
`Ambiguous` list and the `test-documenter` agent are for.

**When resolving `Ambiguous classification` items** (step 2 below), use
[references/classification-guide.md](references/classification-guide.md) — it
gives the semantic Unit/Mock/Integration/E2E definitions the script cannot infer,
the resolution rules of thumb, and the exact JSDoc-comment format (with a
good/bad example) the codemod emits.

## Steps

1. **Preview**: `python scripts/document_tests.py $ARGUMENTS --check`
   Read the summary: total test cases, classification counts, any `Skipped
   (custom doc comment present)` and `Ambiguous classification` lists.
2. **Decide whether the agent is needed**:
   - If there are zero `Skipped` and zero `Ambiguous` entries, the change is
     purely mechanical - apply directly: `python scripts/document_tests.py $ARGUMENTS`.
   - Otherwise, spawn the **`test-documenter`** agent with the target path and
     the preview output. It applies the script, then hand-resolves every
     `Ambiguous` item by reading the test body, and leaves every `Skipped`
     (custom doc comment) item untouched unless the user asked to standardize
     that specific file.
3. **Verify no regressions**: run the project's lint command (e.g.
   `npm run lint`), or `node --check <file>` on each touched plain `.js` file.
   A broken insertion shows up as a syntax error, not a passing/failing test,
   so this check is cheap and catches it immediately. For a small scope, also
   run the project's test command.
4. Report the summary the agent (or the direct script run) produced.

## Output

```
## Test Documentation - <path>
Scanned: N files, M test cases
[Unit] a  [Mock] b  [Integration] c  [E2E] d
Documented: X new/updated
Skipped (custom doc comments, left as-is): <list, or none>
Ambiguous - resolved: <file::describe > test -> classification>
Verification: <lint/syntax command> -> <pass/fail>
```

If the verification step fails, stop and hand the failure to `frontend-expert`
before re-running this skill - do not re-apply the codemod over a file that's
already broken. If the user wants hand-written doc comments standardized too,
re-run with the `test-documenter` agent and explicit permission to `--force` the
specific files named.

## Completion checklist

- [ ] `--check` preview run before any apply - counts, `Skipped`, and `Ambiguous` lists reviewed
- [ ] Every `Skipped (custom doc comment present)` item left untouched, unless the user explicitly asked to `--force` that specific file
- [ ] Every `Ambiguous classification` item resolved by reading the actual test body - not left at the script's best-effort guess
- [ ] The project's lint or syntax check run after apply and passed
- [ ] Diff is JSDoc comments only - no test logic, fixtures, assertions, titles, or imports changed
- [ ] Classification counts, skipped list, and ambiguous resolutions all included in the final report

---
name: js-typecheck
description: User-invoked as /js-typecheck [path]. Type-checks plain JavaScript files (default the whole repo) against their JSDoc annotations using the TypeScript compiler in checkJs mode, with no build step and no .ts files - then triages each error as a real bug, a wrong annotation, or a missing type. Use before merging a change to shared JS modules, or when adopting `// @ts-check` in an existing codebase.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /js-typecheck [path]
---

# JavaScript Type Check

Check every `.js`/`.mjs` file under `$ARGUMENTS` (default the whole repo) against its JSDoc
types with the TypeScript compiler in `checkJs` mode. This catches the class of bug a
plain-JavaScript project otherwise finds only at runtime - a misspelled property, a
possibly-`null` DOM query used unguarded, a function called with the wrong argument
shape - without converting anything to TypeScript.

## Steps

1. **Pick the config**:
   - If the repo has a `jsconfig.json` or a `tsconfig.json` with `"checkJs": true`, use
     it: `npx --no-install tsc --noEmit -p <that config>`.
   - Otherwise run a one-off check without writing any config:
     `npx --yes -p typescript tsc --noEmit --allowJs --checkJs --target es2022 --module nodenext --moduleResolution nodenext --lib es2022,dom,dom.iterable <files>`
     where `<files>` are the `.js`/`.mjs` files under `$ARGUMENTS`, excluding
     `node_modules/`, `dist/`, `build/`, and `coverage/`.
   - Say which of the two you used in the report.
2. **Summarize the output** - do not paste it whole. Group errors by file and by
   TypeScript error code (`TS2339` property does not exist, `TS2531`/`TS18047` possibly
   null, `TS2345` argument type mismatch, ...).
3. **Triage every error** into one of:
   - **Bug** - the code really can fail at runtime (e.g. `document.querySelector(...)` used
     without a null check on a page where the element may be absent).
   - **Wrong annotation** - the JSDoc says something the code does not do; the annotation
     is the thing to fix.
   - **Missing type** - an untyped value (`any`-by-inference from an untyped import or
     `JSON.parse`) that needs a `@typedef` or a validation step at the boundary.
4. **Hand fixes off** - bugs and missing types to `javascript-expert` (or
   `frontend-expert`), with `file:line` and the triage class. This skill reports; it does
   not edit.

## Output

```
## JS Type Check - <path>
Mode: project config <file> | one-off checkJs
Files checked: N
Errors: M (Bug a · Wrong annotation b · Missing type c)
### <file:line> - TS<code> - <Bug|Wrong annotation|Missing type>
- What: <one sentence>
- Fix: <one sentence>
Verdict: CLEAN | <a> bug(s) to fix
```

## Completion checklist

- [ ] The report names which mode ran (project config vs. one-off flags)
- [ ] Build output directories and `node_modules/` excluded from the file list
- [ ] Every error triaged as Bug, Wrong annotation, or Missing type - none left unclassified
- [ ] Compiler output summarized by file and error code, not pasted whole
- [ ] Fixes handed to `javascript-expert`/`frontend-expert`, not edited by this skill

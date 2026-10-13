---
name: ts-strictness-audit
description: User-invoked as /ts-strictness-audit [path]. Audits TypeScript code under path (default the whole repo) for type-safety escape hatches - explicit `any`, unchecked `as` casts, non-null assertions, `@ts-ignore`/`@ts-nocheck`, and disabled tsconfig strictness flags - and reports each with a risk rank and a sound replacement. Use before merging a change to shared types, or to measure type-safety debt.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /ts-strictness-audit [path]
---

# TypeScript Strictness Audit

Find every place under `$ARGUMENTS` (default the whole repo) where the type system has been
told to stop checking. Each escape hatch is a spot where a compile-clean build can still
fail at runtime. A clean `tsc` run says nothing about these, which is why this skill greps
for them explicitly.

## Steps

1. **Config**: read every `tsconfig*.json` in scope (following `extends`). Report whether
   `strict` is on and list any strict-family flag explicitly set to `false`
   (`strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, ...). Note whether
   `noUncheckedIndexedAccess` is enabled.
2. **Escape hatches**: search `.ts`/`.tsx`/`.mts`/`.cts` files, excluding `node_modules/`,
   `dist/`, `build/`, and generated `.d.ts` files:
   - `@ts-nocheck`, `@ts-ignore`, and `@ts-expect-error` without a reason comment
   - explicit `any`: `: any`, `<any>`, `as any`, `any[]`, `Record<string, any>`
   - `as unknown as` double casts, and other `as` casts except `as const`
   - non-null assertions: an identifier or `)`/`]` followed by `!` then `.`, `[`, `(`, `)`,
     `,`, or `;` (review each hit - `!==` and logical `!` are not assertions)
   - `eslint-disable` comments that switch off `@typescript-eslint/no-explicit-any`,
     `no-non-null-assertion`, or `ban-ts-comment`
3. **Rank each hit**:
   - **HIGH** - at a trust boundary (API response, `JSON.parse`, storage, URL params,
     `postMessage`) or in a shared/exported type, a whole-file `@ts-nocheck`, or a
     disabled strict flag.
   - **MEDIUM** - inside feature logic where a wrong value would reach the UI.
   - **LOW** - tests, fixtures, or a cast the surrounding markup/guard makes provably safe.
4. **Propose a sound replacement** per hit: `unknown` plus narrowing, a type guard, a schema
   check, a discriminated union, `satisfies`, or a guarded optional access instead of `!`.
5. If the user wants fixes, hand the HIGH/MEDIUM list to `typescript-expert`. This skill
   reports; it does not edit.

## Output

```
## TS Strictness Audit - <path>
Config: strict <on|off>; disabled flags: <list or none>; noUncheckedIndexedAccess <on|off>
Files scanned: N
Escape hatches: M (HIGH a · MEDIUM b · LOW c)
  any: x · as-casts: y · non-null !: z · ts-comments: w · lint disables: v
### [HIGH|MEDIUM|LOW] <file:line> - <kind>
- Why it matters: <one sentence>
- Sound replacement: <one sentence>
Verdict: CLEAN | <a> HIGH finding(s)
```

## Completion checklist

- [ ] Every tsconfig in scope read, including its `extends` chain
- [ ] `node_modules/`, build output, and generated `.d.ts` files excluded
- [ ] Each non-null-assertion grep hit confirmed by reading the line (not `!==` or logical not)
- [ ] Every hit ranked HIGH/MEDIUM/LOW with a concrete sound replacement
- [ ] Fixes handed to `typescript-expert`, not edited by this skill

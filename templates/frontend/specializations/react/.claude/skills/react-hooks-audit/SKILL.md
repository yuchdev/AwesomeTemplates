---
name: react-hooks-audit
description: User-invoked as /react-hooks-audit [path]. Checks every React component and custom hook under path (default the whole repo) against a fixed hooks-correctness checklist - rules-of-hooks violations, missing or suppressed effect dependencies, effects without cleanup, async races, state mirrored from props, index keys, and unsafe dangerouslySetInnerHTML. Use before merging any change that adds or touches effects, custom hooks, or list rendering.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /react-hooks-audit [path]
---

# React Hooks Audit

Review every component and custom hook under `$ARGUMENTS` (default the whole repo) against a
fixed correctness checklist. This is a narrower, mechanical companion to `feature-reviewer`.
It exists because hook bugs - stale closures, leaked subscriptions, races between overlapping
requests - usually pass review and tests, and show up only under real timing.

## Steps

1. **Run the linter first** if the project has `eslint-plugin-react-hooks`:
   `npm run lint` (or `npx --no-install eslint <path>`). Every `rules-of-hooks` error and
   `exhaustive-deps` warning is a finding; the rest of this checklist covers what the
   linter cannot see.
2. **Find call sites**: `grep -rnE "use(Effect|LayoutEffect|State|Reducer|Memo|Callback|Ref|Context)\(|dangerouslySetInnerHTML|key=\{" $ARGUMENTS`
   over `.jsx`/`.tsx`/`.js`/`.ts`, excluding `node_modules/` and build output.
3. **For each site, check**:
   - **Rules of hooks**: called unconditionally at the top level of a component or `use…`
     function - not inside a condition, loop, callback, or after an early `return`.
   - **Suppressed dependencies**: any `eslint-disable` for `react-hooks/exhaustive-deps`
     is a finding unless a comment explains why the omitted value is truly stable.
   - **Effect cleanup**: every subscription, listener, interval/timeout, observer, or
     socket an effect creates is released in the returned cleanup.
   - **Async races**: an effect that fetches aborts (`AbortController`) or ignores a
     response that arrives after its dependencies changed or the component unmounted.
   - **Unneeded effects**: an effect that only sets state derived from props/state, or
     that handles what is really a user event, should be computed during render or moved
     into the event handler.
   - **Mirrored props**: `useState(props.x)` with no reset path goes stale when `x`
     changes.
   - **List keys**: `key={index}` (or no key) on a list that can reorder, filter, or insert.
   - **`dangerouslySetInnerHTML`**: the value is either a constant or passed through a
     vetted sanitizer - otherwise it is a HIGH finding for `security-auditor`.
4. **Report every finding** with `file:line`, the rule violated, and a one-line fix. Do not
   report a finding for code whose data flow you haven't actually traced - a guess is worse
   than no finding here.
5. If the user wants fixes, hand them to `react-expert`. This skill reviews; it does not
   edit.

## Output

```
## React Hooks Audit - <path>
Lint: <ran: N rules-of-hooks, M exhaustive-deps | not configured>
Call sites scanned: N
Findings: M
### <file:line> - <rule violated>
- Why: <one sentence>
- Fix: <one sentence>
Verdict: CLEAN | <M> finding(s) to address
```

## Completion checklist

- [ ] The hooks lint rules ran first (or the report says they are not configured)
- [ ] Every effect, custom hook, list render, and `dangerouslySetInnerHTML` under the target path was checked, not just the suspicious ones
- [ ] Each finding names the specific rule (hook order, deps, cleanup, race, derived state, key, raw HTML) it violates
- [ ] No finding reported without tracing the actual data flow
- [ ] Fixes handed to `react-expert`, not edited by this skill

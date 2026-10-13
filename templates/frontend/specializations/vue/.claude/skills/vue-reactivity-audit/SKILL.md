---
name: vue-reactivity-audit
description: User-invoked as /vue-reactivity-audit [path]. Checks every Vue single-file component and composable under path (default the whole repo) against a fixed reactivity-correctness checklist - destructured reactive state, mutated props, watchers used where computed belongs, missing watcher/lifecycle cleanup, accidental module-level shared state, v-for keys and v-if/v-for on one element, and unsafe v-html. Use before merging any change that adds or touches reactive state, watchers, composables, or stores.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /vue-reactivity-audit [path]
---

# Vue Reactivity Audit

Review every `.vue` component and composable under `$ARGUMENTS` (default the whole repo)
against a fixed correctness checklist. This is a narrower, mechanical companion to
`feature-reviewer`. It exists because lost reactivity fails silently - the UI simply stops
updating, with no error - so these bugs pass a normal code read and a happy-path test.

## Steps

1. **Run the linter first** if the project has `eslint-plugin-vue`: `npm run lint` (or
   `npx --no-install eslint <path>`). Findings from `vue/no-mutating-props`,
   `vue/require-v-for-key`, `vue/no-use-v-if-with-v-for`, and `vue/no-v-html` count; the
   rest of this checklist covers what the linter cannot see.
2. **Find sites**: `grep -rnE "reactive\(|ref\(|computed\(|watch(Effect)?\(|onMounted|defineProps|storeToRefs|v-html|v-for" $ARGUMENTS`
   over `.vue`/`.js`/`.ts`, excluding `node_modules/` and build output.
3. **For each site, check**:
   - **Lost reactivity**: a `reactive` object, `props`, or a Pinia store destructured
     without `toRefs`/`storeToRefs`; a `reactive` variable reassigned wholesale; a
     `watch` on a destructured value instead of a getter.
   - **Mutated props**: assignment to a prop, or in-place mutation of a prop object/array
     (`props.items.push(...)`).
   - **Watch vs. computed**: a watcher whose only job is to copy or derive a value into
     another `ref` should be a `computed`; a `computed` with side effects or async work is
     a bug.
   - **Cleanup**: listeners, timers, observers, and third-party widgets created in
     `onMounted` or a watcher are released in `onUnmounted` or the watcher's cleanup; async
     work in a watcher is cancelled when the source changes again.
   - **Shared state by accident**: `ref`/`reactive` declared at module level in a
     composable is shared by every caller - a finding unless that sharing is intended and
     documented.
   - **Lists**: `v-for` without a stable `:key` (or keyed by index on a changing list);
     `v-if` on the same element as `v-for`.
   - **`v-html`**: the bound value is a constant or passed through a vetted sanitizer -
     otherwise it is a HIGH finding for `security-auditor`.
4. **Report every finding** with `file:line`, the rule violated, and a one-line fix. Do not
   report a finding for code whose data flow you haven't actually traced - a guess is worse
   than no finding here.
5. If the user wants fixes, hand them to `vue-expert`. This skill reviews; it does not edit.

## Output

```
## Vue Reactivity Audit - <path>
Lint: <ran: N findings | not configured>
Components/composables scanned: N
Findings: M
### <file:line> - <rule violated>
- Why: <one sentence>
- Fix: <one sentence>
Verdict: CLEAN | <M> finding(s) to address
```

## Completion checklist

- [ ] The Vue lint rules ran first (or the report says they are not configured)
- [ ] Every component, composable, and store under the target path was checked, not just the suspicious ones
- [ ] Each finding names the specific rule (lost reactivity, prop mutation, watch vs. computed, cleanup, shared state, list keys, raw HTML) it violates
- [ ] No finding reported without tracing the actual data flow
- [ ] Fixes handed to `vue-expert`, not edited by this skill

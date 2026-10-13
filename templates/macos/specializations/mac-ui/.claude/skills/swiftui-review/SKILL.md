---
name: swiftui-review
description: User-invoked as /swiftui-review [path]. Greps the given path (default the whole repo) for SwiftUI and AppKit-bridge code and checks each view against a fixed checklist - state with two owners, unstable ForEach identity, side effects or heavy work in body, AnyView, unstructured Task in onAppear, AppKit objects used off the main actor, and representable update/teardown mistakes. Use before merging any change that adds or touches SwiftUI views or NSViewRepresentable bridges.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /swiftui-review [path]
---

# SwiftUI Review

Review every SwiftUI view and AppKit bridge under `$ARGUMENTS` (default the whole repo)
against a fixed correctness checklist. This is a narrower, mechanical companion to
`feature-reviewer` - SwiftUI's invalidation and identity bugs look fine in a normal
diff and only show up as a stale row, a reset scroll position, or a janky window.

## Steps

1. **Find the surface**:
   `grep -rnE "struct .*: View|: App\b|@State|@Bindable|@StateObject|@ObservedObject|@EnvironmentObject|ForEach|AnyView|NSViewRepresentable|NSViewControllerRepresentable|NSHostingView|\.onAppear|\.task" $ARGUMENTS --include=*.swift`
2. **For each view / bridge, check**:
   - **State ownership** - is any value held in more than one `@State`/model, or is a
     view-created object held with `@ObservedObject` (recreated each update) instead of
     `@StateObject` / `@State` + `@Observable`?
   - **Identity** - does every `ForEach` use a stable, unique `id` (not an array index,
     not `\.self` on a mutable or non-unique value, not a per-render `UUID()`)?
   - **`body` purity** - any I/O, sorting/filtering a large collection, formatter
     construction, `print`, or mutation inside `body` or a computed subview?
   - **Type erasure** - `AnyView` where a `@ViewBuilder`, `Group`, or generic works?
   - **Async** - `Task {}` inside `.onAppear` instead of `.task`/`.task(id:)`; a
     `Task` capturing `self` strongly in a long-lived model; missing cancellation?
   - **Main-actor isolation** - an `@Observable` model that drives UI without
     `@MainActor`; UI state mutated from a background closure?
   - **Representable hygiene** - `updateNSView` rebuilding the view or resetting state
     on every update; no `Coordinator` for callbacks; no `dismantleNSView` cleanup for
     observers/timers?
   - **AppKit threading** - `NSView`/`NSWindow`/`NSMenu` touched from a non-main
     context?
   - **Mac conventions** - a toolbar-only action with no menu command / key equivalent;
     fixed hex colours for chrome; missing accessibility label on a custom control?
   - **Preview** - does a `#Preview` exist and avoid network/persistence/keychain?
3. **Report every finding** with `file:line`, the specific rule violated, and a
   one-line fix suggestion. Do not report a finding for code whose state ownership you
   have not actually traced - a guess is worse than no finding here.
4. If findings exist and the user wants them fixed, hand them to `swiftui-expert`
   (declarative layer) or `appkit-expert` (AppKit/bridge layer) rather than fixing them
   from this skill - this skill reviews, it doesn't edit.

## Output

```
## SwiftUI Review - <path>
Views scanned: N   Bridges scanned: B
Findings: M
### <file:line> - <rule violated>
- Why: <one sentence>
- Fix: <one sentence>
Verdict: CLEAN | <M> finding(s) to address
```

## Completion checklist

- [ ] Every `View`, `App`, and `NSViewRepresentable` under the target path was checked, not just the ones that looked suspicious
- [ ] Each finding names the specific rule (ownership, identity, body purity, erasure, async, isolation, bridge, threading, convention) it violates
- [ ] No finding reported without tracing the actual state owner, not a guess
- [ ] Findings handed to `swiftui-expert` / `appkit-expert` for fixes, not edited by this skill

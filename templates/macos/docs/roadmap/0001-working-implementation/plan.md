# Milestone 0001 - Working Implementation

**Package:** `{{PROJECT_PACKAGE}}` | **Swift sources:** `Sources/{{PROJECT_PACKAGE}}/` | **C++ core (if any):** `core/`

Illustrative milestone showing the roadmap folder taxonomy `implement-story`
and `task-verifier` expect: one story folder per numbered story
(`{TT.t}-{story-slug}/`), one task spec file per numbered step
(`{NN}-{task-slug}.md`), a `README.md` per story summarizing its tasks,
and this `plan.md` plus a sibling `status.md` at the milestone root. Replace
this whole milestone with your own project's first real milestone once you
adopt this template - it exists to show the shape, not to be extended.

Each task spec names its owner: `swift-expert` for Swift/SwiftUI/AppKit work,
`cpp-expert` for the C++ core, `testing-expert` for tests. A story that crosses
the Swift/C++ boundary lists the `cpp-expert` task before the `swift-expert`
task that consumes it.

## Stories

| Story | Name                                                 | Category | Output                                  |
|------|-------------------------------------------------------|----------|------------------------------------------|
| 01.0 | Generic working implementation (app shell, core, …)   | feature  | Make working PoC macOS application       |

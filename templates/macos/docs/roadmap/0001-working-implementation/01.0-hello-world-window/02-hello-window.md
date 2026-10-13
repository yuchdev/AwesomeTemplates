# 02 - Hello window

**Parent story:** [README.md](README.md)
**Owner:** `swift-expert`
**Status:** ⬜ Not started
**Depends on:** [01-config-model.md](01-config-model.md)

## Objective

This task is a stub to rename and implement a real one.
All subsequent paragraphs also should be rewritten into a real task.

## Files

- `Sources/{{PROJECT_PACKAGE}}/UI/HelloView.swift` - new SwiftUI view.
- `Sources/{{PROJECT_PACKAGE}}/UI/HelloViewModel.swift` - new `@MainActor` view model.
- Wire the view into the app's existing `Scene` / `WindowGroup`.

## Types and Functions

- `HelloViewModel` (`@MainActor`, `@Observable`) exposing `greeting: String`, initialised from `AppConfig`.
- `HelloView` displaying `viewModel.greeting`.

## Constraints

- None

## Success criteria

- [ ] The app's main window shows `AppConfig.greeting`.
- [ ] `greeting` comes from `AppConfig` (task 01) - no hardcoded string in the view.
- [ ] The view has a working `#Preview` and an accessibility label.

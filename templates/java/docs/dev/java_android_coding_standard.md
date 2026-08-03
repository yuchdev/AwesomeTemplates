# {{PROJECT_NAME}} Java/Android Style Guide

Referenced by `java-expert` and `testing-expert` (`.claude/agents/`). This is a
starting skeleton, not a finished standard - the `java` preset ships with
those two agents intentionally incomplete (see the preset's own history);
fill in the project-specific rules below before relying on it.

## Contents

- **Style** - formatting, naming, package structure, nullability annotation
  conventions (`@NonNull` / `@Nullable`).
- **Javadoc** - what requires a doc comment (every public class, method,
  Android component, repository, DTO/entity, and test fixture).
- **Testing** - the test classification scheme `testing-expert` uses when it
  reports coverage/risk deltas (unit vs. instrumented vs. UI).
- **Android conventions** - component thinness (UI classes bind state and
  delegate to ViewModels/controllers/repositories/services), dependency
  injection pattern, and any lint/`gradlew` gates CI enforces.

## Project-specific overrides

Add this project's mandatory rules here: concrete, enforced-by-a-hook-or-CI-gate
rules, not general advice. Each entry should name what enforces it (a Gradle
task, a lint rule, a CI gate, a review checklist item) so the rule is auditable
rather than aspirational.

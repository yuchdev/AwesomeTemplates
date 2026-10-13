# Example efficiency audit - 2026-01-05

**Scope:** `src/ingest/` (files touched by the last 2 weeks of commits).

## Findings

| Severity | Finding                                                           | Evidence                                              |
|----------|-------------------------------------------------------------------|-------------------------------------------------------|
| MEDIUM   | `parseBatch()` re-reads the same file on every call inside a loop | `ingest/parser.cpp:42` - no caching across iterations |
| LOW      | Unbounded vector growth in `buffer_` under high throughput        | `ingest/parser.cpp:88`                                |
| MEDIUM   | Strong `self` capture in a stored `Task` closure retains the view model | `Sources/App/IngestViewModel.swift:61` - no `[weak self]` |
| INFO     | No license conflicts found in current dependency set              | `CMakeLists.txt`, `Package.resolved`                  |

## Verdict

No CRITICAL or HIGH findings - does not block merge.

## Recommended actions

1. Cache the parsed file across loop iterations in `parse_batch()`.
2. Cap `_buffer` at a fixed size or move to a streaming approach.
3. Capture `[weak self]` in `IngestViewModel`'s long-lived `Task` and cancel it in `deinit`/`onDisappear`.

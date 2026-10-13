---
name: boost-asio-review
description: User-invoked as /boost-asio-review [path]. Greps the given path (default the whole repo) for Boost.Asio async call sites and checks each one against a fixed lifetime/cancellation/threading checklist - dangling handler captures, missing work guards, unserialized shared state across completion handlers, unbounded network reads - plus macOS-specific traps (SIGPIPE, TLS backend, sandbox network entitlements, Boost crossing into Swift). Use before merging any change that adds or touches async Asio/Beast code.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /boost-asio-review [path]
---

# Boost.Asio Review (macOS)

Review every Boost.Asio (and Beast, where it sits on top of Asio) async call site under
`$ARGUMENTS` (default the whole repo) against a fixed correctness checklist. This is a
narrower, mechanical companion to `feature-reviewer` - it exists because async
lifetime/cancellation bugs are structurally different from the correctness issues a
general code review catches, and are easy to miss without deliberately grepping for the
Asio-specific danger signs.

## Steps

1. **Find call sites**: `grep -rn "async_\|io_context\|strand\|use_future\|awaitable<" $ARGUMENTS`
   (adjust the pattern for the project's actual async surface - `async_read`,
   `async_write`, `async_connect`, `async_accept`, `co_spawn`, etc.).
2. **For each call site, check**:
   - **Handler capture lifetime**: does the completion handler keep alive everything it
     touches (via `shared_from_this()` or an explicit `shared_ptr` capture) for the
     operation's duration, or does it capture `this`/a reference that could be destroyed
     first?
   - **Work guard**: if the surrounding `io_context` is expected to keep running with no
     pending operations at some point, is there an explicit `executor_work_guard` (or a
     documented reason one isn't needed)?
   - **Strand/serialization**: if the handler touches state also touched by another
     handler, is access serialized via a `strand` (or single-threaded `io_context`), not
     an ad hoc mutex bolted onto callback code?
   - **Cancellation/timeout handling**: on `operation_aborted` (or an explicit timeout),
     is the handler's cleanup path exercised and correct - not silently dropped?
   - **Beast-specific**: does every stream reading from an untrusted peer have an
     explicit `expires_after`/timeout set, and is the body fully read/streamed before
     the next operation reuses the stream?
3. **macOS-specific checks**:
   - **SIGPIPE**: is a raw socket adopted with `assign()` given `SO_NOSIGPIPE` (macOS has
     no `MSG_NOSIGNAL`), or is `SIGPIPE` ignored once at startup?
   - **TLS backend**: does `boost::asio::ssl` rely on OpenSSL that the project bundles
     and patches, with hostname verification enabled (`set_verify_callback` /
     `ssl::host_name_verification`)? Flag `verify_none`.
   - **Entitlements**: does the code open a client or listening socket that the target's
     `.entitlements` (`network.client` / `network.server`) does not grant?
   - **Fork**: any `fork()`/`system()` in a process that runs an `io_context`?
   - **Swift boundary**: does a Boost type, `error_code`, or exception appear in a header
     the Swift side imports, or does a handler call into Swift without stating the thread?
4. **Report every finding** with `file:line`, the specific rule violated, and a
   one-line fix suggestion. Do not report a finding for code you haven't actually traced
   the ownership/lifetime of - a guess is worse than no finding here.
5. If findings exist and the user wants them fixed, hand them to `cpp-expert` (or
   `boost-expert` for anything Asio/Beast-API-specific) rather than fixing them yourself
   from this skill - this skill reviews, it doesn't edit.

## Output

```
## Boost.Asio Review - <path>
Call sites scanned: N
Findings: M
### <file:line> - <rule violated>
- Why: <one sentence>
- Fix: <one sentence>
Verdict: CLEAN | <M> finding(s) to address
```

## Completion checklist

- [ ] Every `async_*`/`co_spawn`/coroutine call site under the target path was checked, not just the ones that looked suspicious
- [ ] Each finding names the specific rule (handler lifetime, work guard, strand, cancellation, timeout, SIGPIPE, TLS, entitlement, fork, Swift boundary) it violates
- [ ] No finding reported without tracing the actual ownership/lifetime, not a guess
- [ ] Findings handed to `cpp-expert`/`boost-expert` for fixes, not edited by this skill

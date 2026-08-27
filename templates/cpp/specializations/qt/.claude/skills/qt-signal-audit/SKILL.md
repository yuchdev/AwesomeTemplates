---
name: qt-signal-audit
description: User-invoked as /qt-signal-audit [path]. Greps the given path (default the whole repo) for Qt connect() call sites and QObject lifetime patterns and checks each one against a fixed checklist - context-free lambda connections, string-based SIGNAL/SLOT macros, cross-thread connections using the wrong connection type, and QObjects wrapped in a second ownership mechanism. Use before merging any change that adds or touches signal/slot wiring or QObject lifetime.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /qt-signal-audit [path]
---

# Qt Signal/Slot Audit

Review every Qt `connect()` call site and `QObject`-derived class under `$ARGUMENTS`
(default the whole repo) against a fixed correctness checklist. This is a narrower,
mechanical companion to `feature-reviewer` - it exists because signal/slot lifetime bugs
(a lambda that outlives its captures, a cross-thread delivery race) are structurally
different from the correctness issues a general code review catches, and are easy to
miss without deliberately grepping for the Qt-specific danger signs.

## Steps

1. **Find call sites**: `grep -rn "connect(\|SIGNAL(\|SLOT(\|deleteLater\|moveToThread" $ARGUMENTS`.
2. **For each `connect()` call, check**:
   - **String-based macros**: does it use `SIGNAL()`/`SLOT()` instead of the
     functor/pointer-to-member syntax? Flag it - the string form isn't compile-time
     checked and is not the standard for new code in this preset.
   - **Context-free lambda**: is a lambda connected with no `receiver`/context object
     argument? Flag it - the connection outlives any object the lambda captures by
     reference or by raw pointer.
   - **Connection type across threads**: if sender and receiver live on different
     threads, is the connection type explicit (`Qt::QueuedConnection`, or
     `BlockingQueuedConnection` only with a stated reason), rather than left at
     `Qt::AutoConnection` and assumed correct?
3. **For each `QObject`-derived class, check**:
   - **`Q_OBJECT` present** if the class declares signals/slots or is used in a queued
     connection.
   - **Ownership**: is a Qt-parented object (created with a parent, or added to a
     layout/parent widget) also held in a `unique_ptr`/`shared_ptr` elsewhere? Flag the
     double-ownership risk.
   - **Cross-thread deletion**: is `delete` called directly on a `QObject` that might
     still be a target of a queued signal from another thread, instead of
     `deleteLater()`?
4. **Report every finding** with `file:line`, the specific rule violated, and a
   one-line fix suggestion. Do not report a finding for a pattern you haven't confirmed
   by reading the actual object's ownership/thread affinity - a guess is worse than no
   finding here.
5. If findings exist and the user wants them fixed, hand them to `cpp-expert` (or
   `qt-expert` for anything Qt-API-specific) rather than fixing them yourself from this
   skill - this skill reviews, it doesn't edit.

## Output

```
## Qt Signal/Slot Audit - <path>
Call sites scanned: N
Findings: M
### <file:line> - <rule violated>
- Why: <one sentence>
- Fix: <one sentence>
Verdict: CLEAN | <M> finding(s) to address
```

## Completion checklist

- [ ] Every `connect()` call site under the target path was checked, not just the ones that looked suspicious
- [ ] Every `QObject`-derived class touched by the change was checked for `Q_OBJECT`, ownership, and cross-thread deletion
- [ ] Each finding names the specific rule (string macro, context-free lambda, connection type, ownership, cross-thread delete) it violates
- [ ] No finding reported without confirming the actual ownership/thread affinity, not a guess
- [ ] Findings handed to `cpp-expert`/`qt-expert` for fixes, not edited by this skill

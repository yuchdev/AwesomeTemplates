"""Severity-gated console tracing for `generate`'s pipeline - so every step
(files copied, docs regenerated, each marker resolved, each Anthropic API
call) is visible live in the console instead of only surfacing in the final
warnings/summary block.

A single `LogHelper` is built once in `cli.py` from `--log-severity` and
threaded explicitly as an optional keyword through `copy_preset`/`docgen`/
`resolver`, the same way `warnings: list[str]` is already threaded through all
of those - not a module-global logger, so tests can omit it (or inject one
backed by a captured stream) without monkeypatching global state. Every
function that accepts `log` defaults it to `NULL_LOG` when omitted, so no
existing caller's output changes just because this parameter exists.

Deliberately not Python's stdlib `logging` module: this narrates one
command's own progress to the user's terminal, not process-wide diagnostic
logging with handlers/formatters/propagation - a plain leveled Console
wrapper is the right amount of machinery. Writes to stderr (not stdout) so
`generate --json --log-severity debug` still emits parseable JSON on stdout
with the live trace interleaved on stderr, the same stdout/stderr split any
well-behaved CLI keeps between data and diagnostics.

Distinct from `graph`'s own `--log-verbosity {info,debug}` flag in `cli.py`,
which stays as-is - that flag's two-level, additive-only shape (see
`_LOG_LEVELS`) predates this module and only narrates `graph`'s own
dependency-scan phases, not `generate`'s copy/docgen/AI pipeline.
"""

from __future__ import annotations

import enum

from rich.console import Console


class LogSeverity(str, enum.Enum):
    """Ordered loudest-first. `--log-severity X` shows every level at or
    above X's information value: X=debug shows everything (including per-file
    copies and per-marker API call detail); X=error shows only errors."""

    error = "error"
    warning = "warning"
    info = "info"
    debug = "debug"


_RANK: dict[LogSeverity, int] = {
    LogSeverity.error: 0,
    LogSeverity.warning: 1,
    LogSeverity.info: 2,
    LogSeverity.debug: 3,
}

_STYLE: dict[LogSeverity, str] = {
    LogSeverity.error: "bold red",
    LogSeverity.warning: "yellow",
    LogSeverity.info: "cyan",
    LogSeverity.debug: "dim",
}


class LogHelper:
    def __init__(self, severity: LogSeverity = LogSeverity.warning, console: Console | None = None):
        self.severity = severity
        self.console = console if console is not None else Console(stderr=True)

    def _emit(self, level: LogSeverity, message: str) -> None:
        if _RANK[level] > _RANK[self.severity]:
            return
        style = _STYLE[level]
        # soft_wrap=True: trace lines routinely carry full filesystem paths -
        # rich's default word-wrap would otherwise break a path mid-string
        # across two physical lines, which is unreadable and un-greppable.
        self.console.print(f"[{style}]{level.value}:[/{style}] {message}", soft_wrap=True)

    def error(self, message: str) -> None:
        self._emit(LogSeverity.error, message)

    def warning(self, message: str) -> None:
        self._emit(LogSeverity.warning, message)

    def info(self, message: str) -> None:
        self._emit(LogSeverity.info, message)

    def debug(self, message: str) -> None:
        self._emit(LogSeverity.debug, message)


class _NullLogHelper:
    """No-op stand-in used whenever a caller omits `log` - every method is a
    deliberate no-op, not merely a very-quiet LogHelper, so omitting `log`
    costs nothing and prints nothing, ever."""

    def error(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def debug(self, message: str) -> None:
        pass


NULL_LOG = _NullLogHelper()

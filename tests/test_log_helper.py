from __future__ import annotations

from awesome_templates.log_helper import NULL_LOG, LogHelper, LogSeverity


class _FakeConsole:
    """Captures printed messages instead of touching a real stream, so tests
    can assert on exactly what a given severity level did or didn't emit."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, message: str, **kwargs) -> None:
        self.lines.append(message)


def _log_all_levels(log: LogHelper) -> None:
    log.error("an error")
    log.warning("a warning")
    log.info("an info")
    log.debug("a debug")


def test_error_severity_shows_only_errors():
    console = _FakeConsole()
    log = LogHelper(severity=LogSeverity.error, console=console)
    _log_all_levels(log)
    assert len(console.lines) == 1
    assert "an error" in console.lines[0]


def test_warning_severity_shows_error_and_warning_only():
    console = _FakeConsole()
    log = LogHelper(severity=LogSeverity.warning, console=console)
    _log_all_levels(log)
    joined = "\n".join(console.lines)
    assert "an error" in joined
    assert "a warning" in joined
    assert "an info" not in joined
    assert "a debug" not in joined


def test_info_severity_shows_error_warning_and_info():
    console = _FakeConsole()
    log = LogHelper(severity=LogSeverity.info, console=console)
    _log_all_levels(log)
    joined = "\n".join(console.lines)
    assert "an error" in joined
    assert "a warning" in joined
    assert "an info" in joined
    assert "a debug" not in joined


def test_debug_severity_shows_everything():
    console = _FakeConsole()
    log = LogHelper(severity=LogSeverity.debug, console=console)
    _log_all_levels(log)
    assert len(console.lines) == 4


def test_default_severity_is_warning():
    console = _FakeConsole()
    log = LogHelper(console=console)
    assert log.severity == LogSeverity.warning


def test_null_log_never_emits(capsys):
    # NULL_LOG has no console at all - calling every method must be a total
    # no-op regardless of how loud the message is.
    NULL_LOG.error("x")
    NULL_LOG.warning("x")
    NULL_LOG.info("x")
    NULL_LOG.debug("x")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

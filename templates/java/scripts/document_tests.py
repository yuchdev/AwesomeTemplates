"""Insert standardized Javadoc documentation comments onto JUnit test methods.

For every method annotated ``@Test``/``@ParameterizedTest`` found under a target
directory, generates a Javadoc comment that classifies the test as one of
``Unit``, ``Mock``, ``Integration``, or ``E2E`` and fills a fixed narrative
template (Scenario / Boundaries / On-failure-first-check) derived mechanically
from the method's name, enclosing class, parameters, and body - no test logic
is read for "meaning", only scanned for structural signals (mocking,
instrumentation/UI runners, source-set placement).

There is no Java equivalent of Python's ``ast`` module in the stdlib, so this
codemod is regex- and brace-counting-based rather than AST-based. It is a
best-effort heuristic, same spirit as ``document_tests.py`` in the ``python``
preset, not a Java parser: unusual formatting (annotation arguments spanning
many lines, braces inside string literals used as method-body delimiters,
``@Nested`` classes closing before the next class declaration) can confuse it.
When in doubt it flags a test ``ambiguous`` rather than guessing silently -
see the ``document-tests`` skill for how those are hand-resolved.

Classification heuristic (path/filename-first, body-refined):

- path contains an ``androidTest`` directory -> ``E2E`` (instrumentation/UI
  source set by convention).
- else path contains an ``integrationTest``/``integration`` directory, or the
  filename ends ``IT.java`` (Maven Failsafe convention):
    - body uses an instrumentation/UI marker (Espresso, ``ActivityScenario``,
      Compose test rule, UI Automator) -> ``E2E``
    - else -> ``Integration``
- else path contains a ``test`` directory (or unrecognised layout):
    - body uses an instrumentation/UI marker -> ``E2E`` (e.g. Robolectric +
      Espresso hybrids that still live in the unit source set)
    - body uses a Mockito/Robolectric mocking marker -> ``Mock``
    - else -> ``Unit``
    - tests in an unrecognised directory are additionally flagged
      ``ambiguous`` for human/agent review, since no directory convention
      backs the guess.

A generated Javadoc is recognisable by its first content line matching
``r"^\\[(Unit|Mock|Integration|E2E)\\] .+: verifies .+\\.$"``. Re-running this
script re-generates (and overwrites) only Javadocs matching that pattern, so
it is safe to run repeatedly as tests change. A pre-existing hand-written
Javadoc that does NOT match the pattern is left alone and reported as
skipped, unless ``--force`` is passed.

Usage::

    python scripts/document_tests.py                    # scan the whole repo
    python scripts/document_tests.py app/src/test/java   # scope to a directory
    python scripts/document_tests.py --check             # report only, no writes
    python scripts/document_tests.py --force             # overwrite hand-written Javadocs too

Exit status is ``1`` in ``--check`` mode when any test would change, else ``0``.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_TARGET = "."

# Directories that never hold real test sources - skip descending into them.
EXCLUDED_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    "build",
    "out",
    "target",
    "node_modules",
}

CLASSIFICATIONS = ("Unit", "Mock", "Integration", "E2E")

_GENERATED_TITLE_RE = re.compile(r"^\[(Unit|Mock|Integration|E2E)\] .+: verifies .+\.$")

_E2E_BODY_MARKERS = (
    "espresso",
    "onview(",
    "activityscenario",
    "instrumentation",
    "uiautomator",
    "composetestrule",
    "createandroidcomposerule",
    "intending(",
    "intents.",
)
_MOCK_BODY_MARKERS = (
    "mockito",
    "@mock",
    "mock(",
    "when(",
    "verify(",
    "robolectric",
    "powermock",
    "doreturn(",
    "doanswer(",
)

_TEST_ANNOT_RE = re.compile(r"^([ \t]*)@(Test|ParameterizedTest)\b")
_CLASS_RE = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*"
    r"(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:abstract\s+)?"
    r"class\s+(\w+)"
)
_SIG_NAME_RE = re.compile(r"([A-Za-z_]\w*)\s*\(")


def _display_path(file_path: Path) -> str:
    try:
        return str(file_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(file_path)


@dataclass
class TestCase:
    """One discovered ``@Test``/``@ParameterizedTest`` method and its rendered Javadoc."""

    file_path: Path
    qualname: str
    method_name: str
    classification: str
    ambiguous: bool
    insert_line: int  # 0-indexed line to insert before (the top of the annotation block)
    delete_start: Optional[int]  # 0-indexed inclusive start of an existing generated Javadoc
    delete_end: Optional[int]  # 0-indexed inclusive end of an existing generated Javadoc
    skip_custom_docstring: bool
    indent: str
    rendered: str = field(default="")


def _humanize(identifier: str) -> str:
    name = re.sub(r"^test_?", "", identifier, flags=re.IGNORECASE)
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+", name)
    return " ".join(w.lower() for w in words) if words else name.lower()


def _humanize_class(class_name: str) -> str:
    name = re.sub(r"(Tests?|TestCase|IT)$", "", class_name)
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+", name)
    return " ".join(w.lower() for w in words) if words else class_name.lower()


def _context_label(file_path: Path, class_name: Optional[str]) -> str:
    if class_name:
        return _humanize_class(class_name)
    return _humanize_class(file_path.stem)


def _params_line(sig_text: str) -> str:
    open_idx = sig_text.find("(")
    if open_idx == -1:
        return "none"
    depth = 0
    close_idx = -1
    for idx in range(open_idx, len(sig_text)):
        if sig_text[idx] == "(":
            depth += 1
        elif sig_text[idx] == ")":
            depth -= 1
            if depth == 0:
                close_idx = idx
                break
    if close_idx == -1:
        return "none"
    raw = sig_text[open_idx + 1 : close_idx].strip()
    if not raw:
        return "none"
    names = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = re.findall(r"[A-Za-z_]\w*", part)
        if tokens:
            names.append(tokens[-1])
    return ", ".join(names) if names else "none"


def _extract_body(lines: list[str], brace_line: int) -> str:
    """Brace-count from the first ``{`` at/after ``brace_line`` to its match.

    Ignores string/char literal and comment contents on a best-effort basis
    (not a full lexer) - good enough to keep an unrelated ``}`` inside a log
    message from truncating the scan early in the common case.
    """
    depth = 0
    started = False
    in_line_comment = False
    in_block_comment = False
    in_string = False
    in_char = False
    collected: list[str] = []

    for line in lines[brace_line:]:
        in_line_comment = False
        i = 0
        buf = []
        while i < len(line):
            ch = line[i]
            nxt = line[i + 1] if i + 1 < len(line) else ""
            if in_line_comment:
                break
            if in_block_comment:
                if ch == "*" and nxt == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if in_string:
                buf.append(ch)
                if ch == "\\":
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                i += 1
                continue
            if in_char:
                buf.append(ch)
                if ch == "\\":
                    i += 2
                    continue
                if ch == "'":
                    in_char = False
                i += 1
                continue
            if ch == "/" and nxt == "/":
                in_line_comment = True
                break
            if ch == "/" and nxt == "*":
                in_block_comment = True
                i += 2
                continue
            if ch == '"':
                in_string = True
                buf.append(ch)
                i += 1
                continue
            if ch == "'":
                in_char = True
                buf.append(ch)
                i += 1
                continue
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
            buf.append(ch)
            i += 1
            if started and depth == 0:
                collected.append("".join(buf))
                return "\n".join(collected).lower()
        collected.append("".join(buf))
    return "\n".join(collected).lower()


def _classify(file_path: Path, body_text: str) -> tuple[str, bool]:
    parts = {p.lower() for p in file_path.parts}
    stem = file_path.stem
    has_e2e_marker = any(marker in body_text for marker in _E2E_BODY_MARKERS)
    has_mock_marker = any(marker in body_text for marker in _MOCK_BODY_MARKERS)

    if "androidtest" in parts:
        return "E2E", False

    if "integrationtest" in parts or "integration" in parts or stem.endswith("IT"):
        if has_e2e_marker:
            return "E2E", False
        return "Integration", False

    if "test" in parts:
        if has_e2e_marker:
            return "E2E", False
        if has_mock_marker:
            return "Mock", False
        return "Unit", False

    # Unrecognised directory layout: best-effort cascade, flagged for review.
    if has_e2e_marker:
        return "E2E", True
    if has_mock_marker:
        return "Mock", True
    return "Unit", True


def _render_javadoc(indent: str, classification: str, context_label: str, method_name: str, params: str) -> str:
    subject = _humanize(method_name)

    lines = [
        f"{indent}/**",
        f"{indent} * [{classification}] {context_label}: verifies {subject}.",
        f"{indent} *",
        f"{indent} * <p>Scenario:",
        f"{indent} * <ul>",
        f"{indent} *   <li>Given {params}",
        f"{indent} *   <li>When {method_name} executes the target flow",
        f"{indent} *   <li>Then the expected outcome for {subject} is confirmed",
        f"{indent} * </ul>",
        f"{indent} *",
        f"{indent} * <p>Boundaries:",
        f"{indent} * <ul>",
        f"{indent} *   <li>Focus: {subject}",
        f"{indent} *   <li>Fixtures/params: {params}",
        f"{indent} *   <li>Scope: assertions and setup in this test method only",
        f"{indent} * </ul>",
        f"{indent} *",
        f"{indent} * <p>On failure, first check:",
        f"{indent} * <ul>",
        f"{indent} *   <li>Assertion details tied to {subject}",
        f"{indent} *   <li>Fixture or mock setup used by this test",
        f"{indent} *   <li>Recent changes in code paths exercised by {context_label}",
        f"{indent} * </ul>",
        f"{indent} */",
    ]
    return "\n".join(lines)


def _existing_javadoc_range(lines: list[str], top: int) -> tuple[Optional[int], Optional[int], Optional[str]]:
    end = top - 1
    while end >= 0 and not lines[end].strip():
        end -= 1
    if end < 0 or not lines[end].strip().endswith("*/"):
        return None, None, None

    start = end
    while start >= 0 and "/**" not in lines[start]:
        start -= 1
        if start < top - 200:  # runaway guard for a malformed/missing opener
            return None, None, None
    if start < 0:
        return None, None, None

    if lines[start].strip() == "/**":
        first_content = lines[start + 1].strip().lstrip("*").strip() if start + 1 <= end else ""
    else:
        after_open = lines[start].split("/**", 1)[1]
        first_content = after_open.strip().lstrip("*").strip()

    return start, end, first_content


def _collect_file(file_path: Path, lines: list[str]) -> list[TestCase]:
    cases: list[TestCase] = []
    n = len(lines)
    last_class_name: Optional[str] = None

    i = 0
    while i < n:
        class_match = _CLASS_RE.match(lines[i])
        if class_match:
            last_class_name = class_match.group(1)

        annot_match = _TEST_ANNOT_RE.match(lines[i])
        if not annot_match:
            i += 1
            continue

        top = i
        while top - 1 >= 0 and lines[top - 1].strip().startswith("@"):
            top -= 1
        bottom = i
        while bottom + 1 < n and lines[bottom + 1].strip().startswith("@"):
            bottom += 1

        sig_idx = bottom + 1
        while sig_idx < n and not lines[sig_idx].strip():
            sig_idx += 1

        sig_lines: list[str] = []
        j = sig_idx
        while j < n:
            sig_lines.append(lines[j])
            if "{" in lines[j]:
                break
            j += 1
        else:
            i = bottom + 1
            continue

        sig_text = "\n".join(sig_lines)
        name_match = _SIG_NAME_RE.search(sig_text)
        if not name_match:
            i = bottom + 1
            continue
        method_name = name_match.group(1)

        indent = re.match(r"[ \t]*", lines[top]).group(0)
        del_start, del_end, existing_title = _existing_javadoc_range(lines, top)
        skip_custom = existing_title is not None and not _GENERATED_TITLE_RE.match(existing_title)

        body_text = _extract_body(lines, j)
        classification, ambiguous = _classify(file_path, body_text)
        context_label = _context_label(file_path, last_class_name)
        params = _params_line(sig_text)

        qualname = f"{last_class_name}.{method_name}" if last_class_name else method_name
        rendered = _render_javadoc(indent, classification, context_label, method_name, params)

        cases.append(
            TestCase(
                file_path=file_path,
                qualname=qualname,
                method_name=method_name,
                classification=classification,
                ambiguous=ambiguous,
                insert_line=top,
                delete_start=del_start,
                delete_end=del_end,
                skip_custom_docstring=skip_custom,
                indent=indent,
                rendered=rendered,
            )
        )
        i = j + 1

    return cases


def _apply_edits(lines: list[str], cases: list[TestCase], force: bool) -> tuple[list[str], list[TestCase]]:
    out = list(lines)
    applied: list[TestCase] = []
    for case in sorted(cases, key=lambda c: c.insert_line, reverse=True):
        if case.skip_custom_docstring and not force:
            continue
        rendered_lines = case.rendered.split("\n")
        if case.delete_start is not None and case.delete_end is not None:
            out[case.delete_start : case.delete_end + 1] = rendered_lines
        else:
            out[case.insert_line : case.insert_line] = rendered_lines
        applied.append(case)
    return out, applied


def _discover_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if target.name.endswith((".java",)) else []
    files: list[Path] = []
    for pattern in ("*Test.java", "*Tests.java", "*TestCase.java", "*IT.java"):
        for candidate in target.rglob(pattern):
            if EXCLUDED_DIRS & set(candidate.parts):
                continue
            files.append(candidate)
    return sorted(set(files))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", default=DEFAULT_TARGET, help="Test file or directory (default: whole repo)")
    parser.add_argument("--check", action="store_true", help="Report only; exit 1 if changes are pending")
    parser.add_argument("--force", action="store_true", help="Overwrite hand-written Javadocs too")
    args = parser.parse_args()

    target = (REPO_ROOT / args.path).resolve() if not Path(args.path).is_absolute() else Path(args.path)
    files = _discover_files(target)

    counts = dict.fromkeys(CLASSIFICATIONS, 0)
    documented = 0
    skipped_custom: list[str] = []
    ambiguous: list[str] = []
    changed_files = 0

    for file_path in files:
        source = file_path.read_text(encoding="utf-8")
        lines = source.split("\n")

        cases = _collect_file(file_path, lines)
        if not cases:
            continue

        for case in cases:
            counts[case.classification] += 1
            rel = f"{_display_path(file_path)}::{case.qualname}"
            if case.ambiguous:
                ambiguous.append(rel)
            if case.skip_custom_docstring:
                skipped_custom.append(rel)

        new_lines, applied = _apply_edits(lines, cases, args.force)
        if not applied:
            continue

        changed_files += 1
        documented += len(applied)
        if not args.check:
            file_path.write_text("\n".join(new_lines), encoding="utf-8")

    print(f"Scanned {len(files)} file(s), {sum(counts.values())} test method(s).")
    print("  " + "  ".join(f"[{c}] {n}" for c, n in counts.items()))
    verb = "would document" if args.check else "documented"
    print(f"{verb.capitalize()} {documented} test(s) across {changed_files} file(s).")
    if skipped_custom:
        print(f"Skipped (custom Javadoc present, use --force to overwrite): {len(skipped_custom)}")
        for rel in skipped_custom:
            print(f"  - {rel}")
    if ambiguous:
        print(f"Ambiguous classification (needs review, no directory convention matched): {len(ambiguous)}")
        for rel in ambiguous:
            print(f"  - {rel}")

    if args.check and documented:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

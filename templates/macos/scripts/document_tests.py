"""Insert standardized documentation comments onto C++ (GoogleTest) and Swift
(XCTest / Swift Testing) test cases.

This is the ``macos`` preset's variant: that preset ships both a C++ core and a
Swift application layer, so one codemod covers both test languages. It
dispatches on file extension - ``.cpp``/``.cc``/``.cxx`` files are scanned for
GoogleTest macros and get a ``/** ... */`` Doxygen comment; ``.swift`` files
are scanned for XCTest ``func testXxx()`` methods and Swift Testing ``@Test``
functions and get a ``///`` DocC comment. The comment *content* (title regex,
Scenario / Boundaries / On-failure stanzas, classification model) is identical
across both languages so a reader - and ``test-documenter`` - sees one scheme.

For every ``TEST``/``TEST_F``/``TEST_P``/``TYPED_TEST``/``TYPED_TEST_P`` macro
invocation, ``func test...()`` XCTest method, or ``@Test`` function found under
a target directory, generates a comment that classifies the test as one of
``Unit``, ``Mock``, ``Integration``, or ``E2E`` and fills a fixed narrative
template derived mechanically from the test's suite name, test name, and body -
no test logic is read for "meaning", only scanned for structural signals
(mocking, subprocess/end-to-end runners, directory placement).

There is no C++ or Swift equivalent of Python's ``ast`` module in the stdlib,
so this codemod is regex- and brace-counting-based rather than AST-based. It is
a best-effort heuristic, same spirit as ``document_tests.py`` in the ``python``
preset, not a parser: unusual formatting (a macro invocation or attribute split
across many lines, braces inside a raw string literal used as a test-body
delimiter) can confuse it. When in doubt it flags a test ``ambiguous`` rather
than guessing silently - see the ``document-tests`` skill for how those are
hand-resolved.

Classification heuristic (path/filename-first, body-refined):

- path contains an ``e2e`` or ``*UITests`` directory, or the filename ends
  ``_e2e_test.cpp``/``_e2e_test.cc``/``E2ETests.swift``/``UITests.swift``
  -> ``E2E`` (end-to-end suite by convention).
- else path contains an ``integration``/``*IntegrationTests`` directory, or the
  filename ends ``_integration_test.cpp``/``_integration_test.cc``/``IT.cpp``/
  ``IT.cc``/``IntegrationTests.swift`` (Maven-Failsafe-style convention some
  repos borrow):
    - body uses an end-to-end marker (a spawned subprocess, a real HTTP/gRPC
      client, a socket) -> ``E2E``
    - else -> ``Integration``
- else path contains a ``unit``/``test``/``tests`` directory, or a directory
  whose name ends in ``Tests`` (SwiftPM's ``Tests/FooTests/``, Xcode's
  ``FooTests/``) (or unrecognised layout):
    - body uses an end-to-end marker -> ``E2E``
    - body uses a GoogleMock marker -> ``Mock``
    - else -> ``Unit``
    - tests in an unrecognised directory are additionally flagged
      ``ambiguous`` for human/agent review, since no directory convention
      backs the guess.

A generated comment (Doxygen or DocC) is recognisable by its first content line matching
``r"^\\[(Unit|Mock|Integration|E2E)\\] .+: verifies .+\\.$"``. Re-running this
script re-generates (and overwrites) only comments matching that pattern, so
it is safe to run repeatedly as tests change. A pre-existing hand-written
comment that does NOT match the pattern is left alone and reported as
skipped, unless ``--force`` is passed.

Usage::

    python scripts/document_tests.py                     # scan the whole repo
    python scripts/document_tests.py tests/unit           # scope to a directory
    python scripts/document_tests.py Tests/FooTests       # a Swift test target
    python scripts/document_tests.py --check              # report only, no writes
    python scripts/document_tests.py --force              # overwrite hand-written comments too

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
    ".idea",
    "build",
    "out",
    "_deps",
    "node_modules",
    "vcpkg_installed",
    ".cache",
    # Swift / Xcode build and dependency output.
    ".build",
    ".swiftpm",
    "DerivedData",
    "SourcePackages",
    "Pods",
    "Carthage",
    "xcuserdata",
}
# Prefixes for generated out-of-source build directories (CLion's convention
# among others), which don't fit a fixed-name exclusion set.
EXCLUDED_DIR_PREFIXES = ("cmake-build",)

CLASSIFICATIONS = ("Unit", "Mock", "Integration", "E2E")

_GENERATED_TITLE_RE = re.compile(r"^\[(Unit|Mock|Integration|E2E)\] .+: verifies .+\.$")

_E2E_BODY_MARKERS = (
    "std::system(",
    " system(",
    "popen(",
    "fork(",
    "execve(",
    "boost::process",
    "subprocess::",
    "curl_easy_",
    "httplib::client",
    "grpc::createchannel",
    "::socket(",
)
_MOCK_BODY_MARKERS = (
    "mock_method",
    "expect_call(",
    "nicemock<",
    "strictmock<",
    "on_call(",
    "::testing::mock",
    "returnref(",
    "willonce(",
    "willrepeatedly(",
)

# Swift has no mocking framework in the standard toolchain, so mock detection is
# a naming-convention heuristic (MockFoo / FakeFoo / StubFoo / SpyFoo). The text
# is lower-cased before matching.
_SWIFT_E2E_BODY_MARKERS = (
    "process()",
    "nstask",
    "xcuiapplication",
    "urlsession.shared",
    "urlsession(configuration",
    "posix_spawn",
    "nwconnection",
    "nwlistener",
    "executableurl",
)
_SWIFT_MOCK_BODY_MARKERS = (
    "mock",
    "fake",
    "stub",
    "spy",
)

_CPP_SUFFIXES = (".cpp", ".cc", ".cxx")
_SWIFT_SUFFIX = ".swift"

_TEST_START_RE = re.compile(r"^([ \t]*)\b(TEST_P|TEST_F|TYPED_TEST_P|TYPED_TEST|TEST)\s*\(")
_MACRO_RE = re.compile(
    r"\b(TEST_P|TEST_F|TYPED_TEST_P|TYPED_TEST|TEST)\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*\)",
    re.S,
)


_SWIFT_FUNC_RE = re.compile(
    r"^[ \t]*(?:@\w+(?:\([^)]*\))?\s+)*"
    r"(?:(?:public|internal|private|fileprivate|open|final|override|static|class|nonisolated|mutating)\s+)*"
    r"func\s+([A-Za-z_]\w*)\s*[(<]"
)
_SWIFT_XCTEST_FUNC_RE = re.compile(r"\bfunc\s+(test\w*)\s*\(\s*\)")
_SWIFT_TYPE_RE = re.compile(
    r"^[ \t]*(?:@\w+(?:\([^)]*\))?\s+)*"
    r"(?:(?:public|internal|private|fileprivate|open|final)\s+)*"
    r"(?:class|struct|actor|extension)\s+([A-Za-z_]\w*)"
)
_SWIFT_TEST_ATTR_RE = re.compile(r"@Test\b")


def _display_path(file_path: Path) -> str:
    try:
        return str(file_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(file_path)


@dataclass
class TestCase:
    """One discovered test case (GoogleTest macro, XCTest method, or Swift Testing
    ``@Test`` function) and its rendered doc comment."""

    file_path: Path
    qualname: str
    test_name: str
    classification: str
    ambiguous: bool
    insert_line: int  # 0-indexed line to insert before (the top of the macro invocation)
    delete_start: Optional[int]  # 0-indexed inclusive start of an existing generated comment
    delete_end: Optional[int]  # 0-indexed inclusive end of an existing generated comment
    skip_custom_docstring: bool
    indent: str
    rendered: str = field(default="")


def _humanize(identifier: str) -> str:
    name = re.sub(r"^(test_?|Test)", "", identifier)
    name = name.replace("_", " ")
    words: list[str] = []
    for chunk in name.split():
        words.extend(re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+", chunk))
    return " ".join(w.lower() for w in words) if words else name.lower()


def _humanize_suite(suite_name: str) -> str:
    name = re.sub(r"(Tests?|TestSuite|TestCase|Fixture|IT)$", "", suite_name)
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+", name)
    return " ".join(w.lower() for w in words) if words else suite_name.lower()


def _context_label(file_path: Path, suite_name: str) -> str:
    return _humanize_suite(suite_name) if suite_name else _humanize_suite(file_path.stem)


def _params_line(macro: str) -> str:
    if macro == "TEST_P":
        return "GetParam()"
    if macro == "TYPED_TEST_P":
        return "TypeParam"
    return "none"


def _extract_body(lines: list[str], brace_line: int, char_literals: bool = True) -> str:
    """Brace-count from the first ``{`` at/after ``brace_line`` to its match.

    Ignores string/char literal and comment contents on a best-effort basis
    (not a full lexer) - good enough to keep an unrelated ``}`` inside a log
    message or a raw string literal from truncating the scan early in the
    common case. Swift has no ``'x'`` character literal (an apostrophe outside a
    string or comment never occurs), so Swift callers pass ``char_literals=False``.
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
            if ch == "'" and char_literals:
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
    is_swift = file_path.suffix == _SWIFT_SUFFIX
    e2e_markers = _SWIFT_E2E_BODY_MARKERS if is_swift else _E2E_BODY_MARKERS
    mock_markers = _SWIFT_MOCK_BODY_MARKERS if is_swift else _MOCK_BODY_MARKERS
    has_e2e_marker = any(marker in body_text for marker in e2e_markers)
    has_mock_marker = any(marker in body_text for marker in mock_markers)
    # SwiftPM/Xcode name test directories ``FooTests`` / ``FooUITests``.
    ui_dir = any(p.endswith("uitests") for p in parts)
    integration_dir = any(p.endswith("integrationtests") for p in parts)
    tests_dir = any(p.endswith("tests") for p in parts)

    if "e2e" in parts or ui_dir or stem.endswith(("_e2e_test", "E2ETest", "E2ETests", "UITests")):
        return "E2E", False

    if "integration" in parts or integration_dir or stem.endswith(("_integration_test", "IT", "IntegrationTests")):
        if has_e2e_marker:
            return "E2E", False
        return "Integration", False

    if parts & {"unit", "test", "tests"} or tests_dir:
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


def _render_doc_comment(indent: str, classification: str, context_label: str, test_name: str, params: str) -> str:
    subject = _humanize(test_name)

    lines = [
        f"{indent}/**",
        f"{indent} * [{classification}] {context_label}: verifies {subject}.",
        f"{indent} *",
        f"{indent} * Scenario:",
        f"{indent} *   - Given {params}",
        f"{indent} *   - When {test_name} executes the target flow",
        f"{indent} *   - Then the expected outcome for {subject} is confirmed",
        f"{indent} *",
        f"{indent} * Boundaries:",
        f"{indent} *   - Focus: {subject}",
        f"{indent} *   - Fixtures/params: {params}",
        f"{indent} *   - Scope: assertions and setup in this test case only",
        f"{indent} *",
        f"{indent} * On failure, first check:",
        f"{indent} *   - Assertion details tied to {subject}",
        f"{indent} *   - Fixture or mock setup used by this test",
        f"{indent} *   - Recent changes in code paths exercised by {context_label}",
        f"{indent} */",
    ]
    return "\n".join(lines)


def _existing_doc_comment_range(lines: list[str], top: int) -> tuple[Optional[int], Optional[int], Optional[str]]:
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

    i = 0
    while i < n:
        start_match = _TEST_START_RE.match(lines[i])
        if not start_match:
            i += 1
            continue

        top = i
        sig_lines: list[str] = []
        j = i
        while j < n:
            sig_lines.append(lines[j])
            if "{" in lines[j]:
                break
            j += 1
        else:
            i = top + 1
            continue

        sig_text = "\n".join(sig_lines)
        macro_match = _MACRO_RE.search(sig_text)
        if not macro_match:
            i = top + 1
            continue
        macro, suite_name, test_name = macro_match.group(1), macro_match.group(2), macro_match.group(3)

        indent = re.match(r"[ \t]*", lines[top]).group(0)
        del_start, del_end, existing_title = _existing_doc_comment_range(lines, top)
        skip_custom = existing_title is not None and not _GENERATED_TITLE_RE.match(existing_title)

        body_text = _extract_body(lines, j)
        classification, ambiguous = _classify(file_path, body_text)
        context_label = _context_label(file_path, suite_name)
        params = _params_line(macro)

        qualname = f"{suite_name}.{test_name}"
        rendered = _render_doc_comment(indent, classification, context_label, test_name, params)

        cases.append(
            TestCase(
                file_path=file_path,
                qualname=qualname,
                test_name=test_name,
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


def _render_swift_doc_comment(
    indent: str, classification: str, context_label: str, test_name: str, params: str
) -> str:
    """The DocC (``///``) twin of ``_render_doc_comment`` - same title regex,
    same stanzas, so one reader/agent understands both languages."""
    subject = _humanize(test_name)
    body = [
        f"[{classification}] {context_label}: verifies {subject}.",
        "",
        "Scenario:",
        f"  - Given {params}",
        f"  - When {test_name} executes the target flow",
        f"  - Then the expected outcome for {subject} is confirmed",
        "",
        "Boundaries:",
        f"  - Focus: {subject}",
        f"  - Fixtures/params: {params}",
        "  - Scope: assertions and setup in this test case only",
        "",
        "On failure, first check:",
        f"  - Assertion details tied to {subject}",
        "  - Fixture or test-double setup used by this test",
        f"  - Recent changes in code paths exercised by {context_label}",
    ]
    return "\n".join(f"{indent}///{(' ' + line) if line else ''}" for line in body)


def _swift_attribute_start(lines: list[str], k: int) -> Optional[int]:
    """If line ``k`` is (the end of) an attribute, return the line it starts on.

    Handles a single-line ``@Attr`` / ``@Attr(args)`` and a multi-line
    ``@Test(arguments: [...])`` whose parentheses balance within 8 lines.
    """
    if k < 0:
        return None
    if lines[k].lstrip().startswith("@"):
        return k
    if lines[k].rstrip().endswith((")", "]")):
        for m in range(k - 1, max(k - 9, -1), -1):
            if lines[m].lstrip().startswith("@"):
                joined = " ".join(lines[m : k + 1])
                if joined.count("(") == joined.count(")"):
                    return m
                return None
    return None


def _swift_doc_comment_range(lines: list[str], top: int) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """Contiguous ``///`` block directly above ``top``, else fall back to a
    ``/** */`` block via the shared C-style scan."""
    end = top - 1
    if end >= 0 and lines[end].strip().startswith("///"):
        start = end
        while start - 1 >= 0 and lines[start - 1].strip().startswith("///"):
            start -= 1
        first = lines[start].strip()[3:].strip()
        return start, end, first
    return _existing_doc_comment_range(lines, top)


def _swift_enclosing_type(lines: list[str], func_line: int) -> str:
    """Nearest preceding type/extension declaration with a smaller indent."""
    indent = len(lines[func_line]) - len(lines[func_line].lstrip())
    for k in range(func_line - 1, -1, -1):
        match = _SWIFT_TYPE_RE.match(lines[k])
        if match and (len(lines[k]) - len(lines[k].lstrip())) < indent:
            return match.group(1)
    return ""


def _collect_swift_file(file_path: Path, lines: list[str]) -> list[TestCase]:
    cases: list[TestCase] = []
    n = len(lines)
    i = 0
    while i < n:
        func_match = _SWIFT_FUNC_RE.match(lines[i])
        if not func_match:
            i += 1
            continue

        # Gather the attribute lines stacked directly above (or on) the func.
        top = i
        attr_text = lines[i]
        k = _swift_attribute_start(lines, i - 1)
        while k is not None:
            attr_text = lines[k] + "\n" + attr_text
            top = k
            k = _swift_attribute_start(lines, k - 1)

        func_name = func_match.group(1)
        is_swift_testing = bool(_SWIFT_TEST_ATTR_RE.search(attr_text))
        is_xctest = bool(_SWIFT_XCTEST_FUNC_RE.search(lines[i]))
        if not (is_swift_testing or is_xctest):
            i += 1
            continue

        j = i
        while j < n and "{" not in lines[j]:
            j += 1
        if j >= n:
            i += 1
            continue

        indent = re.match(r"[ \t]*", lines[top]).group(0)
        del_start, del_end, existing_title = _swift_doc_comment_range(lines, top)
        skip_custom = existing_title is not None and not _GENERATED_TITLE_RE.match(existing_title)

        body_text = _extract_body(lines, j, char_literals=False)
        classification, ambiguous = _classify(file_path, body_text)
        suite_name = _swift_enclosing_type(lines, i)
        context_label = _context_label(file_path, suite_name)
        params = "arguments" if "arguments:" in attr_text else "none"

        cases.append(
            TestCase(
                file_path=file_path,
                qualname=f"{suite_name}.{func_name}" if suite_name else func_name,
                test_name=func_name,
                classification=classification,
                ambiguous=ambiguous,
                insert_line=top,
                delete_start=del_start,
                delete_end=del_end,
                skip_custom_docstring=skip_custom,
                indent=indent,
                rendered=_render_swift_doc_comment(indent, classification, context_label, func_name, params),
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
            if out[case.delete_start : case.delete_end + 1] == rendered_lines:
                continue  # already up to date: not a change, so --check stays quiet
            out[case.delete_start : case.delete_end + 1] = rendered_lines
        else:
            out[case.insert_line : case.insert_line] = rendered_lines
        applied.append(case)
    return out, applied


def _excluded(candidate: Path) -> bool:
    parts = candidate.parts
    if EXCLUDED_DIRS & set(parts):
        return True
    return any(part.startswith(EXCLUDED_DIR_PREFIXES) for part in parts)


def _discover_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if target.name.endswith((*_CPP_SUFFIXES, _SWIFT_SUFFIX)) else []
    files: list[Path] = []
    for pattern in (
        "*_test.cpp",
        "*_test.cc",
        "*_test.cxx",
        "*Test.cpp",
        "*Tests.cpp",
        "*IT.cpp",
        "*IT.cc",
        # Swift: SwiftPM/Xcode name test files ``FooTests.swift`` / ``FooTest.swift``.
        "*Tests.swift",
        "*Test.swift",
        "*IT.swift",
    ):
        for candidate in target.rglob(pattern):
            if _excluded(candidate):
                continue
            files.append(candidate)
    return sorted(set(files))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", default=DEFAULT_TARGET, help="Test file or directory (default: whole repo)")
    parser.add_argument("--check", action="store_true", help="Report only; exit 1 if changes are pending")
    parser.add_argument("--force", action="store_true", help="Overwrite hand-written doc comments too")
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

        if file_path.suffix == _SWIFT_SUFFIX:
            cases = _collect_swift_file(file_path, lines)
        else:
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

    print(f"Scanned {len(files)} file(s), {sum(counts.values())} test case(s).")
    print("  " + "  ".join(f"[{c}] {n}" for c, n in counts.items()))
    verb = "would document" if args.check else "documented"
    print(f"{verb.capitalize()} {documented} test(s) across {changed_files} file(s).")
    if skipped_custom:
        print(f"Skipped (custom doc comment present, use --force to overwrite): {len(skipped_custom)}")
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

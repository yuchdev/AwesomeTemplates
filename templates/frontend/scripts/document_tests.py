"""Insert standardized JSDoc documentation comments onto JavaScript/TypeScript test cases.

For every ``it(...)``/``test(...)``/``specify(...)`` call (including the
``.only``/``.skip``/``.each`` variants shared by Vitest, Jest, Mocha, the Node.js
built-in runner, and Playwright Test) found under a target directory, generates
a JSDoc comment that classifies the test as one of ``Unit``, ``Mock``,
``Integration``, or ``E2E`` and fills a fixed narrative template (Scenario /
Boundaries / On-failure-first-check) derived mechanically from the test title,
its enclosing ``describe`` titles, and its body - no test logic is read for
"meaning", only scanned for structural signals (mocking, browser drivers,
directory placement).

The Python stdlib has no JavaScript parser, so this codemod is regex- and
paren-counting-based rather than AST-based, same spirit as ``document_tests.py``
in the ``cpp`` preset. Its small lexer skips string literals, template literals
(including nested ``${...}``), and comments, but not regex literals: a regex
containing an unbalanced ``(`` or a quote can confuse it. Only tests whose call
starts a line and whose title is a string literal are recognised. When in doubt
it flags a test ``ambiguous`` rather than guessing silently - see the
``document-tests`` skill for how those are hand-resolved.

Classification heuristic (path/filename-first, body-refined):

- path contains an ``e2e`` or ``cypress`` directory, or the filename has an
  ``.e2e.`` segment (``login.e2e.spec.ts``) -> ``E2E``.
- else path contains an ``integration`` directory, or the filename has an
  ``.integration.``/``.int.`` segment:
    - body drives a real browser (``page.goto(``, ``cy.visit(``, a Playwright
      ``({ page })`` fixture, ...) -> ``E2E``
    - else -> ``Integration``
- else the file sits in a ``unit``/``test``/``tests``/``__tests__``/``spec``
  directory, or is a ``*.test.*`` file anywhere (the co-located convention):
    - body drives a real browser -> ``E2E``
    - body, or module scope, uses a mocking marker -> ``Mock``
    - else -> ``Unit``
- else (a ``*.spec.*`` file outside any test directory): same body-based
  cascade, additionally flagged ``ambiguous`` - that suffix means "Playwright
  browser test" in some projects and "Vitest/Jasmine unit test" in others, so
  no convention backs the guess.

Module-scope mocks count for every test in the file: Vitest and Jest hoist
``vi.mock()``/``jest.mock()`` above the imports, so they are almost never
inside the test body the way a GoogleMock ``EXPECT_CALL`` is.

A generated JSDoc comment is recognisable by its first content line matching
``r"^\\[(Unit|Mock|Integration|E2E)\\] .+: verifies .+\\.$"``. Re-running this
script re-generates only comments matching that pattern, and leaves one that
is already up to date untouched, so it is safe to run repeatedly as tests
change and ``--check`` exits ``0`` on a fully documented suite. A pre-existing
hand-written comment that does NOT match the pattern is left alone and
reported as skipped, unless ``--force`` is passed.

Usage::

    python scripts/document_tests.py                     # scan the whole repo
    python scripts/document_tests.py tests/unit           # scope to a directory
    python scripts/document_tests.py --check              # report only, no writes
    python scripts/document_tests.py --force              # overwrite hand-written comments too

Exit status is ``1`` in ``--check`` mode when any test would change, else ``0``.
"""

from __future__ import annotations

import argparse
import bisect
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
    ".vscode",
    ".cache",
    ".next",
    ".nuxt",
    ".output",
    ".svelte-kit",
    ".vite",
    ".turbo",
    "node_modules",
    "bower_components",
    "dist",
    "build",
    "out",
    "coverage",
    "playwright-report",
    "test-results",
    "storybook-static",
}

TEST_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")

CLASSIFICATIONS = ("Unit", "Mock", "Integration", "E2E")

_GENERATED_TITLE_RE = re.compile(r"^\[(Unit|Mock|Integration|E2E)\] .+: verifies .+\.$")

# Matched against the lowercased text of one test call.
_E2E_BODY_MARKERS = (
    "({ page",
    "page.goto(",
    "page.locator(",
    "page.getbyrole(",
    "page.click(",
    "page.fill(",
    "cy.visit(",
    "cy.get(",
    "browser.url(",
    "browser.newpage(",
    "puppeteer.launch(",
)
_MOCK_BODY_MARKERS = (
    "vi.fn(",
    "vi.spyon(",
    "vi.usefaketimers(",
    "vi.stubglobal(",
    "jest.fn(",
    "jest.spyon(",
    "jest.usefaketimers(",
    "mock.fn(",
    "mock.method(",
    "mock.timers",
    "sinon.",
    "server.use(",
    "nock(",
    "fetchmock",
    "mockresolvedvalue",
    "mockreturnvalue",
    "mockimplementation",
)
# Matched against the lowercased text of the whole file: these calls apply to
# every test in the file even though they sit at module scope.
_MODULE_MOCK_MARKERS = (
    "vi.mock(",
    "vi.domock(",
    "jest.mock(",
    "jest.unstable_mockmodule(",
    "setupserver(",
    "setupworker(",
)

_MODIFIERS = r"(?:\.(?:only|skip|todo|concurrent|sequential|serial|parallel|fails|fixme|slow))*"
_TEST_START_RE = re.compile(rf"^([ \t]*)(?:test|it|specify){_MODIFIERS}(\.each)?\s*[(`]", re.M)
_DESCRIBE_START_RE = re.compile(
    rf"^([ \t]*)(?:describe|context|suite|test\.describe){_MODIFIERS}(\.each)?\s*[(`]", re.M
)

_CLOSERS = {"(": ")", "[": "]", "{": "}"}


def _display_path(file_path: Path) -> str:
    try:
        return str(file_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(file_path)


@dataclass
class TestCase:
    """One discovered test call and its rendered JSDoc comment."""

    file_path: Path
    qualname: str
    classification: str
    ambiguous: bool
    insert_line: int  # 0-indexed line to insert before (the line the test call starts on)
    delete_start: Optional[int]  # 0-indexed inclusive start of an existing generated comment
    delete_end: Optional[int]  # 0-indexed inclusive end of an existing generated comment
    skip_custom_docstring: bool
    rendered: str = field(default="")


# --- a minimal JavaScript lexer: strings, template literals, comments --------


def _skip_string(src: str, i: int) -> int:
    """``src[i]`` is ``'`` or ``"``; return the index just past its closing quote."""
    quote = src[i]
    j = i + 1
    while j < len(src):
        ch = src[j]
        if ch == "\\":
            j += 2
            continue
        if ch == quote or ch == "\n":  # a newline ends an unterminated literal
            return j + 1
        j += 1
    return len(src)


def _skip_template(src: str, i: int) -> int:
    """``src[i]`` is a backtick; return the index just past the closing backtick."""
    j = i + 1
    while j < len(src):
        ch = src[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "`":
            return j + 1
        if src.startswith("${", j):
            end = _match_close(src, j + 1)
            j = end if end is not None else len(src)
            continue
        j += 1
    return len(src)


def _match_close(src: str, i: int) -> Optional[int]:
    """``src[i]`` is ``(``, ``[``, or ``{``; return the index just past its
    matching closer, or None if the file ends first."""
    stack = [_CLOSERS[src[i]]]
    j = i + 1
    n = len(src)
    while j < n:
        ch = src[j]
        if ch in "'\"":
            j = _skip_string(src, j)
            continue
        if ch == "`":
            j = _skip_template(src, j)
            continue
        if src.startswith("//", j):
            newline = src.find("\n", j)
            j = n if newline == -1 else newline
            continue
        if src.startswith("/*", j):
            close = src.find("*/", j + 2)
            j = n if close == -1 else close + 2
            continue
        if ch in _CLOSERS:
            stack.append(_CLOSERS[ch])
        elif ch in ")]}":
            stack.pop()  # best effort: a mismatched closer still closes something
            if not stack:
                return j + 1
        j += 1
    return None


def _skip_ws(src: str, i: int) -> int:
    while i < len(src) and src[i].isspace():
        i += 1
    return i


def _read_title(src: str, i: int) -> tuple[Optional[str], int]:
    """Read the string-literal title starting at (or after whitespace from)
    ``src[i]``. Returns (title, index past it), or (None, i) when the first
    argument is not a literal."""
    i = _skip_ws(src, i)
    if i >= len(src) or src[i] not in "'\"`":
        return None, i
    end = _skip_template(src, i) if src[i] == "`" else _skip_string(src, i)
    return src[i + 1 : end - 1], end


@dataclass
class _Call:
    start: int  # offset of the callee's first character
    open_paren: int  # offset of the "(" holding the title and callback
    end: int  # offset just past the matching ")"
    title: str
    parameterized: bool


def _parse_calls(src: str, pattern: re.Pattern[str]) -> list[_Call]:
    calls: list[_Call] = []
    for m in pattern.finditer(src):
        start = m.start() + len(m.group(1))
        pos = m.end() - 1  # at the "(" or backtick that ended the match
        parameterized = m.group(2) is not None
        if parameterized:
            # `.each([...])(title, fn)` or `.each`table`(title, fn)` - skip the table.
            table_end = _skip_template(src, pos) if src[pos] == "`" else _match_close(src, pos)
            if table_end is None:
                continue
            pos = _skip_ws(src, table_end)
        if pos >= len(src) or src[pos] != "(":
            continue
        end = _match_close(src, pos)
        if end is None:
            continue
        title, _ = _read_title(src, pos + 1)
        if title is None:
            continue
        calls.append(_Call(start=start, open_paren=pos, end=end, title=title, parameterized=parameterized))
    return calls


# --- classification and rendering -------------------------------------------


def _relative_parts(file_path: Path) -> list[str]:
    try:
        rel = file_path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        rel = file_path
    return [p.lower() for p in rel.parent.parts]


def _classify(file_path: Path, call_text: str, file_text: str) -> tuple[str, bool]:
    parts = set(_relative_parts(file_path))
    segments = set(file_path.name.lower().split(".")[1:-1])
    has_e2e_marker = any(marker in call_text for marker in _E2E_BODY_MARKERS)
    has_mock_marker = any(marker in call_text for marker in _MOCK_BODY_MARKERS) or any(
        marker in file_text for marker in _MODULE_MOCK_MARKERS
    )

    if parts & {"e2e", "cypress"} or "e2e" in segments:
        return "E2E", False

    if "integration" in parts or segments & {"integration", "int"}:
        if has_e2e_marker:
            return "E2E", False
        return "Integration", False

    if parts & {"unit", "test", "tests", "__tests__", "spec", "specs"} or "test" in segments:
        if has_e2e_marker:
            return "E2E", False
        if has_mock_marker:
            return "Mock", False
        return "Unit", False

    # A *.spec.* file outside any test directory: best-effort cascade, flagged for review.
    if has_e2e_marker:
        return "E2E", True
    if has_mock_marker:
        return "Mock", True
    return "Unit", True


def _clean(text: str) -> str:
    """Collapse a title to one comment-safe line."""
    text = re.sub(r"\s+", " ", text).strip().replace("*/", "* /")
    return text.rstrip(".!?;:") or "the test case"


def _humanize_stem(file_path: Path) -> str:
    stem = file_path.name.split(".")[0]
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+", stem)
    return " ".join(w.lower() for w in words) if words else stem.lower()


def _render_doc_comment(indent: str, classification: str, context_label: str, subject: str, params: str) -> str:
    lines = [
        f"{indent}/**",
        f'{indent} * [{classification}] {context_label}: verifies "{subject}".',
        f"{indent} *",
        f"{indent} * Scenario:",
        f"{indent} *   - Given the setup in this test and its enclosing describe blocks",
        f'{indent} *   - When the "{subject}" case executes the target flow',
        f"{indent} *   - Then the expected outcome for {subject} is confirmed",
        f"{indent} *",
        f"{indent} * Boundaries:",
        f"{indent} *   - Focus: {subject}",
        f"{indent} *   - Fixtures/params: {params}",
        f"{indent} *   - Scope: assertions and setup in this test case only",
        f"{indent} *",
        f"{indent} * On failure, first check:",
        f"{indent} *   - Assertion details tied to {subject}",
        f"{indent} *   - Fixture, mock, or page setup used by this test",
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


def _collect_file(file_path: Path, src: str) -> list[TestCase]:
    lines = src.split("\n")
    line_starts = [0]
    for line in lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)
    file_text = src.lower()

    describes = _parse_calls(src, _DESCRIBE_START_RE)
    cases: list[TestCase] = []
    for call in _parse_calls(src, _TEST_START_RE):
        top = bisect.bisect_right(line_starts, call.start) - 1
        indent = re.match(r"[ \t]*", lines[top]).group(0)

        chain = [_clean(d.title) for d in describes if d.start < call.start and call.end <= d.end]
        subject = _clean(call.title)
        context_label = " > ".join(chain) if chain else _humanize_stem(file_path)
        params = "each-table rows (parameterized)" if call.parameterized else "none"

        classification, ambiguous = _classify(file_path, src[call.open_paren : call.end].lower(), file_text)
        del_start, del_end, existing_title = _existing_doc_comment_range(lines, top)
        skip_custom = existing_title is not None and not _GENERATED_TITLE_RE.match(existing_title)

        cases.append(
            TestCase(
                file_path=file_path,
                qualname=" > ".join([*chain, subject]),
                classification=classification,
                ambiguous=ambiguous,
                insert_line=top,
                delete_start=del_start,
                delete_end=del_end,
                skip_custom_docstring=skip_custom,
                rendered=_render_doc_comment(indent, classification, context_label, subject, params),
            )
        )
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
                continue  # already up to date - not a pending change
            out[case.delete_start : case.delete_end + 1] = rendered_lines
        else:
            out[case.insert_line : case.insert_line] = rendered_lines
        applied.append(case)
    return out, applied


def _is_test_file(path: Path) -> bool:
    if not path.name.endswith(TEST_EXTENSIONS):
        return False
    segments = set(path.name.lower().split(".")[1:-1])
    parts = set(_relative_parts(path))
    stem = path.stem.lower()
    if parts & {"test", "tests", "__tests__", "spec", "specs", "unit", "integration", "e2e", "cypress"}:
        return True
    if stem in {"test", "spec", "integration", "int", "e2e"}:
        return True
    return bool(segments & {"test", "spec", "integration", "int", "e2e"})


def _discover_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if _is_test_file(target) else []
    files = [
        candidate
        for candidate in target.rglob("*")
        if candidate.is_file() and not EXCLUDED_DIRS & set(candidate.parts) and _is_test_file(candidate)
    ]
    return sorted(files)


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
        cases = _collect_file(file_path, source)
        if not cases:
            continue

        for case in cases:
            counts[case.classification] += 1
            rel = f"{_display_path(file_path)}::{case.qualname}"
            if case.ambiguous:
                ambiguous.append(rel)
            if case.skip_custom_docstring:
                skipped_custom.append(rel)

        new_lines, applied = _apply_edits(source.split("\n"), cases, args.force)
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

"""Run the simple-code checks from the command line or a hook."""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

from rules import (
    MAX_CODE_LINES,
    MAX_MARKDOWN_WORDS,
    OTHER_CODE_SUFFIXES,
    SKIPPED_FOLDERS,
    Finding,
    Severity,
    check_comment_length,
    check_core_purity,
    check_docstring_length,
    check_docstring_presence,
    check_names,
    run_ruff,
)
from typescript_rules import TYPESCRIPT_SUFFIXES, check_typescript, run_eslint

CHECKED_SUFFIXES = {".py", ".md"} | TYPESCRIPT_SUFFIXES | OTHER_CODE_SUFFIXES


def check_python(path: str, source: str) -> list[Finding]:
    """Run every Python check on one file's source."""
    try:
        tree = ast.parse(source)
    except SyntaxError as syntax_error:
        line = syntax_error.lineno or 1
        return [Finding(path, line, "syntax", str(syntax_error), Severity.FAIL)]
    findings = check_comment_length(path, source)
    for check in (check_docstring_length, check_docstring_presence, check_names, check_core_purity):
        findings += check(path, tree)
    line_count = len(source.splitlines())
    if line_count > MAX_CODE_LINES:
        message = f"file has {line_count} lines; consider splitting past {MAX_CODE_LINES}"
        findings.append(Finding(path, 1, "file-length", message, Severity.WARN))
    return findings + run_ruff(path)


def check_markdown(path: str, text: str) -> list[Finding]:
    """Warn when user-facing Markdown runs past the word limit."""
    if ".claude" in Path(path).parts:
        return []
    word_count = len(text.split())
    if word_count <= MAX_MARKDOWN_WORDS:
        return []
    message = f"document has {word_count} words; consider splitting past {MAX_MARKDOWN_WORDS}"
    return [Finding(path, 1, "document-length", message, Severity.WARN)]


def check_other_code(path: str, text: str) -> list[Finding]:
    """Warn when a file in a language without a pack runs long."""
    line_count = len(text.splitlines())
    if line_count <= MAX_CODE_LINES:
        return []
    message = f"file has {line_count} lines; consider splitting past {MAX_CODE_LINES}"
    return [Finding(path, 1, "file-length", message, Severity.WARN)]


def check_file(path: Path) -> list[Finding]:
    """Dispatch one file to the checks for its type."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        return check_python(str(path), text)
    if path.suffix == ".md":
        return check_markdown(str(path), text)
    if path.suffix in TYPESCRIPT_SUFFIXES:
        return check_typescript(str(path), text)
    return check_other_code(str(path), text)


def collect_files(targets: list[str]) -> list[Path]:
    """Expand files and folders into the checkable files inside."""
    files = []
    for target in map(Path, targets):
        if target.is_file():
            files.append(target)
            continue
        for folder, subfolders, names in os.walk(target):
            subfolders[:] = sorted(set(subfolders) - SKIPPED_FOLDERS)
            files += [Path(folder, name) for name in sorted(names) if Path(name).suffix in CHECKED_SUFFIXES]
    return files


def check_files(paths: list[Path]) -> list[Finding]:
    """Run every check on these files, with ESLint batched."""
    findings = run_eslint([str(path) for path in paths if path.suffix in TYPESCRIPT_SUFFIXES])
    for path in paths:
        findings += check_file(path)
    return findings


def run_as_hook() -> int:
    """Check the file Claude just edited and report back through the hook."""
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path or Path(file_path).suffix not in CHECKED_SUFFIXES or not Path(file_path).is_file():
        return 0
    findings = check_files([Path(file_path)])
    failures = [finding for finding in findings if finding.severity is Severity.FAIL]
    report = "\n".join(finding.render() for finding in findings)
    if failures:
        print(f"simple-code checks failed; fix before continuing:\n{report}", file=sys.stderr)
        return 2
    if findings:
        context = {"hookEventName": "PostToolUse", "additionalContext": report}
        print(json.dumps({"hookSpecificOutput": context}))
    return 0


def run_as_command(targets: list[str]) -> int:
    """Check files or folders and print a pass or fail report."""
    findings = check_files(collect_files(targets or ["."]))
    for finding in findings:
        print(finding.render())
    failure_count = sum(finding.severity is Severity.FAIL for finding in findings)
    warning_count = len(findings) - failure_count
    verdict = "FAIL" if failure_count else "PASS"
    print(f"{verdict}: {failure_count} failures, {warning_count} warnings")
    return 1 if failure_count else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--hook"]:
        sys.exit(run_as_hook())
    sys.exit(run_as_command(sys.argv[1:]))

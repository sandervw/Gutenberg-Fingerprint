"""TypeScript and JavaScript checks for the simple-code rules."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from rules import MAX_CODE_LINES, MAX_COMMENT_WORDS, Finding, Severity

TYPESCRIPT_SUFFIXES = {".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"}
ESLINT_CONFIG = Path(__file__).resolve().parent.parent / "eslint.config.mjs"
QUOTES = {"'", '"', "`"}
EXPORT_PATTERN = re.compile(
    r"export\s+(default\s+)?(declare\s+)?(async\s+)?(abstract\s+)?(function|class)\b"
    r"|export\s+(const|let)\s+\w+\s*(:[^=]+)?=\s*(async\s+)?(function\b|\(|<|\w+\s*=>)"
    r"|export\s+default\s+\{"
)


def line_at(source: str, position: int) -> int:
    """Return the one-based line number of a character position."""
    return source.count("\n", 0, position) + 1


def skip_string(source: str, position: int) -> int:
    """Return the position just past the string starting here."""
    quote = source[position]
    position += 1
    while position < len(source):
        character = source[position]
        if character == "\\":
            position += 2
            continue
        if character == quote:
            return position + 1
        if character == "\n" and quote != "`":
            return position
        position += 1
    return position


def starts_line_comment(source: str, position: int) -> bool:
    """Return true for a line comment, but not a URL's double slash."""
    is_slashes = source.startswith("//", position)
    return is_slashes and (position == 0 or source[position - 1] != ":")


def find_comments(source: str) -> list[tuple[int, str]]:
    """Return (line, text) for every comment, skipping string contents."""
    comments = []
    position = 0
    while position < len(source):
        if source[position] in QUOTES:
            position = skip_string(source, position)
        elif starts_line_comment(source, position):
            end = source.find("\n", position)
            end = len(source) if end == -1 else end
            comments.append((line_at(source, position), source[position + 2 : end]))
            position = end
        elif source.startswith("/*", position):
            end = source.find("*/", position + 2)
            end = len(source) if end == -1 else end
            comments.append((line_at(source, position), source[position + 2 : end]))
            position = end + 2
        else:
            position += 1
    return comments


def check_comment_length(path: str, source: str) -> list[Finding]:
    """Fail any comment or JSDoc block longer than the word limit."""
    findings = []
    for line, text in find_comments(source):
        word_count = len(text.replace("*", " ").split())
        if word_count > MAX_COMMENT_WORDS:
            message = f"comment has {word_count} words; limit is {MAX_COMMENT_WORDS}"
            findings.append(Finding(path, line, "comment-length", message, Severity.FAIL))
    return findings


def has_jsdoc_above(lines: list[str], index: int) -> bool:
    """Return true when a JSDoc block sits directly above this line."""
    cursor = index - 1
    while cursor >= 0 and (not lines[cursor].strip() or lines[cursor].strip().startswith("@")):
        cursor -= 1
    if cursor < 0 or not lines[cursor].rstrip().endswith("*/"):
        return False
    while cursor >= 0 and "/*" not in lines[cursor]:
        cursor -= 1
    return cursor >= 0 and "/**" in lines[cursor]


def check_jsdoc_presence(path: str, source: str) -> list[Finding]:
    """Fail exported functions, classes, and default objects without JSDoc."""
    findings = []
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if not EXPORT_PATTERN.match(line) or has_jsdoc_above(lines, index):
            continue
        message = "export needs one short /** JSDoc */ comment"
        findings.append(Finding(path, index + 1, "docstring-missing", message, Severity.FAIL))
    return findings


def find_eslint(path: str) -> tuple[str, Path] | None:
    """Return the project's eslint executable and folder, searching upward."""
    for folder in Path(path).resolve().parents:
        binary_folder = folder / "node_modules" / ".bin"
        executable = shutil.which("eslint", path=str(binary_folder)) if binary_folder.is_dir() else None
        if executable:
            return executable, folder
    return None


def convert_eslint_message(path: str, message: dict) -> Finding:
    """Turn one ESLint message into a finding with a readable text."""
    rule_id = message.get("ruleId") or "eslint"
    text = message["message"]
    if rule_id == "@typescript-eslint/naming-convention":
        text = text.split(" must not match")[0] + " uses a short form; spell it out"
    severity = Severity.FAIL if message.get("severity") == 2 else Severity.WARN
    return Finding(path, message.get("line", 1), f"eslint {rule_id}", text, severity)


def run_eslint(paths: list[str]) -> list[Finding]:
    """Run ESLint once per project folder and convert its findings."""
    projects: dict[tuple[str, Path], list[str]] = {}
    findings = []
    for path in (path for path in paths if not path.endswith(".d.ts")):
        located = find_eslint(path)
        if located is None:
            findings.append(Finding(path, 1, "eslint", "eslint is not installed; lint checks skipped", Severity.WARN))
        else:
            projects.setdefault(located, []).append(path)
    for (executable, project_folder), project_paths in projects.items():
        findings += lint_project(executable, project_folder, project_paths)
    return findings


def lint_project(executable: str, project_folder: Path, paths: list[str]) -> list[Finding]:
    """Run ESLint once from one project folder over its files."""
    linted = {str(Path(path).resolve()): path for path in paths}
    first_path = paths[0]
    relative = [os.path.relpath(path, project_folder) for path in linted]
    command = [executable, "--config", str(ESLINT_CONFIG), "--format", "json", "--no-warn-ignored", *relative]
    result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=project_folder)
    if result.returncode not in (0, 1):
        message = f"eslint could not run: {result.stderr.strip()[:200]}"
        return [Finding(first_path, 1, "eslint", message, Severity.FAIL)]
    findings = []
    for report in json.loads(result.stdout or "[]"):
        path = linted.get(report["filePath"], report["filePath"])
        findings += [convert_eslint_message(path, message) for message in report["messages"]]
    return findings


def check_typescript(path: str, source: str) -> list[Finding]:
    """Run every TypeScript check except ESLint on one file's source."""
    if path.endswith(".d.ts"):
        return []
    findings = check_comment_length(path, source) + check_jsdoc_presence(path, source)
    line_count = len(source.splitlines())
    if line_count > MAX_CODE_LINES:
        message = f"file has {line_count} lines; consider splitting past {MAX_CODE_LINES}"
        findings.append(Finding(path, 1, "file-length", message, Severity.WARN))
    return findings

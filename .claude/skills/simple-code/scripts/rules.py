"""Settings and individual checks for the simple-code rules."""
from __future__ import annotations

import ast
import io
import json
import re
import shutil
import subprocess
import tokenize
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Edit these settings to fit the repository.
MAX_COMMENT_WORDS = 12
MAX_CODE_LINES = 300
MAX_MARKDOWN_WORDS = 700
ALLOWED_SHORT_NAMES = {"id", "url", "api"}
EXEMPT_NAMES = {"self", "_"}
SMALL_WORDS = {
    "a", "an", "as", "at", "be", "by", "do", "go", "if", "in", "is",
    "it", "me", "my", "no", "of", "on", "or", "so", "to", "up", "we",
}
BANNED_WORDS = {
    "acc", "addr", "arg", "args", "attr", "attrs", "avg", "btn", "buf",
    "calc", "cfg", "cls", "cmd", "cnt", "conf", "conn", "csv", "ctx",
    "cur", "curr", "desc", "dest", "dict", "dir", "doc", "dst", "elem",
    "env", "err", "evt", "exc", "exe", "expr", "fmt", "func", "gen",
    "hdr", "html", "http", "https", "idx", "img", "impl", "init", "iter",
    "json", "kwargs", "len", "lib", "lst", "mgr", "msg", "num", "obj",
    "opt", "opts", "param", "params", "pkg", "pos", "prev", "proc",
    "prop", "ptr", "pwd", "qty", "recv", "ref", "req", "res", "resp",
    "ret", "seq", "sql", "src", "srv", "str", "tmp", "txt", "usr",
    "util", "utils", "uuid", "val", "vals", "var", "vars", "xml",
}
CORE_FOLDER_NAMES = {"core"}
CORE_FORBIDDEN_IMPORTS = {
    "sqlite3", "requests", "httpx", "urllib", "socket", "subprocess",
    "shutil", "pyodbc", "psycopg2", "sqlalchemy", "boto3", "random",
}
CORE_FORBIDDEN_CALLS = {"open", "print", "input"}
CORE_FORBIDDEN_METHODS = {"now", "today", "utcnow"}
SKIPPED_FOLDERS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "dist",
    "build", "target", "coverage", "playwright-report", "test-results",
    "vendor", "worktrees",
}
OTHER_CODE_SUFFIXES = {
    ".c", ".h", ".cc", ".cpp", ".hpp", ".rs", ".go", ".java", ".kt",
    ".cs", ".swift", ".rb", ".lua", ".sh", ".sql", ".zig", ".dart",
}
RUFF_CONFIG = Path(__file__).resolve().parent.parent / "ruff.toml"
WORD_PATTERN = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")


class Severity(Enum):
    """Whether a finding fails the check or only warns."""

    FAIL = "FAIL"
    WARN = "WARN"


@dataclass(frozen=True)
class Finding:
    """One rule violation at a file location."""

    path: str
    line: int
    rule: str
    message: str
    severity: Severity

    def render(self) -> str:
        """Format the finding as one report line."""
        location = f"{self.path}:{self.line}"
        return f"{self.severity.value} {location} [{self.rule}] {self.message}"


def check_comment_length(path: str, source: str) -> list[Finding]:
    """Fail any hash comment longer than the word limit."""
    findings = []
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        word_count = len(token.string.lstrip("#").split())
        if word_count > MAX_COMMENT_WORDS:
            message = f"comment has {word_count} words; limit is {MAX_COMMENT_WORDS}"
            findings.append(Finding(path, token.start[0], "comment-length", message, Severity.FAIL))
    return findings


def check_docstring_length(path: str, tree: ast.Module) -> list[Finding]:
    """Fail any docstring longer than the word limit."""
    findings = []
    documented = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, documented):
            continue
        docstring = ast.get_docstring(node)
        if docstring and len(docstring.split()) > MAX_COMMENT_WORDS:
            line = node.body[0].lineno
            message = f"docstring has {len(docstring.split())} words; limit is {MAX_COMMENT_WORDS}"
            findings.append(Finding(path, line, "docstring-length", message, Severity.FAIL))
    return findings


def check_docstring_presence(path: str, tree: ast.Module) -> list[Finding]:
    """Fail public module-level functions and classes without a docstring."""
    findings = []
    definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in tree.body:
        if not isinstance(node, definitions) or node.name.startswith("_"):
            continue
        if ast.get_docstring(node) is None:
            message = f"public '{node.name}' needs one short docstring"
            findings.append(Finding(path, node.lineno, "docstring-missing", message, Severity.FAIL))
    return findings


def is_self_attribute(node: ast.AST) -> bool:
    """Return true when the node assigns an attribute on self."""
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"


def defined_name(node: ast.AST) -> str | None:
    """Return the name this node defines, if the author chose one."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.arg):
        return node.arg
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        return node.id
    if is_self_attribute(node) and isinstance(node.ctx, ast.Store):
        return node.attr
    if isinstance(node, ast.ExceptHandler):
        return node.name
    if isinstance(node, ast.alias):
        return node.asname
    return None


def word_problem(word: str, word_count: int) -> str | None:
    """Explain why one word inside a name is not descriptive."""
    if word in ALLOWED_SHORT_NAMES:
        return None
    if word in BANNED_WORDS:
        return f"'{word}' is a short form; spell it out"
    if word in SMALL_WORDS and word_count > 1:
        return None
    if len(word) < 3:
        return f"'{word}' is too short to be descriptive"
    return None


def name_problem(name: str) -> str | None:
    """Explain why a name breaks the naming rule, or return None."""
    if name in EXEMPT_NAMES or (name.startswith("__") and name.endswith("__")):
        return None
    words = [word.lower() for word in WORD_PATTERN.findall(name) if not word.isdigit()]
    for word in words:
        problem = word_problem(word, len(words))
        if problem:
            return problem
    return None


def check_names(path: str, tree: ast.Module) -> list[Finding]:
    """Fail names that are abbreviated or too short."""
    findings = []
    reported = set()
    for node in ast.walk(tree):
        name = defined_name(node)
        if not name or name in reported:
            continue
        problem = name_problem(name)
        if problem:
            reported.add(name)
            line = getattr(node, "lineno", 1)
            findings.append(Finding(path, line, "naming", f"'{name}': {problem}", Severity.FAIL))
    return findings


def forbidden_call(call: ast.Call) -> str | None:
    """Return the side-effecting call name, if this call has one."""
    function = call.func
    if isinstance(function, ast.Name) and function.id in CORE_FORBIDDEN_CALLS:
        return function.id
    if isinstance(function, ast.Attribute) and function.attr in CORE_FORBIDDEN_METHODS:
        return function.attr
    is_clock = isinstance(function, ast.Attribute) and function.attr == "time"
    if is_clock and isinstance(function.value, ast.Name) and function.value.id == "time":
        return "time.time"
    return None


def imported_modules(node: ast.AST) -> list[str]:
    """Return top-level module names imported by this node."""
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module.split(".")[0]]
    return []


def check_core_purity(path: str, tree: ast.Module) -> list[Finding]:
    """Fail input, output, clock, or randomness inside core folders."""
    if not CORE_FOLDER_NAMES & set(Path(path).parts):
        return []
    findings = []
    for node in ast.walk(tree):
        for module in imported_modules(node):
            if module in CORE_FORBIDDEN_IMPORTS:
                message = f"core code imports '{module}'; move it to the shell"
                findings.append(Finding(path, node.lineno, "core-purity", message, Severity.FAIL))
        call_name = forbidden_call(node) if isinstance(node, ast.Call) else None
        if call_name:
            message = f"core code calls '{call_name}'; pass the result in instead"
            findings.append(Finding(path, node.lineno, "core-purity", message, Severity.FAIL))
    return findings


def run_ruff(path: str) -> list[Finding]:
    """Run ruff with the kit configuration and convert its findings."""
    ruff_executable = shutil.which("ruff")
    if ruff_executable is None:
        return [Finding(path, 1, "ruff", "ruff is not installed; ruff checks skipped", Severity.WARN)]
    command = [ruff_executable, "check", "--config", str(RUFF_CONFIG), "--no-cache"]
    command += ["--output-format", "json", "--exit-zero", path]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = f"ruff could not run: {result.stderr.strip()[:200]}"
        return [Finding(path, 1, "ruff", message, Severity.FAIL)]
    findings = []
    for violation in json.loads(result.stdout or "[]"):
        line = violation["location"]["row"]
        rule = f"ruff {violation['code']}"
        findings.append(Finding(path, line, rule, violation["message"], Severity.FAIL))
    return findings

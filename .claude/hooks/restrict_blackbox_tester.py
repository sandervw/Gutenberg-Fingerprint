"""Keep the blackbox-tester to use cases and black-box specs."""

# This is test isolation, not a security boundary.
# The specs the tester writes run as code with the user's rights.
# The hook also does nothing if `python` is missing.
# Its limits come from the blackbox block of .claude/project.json.

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from urllib.parse import urlparse

UNSAFE_CHARACTERS = re.compile(r"[;&|`><$\n\r\x00]")
URL_UNSAFE = re.compile(r"[\s\x00-\x1f\\]")
PATH_TOOLS = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "Grep": "path", "Glob": "path"}


def project_root() -> str:
    """Return the project root with symlinks resolved."""
    return os.path.normcase(os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR", ".")))


def blackbox_settings(root: str) -> dict:
    """Read the blackbox block from the project config."""
    with open(os.path.join(root, ".claude", "project.json"), encoding="utf-8") as config_file:
        return json.load(config_file)["blackbox"]


def resolve(raw_path: str, root: str) -> str:
    """Resolve a path against the root, following symlinks."""
    return os.path.normcase(os.path.realpath(os.path.join(root, raw_path)))


def is_within(resolved: str, targets: list[str]) -> bool:
    """Return True when the resolved path is inside a target."""
    return any(resolved == target or resolved.startswith(target + os.sep) for target in targets)


def url_violation(url: object, settings: dict) -> str | None:
    """Return a reason unless the URL points at an allowed host."""
    if not isinstance(url, str) or URL_UNSAFE.search(url):
        return f"Navigation to '{url}' is blocked."
    parts = urlparse(url)
    hostname = parts.hostname or ""
    is_web = parts.scheme in ("http", "https")
    is_exact_host = hostname in settings["allowedHosts"]
    is_suffix_host = any(hostname.endswith(suffix) for suffix in settings["allowedHostSuffixes"])
    if is_web and (is_exact_host or is_suffix_host):
        return None
    return f"Navigation to '{url}' is blocked. Allowed hosts are listed in .claude/project.json."


def argument_violation(argument: str, root: str, settings: dict) -> str | None:
    """Return a reason unless it is a spec path or safe flag."""
    if any(re.fullmatch(flag, argument) for flag in settings["safeFlags"]):
        return None
    spec_folder = resolve(settings["specFolder"], root)
    if not argument.startswith("-") and is_within(resolve(argument, root), [spec_folder]):
        return None
    return f"Argument '{argument}' is not allowed. Use spec paths under {settings['specFolder']}/ or a safe flag."


def command_violation(command: str, root: str, settings: dict) -> str | None:
    """Return a reason when Bash is not a test or start command."""
    if UNSAFE_CHARACTERS.search(command):
        return "Bash command has chaining, redirection, or control characters."
    try:
        arguments = shlex.split(command)
    except ValueError as error:
        return f"Bash command cannot be parsed: {error}"
    if arguments in settings["startCommands"]:
        return None
    for prefix in settings["testCommands"]:
        if arguments[: len(prefix)] == prefix:
            extras = [argument for argument in arguments[len(prefix):] if argument != "--"]
            reasons = (argument_violation(argument, root, settings) for argument in extras)
            return next((reason for reason in reasons if reason), None)
    return f"Bash may only run the black-box tests or start the app, not: {command}"


def path_violation(tool_name: str, tool_input: dict, root: str, settings: dict) -> str | None:
    """Return a reason when a file tool leaves the allowed folders."""
    pattern = tool_input.get("pattern", "")
    glob_leaves_folders = tool_name == "Glob" and (".." in pattern or os.path.isabs(pattern))
    if glob_leaves_folders:
        return f"Glob pattern leaves the allowed folders: {pattern}"
    raw_path = tool_input.get(PATH_TOOLS[tool_name], "")
    allowed = [resolve(path, root) for path in settings["readablePaths"]]
    if not raw_path or not is_within(resolve(raw_path, root), allowed):
        return f"{tool_name} on '{raw_path}' is blocked. Allowed: {', '.join(settings['readablePaths'])}."
    return None


def find_violation(tool_name: str, tool_input: dict, root: str, settings: dict) -> str | None:
    """Return a reason when the call is not allowed, else None."""
    if tool_name in settings["navigateTools"]:
        return url_violation(tool_input.get("url"), settings)
    if tool_name in settings["allowedTools"]:
        return None
    if tool_name == "Bash":
        return command_violation(tool_input.get("command", ""), root, settings)
    if tool_name in PATH_TOOLS:
        return path_violation(tool_name, tool_input, root, settings)
    return f"Tool '{tool_name}' is not allowed for the blackbox-tester."


def main() -> None:
    """Exit 2 when the tool call is blocked or unreadable."""
    try:
        payload = json.load(sys.stdin)
        root = project_root()
        settings = blackbox_settings(root)
        reason = find_violation(payload["tool_name"], payload.get("tool_input", {}), root, settings)
    except Exception as error:  # noqa: BLE001 - fail closed on any surprise
        reason = f"Hook failed, so the call is blocked: {error!r}"
    if reason:
        print(reason, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

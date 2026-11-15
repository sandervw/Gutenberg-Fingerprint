"""Allow `git push` only to one claude/ branch on origin."""

# Fails closed: any error blocks the call with exit code 2.

from __future__ import annotations

import json
import re
import shlex
import sys

PUSH_COMMAND = re.compile(r"(?:^|[;&|(\n\"'])\s*git(?:\s+-C\s+\S+)*\s+push\b(?P<rest>[^;&|\n]*)")
BRANCH = re.compile(r"claude/[A-Za-z0-9._/-]+")
UPSTREAM_FLAGS = {"-u", "--set-upstream"}
REMOTE = "origin"


def push_problem(rest: str) -> str | None:
    """Explain why one push's arguments are not allowed, or None."""
    words = [word for word in shlex.split(rest) if word not in UPSTREAM_FLAGS]
    is_one_claude_branch = len(words) == 2 and words[0] == REMOTE and BRANCH.fullmatch(words[1]) is not None
    if is_one_claude_branch and ".." not in words[1]:
        return None
    return f"Push blocked: use `git push -u {REMOTE} claude/<branch>` with one branch and no other options."


def command_problem(command: str) -> str | None:
    """Return the first blocked push in a Bash command, or None."""
    problems = (push_problem(match.group("rest")) for match in PUSH_COMMAND.finditer(command))
    return next((problem for problem in problems if problem), None)


def main() -> None:
    """Read the Bash call from stdin and block bad pushes."""
    try:
        problem = command_problem(json.load(sys.stdin)["tool_input"]["command"])
    except (ValueError, KeyError, TypeError) as error:
        problem = f"Push guard error, call blocked: {error!r}"
    if problem is not None:
        print(problem, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

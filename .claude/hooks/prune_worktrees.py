"""After a git push, remove clean worktrees in .claude/worktrees merged into main."""

# Fails loudly: any error is reported to Claude with exit code 2.

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from hook_settings import MAIN_BRANCH, MAIN_REFERENCE, REMOTE

PUSH_COMMAND = re.compile(r"\bgit\s+push\b")
WORKTREE_FOLDER = "/.claude/worktrees/"


def git(folder: str, *arguments: str) -> str:
    """Run a git command in the folder and return its output."""
    return subprocess.run(["git", *arguments], cwd=folder, capture_output=True, text=True, check=True).stdout


def agent_worktrees(folder: str) -> list[str]:
    """List unlocked worktrees under .claude/worktrees, except the current one."""
    current = Path(git(folder, "rev-parse", "--show-toplevel").strip()).resolve()
    paths = []
    for block in git(folder, "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.splitlines()
        path = lines[0].removeprefix("worktree ") if lines else ""
        is_agent_worktree = WORKTREE_FOLDER in path and Path(path).is_dir()
        is_locked = any(line.startswith("locked") for line in lines)
        is_current = is_agent_worktree and Path(path).resolve() == current
        if is_agent_worktree and not is_locked and not is_current:
            paths.append(path)
    return paths


def is_stale(folder: str, path: str) -> bool:
    """Say whether a worktree is clean with every commit on main."""
    if git(path, "status", "--porcelain"):
        return False
    head = git(path, "rev-parse", "HEAD").strip()
    command = ["git", "merge-base", "--is-ancestor", head, MAIN_REFERENCE]
    merged = subprocess.run(command, cwd=folder, capture_output=True, text=True, check=False)
    if merged.returncode not in (0, 1):
        raise subprocess.CalledProcessError(merged.returncode, command, merged.stdout, merged.stderr)
    return merged.returncode == 0


def prune(folder: str) -> list[str]:
    """Remove the stale agent worktrees and return their paths."""
    git(folder, "fetch", "--quiet", REMOTE, MAIN_BRANCH)
    git(folder, "worktree", "prune")
    removed = [path for path in agent_worktrees(folder) if is_stale(folder, path)]
    for path in removed:
        git(folder, "worktree", "remove", path)
    return removed


def main() -> int:
    """Prune worktrees after a push and tell Claude which ones went."""
    payload = json.load(sys.stdin)
    if not PUSH_COMMAND.search(payload.get("tool_input", {}).get("command", "")):
        return 0
    try:
        removed = prune(payload["cwd"])
    except (OSError, KeyError, subprocess.CalledProcessError) as error:
        print(f"worktree prune failed: {error}", file=sys.stderr)
        return 2
    if removed:
        context = {"hookEventName": "PostToolUse", "additionalContext": "Removed stale worktrees:\n" + "\n".join(removed)}
        print(json.dumps({"hookSpecificOutput": context}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

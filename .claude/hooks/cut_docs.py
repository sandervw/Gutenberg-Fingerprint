"""Require the doc-cutter agent on every changed Markdown file."""

# Fails loudly: any error is reported to Claude with exit code 2.

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

CUTTER = "doc-cutter"


def git(folder: Path, *arguments: str) -> str:
    """Run a git command in the folder and return its output."""
    return subprocess.run(["git", *arguments], cwd=folder, capture_output=True, text=True, check=True).stdout


def changed_markdown(repository: Path) -> dict[str, str]:
    """Hash each Markdown file changed on this branch, committed or not."""
    base = git(repository, "merge-base", "HEAD", "origin/main").strip()
    tracked = git(repository, "diff", "--name-only", base).splitlines()
    untracked = git(repository, "ls-files", "--others", "--exclude-standard").splitlines()
    paths = {path for path in tracked + untracked if path.endswith(".md") and (repository / path).is_file()}
    return {path: hashlib.sha256((repository / path).read_bytes()).hexdigest() for path in sorted(paths)}


def state_file(folder: str) -> tuple[Path, Path]:
    """Return the repository root and the cutter's file of seen hashes."""
    repository = Path(git(Path(folder), "rev-parse", "--show-toplevel").strip())
    return repository, repository / git(repository, "rev-parse", "--git-path", "doc-cutter.json").strip()


def record_seen(folder: str) -> None:
    """Mark every changed Markdown file as seen by the cutter."""
    repository, seen_file = state_file(folder)
    seen = json.loads(seen_file.read_text()) if seen_file.is_file() else {}
    seen_file.write_text(json.dumps({**seen, **changed_markdown(repository)}, indent=2))


def unseen_markdown(folder: str) -> list[str]:
    """List changed Markdown files the cutter has not seen yet."""
    repository, seen_file = state_file(folder)
    seen = json.loads(seen_file.read_text()) if seen_file.is_file() else {}
    return [path for path, value in changed_markdown(repository).items() if seen.get(path) != value]


def main() -> int:
    """Record what the cutter saw, or block until it sees everything."""
    try:
        payload = json.load(sys.stdin)
        if payload.get("hook_event_name") == "SubagentStop":
            record_seen(payload["cwd"])
            return 0
        pending = [] if payload.get("agent_type") == CUTTER else unseen_markdown(payload["cwd"])
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"doc cutter hook failed: {error}", file=sys.stderr)
        return 2
    if pending:
        listing = "\n".join(f"- {path}" for path in pending)
        reason = f"Run the `{CUTTER}` agent in the foreground on these files before anything else:\n{listing}"
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

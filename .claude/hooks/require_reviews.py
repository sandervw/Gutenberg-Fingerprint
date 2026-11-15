"""Block `gh pr merge` until review verdicts cover the PR's head commit."""

# Verdicts are PR comments the CTO posts after a reviewer passes.
# Paths and suffixes come from the reviews block of .claude/project.json.
# Fails closed: any error blocks the call with exit code 2.

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

MERGE_COMMAND = re.compile(r"\bgh\s+pr\s+merge\b(?P<rest>[^;&|]*)")


def review_settings() -> dict:
    """Read the reviews block from the project config."""
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    config = json.loads((root / ".claude" / "project.json").read_text(encoding="utf-8"))
    return config["reviews"]


def required_reviews(paths: list[str], settings: dict) -> list[str]:
    """Name the reviews a PR with these changed paths needs."""
    code_suffixes = tuple(settings["codeSuffixes"])
    security_paths = tuple(settings["securityPaths"])
    reviews = []
    if any(path.endswith(code_suffixes) for path in paths):
        reviews.extend(["Simplicity", "Architecture"])
    if any(path.startswith(security_paths) for path in paths):
        reviews.append("Security")
    return reviews


def missing_reviews(required: list[str], comments: list[str], head: str) -> list[str]:
    """List required reviews with no PASS comment for this head commit."""
    short_head = head[:7]
    return [
        review
        for review in required
        if not any(f"{review} review: PASS ({short_head})" in comment for comment in comments)
    ]


def target_in(rest: str) -> str | None:
    """Take the PR number, URL, or branch from the merge arguments."""
    return next((word for word in rest.split() if not word.startswith("-")), None)


def github(command: list[str]) -> str:
    """Run a gh command and return its output, raising on failure."""
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout


def merge_problem(command: str) -> str | None:
    """Explain why this command may not run, or None if it may."""
    match = MERGE_COMMAND.search(command)
    if match is None:
        return None
    target = target_in(match.group("rest"))
    view = ["gh", "pr", "view"] if target is None else ["gh", "pr", "view", target]
    details = json.loads(github([*view, "--json", "number,headRefOid,files,comments"]))
    number = details["number"]
    head = details["headRefOid"]
    paths = [file["path"] for file in details["files"]]
    comments = [comment["body"] for comment in details["comments"]]
    missing = missing_reviews(required_reviews(paths, review_settings()), comments, head)
    if not missing:
        return None
    names = " and ".join(f"{review.lower()}-reviewer" for review in missing)
    verdicts = ", ".join(f'"{review} review: PASS ({head[:7]})"' for review in missing)
    return (
        f"Merge blocked: PR #{number} needs {names} on commit {head[:7]}. "
        f"Run each, fix every FAIL, then post {verdicts} with gh pr comment {number}."
    )


def main() -> None:
    """Read the Bash call from stdin and block it when needed."""
    try:
        problem = merge_problem(json.load(sys.stdin)["tool_input"]["command"])
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        problem = f"Merge gate error, call blocked: {error!r}"
    if problem is not None:
        print(problem, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

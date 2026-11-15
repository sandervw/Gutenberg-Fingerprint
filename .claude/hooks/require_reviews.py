"""Block `gh pr merge` until review verdicts cover the PR's head commit."""

# Verdicts are owner PR comments posted after a reviewer passes.
# Fails closed: any error blocks the call with exit code 2.

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass

from hook_settings import project_section

MERGE_COMMAND = re.compile(r"\bgh\b[^;&|\n]*?\bpr\s+merge\b(?P<rest>[^;&|\n]*)")
METHOD_FLAGS = {"--merge", "--squash", "--rebase", "--delete-branch", "-m", "-s", "-r", "-d"}
TRUSTED_AUTHOR = "OWNER"
PIN_FLAG = "--match-head-commit"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
MERGE_USAGE = f"`gh pr merge <number> --merge {PIN_FLAG} <full sha>`"
FILES_QUERY = ".[] | .filename, (.previous_filename // empty)"
CHAINING = re.compile(r"[;&|\n`]|\$\(")


@dataclass(frozen=True)
class MergeRequest:
    """A plain merge of one PR, pinned to one head commit."""

    number: str
    head: str


@dataclass(frozen=True)
class ReviewSettings:
    """Which changed paths need which reviews."""

    code_suffixes: tuple[str, ...]
    security_paths: tuple[str, ...]


def review_settings() -> ReviewSettings:
    """Parse the reviews block of the project config."""
    config = project_section("reviews")
    return ReviewSettings(tuple(config["codeSuffixes"]), tuple(config["securityPaths"]))


def verdict(review: str, head: str) -> str:
    """Return the PASS comment text for a review on a commit."""
    return f"{review} review: PASS ({head[:7]})"


def required_reviews(paths: list[str], settings: ReviewSettings) -> list[str]:
    """Name the reviews a PR with these changed paths needs."""
    reviews = []
    if any(path.endswith(settings.code_suffixes) for path in paths):
        reviews.extend(["Simplicity", "Architecture"])
    if any(path.startswith(settings.security_paths) for path in paths):
        reviews.append("Security")
    return reviews


def missing_reviews(required: list[str], comments: list[str], head: str) -> list[str]:
    """List required reviews with no PASS comment for this head commit."""
    return [review for review in required if not any(verdict(review, head) in comment for comment in comments)]


def parse_merge(rest: str) -> MergeRequest | None:
    """Parse a plain, head-pinned merge, or return None."""
    words = shlex.split(rest)
    pin_at = words.index(PIN_FLAG) if PIN_FLAG in words else len(words)
    pinned = words[pin_at + 1] if pin_at + 1 < len(words) else ""
    others = words[:pin_at] + words[pin_at + 2:]
    numbers = [word for word in others if word.isdigit()]
    others_are_methods = all(word in METHOD_FLAGS for word in others if not word.isdigit())
    is_plain = len(numbers) == 1 and others_are_methods and FULL_SHA.fullmatch(pinned) is not None
    return MergeRequest(numbers[0], pinned) if is_plain else None


def changed_paths(number: str) -> list[str]:
    """List every path a PR touches, including rename sources."""
    endpoint = f"repos/{{owner}}/{{repo}}/pulls/{number}/files"
    return github(["gh", "api", endpoint, "--paginate", "--jq", FILES_QUERY]).splitlines()


def github(command: list[str]) -> str:
    """Run a gh command and return its output, raising on failure."""
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def merge_problem(command: str) -> str | None:
    """Explain why any merge in this command may not run, or None."""
    matches = list(MERGE_COMMAND.finditer(command))
    if matches and CHAINING.search(command):
        return f"Merge blocked: run {MERGE_USAGE} as its own command."
    problems = (pull_request_problem(match.group("rest")) for match in matches)
    return next((problem for problem in problems if problem), None)


def pull_request_problem(rest: str) -> str | None:
    """Explain why one merge may not run, or None if it may."""
    request = parse_merge(rest)
    if request is None:
        return f"Merge blocked for {rest.strip()!r}: use {MERGE_USAGE}, nothing else."
    number = request.number
    details = json.loads(github(["gh", "pr", "view", number, "--json", "headRefOid,comments"]))
    head = details["headRefOid"]
    if request.head != head:
        return f"Merge blocked: PR #{number} head is {head}, not {request.head}. Re-review it."
    paths = changed_paths(number)
    owner_comments = [
        comment["body"] for comment in details["comments"] if comment["authorAssociation"] == TRUSTED_AUTHOR
    ]
    missing = missing_reviews(required_reviews(paths, review_settings()), owner_comments, head)
    if not missing:
        return None
    names = " and ".join(f"{review.lower()}-reviewer" for review in missing)
    verdicts = ", ".join(f'"{verdict(review, head)}"' for review in missing)
    return (
        f"Merge blocked: PR #{number} needs {names} on commit {head}. "
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

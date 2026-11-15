"""Git names and project config the hooks share."""

from __future__ import annotations

import json
import os
from pathlib import Path

REMOTE = "origin"
MAIN_BRANCH = "main"
MAIN_REFERENCE = f"{REMOTE}/{MAIN_BRANCH}"
SEPARATORS = ";&|\n"
COMMAND_TEXT = f"[^{SEPARATORS}]"


def project_root() -> Path:
    """Return the project folder Claude runs the hooks in."""
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def project_section(name: str) -> dict:
    """Return one named block of .claude/project.json."""
    config_path = project_root() / ".claude" / "project.json"
    return json.loads(config_path.read_text(encoding="utf-8"))[name]

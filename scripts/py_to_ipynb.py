# Ship-time converter: a `# %%`-sectioned .py -> minimal nbformat-4 .ipynb,
# the documented import format for Fabric notebooks (fab import --format .ipynb).
# Usage: uv run python scripts/py_to_ipynb.py <src.py> <dest.ipynb>

from __future__ import annotations

import json
import sys
from pathlib import Path

CELL_MARKER = "# %%"


def split_cells(source: str) -> list[str]:
    """Split on lines opening with the cell marker; drop empty cells."""
    groups: list[list[str]] = [[]]
    for line in source.splitlines():
        if line.startswith(CELL_MARKER):
            groups.append([line])
        else:
            groups[-1].append(line)
    return ["\n".join(g).strip("\n") for g in groups if any(s.strip() for s in g)]


def to_ipynb(cells: list[str]) -> dict[str, object]:
    """Minimal nbformat-4 body per the Fabric notebook-definition doc."""
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "cells": [
            {
                "cell_type": "code",
                "source": [f"{line}\n" for line in cell.splitlines()],
                "execution_count": None,
                "outputs": [],
                "metadata": {},
            }
            for cell in cells
        ],
        "metadata": {"language_info": {"name": "python"}},
    }


def main(src: Path, dest: Path) -> None:
    with src.open("r", encoding="utf-8") as fh:
        cells = split_cells(fh.read())
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        json.dump(to_ipynb(cells), fh, ensure_ascii=False, indent=1)
    print(f"{src} -> {dest} ({len(cells)} cells)")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))

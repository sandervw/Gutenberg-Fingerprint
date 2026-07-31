# Ship-time converter: a `# %%`-sectioned .py -> minimal nbformat-4 .ipynb,
# the documented import format for Fabric notebooks (fab import --format .ipynb).
# Usage: uv run python scripts/py_to_ipynb.py <src.py> <dest.ipynb>

from __future__ import annotations

import json
import sys
from pathlib import Path

CELL_MARKER = "# %%"

# Metadata mirrors a portal-exported Python-kernel notebook (fab export,
# 2026-07-11). Without kernel_info/kernelspec, Fabric defaults an imported
# notebook to the Spark kernel, where polars/deltalake do not exist.
KERNEL_METADATA: dict[str, object] = {
    "kernel_info": {"name": "jupyter", "jupyter_kernel_name": "python3.12"},
    "kernelspec": {"name": "jupyter", "display_name": "Jupyter"},
    "language_info": {"name": "python"},
    "microsoft": {"language": "python", "language_group": "jupyter_python"},
}

# Default-lakehouse binding (lh_bronze). Imports without it leave the
# notebook detached, so /lakehouse/default/ never mounts.
LAKEHOUSE_DEPENDENCY: dict[str, object] = {
    "lakehouse": {
        "known_lakehouses": [{"id": "1cebda9c-5c4f-47bb-a82a-4820a7fdf71f"}],
        "default_lakehouse": "1cebda9c-5c4f-47bb-a82a-4820a7fdf71f",
        "default_lakehouse_name": "lh_bronze",
        "default_lakehouse_workspace_id": "bfad3948-6e3b-4eeb-8ee1-485e0f47c87b",
    }
}

CELL_METADATA: dict[str, object] = {
    "microsoft": {"language": "python", "language_group": "jupyter_python"}
}


def split_cells(source: str) -> list[str]:
    """Split on lines opening with the cell marker; drop empty cells. A bare
    marker starts a cell without the marker line itself, for magic-only cells:
    Fabric's %run refuses to share a cell with any other code or magic."""
    groups: list[list[str]] = [[]]
    for line in source.splitlines():
        if line.startswith(CELL_MARKER):
            groups.append([] if line.strip() == CELL_MARKER else [line])
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
                "metadata": CELL_METADATA,
            }
            for cell in cells
        ],
        "metadata": {**KERNEL_METADATA, "dependencies": LAKEHOUSE_DEPENDENCY},
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

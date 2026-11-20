# Site extract: run each page's .sql once, writing .json beside it.

from __future__ import annotations

from pathlib import Path

from python import storage
from python.core.site_rows import rows_as_text

ROUTES: Path = storage.REPOSITORY_ROOT / "site" / "src" / "routes"


def main() -> None:
    """Write every route query's rows to a .json file beside its query."""
    query_files = sorted(ROUTES.rglob("*.sql"))
    for query_file in query_files:
        rows = storage.read_query(query_file.read_text(encoding="utf-8"))
        query_file.with_suffix(".json").write_text(rows_as_text(rows), encoding="utf-8", newline="\n")
    storage.emit("site_queries", len(query_files))


if __name__ == "__main__":
    main()

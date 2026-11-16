# Strip: bronze texts -> silver corpus markdown, minus PG boilerplate.

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import polars

from python import storage
from python.core.ledger import UTC_DATETIME_TYPE
from python.core.strip import author_folder, display_author, title_slug, to_markdown

TEXTS_ROOT: Path = storage.file_path("bronze/texts")
SELF_ROOT: Path = storage.file_path("bronze/self")


def main() -> None:
    """Rebuild the silver corpus from bronze texts and self works."""
    run_time = datetime.now(timezone.utc)
    corpus_root = storage.file_path("silver/corpus")

    roster = storage.read_table("raw.raw_works", columns=["gutenberg_id", "title", "authors"])

    if corpus_root.exists():
        shutil.rmtree(corpus_root)  # derived layer: full rebuild keeps it roster-shaped
    corpus_root.mkdir(parents=True)

    stripped = failed = missing = 0
    for row in roster.sort("gutenberg_id").iter_rows(named=True):
        source = TEXTS_ROOT / f"{row['gutenberg_id']}.txt"
        if not source.exists():
            missing += 1
            continue
        author = display_author(row["authors"] or "")
        title = row["title"] or ""
        try:
            markdown = to_markdown(source.read_bytes(), title, author)
        except ValueError as error:
            print(f"{row['gutenberg_id']}: {error}")
            failed += 1
            continue
        filename = f"{row['gutenberg_id']}-{title_slug(title)}.md"
        destination = corpus_root / author_folder(author) / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(markdown, encoding="utf-8", newline="\n")
        stripped += 1

    # Self corpus is already clean markdown: promote as-is
    promoted = 0
    if SELF_ROOT.exists():
        self_destination = corpus_root / storage.SELF_FOLDER
        self_destination.mkdir(exist_ok=True)
        for source in sorted(SELF_ROOT.glob("*.md")):
            shutil.copyfile(source, self_destination / source.name)
            promoted += 1

    audit = polars.DataFrame(
        [(run_time, roster.height, stripped, failed, missing)],
        schema={
            "run_ts": UTC_DATETIME_TYPE, "roster_size": polars.Int64,
            "stripped": polars.Int64, "failed": polars.Int64, "missing_text": polars.Int64,
        },
        orient="row",
    )
    storage.write_table("bronze.strip_audit", audit, mode="append")
    print(f"corpus: {stripped:,} written, {failed:,} failed, {missing:,} missing, {promoted} self -> {corpus_root}")


if __name__ == "__main__":
    main()

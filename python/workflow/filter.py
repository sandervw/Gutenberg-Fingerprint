# Filter: bronze catalog -> raw_works (English SF/fantasy), plus CDC gate count.

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl

from python.helpers import storage

# %% Scope + genre - checks both subjects (LCSH) and bookshelves

SUBJECTS: pl.Expr = pl.col("subjects").fill_null("")
SHELVES: pl.Expr = pl.col("bookshelves").fill_null("")


def shelf_token(pattern: str) -> pl.Expr:
    """Whole-shelf match; the column is a '; '-joined list."""
    return SHELVES.str.contains(rf"(^|; ){pattern}($|;)")


SF_CORE: pl.Expr = SUBJECTS.str.contains("(?i)science fiction") | shelf_token(
    "(Science Fiction|Science Fiction by Women|Precursors of Science Fiction)"
)
FANTASY_CORE: pl.Expr = SUBJECTS.str.contains("(?i)fantas") | shelf_token("Fantasy")
SFF_SHELF: pl.Expr = shelf_token("Category: Science-Fiction & Fantasy")

SF_THEME: pl.Expr = SUBJECTS.str.contains(
    "(?i)interplanetary|space flight|time travel|robot|extraterrestrial|outer space"
    "|life on other planets|end of the world|utopia|dystopia"
)
FANTASY_THEME: pl.Expr = SUBJECTS.str.contains(
    "(?i)fairy tal|fairies|magic|mythology|folklore|dragons|witch|wizard"
    "|ghost stories|supernatural|imaginary places|legends"
)

ABOUT_SUBDIVISION: str = (
    r"(?i)--\s*(history and criticism|authorship|criticism|bibliograph"
    r"|study and teaching|biography|congresses|dictionaries|indexes)"
)
IS_ABOUT: pl.Expr = (
    SUBJECTS.str.split("; ")
    .list.eval(
        pl.element().str.contains(ABOUT_SUBDIVISION)
        & pl.element().str.contains(r"(?i)--\s*fiction").not_()
    )
    .list.any()
)

IN_SCOPE: pl.Expr = (SF_CORE | FANTASY_CORE | SFF_SHELF) & IS_ABOUT.not_()

GENRE: pl.Expr = (
    pl.when((SF_CORE | SF_THEME) & (FANTASY_CORE | FANTASY_THEME).not_())
    .then(pl.lit("Sci-Fi"))
    .when((FANTASY_CORE | FANTASY_THEME) & (SF_CORE | SF_THEME).not_())
    .then(pl.lit("Fantasy"))
    .otherwise(pl.lit("Undetermined"))
)

# %% Run

if __name__ == "__main__":
    catalog_df: pl.DataFrame = storage.read_table("bronze.catalog")

    raw_works_df: pl.DataFrame = catalog_df.filter(
        (pl.col("type") == "Text") & (pl.col("language") == "en") & IN_SCOPE
    ).with_columns(GENRE.alias("genre"))

    storage.write_table("raw.raw_works", raw_works_df, mode="overwrite")

    by_genre: dict[str, int] = dict(
        raw_works_df.group_by("genre").len().sort("genre").iter_rows()
    )
    print(f"raw_works: kept {raw_works_df.height:,} of {catalog_df.height:,} catalog rows")
    print(f"genre split: {by_genre}")

    # CDC diff - in-scope set vs watermark, logged to ingest_audit
    joined: pl.DataFrame = raw_works_df.select("gutenberg_id", "catalog_row_hash").join(
        storage.read_table("bronze.watermark").select(
            "gutenberg_id", pl.col("catalog_row_hash").alias("seen_hash")
        ),
        on="gutenberg_id",
        how="left",
    )
    candidate_new: int = joined.filter(pl.col("seen_hash").is_null()).height
    candidate_changed: int = joined.filter(
        pl.col("seen_hash").is_not_null()
        & (pl.col("seen_hash") != pl.col("catalog_row_hash"))
    ).height
    audit_row: pl.DataFrame = pl.DataFrame(
        {
            "run_ts": [datetime.now(timezone.utc)],
            "run_type": ["catalog_refresh"],
            "books_in_catalog": [catalog_df.height],
            "candidate_new": [candidate_new],
            "candidate_changed": [candidate_changed],
            "downloaded": [0],  # text_ingest.py logs the real downloads
            "failed": [0],
        },
        schema={
            "run_ts": storage.UTC_DATETIME_TYPE,
            "run_type": pl.Utf8,
            "books_in_catalog": pl.Int64,
            "candidate_new": pl.Int64,
            "candidate_changed": pl.Int64,
            "downloaded": pl.Int64,
            "failed": pl.Int64,
        },
    )
    storage.write_table("bronze.ingest_audit", audit_row, mode="append")
    print(f"new in-scope works: {candidate_new:,} | changed: {candidate_changed:,}")

    storage.emit("new_count", candidate_new + candidate_changed)

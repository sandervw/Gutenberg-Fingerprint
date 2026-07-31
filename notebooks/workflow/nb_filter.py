# Fabric notebook: nb_filter
# Bronze Tables/catalog -> silver Tables/dbo/raw_works: keep English science-fiction
# and fantasy texts, drop the rest.
# lh_silver is schema-enabled: tables must sit under a schema folder or land "Unidentified".
# Also holds the pipeline's CDC gate: the diff only means anything against the
# in-scope subset, since out-of-scope books never enter the watermark.

from __future__ import annotations

from datetime import datetime, timezone

import notebookutils
import polars as pl
from deltalake import DeltaTable, write_deltalake

ONELAKE: str = "abfss://gutenberg-fingerprint@onelake.dfs.fabric.microsoft.com"
CATALOG_TABLE: str = f"{ONELAKE}/lh_bronze.Lakehouse/Tables/catalog"
WATERMARK_TABLE: str = f"{ONELAKE}/lh_bronze.Lakehouse/Tables/watermark"
AUDIT_TABLE: str = f"{ONELAKE}/lh_bronze.Lakehouse/Tables/ingest_audit"
RAW_WORKS_TABLE: str = f"{ONELAKE}/lh_silver.Lakehouse/Tables/dbo/raw_works"

STORAGE_OPTIONS: dict[str, str] = {
    "bearer_token": notebookutils.credentials.getToken("storage"),
    "use_fabric_endpoint": "true",
}

catalog_df: pl.DataFrame = pl.from_arrow(
    DeltaTable(CATALOG_TABLE, storage_options=STORAGE_OPTIONS).to_pyarrow_table()
)

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

raw_works_df: pl.DataFrame = catalog_df.filter(
    (pl.col("type") == "Text") & (pl.col("language") == "en") & IN_SCOPE
).with_columns(GENRE.alias("genre"))

write_deltalake(
    RAW_WORKS_TABLE,
    raw_works_df.to_arrow(),
    mode="overwrite",
    schema_mode="overwrite",
    storage_options=STORAGE_OPTIONS,
)
DeltaTable(RAW_WORKS_TABLE, storage_options=STORAGE_OPTIONS).create_checkpoint()

by_genre: dict[str, int] = dict(
    raw_works_df.group_by("genre").len().sort("genre").iter_rows()
)
print(f"raw_works: kept {raw_works_df.height:,} of {catalog_df.height:,} catalog rows")
print(f"genre split: {by_genre}")

# %% CDC diff - fantasy set vs watermark, logged to ingest_audit

joined: pl.DataFrame = raw_works_df.select("gutenberg_id", "catalog_row_hash").join(
    pl.from_arrow(
        DeltaTable(WATERMARK_TABLE, storage_options=STORAGE_OPTIONS).to_pyarrow_table()
    ).select("gutenberg_id", pl.col("catalog_row_hash").alias("seen_hash")),
    on="gutenberg_id",
    how="left",
)
candidate_new: int = joined.filter(pl.col("seen_hash").is_null()).height
candidate_changed: int = joined.filter(
    pl.col("seen_hash").is_not_null() & (pl.col("seen_hash") != pl.col("catalog_row_hash"))
).height
audit_row: pl.DataFrame = pl.DataFrame(
    {
        "run_ts": [datetime.now(timezone.utc)],
        "run_type": ["catalog_refresh"],
        "books_in_catalog": [catalog_df.height],
        "candidate_new": [candidate_new],
        "candidate_changed": [candidate_changed],
        "downloaded": [0],  # nb_text_ingest logs the real downloads
        "failed": [0],
    }
)
write_deltalake(AUDIT_TABLE, audit_row.to_arrow(), mode="append", storage_options=STORAGE_OPTIONS)
print(f"new in-scope works: {candidate_new:,} | changed: {candidate_changed:,}")

# %% Gate - own cell, exit() overwrites its cell's output

notebookutils.notebook.exit(str(candidate_new + candidate_changed))

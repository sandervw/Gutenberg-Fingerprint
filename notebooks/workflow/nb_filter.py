# Fabric notebook: nb_filter
# Bronze Tables/catalog -> silver Tables/dbo/raw_works: keep English fantasy texts, drop the rest.
# lh_silver is schema-enabled: tables must sit under a schema folder or land "Unidentified".
# Also holds the pipeline's CDC gate: the diff only means anything against the
# fantasy subset, since non-fantasy books never enter the watermark.

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

is_fantasy = pl.col("subjects").fill_null("").str.contains("(?i)fantasy") | pl.col(
    "bookshelves"
).fill_null("").str.contains(r"(^|; )Fantasy($|;)")

raw_works_df: pl.DataFrame = catalog_df.filter(
    (pl.col("type") == "Text") & (pl.col("language") == "en") & is_fantasy
)

write_deltalake(
    RAW_WORKS_TABLE,
    raw_works_df.to_arrow(),
    mode="overwrite",
    schema_mode="overwrite",
    storage_options=STORAGE_OPTIONS,
)
DeltaTable(RAW_WORKS_TABLE, storage_options=STORAGE_OPTIONS).create_checkpoint()
print(f"raw_works: kept {raw_works_df.height:,} of {catalog_df.height:,} catalog rows")

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
print(f"new fantasy works: {candidate_new:,} | changed: {candidate_changed:,}")

# %% Gate - own cell, exit() overwrites its cell's output

notebookutils.notebook.exit(str(candidate_new + candidate_changed))

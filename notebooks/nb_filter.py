# Fabric notebook: nb_filter
# Bronze Tables/catalog -> silver Tables/dbo/raw_works: keep English fantasy texts, drop the rest.
# lh_silver is schema-enabled: tables must sit under a schema folder or land "Unidentified".

from __future__ import annotations

import notebookutils
import polars as pl
from deltalake import DeltaTable, write_deltalake

ONELAKE: str = "abfss://gutenberg-fingerprint@onelake.dfs.fabric.microsoft.com"
CATALOG_TABLE: str = f"{ONELAKE}/lh_bronze.Lakehouse/Tables/catalog"
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

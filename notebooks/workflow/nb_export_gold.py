# Fabric notebook: nb_export_gold
# wh_gold gold marts (dim_*/fact_*/mart_*) -> lh_silver Files/exports/*.parquet.

from __future__ import annotations

from pathlib import Path

import notebookutils
import polars as pl

WAREHOUSE: str = "wh_gold"
EXPORT_LAKEHOUSE: str = "abfss://gutenberg-fingerprint@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse"
EXPORT_SUBDIR: str = "Files/exports"
EXPORT_PREFIXES: tuple[str, ...] = ("dim_", "fact_", "mart_")

conn = notebookutils.data.connect_to_artifact(WAREHOUSE)

# Physical tables only (staging/intermediate materialize as views)
table_names = pl.from_pandas(
    conn.query(
        "SELECT TABLE_NAME AS tname FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = 'dbo' AND TABLE_TYPE = 'BASE TABLE'"
    )
)["tname"].to_list()
tables = sorted(t for t in table_names if t.startswith(EXPORT_PREFIXES))
if not tables:
    raise RuntimeError(f"No dim_/fact_/mart_ base tables found in {WAREHOUSE}")

# Mount the destination so polars can write parquet to a local path.
notebookutils.fs.mount(EXPORT_LAKEHOUSE, "/export")
export_root = Path(notebookutils.fs.getMountPath("/export")) / EXPORT_SUBDIR
export_root.mkdir(parents=True, exist_ok=True)

for name in tables:
    frame = pl.from_pandas(conn.query(f"SELECT * FROM dbo.{name}"))
    frame.write_parquet(export_root / f"{name}.parquet")
    print(f"{name}: {frame.height:,} rows -> {EXPORT_SUBDIR}/{name}.parquet")

print(f"Exported {len(tables)} gold tables to {EXPORT_LAKEHOUSE}/{EXPORT_SUBDIR}")

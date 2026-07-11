# Fabric notebook: nb_catalog_ingest
#
# Writes, per run:
#   Files/catalog/pg_catalog_<date>.csv  raw feed snapshot, byte-for-byte
#   Tables/catalog                       full catalog photo, overwritten each run
#   Tables/watermark                     CDC ledger; created once, filled by backfill
#   Tables/ingest_audit                  one row per run: diff counts vs the watermark

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import notebookutils
import polars as pl
import pyarrow as pa
import requests
from deltalake import DeltaTable, write_deltalake

# PG regenerates this feed weekly
CATALOG_URL: str = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
USER_AGENT: str = "gutenberg-fingerprint-pipeline/0.1 (contact: samvanwilligen@gmail.com)"

FILES_ROOT: Path = Path("/lakehouse/default/Files")

ONELAKE_TABLES: str = (
    "abfss://gutenberg-fingerprint@onelake.dfs.fabric.microsoft.com"
    "/lh_bronze.Lakehouse/Tables"
)
CATALOG_TABLE: str = f"{ONELAKE_TABLES}/catalog"
WATERMARK_TABLE: str = f"{ONELAKE_TABLES}/watermark"
AUDIT_TABLE: str = f"{ONELAKE_TABLES}/ingest_audit"

# OneLake token, roughly one hour of life, plenty for a single run
STORAGE_OPTIONS: dict[str, str] = {
    "bearer_token": notebookutils.credentials.getToken("storage"),
    "use_fabric_endpoint": "true",
}

# Every timestamp tz-aware UTC
TS_UTC: pl.Datetime = pl.Datetime("us", "UTC")


# %% Download - one polite GET, streamed into Files/


def download_catalog(url: str, dest: Path, timeout_s: float = 120.0) -> int:
    """Stream the catalog feed to dest; return bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with requests.get(
        url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=timeout_s
    ) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                written += fh.write(chunk)
    return written


# %% Parse - normalize columns, hash rows


def normalize_column(name: str) -> str:
    """'Text#' -> 'text', 'LoCC' -> 'locc', 'Bookshelves' -> 'bookshelves'."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def row_hashes(df: pl.DataFrame, id_col: str = "gutenberg_id") -> pl.Series:
    """sha256 per row over every non-id field, in column order."""
    payload_cols = [c for c in df.columns if c != id_col]
    # \x1f (unit separator) between fields
    payload = df.select(
        pl.concat_str(
            [pl.col(c).fill_null("") for c in payload_cols], separator="\x1f"
        ).alias("payload")
    )["payload"]
    return pl.Series(
        "catalog_row_hash",
        [hashlib.sha256(s.encode("utf-8")).hexdigest() for s in payload],
    )


def load_catalog(csv_path: Path, run_ts: datetime) -> pl.DataFrame:
    # infer_schema_length=0 keeps every column as text
    df = pl.read_csv(csv_path, infer_schema_length=0)
    df = df.rename({c: normalize_column(c) for c in df.columns})
    if "text" not in df.columns:
        raise KeyError(f"expected a 'Text#' column in the feed, got: {df.columns}")
    df = df.rename({"text": "gutenberg_id"}).with_columns(
        pl.col("gutenberg_id").cast(pl.Int64)  # strict cast: format drift should fail loudly
    )
    return df.with_columns(
        row_hashes(df).alias("catalog_row_hash"),
        pl.lit(f"{run_ts:%Y-%m-%d}").alias("snapshot_date"),
        pl.lit(run_ts, dtype=TS_UTC).alias("loaded_at"),
    )


# %% Write - catalog photo via delta-rs


def write_catalog(df: pl.DataFrame, table_uri: str) -> None:
    write_deltalake(
        table_uri,
        df.to_arrow(),
        mode="overwrite",
        schema_mode="overwrite",
        storage_options=STORAGE_OPTIONS,
    )
    # Manual checkpoint per run keeps the log short
    DeltaTable(table_uri, storage_options=STORAGE_OPTIONS).create_checkpoint()


# %% Watermark - create once, never overwrite

WATERMARK_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("gutenberg_id", pa.int64()),
        pa.field("catalog_row_hash", pa.string()),  # catalog row as last processed
        pa.field("text_hash", pa.string()),  # sha256 of downloaded text; backfill fills it
        pa.field("first_seen", pa.timestamp("us", tz="UTC")),
        pa.field("last_changed", pa.timestamp("us", tz="UTC")),
        pa.field("status", pa.string()),  # pending | ingested | failed | excluded
    ]
)


def ensure_watermark(table_uri: str) -> DeltaTable:
    # mode="ignore": create only when absent
    return DeltaTable.create(
        table_uri, schema=WATERMARK_SCHEMA, mode="ignore", storage_options=STORAGE_OPTIONS
    )


# %% CDC diff - catalog photo vs watermark ledger


@dataclass(frozen=True)
class CdcCounts:
    books_in_catalog: int
    candidate_new: int
    candidate_changed: int


def diff_counts(catalog: pl.DataFrame, watermark: DeltaTable) -> CdcCounts:
    wm = pl.from_arrow(watermark.to_pyarrow_table())
    wm = wm.select("gutenberg_id", "catalog_row_hash").rename({"catalog_row_hash": "seen_hash"})
    joined = catalog.select("gutenberg_id", "catalog_row_hash").join(
        wm, on="gutenberg_id", how="left"
    )
    return CdcCounts(
        books_in_catalog=joined.height,
        candidate_new=joined.filter(pl.col("seen_hash").is_null()).height,
        candidate_changed=joined.filter(
            pl.col("seen_hash").is_not_null()
            & (pl.col("seen_hash") != pl.col("catalog_row_hash"))
        ).height,
    )


def write_audit(counts: CdcCounts, run_ts: datetime, table_uri: str) -> None:
    row = pl.DataFrame(
        {
            "run_ts": [run_ts],
            "run_type": ["catalog_refresh"],
            "books_in_catalog": [counts.books_in_catalog],
            "candidate_new": [counts.candidate_new],
            "candidate_changed": [counts.candidate_changed],
            "downloaded": [0],  # backfill and CDC runs count real downloads here
            "failed": [0],
        },
        schema={
            "run_ts": TS_UTC,
            "run_type": pl.Utf8,
            "books_in_catalog": pl.Int64,
            "candidate_new": pl.Int64,
            "candidate_changed": pl.Int64,
            "downloaded": pl.Int64,
            "failed": pl.Int64,
        },
    )
    write_deltalake(table_uri, row.to_arrow(), mode="append", storage_options=STORAGE_OPTIONS)


# %% Run

run_ts: datetime = datetime.now(timezone.utc)
raw_path: Path = FILES_ROOT / "catalog" / f"pg_catalog_{run_ts:%Y-%m-%d}.csv"

raw_bytes: int = download_catalog(CATALOG_URL, raw_path)
print(f"raw feed -> {raw_path} ({raw_bytes:,} bytes)")

catalog_df: pl.DataFrame = load_catalog(raw_path, run_ts)
print(f"parsed {catalog_df.height:,} rows, {catalog_df.width} columns")

write_catalog(catalog_df, CATALOG_TABLE)
watermark: DeltaTable = ensure_watermark(WATERMARK_TABLE)
counts: CdcCounts = diff_counts(catalog_df, watermark)
write_audit(counts, run_ts, AUDIT_TABLE)

print(
    f"catalog: {counts.books_in_catalog:,} books | "
    f"new vs watermark: {counts.candidate_new:,} | changed: {counts.candidate_changed:,}"
)
